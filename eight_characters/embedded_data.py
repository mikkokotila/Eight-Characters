from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from bisect import bisect_right


UTC = timezone.utc

ENGINE_MODEL_IDS = {
    'vsop87_series': 'VSOP87D_full_Earth',
    'nutation_model': 'IAU_2000A',
    'mean_obliquity_model': 'IAU_2006',
    'delta_t_model': 'Espenak_Meeus',
}


LEAP_SECOND_METADATA = {
    'source': 'IANA leap-seconds.list',
    'last_update': '2017-01-01T00:00:00Z',
    'expires': '2025-06-28T00:00:00Z',
}


@dataclass(frozen=True)
class DeltaTSegment:
    start_year: float
    end_year: float
    reference: str

    def contains(self, decimal_year_value: float) -> bool:
        return self.start_year <= decimal_year_value < self.end_year

    def evaluate(self, decimal_year_value: float) -> float:
        raise NotImplementedError


@dataclass(frozen=True)
class Segment1941to1961(DeltaTSegment):
    def evaluate(self, decimal_year_value: float) -> float:
        t = decimal_year_value - 1950.0
        return 29.07 + 0.407 * t - (t ** 2) / 233.0 + (t ** 3) / 2547.0


@dataclass(frozen=True)
class Segment1961to1986(DeltaTSegment):
    def evaluate(self, decimal_year_value: float) -> float:
        t = decimal_year_value - 1975.0
        return 45.45 + 1.067 * t - (t ** 2) / 260.0 - (t ** 3) / 718.0


@dataclass(frozen=True)
class Segment1986to2005(DeltaTSegment):
    def evaluate(self, decimal_year_value: float) -> float:
        t = decimal_year_value - 2000.0
        return (
            63.86
            + 0.3345 * t
            - 0.060374 * (t ** 2)
            + 0.0017275 * (t ** 3)
            + 0.000651814 * (t ** 4)
            + 0.00002373599 * (t ** 5)
        )


@dataclass(frozen=True)
class Segment2005to2050(DeltaTSegment):
    def evaluate(self, decimal_year_value: float) -> float:
        t = decimal_year_value - 2000.0
        return 62.92 + 0.32217 * t + 0.005589 * (t ** 2)


@dataclass(frozen=True)
class Segment2050to2150(DeltaTSegment):
    def evaluate(self, decimal_year_value: float) -> float:
        u = (decimal_year_value - 1820.0) / 100.0
        return -20.0 + 32.0 * (u ** 2) - 0.5628 * (2150.0 - decimal_year_value)


DELTA_T_SEGMENTS: tuple[DeltaTSegment, ...] = (
    Segment1941to1961(1941.0, 1961.0, 't = y - 1950'),
    Segment1961to1986(1961.0, 1986.0, 't = y - 1975'),
    Segment1986to2005(1986.0, 2005.0, 't = y - 2000'),
    Segment2005to2050(2005.0, 2050.0, 't = y - 2000'),
    Segment2050to2150(2050.0, 2150.0, 'u = (y - 1820) / 100'),
)


# Effective TAI-UTC at each UTC threshold moment.
LEAP_SECOND_OFFSETS: tuple[tuple[datetime, int], ...] = (
    (datetime(1972, 1, 1, tzinfo=UTC), 10),
    (datetime(1972, 7, 1, tzinfo=UTC), 11),
    (datetime(1973, 1, 1, tzinfo=UTC), 12),
    (datetime(1974, 1, 1, tzinfo=UTC), 13),
    (datetime(1975, 1, 1, tzinfo=UTC), 14),
    (datetime(1976, 1, 1, tzinfo=UTC), 15),
    (datetime(1977, 1, 1, tzinfo=UTC), 16),
    (datetime(1978, 1, 1, tzinfo=UTC), 17),
    (datetime(1979, 1, 1, tzinfo=UTC), 18),
    (datetime(1980, 1, 1, tzinfo=UTC), 19),
    (datetime(1981, 7, 1, tzinfo=UTC), 20),
    (datetime(1982, 7, 1, tzinfo=UTC), 21),
    (datetime(1983, 7, 1, tzinfo=UTC), 22),
    (datetime(1985, 7, 1, tzinfo=UTC), 23),
    (datetime(1988, 1, 1, tzinfo=UTC), 24),
    (datetime(1990, 1, 1, tzinfo=UTC), 25),
    (datetime(1991, 1, 1, tzinfo=UTC), 26),
    (datetime(1992, 7, 1, tzinfo=UTC), 27),
    (datetime(1993, 7, 1, tzinfo=UTC), 28),
    (datetime(1994, 7, 1, tzinfo=UTC), 29),
    (datetime(1996, 1, 1, tzinfo=UTC), 30),
    (datetime(1997, 7, 1, tzinfo=UTC), 31),
    (datetime(1999, 1, 1, tzinfo=UTC), 32),
    (datetime(2006, 1, 1, tzinfo=UTC), 33),
    (datetime(2009, 1, 1, tzinfo=UTC), 34),
    (datetime(2012, 7, 1, tzinfo=UTC), 35),
    (datetime(2015, 7, 1, tzinfo=UTC), 36),
    (datetime(2017, 1, 1, tzinfo=UTC), 37),
)

_LEAP_THRESHOLDS = tuple(item[0] for item in LEAP_SECOND_OFFSETS)


def get_tzdb_version() -> str:
    try:
        return metadata.version('tzdata')
    except metadata.PackageNotFoundError:
        return 'system'


def get_leap_second_offset_seconds(utc_datetime: datetime) -> int:
    if utc_datetime.tzinfo is None:
        raise ValueError('utc_datetime must be timezone-aware UTC.')

    idx = bisect_right(_LEAP_THRESHOLDS, utc_datetime) - 1
    if idx < 0:
        return 0
    return LEAP_SECOND_OFFSETS[idx][1]


def evaluate_delta_t_seconds(decimal_year_value: float) -> float:
    for segment in DELTA_T_SEGMENTS:
        if segment.contains(decimal_year_value):
            return segment.evaluate(decimal_year_value)
    raise ValueError('Decimal year outside supported delta-T segments.')
