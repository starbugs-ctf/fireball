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


async def check(response):
    if response.status != 200:
        logger.error("Failed siren request: %s", await response.text())


class SirenAPI:
    def __init__(self, api_url: str):
        self.client = aiohttp.ClientSession()
        self.api_url = api_url

    async def teams(self) -> List[Team]:
        async with self.client.get(self.api_url + "/api/teams") as response:
            await check(response)
            return list(map(lambda team_raw: Team(**team_raw), await response.json()))

    async def problems(self) -> List[Problem]:
        async with self.client.get(self.api_url + "/api/problems") as response:
            await check(response)
            return list(
                map(lambda problem_raw: Problem(**problem_raw), await response.json())
            )

    async def delete_exploits(self, exploit_name: str, problem_id: int):
        async with self.client.delete(
            self.api_url + "/api/exploits",
            json={"name": exploit_name, "problemId": problem_id},
        ) as response:
            await check(response)
            return await response.json()

    async def create_exploit(
        self, exploit_name: str, exploit_key: str, problem_id: int, enabled: bool
    ):
        async with self.client.post(
            self.api_url + "/api/exploits",
            json={
                "name": exploit_name,
                "key": exploit_key,
                "problemId": problem_id,
                "enabled": enabled,
            },
        ) as response:
            await check(response)
            return await response.json()

    async def endpoint(self, team_id: int, problem_id: int) -> Endpoint:
        async with self.client.post(
            self.api_url + "/api/endpoint",
            json={
                "teamId": team_id,
                "problemId": problem_id,
            },
        ) as response:
            await check(response)
            return Endpoint(**(await response.json()))

    async def create_task(self, round_id: int, exploit_key: str, team_id: int):
        async with self.client.post(
            self.api_url + "/api/tasks",
            json={
                "roundId": round_id,
                "exploitKey": exploit_key,
                "teamId": team_id,
            },
        ) as response:
            await check(response)
            return await response.json()

    async def update_task(self, task_id: int, data: Dict[str, str]):
        async with self.client.put(
            self.api_url + f"/api/tasks/{task_id}", json=data
        ) as response:
            await check(response)
            return await response.json()

    async def create_flag_submission(
        self, task_id: int, flag: str, submission_result: str, message: str
    ):
        async with self.client.post(
            self.api_url + "/api/flags",
            json={
                "taskId": task_id,
                "flag": flag,
                "submissionResult": submission_result,
                "message": message,
            },
        ) as response:
            await check(response)
            return await response.json()

    async def get_current_round(self) -> int:
        async with self.client.get(
            self.api_url + "/api/current_round",
        ) as response:
            await check(response)
            return (await response.json())["round"]

    async def successful_exploit(self, round_id: int, problem_id: int, team_id: int):
        async with self.client.post(
            self.api_url + "/api/successful_exploit",
            json={
                "roundId": round_id,
                "problemId": problem_id,
                "teamId": team_id,
            }
        ) as response:
            await check(response)
            return await response.json()
