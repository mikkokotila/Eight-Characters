"""The twelve life stages (十二长生) of a stem on a branch.

Yang stems run forward through the branches and yin stems backward, and Earth
follows Fire, as in 三命通会 and the canon's mapping. The table is the one the
Evolution engine keeps; tests hold every cell to the canon's own table and to an
independent reference.
"""

from eight_characters.data import BRANCHES, STEMS, ElementName
from eight_characters.evolution.primitives import (
    ELEMENT_EARTH,
    ELEMENT_FIRE,
    ELEMENT_METAL,
    ELEMENT_WATER,
    ELEMENT_WOOD,
    life_stage_anchor,
)

# The engine's branch order, Zi first.
_BRANCH_ORDER = '子丑寅卯辰巳午未申酉戌亥'
_ELEMENT_INDEX: dict[ElementName, int] = {
    'wood': ELEMENT_WOOD,
    'fire': ELEMENT_FIRE,
    'earth': ELEMENT_EARTH,
    'metal': ELEMENT_METAL,
    'water': ELEMENT_WATER,
}


def life_stage(stem: str, branch: str) -> int:
    """The stage, 1 (Birth) to 12 (Nurture), of `stem` on `branch`."""
    if stem not in STEMS:
        raise ValueError(f'Unknown stem: {stem!r}')
    if branch not in BRANCHES:
        raise ValueError(f'Unknown branch: {branch!r}')
    info = STEMS[stem]
    polarity = 1 if info['polarity'] == 'Yang' else 0
    return life_stage_anchor(
        _ELEMENT_INDEX[info['element']], polarity, _BRANCH_ORDER.index(branch) + 1
    )
