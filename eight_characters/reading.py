"""What the canon's taxonomy says of one natal chart, passage by passage.

Every passage is the canon's own words (canon.py), chosen by the chart: the Day
Master, the Ten God of each stem, the branch in each pillar, the Day Master on each
branch, the life stages, and the relationships the engine detects. Nothing here
writes, shortens or rephrases a passage, and nothing assesses strength or predicts.

The canon speaks in English; the reading is English only.
"""

import re
from collections.abc import Mapping, Sequence
from typing import Literal

from typing_extensions import TypedDict

from eight_characters.canon import (
    PAIRINGS,
    PILLARS,
    STEM_CHARS,
    Canon,
    CanonError,
    Entry,
    Family,
    Paragraph,
)
from eight_characters.day_master_context import SEASON_GROUPS, SeasonName
from eight_characters.interactions import Interaction
from eight_characters.life_stages import life_stage
from eight_characters.ten_gods import TEN_GOD_NAMES, TenGodName

POLICY = 'canon_taxonomy_v1'

# Six stem-on-branch passages end with a sentence that holds only when the pairing is
# the Day Pillar. Outside the Day Pillar the reading leaves it out. The list is
# explicit and checked against the canon, word for word, when the canon loads.
DAY_PILLAR_ONLY: dict[str, str] = {
    '甲午': 'As a Day Pillar, the self is bound to the ground that is consuming it.',
    '丁亥': 'As a Day Pillar, the self is bound to what it sits on.',
    '戊子': 'As a Day Pillar, the self is bound to what it sits on, and the spouse palace is held tightly, sometimes too tightly.',
    '辛巳': 'As a Day Pillar, the self is bound to what it sits on — the gem bound to the fire, dangerous and magnetic.',
    '壬午': 'As a Day Pillar, the self is bound to what it sits on — wealth and the spouse palace held by attraction rather than control.',
    '癸巳': 'As a Day Pillar, the self is bound to what it sits on.',
}

# The one relationship whose entry states what the season decides: the Zi-Wu clash.
# Spring and autumn are its neutral seasons. Checked against the canon when it loads.
SEASON_SENTENCES: dict[str, dict[SeasonName, str]] = {
    '子午': {
        'summer': 'The seasonal question matters enormously: in summer, the clash favors Fire (Wu overwhelms Zi).',
        'winter': 'In winter, the clash favors Water (Zi extinguishes Wu).',
        'spring': 'In neutral seasons, the clash is a genuine standoff, and the disruption affects both domains equally.',
        'autumn': 'In neutral seasons, the clash is a genuine standoff, and the disruption affects both domains equally.',
    },
}

# How each stem combination names its Day Master in the canon's labels.
_COMBINATION_NAME: dict[str, str] = {
    '甲': 'Jia',
    '乙': 'Yi',
    '丙': 'Bing',
    '丁': 'Ding',
    '戊': 'Wu',
    '己': 'Ji',
    '庚': 'Geng',
    '辛': 'Xin',
    '壬': 'Ren',
    '癸': 'Gui',
}
_PARTNER = {'甲': '己', '乙': '庚', '丙': '辛', '丁': '壬', '戊': '癸'}
_PARTNER.update({b: a for a, b in list(_PARTNER.items())})

_SEASON_BY_BRANCH: dict[str, SeasonName] = {
    char: name for chars, name, _ in SEASON_GROUPS for char in chars
}
RelationshipKind = Literal[
    'stem_combination', 'branch_combination', 'branch_clash', 'harmony_frame'
]


def _family(canon: Canon, kind: RelationshipKind) -> Family:
    if kind == 'stem_combination':
        return canon['stem_combinations']
    if kind == 'branch_combination':
        return canon['six_harmonies']
    if kind == 'branch_clash':
        return canon['clashes']
    return canon['three_harmonies']


class StageReading(TypedDict):
    stage: int
    name: str
    chinese: str
    paragraphs: list[Paragraph]


class StemReading(TypedDict):
    kind: Literal['day_master', 'ten_god']
    ten_god: TenGodName | None
    paragraphs: list[Paragraph]


class PillarReading(TypedDict):
    stem: str
    branch: str
    # The Day Master in this pillar.
    lens: list[Paragraph]
    # Who stands on the stem, for the Day Master; on the Day, the Day Master itself.
    stem_reading: StemReading
    # How the pillar's own stem fares on its branch: its stage's core passage, which
    # speaks of "the element" from no one's seat. None on the Day.
    own_stage: StageReading | None
    # The branch in this pillar, and the branch itself.
    ground: list[Paragraph]
    ground_about: list[Paragraph]
    # The Day Master on this branch; on the Day, its seat.
    meets: list[Paragraph]
    # The Day Master's stage on this branch, in this pillar.
    stage: StageReading


class RoleReading(TypedDict):
    # The canon's heading for the role, e.g. 'The Equal (Companion)', and its relation.
    name: str
    relation: str
    core: list[Paragraph]
    # What it means on each visible stem where it stands, by pillar.
    stems: dict[str, list[Paragraph]]


class Condition(TypedDict):
    season: SeasonName
    sentence: str


class RelationshipReading(TypedDict):
    kind: RelationshipKind
    # What a relationship of this kind is.
    introduction: list[Paragraph]
    # What this pillar pairing means; the label keeps the canon's words about distance.
    pairing: Paragraph | None
    entry: Entry
    # For a stem combination: with the Day Master, or between two other stems.
    with_day_master: Paragraph | None
    neither_day_master: Paragraph | None
    dynamic: Paragraph | None
    mechanics: list[Paragraph]
    # What the chart already decides in the entry's own words, e.g. the season.
    condition: Condition | None


class RingStage(TypedDict):
    stage: int
    branch: str
    name: str
    chinese: str


class CycleReading(TypedDict):
    # The Day Master's stage on each branch of the chart.
    stages: dict[str, int]
    # The Day Master's twelve stages in order, each with its branch, for the ring.
    ring: list[RingStage]
    introduction: list[Paragraph]
    mapping_introduction: list[Paragraph]
    narrative: list[Paragraph]
    reconception: list[Paragraph]


class DayMasterReading(TypedDict):
    stem: str
    title: str
    introduction: list[Paragraph]
    core: list[Paragraph]
    grounds_introduction: list[Paragraph]
    grounds: list[Paragraph]
    cycle: CycleReading


class Reading(TypedDict):
    policy: Literal['canon_taxonomy_v1']
    language: Literal['en']
    day_master: DayMasterReading
    pillars: dict[str, PillarReading]
    roles_introduction: list[Paragraph]
    roles: dict[TenGodName, RoleReading]
    branches_introduction: list[Paragraph]
    relationships: dict[str, RelationshipReading]


def _plain(texts: Sequence[str]) -> list[Paragraph]:
    return [{'label': None, 'text': text} for text in texts]


def _sentences(text: str) -> list[str]:
    return re.split(r'(?<=[.!?])\s+', text)


def check_reading_canon(canon: Canon) -> None:
    """The canon holds every sentence and label the reading relies on; else it raises."""
    grounds = canon['stems_on_branches']
    for pair, sentence in DAY_PILLAR_ONLY.items():
        if sentence not in _sentences(grounds[pair[0]]['branches'][pair[1]]):
            raise CanonError(
                f'the Day-Pillar sentence of {pair} is no longer in the canon'
            )
    for key, by_season in SEASON_SENTENCES.items():
        entry = canon['clashes']['entries'][key]
        said = [s for p in entry['paragraphs'] for s in _sentences(p['text'])]
        for sentence in by_season.values():
            if sentence not in said:
                raise CanonError(
                    f'the season sentence of the {key} clash is no longer in the canon'
                )
    for pair, entry in canon['stem_combinations']['entries'].items():
        labels = [p['label'] for p in entry['paragraphs'] if p['label'] is not None]
        expected = [
            f'When {_COMBINATION_NAME[pair[0]]} is the Day Master combining with {_COMBINATION_NAME[pair[1]]}',
            f'When {_COMBINATION_NAME[pair[1]]} is the Day Master combining with {_COMBINATION_NAME[pair[0]]}',
            'The relational dynamic',
            'When neither Stem is the Day Master',
        ]
        if labels != expected:
            raise CanonError(
                f'the {pair} combination has labels {labels!r}, expected {expected!r}'
            )
    table = canon['cycle']['table']
    for stem in STEM_CHARS:
        for branch, stage in table[stem].items():
            if life_stage(stem, branch) != stage:
                raise CanonError(
                    f'the canon puts {stem} on {branch} at stage {stage}, the engine does not'
                )


def _labelled(entry: Entry, label: str) -> Paragraph:
    found = [p for p in entry['paragraphs'] if p['label'] == label]
    if len(found) != 1:
        raise CanonError(f'{entry["title"]}: expected one paragraph labelled {label!r}')
    return found[0]


def _stage_reading(
    canon: Canon, stage: int, paragraphs: list[Paragraph]
) -> StageReading:
    info = canon['stages'][stage]
    return {
        'stage': stage,
        'name': info['name'],
        'chinese': info['chinese'],
        'paragraphs': paragraphs,
    }


def _pairing(members: Sequence[str]) -> str:
    ordered = sorted(members, key=PILLARS.index)
    label = f'{ordered[0].title()}–{ordered[1].title()}'
    if label not in PAIRINGS:
        raise ValueError(f'No pillar pairing {label!r}')
    return label


def _relationship(
    canon: Canon,
    interaction: Interaction,
    pillars: Mapping[str, tuple[str, str]],
    season: SeasonName,
) -> RelationshipReading:
    kind = interaction['kind']
    family = _family(canon, kind)
    chars = [member['char'] for member in interaction['members']]
    size = 3 if kind == 'harmony_frame' else 2
    matching = [
        key for key in family['entries'] if len(key) == size and set(key) == set(chars)
    ]
    if len(matching) != 1:
        raise CanonError(
            f'no single canon entry for the relationship {interaction["id"]}'
        )
    key = matching[0]
    entry = family['entries'][key]
    member_pillars = [member['pillar'] for member in interaction['members']]
    pairing = family['pairings'][_pairing(member_pillars)] if size == 2 else None
    with_dm = neither = dynamic = None
    mechanics: list[Paragraph] = []
    if kind == 'stem_combination':
        day_master = pillars['day'][0]
        if 'day' in member_pillars:
            other = _PARTNER[day_master]
            with_dm = _labelled(
                entry,
                f'When {_COMBINATION_NAME[day_master]} is the Day Master combining with {_COMBINATION_NAME[other]}',
            )
        else:
            neither = _labelled(entry, 'When neither Stem is the Day Master')
        dynamic = _labelled(entry, 'The relational dynamic')
        mechanics = canon['combination_mechanics']
    by_season = SEASON_SENTENCES.get(key) if kind == 'branch_clash' else None
    condition: Condition | None = (
        {'season': season, 'sentence': by_season[season]} if by_season else None
    )
    lead: list[Paragraph] = [
        p
        for p in entry['paragraphs']
        if kind != 'stem_combination' or p['label'] is None
    ]
    return {
        'kind': kind,
        'introduction': family['introduction'],
        'pairing': pairing,
        'entry': {'title': entry['title'], 'paragraphs': lead},
        'with_day_master': with_dm,
        'neither_day_master': neither,
        'dynamic': dynamic,
        'mechanics': mechanics,
        'condition': condition,
    }


def build_reading(
    canon: Canon,
    pillars: Mapping[str, tuple[str, str]],
    ten_gods: Mapping[tuple[str, str], TenGodName],
    interactions: Sequence[Interaction],
) -> Reading:
    """The canon's passages for this chart, by the pages that show them."""
    if set(pillars) != set(PILLARS):
        raise ValueError('A reading requires exactly year, month, day, and hour.')
    day_master = pillars['day'][0]
    if day_master not in STEM_CHARS:
        raise ValueError(f'Invalid Day Master: {day_master!r}')
    lens = canon['day_masters'][day_master]
    grounds = canon['stems_on_branches'][day_master]

    readings: dict[str, PillarReading] = {}
    visible: dict[TenGodName, dict[str, list[Paragraph]]] = {
        name: {} for name in TEN_GOD_NAMES
    }
    for pillar in PILLARS:
        stem, branch = pillars[pillar]
        is_day = pillar == 'day'
        if is_day:
            stem_reading: StemReading = {
                'kind': 'day_master',
                'ten_god': None,
                'paragraphs': _plain(lens['core']),
            }
            own_stage = None
        else:
            god = ten_gods[(day_master, stem)]
            placement = _plain([canon['ten_gods'][god]['stems'][pillar]])
            visible[god][pillar] = placement
            stem_reading = {'kind': 'ten_god', 'ten_god': god, 'paragraphs': placement}
            own = life_stage(stem, branch)
            own_stage = _stage_reading(canon, own, _plain(canon['stages'][own]['core']))
        text = grounds['branches'][branch]
        only = DAY_PILLAR_ONLY.get(day_master + branch)
        if only is not None and not is_day:
            text = ' '.join(s for s in _sentences(text) if s != only)
        stage = life_stage(day_master, branch)
        readings[pillar] = {
            'stem': stem,
            'branch': branch,
            'lens': _plain([lens['pillars'][pillar]]),
            'stem_reading': stem_reading,
            'own_stage': own_stage,
            'ground': _plain([canon['branches'][branch]['pillars'][pillar]]),
            'ground_about': _plain(canon['branches'][branch]['core']),
            'meets': _plain([text]),
            'stage': _stage_reading(
                canon, stage, _plain([canon['stages'][stage]['pillars'][pillar]])
            ),
        }

    table = canon['cycle']['table'][day_master]
    ring: list[RingStage] = [
        {
            'stage': stage,
            'branch': branch,
            'name': canon['stages'][stage]['name'],
            'chinese': canon['stages'][stage]['chinese'],
        }
        for branch, stage in sorted(table.items(), key=lambda item: item[1])
    ]
    season = _SEASON_BY_BRANCH[pillars['month'][1]]
    return {
        'policy': POLICY,
        'language': 'en',
        'day_master': {
            'stem': day_master,
            'title': lens['title'],
            'introduction': canon['introductions']['day_master_lens'],
            'core': _plain(lens['core']),
            'grounds_introduction': canon['introductions']['stems_on_branches'],
            'grounds': _plain(grounds['introduction']),
            'cycle': {
                'stages': {
                    pillar: life_stage(day_master, pillars[pillar][1])
                    for pillar in PILLARS
                },
                'ring': ring,
                'introduction': canon['cycle']['introduction'],
                'mapping_introduction': _plain(canon['cycle']['mapping_introduction']),
                'narrative': _plain([canon['cycle']['narratives'][day_master]]),
                'reconception': _plain(canon['cycle']['reconception']),
            },
        },
        'pillars': readings,
        'roles_introduction': canon['introductions']['ten_gods'],
        'roles': {
            name: {
                'name': canon['ten_gods'][name]['name'],
                'relation': canon['ten_gods'][name]['relation'],
                'core': _plain(canon['ten_gods'][name]['core']),
                'stems': visible[name],
            }
            for name in TEN_GOD_NAMES
        },
        'branches_introduction': canon['introductions']['branches'],
        'relationships': {
            interaction['id']: _relationship(canon, interaction, pillars, season)
            for interaction in interactions
        },
    }
