import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from subprocess import check_call, check_output

import pytest

from fireball.repo import Repo


def write_file(path: Path, contents: str):
    with open(path, "w") as f:
        f.write(contents)


def test_repo_empty():
    loop = asyncio.get_event_loop()
    with tempfile.TemporaryDirectory() as path_name:
        path = Path(path_name)

        check_call(["git", "init"], cwd=path)
        write_file(path / "README.md", "# hello")
        check_call(["git", "add", "-A"], cwd=path)
        check_call(["git", "commit", "-m", "Initial commit"], cwd=path)
        commit_hash = (
            check_output(["git", "rev-parse", "HEAD"], cwd=path).decode().strip()
        )

        repo = Repo(path, commit_hash, "master")
        result = loop.run_until_complete(repo.scan())
        assert result is None

        new_exploit_path = path / "high" / "ground"
        os.makedirs(new_exploit_path)
        write_file(new_exploit_path / "siren.toml", "# something")
        check_call(["git", "add", "-A"], cwd=path)
        check_call(["git", "commit", "-m", "New exploit"], cwd=path)
        commit_hash = (
            check_output(["git", "rev-parse", "HEAD"], cwd=path).decode().strip()
        )

        check_call(["git", "checkout", "HEAD~1"], cwd=path)

        result = loop.run_until_complete(repo.scan())

        assert result is not None
        assert result.updated_exploits[0] == Path("high/ground")
        assert len(result.removed_exploits) == 0
        assert result.last_processed_hash == commit_hash

        write_file(new_exploit_path / "Dockerfile", "# something")
        check_call(["git", "add", "-A"], cwd=path)
        check_call(["git", "commit", "-m", "Update exploit"], cwd=path)
        commit_hash = (
            check_output(["git", "rev-parse", "HEAD"], cwd=path).decode().strip()
        )

        check_call(["git", "checkout", "HEAD~2"], cwd=path)

        result = loop.run_until_complete(repo.scan())

        assert result is not None
        assert result.updated_exploits[0] == Path("high/ground")
        assert len(result.removed_exploits) == 0
        assert result.last_processed_hash == commit_hash

        shutil.rmtree(new_exploit_path)
        check_call(["git", "add", "-A"], cwd=path)
        check_call(["git", "commit", "-m", "Remove exploit"], cwd=path)
        commit_hash = (
            check_output(["git", "rev-parse", "HEAD"], cwd=path).decode().strip()
        )

        check_call(["git", "checkout", "HEAD~2"], cwd=path)

        result = loop.run_until_complete(repo.scan())

        assert result is not None
        assert len(result.updated_exploits) == 0
        assert result.removed_exploits[0] == Path("high/ground")
        assert result.last_processed_hash == commit_hash
