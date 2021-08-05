import asyncio
import logging
from typing import Any, Dict

import aiohttp


class DiscordHandler(logging.Handler):
    def __init__(self, webhook_url: str):
        super(DiscordHandler, self).__init__()
        self._webhook_url = webhook_url
        self._session = aiohttp.ClientSession()

    def emit(self, record: logging.LogRecord):
        data = self._format_message(record)

        # TODO: not really sure what to do with this task thing,
        # since I cannot await it here
        asyncio.create_task(self.send_message(data))

    def _format_message(self, record: logging.LogRecord) -> Dict[str, Any]:
        return {"content": record.getMessage()}

    async def send_message(self, data: Dict[str, Any]):
        await self._session.post(self._webhook_url, json=data)


def configure_discord_logging(webhook_url: str):
    root = logging.getLogger()

    discord_handler = DiscordHandler(webhook_url)
    discord_handler.setLevel(logging.INFO)

    root.addHandler(discord_handler)
