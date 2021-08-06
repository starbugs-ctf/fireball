import os

PROD = os.environ.get("PROD") is not None

DOCKER_SOCKET: str = (
    os.environ["FIREBALL_DOCKER_SOCKET"]
    if "FIREBALL_DOCKER_SOCKET" in os.environ
    else "unix:///var/run/docker.sock"
)

# URL of the main dashboard
# WEBSERV_URL: str = os.environ["FIREBALL_WEBSERV_URL"]
WEBSERV_URL: str = "http://localhost:3000"

if PROD:
    EXPLOIT_REPO_PATH: str = "../defcon-ctf-2021"
    EXPLOIT_REPO_BRANCH: str = "origin/main"
    DEFCON_API = "http://10.13.37.13"
    WEBHOOK_URL: str = "https://discordapp.com/api/webhooks/873024285730562088/Jxw4R7GlxzdzNYCRtaO7X-q3-XwsScetdoLgOVV11Sm2PzJwl0fk7ZvSHEh_pgABfBgn"
else:
    EXPLOIT_REPO_PATH: str = "../exploits-testing"
    EXPLOIT_REPO_BRANCH: str = "origin/master"
    DEFCON_API = None
    WEBHOOK_URL = None

DOCKER_MAX_CONTAINERS_RUNNING: int = 30
DOCKER_POLLING_INTERVAL: int = 10
