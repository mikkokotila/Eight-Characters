"""The schools a person can choose for Today, by id, and the default of each.

Each setting is a school: a rule named for the classics it comes from. A person picks
a preset and never types a number. The rules themselves, and what the API says of each
preset, are in eight_characters/schools.py; the ids live here so that the account
records can check them without loading the engine.
"""

from typing import Final, Literal, TypeGuard

# Which elements feed the Day Master and which drain it: each element's weight.
FavourableSchool = Literal['support', 'climate']
# Which part of the year is Earth's, which sets every element's seasonal standing.
SeasonSchool = Literal['eighteen', 'months', 'late_summer', 'commander']
# How the year and the luck pillar count.
TransitSchool = Literal['phases', 'whole', 'seasoned']

FAVOURABLE_SCHOOLS: Final[tuple[FavourableSchool, ...]] = ('support', 'climate')
SEASON_SCHOOLS: Final[tuple[SeasonSchool, ...]] = (
    'eighteen',
    'months',
    'late_summer',
    'commander',
)
TRANSIT_SCHOOLS: Final[tuple[TransitSchool, ...]] = ('phases', 'whole', 'seasoned')

DEFAULT_FAVOURABLE: Final[FavourableSchool] = 'support'
DEFAULT_SEASON: Final[SeasonSchool] = 'eighteen'
DEFAULT_TRANSITS: Final[TransitSchool] = 'phases'


def is_favourable_school(value: str) -> TypeGuard[FavourableSchool]:
    return value in FAVOURABLE_SCHOOLS


def is_season_school(value: str) -> TypeGuard[SeasonSchool]:
    return value in SEASON_SCHOOLS


def is_transit_school(value: str) -> TypeGuard[TransitSchool]:
    return value in TRANSIT_SCHOOLS
