import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import dateutil
import toml
from aiodocker import Docker
from aiodocker.containers import DockerContainer
from aiodocker.exceptions import DockerError
from pydantic.dataclasses import dataclass

from .exploit import Exploit

logger = logging.getLogger(__name__)


@dataclass
class TaskStatus:
    status: str  # PENDING, RUNNING, OKAY, RUNTIME_ERROR, TIMEOUT
    flag: Optional[str] = None
    stdout: str
    stderr: str


def is_over_timeout(started_at: str, timeout: int):
    started_at = dateutil.parser.parse(started_at)
    if started_at + timedelta(seconds=timeout) > datetime.now():
        return True
    else:
        return False


async def extract_flag(container: DockerContainer) -> Optional[str]:
    try:
        tar = await container.get_archive("/flag")
    except DockerError as e:
        if e.status == 404:
            return None

        raise e

    try:
        return tar.extractfile("/flag").read().decode()
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
    def __init__(self, exploit: Exploit, container: DockerContainer):
        self.exploit = exploit
        self.container = container

    @property
    def id(self):
        return self.container.id

    async def status(self):
        # https://docs.docker.com/engine/api/v1.41/#operation/ContainerInspect
        stats = await self.container.show()
        stdout, stderr = await get_logs(self.container)

        status = stats["State"]["Status"]

        if status == "running":
            if is_over_timeout(stats["State"]["StartedAt"], self.exploit.timeout):
                await self.container.delete()
                return TaskStatus(status="TIMEOUT", stdout=stdout, stderr=stderr)
            else:
                return TaskStatus(status="RUNNING", stdout=stdout, stderr=stderr)

        elif status == "exited":
            exit_code = stats["State"]["ExitCode"]

            if exit_code == 0:
                flag = await extract_flag(self.container)
                await self.container.delete()
                return TaskStatus(
                    status="OKAY", stdout=stdout, stderr=stderr, flag=flag
                )
            else:
                # Not removing the container on purpose here to ease debugging
                return TaskStatus(
                    status="RUNTIME_ERROR",
                    stdout=stdout,
                    stderr=stderr,
                )

        elif status == "paused" or status == "created":
            return TaskStatus(
                status="PENDING",
                stdout=stdout,
                stderr=stderr,
            )
        else:
            # One of restarting, removing, or dead
            # Not removing the container on purpose here to ease debugging
            return TaskStatus(
                status="RUNTIME_ERROR",
                stdout=stdout,
                stderr=stderr,
            )
