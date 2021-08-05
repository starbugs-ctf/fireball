import logging
from typing import List

import aiohttp

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


@dataclass
class Endpoint:
    host: str
    port: str


def check(response):
    if response.status != 200:
        log.error(response)


class SirenAPI:
    def __init__(self, api_url: str):
        self.client = aiohttp.ClientSession()
        self.api_url = api_url

    async def teams(self) -> List[Team]:
        async with self.client.get(self.api_url + "/api/teams") as response:
            check(response)
            return list(map(lambda team_raw: Team(**team_raw), await response.json()))

    async def problems(self) -> List[Problem]:
        async with self.client.get(self.api_url + "/api/problems") as response:
            check(response)
            return list(
                map(lambda problem_raw: Problem(**problem_raw), await response.json())
            )

    async def delete_exploits(self, exploit_name: str, problem_id: int):
        async with self.client.delete(
            self.api_url + "/api/exploits",
            data={"name": exploit_name, "problemId": problem_id},
        ) as response:
            check(response)
            return await response.json()

    async def create_exploit(
        self, exploit_name: str, exploit_key: str, problem_id: int
    ):
        async with self.client.post(
            self.api_url + "/api/exploits",
            data={
                "name": exploit_name,
                "key": exploit_key,
                "problemId": problem_id,
            },
        ) as response:
            check(response)
            return await response.json()

    async def endpoint(self, team_id: int, problem_id: int) -> Endpoint:
        async with self.client.post(
            self.api_url + "/api/endpoint",
            data={
                "teamId": team_id,
                "problemId": problem_id,
            },
        ) as response:
            check(response)
            return Endpoint(**(await response.json()))

    async def create_task(self, round_id: int, exploit_key: str, team_id: int):
        async with self.client.post(
            self.api_url + "/api/tasks",
            data={
                "roundId": round_id,
                "exploitKey": exploit_key,
                "teamId": team_id,
            },
        ) as response:
            check(response)
            return await response.json()
