"""The account database: one SQLite file.

Every change to a record the backup keeps (so far, a user) is logged in the
`changes` table in the same transaction as the change itself, and the backup copies
exactly the records logged there. The database is never created by accident: opening
one that is missing fails, and a new or restored one is built aside and moved into
place only when complete.
"""

import os
import sqlite3
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from eight_characters.accounts.records import (
    Language,
    Plan,
    RecordError,
    RecordKind,
    User,
    is_id,
    is_language,
    is_plan,
    new_id,
    normalize_email,
    timestamp,
    user_path,
)

# Numbered migrations: the database's `user_version` is how many have run. Each runs
# in its own transaction, so a database is always at one version or the next.
MIGRATIONS: Final[tuple[tuple[str, ...], ...]] = (
    (
        """
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            language TEXT NOT NULL CHECK (language IN ('fi', 'en')),
            plan TEXT NOT NULL CHECK (plan IN ('free', 'basic', 'pro', 'max')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        ) STRICT
        """,
        """
        CREATE TABLE changes (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL CHECK (kind IN ('user')),
            record_id TEXT NOT NULL,
            path TEXT NOT NULL
        ) STRICT
        """,
        """
        CREATE TABLE backup_progress (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            backed_up_seq INTEGER NOT NULL
        ) STRICT
        """,
        'INSERT INTO backup_progress (id, backed_up_seq) VALUES (1, 0)',
    ),
)
SCHEMA_VERSION: Final = len(MIGRATIONS)
BUSY_TIMEOUT_SECONDS: Final = 5.0
_USER_COLUMNS: Final = 'id, email, language, plan, created_at, updated_at'


class StoreError(Exception):
    """The account database cannot do what was asked."""


class EmailTaken(StoreError):
    """An account with that email address exists already."""


class UnknownUser(StoreError):
    """No account has that id."""


@dataclass(frozen=True)
class RecordChange:
    """A record changed since the last backup: its path, and it now (None if gone)."""

    path: str
    user: User | None


@dataclass(frozen=True)
class BackupSnapshot:
    """What the backup has to copy, read in one transaction.

    Changes up to `after_seq` are in the backup already; this snapshot covers those up
    to `through_seq`, one entry per record however often it changed.
    """

    after_seq: int
    through_seq: int
    changes: tuple[RecordChange, ...]
    user_count: int


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _uri(path: Path, mode: str) -> str:
    # `mode=rw` refuses a missing file instead of creating an empty database.
    return f'{path.resolve().as_uri()}?mode={mode}'


@contextmanager
def _connection(
    path: Path, mode: str = 'rw'
) -> Generator[sqlite3.Connection, None, None]:
    connection = sqlite3.connect(
        _uri(path, mode), uri=True, isolation_level=None, timeout=BUSY_TIMEOUT_SECONDS
    )
    try:
        connection.execute('PRAGMA foreign_keys = ON')
        # With the write-ahead log, FULL makes every commit durable on its own.
        connection.execute('PRAGMA synchronous = FULL')
        yield connection
    finally:
        connection.close()


def _user_version(connection: sqlite3.Connection) -> int:
    row = connection.execute('PRAGMA user_version').fetchone()
    version = row[0]
    if not isinstance(version, int):
        raise StoreError('The database reports no schema version.')
    return version


def _migrate(connection: sqlite3.Connection, from_version: int) -> None:
    for version in range(from_version + 1, SCHEMA_VERSION + 1):
        connection.execute('BEGIN IMMEDIATE')
        try:
            for statement in MIGRATIONS[version - 1]:
                connection.execute(statement)
            connection.execute(f'PRAGMA user_version = {version}')
        except BaseException:
            connection.execute('ROLLBACK')
            raise
        connection.execute('COMMIT')


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _user_from_row(row: tuple[Any, ...]) -> User:
    fields = [str(value) if isinstance(value, str) else None for value in row]
    identifier, email, language, plan, created_at, updated_at = fields
    if (
        identifier is None
        or email is None
        or language is None
        or plan is None
        or created_at is None
        or updated_at is None
    ):
        raise StoreError('A user row holds a value that is not text.')
    if not is_language(language) or not is_plan(plan):
        raise StoreError('A user row holds an unknown language or plan.')
    return User(
        id=identifier,
        email=email,
        language=language,
        plan=plan,
        created_at=created_at,
        updated_at=updated_at,
    )


def _select_user(connection: sqlite3.Connection, where: str, value: str) -> User | None:
    row = connection.execute(
        f'SELECT {_USER_COLUMNS} FROM users WHERE {where} = ?', (value,)
    ).fetchone()
    return None if row is None else _user_from_row(row)


def _log_change(
    connection: sqlite3.Connection, kind: RecordKind, record_id: str, path: str
) -> None:
    connection.execute(
        'INSERT INTO changes (kind, record_id, path) VALUES (?, ?, ?)',
        (kind, record_id, path),
    )


def _insert_user(connection: sqlite3.Connection, user: User) -> None:
    connection.execute(
        f'INSERT INTO users ({_USER_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?)',
        (
            user.id,
            user.email,
            user.language,
            user.plan,
            user.created_at,
            user.updated_at,
        ),
    )


def _scalar(connection: sqlite3.Connection, query: str, *params: object) -> int:
    row = connection.execute(query, params).fetchone()
    value = None if row is None else row[0]
    if not isinstance(value, int):
        raise StoreError(f'Expected a number from: {query}')
    return value


class AccountStore:
    """The account database at one path. Each call opens its own connection."""

    def __init__(self, path: Path, *, clock: Callable[[], datetime] = _utc_now) -> None:
        self.path = path
        self._clock = clock

    @classmethod
    def open(
        cls, path: Path, *, clock: Callable[[], datetime] = _utc_now
    ) -> 'AccountStore':
        """The database at `path`, brought to this app's schema.

        Refuses a missing file, a file that is no account database, and a database
        from a newer version of the app.
        """
        if not path.is_file():
            raise StoreError(f'No account database at {path}.')
        with _connection(path) as connection:
            version = _user_version(connection)
            if version == 0:
                raise StoreError(f'{path} is not an account database.')
            if version > SCHEMA_VERSION:
                raise StoreError(
                    f'The database at {path} has schema {version}; this version of '
                    f'the app knows schemas up to {SCHEMA_VERSION}.'
                )
            _migrate(connection, version)
        return cls(path, clock=clock)

    @classmethod
    def create(
        cls, path: Path, *, clock: Callable[[], datetime] = _utc_now
    ) -> 'AccountStore':
        """A new, empty database at `path`, which must not exist."""
        return cls._build(path, (), clock)

    @classmethod
    def restore(
        cls,
        path: Path,
        users: Sequence[User],
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> 'AccountStore':
        """A new database at `path` holding exactly these users, as backed up.

        Nothing is logged for the backup: the records came from it.
        """
        return cls._build(path, users, clock)

    @classmethod
    def _build(
        cls,
        path: Path,
        users: Sequence[User],
        clock: Callable[[], datetime],
    ) -> 'AccountStore':
        if path.exists():
            raise StoreError(f'{path} exists already; refusing to build over it.')
        partial = path.with_name(f'{path.name}.partial')
        if partial.exists():
            raise StoreError(
                f'{partial} is left from an interrupted build; remove it first.'
            )
        try:
            with _connection(partial, 'rwc') as connection:
                os.chmod(partial, 0o600)
                _migrate(connection, 0)
                connection.execute('BEGIN IMMEDIATE')
                try:
                    for user in users:
                        _insert_user(connection, user)
                except BaseException:
                    connection.execute('ROLLBACK')
                    raise
                connection.execute('COMMIT')
            # A hard link moves it into place only if nothing is there yet.
            os.link(partial, path)
        except sqlite3.IntegrityError as exc:
            partial.unlink(missing_ok=True)
            raise StoreError(f'The records cannot form one database: {exc}') from exc
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        partial.unlink()
        _fsync_directory(path.parent)
        with _connection(path) as connection:
            # Kept in the file, so every later connection writes ahead to a log.
            mode = connection.execute('PRAGMA journal_mode = WAL').fetchone()
            if mode is None or mode[0] != 'wal':
                raise StoreError(f'{path} cannot use a write-ahead log.')
        return cls(path, clock=clock)

    @contextmanager
    def _write(self) -> Generator[sqlite3.Connection, None, None]:
        with _connection(self.path) as connection:
            connection.execute('BEGIN IMMEDIATE')
            try:
                yield connection
            except BaseException:
                connection.execute('ROLLBACK')
                raise
            connection.execute('COMMIT')

    @contextmanager
    def _read(self) -> Generator[sqlite3.Connection, None, None]:
        # One transaction, so every query sees the same moment.
        with _connection(self.path) as connection:
            connection.execute('BEGIN')
            try:
                yield connection
            finally:
                connection.execute('ROLLBACK')

    def _now(self) -> str:
        return timestamp(self._clock())

    # ── Users ──

    def create_user(self, email: str, language: str) -> User:
        """A new free account. Raises EmailTaken if the address has one already."""
        if not is_language(language):
            raise RecordError(f'Unknown language: {language!r}.')
        now = self._now()
        user = User(
            id=new_id(),
            email=normalize_email(email),
            language=language,
            plan='free',
            created_at=now,
            updated_at=now,
        )
        with self._write() as connection:
            if _select_user(connection, 'email', user.email) is not None:
                raise EmailTaken('An account with that email address exists.')
            _insert_user(connection, user)
            _log_change(connection, 'user', user.id, user_path(user.id))
        return user

    def user_by_email(self, email: str) -> User | None:
        with _connection(self.path) as connection:
            return _select_user(connection, 'email', normalize_email(email))

    def user_by_id(self, user_id: str) -> User | None:
        if not is_id(user_id):
            return None
        with _connection(self.path) as connection:
            return _select_user(connection, 'id', user_id)

    def users(self) -> list[User]:
        """Every account, in id order."""
        with _connection(self.path) as connection:
            rows = connection.execute(
                f'SELECT {_USER_COLUMNS} FROM users ORDER BY id'
            ).fetchall()
        return [_user_from_row(row) for row in rows]

    def set_language(self, user_id: str, language: str) -> User:
        if not is_language(language):
            raise RecordError(f'Unknown language: {language!r}.')
        return self._update_user(user_id, language=language)

    def set_plan(self, user_id: str, plan: str) -> User:
        if not is_plan(plan):
            raise RecordError(f'Unknown plan: {plan!r}.')
        return self._update_user(user_id, plan=plan)

    def _update_user(
        self,
        user_id: str,
        *,
        language: Language | None = None,
        plan: Plan | None = None,
    ) -> User:
        with self._write() as connection:
            current = _select_user(connection, 'id', user_id)
            if current is None:
                raise UnknownUser('No account has that id.')
            changed = replace(
                current,
                language=current.language if language is None else language,
                plan=current.plan if plan is None else plan,
            )
            if changed == current:
                return current
            changed = replace(changed, updated_at=max(self._now(), current.updated_at))
            connection.execute(
                'UPDATE users SET language = ?, plan = ?, updated_at = ? WHERE id = ?',
                (changed.language, changed.plan, changed.updated_at, changed.id),
            )
            _log_change(connection, 'user', changed.id, user_path(changed.id))
        return changed

    def delete_user(self, user_id: str) -> None:
        with self._write() as connection:
            deleted = connection.execute(
                'DELETE FROM users WHERE id = ?', (user_id,)
            ).rowcount
            if deleted != 1:
                raise UnknownUser('No account has that id.')
            _log_change(connection, 'user', user_id, user_path(user_id))

    # ── Backup ──

    def backup_snapshot(self) -> BackupSnapshot:
        """Every record changed since the last backup, as it is now."""
        with self._read() as connection:
            after = _scalar(
                connection, 'SELECT backed_up_seq FROM backup_progress WHERE id = 1'
            )
            # Backed-up changes are pruned, so the log alone may be empty.
            through = max(
                after,
                _scalar(connection, 'SELECT COALESCE(MAX(seq), 0) FROM changes'),
            )
            rows = connection.execute(
                'SELECT kind, record_id, path FROM changes '
                'WHERE seq > ? AND seq <= ? ORDER BY seq',
                (after, through),
            ).fetchall()
            latest: dict[str, str] = {}
            for kind, record_id, path in rows:
                if kind != 'user' or not isinstance(record_id, str):
                    raise StoreError(
                        f'The change log holds an unknown record: {kind!r}.'
                    )
                if not isinstance(path, str) or path != user_path(record_id):
                    raise StoreError(
                        "The change log holds a path that is not the record's."
                    )
                latest[path] = record_id
            changes = tuple(
                RecordChange(path=path, user=_select_user(connection, 'id', record_id))
                for path, record_id in sorted(latest.items())
            )
            user_count = _scalar(connection, 'SELECT COUNT(*) FROM users')
        return BackupSnapshot(
            after_seq=after,
            through_seq=through,
            changes=changes,
            user_count=user_count,
        )

    def mark_backed_up(self, through_seq: int) -> None:
        """Records changes up to `through_seq` as safely in the backup."""
        with self._write() as connection:
            current = _scalar(
                connection, 'SELECT backed_up_seq FROM backup_progress WHERE id = 1'
            )
            if through_seq < current:
                raise StoreError(
                    f'The backup reached change {current}; it cannot go back to {through_seq}.'
                )
            connection.execute(
                'UPDATE backup_progress SET backed_up_seq = ? WHERE id = 1',
                (through_seq,),
            )
            connection.execute('DELETE FROM changes WHERE seq <= ?', (through_seq,))
