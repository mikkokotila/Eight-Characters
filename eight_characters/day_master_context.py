"""Natal Day Master evidence, not an overall strength or favorability score.

Roots are same-element hidden stems, with exact-stem matches distinguished.
Resource is support, not a root. The Day Master itself is not a companion.
Season is a coarse traditional month-branch group, not local weather or a
within-month governing-qi assessment. Nothing here applies transformations.
"""

from collections.abc import Mapping, Sequence
from typing import Literal

from typing_extensions import TypedDict

from eight_characters.data import BRANCHES, ElementName
from eight_characters.natal_evidence import (
    Identity,
    RootEvidence,
    StemEvidence,
    natal_occurrences,
    roots_for_stem,
    stem_identity,
)
from eight_characters.ten_gods import TenGodName

SeasonName = Literal['spring', 'summer', 'autumn', 'winter']
SEASON_GROUPS: tuple[tuple[str, SeasonName, ElementName], ...] = (
    ('寅卯辰', 'spring', 'wood'),
    ('巳午未', 'summer', 'fire'),
    ('申酉戌', 'autumn', 'metal'),
    ('亥子丑', 'winter', 'water'),
)
_SEASON_BY_BRANCH: dict[str, tuple[SeasonName, ElementName]] = {
    char: (name, element) for chars, name, element in SEASON_GROUPS for char in chars
}


class SeasonalContext(TypedDict):
    basis: Literal['traditional_month_branch_groups']
    name: SeasonName
    element: ElementName
    month_branch: Identity
    hidden_stems: list[StemEvidence]


class SupportEvidence(TypedDict):
    companions: list[StemEvidence]
    resources: list[StemEvidence]


class DayMasterContext(TypedDict):
    policy: Literal['natal_presence_v1']
    day_master: Identity
    season: SeasonalContext
    roots: list[RootEvidence]
    support: SupportEvidence


def build_day_master_context(
    pillars: Mapping[str, tuple[str, str]],
    hidden_stems: Mapping[str, Sequence[str]],
    ten_gods: Mapping[tuple[str, str], TenGodName],
) -> DayMasterContext:
    """Describe normalized pillars using the existing validated mapping sources.

    Records are chronological (year, month, day, hour), visible before hidden,
    with hidden stems in mapping qi order. Repeated branches remain separate.
    Presence is preserved even when a relationship also involves the branch.
    """
    occurrences = natal_occurrences(pillars, hidden_stems, ten_gods)
    day_master = pillars['day'][0]
    roots = roots_for_stem(day_master, occurrences)
    month_hidden = [
        record.copy()
        for record in occurrences
        if record['pillar'] == 'month' and record['component'] == 'hidden_stem'
    ]
    companions = [
        record.copy()
        for record in occurrences
        if record['ten_god'] in ('friend', 'rob_wealth')
    ]
    resources = [
        record.copy()
        for record in occurrences
        if record['ten_god'] in ('direct_resource', 'indirect_resource')
    ]

    month_branch = pillars['month'][1]
    branch_info = BRANCHES[month_branch]
    season_name, season_element = _SEASON_BY_BRANCH[month_branch]
    return {
        'policy': 'natal_presence_v1',
        'day_master': stem_identity(day_master),
        'season': {
            'basis': 'traditional_month_branch_groups',
            'name': season_name,
            'element': season_element,
            'month_branch': {
                'char': month_branch,
                'pinyin': branch_info['pinyin'],
                'element': branch_info['element'],
                'polarity': branch_info['polarity'],
            },
            'hidden_stems': month_hidden,
        },
        'roots': roots,
        'support': {'companions': companions, 'resources': resources},
    }
