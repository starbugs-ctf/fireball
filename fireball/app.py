from fastapi import FastAPI, BackgroundTasks
import aiohttp, asyncio

from .db import database
from .runtime import Runtime
from .docker import Docker
from .repo import Repo
from .config import DOCKER_SOCKET, EXPLOIT_REPO_INITIAL_HASH, EXPLOIT_REPO_PATH, WEBSERV_URL
from fastapi_utils.tasks import repeat_every

app = FastAPI()

runtime = Runtime(
    Repo(EXPLOIT_REPO_PATH, EXPLOIT_REPO_INITIAL_HASH, "origin/master"),
    Docker(DOCKER_SOCKET),
)

# Test function, you should remove this after shit works
@app.on_event("startup")
async def test_container_deploy() -> None:
    print("test container deploy")
    res = await runtime.docker.run_image("aa971014ec5bfa64243d64e8fadcff621a254e22598206ce94eba4dc5c597a59", env={}, labels={"fireball.task_id": 42})
    print(res)

@app.on_event("startup")
@repeat_every(seconds=10)
async def check_docker() -> None:
    # Check what containers we currently manage
    print("check_dockers")
    containers = runtime.docker.get_managed_containers()

    for c in containers:
        task_id = c.labels['fireball.task_id']

        # Need to do a status update
        async with aiohttp.ClientSession() as session:
            status = docker.get_status_for_container(c)
            print(f"Update task {task_id}: {status}")
            result = await session.put(WEBSERV_URL + "/tasks/" + task_id, json=status)
        
        if c.status != 'running':
            # TODO: Dispose of the task
            print(f"TODO: Dispose of task {task_id}")


    # TODO: If we aren't at some TASK_LIMIT, we should query the web server for tasks we need to run,
    # and start the docker containers for them

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
