from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from eight_characters.conventions import ConventionSettings
from eight_characters.embedded_data import (
    LEAP_SECOND_METADATA,
    evaluate_delta_t_seconds,
    get_leap_second_offset_seconds,
    get_tzdb_version,
)
from eight_characters.policy import EnginePolicy


UTC = timezone.utc


class TimeResolutionError(ValueError):
    pass


class AmbiguousTimeError(TimeResolutionError):
    pass


class NonexistentTimeError(TimeResolutionError):
    pass


@dataclass(frozen=True)
class BirthInput:
    year: int | None = None
    month: int | None = None
    day: int | None = None
    hour: int | None = None
    minute: int | None = None
    second: int | None = None
    timezone_name: str | None = None
    longitude: float = 0.0
    latitude: float = 0.0
    fold: int | None = None
    utc_timestamp: str | None = None
    birth_time_uncertainty_seconds: float | None = None
    conventions: ConventionSettings = ConventionSettings()


@dataclass(frozen=True)
class NormalizedTimeInput:
    utc_datetime: datetime
    civil_datetime_local: datetime | None
    timezone_name: str | None
    fold: int | None
    longitude: float
    latitude: float
    high_latitude_warning: bool
    tzdb_version: str


@dataclass(frozen=True)
class TTConversionResult:
    tt_datetime: datetime
    tt_minus_utc_seconds: float
    delta_t_seconds: float
    conversion_method: str
    leap_second_metadata: dict[str, str]


def _parse_utc_timestamp(utc_timestamp: str) -> datetime:
    raw_value = utc_timestamp.strip()
    if raw_value.endswith('Z'):
        raw_value = raw_value[:-1] + '+00:00'
    parsed = datetime.fromisoformat(raw_value)
    if parsed.tzinfo is None:
        raise ValueError('utc_timestamp must include timezone information.')
    return parsed.astimezone(UTC)


def _resolve_local_time(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    timezone_name: str,
    fold: int | None,
) -> datetime:
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError('Unrecognized timezone identifier.') from exc

    wall = datetime(year, month, day, hour, minute, second)
    dt0 = wall.replace(tzinfo=tz, fold=0)
    dt1 = wall.replace(tzinfo=tz, fold=1)

    utc0 = dt0.astimezone(UTC)
    utc1 = dt1.astimezone(UTC)

    rt0 = utc0.astimezone(tz)
    rt1 = utc1.astimezone(tz)

    def _matches(roundtrip_dt: datetime, expected_fold: int) -> bool:
        return roundtrip_dt.replace(tzinfo=None) == wall and roundtrip_dt.fold == expected_fold

    m0 = _matches(rt0, 0)
    m1 = _matches(rt1, 1)

    if not m0 and not m1:
        raise NonexistentTimeError(
            'This local time does not exist due to DST transition. Provide utc_timestamp directly.'
        )

    if m0 and m1 and utc0 != utc1:
        if fold is None:
            raise AmbiguousTimeError(
                'This local time is ambiguous due to DST fall-back. '
                'Specify fold=0 (first occurrence) or fold=1 (second).'
            )
        if fold not in (0, 1):
            raise ValueError('fold must be 0 or 1.')
        return utc0 if fold == 0 else utc1

    if m0:
        return utc0
    if m1:
        return utc1

    raise TimeResolutionError('Internal error: could not resolve local time to UTC.')


def normalize_birth_input(value: BirthInput) -> NormalizedTimeInput:
    policy = EnginePolicy()
    value.conventions.validate()

    if value.latitude < -90.0 or value.latitude > 90.0:
        raise ValueError('Invalid latitude.')
    if value.longitude < -180.0 or value.longitude > 180.0:
        raise ValueError('Invalid longitude.')

    high_latitude_warning = value.latitude > 66.0 or value.latitude < -66.0
    tzdb_version = get_tzdb_version()

    if value.utc_timestamp:
        utc_datetime = _parse_utc_timestamp(value.utc_timestamp)
        policy.validate_year(utc_datetime.year)
        return NormalizedTimeInput(
            utc_datetime=utc_datetime,
            civil_datetime_local=None,
            timezone_name=None,
            fold=None,
            longitude=value.longitude,
            latitude=value.latitude,
            high_latitude_warning=high_latitude_warning,
            tzdb_version=tzdb_version,
        )

    required_local_fields = (
        value.year,
        value.month,
        value.day,
        value.hour,
        value.minute,
        value.second,
        value.timezone_name,
    )
    if any(field is None for field in required_local_fields):
        raise ValueError('Local time mode requires date, time, and timezone fields.')

    policy.validate_year(value.year)

    utc_datetime = _resolve_local_time(
        year=value.year,
        month=value.month,
        day=value.day,
        hour=value.hour,
        minute=value.minute,
        second=value.second,
        timezone_name=value.timezone_name,
        fold=value.fold,
    )

    civil_datetime_local = datetime(
        value.year,
        value.month,
        value.day,
        value.hour,
        value.minute,
        value.second,
    )

    return NormalizedTimeInput(
        utc_datetime=utc_datetime,
        civil_datetime_local=civil_datetime_local,
        timezone_name=value.timezone_name,
        fold=value.fold,
        longitude=value.longitude,
        latitude=value.latitude,
        high_latitude_warning=high_latitude_warning,
        tzdb_version=tzdb_version,
    )


def decimal_year(utc_datetime: datetime) -> float:
    if utc_datetime.tzinfo is None:
        raise ValueError('utc_datetime must be timezone-aware UTC.')
    normalized_utc = utc_datetime.astimezone(UTC)
    year_value = normalized_utc.year
    start = datetime(year_value, 1, 1, tzinfo=UTC)
    end = datetime(year_value + 1, 1, 1, tzinfo=UTC)
    elapsed_seconds = (normalized_utc - start).total_seconds()
    total_seconds = (end - start).total_seconds()
    return year_value + elapsed_seconds / total_seconds


def convert_utc_to_tt(utc_datetime: datetime) -> TTConversionResult:
    if utc_datetime.tzinfo is None:
        raise ValueError('utc_datetime must be timezone-aware UTC.')
    normalized_utc = utc_datetime.astimezone(UTC)
    threshold = datetime(1972, 1, 1, tzinfo=UTC)

    if normalized_utc >= threshold:
        tai_minus_utc = float(get_leap_second_offset_seconds(normalized_utc))
        tt_minus_utc = tai_minus_utc + 32.184
        tt_datetime = normalized_utc.replace(tzinfo=None) + timedelta(seconds=tt_minus_utc)
        return TTConversionResult(
            tt_datetime=tt_datetime,
            tt_minus_utc_seconds=tt_minus_utc,
            delta_t_seconds=tt_minus_utc,
            conversion_method='leap_seconds',
            leap_second_metadata=LEAP_SECOND_METADATA,
        )

    decimal_year_value = decimal_year(normalized_utc)
    delta_t_seconds = evaluate_delta_t_seconds(decimal_year_value)
    tt_datetime = normalized_utc.replace(tzinfo=None) + timedelta(seconds=delta_t_seconds)
    return TTConversionResult(
        tt_datetime=tt_datetime,
        tt_minus_utc_seconds=delta_t_seconds,
        delta_t_seconds=delta_t_seconds,
        conversion_method='delta_t',
        leap_second_metadata=LEAP_SECOND_METADATA,
    )
