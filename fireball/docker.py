import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import aiodocker
from aiodocker.containers import DockerContainer
from docker.utils.build import tar

from .exceptions import DockerBuildError


class Docker:
    def __init__(self, url: Optional[str] = None):
        self.client = aiodocker.Docker(url=url)

    async def close(self):
        return await self.client.close()

    async def build_image_from_path(self, path: Path):
        gzip = True
        dockerfile = "Dockerfile"
        if not (path / dockerfile).exists():
            raise DockerBuildError(f"Unable to find dockerfile at {path}")

        # From https://github.com/docker/docker-py/blob/a9748a8b702a3c75b46ba8c8d0490e4b8ec5ab04/docker/api/build.py#L150-L162
        dockerignore = os.path.join(path, ".dockerignore")
        exclude = None
        if os.path.exists(dockerignore):
            with open(dockerignore) as f:
                exclude = list(
                    filter(
                        lambda x: x != "" and x[0] != "#",
                        [l.strip() for l in f.read().splitlines()],
                    )
                )
        context = tar(path, exclude=exclude, gzip=gzip)
        encoding = "gzip"

        result: Any = await self.client.images.build(
            path_dockerfile=dockerfile,
            fileobj=context,
            encoding=encoding,
            stream=False,
        )
        # Type annotation on that function is wrong, it actualy returs a List
        result = cast(List[Dict[str, Any]], result)

        image_hash = None
        for res in result:
            if "error" in res:
                raise DockerBuildError(res["error"])

            if "aux" in res and "ID" in res["aux"]:
                image_hash = res["aux"]["ID"]

        if image_hash is None:
            raise DockerBuildError("Wasn't able to get the image hash")

        return image_hash

    async def create_container(
        self, image_hash: str, env: Dict[str, str], labels: Dict[str, str]
    ) -> str:
        env_list = [f"{key}={value}" for key, value in env.items()]

        # See https://docs.docker.com/engine/api/v1.41/#operation/ContainerCreate
        config = {
            "Env": env_list,
            "Image": image_hash,
            "Labels": {"fireball.managed": "true", **labels},
        }
        container = await self.client.containers.create(config=config)
        return container

    async def get_managed_containers(self):
        containers = await self.client.containers.list(
            all=True, filters=json.dumps({"label": "fireball.managed=true"})
        )
        return containers
