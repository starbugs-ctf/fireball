import logging
from dataclasses import dataclass
from typing import Dict
import asyncio

from pathlib import Path, PurePosixPath
import aiohttp

from .config import WEBSERV_URL
from .docker import Docker
from .exploit import Exploit
from .repo import Repo, RepoScanResult
from .task import Task
from .siren import SirenAPI, Team, Problem

logger = logging.getLogger(__name__)


class Runtime:
    repo: Repo
    docker: Docker
    exploits: Dict[str, Exploit]

    current_round: int

    # team slug -> team
    teams: Dict[str, Team]

    # problem slug -> team
    problems: Dict[str, Problem]

    def __init__(self, repo: Repo, docker: Docker, siren_api: SirenAPI):
        self.repo = repo
        self.docker = docker
        self.siren = siren_api
        self.exploits = {}

        self.current_round = -1

        self.teams = {}
        self.problems = {}

        self.main_loop_lock = asyncio.Lock()
        self.main_loop_task = None

        self.docker_poll_interval = 10

    async def connect(self) -> None:
        await self.repo.connect()
        await self.refresh()
        self.main_loop_task = asyncio.create_task(self.main_loop())
        logger.info("Runtime initialized")

    async def disconnect(self) -> None:
        await self.main_loop_lock.acquire()
        self.main_loop_task.cancel()

    async def stupid(self):
        print("WTF")
        logger.debug("Polling docker")
        containers = await self.docker.get_managed_containers()
        tasks = []

        logger.debug("containers")
        logger.debug(containers)

        for container in containers:
            exploit_id = container["Config"]["Labels"]["fireball.exploit_id"]
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

    async def main_loop(self):
        # while True:
        pass
        # self.update()

    async def refresh(self) -> None:
        self.teams.clear()
        logger.info("=== Teams ===")
        for team in await self.siren.teams():
            logger.info(team)
            self.teams[team.slug] = team

        self.problems.clear()
        logger.info("=== Problem ===")
        for problem in await self.siren.problems():
            logger.info(problem)
            self.problems[problem.slug] = problem

    async def game_tick(self, round_id: int) -> None:
        self.current_round = round_id
        logger.info(f"New tick {round_id}")
        logger.debug(self.exploits)

        for exploit_id in self.exploits.keys():
            logger.debug(f"exploit_id {exploit_id}")
            await self.start_exploit(exploit_id)

    async def repo_scan(self) -> None:
        # result = await self.repo.scan()
        # logger.debug("scan done")
        # if result is None:
        #     return

        # logger.debug("scan pass")
        # logger.debug(result)

        # Be careful! The term "exploit ID" refers to different things
        # on the web server and the task runner

        result = RepoScanResult(
            updated_exploits=[Path("rorschach/test-exploit")],
            removed_exploits=[],
            last_processed_hash="",
        )

        for path in result.removed_exploits:
            chal_name = path.parts[0]
            exploit_name = path.parts[1]
            exploit_id = f"{chal_name}:{exploit_name}"
            logger.info(f"Deleting exploit {exploit_id}")

            del self.exploits[exploit_id]

            delete_exploits_result = await self.siren.delete_exploits(
                exploit_name, self.problems[chal_name].id
            )
            logger.debug(f"Deleted exploits: {delete_exploits_result}")

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
                continue

            new_exploit = await self.siren.create_exploit(
                exploit_name, exploit.docker_image_hash, self.problems[chal_name].id
            )
            logger.debug(f"Created exploits: {new_exploit}")

            # Run the updated exploit
            await self.start_exploit(exploit_id)

    async def start_exploit(self, exploit_id: str) -> None:
        if self.current_round < 0:
            # Skip if the contest is not running right now
            pass

        logger.debug("start_exploit")
        exploit = self.exploits[exploit_id]
        if exploit.enabled:
            logger.info(f"Running exploit {exploit_id}")

            for team in self.teams.values():
                if team.slug not in exploit.ignore_teams:
                    logger.debug(
                        f"Running exploit {exploit_id} against team {team.name}"
                    )

                    endpoint = await self.siren.endpoint(
                        team.id, self.problems[exploit.chal_name].id
                    )
                    logger.debug("endpoint")

                    task = await self.siren.create_task(
                        self.current_round, exploit.docker_image_hash, team.id
                    )
                    logger.debug("task")

                    await self.docker.create_container(
                        exploit.docker_image_hash,
                        {
                            "HOST": endpoint.host,
                            "PORT": endpoint.port,
                        },
                        {
                            "fireball.exploit_id": exploit_id,
                            "fireball.task_id": str(task["id"]),
                        },
                    )
