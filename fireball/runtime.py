class Runtime:
    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def game_tick(self) -> None:
        # TODO
        print("tick")
        raise NotImplementedError

    async def repo_scan(self) -> None:
        # TODO
        print("scan")
        raise NotImplementedError
