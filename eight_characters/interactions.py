"""Deterministic natal relationship presence, independent of Evolution inference.

Only the first 21 shared families are in scope: five stem combinations, six
branch combinations, six branch clashes, and four complete harmony frames.
Presence is not activation, strength, transformation, or a life prediction.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import combinations
from typing import Literal

from typing_extensions import TypedDict

from eight_characters.data import BRANCHES, STEMS, ElementName
from eight_characters.evolution.families import (
    FAMILY_BRANCH_PAIR,
    FAMILY_BRANCH_TRIPLE,
    FAMILY_STEM_PAIR,
    family_spec,
)

PILLAR_NAMES = ('year', 'month', 'day', 'hour')
InteractionKind = Literal[
    'stem_combination', 'branch_combination', 'branch_clash', 'harmony_frame'
]
Component = Literal['stem', 'branch']


class InteractionMember(TypedDict):
    pillar: str
    char: str
    pinyin: str


class Interaction(TypedDict):
    id: str
    kind: InteractionKind
    component: Component
    members: list[InteractionMember]
    adjacent: bool
    completeness: Literal['pair', 'complete']
    potential_element: ElementName | None
    transformation: Literal['not_assessed', 'not_applicable']


@dataclass(frozen=True)
class InteractionRule:
    rule_index: int
    kind: InteractionKind
    component: Component
    members: tuple[str, ...]
    potential_element: ElementName | None


_STEM_CHARS = '甲乙丙丁戊己庚辛壬癸'
_BRANCH_CHARS = '子丑寅卯辰巳午未申酉戌亥'
_ELEMENTS: tuple[ElementName, ...] = ('wood', 'fire', 'earth', 'metal', 'water')
_RULE_KINDS: tuple[InteractionKind, ...] = (
    *('stem_combination',) * 5,
    *('branch_combination',) * 6,
    *('branch_clash',) * 6,
    *('harmony_frame',) * 4,
)


def _build_rules() -> tuple[InteractionRule, ...]:
    rules: list[InteractionRule] = []
    for rule_index, kind in enumerate(_RULE_KINDS, start=1):
        spec = family_spec(rule_index)
        component: Component = 'stem' if kind == 'stem_combination' else 'branch'
        expected_category = (
            FAMILY_STEM_PAIR
            if component == 'stem'
            else FAMILY_BRANCH_TRIPLE
            if kind == 'harmony_frame'
            else FAMILY_BRANCH_PAIR
        )
        member_ids = spec.stem_members if component == 'stem' else spec.branch_members
        chars = _STEM_CHARS if component == 'stem' else _BRANCH_CHARS
        size = 3 if kind == 'harmony_frame' else 2
        if (
            spec.category != expected_category
            or len(member_ids) != size
            or len(set(member_ids)) != size
            or any(member < 1 or member > len(chars) for member in member_ids)
        ):
            raise RuntimeError(f'Invalid shared relationship family: {rule_index}')
        # Branch-pair transformation targets vary by convention; Basic does not
        # publish a target for them. Stem/frame targets are potential only.
        potential_element = None
        if kind in ('stem_combination', 'harmony_frame'):
            target = spec.target_element_index
            if target is None or not 0 <= target < len(_ELEMENTS):
                raise RuntimeError(f'Missing relationship target: {rule_index}')
            potential_element = _ELEMENTS[target]
        rules.append(
            InteractionRule(
                rule_index,
                kind,
                component,
                tuple(chars[member - 1] for member in member_ids),
                potential_element,
            )
        )
    return tuple(rules)


INTERACTION_RULES = _build_rules()


def detect_interactions(
    pillars: Mapping[str, tuple[str, str]],
) -> list[Interaction]:
    """Return all matching occurrences, ordered by rule then natal position.

    The caller supplies normalized (stem, branch) pairs. Hidden stems do not
    create additional stem combinations. Repeated pillars remain distinct;
    each complete triple contains three different required branch identities.
    """
    if set(pillars) != set(PILLAR_NAMES):
        raise ValueError('Interactions require exactly year, month, day, and hour.')
    for name in PILLAR_NAMES:
        pair = pillars[name]
        if len(pair) != 2 or pair[0] not in STEMS or pair[1] not in BRANCHES:
            raise ValueError(f'Invalid stem/branch pair for {name}: {pair!r}')

    result: list[Interaction] = []
    for rule in INTERACTION_RULES:
        component_index = 0 if rule.component == 'stem' else 1
        chars = tuple(pillars[name][component_index] for name in PILLAR_NAMES)
        for positions in combinations(range(4), len(rule.members)):
            if {chars[position] for position in positions} != set(rule.members):
                continue
            members: list[InteractionMember] = [
                {
                    'pillar': PILLAR_NAMES[position],
                    'char': chars[position],
                    'pinyin': (
                        STEMS[chars[position]]['pinyin']
                        if rule.component == 'stem'
                        else BRANCHES[chars[position]]['pinyin']
                    ),
                }
                for position in positions
            ]
            result.append(
                {
                    'id': f'{rule.kind}:{rule.rule_index}:'
                    + '-'.join(member['pillar'] for member in members),
                    'kind': rule.kind,
                    'component': rule.component,
                    'members': members,
                    'adjacent': positions[-1] - positions[0] == len(positions) - 1,
                    'completeness': 'complete' if len(positions) == 3 else 'pair',
                    'potential_element': rule.potential_element,
                    'transformation': (
                        'not_applicable'
                        if rule.kind == 'branch_clash'
                        else 'not_assessed'
                    ),
                }
            )
    return result
