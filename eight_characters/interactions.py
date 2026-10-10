"""Deterministic relationship presence, natal and with a luck pillar, independent of
Evolution inference.

Rules 1-21 are the shared family catalog's: five stem combinations, six branch
combinations, six branch clashes, and four complete harmony frames. Rules 22-44 are
Standard's own and follow the canon (canon/Taxonomy.md), where Evolution's catalog
differs from it: half-frames that hold their peak, the four directional combinations,
the three punishments with their halves, the four self-punishments, and the six harms.
Presence is not activation, strength, transformation, or a life prediction.
"""

from collections.abc import Mapping, Sequence
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
# A luck pillar's position, after the natal four (detect_luck_interactions).
LUCK = 'luck'
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


class AbsorbedInteraction(TypedDict):
    # A natal half, and the complete wholes with the luck pillar that absorb it.
    id: str
    by: list[str]


class LuckInteractions(TypedDict):
    interactions: list[Interaction]
    absorbed: list[AbsorbedInteraction]


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
# Each rule's members as a set, for matching.
_MEMBERS: dict[int, frozenset[str]] = {
    rule.rule_index: frozenset(rule.members) for rule in INTERACTION_RULES
}


def _matches(rule: InteractionRule, found: frozenset[str]) -> bool:
    """Whether the distinct characters at some positions make the rule's relationship."""
    members = _MEMBERS[rule.rule_index]
    if rule.kind in _HALVES:
        return (
            len(found) == 2
            and found <= members
            and (rule.peak is None or rule.peak in found)
        )
    return found == members


def _size(rule: InteractionRule) -> int:
    return 2 if rule.kind in _HALVES else len(rule.members)


Pair = tuple[str, str]
Found = list[tuple[InteractionRule, tuple[int, ...]]]


def _check_pair(name: str, pair: Pair) -> None:
    if len(pair) != 2 or pair[0] not in STEMS or pair[1] not in BRANCHES:
        raise ValueError(f'Invalid stem/branch pair for {name}: {pair!r}')


def _natal_pairs(pillars: Mapping[str, Pair]) -> list[Pair]:
    if set(pillars) != set(PILLAR_NAMES):
        raise ValueError('Interactions require exactly year, month, day, and hour.')
    for name in PILLAR_NAMES:
        _check_pair(name, pillars[name])
    return [pillars[name] for name in PILLAR_NAMES]


def _find(pairs: Sequence[Pair]) -> Found:
    """Every rule's matches among the positions, ordered by rule then position."""
    # Each component's characters at each pair or triple of positions, gathered once
    # for all the rules that look at them.
    groups: dict[tuple[int, int], list[tuple[tuple[int, ...], frozenset[str]]]] = {}
    found: Found = []
    for rule in INTERACTION_RULES:
        component_index = 0 if rule.component == 'stem' else 1
        size = _size(rule)
        group = groups.get((component_index, size))
        if group is None:
            group = [
                (
                    positions,
                    frozenset(
                        pairs[position][component_index] for position in positions
                    ),
                )
                for positions in combinations(range(len(pairs)), size)
            ]
            groups[(component_index, size)] = group
        found.extend(
            (rule, positions) for positions, chars in group if _matches(rule, chars)
        )
    return found


def _absorbers(
    rule: InteractionRule, positions: tuple[int, ...], found: Found
) -> Found:
    """The complete wholes of a half's own members that hold all of its positions."""
    if rule.kind not in _WHOLE_OF:
        return []
    return [
        (whole, held)
        for whole, held in found
        if whole.kind == _WHOLE_OF[rule.kind]
        and set(whole.members) == set(rule.members)
        and set(positions) <= set(held)
    ]


def _id(rule: InteractionRule, positions: tuple[int, ...], names: Sequence[str]) -> str:
    return f'{rule.kind}:{rule.rule_index}:' + '-'.join(names[p] for p in positions)


def _interaction(
    rule: InteractionRule,
    positions: tuple[int, ...],
    names: Sequence[str],
    pairs: Sequence[Pair],
    adjacent: bool,
) -> Interaction:
    component_index = 0 if rule.component == 'stem' else 1
    members: list[InteractionMember] = [
        {
            'pillar': names[position],
            'char': pairs[position][component_index],
            'pinyin': (
                STEMS[pairs[position][0]]['pinyin']
                if rule.component == 'stem'
                else BRANCHES[pairs[position][1]]['pinyin']
            ),
        }
        for position in positions
    ]
    return {
        'id': _id(rule, positions, names),
        'kind': rule.kind,
        'component': rule.component,
        'members': members,
        'adjacent': adjacent,
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
    pairs = _natal_pairs(pillars)
    found = _find(pairs)
    return [
        _interaction(
            rule,
            positions,
            PILLAR_NAMES,
            pairs,
            positions[-1] - positions[0] == len(positions) - 1,
        )
        for rule, positions in found
        if not _absorbers(rule, positions, found)
    ]


def detect_luck_interactions(
    pillars: Mapping[str, tuple[str, str]],
    luck: tuple[str, str],
    *,
    position: str = LUCK,
) -> LuckInteractions:
    """The relationships a luck pillar forms with the natal chart.

    The luck pillar is a fifth position after the natal four, under the same rules,
    and it counts as adjacent to every natal pillar: a relationship it takes part in
    is adjacent when its natal members are. Listed are the relationships the luck
    pillar takes part in, ordered by rule then position, and the natal halves that a
    complete whole with the luck pillar absorbs. A half a natal whole already
    absorbs is not a natal finding, so the luck pillar cannot absorb it.

    Another pillar read the same way, such as a year's, takes the fifth place under
    its own `position` name.
    """
    if position in PILLAR_NAMES:
        raise ValueError(f'The fifth position cannot be named {position!r}.')
    pairs = _natal_pairs(pillars)
    _check_pair(position, luck)
    pairs.append(luck)
    names = (*PILLAR_NAMES, position)
    at = len(PILLAR_NAMES)
    found = _find(pairs)
    interactions: list[Interaction] = []
    absorbed: list[AbsorbedInteraction] = []
    for rule, positions in found:
        absorbers = _absorbers(rule, positions, found)
        if at in positions:
            if not absorbers:
                natal = [position for position in positions if position != at]
                interactions.append(
                    _interaction(
                        rule,
                        positions,
                        names,
                        pairs,
                        natal[-1] - natal[0] == len(natal) - 1,
                    )
                )
        elif absorbers and all(at in held for _, held in absorbers):
            absorbed.append(
                {
                    'id': _id(rule, positions, names),
                    'by': [_id(whole, held, names) for whole, held in absorbers],
                }
            )
    return {'interactions': interactions, 'absorbed': absorbed}


def branch_ties(first: str, second: str) -> list[InteractionKind]:
    """The kinds of relationship two branches form between themselves, in the
    catalogue's order: its pairs, the halves of its triples, and a self-punishment
    when the two are one branch that punishes itself."""
    for branch in (first, second):
        if branch not in BRANCHES:
            raise ValueError(f'Invalid branch: {branch!r}')
    found = frozenset((first, second))
    return [
        rule.kind
        for rule in INTERACTION_RULES
        if rule.component == 'branch' and _size(rule) == 2 and _matches(rule, found)
    ]
