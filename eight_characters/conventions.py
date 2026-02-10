from dataclasses import dataclass


ZI_CONVENTION_SPLIT_MIDNIGHT = 'split_midnight'
ZI_CONVENTION_WHOLE_ZI_23 = 'whole_zi_23'

HOUR_BASIS_TRUE_SOLAR = 'true_solar'
HOUR_BASIS_CIVIL = 'civil'

DAY_BOUNDARY_BASIS_TRUE_SOLAR = 'true_solar'
DAY_BOUNDARY_BASIS_CIVIL = 'civil'

ALLOWED_ZI_CONVENTIONS = (
    ZI_CONVENTION_SPLIT_MIDNIGHT,
    ZI_CONVENTION_WHOLE_ZI_23,
)
ALLOWED_HOUR_BASES = (
    HOUR_BASIS_TRUE_SOLAR,
    HOUR_BASIS_CIVIL,
)
ALLOWED_DAY_BOUNDARY_BASES = (
    DAY_BOUNDARY_BASIS_TRUE_SOLAR,
    DAY_BOUNDARY_BASIS_CIVIL,
)


@dataclass(frozen=True)
class ConventionSettings:
    zi_convention: str = ZI_CONVENTION_SPLIT_MIDNIGHT
    hour_basis: str = HOUR_BASIS_TRUE_SOLAR
    day_boundary_basis: str = DAY_BOUNDARY_BASIS_TRUE_SOLAR

    def validate(self) -> None:
        if self.zi_convention not in ALLOWED_ZI_CONVENTIONS:
            raise ValueError('Invalid zi_convention.')
        if self.hour_basis not in ALLOWED_HOUR_BASES:
            raise ValueError('Invalid hour_basis.')
        if self.day_boundary_basis not in ALLOWED_DAY_BOUNDARY_BASES:
            raise ValueError('Invalid day_boundary_basis.')


def all_supported_convention_combinations() -> list[ConventionSettings]:
    combinations: list[ConventionSettings] = []
    for zi_convention in ALLOWED_ZI_CONVENTIONS:
        for hour_basis in ALLOWED_HOUR_BASES:
            for day_boundary_basis in ALLOWED_DAY_BOUNDARY_BASES:
                combinations.append(
                    ConventionSettings(
                        zi_convention=zi_convention,
                        hour_basis=hour_basis,
                        day_boundary_basis=day_boundary_basis,
                    )
                )
    return combinations
