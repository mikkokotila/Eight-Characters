"""What each luck pillar brings to a natal chart, phase by phase.

San Ming Tong Hui, volume 2, 'On Major Cycles': while a luck period is on its stem,
its branch is used as well; while it is on its branch, the stem is set aside. A
cycle's stem phase is its first five years and its branch phase its last five
(luck_pillars). So the luck stem, and the relationships it forms, act in the stem
phase; the luck branch, its hidden stems, the Day Master's stage on it, and the
relationships it forms, act in both. The luck pillar counts as adjacent to every
natal pillar (interactions.detect_luck_interactions).

Presence and counts only: nothing here weighs strength, applies a transformation or
predicts. Ten Gods stay relative to the natal Day Master. A count is one for each
character, or each stem occurrence, with no weights.
"""

from collections.abc import Mapping, Sequence
from typing import Literal

from typing_extensions import TypedDict

from eight_characters.data import BRANCHES, STEMS, ElementName
from eight_characters.interactions import (
    LUCK,
    AbsorbedInteraction,
    Component,
    Interaction,
    detect_luck_interactions,
)
from eight_characters.life_stages import life_stage
from eight_characters.luck_pillars import LuckPillar, PhaseName
from eight_characters.natal_evidence import (
    PILLAR_NAMES,
    QI_TYPES,
    RootEvidence,
    StemEvidence,
    natal_occurrences,
    roots_for_stem,
    stem_identity,
)
from eight_characters.ten_gods import TEN_GOD_NAMES, TenGodName

PHASES: tuple[PhaseName, ...] = ('stem', 'branch')
ELEMENTS: tuple[ElementName, ...] = ('wood', 'fire', 'earth', 'metal', 'water')
# The phases in which a luck pillar's stem, or its branch, acts.
ACTS_IN: dict[Component, list[PhaseName]] = {
    'stem': ['stem'],
    'branch': ['stem', 'branch'],
}


class LuckOccurrence(StemEvidence):
    # Whether the natal chart holds no occurrence of this Ten God at all.
    new_to_chart: bool
    phases: list[PhaseName]


class LuckRoot(RootEvidence):
    phases: list[PhaseName]


class LuckInteraction(Interaction):
    phases: list[PhaseName]


class LuckAbsorbed(AbsorbedInteraction):
    phases: list[PhaseName]


class Counts(TypedDict):
    # Each visible character by its own element: eight natal, nine or ten with luck.
    elements: dict[ElementName, int]
    # Each occurrence by its Ten God: every non-Day-Master visible stem and every
    # hidden stem.
    ten_gods: dict[TenGodName, int]


class DecadeContext(TypedDict):
    sequence: int
    # The luck stem, then the hidden stems of the luck branch.
    occurrences: list[LuckOccurrence]
    day_master_stage: int
    roots: list[LuckRoot]
    interactions: list[LuckInteraction]
    absorbed: list[LuckAbsorbed]
    counts: dict[PhaseName, Counts]


class LuckContext(TypedDict):
    policy: Literal['luck_context_v1']
    natal_counts: Counts
    decades: list[DecadeContext]


def _counts(
    elements: Sequence[ElementName], occurrences: Sequence[StemEvidence]
) -> Counts:
    by_element = dict.fromkeys(ELEMENTS, 0)
    for element in elements:
        by_element[element] += 1
    by_ten_god = dict.fromkeys(TEN_GOD_NAMES, 0)
    for record in occurrences:
        by_ten_god[record['ten_god']] += 1
    return {'elements': by_element, 'ten_gods': by_ten_god}


def _decade(
    pillars: Mapping[str, tuple[str, str]],
    luck: LuckPillar,
    hidden_stems: Mapping[str, Sequence[str]],
    ten_gods: Mapping[tuple[str, str], TenGodName],
    natal: Sequence[StemEvidence],
    natal_elements: Sequence[ElementName],
    position: str,
) -> DecadeContext:
    stem, branch = luck['stem']['chinese'], luck['branch']['chinese']
    if STEMS.get(stem) is None or BRANCHES.get(branch) is None:
        raise ValueError(f'Invalid luck pillar: {stem}{branch}')
    day_master = pillars['day'][0]
    present = {record['ten_god'] for record in natal}

    def evidence(char: str, qi: int | None) -> StemEvidence:
        god = ten_gods.get((day_master, char))
        if god not in TEN_GOD_NAMES:
            raise ValueError(f'Missing or invalid ten god for {day_master}/{char}.')
        return {
            **stem_identity(char),
            'pillar': position,
            'component': 'stem' if qi is None else 'hidden_stem',
            'branch': None if qi is None else branch,
            'qi_type': None if qi is None else QI_TYPES[qi],
            'ten_god': god,
        }

    hidden = hidden_stems.get(branch)
    if (
        hidden is None
        or not 1 <= len(hidden) <= len(QI_TYPES)
        or len(set(hidden)) != len(hidden)
        or any(char not in STEMS for char in hidden)
    ):
        raise ValueError(f'Invalid hidden-stem mapping for {branch}.')
    visible = evidence(stem, None)
    hidden_records = [evidence(char, qi) for qi, char in enumerate(hidden)]
    occurrences: list[LuckOccurrence] = [
        {
            **record,
            'new_to_chart': record['ten_god'] not in present,
            'phases': list(
                ACTS_IN['stem' if record['component'] == 'stem' else 'branch']
            ),
        }
        for record in (visible, *hidden_records)
    ]
    found = detect_luck_interactions(pillars, (stem, branch), position=position)
    interactions: list[LuckInteraction] = [
        {**relationship, 'phases': list(ACTS_IN[relationship['component']])}
        for relationship in found['interactions']
    ]
    phases_of = {
        relationship['id']: relationship['phases'] for relationship in interactions
    }
    absorbed: list[LuckAbsorbed] = []
    for half in found['absorbed']:
        missing = [whole for whole in half['by'] if whole not in phases_of]
        if missing:
            raise RuntimeError(
                f'{half["id"]} is absorbed by unlisted wholes: {missing}'
            )
        absorbed.append(
            {
                **half,
                'phases': [
                    phase
                    for phase in PHASES
                    if any(phase in phases_of[whole] for whole in half['by'])
                ],
            }
        )
    stem_element = STEMS[stem]['element']
    branch_element = BRANCHES[branch]['element']
    return {
        'sequence': luck['sequence'],
        'occurrences': occurrences,
        'day_master_stage': life_stage(day_master, branch),
        'roots': [
            {**root, 'phases': list(ACTS_IN['branch'])}
            for root in roots_for_stem(day_master, hidden_records)
        ],
        'interactions': interactions,
        'absorbed': absorbed,
        'counts': {
            'stem': _counts(
                [*natal_elements, stem_element, branch_element],
                [*natal, visible, *hidden_records],
            ),
            'branch': _counts(
                [*natal_elements, branch_element], [*natal, *hidden_records]
            ),
        },
    }


def build_luck_context(
    pillars: Mapping[str, tuple[str, str]],
    luck_pillars: Sequence[LuckPillar],
    hidden_stems: Mapping[str, Sequence[str]],
    ten_gods: Mapping[tuple[str, str], TenGodName],
    *,
    position: str = LUCK,
) -> LuckContext:
    """Every decade's luck context, in the luck pillars' order. Another pillar read
    as a luck pillar is, such as a year's, takes the fifth place under its own
    `position` name (interactions.detect_luck_interactions)."""
    natal = natal_occurrences(pillars, hidden_stems, ten_gods)
    natal_elements: list[ElementName] = [
        *(STEMS[pillars[name][0]]['element'] for name in PILLAR_NAMES),
        *(BRANCHES[pillars[name][1]]['element'] for name in PILLAR_NAMES),
    ]
    return {
        'policy': 'luck_context_v1',
        'natal_counts': _counts(natal_elements, natal),
        'decades': [
            _decade(
                pillars, luck, hidden_stems, ten_gods, natal, natal_elements, position
            )
            for luck in luck_pillars
        ],
    }
