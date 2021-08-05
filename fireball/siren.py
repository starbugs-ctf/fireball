import aiohttp


class SirenAPI:
    def __init__(self, api_url: str):
        self.client = aiohttp.ClientSession()
        self.api_url = api_url
