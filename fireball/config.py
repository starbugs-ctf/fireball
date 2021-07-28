import os

# DATABASE_URL: str = os.environ["FIREBALL_DATABASE_URL"]
DATABASE_URL: str = "sqlite:///./dev/db.sqlite"

DOCKER_SOCKET: str = (
    os.environ["FIREBALL_DOCKET_SOCKET"]
    if "FIREBALL_DOCKET_SOCKET" in os.environ
    else "/var/run/docker.sock"
)

# URL of the main dashboard
# WEBSERV_URL: str = os.environ["FIREBALL_WEBSERV_URL"]
WEBSERV_URL: str = ""
