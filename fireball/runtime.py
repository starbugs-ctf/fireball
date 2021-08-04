import logging
from typing import Dict

from .repo import Repo
from .docker import Docker
from .exploit import Exploit

logger = logging.getLogger(__name__)


class Runtime:
    repo: Repo
    docker: Docker
    exploits: Dict[str, Exploit]

    def __init__(self, repo: Repo, docker: Docker):
        self.repo = repo
        self.docker = docker
        self.exploits = {}

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def game_tick(self) -> None:
        # TODO
        print("tick")
        raise NotImplementedError

    async def repo_scan(self) -> None:
        result = await self.repo.scan()
        if result is None:
            return

        for path in result.removed_exploits:
            chal_name = path.parts[0]
            exploit_name = path.parts[1]
            exploit_id = f"{chal_name}:{exploit_name}"
            del self.exploits[exploit_id]

        for path in result.updated_exploits:
            chal_name = path.parts[0]
            exploit_name = path.parts[1]
            exploit_id = f"{chal_name}:{exploit_name}"

            try:
                exploit = await Exploit.from_path(
                    self, self.repo.path / path, exploit_name, chal_name
                )
                self.exploits[exploit_id] = exploit
            except Exception as e:
                # TODO: proper logging
                logger.error("%s", e)
