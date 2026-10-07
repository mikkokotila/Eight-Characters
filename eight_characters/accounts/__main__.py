"""Account database and backup commands: python -m eight_characters.accounts --help."""

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pyrage

from eight_characters.accounts.backup import BackupError, run_backup, squash_history
from eight_characters.accounts.records import RecordError, timestamp
from eight_characters.accounts.restore import read_identity, restore_backup
from eight_characters.accounts.store import AccountStore, StoreError


def write_identity(path: Path) -> pyrage.x25519.Recipient:
    """A new age key pair: the private key into a new file only its owner can read,
    in the form `age-keygen` writes; the public key returned."""
    identity = pyrage.x25519.Identity.generate()
    recipient = identity.to_public()
    text = (
        f'# created: {timestamp(datetime.now(UTC))}\n'
        f'# public key: {recipient}\n'
        f'{identity}\n'
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        handle.write(text)
    return recipient


def parse_recipient(text: str) -> pyrage.x25519.Recipient:
    try:
        return pyrage.x25519.Recipient.from_str(text)
    except pyrage.RecipientError as exc:
        raise BackupError('The recipient is not an age public key (age1…).') from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='python -m eight_characters.accounts',
        description='The account database and its encrypted Git backup.',
    )
    commands = parser.add_subparsers(dest='command', required=True)

    init = commands.add_parser('init', help='Create a new, empty account database.')
    init.add_argument('--database', type=Path, required=True)

    keygen = commands.add_parser(
        'keygen',
        help='Make the backup key pair: the private key into a new file, the '
        'public key printed. Keep the private key offline.',
    )
    keygen.add_argument('--identity', type=Path, required=True)

    backup = commands.add_parser(
        'backup',
        help='Copy the records changed since the last backup into the checkout, '
        'commit and push.',
    )
    backup.add_argument('--database', type=Path, required=True)
    backup.add_argument('--checkout', type=Path, required=True)
    backup.add_argument(
        '--recipient', required=True, help='The age public key (age1…).'
    )
    backup.add_argument(
        '--heartbeat',
        type=int,
        metavar='SECONDS',
        help='With nothing new, commit an empty "backup: alive" once the last commit '
        'is this old, so a quiet backup is told from a stopped one.',
    )

    restore = commands.add_parser(
        'restore', help='Build a new account database from a backup checkout.'
    )
    restore.add_argument('--checkout', type=Path, required=True)
    restore.add_argument(
        '--identity', type=Path, required=True, help='The age private key file.'
    )
    restore.add_argument('--database', type=Path, required=True)

    squash = commands.add_parser(
        'squash-history',
        help='Replace the backup history with one commit of its current files.',
    )
    squash.add_argument('--database', type=Path, required=True)
    squash.add_argument('--checkout', type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    command = cast(str, args.command)
    try:
        if command == 'init':
            database = cast(Path, args.database)
            AccountStore.create(database)
            print(f'Created an empty account database at {database}.')
        elif command == 'keygen':
            recipient = write_identity(cast(Path, args.identity))
            print(recipient)
        elif command == 'backup':
            seconds = cast(int | None, args.heartbeat)
            if seconds is not None and seconds < 1:
                raise BackupError('--heartbeat must be at least one second.')
            store = AccountStore.open(cast(Path, args.database))
            result = run_backup(
                store,
                cast(Path, args.checkout),
                parse_recipient(cast(str, args.recipient)),
                None if seconds is None else timedelta(seconds=seconds),
            )
            print(
                f'{result.written} written, {result.removed} removed'
                f'{", alive" if result.heartbeat else ""}, '
                f'{"pushed" if result.pushed else "nothing to push"}; '
                f'backed up through change {result.backed_up_seq}.'
            )
        elif command == 'restore':
            restored = restore_backup(
                cast(Path, args.checkout),
                read_identity(cast(Path, args.identity)),
                cast(Path, args.database),
            )
            print(f'Restored {restored.users} users into {args.database}.')
        elif command == 'squash-history':
            store = AccountStore.open(cast(Path, args.database))
            print(squash_history(store, cast(Path, args.checkout)))
        else:
            raise AssertionError(f'Unhandled command {command!r}')
    except (BackupError, RecordError, StoreError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    except FileExistsError as exc:
        print(f'error: {exc.filename} exists already.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
