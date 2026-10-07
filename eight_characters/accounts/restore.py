"""Rebuilding the account database from a backup checkout.

Every file is checked before anything is written: the manifest, the key, the layout,
each record's decryption and form, and the count. The new database appears only
once it holds them all.
"""

from dataclasses import dataclass
from pathlib import Path

import pyrage

from eight_characters.accounts.backup import (
    BackupError,
    checkout_lock,
    own_tree,
    read_manifest,
    record_files,
    require_clean,
    work_tree,
)
from eight_characters.accounts.records import RecordError, User, decode_user
from eight_characters.accounts.store import AccountStore, StoreError


class RestoreError(BackupError):
    """The backup cannot be restored as it is; the message says why."""


@dataclass(frozen=True)
class RestoreResult:
    users: int


def read_identity(path: Path) -> pyrage.x25519.Identity:
    """The age private key in an identity file, as `age-keygen` or `keygen` write it."""
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except OSError as exc:
        raise RestoreError(f'Cannot read the key file {path}: {exc.strerror}') from exc
    except UnicodeDecodeError as exc:
        raise RestoreError(f'{path} is not text, so it holds no age key.') from exc
    keys = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
    if len(keys) != 1:
        raise RestoreError(f'{path} must hold exactly one age private key.')
    try:
        return pyrage.x25519.Identity.from_str(keys[0])
    except pyrage.IdentityError as exc:
        raise RestoreError(f'{path} does not hold an age private key.') from exc


def restore_backup(
    checkout: Path, identity: pyrage.x25519.Identity, database: Path
) -> RestoreResult:
    """A new account database at `database`, rebuilt from the backup in `checkout`."""
    if database.exists():
        raise RestoreError(f'{database} exists already; restore into a new path.')
    root = work_tree(checkout)
    # Held while reading, so a backup run cannot change files half way through.
    with checkout_lock(root):
        require_clean(root)
        manifest = read_manifest(root)
        if manifest is None:
            raise RestoreError('The checkout has no manifest.json; it is no backup.')
        tree = own_tree(root)
        if tree is None:
            raise RestoreError('The checkout has no commits; it is no backup.')
        if manifest.recipient != str(identity.to_public()):
            raise RestoreError('This key is not the one the backup was encrypted to.')
        users: list[User] = []
        emails: set[str] = set()
        for name, user_id in record_files(root):
            try:
                plaintext = pyrage.decrypt((root / name).read_bytes(), [identity])
            except pyrage.DecryptError as exc:
                raise RestoreError(f'{name} does not decrypt with this key.') from exc
            try:
                user = decode_user(plaintext)
            except RecordError as exc:
                raise RestoreError(f'{name}: {exc}') from exc
            if user.id != user_id:
                raise RestoreError(f'{name} holds the record of another user.')
            if user.email in emails:
                raise RestoreError(f"{name} repeats another account's email address.")
            emails.add(user.email)
            users.append(user)
        if len(users) != manifest.user_count:
            raise RestoreError(
                f'The backup holds {len(users)} users but its manifest counts '
                f'{manifest.user_count}.'
            )
        try:
            AccountStore.restore(database, users, tree=tree)
        except StoreError as exc:
            raise RestoreError(str(exc)) from exc
    return RestoreResult(users=len(users))
