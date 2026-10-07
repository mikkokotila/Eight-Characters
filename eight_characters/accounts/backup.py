"""The backup: every account record as its own age-encrypted file in a Git checkout.

A run writes the records changed since the last run that reached the remote, commits
them and pushes; only then does the database count them as backed up. Files are
encrypted to a public key (the recipient), so the server and GitHub hold nothing
readable: the private key stays offline with whoever restores.

The backup job owns the checkout. A checkout with changes of its own, a commit the
backup did not make, a manifest made for another key, or a file count that differs
from the database stops the run, with the reason, rather than being worked around.
"""

import fcntl
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

import pyrage

from eight_characters.accounts.records import canonical_json, encode_user, is_id
from eight_characters.accounts.store import AccountStore, BackupSnapshot

ENCRYPTED_SUFFIX: Final = '.age'
MANIFEST: Final = 'manifest.json'
MANIFEST_SCHEMA: Final = 1
USER_FILE: Final = 'user.json.age'
# Everything a backup checkout may hold at its root, and which of it are files.
TOP_LEVEL: Final = frozenset({'.git', '.gitattributes', 'README.md', MANIFEST, 'users'})
_TOP_LEVEL_FILES: Final = frozenset({'.gitattributes', 'README.md', MANIFEST})
# In the Git directory while a run writes into the checkout: the next run knows from
# it that one stopped part way, and takes up what it left.
WRITING_MARKER: Final = 'eight-characters-backup.writing'
_MANIFEST_FIELDS: Final = frozenset({'counts', 'encryption', 'recipient', 'schema'})
_SHARD = re.compile(r'[0-9a-f]{2}')
# A hung command fails the run instead of holding it forever.
GIT_TIMEOUT_SECONDS: Final = 120.0
README: Final = b"""# Eight Characters account backup

Every account record is its own file under `users/`, encrypted with age
(https://age-encryption.org) to the public key in `manifest.json`. Only the holder
of the matching private key can read them.

Rebuild an account database from a clone of this repository:

    python -m eight_characters.accounts restore --checkout . --identity KEY_FILE --database NEW_DATABASE

Read one record:

    age --decrypt --identity KEY_FILE users/3f/3f.../user.json.age

The backup job writes everything here. Commits made by hand stop it.
"""
STATIC_FILES: Final[dict[str, bytes]] = {
    'README.md': README,
    '.gitattributes': b'*.age binary\n',
}
_COMMITTER: Final = (
    '-c',
    'user.name=Eight Characters backup',
    '-c',
    'user.email=backup@eight-characters.invalid',
    '-c',
    'commit.gpgsign=false',
)


class BackupError(Exception):
    """The backup run stopped; the message says why."""


class BackupBusy(BackupError):
    """Another backup run holds the checkout."""


@dataclass(frozen=True)
class BackupResult:
    written: int
    removed: int
    commit: str | None
    pushed: bool
    backed_up_seq: int
    # Whether the run first took up one that stopped while writing.
    recovered: bool = False


@dataclass(frozen=True)
class Manifest:
    """What the backup says of itself: the key its files are encrypted to, and how
    many records it holds."""

    recipient: str
    user_count: int


def _git_run(
    root: Path, args: tuple[str, ...], stdin: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ('git', '-C', str(root), *args),
            input=stdin,
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
            # Never wait for a password nobody will type.
            env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'},
        )
    except subprocess.TimeoutExpired as exc:
        raise BackupError(
            f'git {args[0]} took longer than {GIT_TIMEOUT_SECONDS:.0f} s.'
        ) from exc


def _git(root: Path, *args: str, stdin: bytes | None = None) -> str:
    completed = _git_run(root, args, stdin)
    if completed.returncode != 0:
        message = completed.stderr.decode(errors='replace').strip()
        raise BackupError(f'git {args[0]} failed ({completed.returncode}): {message}')
    return completed.stdout.decode()


def _git_ref(root: Path, ref: str) -> str | None:
    """The commit a ref names, or None when it names none (yet)."""
    completed = _git_run(
        root, ('rev-parse', '--verify', '--quiet', f'{ref}^{{commit}}')
    )
    if completed.returncode == 1:
        return None
    if completed.returncode != 0:
        message = completed.stderr.decode(errors='replace').strip()
        raise BackupError(f'git rev-parse failed ({completed.returncode}): {message}')
    return completed.stdout.decode().strip()


def work_tree(checkout: Path) -> Path:
    """The checkout's root, which must be the root of its own Git work tree."""
    if not checkout.is_dir():
        raise BackupError(f'The backup checkout {checkout} is not a folder.')
    root = checkout.resolve()
    completed = _git_run(root, ('rev-parse', '--show-toplevel'))
    top = completed.stdout.decode().strip()
    if completed.returncode != 0 or Path(top).resolve() != root:
        raise BackupError(f'{checkout} is not the root of a Git checkout.')
    return root


@contextmanager
def checkout_lock(root: Path) -> Generator[None, None, None]:
    """Holds the checkout for one run; a second run at the same time is refused."""
    git_dir = Path(_git(root, 'rev-parse', '--absolute-git-dir').strip())
    with open(git_dir / 'eight-characters-backup.lock', 'w') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BackupBusy('Another backup run holds the checkout.') from exc
        yield


def git_dir(root: Path) -> Path:
    return Path(_git(root, 'rev-parse', '--absolute-git-dir').strip())


def _branch_ref(root: Path) -> str:
    return _git(root, 'symbolic-ref', 'HEAD').strip()


def _take_up_stopped_run(root: Path, directory: Path) -> bool:
    """Puts back a checkout that a run left part written, as a killed process or a
    restart leaves it, and says whether there was one. Its marker says the changes it
    left are its own; the database still holds them, so the next run writes them
    again. Without the marker, changes are someone else's, and stop the run."""
    marker = directory / WRITING_MARKER
    if not marker.exists():
        return False
    # Locks that Git commands stopped with it left behind. The checkout lock is held,
    # so no other run is using them.
    for lock in ('index.lock', f'{_branch_ref(root)}.lock'):
        (directory / lock).unlink(missing_ok=True)
    _discard_uncommitted(root)
    marker.unlink()
    return True


def _mark_writing(directory: Path) -> None:
    # On disk before the first file is written, so that even a power cut leaves it.
    descriptor = os.open(directory / WRITING_MARKER, os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    folder = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(folder)
    finally:
        os.close(folder)


def require_clean(root: Path) -> None:
    status = _git(root, 'status', '--porcelain=v1', '--untracked-files=all')
    if status.strip():
        raise BackupError(
            'The backup checkout has changes the backup did not make; '
            f'it holds only what the backup writes:\n{status.rstrip()}'
        )


def _write_atomically(target: Path, data: bytes, scratch: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    # Written beside the repository's own files, so a crash leaves nothing in the tree.
    descriptor, name = tempfile.mkstemp(dir=scratch, prefix='eight-characters-')
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(data)
        os.replace(name, target)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def _write_if_different(target: Path, data: bytes, scratch: Path) -> bool:
    if target.is_file() and target.read_bytes() == data:
        return False
    _write_atomically(target, data, scratch)
    return True


def _remove_empty_parents(directory: Path, root: Path) -> None:
    while directory != root and directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent


def manifest_bytes(manifest: Manifest) -> bytes:
    return canonical_json(
        {
            'counts': {'user': manifest.user_count},
            'encryption': 'age',
            'recipient': manifest.recipient,
            'schema': MANIFEST_SCHEMA,
        }
    )


def read_manifest(root: Path) -> Manifest | None:
    """The checkout's manifest, or None before the first backup wrote one."""
    path = root / MANIFEST
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise BackupError(f'{MANIFEST} in the backup is not a file.')
    data = path.read_bytes()
    try:
        value: object = json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError('The backup manifest is not UTF-8 JSON.') from exc
    if not isinstance(value, dict):
        raise BackupError('The backup manifest must be a JSON object.')
    fields = cast(dict[str, Any], value)
    if frozenset(fields) != _MANIFEST_FIELDS:
        raise BackupError(
            f'The backup manifest has the wrong fields: {sorted(fields)}.'
        )
    schema: object = fields['schema']
    if type(schema) is not int or schema != MANIFEST_SCHEMA:
        raise BackupError(
            f'A backup manifest of schema {schema!r} is not one this app reads.'
        )
    if fields['encryption'] != 'age':
        raise BackupError('The backup manifest names an encryption other than age.')
    recipient: object = fields['recipient']
    counts: object = fields['counts']
    if not isinstance(recipient, str) or not isinstance(counts, dict):
        raise BackupError("The backup manifest's recipient or counts are malformed.")
    tally = cast(dict[str, Any], counts)
    user_count: object = tally.get('user')
    if (
        frozenset(tally) != frozenset({'user'})
        or type(user_count) is not int
        or user_count < 0
    ):
        raise BackupError("The backup manifest's counts are malformed.")
    manifest = Manifest(recipient=recipient, user_count=user_count)
    if manifest_bytes(manifest) != data:
        raise BackupError('The backup manifest is not in canonical form.')
    return manifest


def _listing(directory: Path, where: str) -> list[Path]:
    """A folder's entries in name order. A link could lead outside the checkout, so
    one anywhere stops the backup."""
    entries = sorted(directory.iterdir())
    for entry in entries:
        if entry.is_symlink():
            raise BackupError(
                f'The backup holds a link, which it never writes: {where}{entry.name}'
            )
    return entries


def record_files(root: Path) -> list[tuple[str, str]]:
    """Every user record file in the checkout, as (path from the root, user id).

    Anything the backup never writes stops it here, links included, so that a restore
    never meets a file it does not know. Empty folders, which Git does not keep, are
    passed over.
    """
    for entry in _listing(root, ''):
        if entry.name not in TOP_LEVEL:
            raise BackupError(
                f'The backup holds something it never writes: {entry.name}'
            )
        if entry.name in _TOP_LEVEL_FILES and not entry.is_file():
            raise BackupError(
                f'The backup holds {entry.name} as something other than the file '
                'it writes.'
            )
    users = root / 'users'
    if not users.exists():
        return []
    if not users.is_dir():
        raise BackupError('users in the backup is not a folder.')
    found: list[tuple[str, str]] = []
    for shard in _listing(users, 'users/'):
        if not shard.is_dir() or _SHARD.fullmatch(shard.name) is None:
            raise BackupError(
                f'The backup holds something it never writes: users/{shard.name}'
            )
        for folder in _listing(shard, f'users/{shard.name}/'):
            where = f'users/{shard.name}/{folder.name}'
            if (
                not folder.is_dir()
                or not is_id(folder.name)
                or folder.name[:2] != shard.name
            ):
                raise BackupError(
                    f'The backup holds something it never writes: {where}'
                )
            names = [entry.name for entry in _listing(folder, f'{where}/')]
            if not names:
                continue
            if names != [USER_FILE] or not (folder / USER_FILE).is_file():
                raise BackupError(
                    f'{where} should hold the file {USER_FILE} alone, not {names}.'
                )
            found.append((f'{where}/{USER_FILE}', folder.name))
    return found


def head_commit(root: Path) -> str | None:
    """The checkout's last commit, or None before the first."""
    return _git_ref(root, 'HEAD')


def _push_if_ahead(root: Path) -> bool:
    branch = _git(root, 'symbolic-ref', '--short', 'HEAD').strip()
    head = _git_ref(root, 'HEAD')
    if head is None:
        return False
    if _git_ref(root, f'refs/remotes/origin/{branch}') == head:
        return False
    _git(root, 'push', '--quiet', 'origin', f'HEAD:refs/heads/{branch}')
    return True


def _discard_uncommitted(root: Path) -> None:
    """Puts the work tree and the index back to the last commit, dropping what a run
    wrote. The run began with a clean checkout, so everything uncommitted is its own."""
    if _git_ref(root, 'HEAD') is None:
        _git(root, 'read-tree', '--empty')
    else:
        _git(root, 'reset', '--quiet', '--hard', 'HEAD')
    _git(root, 'clean', '--quiet', '--force', '-d')


def _advance(root: Path, store: AccountStore, tree: str, message: str) -> str:
    """Commits `tree` on the checkout's branch and returns the commit. It is recorded
    as pending before the branch moves to it, and as the backup's own after: a run
    stopped in between is taken up by the next, which finds the checkout at the
    pending commit."""
    parent = head_commit(root)
    commit = _git(
        root,
        *_COMMITTER,
        'commit-tree',
        tree,
        *(('-p', parent) if parent is not None else ()),
        '-m',
        message,
    ).strip()
    store.record_pending_head(commit)
    # Moves only from the parent: anything else there makes Git refuse.
    _git(root, 'update-ref', _branch_ref(root), commit, parent or '')
    store.record_backup_head(commit)
    return commit


def _require_own_head(
    root: Path, store: AccountStore, snapshot: BackupSnapshot
) -> None:
    """Stops the run unless the checkout's last commit is the one the backup made last
    (or read, when restored), or one it made and had not recorded yet. Comparing
    commits, not files, catches commits made by hand even when undone since: pushing
    would publish them."""
    if snapshot.squash_of is not None:
        raise BackupError(
            'A squash of the history stopped part way; run squash-history again '
            'to finish it.'
        )
    current = head_commit(root)
    if current == snapshot.head:
        if snapshot.pending_head is not None:
            # The last run stopped before moving the checkout to its commit.
            store.record_backup_head(current)
        return
    if snapshot.pending_head is not None and current == snapshot.pending_head:
        # The last run moved the checkout to its commit and stopped before recording
        # it.
        store.record_backup_head(current)
        return
    raise BackupError(
        'The checkout is not the backup this database last wrote: it holds commits '
        'the backup did not make (even ones undone since), or another backup.'
    )


def _write_and_commit(
    root: Path,
    store: AccountStore,
    snapshot: BackupSnapshot,
    recipient: pyrage.x25519.Recipient,
    scratch: Path,
) -> tuple[int, int, str | None]:
    """Writes the snapshot's records into the work tree and commits them; returns
    how many were written and removed, and the commit (None if nothing changed)."""
    touched: list[str] = []
    for name, content in STATIC_FILES.items():
        if _write_if_different(root / name, content, scratch):
            touched.append(name)
    written = 0
    removed = 0
    for change in snapshot.changes:
        name = f'{change.path}{ENCRYPTED_SUFFIX}'
        target = root / name
        if change.user is not None:
            ciphertext = pyrage.encrypt(encode_user(change.user), [recipient])
            _write_atomically(target, ciphertext, scratch)
            written += 1
            touched.append(name)
        elif target.exists():
            target.unlink()
            _remove_empty_parents(target.parent, root)
            removed += 1
            touched.append(name)
        # A record made and deleted between two runs never reached the backup.
    manifest = Manifest(recipient=str(recipient), user_count=snapshot.user_count)
    if _write_if_different(root / MANIFEST, manifest_bytes(manifest), scratch):
        touched.append(MANIFEST)
    on_disk = len(record_files(root))
    if on_disk != snapshot.user_count:
        raise BackupError(
            f'The checkout holds {on_disk} user files but the database '
            f'{snapshot.user_count} users.'
        )
    if not touched:
        return written, removed, None
    _git(
        root,
        'add',
        '--all',
        '--pathspec-from-file=-',
        '--pathspec-file-nul',
        stdin='\0'.join(touched).encode(),
    )
    if not _git(root, 'diff', '--cached', '--name-only'):
        return written, removed, None
    commit = _advance(
        root,
        store,
        _git(root, 'write-tree').strip(),
        f'backup: {written} written, {removed} removed',
    )
    return written, removed, commit


def run_backup(
    store: AccountStore, checkout: Path, recipient: pyrage.x25519.Recipient
) -> BackupResult:
    """Copies every record changed since the last backup into the checkout, then
    commits, pushes and marks the changes backed up, in that order.

    A run that fails before its commit puts the checkout back as it found it, so the
    next run meets the same problem and names it; one stopped outright (killed, or
    the server restarting) is put back by the next run.
    """
    root = work_tree(checkout)
    with checkout_lock(root):
        scratch = git_dir(root)
        recovered = _take_up_stopped_run(root, scratch)
        require_clean(root)
        records = record_files(root)
        existing = read_manifest(root)
        if existing is None and records:
            raise BackupError(
                'The backup holds records but no manifest naming the key they are '
                'encrypted to.'
            )
        if existing is not None and existing.recipient != str(recipient):
            raise BackupError(
                'The backup was encrypted to another key. Files made for two keys '
                'would leave a restore that can read only some of them.'
            )
        snapshot = store.backup_snapshot()
        # Without the private key the server cannot read a file, but it knows what it
        # committed last: anything else in the checkout, such as a file corrupted or
        # changed by hand, stops the run before it adds to it.
        _require_own_head(root, store, snapshot)
        _mark_writing(scratch)
        try:
            # The commit is recorded before the push, so a failed push leaves it for
            # the next run to push.
            written, removed, commit = _write_and_commit(
                root, store, snapshot, recipient, scratch
            )
        except BaseException:
            _discard_uncommitted(root)
            (scratch / WRITING_MARKER).unlink()
            raise
        (scratch / WRITING_MARKER).unlink()
        pushed = _push_if_ahead(root)
        store.mark_backed_up(snapshot.through_seq)
    return BackupResult(
        written=written,
        removed=removed,
        commit=commit,
        pushed=pushed,
        backed_up_seq=snapshot.through_seq,
        recovered=recovered,
    )


def squash_history(store: AccountStore, checkout: Path) -> str:
    """Replaces the backup's history with one commit of its current files.

    Deleted accounts leave the history this way. Only the backup this database last
    wrote, whole, is squashed: the history may be all that holds a record lost since.
    Everything must be pushed first, and the remote must not have moved: the force push
    names the commit it replaces.

    The squash is recorded before anything moves, and the remote moves before the
    checkout. Stopped part way, it stops the backup until it is run again, which
    finishes it; a push that fails while the remote has not moved leaves the history
    as it was, and the backup goes on.
    """
    root = work_tree(checkout)
    with checkout_lock(root):
        _take_up_stopped_run(root, git_dir(root))
        require_clean(root)
        records = record_files(root)
        manifest = read_manifest(root)
        if manifest is None:
            raise BackupError('The checkout has no manifest.json; it is no backup.')
        if len(records) != manifest.user_count:
            raise BackupError(
                f'The backup holds {len(records)} records but its manifest counts '
                f'{manifest.user_count}; its history may hold the others.'
            )
        snapshot = store.backup_snapshot()
        branch = _git(root, 'symbolic-ref', '--short', 'HEAD').strip()
        local = head_commit(root)
        if local is None:
            raise BackupError('The backup has no commits to squash.')
        _git(root, 'fetch', '--quiet', 'origin', branch)
        remote = _git_ref(root, f'refs/remotes/origin/{branch}')
        if snapshot.squash_of is None:
            if local != snapshot.head:
                raise BackupError(
                    'The checkout is not the backup this database last wrote; its '
                    'history stays.'
                )
            if remote != local:
                raise BackupError(
                    'The backup checkout and its remote differ; push or reconcile '
                    'first.'
                )
            tree = _git(root, 'rev-parse', 'HEAD^{tree}').strip()
            squashed = _git(
                root,
                *_COMMITTER,
                'commit-tree',
                tree,
                '-m',
                'backup: history squashed',
            ).strip()
            base = local
            store.record_pending_squash(squashed, base)
        else:
            squashed, base = snapshot.pending_head, snapshot.squash_of
            if squashed is None:
                raise BackupError('The database records a squash without its commit.')
            # The remote moves first, so the checkout never stands ahead of it.
            if (
                local not in (base, squashed)
                or remote not in (base, squashed)
                or (local == squashed and remote == base)
            ):
                raise BackupError(
                    'A squash stopped part way, and its checkout or remote has moved '
                    'since; reconcile them by hand.'
                )
        if remote == base:
            pushed = _git_run(
                root,
                (
                    'push',
                    '--quiet',
                    f'--force-with-lease=refs/heads/{branch}:{base}',
                    'origin',
                    f'{squashed}:refs/heads/{branch}',
                ),
            )
            if pushed.returncode != 0:
                message = pushed.stderr.decode(errors='replace').strip()
                _git(root, 'fetch', '--quiet', 'origin', branch)
                if _git_ref(root, f'refs/remotes/origin/{branch}') != base:
                    raise BackupError(
                        f'git push failed ({pushed.returncode}) and the remote has '
                        f'moved: {message}'
                    )
                # Nothing moved: the backup goes on with its history.
                store.record_backup_head(base)
                raise BackupError(
                    f'git push failed ({pushed.returncode}); the history stays as it '
                    f'was: {message}'
                )
        if local == base:
            _git(root, 'update-ref', f'refs/heads/{branch}', squashed, base)
        store.record_backup_head(squashed)
        # The old commits are gone from the remote; drop them here too.
        _git(root, 'reflog', 'expire', '--expire=now', '--all')
        _git(root, 'gc', '--quiet', '--prune=now')
    return squashed
