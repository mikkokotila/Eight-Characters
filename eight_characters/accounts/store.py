"""The account database: one SQLite file.

Every change to a record the backup keeps (so far, a user) is logged in the
`changes` table in the same transaction as the change itself, and the backup copies
exactly the records logged there. The database is never created by accident: opening
one that is missing fails, and a new or restored one is built aside and moved into
place only when complete.
"""

import hmac
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
            backed_up_seq INTEGER NOT NULL,
            head TEXT,
            pending_head TEXT,
            squash_of TEXT,
            CHECK (squash_of IS NULL OR pending_head IS NOT NULL)
        ) STRICT
        """,
        'INSERT INTO backup_progress (id, backed_up_seq) VALUES (1, 0)',
    ),
    # 2: sessions, sign-in codes and the requests for them. None is backed up: after a
    # restore, people sign in again.
    (
        """
        CREATE TABLE sessions (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        ) STRICT
        """,
        'CREATE INDEX sessions_by_user ON sessions (user_id)',
        """
        CREATE TABLE sign_in_codes (
            email TEXT PRIMARY KEY,
            code_hash TEXT NOT NULL,
            new_language TEXT CHECK (new_language IN ('fi', 'en')),
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            attempts INTEGER NOT NULL CHECK (attempts >= 0)
        ) STRICT
        """,
        """
        CREATE TABLE code_requests (
            id INTEGER PRIMARY KEY,
            email TEXT NOT NULL,
            client TEXT NOT NULL,
            requested_at TEXT NOT NULL
        ) STRICT
        """,
        'CREATE INDEX code_requests_by_email ON code_requests (email, requested_at)',
        'CREATE INDEX code_requests_by_client ON code_requests (client, requested_at)',
    ),
)
SCHEMA_VERSION: Final = len(MIGRATIONS)
# SQLite's own field for telling an application's files from others ('E8CH').
APPLICATION_ID: Final = 0x45384348
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
class Session:
    """A signed-in browser. Only a keyed hash of its token is kept."""

    token_hash: str
    user_id: str
    created_at: str
    expires_at: str


@dataclass(frozen=True)
class SignInCode:
    """The code last sent to an address. `new_language` is set when redeeming it
    creates the account, in that language."""

    email: str
    code_hash: str
    new_language: Language | None
    created_at: str
    expires_at: str
    attempts: int


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
    # The backup's last commit, or the one a restore read; None before the first.
    head: str | None
    # A commit made and about to become the checkout's: if the run stopped after
    # moving the checkout to it but before recording it, the next run finds it there.
    pending_head: str | None
    # While a squash of the history is under way, the commit it replaces; the squash
    # is then `pending_head`.
    squash_of: str | None


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


def _application_id(connection: sqlite3.Connection) -> int:
    row = connection.execute('PRAGMA application_id').fetchone()
    value = row[0]
    if not isinstance(value, int):
        raise StoreError('The database reports no application id.')
    return value


def _migrate(connection: sqlite3.Connection) -> None:
    """Runs the migrations the database lacks, each in its own transaction.

    The version is read under the write lock, so a second process opening the same
    database at the same moment finds each migration done instead of running it twice.
    """
    while True:
        connection.execute('BEGIN IMMEDIATE')
        try:
            version = _user_version(connection)
            if version > SCHEMA_VERSION:
                raise StoreError(
                    f'The database has schema {version}; this version of the app '
                    f'knows schemas up to {SCHEMA_VERSION}.'
                )
            current = version == SCHEMA_VERSION
            if not current:
                for statement in MIGRATIONS[version]:
                    connection.execute(statement)
                connection.execute(f'PRAGMA user_version = {version + 1}')
        except BaseException:
            connection.execute('ROLLBACK')
            raise
        connection.execute('COMMIT')
        if current:
            return


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


def _commit_or_none(value: object) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise StoreError('The backup progress holds a commit that is not text.')


def _scalar(connection: sqlite3.Connection, query: str, *params: object) -> int:
    row = connection.execute(query, params).fetchone()
    value = None if row is None else row[0]
    if not isinstance(value, int):
        raise StoreError(f'Expected a number from: {query}')
    return value


def _texts(row: tuple[Any, ...]) -> tuple[str, ...]:
    if not all(isinstance(value, str) for value in row):
        raise StoreError('A row holds a value that is not text.')
    return tuple(str(value) for value in row)


def _code_from_row(row: tuple[Any, ...]) -> SignInCode:
    address, code_hash, new_language, created_at, expires_at, attempts = row
    if new_language is not None and not (
        isinstance(new_language, str) and is_language(new_language)
    ):
        raise StoreError('A sign-in code holds an unknown language.')
    if not isinstance(attempts, int):
        raise StoreError('A sign-in code holds a count that is not a number.')
    texts = _texts((address, code_hash, created_at, expires_at))
    return SignInCode(
        email=texts[0],
        code_hash=texts[1],
        new_language=new_language,
        created_at=texts[2],
        expires_at=texts[3],
        attempts=attempts,
    )


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
            if version == 0 or _application_id(connection) != APPLICATION_ID:
                raise StoreError(f'{path} is not an account database.')
            if version > SCHEMA_VERSION:
                raise StoreError(
                    f'The database at {path} has schema {version}; this version of '
                    f'the app knows schemas up to {SCHEMA_VERSION}.'
                )
            _migrate(connection)
        return cls(path, clock=clock)

    @classmethod
    def create(
        cls, path: Path, *, clock: Callable[[], datetime] = _utc_now
    ) -> 'AccountStore':
        """A new, empty database at `path`, which must not exist."""
        return cls._build(path, (), None, clock)

    @classmethod
    def restore(
        cls,
        path: Path,
        users: Sequence[User],
        *,
        head: str,
        clock: Callable[[], datetime] = _utc_now,
    ) -> 'AccountStore':
        """A new database at `path` holding exactly these users, as backed up in the
        Git commit `head`.

        Nothing is logged for the backup: the records came from it.
        """
        return cls._build(path, users, head, clock)

    @classmethod
    def _build(
        cls,
        path: Path,
        users: Sequence[User],
        head: str | None,
        clock: Callable[[], datetime],
    ) -> 'AccountStore':
        if path.exists():
            raise StoreError(f'{path} exists already; refusing to build over it.')
        partial = path.with_name(f'{path.name}.partial')
        # Made here and nowhere else at the same time: a second build fails at once
        # instead of sharing, or later removing, this one's file.
        try:
            descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise StoreError(
                f'{partial} exists: another build is under way, or one was '
                'interrupted. Remove it if none is running.'
            ) from exc
        os.close(descriptor)
        try:
            with _connection(partial) as connection:
                connection.execute(f'PRAGMA application_id = {APPLICATION_ID}')
                _migrate(connection)
                connection.execute('BEGIN IMMEDIATE')
                try:
                    for user in users:
                        _insert_user(connection, user)
                    connection.execute(
                        'UPDATE backup_progress SET head = ? WHERE id = 1', (head,)
                    )
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
        """Deletes the account, its sessions and its address's sign-in code.

        The record of codes asked for stays until it is an hour old, as for any
        address: deleting the account must not reset the hourly limits, or deleting
        and creating it again would send emails without end."""
        with self._write() as connection:
            user = _select_user(connection, 'id', user_id)
            if user is None:
                raise UnknownUser('No account has that id.')
            # Sessions go with the user (ON DELETE CASCADE).
            connection.execute('DELETE FROM users WHERE id = ?', (user.id,))
            connection.execute(
                'DELETE FROM sign_in_codes WHERE email = ?', (user.email,)
            )
            _log_change(connection, 'user', user.id, user_path(user.id))

    # ── Sessions ──

    def create_session(self, session: Session) -> bool:
        """Keeps a session for its account, in the same statement that finds the
        account: False, and no session, if the account is gone."""
        with self._write() as connection:
            created = connection.execute(
                'INSERT INTO sessions (token_hash, user_id, created_at, expires_at) '
                'SELECT ?, id, ?, ? FROM users WHERE id = ?',
                (
                    session.token_hash,
                    session.created_at,
                    session.expires_at,
                    session.user_id,
                ),
            ).rowcount
        return created == 1

    def session(self, token_hash: str) -> Session | None:
        with _connection(self.path) as connection:
            row = connection.execute(
                'SELECT token_hash, user_id, created_at, expires_at FROM sessions '
                'WHERE token_hash = ?',
                (token_hash,),
            ).fetchone()
        if row is None:
            return None
        texts = _texts(row)
        return Session(
            token_hash=texts[0],
            user_id=texts[1],
            created_at=texts[2],
            expires_at=texts[3],
        )

    def session_and_user(self, token_hash: str) -> tuple[Session, User] | None:
        """A session and its account, read in one query, or None if either is gone:
        an account deleted meanwhile takes its sessions with it."""
        with _connection(self.path) as connection:
            row = connection.execute(
                'SELECT s.token_hash, s.user_id, s.created_at, s.expires_at, '
                'u.id, u.email, u.language, u.plan, u.created_at, u.updated_at '
                'FROM sessions AS s JOIN users AS u ON u.id = s.user_id '
                'WHERE s.token_hash = ?',
                (token_hash,),
            ).fetchone()
        if row is None:
            return None
        texts = _texts(row[:4])
        session = Session(
            token_hash=texts[0],
            user_id=texts[1],
            created_at=texts[2],
            expires_at=texts[3],
        )
        return session, _user_from_row(row[4:])

    def extend_session(self, token_hash: str, expires_at: str, now: str) -> bool:
        """Extends a session that is still live at `now`; False if it is gone or has
        ended meanwhile."""
        with self._write() as connection:
            extended = connection.execute(
                'UPDATE sessions SET expires_at = ? '
                'WHERE token_hash = ? AND expires_at > ?',
                (expires_at, token_hash, now),
            ).rowcount
        return extended == 1

    def end_expired_session(self, token_hash: str, now: str) -> None:
        """Deletes a session if it has ended by `now`: a request that renewed it
        meanwhile keeps it."""
        with self._write() as connection:
            connection.execute(
                'DELETE FROM sessions WHERE token_hash = ? AND expires_at <= ?',
                (token_hash, now),
            )

    def delete_session(self, token_hash: str) -> None:
        with self._write() as connection:
            connection.execute(
                'DELETE FROM sessions WHERE token_hash = ?', (token_hash,)
            )

    def delete_sessions(self, user_id: str) -> int:
        """Signs the account out everywhere; returns how many sessions ended."""
        with self._write() as connection:
            return connection.execute(
                'DELETE FROM sessions WHERE user_id = ?', (user_id,)
            ).rowcount

    def delete_expired(self, now: str, requests_before: str) -> None:
        """Drops sessions and codes past their time, and the record of codes asked
        for before `requests_before`, the start of the hourly limits' window."""
        with self._write() as connection:
            connection.execute('DELETE FROM sessions WHERE expires_at <= ?', (now,))
            connection.execute(
                'DELETE FROM sign_in_codes WHERE expires_at <= ?', (now,)
            )
            connection.execute(
                'DELETE FROM code_requests WHERE requested_at < ?', (requests_before,)
            )

    def account_data(self, user_id: str) -> dict[str, Any]:
        """Everything kept for an account, read at one moment: its record, its sessions
        and its address's sign-in code (without their hashes), and the record of codes
        asked for, with the client addresses they came from."""
        with self._read() as connection:
            user = _select_user(connection, 'id', user_id)
            if user is None:
                raise UnknownUser('No account has that id.')
            sessions = connection.execute(
                'SELECT created_at, expires_at FROM sessions WHERE user_id = ? '
                'ORDER BY created_at, expires_at',
                (user.id,),
            ).fetchall()
            code = connection.execute(
                'SELECT created_at, expires_at, attempts FROM sign_in_codes '
                'WHERE email = ?',
                (user.email,),
            ).fetchone()
            requests = connection.execute(
                'SELECT requested_at, client FROM code_requests WHERE email = ? '
                'ORDER BY requested_at, id',
                (user.email,),
            ).fetchall()
        sign_in_code: dict[str, Any] | None = None
        if code is not None:
            created_at, expires_at = _texts(code[:2])
            sign_in_code = {
                'attempts': code[2],
                'created_at': created_at,
                'expires_at': expires_at,
            }
        return {
            'account': {
                'created_at': user.created_at,
                'email': user.email,
                'id': user.id,
                'language': user.language,
                'plan': user.plan,
                'updated_at': user.updated_at,
            },
            'code_requests': [
                dict(zip(('requested_at', 'client'), _texts(row), strict=True))
                for row in requests
            ],
            'sessions': [
                dict(zip(('created_at', 'expires_at'), _texts(row), strict=True))
                for row in sessions
            ],
            'sign_in_code': sign_in_code,
        }

    # ── Sign-in codes ──

    def put_code(self, code: SignInCode) -> None:
        """Keeps this code for its address, replacing any earlier one."""
        with self._write() as connection:
            connection.execute(
                'INSERT OR REPLACE INTO sign_in_codes '
                '(email, code_hash, new_language, created_at, expires_at, attempts) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (
                    code.email,
                    code.code_hash,
                    code.new_language,
                    code.created_at,
                    code.expires_at,
                    code.attempts,
                ),
            )

    def code(self, email: str) -> SignInCode | None:
        with _connection(self.path) as connection:
            row = connection.execute(
                'SELECT email, code_hash, new_language, created_at, expires_at, '
                'attempts FROM sign_in_codes WHERE email = ?',
                (email,),
            ).fetchone()
        return None if row is None else _code_from_row(row)

    def take_code(
        self, email: str, code_hash: str, now: str, tries: int
    ) -> SignInCode | None:
        """The address's code if `code_hash` is its hash and it is still good, used
        up by being taken. A wrong try is counted, and the code is dropped at
        `tries` wrong ones. All in one write, so two tries never race."""
        with self._write() as connection:
            row = connection.execute(
                'SELECT email, code_hash, new_language, created_at, expires_at, '
                'attempts FROM sign_in_codes WHERE email = ?',
                (email,),
            ).fetchone()
            if row is None:
                return None
            code = _code_from_row(row)
            if code.expires_at <= now:
                connection.execute(
                    'DELETE FROM sign_in_codes WHERE email = ?', (email,)
                )
                return None
            if not hmac.compare_digest(code.code_hash, code_hash):
                if code.attempts + 1 >= tries:
                    connection.execute(
                        'DELETE FROM sign_in_codes WHERE email = ?', (email,)
                    )
                else:
                    connection.execute(
                        'UPDATE sign_in_codes SET attempts = attempts + 1 '
                        'WHERE email = ?',
                        (email,),
                    )
                return None
            connection.execute('DELETE FROM sign_in_codes WHERE email = ?', (email,))
        return code

    def delete_code(self, email: str) -> None:
        with self._write() as connection:
            connection.execute('DELETE FROM sign_in_codes WHERE email = ?', (email,))

    def allow_code_request(
        self,
        email: str,
        client: str,
        now: str,
        window_start: str,
        per_address: int,
        per_client: int,
    ) -> bool:
        """Records a request for a code unless the address or the client has made
        its limit of requests since `window_start`. Refused requests are not
        counted, so asking again cannot lengthen a wait."""
        with self._write() as connection:
            connection.execute(
                'DELETE FROM code_requests WHERE requested_at < ?', (window_start,)
            )
            by_address = _scalar(
                connection,
                'SELECT COUNT(*) FROM code_requests WHERE email = ?',
                email,
            )
            by_client = _scalar(
                connection,
                'SELECT COUNT(*) FROM code_requests WHERE client = ?',
                client,
            )
            if by_address >= per_address or by_client >= per_client:
                return False
            connection.execute(
                'INSERT INTO code_requests (email, client, requested_at) '
                'VALUES (?, ?, ?)',
                (email, client, now),
            )
        return True

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
            row = connection.execute(
                'SELECT head, pending_head, squash_of FROM backup_progress WHERE id = 1'
            ).fetchone()
        if row is None:
            raise StoreError('The database keeps no backup progress.')
        return BackupSnapshot(
            after_seq=after,
            through_seq=through,
            changes=changes,
            user_count=user_count,
            head=_commit_or_none(row[0]),
            pending_head=_commit_or_none(row[1]),
            squash_of=_commit_or_none(row[2]),
        )

    def record_pending_head(self, commit: str) -> None:
        """Remembers a commit the backup made and is about to move the checkout to."""
        with self._write() as connection:
            connection.execute(
                'UPDATE backup_progress SET pending_head = ?, squash_of = NULL '
                'WHERE id = 1',
                (commit,),
            )

    def record_pending_squash(self, commit: str, replaces: str) -> None:
        """Remembers a squash under way: its commit, and the one it replaces."""
        with self._write() as connection:
            connection.execute(
                'UPDATE backup_progress SET pending_head = ?, squash_of = ? '
                'WHERE id = 1',
                (commit, replaces),
            )

    def record_backup_head(self, commit: str | None) -> None:
        """Remembers the commit the backup made last, and that nothing is pending."""
        with self._write() as connection:
            connection.execute(
                'UPDATE backup_progress '
                'SET head = ?, pending_head = NULL, squash_of = NULL WHERE id = 1',
                (commit,),
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
