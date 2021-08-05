import logging
from dataclasses import dataclass
from typing import Dict
import asyncio

import aiohttp

from .config import WEBSERV_URL
from .docker import Docker
from .exploit import Exploit
from .repo import Repo
from .task import Task

logger = logging.getLogger(__name__)


@dataclass
class Team:
    id: int
    name: str
    slug: str
    aux: str


@dataclass
class Problem:
    id: int
    enabled: bool
    name: str
    slug: str
    aux: str


class Runtime:
    repo: Repo
    docker: Docker
    exploits: Dict[str, Exploit]

    current_round: int

    # team slug -> team
    teams: Dict[str, Team]

    # problem slug -> team
    problems: Dict[str, Problem]

    def __init__(self, repo: Repo, docker: Docker):
        self.repo = repo
        self.docker = docker
        self.exploits = {}

        self.current_round = -1

        self.teams = {}
        self.problems = {}

        self.main_loop_lock = asyncio.Lock()

    async def connect(self) -> None:
        await self.repo.connect()
        await self.refresh()

    async def disconnect(self) -> None:
        pass

    async def main_loop(self):
        while True:
            async with self.main_loop_lock:
                containers = self.docker.get_managed_containers()
                tasks = []

                for container in containers:
                    try:
                        exploit_id = container["Config"]["Labels"][
                            "fireball.exploit_id"
                        ]
                    except KeyError:
                        logger.warning(
                            "Found a managed container without exploit_id: %s",
                            container.id,
                        )
                        continue

                    if exploit_id not in self.exploits:
                        logger.warning("Couldn't find exploit with id:", exploit_id)
                        continue

                    exploit = self.exploits[exploit_id]
                    tasks.append(Task(exploit, container))

                statuses = await asyncio.gather(
                    *[task.status() for task in tasks], return_exceptions=True
                )

                for status, task in zip(statuses, tasks):
                    if isinstance(status, Exception):
                        logger.error(
                            "An error occured while querying status of %s task: %s",
                            task.id,
                            status,
                        )
                        continue

                    # TODO: send status to siren

    async def refresh(self) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.get(WEBSERV_URL + "/api/teams") as response:
                self.teams.clear()
                logger.info("=== Teams ===")
                for team in await response.json():
                    logger.info(team)
                    self.teams[team["slug"]] = Team(**team)

            async with session.get(WEBSERV_URL + "/api/problems") as response:
                self.problems.clear()
                logger.info("=== Problems ===")
                for problem in await response.json():
                    logger.info(problem)
                    self.problems[problem["slug"]] = Problem(**problem)

    async def game_tick(self, round_id: int) -> None:
        self.current_round = round_id
        logger.info(f"New tick {round_id}")

        for exploit_id in self.exploits.keys():
            await self.start_exploit(exploit_id)

    async def repo_scan(self) -> None:
        result = await self.repo.scan()
        if result is None:
            return

        # Be careful! The term "exploit ID" refers to different things
        # on the web server and the task runner
        async with aiohttp.ClientSession() as session:
            for path in result.removed_exploits:
                chal_name = path.parts[0]
                exploit_name = path.parts[1]
                exploit_id = f"{chal_name}:{exploit_name}"
                logger.info(f"Deleting exploit {exploit_id}")

                del self.exploits[exploit_id]
                async with session.delete(
                    WEBSERV_URL + "/api/exploits",
                    data={
                        "name": exploit_name,
                        "problemId": self.problems[chal_name].id,
                    },
                ) as response:
                    logger.debug(f"Web server response: {response.status}")

            for path in result.updated_exploits:
                chal_name = path.parts[0]
                exploit_name = path.parts[1]
                exploit_id = f"{chal_name}:{exploit_name}"
                logger.info(f"Updating exploit {exploit_id}")

                try:
                    exploit = await Exploit.from_path(
                        self, self.repo.path / path, exploit_name, chal_name
                    )
                    self.exploits[exploit_id] = exploit
                except Exception as e:
                    # TODO: proper logging
                    logger.error("%s", e)

                async with session.post(
                    WEBSERV_URL + "/api/exploits",
                    data={
                        "name": exploit_name,
                        "key": exploit.docker_image_hash,
                        "problemId": self.problems[chal_name].id,
                    },
                ) as response:
                    logger.debug(f"Web server response: {response.status}")
                    logger.debug(await response.json())

                # Run the updated exploit
                self.start_exploit(exploit_id)

    async def start_exploit(self, exploit_id: str) -> None:
        if self.current_round < 0:
            # Skip if the contest is not running right now
            pass

        logger.info(f"Running exploit {exploit_id}")

        async with aiohttp.ClientSession() as session:
            exploit = self.exploits[exploit_id]
            if exploit.enabled:
                for team in self.teams.values():
                    if team not in exploit.ignore_teams:
                        logger.debug(f"Running exploit {exploit_id} against team {team.name}")

                        async with session.post(
                            WEBSERV_URL + "/api/endpoint",
                            data={
                                "teamId": team.id,
                                "problemId": self.problems[exploit.chal_name].id,
                            },
                        ) as response:
                            endpoint = await response.json()

                        async with session.post(
                            WEBSERV_URL + "/api/tasks",
                            data={
                                "roundId": self.current_round,
                                "exploitKey": exploit.docker_image_hash,
                                "teamId": team.id,
                            },
                        ) as response:
                            task = await response.json()
                            self.docker.create_container(
                                exploit.docker_image_hash,
                                {
                                    "HOST": endpoint["host"],
                                    "PORT": endpoint["port"],
                                },
                                {
                                    "fireball.exploit_id": exploit.id,
                                    "fireball.task_id": task["id"],
                                },
                            )
