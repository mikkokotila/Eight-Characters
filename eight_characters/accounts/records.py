"""The account records the app keeps, and their form in the backup.

A record is written as canonical JSON: UTF-8, keys sorted, two-space indents and a
final newline. The same record therefore always gives the same bytes, and a file that
decodes to a record must be exactly those bytes.
"""

import json
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Literal, TypeGuard, cast

Language = Literal['fi', 'en']
Plan = Literal['free', 'basic', 'pro', 'max']
RecordKind = Literal['user']

LANGUAGES: Final[tuple[Language, ...]] = ('fi', 'en')
PLANS: Final[tuple[Plan, ...]] = ('free', 'basic', 'pro', 'max')
# The version of a record's own fields. A record of any other version is refused.
RECORD_SCHEMA: Final = 1
EMAIL_MAX_LENGTH: Final = 254

_ID = re.compile(r'[0-9a-f]{32}')
_TIMESTAMP_FORMAT: Final = '%Y-%m-%dT%H:%M:%SZ'
_TIMESTAMP = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z')
# Deliberately loose: one @, something on each side, a dot in the domain. Whether an
# address works is settled by the code sent to it.
_EMAIL = re.compile(r'[^@\s]+@[^@\s]+\.[^@\s]+')
_USER_FIELDS: Final = frozenset(
    {
        'created_at',
        'email',
        'id',
        'kind',
        'language',
        'plan',
        'schema',
        'updated_at',
    }
)


class RecordError(ValueError):
    """A record, or a file that should hold one, is not valid."""


def new_id() -> str:
    """A new record id: 128 random bits as 32 lowercase hex digits."""
    return secrets.token_hex(16)


def is_id(value: str) -> bool:
    return _ID.fullmatch(value) is not None


def timestamp(moment: datetime) -> str:
    """An aware moment as the records write it: UTC, to the second."""
    if moment.tzinfo is None:
        raise RecordError('A timestamp needs a time zone.')
    return moment.astimezone(UTC).strftime(_TIMESTAMP_FORMAT)


def parse_timestamp(value: str) -> datetime:
    """A moment the records wrote, back as an aware UTC datetime."""
    _check_timestamp('A timestamp', value)
    return datetime.strptime(value, _TIMESTAMP_FORMAT).replace(tzinfo=UTC)


def normalize_email(raw: str) -> str:
    """The address as accounts are keyed by it: trimmed and lowercased.

    Raises RecordError for anything that cannot be an address. The message never
    repeats the address, so it can be logged.
    """
    email = raw.strip().lower()
    if (
        len(email) > EMAIL_MAX_LENGTH
        or not email.isprintable()
        or _EMAIL.fullmatch(email) is None
    ):
        raise RecordError('That is not an email address.')
    return email


def is_language(value: str) -> TypeGuard[Language]:
    return value in LANGUAGES


def is_plan(value: str) -> TypeGuard[Plan]:
    return value in PLANS


def _check_timestamp(name: str, value: str) -> None:
    if _TIMESTAMP.fullmatch(value) is None:
        raise RecordError(f'{name} must be a UTC time like 2026-10-07T12:00:00Z.')
    try:
        datetime.strptime(value, _TIMESTAMP_FORMAT)
    except ValueError as exc:
        raise RecordError(f'{name} is not a real moment.') from exc


@dataclass(frozen=True)
class User:
    """An account. Every instance is valid: the fields are checked on creation."""

    id: str
    email: str
    language: Language
    plan: Plan
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        if not is_id(self.id):
            raise RecordError('A user id must be 32 lowercase hex digits.')
        if normalize_email(self.email) != self.email:
            raise RecordError('A user email must be trimmed and lowercase.')
        if not is_language(self.language):
            raise RecordError(f'Unknown language: {self.language!r}.')
        if not is_plan(self.plan):
            raise RecordError(f'Unknown plan: {self.plan!r}.')
        _check_timestamp('created_at', self.created_at)
        _check_timestamp('updated_at', self.updated_at)
        # The fixed format orders as text the way the moments do.
        if self.updated_at < self.created_at:
            raise RecordError('A user cannot change before it was made.')


def canonical_json(value: dict[str, Any]) -> bytes:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    return f'{text}\n'.encode()


def encode_user(user: User) -> bytes:
    return canonical_json(
        {
            'created_at': user.created_at,
            'email': user.email,
            'id': user.id,
            'kind': 'user',
            'language': user.language,
            'plan': user.plan,
            'schema': RECORD_SCHEMA,
            'updated_at': user.updated_at,
        }
    )


def decode_user(data: bytes) -> User:
    """The user a record file holds, refusing anything but the exact canonical bytes."""
    try:
        value: object = json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecordError('A user record is not UTF-8 JSON.') from exc
    if not isinstance(value, dict):
        raise RecordError('A user record must be a JSON object.')
    record = cast(dict[str, Any], value)
    if frozenset(record) != _USER_FIELDS:
        raise RecordError(f'A user record has the wrong fields: {sorted(record)}.')
    schema: object = record['schema']
    if type(schema) is not int or schema != RECORD_SCHEMA:
        raise RecordError(
            f'A user record of schema {schema!r} is not one this app reads.'
        )
    if record['kind'] != 'user':
        raise RecordError('The record is not a user.')
    texts: dict[str, str] = {}
    for name in ('id', 'email', 'language', 'plan', 'created_at', 'updated_at'):
        field: object = record[name]
        if not isinstance(field, str):
            raise RecordError(f"A user record's {name} must be text.")
        texts[name] = field
    language = texts['language']
    plan = texts['plan']
    if not is_language(language):
        raise RecordError(f'Unknown language: {language!r}.')
    if not is_plan(plan):
        raise RecordError(f'Unknown plan: {plan!r}.')
    user = User(
        id=texts['id'],
        email=texts['email'],
        language=language,
        plan=plan,
        created_at=texts['created_at'],
        updated_at=texts['updated_at'],
    )
    if encode_user(user) != data:
        raise RecordError('A user record is not in canonical form.')
    return user


def user_path(user_id: str) -> str:
    """Where a user's record lives in the backup, relative to its root, unencrypted.

    Records spread over folders named by their id's first two characters, so no
    folder comes near GitHub's recommended limit of 3,000 entries.
    """
    if not is_id(user_id):
        raise RecordError('A user id must be 32 lowercase hex digits.')
    return f'users/{user_id[:2]}/{user_id}/user.json'
