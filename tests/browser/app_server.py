"""The app under test for one browser worker, as `tests/run_checks.py browser` starts it.

It makes a new, empty account database at EC_DATABASE_PATH and serves the app on the
listening socket the runner hands it (its file descriptor, the only argument). The
runner binds that socket to a free port first, so it knows the address before the app
starts, and no other process can take the port meanwhile."""

import os
import socket
import sys
from pathlib import Path

import uvicorn

from eight_characters.accounts.store import AccountStore


def main() -> None:
    listening = socket.socket(fileno=int(sys.argv[1]))
    AccountStore.create(Path(os.environ['EC_DATABASE_PATH']))
    config = uvicorn.Config('eight_characters.main:app', log_level='warning')
    uvicorn.Server(config).run(sockets=[listening])


if __name__ == '__main__':
    main()
