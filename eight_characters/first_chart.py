"""The first chart: what a birth settles, for someone without an account.

A date alone, a date and a place, or a date, a place and a time. Each settles more:

- **A date alone** settles the year and month pillars wherever on Earth the birth was,
  unless the year or month changes at some moment of that date in some time zone
  (UTC−12 to UTC+14). Those are left out, and listed in `changes` with the instant
  in UTC at which they change.
- **A date and a place** give the year, month and day pillars at noon on that date,
  local time. Each that changes during that local day is listed in `changes`, with
  the clock time at which it changes and the pillar on either side, so that a front
  end can say for whom the pillar holds rather than show one that may be wrong. With
  the engine's default conventions the day pillar changes at true solar midnight,
  which on most dates falls on the clock day; the month changes at a jie, and the
  year at Lichun.
- **A date, a place and a time** give all four pillars at that moment, and the
  engine's flags.

With a place, the chart has a Day Master: the day pillar's stem, and the canon's
passage for it, word for word. Every pillar is computed by the engine; nothing here
works one out.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Any, Final, Literal, NotRequired

from typing_extensions import TypedDict

from eight_characters.canon import load_canon
from eight_characters.data import BRANCHES, PILLAR_LABELS, STEMS
from eight_characters.engine import compute_engine_payload
from eight_characters.policy import MAX_SUPPORTED_YEAR, MIN_SUPPORTED_YEAR
from eight_characters.solar_position import julian_date_from_datetime_utc
from eight_characters.time_convert import (
    AmbiguousTimeError,
    BirthInput,
    NonexistentTimeError,
    convert_utc_to_tt,
    load_timezone,
    utc_from_jd_tt,
)

PillarName = Literal['year', 'month', 'day', 'hour']
PILLAR_NAMES: Final[tuple[PillarName, ...]] = ('year', 'month', 'day', 'hour')
# What a date alone can settle, and what a date and a place settle without a time.
DATE_PILLARS: Final[tuple[PillarName, ...]] = ('year', 'month')
DAY_PILLARS: Final[tuple[PillarName, ...]] = ('year', 'month', 'day')
# The widest offsets a civil clock has kept from UTC: a date runs from its midnight at
# UTC+14 to its next midnight at UTC−12.
EARLIEST_OFFSET: Final = timezone(timedelta(hours=14))
LATEST_OFFSET: Final = timezone(timedelta(hours=-12))
NOON: Final = time(12)
SECONDS_PER_DAY: Final = 86400.0

_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')
_TIME = re.compile(r'(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?')


class FirstChartInputError(ValueError):
    """The birth cannot be charted as given; the message says why and can be shown."""


@dataclass(frozen=True)
class Place:
    timezone: str
    latitude: float
    longitude: float
    fold: int | None = None


@dataclass(frozen=True)
class FirstBirth:
    day: date
    clock: time | None
    place: Place | None


class Stem(TypedDict):
    chinese: str
    pinyin: str
    element: str
    polarity: str


class Branch(TypedDict):
    chinese: str
    pinyin: str
    sign: str
    element: str
    polarity: str


class ChartPillar(TypedDict):
    name: str
    stem: Stem
    branch: Branch


class PillarChange(TypedDict):
    pillar: PillarName
    # The clock time on that date, to the second (rounded down), with a place;
    # the instant in UTC without one.
    at: NotRequired[str]
    at_utc: NotRequired[str]
    before: ChartPillar
    after: ChartPillar


class DayMaster(TypedDict):
    stem: str
    pinyin: str
    polarity: str
    element: str
    title: str
    passage: list[str]


class FirstChart(TypedDict):
    pillars: dict[PillarName, ChartPillar]
    changes: list[PillarChange]
    day_master: NotRequired[DayMaster]
    flags: NotRequired[dict[str, Any]]
    engine: dict[str, Any]


def parse_first_birth(
    date_text: str, time_text: str | None, place: Place | None
) -> FirstBirth:
    """The birth, checked: a date that exists within the engine's years, a time in
    HH:MM or HH:MM:SS, a zone the engine knows, and a time only with a place."""
    if _DATE.fullmatch(date_text) is None:
        raise FirstChartInputError('date must be in YYYY-MM-DD format.')
    try:
        day = date.fromisoformat(date_text)
    except ValueError as exc:
        raise FirstChartInputError(f'{date_text} is not a date that exists.') from exc
    if not MIN_SUPPORTED_YEAR <= day.year <= MAX_SUPPORTED_YEAR:
        raise FirstChartInputError(
            f'Date out of supported range ({MIN_SUPPORTED_YEAR}-{MAX_SUPPORTED_YEAR}).'
        )
    clock = None
    if time_text is not None:
        if _TIME.fullmatch(time_text) is None:
            raise FirstChartInputError('time must be in HH:MM or HH:MM:SS format.')
        clock = time.fromisoformat(time_text)
        if place is None:
            raise FirstChartInputError('A birth time needs the birth place.')
    if place is not None:
        try:
            load_timezone(place.timezone)
        except ValueError as exc:
            raise FirstChartInputError(str(exc)) from exc
    return FirstBirth(day=day, clock=clock, place=place)


def _pillar(name: PillarName, stem: str, branch: str) -> ChartPillar:
    stem_data = STEMS[stem]
    branch_data = BRANCHES[branch]
    return {
        'name': PILLAR_LABELS['en'][name],
        'stem': {
            'chinese': stem,
            'pinyin': stem_data['pinyin'],
            'element': stem_data['element'],
            'polarity': stem_data['polarity'],
        },
        'branch': {
            'chinese': branch,
            'pinyin': branch_data['pinyin'],
            'sign': branch_data['animal'],
            'element': branch_data['element'],
            'polarity': branch_data['polarity'],
        },
    }


def _engine_pillar(name: PillarName, payload: dict[str, Any]) -> ChartPillar:
    pillar = payload['pillars'][name]
    return _pillar(name, pillar['stem']['chinese'], pillar['branch']['chinese'])


def _jd_tt(instant: datetime) -> float:
    """An instant as the engine's Terrestrial Time Julian date."""
    utc = instant.astimezone(UTC)
    return (
        julian_date_from_datetime_utc(utc)
        + convert_utc_to_tt(utc).tt_minus_utc_seconds / SECONDS_PER_DAY
    )


def _changes_within(
    payload: dict[str, Any],
    names: tuple[PillarName, ...],
    start: datetime,
    end: datetime,
    zone: Any | None,
) -> list[PillarChange]:
    """Each change of the named pillars in [start, end), from the engine's own
    record of when each pillar last changed before the moment it charted, and when
    it next changes (eight_characters/pillar_changes.py). A pillar changes at most
    once on either side of that moment within a day."""
    moment = float(payload['intermediate']['tt_julian_date'])
    first, last = _jd_tt(start), _jd_tt(end)
    found: list[PillarChange] = []
    for name in names:
        here = _engine_pillar(name, payload)
        for side in ('previous', 'next'):
            change = payload['pillars'][name]['changes'][side]
            sign = -1.0 if side == 'previous' else 1.0
            jd = moment + sign * float(change['seconds']) / SECONDS_PER_DAY
            if not first < jd < last:
                continue
            there = _pillar(
                name,
                change['pillar']['stem']['chinese'],
                change['pillar']['branch']['chinese'],
            )
            instant = utc_from_jd_tt(jd)
            entry: PillarChange = {
                'pillar': name,
                'before': there if side == 'previous' else here,
                'after': here if side == 'previous' else there,
            }
            if zone is None:
                entry['at_utc'] = instant.strftime('%Y-%m-%dT%H:%M:%SZ')
            else:
                entry['at'] = instant.astimezone(zone).strftime('%H:%M:%S')
            found.append(entry)
    found.sort(key=lambda entry: entry.get('at') or entry.get('at_utc') or '')
    return found


def _day_master(stem: str) -> DayMaster:
    lens = load_canon()['day_masters'][stem]
    stem_data = STEMS[stem]
    return {
        'stem': stem,
        'pinyin': stem_data['pinyin'],
        'polarity': stem_data['polarity'],
        'element': stem_data['element'],
        'title': lens['title'],
        'passage': list(lens['core']),
    }


def _day_start(day: date, zone: Any) -> datetime:
    """The first instant of a local date. At a midnight the clocks skip, the day
    starts when they resume (fold 0); at one they repeat, at its first pass."""
    return datetime.combine(day, time(0), tzinfo=zone).astimezone(UTC)


def build_first_chart(birth: FirstBirth) -> FirstChart:
    if birth.place is None:
        # A date alone: the year and month wherever the birth was.
        noon = datetime.combine(birth.day, NOON, tzinfo=UTC)
        payload = compute_engine_payload(
            BirthInput(utc_timestamp=noon.strftime('%Y-%m-%dT%H:%M:%SZ'))
        )
        start = datetime.combine(birth.day, time(0), tzinfo=EARLIEST_OFFSET)
        end = datetime.combine(
            birth.day + timedelta(days=1), time(0), tzinfo=LATEST_OFFSET
        )
        changes = _changes_within(payload, DATE_PILLARS, start, end, None)
        changing = {change['pillar'] for change in changes}
        return {
            'pillars': {
                name: _engine_pillar(name, payload)
                for name in DATE_PILLARS
                if name not in changing
            },
            'changes': changes,
            'engine': payload['engine'],
        }

    place = birth.place
    zone = load_timezone(place.timezone)
    clock = birth.clock or NOON
    shown = clock.strftime('%H:%M:%S' if clock.second else '%H:%M')
    try:
        payload = compute_engine_payload(
            BirthInput(
                year=birth.day.year,
                month=birth.day.month,
                day=birth.day.day,
                hour=clock.hour,
                minute=clock.minute,
                second=clock.second,
                timezone_name=place.timezone,
                longitude=place.longitude,
                latitude=place.latitude,
                # Noon is the chart's own choice: its first pass, if the clocks
                # ever repeated it.
                fold=place.fold if birth.clock is not None else 0,
            )
        )
    except NonexistentTimeError as exc:
        raise FirstChartInputError(
            f'{shown} did not happen on {birth.day} in {place.timezone}: '
            'the clocks skipped it.'
        ) from exc
    except AmbiguousTimeError as exc:
        raise FirstChartInputError(
            f'{shown} happened twice on {birth.day} in {place.timezone}: give fold '
            '0 for its first pass, or 1 for its second.'
        ) from exc
    names = PILLAR_NAMES if birth.clock is not None else DAY_PILLARS
    chart: FirstChart = {
        'pillars': {name: _engine_pillar(name, payload) for name in names},
        'changes': [],
        'day_master': _day_master(payload['pillars']['day']['stem']['chinese']),
        'engine': payload['engine'],
    }
    if birth.clock is None:
        chart['changes'] = _changes_within(
            payload,
            names,
            _day_start(birth.day, zone),
            _day_start(birth.day + timedelta(days=1), zone),
            zone,
        )
    else:
        chart['flags'] = payload['flags']
    return chart
