import logging
from dataclasses import dataclass
from typing import Dict
import asyncio
import random
from aiodocker.exceptions import DockerError

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
    ):
        self.repo = repo
        self.docker = docker
        self.siren = siren_api
        self.defcon = defcon_api
        self.exploits = {}

        self.current_round = 1

        self.teams = {}
        self.problems = {}

        self.main_loop_lock = asyncio.Lock()
        self.main_loop_task = None

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

    async def main_loop(self):
        while True:
            async with self.main_loop_lock:
                logger.debug("Polling docker")
                containers = await self.docker.get_managed_containers()
                tasks = []

                for container in containers:
                    try:
                        exploit_id = container["Labels"]["fireball.exploit_id"]
                        task_id = int(container["Labels"]["fireball.task_id"])
                    except KeyError:
                        logger.warning(
                            "Found a managed container with malformed metadata %s",
                            container.id,
                        )
                        continue

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
                        continue

                    exploit = self.exploits[exploit_id]
                    tasks.append(Task(task_id, exploit, container))

                statuses = await asyncio.gather(
                    *[task.status() for task in tasks], return_exceptions=True
                )

                running_containers = 0
                for status, task in zip(statuses, tasks):
                    if isinstance(status, Exception):
                        logger.error(
                            "An error occurred while querying status of %s task: %s",
                            task.id,
                            status,
                        )
                        continue

                    if status.status == TaskStatusEnum.RUNNING:
                        running_containers += 1

                    if status.status != TaskStatusEnum.PENDING:
                        await self.siren.update_task(
                            task.task_id,
                            {
                                "status": status.status,
                                "stdout": status.stdout,
                                "stderr": status.stderr,
                            },
                        )

                        if status.status == TaskStatusEnum.OKAY:
                            if status.flag != None:
                                await self.submit_flag(task, status)
                                await task.container.delete()
                            else:
                                logger.error(
                                    "Container has finished, but flag wasn't found: %s",
                                    task.container_id,
                                )

                zipped = list(zip(statuses, tasks))
                random.shuffle(zipped)
                for status, task in zipped:
                    if (
                        running_containers < self.docker_max_running_containers
                        and status.status == TaskStatusEnum.PENDING
                    ):
                        try:
                            logger.info(
                                "Running %s, task_id: %s",
                                task.exploit.name,
                                task.task_id,
                            )
                            await task.container.start()
                            running_containers += 1

                            await self.siren.update_task(
                                task.task_id,
                                {
                                    "status": TaskStatusEnum.RUNNING,
                                },
                            )

                        except DockerError as e:
                            logger.error(e)
                            await task.container.delete(force="true")
                            await self.siren.update_task(
                                task.task_id,
                                {
                                    "status": TaskStatusEnum.RUNTIME_ERROR,
                                    "statusMessage": "Failed to start the container",
                                },
                            )
                            continue

                        running_containers += 1

                        await self.siren.update_task(
                            task.task_id,
                            {
                                "status": TaskStatusEnum.RUNNING,
                            },
                        )

            await asyncio.sleep(self.docker_poll_interval)

    async def refresh(self) -> None:
        self.teams.clear()
        # logger.info("=== Teams ===")
        for team in await self.siren.teams():
            # logger.info(team)
            self.teams[team.slug] = team

        self.problems.clear()
        # logger.info("=== Problem ===")
        for problem in await self.siren.problems():
            # logger.info(problem)
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
            pass

        exploit = self.exploits[exploit_id]
        if exploit.enabled:
            logger.info(f"Scheduling exploit {exploit_id}")

            for team in self.teams.values():
                if team.slug not in exploit.ignore_teams:
                    logger.debug(
                        f"Running exploit {exploit_id} against team {team.name}"
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
                        },
                    )

    async def submit_flag(self, task: Task, status: TaskStatus) -> bool:
        logger.info("Submitting flag '%s' for %s", status.flag, task.exploit.chal_name)
        try:
            res = await self.defcon.submit_flag(status.flag)
        except Exception as e:
            logger.error("Failed to submit flag to defcon api: %s", e)
            return False

        if res is not None:
            message = res["message"]
            if message == "ALREADY_SUBMITTED":
                message = "DUPLICATE"
            elif message == "INCORRECT":
                message = "WRONG"

            await self.siren.create_flag_submission(
                task.task_id, status.flag, message, ""
            )
            return True

        return False
