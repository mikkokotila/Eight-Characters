from dataclasses import dataclass
from datetime import datetime

from eight_characters.conventions import (
    ZI_CONVENTION_SPLIT_MIDNIGHT,
    ZI_CONVENTION_WHOLE_ZI_23,
    ConventionSettings,
)
from eight_characters.sexagenary import Pillar


@dataclass(frozen=True)
class IntegrityFlags:
    zi_hour_window: bool
    solar_term_ambiguous: bool
    hour_boundary_proximity_seconds: float
    model_uncertainty_seconds: float
    high_latitude_warning: bool
    alternative_pillars: dict | None


def validate_pillar_set(pillars: dict[str, Pillar]) -> None:
    for pillar in pillars.values():
        pillar.validate_polarity()


def model_uncertainty_seconds_for_year(year_value: int) -> float:
    if year_value < 1972:
        return 1.5
    return 0.5


def hour_boundary_distance_seconds(basis_dt: datetime) -> float:
    seconds_of_hour = basis_dt.minute * 60.0 + basis_dt.second + basis_dt.microsecond / 1_000_000.0
    seconds_to_previous_boundary = seconds_of_hour
    seconds_to_next_boundary = 3600.0 - seconds_of_hour
    return min(seconds_to_previous_boundary, seconds_to_next_boundary)


def is_zi_hour_window(basis_dt: datetime) -> bool:
    return basis_dt.hour in (23, 0)


def build_alternative_zi_convention(conventions: ConventionSettings) -> ConventionSettings:
    if conventions.zi_convention == ZI_CONVENTION_SPLIT_MIDNIGHT:
        return ConventionSettings(
            zi_convention=ZI_CONVENTION_WHOLE_ZI_23,
            hour_basis=conventions.hour_basis,
            day_boundary_basis=conventions.day_boundary_basis,
        )
    return ConventionSettings(
        zi_convention=ZI_CONVENTION_SPLIT_MIDNIGHT,
        hour_basis=conventions.hour_basis,
        day_boundary_basis=conventions.day_boundary_basis,
    )
