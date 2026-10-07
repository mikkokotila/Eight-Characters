"""Shared set-up for the account tests: a fixed clock, Git remotes and checkouts."""

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Commits the tests make by hand carry an identity of their own, so no global Git
# configuration is needed.
COMMITTER = (
    '-c',
    'user.name=Test',
    '-c',
    'user.email=test@example.invalid',
    '-c',
    'commit.gpgsign=false',
)


class Clock:
    """A clock the test moves by hand."""

    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 10, 7, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ('git', '-C', str(root), *COMMITTER, *args),
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f'git {" ".join(args)} failed: {completed.stderr.decode(errors="replace")}'
        )
    return completed.stdout.decode()


def make_remote_and_checkout(base: Path) -> tuple[Path, Path]:
    """An empty bare repository and a clone of it, as a new backup starts."""
    remote = base / 'remote.git'
    checkout = base / 'checkout'
    subprocess.run(('git', 'init', '--quiet', '--bare', str(remote)), check=True)
    subprocess.run(
        ('git', 'clone', '--quiet', str(remote), str(checkout)),
        check=True,
        capture_output=True,
    )
    return remote, checkout


def all_object_contents(repository: Path) -> bytes:
    """Every object in a repository, decompressed, so a search sees what Git stores."""
    return subprocess.run(
        ('git', '-C', str(repository), 'cat-file', '--batch-all-objects', '--batch'),
        capture_output=True,
        check=True,
    ).stdout
