"""Ten-year luck pillars, using the engine's natal pillars and Jie instants.

San Ming Tong Hui, volume 2, 'On Major Cycles': Yang male / Yin female
progress forward, the other two backward; three elapsed days give one year
of starting age. This continuous elapsed-time convention retains seconds,
instead of quantizing into traditional two-hour blocks or whole minutes.

Starting age uses twelve 30-day months. To turn it into a timestamp, add the
years and months to the Gregorian UTC birth, clamp an invalid day to the
month's last day, then add the remaining days and time. Each subsequent cycle
starts on the ten-year UTC anniversary of the first start. Periods include
their start and exclude their end. This is arithmetic, not interpretation.

The same passage: while a cycle is on its stem, its branch is used as well;
while it is on its branch, the stem is set aside. Each cycle is therefore a
stem phase, its first five years, and a branch phase, its last five; the phase
boundary is the fifth UTC anniversary of the cycle's start, counted from the
first start like the cycles' own boundaries.
"""

from calendar import monthrange
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from math import isfinite
from typing import Literal

from typing_extensions import TypedDict

from eight_characters.sexagenary import BRANCHES, STEMS, Pillar
from eight_characters.time_convert import Gender, utc_from_jd_tt

DEFAULT_LUCK_PILLAR_COUNT = 10
MAX_LUCK_PILLAR_COUNT = 12
# Every Jie 1950-2100 is within 2.7 s of the independent reference; the HKO
# residual (~0.85 s) is documented in docs/validation.md. An allowance, not a
# proof of absolute accuracy, and deliberately above the natal 0.5 s allowance.
SOLAR_TERM_ALLOWANCE_SECONDS = 3.0
AGE_SECONDS_PER_BIRTH_SECOND = 120
_AGE_MONTH_SECONDS = 30 * 86400
_AGE_YEAR_SECONDS = 12 * _AGE_MONTH_SECONDS


class LuckAge(TypedDict):
    years: int
    months: int
    days: int
    hours: int
    minutes: int
    seconds: float


class Component(TypedDict):
    index: int
    chinese: str


PhaseName = Literal['stem', 'branch']


class LuckPhase(TypedDict):
    phase: PhaseName
    start_age: LuckAge
    end_age: LuckAge
    start_utc: str
    end_utc: str


class LuckPillar(TypedDict):
    sequence: int
    stem: Component
    branch: Component
    start_age: LuckAge
    end_age: LuckAge
    start_utc: str
    end_utc: str
    phases: list[LuckPhase]


class ReferenceJie(TypedDict):
    term: str
    longitude_deg: float
    tt_julian_date: float
    utc_time: str
    distance_seconds: float


class LuckUncertainty(TypedDict):
    birth_time_seconds: float
    solar_term_allowance_seconds: float
    scaled_age_seconds: float
    boundary_ambiguous: bool


class PreLuckPeriod(TypedDict):
    start_utc: str
    end_utc: str


class LuckPillarsPayload(TypedDict):
    rule_version: str
    phase_rule: Literal['stem_then_branch_v1']
    gender: Gender
    direction: Literal['forward', 'backward']
    year_stem_polarity: Literal['yang', 'yin']
    onset_method: str
    interval_basis: str
    calendar_basis: str
    reference_jie: ReferenceJie
    start_age: LuckAge
    start_utc: str
    uncertainty: LuckUncertainty
    pre_luck_period: PreLuckPeriod
    pillars: list[LuckPillar]


def luck_direction(gender: Gender, year_stem_idx: int) -> int:
    """+1 forward, -1 backward, using the resolved (Lichun-based) year stem."""
    if gender not in ('male', 'female'):
        raise ValueError('gender must be male or female.')
    if not 0 <= year_stem_idx < len(STEMS):
        raise ValueError('Invalid year stem index.')
    return 1 if (gender == 'male') == (year_stem_idx % 2 == 0) else -1


def start_age_from_interval(seconds: float) -> LuckAge:
    """Three elapsed days = one 360-day age year, preserving sub-minute time."""
    if not isfinite(seconds) or seconds < 0.0:
        raise ValueError('Jie interval must be finite and nonnegative.')
    # Round once to an age second before splitting: the solver's 0.01 birth
    # second tolerance becomes 1.2 age seconds. Julian-date roundoff must not
    # turn an exact year/month/day into the preceding component plus 59.999 s.
    scaled_seconds = seconds * AGE_SECONDS_PER_BIRTH_SECOND
    if not isfinite(scaled_seconds):
        raise ValueError('Jie interval is too large for luck-pillar age scaling.')
    remaining = round(scaled_seconds)
    years, remaining = divmod(remaining, _AGE_YEAR_SECONDS)
    months, remaining = divmod(remaining, _AGE_MONTH_SECONDS)
    days, remaining = divmod(remaining, 86400)
    hours, remaining = divmod(remaining, 3600)
    minutes, remaining = divmod(remaining, 60)
    return {
        'years': years,
        'months': months,
        'days': days,
        'hours': hours,
        'minutes': minutes,
        'seconds': float(remaining),
    }


def _calendar_months(instant: datetime, months: int) -> datetime:
    year, month0 = divmod(instant.year * 12 + instant.month - 1 + months, 12)
    return instant.replace(
        year=year,
        month=month0 + 1,
        day=min(instant.day, monthrange(year, month0 + 1)[1]),
    )


def _onset(instant: datetime, age: LuckAge) -> datetime:
    return _calendar_months(instant, age['years'] * 12 + age['months']) + timedelta(
        days=age['days'],
        hours=age['hours'],
        minutes=age['minutes'],
        seconds=age['seconds'],
    )


def _in_year(age: LuckAge, years: int) -> LuckAge:
    """The onset age's months, days and time, in another age year; a fresh record."""
    return {**age, 'years': years}


def _iso_utc(instant: datetime) -> str:
    return (
        instant.astimezone(UTC)
        .isoformat(timespec='microseconds')
        .replace('+00:00', 'Z')
    )


def build_luck_pillars(
    *,
    gender: Gender,
    birth_utc: datetime,
    birth_jd_tt: float,
    year_pillar: Pillar,
    month_pillar: Pillar,
    terms: Sequence[tuple[float, float]],
    labels: dict[float, str],
    count: int = DEFAULT_LUCK_PILLAR_COUNT,
    birth_time_uncertainty_seconds: float = 0.0,
) -> LuckPillarsPayload:
    """Build real cycles 1..count; the period before onset has no luck pillar.

    At a Jie, the new natal month has begun: backward selects that instant
    (inclusive), forward the following Jie (strictly later). A birth whose
    uncertainty overlaps any Jie gets a nominal timeline with a visible flag;
    its direction, anchor and onset are not asserted to be resolved.
    """
    if type(count) is not int or not 1 <= count <= MAX_LUCK_PILLAR_COUNT:
        raise ValueError(f'luck_pillar_count must be 1-{MAX_LUCK_PILLAR_COUNT}.')
    if birth_utc.tzinfo is None:
        raise ValueError('birth_utc must be timezone-aware.')
    if not isfinite(birth_jd_tt):
        raise ValueError('Birth TT Julian date must be finite.')
    if (
        not isfinite(birth_time_uncertainty_seconds)
        or birth_time_uncertainty_seconds < 0
    ):
        raise ValueError(
            'birth_time_uncertainty_seconds must be finite and nonnegative.'
        )
    interval_allowance = birth_time_uncertainty_seconds + SOLAR_TERM_ALLOWANCE_SECONDS
    scaled_age_seconds = interval_allowance * AGE_SECONDS_PER_BIRTH_SECOND
    if not isfinite(scaled_age_seconds):
        raise ValueError(
            'birth_time_uncertainty_seconds is too large for luck-pillar age scaling.'
        )
    for pillar in (year_pillar, month_pillar):
        if not 0 <= pillar.stem_idx < 10 or not 0 <= pillar.branch_idx < 12:
            raise ValueError('Invalid natal pillar index.')
        pillar.validate_polarity()
    direction = luck_direction(gender, year_pillar.stem_idx)
    candidates = [
        (jd, target)
        for target, jd in terms
        if (jd > birth_jd_tt if direction == 1 else jd <= birth_jd_tt)
    ]
    if not candidates:
        raise RuntimeError('Jie instants do not bracket the birth for luck pillars.')
    term_jd, target = min(candidates) if direction == 1 else max(candidates)
    interval = abs(term_jd - birth_jd_tt) * 86400.0
    age = start_age_from_interval(interval)
    onset = _onset(birth_utc.astimezone(UTC), age)
    # Every fifth anniversary of the first onset: cycle k starts at boundary 2(k-1),
    # changes from its stem to its branch at 2k-1, and ends at 2k.
    boundaries = [_calendar_months(onset, index * 60) for index in range(2 * count + 1)]
    pillars: list[LuckPillar] = []
    for index in range(1, count + 1):
        pillar = Pillar(
            (month_pillar.stem_idx + direction * index) % 10,
            (month_pillar.branch_idx + direction * index) % 12,
        )
        pillar.validate_polarity()
        first = age['years'] + (index - 1) * 10
        start_utc = _iso_utc(boundaries[2 * index - 2])
        middle_utc = _iso_utc(boundaries[2 * index - 1])
        end_utc = _iso_utc(boundaries[2 * index])
        pillars.append(
            {
                'sequence': index,
                'stem': {'index': pillar.stem_idx, 'chinese': STEMS[pillar.stem_idx]},
                'branch': {
                    'index': pillar.branch_idx,
                    'chinese': BRANCHES[pillar.branch_idx],
                },
                'start_age': _in_year(age, first),
                'end_age': _in_year(age, first + 10),
                'start_utc': start_utc,
                'end_utc': end_utc,
                'phases': [
                    {
                        'phase': 'stem',
                        'start_age': _in_year(age, first),
                        'end_age': _in_year(age, first + 5),
                        'start_utc': start_utc,
                        'end_utc': middle_utc,
                    },
                    {
                        'phase': 'branch',
                        'start_age': _in_year(age, first + 5),
                        'end_age': _in_year(age, first + 10),
                        'start_utc': middle_utc,
                        'end_utc': end_utc,
                    },
                ],
            }
        )
    boundary_distance = min(abs(jd - birth_jd_tt) * 86400.0 for _, jd in terms)
    return {
        'rule_version': 'dayun_elapsed_time_v1',
        'phase_rule': 'stem_then_branch_v1',
        'gender': gender,
        'direction': 'forward' if direction == 1 else 'backward',
        'year_stem_polarity': 'yang' if year_pillar.stem_idx % 2 == 0 else 'yin',
        'onset_method': 'three_days_per_year_continuous',
        'interval_basis': 'terrestrial_time',
        'calendar_basis': 'gregorian_utc',
        'reference_jie': {
            'term': labels[target],
            'longitude_deg': target,
            'tt_julian_date': term_jd,
            'utc_time': _iso_utc(utc_from_jd_tt(term_jd)),
            'distance_seconds': round(interval, 6),
        },
        'start_age': age,
        'start_utc': _iso_utc(onset),
        'uncertainty': {
            'birth_time_seconds': birth_time_uncertainty_seconds,
            'solar_term_allowance_seconds': SOLAR_TERM_ALLOWANCE_SECONDS,
            'scaled_age_seconds': scaled_age_seconds,
            'boundary_ambiguous': boundary_distance <= interval_allowance,
        },
        'pre_luck_period': {
            'start_utc': _iso_utc(birth_utc),
            'end_utc': _iso_utc(onset),
        },
        'pillars': pillars,
    }
