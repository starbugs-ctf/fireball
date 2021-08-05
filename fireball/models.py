from typing import Dict, List

from pydantic.dataclasses import dataclass


@dataclass
class Exploit:
    name: str
    meta: Dict
    timeout: int
    notifications: List[str]
    docker_image: str
