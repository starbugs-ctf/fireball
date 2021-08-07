import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

import dateutil.parser
import toml
from aiodocker import Docker
from aiodocker.containers import DockerContainer
from aiodocker.exceptions import DockerError

from .exploit import Exploit

logger = logging.getLogger(__name__)


class TaskStatusEnum:
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    OKAY = "OKAY"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    TIMEOUT = "TIMEOUT"


@dataclass
class TaskStatus:
    status: str  # PENDING, RUNNING, OKAY, RUNTIME_ERROR, TIMEOUT
    stdout: str
    stderr: str
    flag: Optional[str] = None


def is_over_timeout(started_at: str, timeout: int):
    started_at_dt: datetime = dateutil.parser.parse(started_at)
    if started_at_dt + timedelta(seconds=timeout) > datetime.now(timezone.utc):
        return True
    else:
        return False


async def extract_flag(container: DockerContainer) -> Optional[str]:
    try:
        tar = await container.get_archive("/tmp/flag")
    except DockerError as e:
        if e.status == 404:
            return None

        raise e

    try:
        return tar.extractfile("flag").read().decode()
    except Exception as e:
        logger.error("Failed to extract flag: %s", e)

    return None


async def get_logs(container: DockerContainer) -> Tuple[str, str]:
    stdout = await container.log(stdout=True)
    stdout = "\n".join(stdout)
    stderr = await container.log(stderr=True)
    stderr = "\n".join(stderr)
    return stdout, stderr


class Task:
    task_id: int
    exploit: Exploit
    container: DockerContainer
    team_slug: str
    status: Optional[TaskStatus]

    def __init__(
        self, task_id: int, exploit: Exploit, container: DockerContainer, team_slug: str
    ):
        self.task_id = task_id
        self.exploit = exploit
        self.container = container
        self.team_slug = team_slug
        self.status = None

    @property
    def container_id(self):
        return self.container.id

    async def start(self):
        logger.info(
            "Running %s against %s, task_id: %s",
            self.exploit.name,
            self.team_slug,
            self.task_id,
        )
        await self.container.start()
        await self._fetch_status()

    async def delete(self, force: bool = False):
        if force:
            await self.container.delete(force="true")
        else:
            await self.container.delete()

        await self._fetch_status()

    async def fetch_status(self) -> None:
        try:
            self.status = await self._fetch_status()
        except Exception as e:
            logger.error(
                "An error occurred while querying status of %s task: %s",
                self.task_id,
                e,
            )

    async def _fetch_status(self) -> TaskStatus:
        # https://docs.docker.com/engine/api/v1.41/#operation/ContainerInspect
        stats = await self.container.show()
        stdout, stderr = await get_logs(self.container)

        status = stats["State"]["Status"]

        if status == "running":
            if is_over_timeout(stats["State"]["StartedAt"], self.exploit.timeout):
                await self.container.delete()
                return TaskStatus(
                    status=TaskStatusEnum.TIMEOUT, stdout=stdout, stderr=stderr
                )
            else:
                return TaskStatus(
                    status=TaskStatusEnum.RUNNING, stdout=stdout, stderr=stderr
                )

        elif status == "exited":
            exit_code = stats["State"]["ExitCode"]

            if exit_code == 0:
                flag = await extract_flag(self.container)
                return TaskStatus(
                    status=TaskStatusEnum.OKAY, stdout=stdout, stderr=stderr, flag=flag
                )
            else:
                await self.container.delete()
                return TaskStatus(
                    status=TaskStatusEnum.RUNTIME_ERROR,
                    stdout=stdout,
                    stderr=stderr,
                )

        elif status == "paused" or status == "created":
            return TaskStatus(
                status=TaskStatusEnum.PENDING,
                stdout=stdout,
                stderr=stderr,
            )
        else:
            # One of restarting, removing, or dead
            # Not removing the container on purpose here to ease debugging
            return TaskStatus(
                status=TaskStatusEnum.RUNTIME_ERROR,
                stdout=stdout,
                stderr=stderr,
            )
