"""The account records the app keeps, and their form in the backup.

A record is written as canonical JSON: UTF-8, keys sorted, two-space indents and a
final newline. The same record therefore always gives the same bytes, and a file that
decodes to a record must be exactly those bytes.

An account's record holds the account and its settings for Today: its own chart, a
partner's, where the person is, and the schools chosen.
"""

import json
import math
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Literal, TypeGuard, cast

from eight_characters import first_chart
from eight_characters.school_presets import (
    DEFAULT_FAVOURABLE,
    DEFAULT_SEASON,
    DEFAULT_TRANSITS,
    FavourableSchool,
    SeasonSchool,
    TransitSchool,
    is_favourable_school,
    is_season_school,
    is_transit_school,
)
from eight_characters.time_convert import Gender, load_timezone

Language = Literal['fi', 'en']
Plan = Literal['free', 'basic', 'pro', 'max']
RecordKind = Literal['user']
# Whose chart: the account holder's own, or their partner's.
Role = Literal['self', 'partner']
ZiConvention = Literal['split_midnight', 'whole_zi_23']

LANGUAGES: Final[tuple[Language, ...]] = ('fi', 'en')
PLANS: Final[tuple[Plan, ...]] = ('free', 'basic', 'pro', 'max')
ROLES: Final[tuple[Role, ...]] = ('self', 'partner')
GENDERS: Final[tuple[Gender, ...]] = ('male', 'female')
# The engine's Zi-hour conventions (conventions.ALLOWED_ZI_CONVENTIONS).
ZI_CONVENTIONS: Final[tuple[ZiConvention, ...]] = ('split_midnight', 'whole_zi_23')
# The version of a record's own fields that this app writes. Schema 1 records, from
# before accounts kept settings, are read as accounts without any; a record of any
# other version is refused.
RECORD_SCHEMA: Final = 2
READABLE_SCHEMAS: Final = (1, 2)
EMAIL_MAX_LENGTH: Final = 254
NAME_MAX_LENGTH: Final = 80
PLACE_NAME_MAX_LENGTH: Final = 200

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
_FIELDS_BY_SCHEMA: Final = {1: _USER_FIELDS, 2: _USER_FIELDS | {'settings'}}
_SETTINGS_FIELDS: Final = frozenset({'charts', 'place', 'schools', 'updated_at'})
_CHARTS_FIELDS: Final = frozenset(ROLES)
_BIRTH_FIELDS: Final = frozenset(
    {'date', 'fold', 'gender', 'name', 'place', 'time', 'zi'}
)
_PLACE_FIELDS: Final = frozenset({'latitude', 'longitude', 'name', 'timezone'})
_SCHOOLS_FIELDS: Final = frozenset({'favourable', 'season', 'transits'})


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


def is_role(value: str) -> TypeGuard[Role]:
    return value in ROLES


def is_gender(value: str) -> TypeGuard[Gender]:
    return value in GENDERS


def is_zi(value: str) -> TypeGuard[ZiConvention]:
    return value in ZI_CONVENTIONS


def _check_text(name: str, value: object, longest: int) -> None:
    """Text a person typed or picked: trimmed, printable, and not too long."""
    if not isinstance(value, str):
        raise RecordError(f'{name} must be text.')
    if not value or value != value.strip():
        raise RecordError(f'{name} must not be empty or start or end with spaces.')
    if len(value) > longest or not value.isprintable():
        raise RecordError(
            f'{name} must be at most {longest} printable characters, on one line.'
        )


def _check_coordinate(name: str, value: object, limit: float) -> None:
    # Only a float: true is no number, and a whole number would not write back as the
    # same bytes.
    if type(value) is not float or not math.isfinite(value) or abs(value) > limit:
        raise RecordError(f'{name} must be a number from {-limit:g} to {limit:g}.')


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


@dataclass(frozen=True)
class Place:
    """A place as the place search gives it: its name, time zone and coordinates."""

    name: str
    timezone: str
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        _check_text('A place name', self.name, PLACE_NAME_MAX_LENGTH)
        _check_coordinate('latitude', self.latitude, 90.0)
        _check_coordinate('longitude', self.longitude, 180.0)
        try:
            load_timezone(self.timezone)
        except ValueError as exc:
            raise RecordError(str(exc)) from exc


@dataclass(frozen=True)
class Birth:
    """A chart an account keeps: when and where someone was born, and the gender that
    sets the direction of their luck pillars.

    Every instance is checked by the first chart's rules (a date within the engine's
    years, a time, a time zone the engine knows). Whether its clock time happened at
    its place is settled when it is saved, by charting it.
    """

    name: str | None
    date: str
    time: str
    place: Place
    # Which pass of a time the clocks repeat: 0 the first, 1 the second.
    fold: int | None
    gender: Gender
    # The Zi-hour convention the chart is drawn with, as its link carries it.
    zi: ZiConvention

    def __post_init__(self) -> None:
        if self.name is not None:
            _check_text('A name', self.name, NAME_MAX_LENGTH)
        if not is_zi(self.zi):
            raise RecordError(f'Unknown Zi-hour convention: {self.zi!r}.')
        if self.fold is not None and (
            type(self.fold) is not int or self.fold not in (0, 1)
        ):
            raise RecordError('fold must be 0, 1 or null.')
        if not is_gender(self.gender):
            raise RecordError(f'Unknown gender: {self.gender!r}.')
        try:
            self.first_birth()
        except first_chart.FirstChartInputError as exc:
            raise RecordError(str(exc)) from exc

    def first_birth(self) -> first_chart.FirstBirth:
        """The birth as the first chart takes it, with its time and place."""
        return first_chart.parse_first_birth(
            self.date,
            self.time,
            first_chart.Place(
                timezone=self.place.timezone,
                latitude=self.place.latitude,
                longitude=self.place.longitude,
                fold=self.fold,
            ),
        )


@dataclass(frozen=True)
class Schools:
    """The school Today follows for each of its three settings."""

    favourable: FavourableSchool
    season: SeasonSchool
    transits: TransitSchool

    def __post_init__(self) -> None:
        if not is_favourable_school(self.favourable):
            raise RecordError(f'Unknown favourable school: {self.favourable!r}.')
        if not is_season_school(self.season):
            raise RecordError(f'Unknown season school: {self.season!r}.')
        if not is_transit_school(self.transits):
            raise RecordError(f'Unknown transit school: {self.transits!r}.')


DEFAULT_SCHOOLS: Final = Schools(
    favourable=DEFAULT_FAVOURABLE, season=DEFAULT_SEASON, transits=DEFAULT_TRANSITS
)


@dataclass(frozen=True)
class ChosenSchools:
    """The schools an account chose; None where it follows the default, and so
    follows a later change of the default too."""

    favourable: FavourableSchool | None
    season: SeasonSchool | None
    transits: TransitSchool | None

    def __post_init__(self) -> None:
        Schools(
            favourable=self.favourable or DEFAULT_FAVOURABLE,
            season=self.season or DEFAULT_SEASON,
            transits=self.transits or DEFAULT_TRANSITS,
        )

    def effective(self) -> Schools:
        """The schools Today follows: each chosen one, or the default."""
        return Schools(
            favourable=self.favourable or DEFAULT_SCHOOLS.favourable,
            season=self.season or DEFAULT_SCHOOLS.season,
            transits=self.transits or DEFAULT_SCHOOLS.transits,
        )


NO_CHOICE: Final = ChosenSchools(favourable=None, season=None, transits=None)


@dataclass(frozen=True)
class Settings:
    """What an account keeps for Today: its own chart, a partner's, where the person
    is, and the schools chosen. An account that has set nothing has none."""

    own: Birth | None
    partner: Birth | None
    place: Place | None
    schools: ChosenSchools
    updated_at: str

    def __post_init__(self) -> None:
        _check_timestamp('updated_at', self.updated_at)

    def chart(self, role: Role) -> Birth | None:
        return self.own if role == 'self' else self.partner


def canonical_json(value: dict[str, Any]) -> bytes:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    return f'{text}\n'.encode()


def place_value(place: Place) -> dict[str, Any]:
    return {
        'latitude': place.latitude,
        'longitude': place.longitude,
        'name': place.name,
        'timezone': place.timezone,
    }


def _birth_value(birth: Birth) -> dict[str, Any]:
    return {
        'date': birth.date,
        'fold': birth.fold,
        'gender': birth.gender,
        'name': birth.name,
        'place': place_value(birth.place),
        'time': birth.time,
        'zi': birth.zi,
    }


def settings_value(settings: Settings) -> dict[str, Any]:
    """The settings as their records write them, and as the API and the export show
    them."""
    return {
        'charts': {
            role: None if birth is None else _birth_value(birth)
            for role, birth in (('partner', settings.partner), ('self', settings.own))
        },
        'place': None if settings.place is None else place_value(settings.place),
        'schools': {
            'favourable': settings.schools.favourable,
            'season': settings.schools.season,
            'transits': settings.schools.transits,
        },
        'updated_at': settings.updated_at,
    }


def encode_settings(settings: Settings) -> bytes:
    return canonical_json(settings_value(settings))


def _fields(value: object, what: str, fields: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RecordError(f'{what} must be a JSON object.')
    record = cast(dict[str, Any], value)
    if frozenset(record) != fields:
        raise RecordError(f'{what} has the wrong fields: {sorted(record)}.')
    return record


def _text(record: dict[str, Any], name: str, what: str) -> str:
    value: object = record[name]
    if not isinstance(value, str):
        raise RecordError(f"{what}'s {name} must be text.")
    return value


def _optional_text(record: dict[str, Any], name: str, what: str) -> str | None:
    value: object = record[name]
    if value is not None and not isinstance(value, str):
        raise RecordError(f"{what}' {name} must be text or null.")
    return value


def _float(record: dict[str, Any], name: str, what: str) -> float:
    value: object = record[name]
    # Only a float: true is no number, and a whole number would not write back as the
    # same bytes.
    if type(value) is not float:
        raise RecordError(f"{what}'s {name} must be a number with a decimal point.")
    return value


def _place_from(value: object, what: str) -> Place:
    record = _fields(value, what, _PLACE_FIELDS)
    return Place(
        name=_text(record, 'name', what),
        timezone=_text(record, 'timezone', what),
        latitude=_float(record, 'latitude', what),
        longitude=_float(record, 'longitude', what),
    )


def _birth_from(value: object, what: str) -> Birth:
    record = _fields(value, what, _BIRTH_FIELDS)
    name: object = record['name']
    if name is not None and not isinstance(name, str):
        raise RecordError(f"{what}'s name must be text or null.")
    fold: object = record['fold']
    if fold is not None and (type(fold) is not int or fold not in (0, 1)):
        raise RecordError(f"{what}'s fold must be 0, 1 or null.")
    gender = _text(record, 'gender', what)
    if not is_gender(gender):
        raise RecordError(f'Unknown gender: {gender!r}.')
    zi = _text(record, 'zi', what)
    if not is_zi(zi):
        raise RecordError(f'Unknown Zi-hour convention: {zi!r}.')
    return Birth(
        name=name,
        date=_text(record, 'date', what),
        time=_text(record, 'time', what),
        place=_place_from(record['place'], f"{what}'s place"),
        fold=cast(int | None, fold),
        gender=gender,
        zi=zi,
    )


def settings_from(value: object) -> Settings:
    """The settings a record's JSON value holds, every part checked."""
    record = _fields(value, 'The settings', _SETTINGS_FIELDS)
    charts = _fields(record['charts'], 'The charts', _CHARTS_FIELDS)
    schools = _fields(record['schools'], 'The schools', _SCHOOLS_FIELDS)
    favourable = _optional_text(schools, 'favourable', 'The schools')
    season = _optional_text(schools, 'season', 'The schools')
    transits = _optional_text(schools, 'transits', 'The schools')
    if favourable is not None and not is_favourable_school(favourable):
        raise RecordError(f'Unknown favourable school: {favourable!r}.')
    if season is not None and not is_season_school(season):
        raise RecordError(f'Unknown season school: {season!r}.')
    if transits is not None and not is_transit_school(transits):
        raise RecordError(f'Unknown transit school: {transits!r}.')
    own: object = charts['self']
    partner: object = charts['partner']
    place: object = record['place']
    return Settings(
        own=None if own is None else _birth_from(own, 'Your chart'),
        partner=None if partner is None else _birth_from(partner, "A partner's chart"),
        place=None if place is None else _place_from(place, 'Where you are'),
        schools=ChosenSchools(favourable=favourable, season=season, transits=transits),
        updated_at=_text(record, 'updated_at', 'The settings'),
    )


def decode_settings(data: bytes) -> Settings:
    """Settings as the database keeps them, refusing anything but canonical bytes."""
    try:
        value: object = json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecordError('The settings are not UTF-8 JSON.') from exc
    settings = settings_from(value)
    if encode_settings(settings) != data:
        raise RecordError('The settings are not in canonical form.')
    return settings


def _user_value(user: User, schema: int, settings: Settings | None) -> dict[str, Any]:
    value: dict[str, Any] = {
        'created_at': user.created_at,
        'email': user.email,
        'id': user.id,
        'kind': 'user',
        'language': user.language,
        'plan': user.plan,
        'schema': schema,
        'updated_at': user.updated_at,
    }
    if schema >= 2:
        value['settings'] = None if settings is None else settings_value(settings)
    elif settings is not None:
        raise RecordError('A schema 1 record holds no settings.')
    return value


def encode_user(user: User, settings: Settings | None) -> bytes:
    """The account's record: the account and its settings, None if it has none."""
    return canonical_json(_user_value(user, RECORD_SCHEMA, settings))


def decode_user(data: bytes) -> tuple[User, Settings | None]:
    """The account a record file holds, and its settings, refusing anything but the
    exact canonical bytes. A schema 1 record holds an account without settings."""
    try:
        value: object = json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecordError('A user record is not UTF-8 JSON.') from exc
    if not isinstance(value, dict):
        raise RecordError('A user record must be a JSON object.')
    record = cast(dict[str, Any], value)
    schema: object = record.get('schema')
    if type(schema) is not int or schema not in READABLE_SCHEMAS:
        raise RecordError(
            f'A user record of schema {schema!r} is not one this app reads.'
        )
    if frozenset(record) != _FIELDS_BY_SCHEMA[schema]:
        raise RecordError(f'A user record has the wrong fields: {sorted(record)}.')
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
    held: object = record.get('settings')
    settings = None if held is None else settings_from(held)
    if canonical_json(_user_value(user, schema, settings)) != data:
        raise RecordError('A user record is not in canonical form.')
    return user, settings


def user_path(user_id: str) -> str:
    """Where a user's record lives in the backup, relative to its root, unencrypted.

    Records spread over folders named by their id's first two characters, so no
    folder comes near GitHub's recommended limit of 3,000 entries.
    """
    if not is_id(user_id):
        raise RecordError('A user id must be 32 lowercase hex digits.')
    return f'users/{user_id[:2]}/{user_id}/user.json'
