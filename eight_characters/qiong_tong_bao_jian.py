"""Qiong Tong Bao Jian's climate table: the stems each Day Master's birth month calls
for, as the Climate school (调候 Tiao Hou) reads them (docs/Today.md, Climate).

The text is prose, not a table. Each entry here keeps the stems in the text's order of
use and the sentence they are taken from, word for word, with the heading it stands
under. Where the text treats months together, each month takes the shared entry. A
stem the text names only as a condition or a fallback is left out.
"""

from dataclasses import dataclass
from typing import Final

from eight_characters.sexagenary import BRANCHES, STEMS

# The month each of the text's month names opens with: 正月 the first is 寅 Yin.
MONTH_BRANCHES: Final = '寅卯辰巳午未申酉戌亥子丑'


@dataclass(frozen=True)
class ClimateEntry:
    day_master: str
    # The month branches the entry covers.
    months: str
    # The stems the text names as used, in its order.
    stems: tuple[str, ...]
    # The heading the sentence stands under, and the sentence, as the text has them.
    heading: str
    sentence: str


TABLE: Final[tuple[ClimateEntry, ...]] = ()


def _index() -> dict[tuple[str, str], ClimateEntry]:
    found: dict[tuple[str, str], ClimateEntry] = {}
    for entry in TABLE:
        if entry.day_master not in STEMS or not entry.stems:
            raise RuntimeError(f'A climate entry is malformed: {entry.heading}')
        if any(stem not in STEMS for stem in entry.stems):
            raise RuntimeError(f'A climate entry names no stem: {entry.heading}')
        if any(stem not in entry.sentence for stem in entry.stems):
            raise RuntimeError(
                f'A climate entry names a stem its sentence lacks: {entry.heading}'
            )
        for month in entry.months:
            if month not in BRANCHES:
                raise RuntimeError(f'A climate entry names no month: {entry.heading}')
            key = (entry.day_master, month)
            if key in found:
                raise RuntimeError(f'Two climate entries for {key}.')
            found[key] = entry
    return found


ENTRIES: Final = _index()


def climate_entry(day_master: str, month_branch: str) -> ClimateEntry:
    entry = ENTRIES.get((day_master, month_branch))
    if entry is None:
        raise LookupError(
            f'The climate table has no entry for {day_master} in the {month_branch} '
            'month.'
        )
    return entry


def climate_stems(day_master: str, month_branch: str) -> list[str]:
    """The stems the text names for this Day Master in this birth month, in order."""
    return list(climate_entry(day_master, month_branch).stems)
