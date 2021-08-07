import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
import asyncio
import random
from aiodocker.exceptions import DockerError
from aiodocker.containers import DockerContainer

import aiohttp

from .config import WEBSERV_URL
from .docker import Docker
from .exploit import Exploit
from .repo import Repo
from .task import Task, TaskStatusEnum, TaskStatus
from .siren import SirenAPI, Team, Problem
from .defcon import DefconAPI

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

    def __init__(
        self,
        repo: Repo,
        docker: Docker,
        siren_api: SirenAPI,
        defcon_api: DefconAPI,
        docker_poll_interval: int,
        docker_max_running_containers: int,
        current_team: str,
    ):
        self.repo = repo
        self.docker = docker
        self.siren = siren_api
        self.defcon = defcon_api
        self.exploits = {}

        self.current_round = 1
        self.current_team = current_team

        self.teams = {}
        self.problems = {}

        self.main_loop_lock = asyncio.Lock()
        self.main_loop_task: Optional[asyncio.Task] = None

        self.docker_poll_interval = docker_poll_interval
        self.docker_max_running_containers = docker_max_running_containers

    async def connect(self) -> None:
        async with self.main_loop_lock:
            logger.info("==============================")
            logger.info("Starting...")
            logger.info("==============================")
            await self.refresh()

            exploit_paths = await self.repo.connect()
            for path in exploit_paths:
                chal_name = path.parts[0]
                exploit_name = path.parts[1]
                exploit_id = f"{chal_name}:{exploit_name}"
                logger.info(f"Adding exploit {exploit_id}")

                try:
                    exploit = await Exploit.from_path(
                        self, self.repo.path / path, exploit_name, chal_name
                    )
                    self.exploits[exploit_id] = exploit
                except Exception as e:
                    logger.error("Failed to parse %s exploit: %s", exploit_id, e)
                    continue

                new_exploit = await self.siren.create_exploit(
                    exploit_name,
                    exploit.docker_image_hash,
                    self.problems[exploit.chal_name].id,
                )

            self.current_round = await self.siren.get_current_round()
            logger.info("Fetched round id %s from siren", self.current_round)
            self.main_loop_task = asyncio.create_task(self.main_loop())
            logger.info("Runtime initialized")

    async def disconnect(self) -> None:
        await self.main_loop_lock.acquire()
        self.main_loop_task.cancel()

    async def get_task_from_container(
        self, container: DockerContainer
    ) -> Optional[Task]:
        try:
            exploit_id = container["Labels"]["fireball.exploit_id"]
            task_id = int(container["Labels"]["fireball.task_id"])
            team_slug = container["Labels"]["fireball.team_slug"]
        except KeyError:
            logger.warning(
                "Found a managed container with malformed metadata %s",
                container.id,
            )
            return None

        if exploit_id not in self.exploits:
            logger.warning("Couldn't find exploit with id:", exploit_id)
            await container.delete(force="true")
            await self.siren.update_task(
                task_id,
                {
                    "status": "RUNTIME_ERROR",
                    "statusMessage": "Dangling exploit",
                },
            )
            return None

        exploit = self.exploits[exploit_id]
        return Task(task_id, exploit, container, team_slug)

    async def poll_docker(self):
        logger.debug("Polling docker")
        containers = await self.docker.get_managed_containers()

        tasks = map(self.get_task_from_container, containers)
        tasks = await asyncio.gather(*tasks)
        tasks = filter(lambda x: x is not None, tasks)
        tasks: List[Task] = list(tasks)

        await asyncio.gather(*[task.fetch_status() for task in tasks])

        # Filter ones where we failed to check the status
        tasks = filter(lambda x: x.status is not None, tasks)
        tasks: List[Task] = list(tasks)

        running_containers = 0
        for task in tasks:
            status = task.status
            if status.status == TaskStatusEnum.RUNNING:
                running_containers += 1

            if status.status != TaskStatusEnum.PENDING:
                await self.update_siren_task(task)

                if status.status == TaskStatusEnum.OKAY:
                    if status.flag is not None:
                        await self.submit_flag(task)
                        await task.delete()
                    else:
                        logger.error(
                            "Container has finished, but flag wasn't found: %s",
                            task.container_id,
                        )

        random.shuffle(tasks)
        for task in tasks:
            if (
                running_containers < self.docker_max_running_containers
                and task.status.status == TaskStatusEnum.PENDING
            ):
                try:
                    await task.start()
                    running_containers += 1
                except DockerError as e:
                    logger.error("Failed to start %s task: %s", task.task_id, e)
                    await self.update_siren_task(task, "Failed to start the container")
                    await task.delete(force=True)
                    continue

                await self.update_siren_task(task)

    async def main_loop(self):
        while True:
            async with self.main_loop_lock:
                try:
                    await self.poll_docker()
                except Exception as e:
                    logger.error("Main loop crashed %s", e)

            await asyncio.sleep(self.docker_poll_interval)

    async def refresh(self) -> None:
        self.teams.clear()
        for team in await self.siren.teams():
            self.teams[team.slug] = team

        self.problems.clear()
        for problem in await self.siren.problems():
            self.problems[problem.slug] = problem

    async def game_tick(self, round_id: int) -> None:
        self.current_round = round_id
        logger.info(f"New tick {round_id}")

        async with self.main_loop_lock:
            for exploit_id in self.exploits.keys():
                await self.start_exploit(exploit_id)

    async def repo_scan(self) -> None:
        result = await self.repo.scan()
        if result is None:
            return

        # Be careful! The term "exploit ID" refers to different things
        # on the web server and the task runner

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
                logger.error("Failed to parse %s exploit: %s", exploit_id, e)
                continue

            try:
                problem_id = self.problems[chal_name].id
            except KeyError:
                logger.warn("Failed to find a problem: %s", chal_name)
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
            return

        exploit = self.exploits[exploit_id]
        if exploit.enabled:
            logger.info(f"Scheduling exploit {exploit_id}")

            for team in self.teams.values():
                if team.slug not in exploit.ignore_teams:
                    logger.debug(
                        f"Scheduling exploit {exploit_id} against team {team.name}"
                    )

                    endpoint = await self.siren.endpoint(
                        team.id, self.problems[exploit.chal_name].id
                    )

                    task = await self.siren.create_task(
                        self.current_round, exploit.docker_image_hash, team.id
                    )

                    await self.docker.create_container(
                        exploit.docker_image_hash,
                        {
                            "HOST": endpoint.host,
                            "PORT": endpoint.port,
                        },
                        {
                            "fireball.exploit_id": exploit_id,
                            "fireball.task_id": str(task["id"]),
                            "fireball.team_slug": team.slug,
                        },
                    )

    async def submit_flag(self, task: Task) -> bool:
        assert task.status is not None
        assert task.status.flag is not None

        logger.info(
            "Submitting flag '%s' for %s", task.status.flag, task.exploit.chal_name
        )
        is_our_flag = task.team_slug == self.current_team

        if not is_our_flag:
            try:
                res = await self.defcon.submit_flag(task.status.flag)
            except Exception as e:
                logger.error("Failed to submit flag to defcon api: %s", e)
                return False

            if res is None:
                return False

            message = res["message"]
            additionalInfo = ""

            if message == "ALREADY_SUBMITTED":
                message = "DUPLICATE"
            elif message == "INCORRECT":
                message = "WRONG"
            elif message == "SERVICE_INACTIVE":
                message = "UNKNOWN_ERROR"
                additionalInfo = "Service is inactive"

            await self.siren.create_flag_submission(
                task.task_id, task.status.flag, message, additionalInfo
            )

        else:
            await self.siren.create_flag_submission(
                task.task_id, task.status.flag, "SKIPPED", ""
            )

        return True

    async def update_siren_task(self, task: Task, message: str = ""):
        assert task.status is not None
        status = task.status
        await self.siren.update_task(
            task.task_id,
            {
                "status": status.status,
                "stdout": status.stdout,
                "stderr": status.stderr,
                "statusMessage": message,
            },
        )
