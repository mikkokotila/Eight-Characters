"""All ten natal roles and visible-stem roots, with presence separate from strength."""

from collections.abc import Mapping, Sequence
from typing import Literal

from typing_extensions import TypedDict

from eight_characters.data import STEMS, ElementName
from eight_characters.natal_evidence import (
    PILLAR_NAMES,
    Identity,
    RootEvidence,
    StemEvidence,
    natal_occurrences,
    roots_for_stem,
    stem_identity,
)
from eight_characters.ten_gods import (
    DAY_MASTER,
    TEN_GOD_NAMES,
    DayMasterName,
    TenGodName,
)

RoleGroupName = Literal['companion', 'output', 'wealth', 'authority', 'resource']
Presence = Literal['visible_only', 'hidden_only', 'visible_and_hidden', 'absent']
GROUPS: tuple[tuple[RoleGroupName, tuple[TenGodName, TenGodName]], ...] = (
    ('companion', ('friend', 'rob_wealth')),
    ('output', ('eating_god', 'hurting_officer')),
    ('wealth', ('indirect_wealth', 'direct_wealth')),
    ('authority', ('seven_killings', 'direct_officer')),
    ('resource', ('indirect_resource', 'direct_resource')),
)


class RoleOccurrence(StemEvidence):
    id: str


class RoleRoot(RootEvidence):
    id: str


class RoleEntry(TypedDict):
    ten_god: TenGodName
    presence: Presence
    visible: list[RoleOccurrence]
    hidden: list[RoleOccurrence]


class RoleGroup(TypedDict):
    group: RoleGroupName
    element: ElementName
    presence: Presence
    roles: list[RoleEntry]


class VisibleStem(Identity):
    id: str
    pillar: str
    ten_god: TenGodName | DayMasterName
    roots: list[RoleRoot]
    exact_hidden_matches: list[str]


class RoleProfile(TypedDict):
    policy: Literal['natal_roles_v1']
    day_master: Identity
    groups: list[RoleGroup]
    visible_stems: list[VisibleStem]


def occurrence_id(record: StemEvidence) -> str:
    return (
        f'visible:{record["pillar"]}'
        if record['component'] == 'stem'
        else f'hidden:{record["pillar"]}:{record["char"]}'
    )


def presence(visible: bool, hidden: bool) -> Presence:
    if visible and hidden:
        return 'visible_and_hidden'
    if visible:
        return 'visible_only'
    return 'hidden_only' if hidden else 'absent'


def build_role_profile(
    pillars: Mapping[str, tuple[str, str]],
    hidden_stems: Mapping[str, Sequence[str]],
    ten_gods: Mapping[tuple[str, str], TenGodName],
) -> RoleProfile:
    """Day Master is a reference, not an additional visible Companion.

    Every hidden and non-Day-Master visible occurrence belongs to exactly one
    role. Visible-stem root records are references to those same occurrences,
    not additive quantities. Exact hidden matches require character equality;
    same-element opposite-polarity roots never qualify as exact matches.
    """
    occurrences = natal_occurrences(pillars, hidden_stems, ten_gods)
    dm = pillars['day'][0]
    elements: dict[TenGodName, ElementName] = {}
    for char in STEMS:
        god = ten_gods.get((dm, char))
        if god not in TEN_GOD_NAMES or god in elements:
            raise ValueError(f'Invalid Ten Gods row for {dm}.')
        elements[god] = STEMS[char]['element']
    groups: list[RoleGroup] = []
    for group, names in GROUPS:
        if elements[names[0]] != elements[names[1]]:
            raise ValueError(f'Role group {group} has inconsistent elements.')
        roles: list[RoleEntry] = []
        for name in names:
            visible: list[RoleOccurrence] = [
                {**record, 'id': occurrence_id(record)}
                for record in occurrences
                if record['ten_god'] == name and record['component'] == 'stem'
            ]
            hidden: list[RoleOccurrence] = [
                {**record, 'id': occurrence_id(record)}
                for record in occurrences
                if record['ten_god'] == name and record['component'] == 'hidden_stem'
            ]
            roles.append(
                {
                    'ten_god': name,
                    'presence': presence(bool(visible), bool(hidden)),
                    'visible': visible,
                    'hidden': hidden,
                }
            )
        groups.append(
            {
                'group': group,
                'element': elements[names[0]],
                'presence': presence(
                    any(r['visible'] for r in roles), any(r['hidden'] for r in roles)
                ),
                'roles': roles,
            }
        )
    visible_stems: list[VisibleStem] = []
    for pillar in PILLAR_NAMES:
        char = pillars[pillar][0]
        roots: list[RoleRoot] = [
            {**r, 'id': occurrence_id(r)} for r in roots_for_stem(char, occurrences)
        ]
        visible_stems.append(
            {
                **stem_identity(char),
                'id': f'visible:{pillar}',
                'pillar': pillar,
                'ten_god': DAY_MASTER if pillar == 'day' else ten_gods[(dm, char)],
                'roots': roots,
                'exact_hidden_matches': [
                    r['id'] for r in roots if r['match'] == 'exact_stem'
                ],
            }
        )
    return {
        'policy': 'natal_roles_v1',
        'day_master': stem_identity(dm),
        'groups': groups,
        'visible_stems': visible_stems,
    }
