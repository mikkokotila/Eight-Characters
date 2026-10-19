"""The account records the app keeps, and their form in the backup.

A record is written as canonical JSON: UTF-8, keys sorted, two-space indents and a
final newline. The same record therefore always gives the same bytes, and a file that
decodes to a record must be exactly those bytes.

An account's record holds the account and its settings: the charts it keeps, which of
them is the person's own, the couples they form, where the person is, and the schools
chosen for Today.
"""

import hashlib
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
ZiConvention = Literal['split_midnight', 'whole_zi_23']

LANGUAGES: Final[tuple[Language, ...]] = ('fi', 'en')
PLANS: Final[tuple[Plan, ...]] = ('free', 'basic', 'pro', 'max')
GENDERS: Final[tuple[Gender, ...]] = ('male', 'female')
# The engine's Zi-hour conventions (conventions.ALLOWED_ZI_CONVENTIONS).
ZI_CONVENTIONS: Final[tuple[ZiConvention, ...]] = ('split_midnight', 'whole_zi_23')
# The version of a record's own fields that this app writes. Schema 1 records, from
# before accounts kept settings, are read as accounts without any. Schema 2 records,
# from before accounts kept charts, have their partner's chart read as a saved chart
# that pairs with the person's own once one is marked. A record of any other version is
# refused.
RECORD_SCHEMA: Final = 3
READABLE_SCHEMAS: Final = (1, 2, 3)
# The default write allowance. Records remain readable above it: a smaller allowance
# must never make a retained library unreadable, unexportable or unrestorable.
CHART_LIMIT: Final = 50
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
_FIELDS_BY_SCHEMA: Final = {
    1: _USER_FIELDS,
    2: _USER_FIELDS | {'settings'},
    3: _USER_FIELDS | {'settings'},
}
# Settings as schema 2 records kept them, with one partner's chart.
_PARTNER_SETTINGS_FIELDS: Final = frozenset(
    {'partner', 'place', 'schools', 'updated_at'}
)
_SETTINGS_FIELDS: Final = frozenset(
    {
        'charts',
        'couples',
        'my_chart',
        'pending_partner',
        'place',
        'schools',
        'updated_at',
    }
)
_CHART_FIELDS: Final = frozenset({'birth', 'id'})
_COUPLE_FIELDS: Final = frozenset({'charts', 'id'})
_BIRTH_FIELDS: Final = frozenset(
    {'date', 'fold', 'gender', 'name', 'place', 'time', 'zi'}
)
_PLACE_FIELDS: Final = frozenset({'city', 'latitude', 'longitude', 'name', 'timezone'})
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


def check_name(name: str | None) -> None:
    """A chart's name: one line of printable text, at most NAME_MAX_LENGTH
    characters, or none."""
    if name is not None:
        _check_text('A name', name, NAME_MAX_LENGTH)


@dataclass(frozen=True)
class Place:
    """A place as the place search gives it: its full name, its city (as a chart's
    link names it), its time zone and its coordinates."""

    name: str
    city: str
    timezone: str
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        _check_text('A place name', self.name, PLACE_NAME_MAX_LENGTH)
        _check_text('A city', self.city, PLACE_NAME_MAX_LENGTH)
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
        check_name(self.name)
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

    def chart_key(self) -> tuple[object, ...]:
        """What the chart is drawn from: the day, the clock time to the second, its
        pass, the place on the globe and its zone, the gender and the Zi-hour
        convention. Two births with the same key are one chart, whatever their names
        or place labels."""
        clock = self.time if len(self.time) == len('00:00:00') else f'{self.time}:00'
        return (
            self.date,
            clock,
            self.fold,
            self.place.timezone,
            self.place.latitude,
            self.place.longitude,
            self.gender,
            self.zi,
        )

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
        # Only None follows the default: anything else must be a school.
        if self.favourable is not None and not is_favourable_school(self.favourable):
            raise RecordError(f'Unknown favourable school: {self.favourable!r}.')
        if self.season is not None and not is_season_school(self.season):
            raise RecordError(f'Unknown season school: {self.season!r}.')
        if self.transits is not None and not is_transit_school(self.transits):
            raise RecordError(f'Unknown transit school: {self.transits!r}.')

    def effective(self) -> Schools:
        """The schools Today follows: each chosen one, or the default."""
        return Schools(
            favourable=DEFAULT_FAVOURABLE
            if self.favourable is None
            else self.favourable,
            season=DEFAULT_SEASON if self.season is None else self.season,
            transits=DEFAULT_TRANSITS if self.transits is None else self.transits,
        )


NO_CHOICE: Final = ChosenSchools(favourable=None, season=None, transits=None)


@dataclass(frozen=True)
class SavedChart:
    """A chart the account keeps: a birth, under the id the library knows it by."""

    id: str
    birth: Birth

    def __post_init__(self) -> None:
        if not is_id(self.id):
            raise RecordError('A chart id must be 32 lowercase hex digits.')


@dataclass(frozen=True)
class Couple:
    """Two saved charts read together: Today reads each from the other's side."""

    id: str
    charts: tuple[str, str]

    def __post_init__(self) -> None:
        if not is_id(self.id):
            raise RecordError('A couple id must be 32 lowercase hex digits.')
        if (
            len(self.charts) != 2
            or not all(is_id(chart) for chart in self.charts)
            or self.charts[0] == self.charts[1]
        ):
            raise RecordError('A couple is two different saved charts.')


@dataclass(frozen=True)
class Settings:
    """What an account keeps: its saved charts, which of them is the person's own, the
    couples they form, where the person is, and the schools chosen for Today. An
    account that has set nothing has none."""

    charts: tuple[SavedChart, ...]
    # The person's own chart, one of `charts`; None until one is marked.
    my_chart: str | None
    couples: tuple[Couple, ...]
    # The chart that was the account's partner before accounts kept charts: it forms a
    # couple with the person's own chart when one is first marked.
    pending_partner: str | None
    place: Place | None
    schools: ChosenSchools
    updated_at: str

    def __post_init__(self) -> None:
        _check_timestamp('updated_at', self.updated_at)
        ids = [chart.id for chart in self.charts]
        if len(set(ids)) != len(ids):
            raise RecordError('Two saved charts share an id.')
        keys = [chart.birth.chart_key() for chart in self.charts]
        if len(set(keys)) != len(keys):
            raise RecordError('The same birth is saved twice.')
        if self.my_chart is not None and self.my_chart not in ids:
            raise RecordError('My chart is not one of the saved charts.')
        couples = [couple.id for couple in self.couples]
        if len(set(couples)) != len(couples):
            raise RecordError('Two couples share an id.')
        pairs = [frozenset(couple.charts) for couple in self.couples]
        if len(set(pairs)) != len(pairs):
            raise RecordError('The same two charts form two couples.')
        if any(not set(couple.charts) <= set(ids) for couple in self.couples):
            raise RecordError('A couple names a chart the account does not keep.')
        # A chart is in any number of couples here: how many a chart may join is a
        # rule for asking for a couple, never for reading a record (#96).
        if self.pending_partner is not None and (
            self.pending_partner not in ids or self.my_chart is not None
        ):
            raise RecordError(
                'A partner waits for a couple only as a saved chart, and only while '
                "no chart is marked as the person's own."
            )

    def chart(self, chart_id: str) -> SavedChart | None:
        return next((chart for chart in self.charts if chart.id == chart_id), None)

    def chart_of(self, birth: Birth) -> SavedChart | None:
        """The saved chart drawn from the same birth, if there is one."""
        key = birth.chart_key()
        return next(
            (chart for chart in self.charts if chart.birth.chart_key() == key), None
        )

    def couples_of(self, chart_id: str) -> tuple[Couple, ...]:
        """The couples a saved chart is in, in the order they were formed."""
        return tuple(couple for couple in self.couples if chart_id in couple.charts)

    def couple_between(self, first: str, second: str) -> Couple | None:
        """The couple two saved charts form, in either order, if they form one."""
        pair = {first, second}
        return next(
            (couple for couple in self.couples if set(couple.charts) == pair), None
        )


def no_settings(now: str) -> Settings:
    """The settings of an account that has set nothing."""
    return Settings(
        charts=(),
        my_chart=None,
        couples=(),
        pending_partner=None,
        place=None,
        schools=NO_CHOICE,
        updated_at=now,
    )


def canonical_json(value: dict[str, Any]) -> bytes:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    return f'{text}\n'.encode()


def place_value(place: Place) -> dict[str, Any]:
    return {
        'city': place.city,
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
    """The settings as their records write them, and as the export shows them."""
    return {
        'charts': [
            {'birth': _birth_value(chart.birth), 'id': chart.id}
            for chart in settings.charts
        ],
        'couples': [
            {'charts': list(couple.charts), 'id': couple.id}
            for couple in settings.couples
        ],
        'my_chart': settings.my_chart,
        'pending_partner': settings.pending_partner,
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
        city=_text(record, 'city', what),
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


def _chosen_from(value: object) -> ChosenSchools:
    schools = _fields(value, 'The schools', _SCHOOLS_FIELDS)
    favourable = _optional_text(schools, 'favourable', 'The schools')
    season = _optional_text(schools, 'season', 'The schools')
    transits = _optional_text(schools, 'transits', 'The schools')
    if favourable is not None and not is_favourable_school(favourable):
        raise RecordError(f'Unknown favourable school: {favourable!r}.')
    if season is not None and not is_season_school(season):
        raise RecordError(f'Unknown season school: {season!r}.')
    if transits is not None and not is_transit_school(transits):
        raise RecordError(f'Unknown transit school: {transits!r}.')
    return ChosenSchools(favourable=favourable, season=season, transits=transits)


def _list(record: dict[str, Any], name: str, what: str) -> list[object]:
    value: object = record[name]
    if not isinstance(value, list):
        raise RecordError(f"{what}'s {name} must be a list.")
    return cast(list[object], value)


def _id(value: object, what: str) -> str:
    if not isinstance(value, str) or not is_id(value):
        raise RecordError(f'{what} must be 32 lowercase hex digits.')
    return value


def partner_chart_id(partner: object) -> str:
    """The id a schema 2 partner's chart is kept under: the same for the same chart
    every time it is read, so the library names it the same until it is written."""
    return hashlib.sha256(
        b'partner\n' + canonical_json(cast(dict[str, Any], partner))
    ).hexdigest()[:32]


def _partner_settings_from(value: object) -> Settings | None:
    """Settings as accounts kept them before they kept charts, with their partner's
    chart read as a saved chart waiting to pair with the person's own; None for any
    other shape."""
    if not _kept_with_a_partner(value):
        return None
    record = cast(dict[str, Any], value)
    partner: object = record['partner']
    held: object = record['place']
    charts: tuple[SavedChart, ...] = ()
    if partner is not None:
        charts = (
            SavedChart(
                id=partner_chart_id(partner),
                birth=_birth_from(partner, "A partner's chart"),
            ),
        )
    return Settings(
        charts=charts,
        my_chart=None,
        couples=(),
        pending_partner=charts[0].id if charts else None,
        place=None if held is None else _place_from(held, 'Where you are'),
        schools=_chosen_from(record['schools']),
        updated_at=_text(record, 'updated_at', 'The settings'),
    )


def settings_from(value: object) -> Settings:
    """The settings a record's JSON value holds, every part checked. Settings kept
    before accounts kept charts read their partner's chart as a saved chart, waiting to
    pair with the person's own."""
    kept = _partner_settings_from(value)
    if kept is not None:
        return kept
    record = _fields(value, 'The settings', _SETTINGS_FIELDS)
    charts = tuple(
        SavedChart(
            id=_id(item['id'], 'A chart id'),
            birth=_birth_from(item['birth'], 'A saved chart'),
        )
        for item in (
            _fields(entry, 'A saved chart', _CHART_FIELDS)
            for entry in _list(record, 'charts', 'The settings')
        )
    )
    couples: list[Couple] = []
    for entry in _list(record, 'couples', 'The settings'):
        item = _fields(entry, 'A couple', _COUPLE_FIELDS)
        members = _list(item, 'charts', 'A couple')
        if len(members) != 2:
            raise RecordError('A couple is two saved charts.')
        couples.append(
            Couple(
                id=_id(item['id'], 'A couple id'),
                charts=(
                    _id(members[0], 'A couple chart'),
                    _id(members[1], 'A couple chart'),
                ),
            )
        )
    mine: object = record['my_chart']
    pending: object = record['pending_partner']
    held = record['place']
    return Settings(
        charts=charts,
        my_chart=None if mine is None else _id(mine, 'My chart'),
        couples=tuple(couples),
        pending_partner=None
        if pending is None
        else _id(pending, 'The pending partner'),
        place=None if held is None else _place_from(held, 'Where you are'),
        schools=_chosen_from(record['schools']),
        updated_at=_text(record, 'updated_at', 'The settings'),
    )


def _kept_with_a_partner(value: object) -> bool:
    """The shape settings had before accounts kept charts."""
    return (
        isinstance(value, dict)
        and frozenset(cast(dict[str, Any], value)) == _PARTNER_SETTINGS_FIELDS
    )


def decode_settings(data: bytes) -> Settings:
    """Settings as the database keeps them, refusing anything but canonical bytes:
    those this app writes, or those it wrote before accounts kept charts."""
    try:
        value: object = json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecordError('The settings are not UTF-8 JSON.') from exc
    settings = settings_from(value)
    written = (
        canonical_json(cast(dict[str, Any], value))
        if _kept_with_a_partner(value)
        else encode_settings(settings)
    )
    if written != data:
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
    if held is not None and _kept_with_a_partner(held) != (schema == 2):
        raise RecordError(f'A schema {schema} record holds settings of another schema.')
    settings = None if held is None else settings_from(held)
    # A schema 2 record is checked as the bytes it was written as; its settings are
    # read into today's form.
    written = (
        canonical_json(record)
        if schema == 2
        else canonical_json(_user_value(user, schema, settings))
    )
    if written != data:
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
