import logging
from pydantic.dataclasses import dataclass
from typing import Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class DefconAPI:
    def __init__(self, api_url: Optional[str]):
        self.client = aiohttp.ClientSession()
        self.api_url = api_url

    async def submit_flag(self, flag: str):
        if self.api_url is None:
            logger.error("Failed to submit flag, defcon url is not defined")
            return None

        async with self.client.post(
            self.api_url + "/api/submit_flag/" + flag,
        ) as response:
            return await response.json()
