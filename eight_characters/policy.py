from dataclasses import dataclass
from datetime import datetime

from eight_characters.conventions import ConventionSettings


MIN_SUPPORTED_YEAR = 1949
MAX_SUPPORTED_YEAR = 2100

SUPPORTED_CALENDAR = 'gregorian'
SUPPORTED_ASTRONOMICAL_MODEL = 'vsop87d_full_earth_plus_iau2000a'
SUPPORTED_REFERENCE_FRAME = 'geocentric_apparent_ecliptic_longitude'

FORBIDDEN_CALCULATION_DEPENDENCIES = (
    'scipy',
    'numpy',
    'swisseph',
)

ENGINE_DECISIONS: dict[str, str] = {
    'D-001': 'Temporal scope is 1949-2100.',
    'D-002': 'Gregorian input only.',
    'D-003': 'Worldwide coordinates supported.',
    'D-004': 'Output scope is Four Pillars only.',
    'D-005': 'Gender is not an input.',
    'D-006': 'Use VSOP87D full Earth series, not EMB.',
    'D-007': 'Use IAU 2000A nutation.',
    'D-007a': 'Use IAU 2006 mean obliquity.',
    'D-008': 'Use Espenak-Meeus delta-T model.',
    'D-009': 'Use geocentric apparent coordinates.',
    'D-010': 'Use pure-Python Brent method; no SciPy.',
    'D-011': 'Do not use Swiss Ephemeris.',
    'D-012': 'Altitude not used.',
    'D-013': 'Route time conversion by post/pre-1972 path.',
    'D-014': 'Use IANA tzdata and expose tzdb version.',
    'D-015': 'Explicit fold/gap handling required.',
    'D-016': 'Embed leap-second table and metadata.',
    'D-017': 'Default hour basis is true solar time.',
    'D-018': 'Default zi convention is split midnight.',
    'D-019': 'Day boundary basis is independent setting.',
    'D-020': 'Year boundary is Lichun at 315 degrees.',
    'D-021': 'Month boundaries are 12 jie longitudes only.',
    'D-022': 'Day index formula: idx0 = (JDN - 11) % 60.',
    'D-023': 'Python first, no compiled calculation dependency.',
    'D-024': 'Geocoding is separate from core engine.',
    'D-025': 'Report uncertainty and ambiguity alternatives.',
}


@dataclass(frozen=True)
class EnginePolicy:
    min_year: int = MIN_SUPPORTED_YEAR
    max_year: int = MAX_SUPPORTED_YEAR
    calendar: str = SUPPORTED_CALENDAR
    astronomical_model: str = SUPPORTED_ASTRONOMICAL_MODEL
    reference_frame: str = SUPPORTED_REFERENCE_FRAME
    output_scope: str = 'four_pillars_only'
    default_hour_basis: str = 'true_solar'
    default_zi_convention: str = 'split_midnight'
    allow_interpretive_layers: bool = False

    def validate_year(self, year: int) -> None:
        if year < self.min_year or year > self.max_year:
            raise ValueError('Date out of supported range (1949-2100).')

    def validate_calendar(self, calendar: str) -> None:
        if calendar != self.calendar:
            raise ValueError('Only Gregorian calendar input is supported.')

    def validate_output_scope(self, include_interpretive_layers: bool) -> None:
        if include_interpretive_layers:
            raise ValueError('Interpretive layers are out of scope.')

    def validate_dependency_policy(self, dependency_names: list[str]) -> None:
        lower_names = {name.lower() for name in dependency_names}
        for forbidden_name in FORBIDDEN_CALCULATION_DEPENDENCIES:
            if forbidden_name in lower_names:
                raise ValueError(f'Forbidden calculation dependency: {forbidden_name}')


def validate_core_input_scope(
    year: int,
    calendar: str,
    conventions: ConventionSettings,
    include_interpretive_layers: bool = False,
) -> None:
    policy = EnginePolicy()
    policy.validate_year(year)
    policy.validate_calendar(calendar)
    policy.validate_output_scope(include_interpretive_layers)
    conventions.validate()


def route_time_conversion(utc_timestamp: datetime) -> str:
    routing_threshold = datetime(1972, 1, 1)
    if utc_timestamp >= routing_threshold:
        return 'post_1972_leap_seconds'
    return 'pre_1972_delta_t'


def decision_ids() -> tuple[str, ...]:
    return tuple(ENGINE_DECISIONS.keys())
