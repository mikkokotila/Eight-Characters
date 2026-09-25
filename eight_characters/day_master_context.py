"""Natal Day Master evidence, not an overall strength or favorability score.

Roots are same-element hidden stems, with exact-stem matches distinguished.
Resource is support, not a root. The Day Master itself is not a companion.
Season is a coarse traditional month-branch group, not local weather or a
within-month governing-qi assessment. Nothing here applies transformations.
"""

from collections.abc import Mapping, Sequence
from typing import Literal

from typing_extensions import TypedDict

from eight_characters.data import BRANCHES, STEMS, ElementName, PolarityName
from eight_characters.ten_gods import TEN_GOD_NAMES, TenGodName

PILLAR_NAMES = ('year', 'month', 'day', 'hour')
QiType = Literal['main', 'middle', 'residual']
SeasonName = Literal['spring', 'summer', 'autumn', 'winter']
QI_TYPES: tuple[QiType, ...] = ('main', 'middle', 'residual')
SEASON_GROUPS: tuple[tuple[str, SeasonName, ElementName], ...] = (
    ('寅卯辰', 'spring', 'wood'),
    ('巳午未', 'summer', 'fire'),
    ('申酉戌', 'autumn', 'metal'),
    ('亥子丑', 'winter', 'water'),
)
_SEASON_BY_BRANCH: dict[str, tuple[SeasonName, ElementName]] = {
    char: (name, element) for chars, name, element in SEASON_GROUPS for char in chars
}


class Identity(TypedDict):
    char: str
    pinyin: str
    element: ElementName
    polarity: PolarityName


class StemEvidence(Identity):
    pillar: str
    component: Literal['stem', 'hidden_stem']
    branch: str | None
    qi_type: QiType | None
    ten_god: TenGodName


class RootEvidence(StemEvidence):
    match: Literal['exact_stem', 'opposite_polarity']


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


def _stem_identity(char: str) -> Identity:
    info = STEMS[char]
    return {
        'char': char,
        'pinyin': info['pinyin'],
        'element': info['element'],
        'polarity': info['polarity'],
    }


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
    if set(pillars) != set(PILLAR_NAMES):
        raise ValueError('Day Master context requires exactly four named pillars.')
    for name in PILLAR_NAMES:
        pair = pillars[name]
        if len(pair) != 2 or pair[0] not in STEMS or pair[1] not in BRANCHES:
            raise ValueError(f'Invalid stem/branch pair for {name}: {pair!r}')
        chars = hidden_stems.get(pair[1])
        if (
            chars is None
            or not 1 <= len(chars) <= len(QI_TYPES)
            or len(set(chars)) != len(chars)
            or any(char not in STEMS for char in chars)
        ):
            raise ValueError(f'Invalid hidden-stem mapping for {pair[1]}.')

    day_master = pillars['day'][0]
    dm_element = STEMS[day_master]['element']
    roots: list[RootEvidence] = []
    companions: list[StemEvidence] = []
    resources: list[StemEvidence] = []
    month_hidden: list[StemEvidence] = []

    for name in PILLAR_NAMES:
        stem, branch = pillars[name]
        # Exclude the Day Master, but retain same-stem occurrences elsewhere.
        occurrences: list[tuple[str, QiType | None]] = (
            [(stem, None)] if name != 'day' else []
        )
        occurrences.extend(zip(hidden_stems[branch], QI_TYPES))
        for char, qi_type in occurrences:
            ten_god = ten_gods.get((day_master, char))
            if ten_god not in TEN_GOD_NAMES:
                raise ValueError(f'Missing or invalid ten god for {day_master}/{char}.')
            evidence: StemEvidence = {
                **_stem_identity(char),
                'pillar': name,
                'component': 'stem' if qi_type is None else 'hidden_stem',
                'branch': None if qi_type is None else branch,
                'qi_type': qi_type,
                'ten_god': ten_god,
            }
            if qi_type is not None:
                if name == 'month':
                    month_hidden.append(evidence.copy())
                if evidence['element'] == dm_element:
                    roots.append(
                        {
                            **evidence,
                            'match': 'exact_stem'
                            if char == day_master
                            else 'opposite_polarity',
                        }
                    )
            if ten_god in ('friend', 'rob_wealth'):
                companions.append(evidence.copy())
            elif ten_god in ('direct_resource', 'indirect_resource'):
                resources.append(evidence.copy())

    month_branch = pillars['month'][1]
    branch_info = BRANCHES[month_branch]
    season_name, season_element = _SEASON_BY_BRANCH[month_branch]
    return {
        'policy': 'natal_presence_v1',
        'day_master': _stem_identity(day_master),
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
