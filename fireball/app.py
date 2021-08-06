from fastapi import BackgroundTasks, FastAPI

from .config import (
    DOCKER_SOCKET,
    EXPLOIT_REPO_PATH,
    WEBSERV_URL,
    DOCKER_MAX_CONTAINERS_RUNNING,
    DOCKER_POLLING_INTERVAL,
    WEBHOOK_URL,
    EXPLOIT_REPO_BRANCH,
    DEFCON_API,
)
from .docker import Docker
from .repo import Repo
from .runtime import Runtime
from .siren import SirenAPI
from .logging import configure_default_logging, configure_discord_logging
from .defcon import DefconAPI


app = FastAPI()

runtime = Runtime(
    Repo(EXPLOIT_REPO_PATH, EXPLOIT_REPO_BRANCH),
    Docker(DOCKER_SOCKET),
    SirenAPI(WEBSERV_URL),
    DefconAPI(DEFCON_API),
    DOCKER_POLLING_INTERVAL,
    DOCKER_MAX_CONTAINERS_RUNNING,
)


@app.on_event("startup")
async def startup():
    configure_default_logging()
    configure_discord_logging(WEBHOOK_URL)
    await runtime.connect()


@app.on_event("shutdown")
async def shutdown():
    await runtime.disconnect()


@app.get("/health_check")
async def health_check():
    return {"status": "ok"}


@app.post("/refresh")
async def runtime_refresh():
    await runtime.refresh()
    return {"status": "ok"}


@app.post("/tick")
async def new_tick(background_tasks: BackgroundTasks, round_id: int):
    """Triggers new tick"""
    background_tasks.add_task(runtime.game_tick, round_id)
    return {"status": "ok"}


@app.post("/scan")
async def new_scan(background_tasks: BackgroundTasks):
    """Triggers repo scan"""
    background_tasks.add_task(runtime.repo_scan)
    return {"status": "ok"}


@app.get("/exec")
async def get_executions(background_tasks: BackgroundTasks, exploit_id: str):
    await runtime.start_exploit(exploit_id)
    return {"status": "ok"}
