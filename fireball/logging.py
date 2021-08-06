import asyncio
import logging
from typing import Any, Dict, Optional
from asyncio import Queue

import aiohttp

DISCORD_API_RATE_LIMIT = 1 / 30  # 50 requests per second


class DiscordHandler(logging.Handler):
    def __init__(self, webhook_url: Optional[str]):
        super(DiscordHandler, self).__init__()
        self._webhook_url = webhook_url
        self._session = aiohttp.ClientSession()
        self._queue: Queue = Queue()
        self._worker_task = asyncio.create_task(self._worker())

    def emit(self, record: logging.LogRecord):
        data = self.format(record)
        self._queue.put_nowait(data)

    async def _worker(self):
        message = ""
        task = None

        async def send():
            nonlocal task, message

            await asyncio.sleep(DISCORD_API_RATE_LIMIT)
            task = None
            await self.send_message(message)
            message = ""

        while True:
            data = await self._queue.get()
            self._queue.task_done()
            if task is not None:
                task.cancel()
                task = None
                message += "\n"
                message += data
            else:
                message = data

            task = asyncio.create_task(send())

    async def send_message(self, message: str):
        if self._webhook_url is not None:
            await self._session.post(self._webhook_url, json={"content": message})


def configure_discord_logging(webhook_url: Optional[str]):
    root = logging.getLogger()

    discord_handler = DiscordHandler(webhook_url)
    discord_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    discord_handler.setFormatter(formatter)
    root.addHandler(discord_handler)


def configure_default_logging():
    root = logging.getLogger("fireball")
    root.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    ch.setFormatter(formatter)
    root.addHandler(ch)
