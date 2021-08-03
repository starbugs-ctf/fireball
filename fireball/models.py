from pydantic.dataclasses import dataclass
from typing import Dict, List


@dataclass
class Exploit:
    name: str
    meta: Dict
    timeout: int
    notifications: List[str]
    docker_image: str
