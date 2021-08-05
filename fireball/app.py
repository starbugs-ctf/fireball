from fastapi import FastAPI, BackgroundTasks

from .db import database
from .runtime import Runtime
from .docker import Docker
from .repo import Repo
from .config import DOCKER_SOCKET, EXPLOIT_REPO_INITIAL_HASH, EXPLOIT_REPO_PATH

app = FastAPI()

runtime = Runtime(
    Repo(EXPLOIT_REPO_PATH, EXPLOIT_REPO_INITIAL_HASH, "origin/master"),
    Docker(DOCKER_SOCKET),
)


@app.on_event("startup")
async def startup():
    await runtime.connect()
    await database.connect()


@app.on_event("shutdown")
async def shutdown():
    await runtime.disconnect()
    await database.disconnect()


@app.get("/health_check")
async def health_check():
    return {"status": "ok"}


@app.post("/refresh")
async def runtime_refresh():
    await runtime.refresh()
    return {"status": "ok"}


@app.post("/tick")
async def new_tick(background_tasks: BackgroundTasks):
    """Triggers new tick"""
    background_tasks.add_task(runtime.game_tick)
    return {"status": "ok"}


@app.post("/scan")
async def new_scan(background_tasks: BackgroundTasks):
    """Triggers repo scan"""
    background_tasks.add_task(runtime.repo_scan)
    return {"status": "ok"}


@app.get("/execution")
async def get_executions(running: bool = False, max_size: int = 100):
    """Returns last N executions of exploits"""
    # TODO
    raise NotImplementedError


@app.get("/execution/{execution_id}")
async def get_execution(execution_id: int):
    """Returns data about `id` execution"""
    # TODO
    raise NotImplementedError


@app.post("/execution/")
async def create_execution():
    """Creates new execution"""
    # TODO
    raise NotImplementedError
