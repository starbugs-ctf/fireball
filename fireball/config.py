import os

# DATABASE_URL: str = os.environ["FIREBALL_DATABASE_URL"]
DATABASE_URL: str = "sqlite:///./dev/db.sqlite"

DOCKER_SOCKET: str = (
    os.environ["FIREBALL_DOCKET_SOCKET"]
    if "FIREBALL_DOCKET_SOCKET" in os.environ
    else "unix:///var/run/docker.sock"
)

# URL of the main dashboard
# WEBSERV_URL: str = os.environ["FIREBALL_WEBSERV_URL"]
WEBSERV_URL: str = ""

EXPLOIT_REPO_PATH: str = "../exploits-testing"
EXPLOIT_REPO_INITIAL_HASH: str = "be8821762fad9d6401467b5a896d16c129b3c66f"
