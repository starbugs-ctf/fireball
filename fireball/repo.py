import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import List, NamedTuple, Optional, Set

from .exceptions import RepoScanError

logger = logging.getLogger(__name__)


def log_failed_process(message: str, stdout: bytes, stderr: bytes):
    stdout_str = stdout.decode()
    stderr_str = stderr.decode()
    logger.error(
        "%s:\nStdout:\n```\n%s```\nStderr:\n```\n%s```",
        message,
        stdout_str,
        stderr_str,
        stacklevel=2,
    )


async def git_fetch(path: Path):
    proc = await asyncio.create_subprocess_exec(
        "git",
        "fetch",
        "--all",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=path,
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        log_failed_process("Failed to fetch new git objects", stdout, stderr)
        raise RepoScanError("Failed to fetch new git objects")


async def git_checkout(path: Path, branch: str):
    proc = await asyncio.create_subprocess_exec(
        "git",
        "checkout",
        branch,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=path,
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        log_failed_process("Failed to checkout repo", stdout, stderr)
        raise RepoScanError("Failed to checkout repo")


async def git_get_hash(path: Path) -> str:
    proc = await asyncio.create_subprocess_exec(
        "git",
        "rev-parse",
        "HEAD",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=path,
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        log_failed_process("Failed to get repo hash", stdout, stderr)
        raise RepoScanError("Failed to get repo hash")

    return stdout.decode().strip()


async def git_changed_exploits(path: Path, from_hash: str) -> Set[PurePosixPath]:
    proc = await asyncio.create_subprocess_exec(
        "git",
        "diff",
        "--name-status",
        from_hash,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=path,
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        log_failed_process("Failed to diff repo", stdout, stderr)
        raise RepoScanError("Failed to diff repo")

    result = set()
    lines = stdout.decode().strip().split("\n")
    for line in lines:
        if line == "":
            continue

        status, path_str = line.split()
        rel_path = PurePosixPath(path_str)

        if len(rel_path.parts) < 3:
            # it is a change outside exploit folders
            continue

        # e.g. "test-problem/test-exploit-2"
        result.add(PurePosixPath(*rel_path.parts[:2]))

    return result


@dataclass
class RepoScanResult:
    updated_exploits: List[Path]
    removed_exploits: List[Path]
    last_processed_hash: str


class Repo:
    def __init__(self, path: str, branch: str):
        self.path = Path(path).absolute()
        assert (self.path / ".git").exists(), "Unable to find git repo"

        # Will be initialized in connect()
        self.last_processed_hash = ""
        self.branch = branch

    async def connect(self) -> None:
        self.last_processed_hash = await git_get_hash(self.path)

    async def scan(self) -> Optional[RepoScanResult]:
        await git_fetch(self.path)
        await git_checkout(self.path, self.branch)

        new_hash = await git_get_hash(self.path)
        if new_hash == self.last_processed_hash:
            # no new commits
            return None

        changes = await git_changed_exploits(self.path, self.last_processed_hash)
        updated_exploits = set()
        removed_exploits = set()

        for exploit_dir in changes:
            full_path = self.path / exploit_dir

            if full_path.exists():
                # something was modified
                updated_exploits.add(exploit_dir)
            else:
                # that exploit directory was deleted
                removed_exploits.add(exploit_dir)

        self.last_processed_hash = new_hash

        return RepoScanResult(
            updated_exploits=list(updated_exploits),
            removed_exploits=list(removed_exploits),
            last_processed_hash=self.last_processed_hash,
        )
