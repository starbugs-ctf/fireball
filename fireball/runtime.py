import aiohttp
import logging
from dataclasses import dataclass
from typing import Dict

from .config import WEBSERV_URL
from .repo import Repo
from .docker import Docker
from .exploit import Exploit

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

    # team slug -> team
    teams: Dict[str, Team]

    # problem slug -> team
    problems: Dict[str, Problem]

    def __init__(self, repo: Repo, docker: Docker):
        self.repo = repo
        self.docker = docker
        self.exploits = {}

        self.teams = {}
        self.problems = {}

    async def connect(self) -> None:
        await self.repo.connect()
        await self.refresh()

    async def disconnect(self) -> None:
        pass

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

    async def game_tick(self) -> None:
        # TODO
        print("tick")
        raise NotImplementedError

    async def repo_scan(self) -> None:
        result = await self.repo.scan()
        if result is None:
            return

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
