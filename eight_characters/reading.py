"""What the canon's taxonomy says of one natal chart, passage by passage.

Every passage is the canon's own words (canon.py), chosen by the chart: the Day
Master, the Ten God of each stem, the branch in each pillar, the Day Master on each
branch, the life stages, and the relationships the engine detects. Nothing here
writes, shortens or rephrases a passage, and nothing assesses strength or predicts.

The canon speaks in English; the reading is English only.
"""

import re
from collections.abc import Callable, Mapping, Sequence
from itertools import combinations
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
from eight_characters.data import BRANCHES
from eight_characters.day_master_context import SEASON_GROUPS, SeasonName
from eight_characters.interactions import (
    CANON_HALF_FRAMES,
    CANON_HARMS,
    CANON_PUNISHMENT_PAIR,
    CANON_PUNISHMENT_TRIANGLES,
    CANON_SELF_PUNISHMENTS,
    Interaction,
    InteractionKind,
)
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
RelationshipKind = InteractionKind
FamilyName = Literal[
    'stem_combinations',
    'six_harmonies',
    'clashes',
    'three_harmonies',
    'directional',
    'punishments',
    'harms',
]
_FAMILY_OF: dict[RelationshipKind, FamilyName] = {
    'stem_combination': 'stem_combinations',
    'branch_combination': 'six_harmonies',
    'branch_clash': 'clashes',
    'harmony_frame': 'three_harmonies',
    'half_frame': 'three_harmonies',
    'directional_combination': 'directional',
    'punishment': 'punishments',
    'half_punishment': 'punishments',
    'self_punishment': 'punishments',
    'harm': 'harms',
}
# The paragraphs that say which form of a punishment a chart holds, as the canon labels
# them; the other forms' paragraphs are left out of its reading. Checked against the
# canon when it loads.
HALF_PUNISHMENT_LABELS: dict[str, str] = {
    '寅巳申': 'When two of three are present (half-punishment)',
    '丑未戌': 'When two of three are present',
}
ACROSS_PILLARS_LABEL = 'Across pillar positions'
ACROSS_PILLARS_ENTRIES = ('寅巳申', '子卯')
SELF_PUNISHMENT_ENTRY = '自刑'
# A frame's paragraph on its half-frames opens with these words.
HALF_FRAMES_OPENING = 'The half-frames:'
# A relationship's line in the list is the canon's sentence about its own form. These
# words open a whole punishment's character and what a harm does in practice; checked
# against the canon when it loads.
PUNISHMENT_CHARACTER = 'The character of this punishment is'
HARM_IN_PRACTICE = 'In practice:'
_POINTS = ('Birth point', 'Peak point', 'Storage point')


def _family(canon: Canon, kind: RelationshipKind) -> Family:
    return canon[_FAMILY_OF[kind]]


def _self_punishment_label(entry: Entry, branch: str) -> str:
    found = [
        p['label']
        for p in entry['paragraphs']
        if p['label'] is not None and p['label'].startswith(branch * 2 + ' ')
    ]
    if len(found) != 1:
        raise CanonError(f'{entry["title"]}: expected one paragraph for {branch * 2}')
    return found[0]


def _point_labels(entry: Entry) -> dict[str, str]:
    """A frame's member points by branch pinyin: 'Peak point (Zi)' under 'Zi'."""
    points: dict[str, str] = {}
    for paragraph in entry['paragraphs']:
        label = paragraph['label']
        if label is not None and label.startswith(_POINTS):
            points[label.split('(')[1].rstrip(')')] = label
    return points


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
    # The one sentence the list shows: the canon's sentence about this form of it.
    line: str
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
    # A sentence ends at its stop, or just after the closing quote that follows it:
    # 'hence "uncivilized." Zi (Water) feeds Mao' holds two.
    return re.split(r'(?<=[.!?])\s+|(?<=[.!?]["”])\s+', text)


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
    punishments = canon['punishments']['entries']
    for key, label in HALF_PUNISHMENT_LABELS.items():
        _labelled(punishments[key], label)
    for key in ACROSS_PILLARS_ENTRIES:
        _labelled(punishments[key], ACROSS_PILLARS_LABEL)
    for branch in CANON_SELF_PUNISHMENTS:
        _self_punishment_label(punishments[SELF_PUNISHMENT_ENTRY], branch)
    for members, entry in canon['three_harmonies']['entries'].items():
        halves = [
            p
            for p in entry['paragraphs']
            if p['label'] is None and p['text'].startswith(HALF_FRAMES_OPENING)
        ]
        if len(halves) != 1 or entry['paragraphs'][0]['label'] is not None:
            raise CanonError(f'{entry["title"]}: its half-frames are not where read')
        if set(_point_labels(entry)) != {BRANCHES[b]['pinyin'] for b in members}:
            raise CanonError(f'{entry["title"]}: its points do not name its branches')
    _check_lines(canon)
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


def _entry_key(family: Family, kind: RelationshipKind, chars: Sequence[str]) -> str:
    """The family's entry for a finding: a half reads its whole's entry."""
    if kind == 'self_punishment':
        return SELF_PUNISHMENT_ENTRY
    found = set(chars)
    if kind in ('half_frame', 'half_punishment'):
        matching = [
            key for key in family['entries'] if len(key) == 3 and found < set(key)
        ]
    else:
        matching = [
            key
            for key in family['entries']
            if len(key) == len(chars) and set(key) == found
        ]
    if len(matching) != 1:
        raise CanonError(f'no single canon entry for {kind} {"".join(chars)}')
    return matching[0]


def _lead(
    entry: Entry, kind: RelationshipKind, key: str, chars: Sequence[str]
) -> list[Paragraph]:
    """The entry's paragraphs for this form of the relationship, in the canon's order.

    A stem combination's labelled paragraphs are read apart. A half-frame reads the
    frame's opening, the points of its two branches and the paragraph on half-frames;
    a punishment reads what applies to the form the chart holds, whole or half; a
    self-punishment reads its own branch.
    """
    paragraphs = entry['paragraphs']
    if kind == 'stem_combination':
        return [p for p in paragraphs if p['label'] is None]
    if kind == 'half_frame':
        points = _point_labels(entry)
        present = {points[BRANCHES[char]['pinyin']] for char in chars}
        return [
            p
            for index, p in enumerate(paragraphs)
            if index == 0
            or p['label'] in present
            or (p['label'] is None and p['text'].startswith(HALF_FRAMES_OPENING))
        ]
    if kind == 'punishment':
        half = HALF_PUNISHMENT_LABELS.get(key)
        return [p for p in paragraphs if half is None or p['label'] != half]
    if kind == 'half_punishment':
        return [
            p for p in paragraphs if p['label'] in (None, HALF_PUNISHMENT_LABELS[key])
        ]
    if kind == 'self_punishment':
        own = _self_punishment_label(entry, chars[0])
        return [p for p in paragraphs if p['label'] in (None, own)]
    return list(paragraphs)


def _pair_name(key: str, chars: Sequence[str]) -> str:
    """Two of a triple's branches by pinyin, in the canon's order: Shen-Zi, Zi-Chen."""
    return '-'.join(BRANCHES[char]['pinyin'] for char in key if char in chars)


def _one(sentences: Sequence[str], matches: Callable[[str], bool], what: str) -> str:
    found = [sentence for sentence in sentences if matches(sentence)]
    if len(found) != 1:
        raise CanonError(f'expected one sentence {what}, found {len(found)}')
    return found[0]


def _line(
    entry: Entry,
    kind: RelationshipKind,
    key: str,
    chars: Sequence[str],
    lead: Sequence[Paragraph],
    pairing: Paragraph | None,
) -> str:
    """The relationship's line in the list: the canon's sentence about this form of it.

    A pairing's first sentence where the family has pairings. Otherwise: for a half, the
    sentence on its own two branches (a half-frame's names the third, absent one); for a
    whole punishment, its character; for a harm, what it does in practice, which runs
    both ways; for a self-punishment, its own branch's first sentence; for anything
    else, the entry's first sentence.
    """
    if pairing is not None:
        return _sentences(pairing['text'])[0]
    said = [sentence for p in lead for sentence in _sentences(p['text'])]
    title = entry['title']
    if kind == 'half_frame':
        absent = next(BRANCHES[char]['pinyin'] for char in key if char not in chars)
        phrase = f'{_pair_name(key, chars)} without {absent}'
        return _one(
            said, lambda sentence: phrase in sentence, f'on {phrase} in {title}'
        )
    if kind == 'half_punishment':
        pair = _pair_name(key, chars)
        own = _labelled(entry, HALF_PUNISHMENT_LABELS[key])
        return _one(
            _sentences(own['text']),
            lambda sentence: sentence.startswith(pair + ' '),
            f'on {pair} in {title}',
        )
    if kind == 'punishment':
        return _one(
            said,
            lambda sentence: sentence.startswith(PUNISHMENT_CHARACTER),
            f'on the character of {title}',
        )
    if kind == 'harm':
        return _one(
            said,
            lambda sentence: sentence.startswith(HARM_IN_PRACTICE),
            f'on {title} in practice',
        )
    if kind == 'self_punishment':
        own = _labelled(entry, _self_punishment_label(entry, chars[0]))
        return _sentences(own['text'])[0]
    return said[0]


def _check_lines(canon: Canon) -> None:
    """Every form of the canon's added families has its line, exactly once."""
    frames = canon['three_harmonies']['entries']
    for key, peak in CANON_HALF_FRAMES:
        for other in key:
            if other != peak:
                chars = [char for char in key if char in (peak, other)]
                lead = _lead(frames[key], 'half_frame', key, chars)
                _line(frames[key], 'half_frame', key, chars, lead, None)
    punishments = canon['punishments']['entries']
    for key in (*CANON_PUNISHMENT_TRIANGLES, CANON_PUNISHMENT_PAIR):
        chars = list(key)
        _line(
            punishments[key],
            'punishment',
            key,
            chars,
            _lead(punishments[key], 'punishment', key, chars),
            None,
        )
    for key in CANON_PUNISHMENT_TRIANGLES:
        for pair in combinations(key, 2):
            lead = _lead(punishments[key], 'half_punishment', key, pair)
            _line(punishments[key], 'half_punishment', key, pair, lead, None)
    entry = punishments[SELF_PUNISHMENT_ENTRY]
    for branch in CANON_SELF_PUNISHMENTS:
        chars = [branch, branch]
        lead = _lead(entry, 'self_punishment', SELF_PUNISHMENT_ENTRY, chars)
        _line(entry, 'self_punishment', SELF_PUNISHMENT_ENTRY, chars, lead, None)
    harms = canon['harms']['entries']
    for key in CANON_HARMS:
        chars = list(key)
        _line(
            harms[key], 'harm', key, chars, _lead(harms[key], 'harm', key, chars), None
        )


def _relationship(
    canon: Canon,
    interaction: Interaction,
    pillars: Mapping[str, tuple[str, str]],
    season: SeasonName,
) -> RelationshipReading:
    kind = interaction['kind']
    family = _family(canon, kind)
    chars = [member['char'] for member in interaction['members']]
    key = _entry_key(family, kind, chars)
    entry = family['entries'][key]
    member_pillars = [member['pillar'] for member in interaction['members']]
    # Only the families the canon gives pairings for read one; a pair's is its pillars'.
    pairing = (
        family['pairings'][_pairing(member_pillars)]
        if len(member_pillars) == 2 and family['pairings']
        else None
    )
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
    lead = _lead(entry, kind, key, chars)
    return {
        'kind': kind,
        'line': _line(entry, kind, key, chars, lead, pairing),
        'introduction': family['introduction'],
        'pairing': pairing,
        'entry': {
            'title': entry['title'],
            'paragraphs': lead,
        },
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
