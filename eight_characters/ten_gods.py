import csv
import re
from pathlib import Path
from typing import Literal

from eight_characters.data import STEMS

# ── Ten Gods (十神) of a stem relative to the Day Master ──

TenGodName = Literal[
    'friend',
    'rob_wealth',
    'eating_god',
    'hurting_officer',
    'indirect_wealth',
    'direct_wealth',
    'seven_killings',
    'direct_officer',
    'indirect_resource',
    'direct_resource',
]
# The day stem is the Day Master (日主) itself, not one of its ten gods.
DayMasterName = Literal['day_master']

TEN_GOD_NAMES: tuple[TenGodName, ...] = (
    'friend',
    'rob_wealth',
    'eating_god',
    'hurting_officer',
    'indirect_wealth',
    'direct_wealth',
    'seven_killings',
    'direct_officer',
    'indirect_resource',
    'direct_resource',
)
DAY_MASTER: DayMasterName = 'day_master'

# Cell labels of resources/mappings/ten-gods.csv.
_TEN_GOD_BY_MAPPING_LABEL: dict[str, TenGodName] = {
    'Friend': 'friend',
    'Rob W.': 'rob_wealth',
    'Eat. God': 'eating_god',
    'Hurt. Off.': 'hurting_officer',
    'Ind. W.': 'indirect_wealth',
    'Dir. W.': 'direct_wealth',
    '7 Kills': 'seven_killings',
    'Dir. Off.': 'direct_officer',
    'Ind. Res.': 'indirect_resource',
    'Dir. Res.': 'direct_resource',
}
_MAPPING_ORIENTATION = 'Day Master \\ Target'
_STEM_HEADER_PATTERN = re.compile(
    r'(?P<pinyin>[A-Za-z]+) \((?P<sign>[+-])(?P<element>[A-Za-z]+)\)'
)
_POLARITY_BY_SIGN = {'+': 'Yang', '-': 'Yin'}
_STEM_CHAR_BY_PINYIN = {stem['pinyin']: char for char, stem in STEMS.items()}


def parse_ten_gods_mapping(csv_path: Path) -> dict[tuple[str, str], TenGodName]:
    """Return the ten god of every (day master stem, target stem) pair."""
    if not csv_path.exists():
        raise RuntimeError(f'Ten gods mapping not found: {csv_path}')
    with csv_path.open('r', encoding='utf-8', newline='') as csv_file:
        rows = list(csv.reader(csv_file))
    if not rows:
        raise RuntimeError(f'Ten gods mapping is empty: {csv_path}')

    header, *body = rows
    if not header or header[0].strip() != _MAPPING_ORIENTATION:
        raise RuntimeError(
            f'Ten gods mapping must be oriented {_MAPPING_ORIENTATION!r}: {csv_path}'
        )
    target_chars = [_stem_char_from_header(cell) for cell in header[1:]]
    _require_every_stem_once(target_chars, axis='columns', csv_path=csv_path)

    lookup: dict[tuple[str, str], TenGodName] = {}
    day_master_chars: list[str] = []
    for row in body:
        if len(row) != len(header):
            raise RuntimeError(
                f'Ten gods mapping row has {len(row)} cells, expected '
                f'{len(header)}: {row!r}'
            )
        day_master_char = _stem_char_from_header(row[0])
        day_master_chars.append(day_master_char)
        row_ten_gods: list[TenGodName] = []
        for target_char, cell in zip(target_chars, row[1:], strict=True):
            ten_god = _TEN_GOD_BY_MAPPING_LABEL.get(cell.strip())
            if ten_god is None:
                raise RuntimeError(
                    f'Unknown ten god label in ten gods mapping: {cell!r}'
                )
            lookup[(day_master_char, target_char)] = ten_god
            row_ten_gods.append(ten_god)
        if sorted(row_ten_gods) != sorted(TEN_GOD_NAMES):
            raise RuntimeError(
                'Ten gods mapping row must assign each ten god exactly once: '
                f'{row[0]!r}'
            )
    _require_every_stem_once(day_master_chars, axis='rows', csv_path=csv_path)
    return lookup


def _stem_char_from_header(cell: str) -> str:
    match = _STEM_HEADER_PATTERN.fullmatch(cell.strip())
    if match is None:
        raise RuntimeError(f'Invalid stem header in ten gods mapping: {cell!r}')
    stem_char = _STEM_CHAR_BY_PINYIN.get(match['pinyin'])
    if stem_char is None:
        raise RuntimeError(f'Unknown stem in ten gods mapping: {cell!r}')
    stem = STEMS[stem_char]
    if (
        _POLARITY_BY_SIGN[match['sign']] != stem['polarity']
        or match['element'].lower() != stem['element']
    ):
        raise RuntimeError(
            f'Stem header contradicts stem data in ten gods mapping: {cell!r}'
        )
    return stem_char


def _require_every_stem_once(
    stem_chars: list[str],
    *,
    axis: str,
    csv_path: Path,
) -> None:
    if sorted(stem_chars) != sorted(STEMS):
        raise RuntimeError(
            f'Ten gods mapping {axis} must list every stem exactly once: {csv_path}'
        )
