import logging
from pydantic.dataclasses import dataclass
from typing import Dict, List

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
        logger.error(response)


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

    async def update_task(self, task_id: num, data: Dict[str, str]):
        async with self.client.put(
            self.api_url + f"/api/tasks/{task_id}", data=data
        ) as response:
            check(response)
            return await response.json()

    async def create_flag_submission(
        self, task_id: num, flag: str, submission_result: str, message: str
    ) -> None:
        async with self.client.put(
            self.api_url + "/api/flags",
            data={
                "taskId": task_id,
                "flag": flag,
                "submissionResult": submission_result,
                "message": message,
            },
        ) as response:
            check(response)
            return await response.json()
