"""When each natal pillar last changed before the birth, and when it next changes.

A change is an instant at which the engine's own rules give a different pillar.
Candidate instants come from each rule: the solar terms for the year (Lichun) and
the month (the twelve jie), and for the day and hour the readings of the clock the
conventions choose (true solar or civil), plus that zone's daylight-saving
transitions. Moving away from the birth, the first candidate at which evaluating the
rules one millisecond before and after gives different pillars is the change, so the
result follows the engine exactly under every convention, across folds and gaps.

Distances are elapsed seconds of Terrestrial Time between the birth and the change.
"""

import heapq
from collections.abc import Callable, Iterable, Iterator, Sequence
from datetime import UTC, datetime, timedelta
from typing import NotRequired

from typing_extensions import TypedDict

from eight_characters.conventions import (
    DAY_BOUNDARY_BASIS_TRUE_SOLAR,
    HOUR_BASIS_TRUE_SOLAR,
    ZI_CONVENTION_WHOLE_ZI_23,
    ConventionSettings,
)
from eight_characters.sexagenary import (
    BRANCHES,
    STEMS,
    Pillar,
    day_pillar,
    hour_pillar,
    month_pillar,
    year_pillar,
)
from eight_characters.solar_position import compute_solar_position_and_tst
from eight_characters.time_convert import convert_utc_to_tt, load_timezone

LICHUN_LONGITUDE = 315.0
# Rules are evaluated this far either side of a candidate instant.
_PROBE = timedelta(milliseconds=1)
# Candidates are searched this far either side of the birth. A day lasts 24 hours on
# its clock, and a daylight-saving jump can stretch it by at most a few hours.
_DAY_WINDOW = timedelta(hours=30)
_HOUR_WINDOW = timedelta(hours=5)
_SOLVE_TOLERANCE = timedelta(microseconds=1)


class ChangePillar(TypedDict):
    stem: dict[str, int | str]
    branch: dict[str, int | str]


class PillarChange(TypedDict):
    seconds: float
    pillar: ChangePillar
    term: NotRequired[str]
    clock: NotRequired[str]
    clock_time: NotRequired[str]


class PillarChanges(TypedDict):
    previous: PillarChange
    next: PillarChange


def _pillar_payload(pillar: Pillar) -> ChangePillar:
    return {
        'stem': {'index': pillar.stem_idx, 'chinese': STEMS[pillar.stem_idx]},
        'branch': {'index': pillar.branch_idx, 'chinese': BRANCHES[pillar.branch_idx]},
    }


def _year_pillar_of(bazi_year: int) -> Pillar:
    # A birth at or after its civil year's Lichun belongs to that bazi year.
    pillar, _ = year_pillar(civil_year=bazi_year, birth_jd_tt=1.0, lichun_jd_tt=0.0)
    return pillar


def _term_changes(
    birth_jd_tt: float,
    terms: Sequence[tuple[float, float]],
    labels: dict[float, str],
    pillar_after: Callable[[float, float], Pillar],
    pillar_before: Callable[[float, float], Pillar],
) -> PillarChanges:
    """Nearest terms at or before, and after, the birth (rules start a pillar at its term)."""
    earlier = [(jd, target) for target, jd in terms if jd <= birth_jd_tt]
    later = [(jd, target) for target, jd in terms if jd > birth_jd_tt]
    if not earlier or not later:
        raise ValueError('Solar terms do not bracket the birth.')
    previous_jd, previous_target = max(earlier)
    next_jd, next_target = min(later)
    return {
        'previous': {
            'seconds': (birth_jd_tt - previous_jd) * 86400.0,
            'term': labels[previous_target],
            'pillar': _pillar_payload(pillar_before(previous_target, previous_jd)),
        },
        'next': {
            'seconds': (next_jd - birth_jd_tt) * 86400.0,
            'term': labels[next_target],
            'pillar': _pillar_payload(pillar_after(next_target, next_jd)),
        },
    }


def year_and_month_changes(
    birth_jd_tt: float,
    bazi_year: int,
    lichun_jds: Sequence[float],
    terms: Sequence[tuple[float, float]],
    labels: dict[float, str],
) -> tuple[PillarChanges, PillarChanges]:
    """`lichun_jds` are the Lichun of the bazi year and of the next; `terms` the jie
    around the birth, as (target longitude, jd_tt)."""
    lichun = [(LICHUN_LONGITUDE, jd) for jd in lichun_jds]
    year = _term_changes(
        birth_jd_tt,
        lichun,
        labels,
        pillar_after=lambda _target, _jd: _year_pillar_of(bazi_year + 1),
        pillar_before=lambda _target, _jd: _year_pillar_of(bazi_year - 1),
    )

    def month_at(target: float, after: bool) -> Pillar:
        # The year stem sets the month stems, and it changes at Lichun, itself a jie.
        year_of = bazi_year
        if target == LICHUN_LONGITUDE:
            year_of = bazi_year + 1 if after else bazi_year - 1
        longitude = (target + (1e-9 if after else -1e-9)) % 360.0
        return month_pillar(longitude, _year_pillar_of(year_of).stem_idx)

    month = _term_changes(
        birth_jd_tt,
        terms,
        labels,
        pillar_after=lambda target, _jd: month_at(target, after=True),
        pillar_before=lambda target, _jd: month_at(target, after=False),
    )
    return year, month


class _Clocks:
    """The engine's day and hour rules as functions of a real instant (aware UTC)."""

    def __init__(
        self,
        birth: datetime,
        timezone_name: str | None,
        longitude_deg: float,
        conventions: ConventionSettings,
    ) -> None:
        self.birth = birth
        self.zone = load_timezone(timezone_name) if timezone_name else None
        self.longitude_deg = longitude_deg
        self.conventions = conventions
        # The same instants are evaluated again and again: the birth, where every
        # solution starts, and either side of each candidate, for the day rule and
        # for the hour rule that follows it.
        self._true_solar: dict[datetime, datetime] = {}
        self._solved: dict[datetime, datetime] = {}

    def true_solar(self, instant: datetime) -> datetime:
        if instant not in self._true_solar:
            tt = convert_utc_to_tt(instant)
            self._true_solar[instant] = compute_solar_position_and_tst(
                utc_datetime=instant,
                longitude_deg=self.longitude_deg,
                tt_minus_utc_seconds=tt.tt_minus_utc_seconds,
            ).true_solar_time
        return self._true_solar[instant]

    def civil(self, instant: datetime) -> datetime:
        # With no timezone the engine reads the civil clock as UTC.
        if self.zone is None:
            return instant.astimezone(UTC).replace(tzinfo=None)
        return instant.astimezone(self.zone).replace(tzinfo=None)

    def reading(self, clock: str, instant: datetime) -> datetime:
        if clock == HOUR_BASIS_TRUE_SOLAR:
            return self.true_solar(instant)
        return self.civil(instant)

    def day(self, instant: datetime) -> Pillar:
        return day_pillar(
            civil_dt_local=self.civil(instant),
            tst_dt=self.true_solar(instant),
            conventions=self.conventions,
        ).pillar

    def hour(self, instant: datetime) -> Pillar:
        return hour_pillar(
            day_stem_idx=self.day(instant).stem_idx,
            civil_dt_local=self.civil(instant),
            tst_dt=self.true_solar(instant),
            conventions=self.conventions,
        )

    def true_solar_instant(self, reading: datetime) -> datetime:
        """The real instant at which true solar time shows the reading."""
        if reading not in self._solved:
            # True solar time runs one-to-one with real time, give or take the slow
            # drift of the equation of time, so this converges within a few steps.
            instant = self.birth + (reading - self.true_solar(self.birth))
            for _ in range(20):
                step = reading - self.true_solar(instant)
                instant += step
                if abs(step) <= _SOLVE_TOLERANCE:
                    break
            else:
                raise ValueError('True solar time could not be inverted.')
            self._solved[reading] = instant
        return self._solved[reading]

    def civil_instants(self, reading: datetime) -> list[datetime]:
        """Real instants at which the civil clock shows the reading (none, one, or two)."""
        if self.zone is None:
            return [reading.replace(tzinfo=UTC)]
        instants: list[datetime] = []
        for fold in (0, 1):
            instant = reading.replace(tzinfo=self.zone, fold=fold).astimezone(UTC)
            # Kept only when the clock really shows the reading then (not in a gap).
            if self.civil(instant) == reading and instant not in instants:
                instants.append(instant)
        return instants

    def zone_transitions(self, start: datetime, end: datetime) -> list[datetime]:
        """Instants at which the civil clock jumps (daylight saving, offset changes)."""
        if self.zone is None:
            return []
        zone = self.zone
        transitions: list[datetime] = []
        step = timedelta(minutes=30)
        cursor = start
        while cursor < end:
            later = min(cursor + step, end)
            if (
                cursor.astimezone(zone).utcoffset()
                != later.astimezone(zone).utcoffset()
            ):
                low, high = cursor, later
                while high - low > _SOLVE_TOLERANCE:
                    middle = low + (high - low) / 2
                    if (
                        middle.astimezone(zone).utcoffset()
                        == low.astimezone(zone).utcoffset()
                    ):
                        low = middle
                    else:
                        high = middle
                transitions.append(high)
            cursor = later
        return transitions


# A candidate change: its instant, the clock that marks it, and what that clock
# shows then, to the second.
_Candidate = tuple[datetime, str, datetime]


def _to_the_second(reading: datetime) -> datetime:
    return (reading + timedelta(microseconds=500_000)).replace(microsecond=0)


def _clock_readings(
    start: datetime, end: datetime, keep: Callable[[datetime], bool]
) -> list[datetime]:
    """Whole-hour clock readings from start to end that the rule marks as boundaries."""
    reading = start.replace(minute=0, second=0, microsecond=0)
    readings: list[datetime] = []
    while reading <= end:
        if keep(reading):
            readings.append(reading)
        reading += timedelta(hours=1)
    return readings


def _true_solar_candidates(
    clocks: _Clocks, readings: list[datetime], later: bool
) -> Iterator[_Candidate]:
    """Boundaries of true solar time on one side of the birth, nearest first.

    True solar time only moves forward, so its readings come in the order of their
    instants, and each is solved only when it is reached. The walk starts from the
    nearest reading on the other side of the birth's: solved to a microsecond, its
    instant can still fall on this side.
    """
    birth_reading = clocks.true_solar(clocks.birth)
    if later:
        start = max(
            (
                index
                for index, reading in enumerate(readings)
                if reading <= birth_reading
            ),
            default=0,
        )
        ordered = readings[start:]
    else:
        start = min(
            (
                index
                for index, reading in enumerate(readings)
                if reading > birth_reading
            ),
            default=len(readings) - 1,
        )
        ordered = readings[start::-1]
    for reading in ordered:
        instant = clocks.true_solar_instant(reading)
        if (instant > clocks.birth) == later:
            yield instant, HOUR_BASIS_TRUE_SOLAR, reading


def _civil_candidates(
    clocks: _Clocks, readings: list[datetime], window: timedelta, later: bool
) -> list[_Candidate]:
    """Boundaries and jumps of the civil clock on one side of the birth, nearest first.

    Around a daylight-saving fold the same reading comes twice, so these are ordered
    by their instants, not by their readings.
    """
    found: list[_Candidate] = [
        (instant, 'civil', reading)
        for reading in readings
        for instant in clocks.civil_instants(reading)
    ]
    found += [
        (instant, 'civil', _to_the_second(clocks.civil(instant)))
        for instant in clocks.zone_transitions(
            clocks.birth - window, clocks.birth + window
        )
    ]
    return sorted(
        (candidate for candidate in found if (candidate[0] > clocks.birth) == later),
        key=lambda candidate: candidate[0],
        reverse=not later,
    )


def _first_change(
    clocks: _Clocks,
    rule: Callable[[datetime], Pillar],
    sources: Sequence[tuple[str, Callable[[datetime], bool], timedelta]],
    later: bool,
) -> _Candidate:
    """The nearest candidate on one side of the birth at which the pillar changes."""
    streams: list[Iterable[_Candidate]] = []
    for clock, keep, window in sources:
        birth_reading = clocks.reading(clock, clocks.birth)
        readings = _clock_readings(birth_reading - window, birth_reading + window, keep)
        if clock == HOUR_BASIS_TRUE_SOLAR:
            streams.append(_true_solar_candidates(clocks, readings, later))
        else:
            streams.append(_civil_candidates(clocks, readings, window, later))
    # Every clock's candidates, merged in order of distance from the birth.
    for candidate in heapq.merge(
        *streams, key=lambda candidate: candidate[0], reverse=not later
    ):
        instant = candidate[0]
        if rule(instant - _PROBE) != rule(instant + _PROBE):
            return candidate
    raise ValueError('No pillar change found around the birth.')


def _clock_changes(
    clocks: _Clocks,
    rule: Callable[[datetime], Pillar],
    sources: Sequence[tuple[str, Callable[[datetime], bool], timedelta]],
) -> PillarChanges:
    """Nearest confirmed changes of a pillar decided on one or more clocks."""
    previous_instant, previous_clock, previous_reading = _first_change(
        clocks, rule, sources, later=False
    )
    next_instant, next_clock, next_reading = _first_change(
        clocks, rule, sources, later=True
    )

    def elapsed(start: datetime, end: datetime) -> float:
        # Terrestrial Time runs uniformly; UTC skips or repeats leap seconds.
        tt_offset = (
            convert_utc_to_tt(end).tt_minus_utc_seconds
            - convert_utc_to_tt(start).tt_minus_utc_seconds
        )
        return (end - start).total_seconds() + tt_offset

    return {
        'previous': {
            'seconds': elapsed(previous_instant, clocks.birth),
            'clock': previous_clock,
            'clock_time': previous_reading.isoformat(),
            'pillar': _pillar_payload(rule(previous_instant - _PROBE)),
        },
        'next': {
            'seconds': elapsed(clocks.birth, next_instant),
            'clock': next_clock,
            'clock_time': next_reading.isoformat(),
            'pillar': _pillar_payload(rule(next_instant + _PROBE)),
        },
    }


def day_and_hour_changes(
    birth_utc: datetime,
    timezone_name: str | None,
    longitude_deg: float,
    conventions: ConventionSettings,
    day: Pillar,
    hour: Pillar,
) -> tuple[PillarChanges, PillarChanges]:
    clocks = _Clocks(birth_utc, timezone_name, longitude_deg, conventions)
    # The rules as instants must give the engine's pillars at the birth itself.
    if clocks.day(birth_utc) != day or clocks.hour(birth_utc) != hour:
        raise ValueError('Pillar change rules disagree with the natal pillars.')

    day_clock = (
        HOUR_BASIS_TRUE_SOLAR
        if conventions.day_boundary_basis == DAY_BOUNDARY_BASIS_TRUE_SOLAR
        else 'civil'
    )
    hour_clock = (
        HOUR_BASIS_TRUE_SOLAR
        if conventions.hour_basis == HOUR_BASIS_TRUE_SOLAR
        else 'civil'
    )
    day_starts_at = 23 if conventions.zi_convention == ZI_CONVENTION_WHOLE_ZI_23 else 0

    def day_boundary(reading: datetime) -> bool:
        return reading.hour == day_starts_at

    def hour_boundary(reading: datetime) -> bool:
        # A double hour starts at every odd hour; Zi begins at 23:00.
        return reading.hour % 2 == 1

    day_changes = _clock_changes(
        clocks, clocks.day, [(day_clock, day_boundary, _DAY_WINDOW)]
    )
    # The hour's stem follows the day's, so a day change changes the hour pillar too.
    hour_changes = _clock_changes(
        clocks,
        clocks.hour,
        [
            (hour_clock, hour_boundary, _HOUR_WINDOW),
            (day_clock, day_boundary, _HOUR_WINDOW),
        ],
    )
    return day_changes, hour_changes
