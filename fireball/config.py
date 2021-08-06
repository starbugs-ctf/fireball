import os

# DATABASE_URL: str = os.environ["FIREBALL_DATABASE_URL"]
DATABASE_URL: str = "sqlite:///./dev/db.sqlite"

DOCKER_SOCKET: str = (
    os.environ["FIREBALL_DOCKER_SOCKET"]
    if "FIREBALL_DOCKER_SOCKET" in os.environ
    else "unix:///var/run/docker.sock"
)

# URL of the main dashboard
# WEBSERV_URL: str = os.environ["FIREBALL_WEBSERV_URL"]
WEBSERV_URL: str = "http://localhost:3000"

EXPLOIT_REPO_PATH: str = "../exploits-testing"

DOCKER_MAX_CONTAINERS_RUNNING: int = 30
DOCKER_POLLING_INTERVAL: int = 10
