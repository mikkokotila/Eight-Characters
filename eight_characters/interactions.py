"""Deterministic natal relationship presence, independent of Evolution inference.

Rules 1-21 are the shared family catalog's: five stem combinations, six branch
combinations, six branch clashes, and four complete harmony frames. Rules 22-44 are
Standard's own and follow the canon (canon/Taxonomy.md), where Evolution's catalog
differs from it: half-frames that hold their peak, the four directional combinations,
the three punishments with their halves, the four self-punishments, and the six harms.
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
    'stem_combination',
    'branch_combination',
    'branch_clash',
    'harmony_frame',
    'half_frame',
    'directional_combination',
    'punishment',
    'half_punishment',
    'self_punishment',
    'harm',
]
Component = Literal['stem', 'branch']
# A pair is a two-member relationship; complete, all three members of a triple; half,
# two of a triple's three.
Completeness = Literal['pair', 'half', 'complete']
Transformation = Literal['not_assessed', 'not_applicable']


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
    completeness: Completeness
    potential_element: ElementName | None
    transformation: Transformation


@dataclass(frozen=True)
class InteractionRule:
    rule_index: int
    kind: InteractionKind
    component: Component
    # The characters the relationship needs. A half holds two of these three; a
    # self-punishment, the same branch twice.
    members: tuple[str, ...]
    potential_element: ElementName | None
    # The member a half must hold: a half-frame's peak. None for a half-punishment,
    # whose any two members make it.
    peak: str | None = None


_STEM_CHARS = '甲乙丙丁戊己庚辛壬癸'
_BRANCH_CHARS = '子丑寅卯辰巳午未申酉戌亥'
_ELEMENTS: tuple[ElementName, ...] = ('wood', 'fire', 'earth', 'metal', 'water')
_RULE_GROUPS: tuple[tuple[InteractionKind, int], ...] = (
    ('stem_combination', 5),
    ('branch_combination', 6),
    ('branch_clash', 6),
    ('harmony_frame', 4),
)
_RULE_KINDS: tuple[InteractionKind, ...] = tuple(
    kind for kind, count in _RULE_GROUPS for _ in range(count)
)
_COMBINING: frozenset[InteractionKind] = frozenset(
    (
        'stem_combination',
        'branch_combination',
        'harmony_frame',
        'half_frame',
        'directional_combination',
    )
)
_HALVES: frozenset[InteractionKind] = frozenset(('half_frame', 'half_punishment'))
# A half's complete form, which absorbs the halves among its own members.
_WHOLE_OF: dict[InteractionKind, InteractionKind] = {
    'half_frame': 'harmony_frame',
    'half_punishment': 'punishment',
}

# The canon's families Standard reads beyond the shared catalog, in the canon's order.
# Each frame's peak is the branch a half-frame must hold (the canon: "one of them the
# Peak Branch").
CANON_HALF_FRAMES: tuple[tuple[str, str], ...] = (
    ('申子辰', '子'),
    ('亥卯未', '卯'),
    ('寅午戌', '午'),
    ('巳酉丑', '酉'),
)
CANON_DIRECTIONAL: tuple[tuple[str, ElementName], ...] = (
    ('亥子丑', 'water'),
    ('寅卯辰', 'wood'),
    ('巳午未', 'fire'),
    ('申酉戌', 'metal'),
)
CANON_PUNISHMENT_TRIANGLES = ('寅巳申', '丑未戌')
CANON_PUNISHMENT_PAIR = '子卯'
CANON_SELF_PUNISHMENTS = '辰午酉亥'
CANON_HARMS = ('子未', '丑午', '寅巳', '卯辰', '申亥', '酉戌')


def _shared_rules() -> list[InteractionRule]:
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
    return rules


def _canon_rules(frames: list[InteractionRule]) -> list[InteractionRule]:
    """Rules 22-44. Each half-frame is a shared frame's members with its peak."""
    rules: list[InteractionRule] = []

    def add(
        kind: InteractionKind,
        members: str,
        potential_element: ElementName | None = None,
        peak: str | None = None,
    ) -> None:
        rules.append(
            InteractionRule(
                22 + len(rules),
                kind,
                'branch',
                tuple(members),
                potential_element,
                peak,
            )
        )

    if len(frames) != len(CANON_HALF_FRAMES):
        raise RuntimeError('Half-frames do not match the shared frames.')
    for frame, (members, peak) in zip(frames, CANON_HALF_FRAMES, strict=True):
        if set(frame.members) != set(members) or peak not in members:
            raise RuntimeError(f'Half-frame {members} does not match its frame.')
        add('half_frame', members, frame.potential_element, peak)
    for members, element in CANON_DIRECTIONAL:
        add('directional_combination', members, element)
    for members in CANON_PUNISHMENT_TRIANGLES:
        add('punishment', members)
    for members in CANON_PUNISHMENT_TRIANGLES:
        add('half_punishment', members)
    add('punishment', CANON_PUNISHMENT_PAIR)
    for branch in CANON_SELF_PUNISHMENTS:
        add('self_punishment', branch * 2)
    for members in CANON_HARMS:
        add('harm', members)
    for rule in rules:
        if any(member not in _BRANCH_CHARS for member in rule.members):
            raise RuntimeError(f'Invalid relationship rule: {rule.rule_index}')
    return rules


def _build_rules() -> tuple[InteractionRule, ...]:
    shared = _shared_rules()
    frames = [rule for rule in shared if rule.kind == 'harmony_frame']
    return (*shared, *_canon_rules(frames))


INTERACTION_RULES = _build_rules()


def _matches(rule: InteractionRule, chars: tuple[str, ...]) -> bool:
    found = set(chars)
    if rule.kind in _HALVES:
        return (
            len(found) == 2
            and found <= set(rule.members)
            and (rule.peak is None or rule.peak in found)
        )
    return found == set(rule.members)


def _size(rule: InteractionRule) -> int:
    return 2 if rule.kind in _HALVES else len(rule.members)


def detect_interactions(
    pillars: Mapping[str, tuple[str, str]],
) -> list[Interaction]:
    """Return all matching occurrences, ordered by rule then natal position.

    The caller supplies normalized (stem, branch) pairs. Hidden stems do not
    create additional stem combinations. Repeated pillars remain distinct;
    each complete triple contains three different required branch identities.
    A complete frame or punishment triangle absorbs the halves of its own kind
    among its own members.
    """
    if set(pillars) != set(PILLAR_NAMES):
        raise ValueError('Interactions require exactly year, month, day, and hour.')
    for name in PILLAR_NAMES:
        pair = pillars[name]
        if len(pair) != 2 or pair[0] not in STEMS or pair[1] not in BRANCHES:
            raise ValueError(f'Invalid stem/branch pair for {name}: {pair!r}')

    found: list[tuple[InteractionRule, tuple[int, ...]]] = []
    for rule in INTERACTION_RULES:
        component_index = 0 if rule.component == 'stem' else 1
        chars = tuple(pillars[name][component_index] for name in PILLAR_NAMES)
        for positions in combinations(range(4), _size(rule)):
            if _matches(rule, tuple(chars[position] for position in positions)):
                found.append((rule, positions))
    wholes = [
        (rule.kind, set(rule.members), set(positions))
        for rule, positions in found
        if rule.kind in _WHOLE_OF.values()
    ]
    result: list[Interaction] = []
    for rule, positions in found:
        if rule.kind in _WHOLE_OF and any(
            kind == _WHOLE_OF[rule.kind]
            and members == set(rule.members)
            and set(positions) <= held
            for kind, members, held in wholes
        ):
            continue
        component_index = 0 if rule.component == 'stem' else 1
        members: list[InteractionMember] = [
            {
                'pillar': PILLAR_NAMES[position],
                'char': pillars[PILLAR_NAMES[position]][component_index],
                'pinyin': (
                    STEMS[pillars[PILLAR_NAMES[position]][0]]['pinyin']
                    if rule.component == 'stem'
                    else BRANCHES[pillars[PILLAR_NAMES[position]][1]]['pinyin']
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
                'completeness': (
                    'half'
                    if rule.kind in _HALVES
                    else 'complete'
                    if len(positions) == 3
                    else 'pair'
                ),
                'potential_element': rule.potential_element,
                'transformation': (
                    'not_assessed' if rule.kind in _COMBINING else 'not_applicable'
                ),
            }
        )
    return result
