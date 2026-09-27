"""The canon's taxonomy (canon/Taxonomy.md) as keyed passages.

Only the package is installed, so it carries a byte-identical copy of the canon at
resources/canon/Taxonomy.md; a test compares the two. Every entry the taxonomy
defines must be present once, with each of its placements, or loading fails.
Passages are the canon's words, unchanged, split into paragraphs. They keep the
canon's two inline marks, *emphasis* and **strong**; any other Markdown in a passage
fails loading, so the app never shows a mark as text.
"""

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

from typing_extensions import TypedDict

from eight_characters.ten_gods import TEN_GOD_NAMES, TenGodName

CANON_PATH = Path(__file__).resolve().parent / 'resources' / 'canon' / 'Taxonomy.md'

STEM_CHARS = '甲乙丙丁戊己庚辛壬癸'
BRANCH_CHARS = '子丑寅卯辰巳午未申酉戌亥'
PILLARS = ('year', 'month', 'day', 'hour')
STEM_PILLARS = ('year', 'month', 'hour')
PAIRINGS = (
    'Year–Month',
    'Year–Day',
    'Year–Hour',
    'Month–Day',
    'Month–Hour',
    'Day–Hour',
)
# The twelve stages in order, as the mapping names them.
STAGE_NAMES = (
    'Birth',
    'Bathing',
    'Capping',
    'Office',
    'Peak',
    'Decline',
    'Sickness',
    'Death',
    'Tomb',
    'Extinction',
    'Embryo',
    'Nurture',
)

PillarName = Literal['year', 'month', 'day', 'hour']
Pairing = Literal[
    'Year–Month', 'Year–Day', 'Year–Hour', 'Month–Day', 'Month–Hour', 'Day–Hour'
]

# The canon names each Ten God by its own name, with the standard name after it.
_TEN_GOD_BY_STANDARD_NAME: dict[str, TenGodName] = {
    'Companion': 'friend',
    'Rob Wealth': 'rob_wealth',
    'Eating God': 'eating_god',
    'Hurting Officer': 'hurting_officer',
    'Indirect Wealth': 'indirect_wealth',
    'Direct Wealth': 'direct_wealth',
    'Seven Killings': 'seven_killings',
    'Direct Officer': 'direct_officer',
    'Indirect Resource': 'indirect_resource',
    'Direct Resource': 'direct_resource',
}

_SIX_HARMONIES = ('子丑', '寅亥', '卯戌', '辰酉', '巳申', '午未')
_THREE_HARMONIES = ('申子辰', '亥卯未', '寅午戌', '巳酉丑')
_DIRECTIONAL = ('亥子丑', '寅卯辰', '巳午未', '申酉戌')
_CLASHES = ('子午', '丑未', '寅申', '卯酉', '辰戌', '巳亥')
_PUNISHMENTS = ('寅巳申', '丑未戌', '子卯', '自刑')
_HARMS = ('子未', '丑午', '寅巳', '卯辰', '申亥', '酉戌')
_STEM_COMBINATIONS = ('甲己', '乙庚', '丙辛', '丁壬', '戊癸')


class CanonError(RuntimeError):
    """The canon does not have the shape the app reads."""


class Paragraph(TypedDict):
    # The bold label that opens the paragraph in the canon, or None.
    label: str | None
    text: str


class TenGodPassages(TypedDict):
    # The canon's heading, e.g. 'The Equal (Companion)', and its relation line.
    name: str
    relation: str
    core: list[str]
    stems: dict[str, str]  # year, month, hour


class DayMasterPassages(TypedDict):
    title: str
    core: list[str]
    pillars: dict[str, str]


class BranchPassages(TypedDict):
    title: str
    core: list[str]
    pillars: dict[str, str]


class StemGrounds(TypedDict):
    title: str
    introduction: list[str]
    branches: dict[str, str]


class Entry(TypedDict):
    title: str
    paragraphs: list[Paragraph]


class Family(TypedDict):
    introduction: list[Paragraph]
    # The meaning of each pillar pairing, where the canon gives one, keyed by the
    # pairing; its label keeps what the canon adds, e.g. '(adjacent)'.
    pairings: dict[str, Paragraph]
    entries: dict[str, Entry]


class Stage(TypedDict):
    number: int
    title: str
    chinese: str
    name: str
    core: list[str]
    pillars: dict[str, str]


class Cycle(TypedDict):
    introduction: list[Paragraph]
    mapping_introduction: list[str]
    # stem -> branch -> stage number (1 = Birth).
    table: dict[str, dict[str, int]]
    # stem -> the paragraph that tells its cycle; Earth shares Fire's.
    narratives: dict[str, str]
    reconception: list[str]


class Canon(TypedDict):
    introductions: dict[str, list[Paragraph]]
    ten_gods: dict[TenGodName, TenGodPassages]
    day_masters: dict[str, DayMasterPassages]
    branches: dict[str, BranchPassages]
    stems_on_branches: dict[str, StemGrounds]
    six_harmonies: Family
    three_harmonies: Family
    directional: Family
    clashes: Family
    punishments: Family
    harms: Family
    stem_combinations: Family
    combination_mechanics: list[Paragraph]
    stages: dict[int, Stage]
    cycle: Cycle


@dataclass
class _Node:
    level: int
    title: str
    paragraphs: list[Paragraph] = field(default_factory=list[Paragraph])
    children: list['_Node'] = field(default_factory=list['_Node'])


_LABEL = re.compile(r'^\*\*(?P<label>[^*]+?):\*\*\s*(?P<text>.*)$')
# The only inline Markdown a passage may keep: *emphasis* and **strong**.
_ALLOWED_INLINE = re.compile(r'\*\*[^*]+\*\*|\*[^*]+\*')
_FORBIDDEN_MARKS = re.compile(r'[`_\[\]<>#\\|]')


def _fail(message: str) -> CanonError:
    return CanonError(f'canon/Taxonomy.md: {message}')


def _check_inline(text: str, where: str) -> str:
    bare = _ALLOWED_INLINE.sub('', text)
    if '*' in bare or _FORBIDDEN_MARKS.search(bare):
        raise _fail(f'unexpected Markdown in {where}: {text[:80]!r}')
    return text


def _heading_title(line: str) -> tuple[int, str]:
    level = len(line) - len(line.lstrip('#'))
    title = line[level:].strip().replace('\\.', '.').replace('*', '').strip()
    return level, title


def _tree(markdown: str) -> _Node:
    root = _Node(0, '')
    stack = [root]
    lines: list[str] = []

    def close_paragraph() -> None:
        if not lines:
            return
        joined = ' '.join(lines).strip()
        lines.clear()
        if joined == '---':
            return
        match = _LABEL.match(joined)
        where = stack[-1].title or 'the preamble'
        if match:
            stack[-1].paragraphs.append(
                {
                    'label': match.group('label').strip(),
                    'text': _check_inline(match.group('text').strip(), where),
                }
            )
        else:
            stack[-1].paragraphs.append(
                {'label': None, 'text': _check_inline(joined, where)}
            )

    for raw in markdown.split('\n'):
        line = raw.strip()
        if line.startswith('#'):
            close_paragraph()
            level, title = _heading_title(line)
            node = _Node(level, title)
            while stack[-1].level >= level:
                stack.pop()
            stack[-1].children.append(node)
            stack.append(node)
        elif not line:
            close_paragraph()
        else:
            lines.append(line)
    close_paragraph()
    if root.paragraphs:
        raise _fail('text before the first heading')
    return root


def _only(node: _Node, count: int, what: str) -> list[_Node]:
    if len(node.children) != count:
        raise _fail(
            f'{node.title}: expected {count} {what}, found {len(node.children)}'
        )
    return node.children


def _unlabelled(node: _Node) -> list[str]:
    return [p['text'] for p in node.paragraphs if p['label'] is None]


def _labelled(node: _Node) -> dict[str, str]:
    result: dict[str, str] = {}
    for paragraph in node.paragraphs:
        label = paragraph['label']
        if label is None:
            continue
        if label in result:
            raise _fail(f'{node.title}: label {label!r} appears twice')
        result[label] = paragraph['text']
    return result


def _exact_labels(node: _Node, expected: tuple[str, ...]) -> dict[str, str]:
    labels = _labelled(node)
    if tuple(labels) != expected:
        raise _fail(f'{node.title}: labels {tuple(labels)!r}, expected {expected!r}')
    return labels


def _one_core(node: _Node, at_least: int = 1) -> list[str]:
    core = _unlabelled(node)
    if len(core) < at_least:
        raise _fail(f'{node.title}: missing its opening passage')
    return core


def _keyed(
    nodes: list[_Node], size: int, expected: tuple[str, ...]
) -> dict[str, _Node]:
    keyed: dict[str, _Node] = {}
    for node in nodes:
        key = node.title[:size]
        if key in keyed:
            raise _fail(f'{node.title}: entry {key} appears twice')
        keyed[key] = node
    if set(keyed) != set(expected):
        raise _fail(f'entries {sorted(keyed)}, expected {sorted(expected)}')
    return {key: keyed[key] for key in expected}


def _section(root: _Node, title: str) -> _Node:
    found = [node for node in root.children if node.title == title]
    if len(found) != 1:
        raise _fail(f'expected one section titled {title!r}, found {len(found)}')
    return found[0]


def _ten_gods(node: _Node) -> dict[TenGodName, TenGodPassages]:
    result: dict[TenGodName, TenGodPassages] = {}
    for child in _only(node, 10, 'Ten Gods'):
        name, _, relation = child.title.partition(' — ')
        standard = re.fullmatch(r'.+ \((?P<standard>[^)]+)\)', name)
        key = (
            _TEN_GOD_BY_STANDARD_NAME.get(standard.group('standard'))
            if standard
            else None
        )
        if key is None or not relation:
            raise _fail(f'unrecognised Ten God heading {child.title!r}')
        if key in result:
            raise _fail(f'Ten God {key} appears twice')
        labels = _exact_labels(child, ('Year Stem', 'Month Stem', 'Hour Stem'))
        result[key] = {
            'name': name,
            'relation': relation,
            'core': _one_core(child),
            'stems': {
                pillar: labels[f'{pillar.title()} Stem'] for pillar in STEM_PILLARS
            },
        }
    if tuple(sorted(result)) != tuple(sorted(TEN_GOD_NAMES)):
        raise _fail('the Ten Gods are not the ten the engine names')
    return {name: result[name] for name in TEN_GOD_NAMES}


def _by_first_char(nodes: list[_Node], chars: str, what: str) -> dict[str, _Node]:
    keyed: dict[str, _Node] = {}
    for node in nodes:
        char = node.title[:1]
        if char not in chars or char in keyed:
            raise _fail(f'unexpected or repeated {what} heading {node.title!r}')
        keyed[char] = node
    if len(keyed) != len(chars):
        raise _fail(f'expected every {what}')
    return {char: keyed[char] for char in chars}


def _pillar_texts(node: _Node) -> dict[str, str]:
    labels = _exact_labels(node, ('Year', 'Month', 'Day', 'Hour'))
    return {pillar: labels[pillar.title()] for pillar in PILLARS}


def _stems_on_branches(node: _Node) -> dict[str, StemGrounds]:
    result: dict[str, StemGrounds] = {}
    for stem, child in _by_first_char(
        _only(node, 10, 'stems'), STEM_CHARS, 'stem'
    ).items():
        branches: dict[str, str] = {}
        for label, text in _labelled(child).items():
            branch = label[:1]
            if branch not in BRANCH_CHARS or branch in branches:
                raise _fail(f'{child.title}: unexpected entry {label!r}')
            branches[branch] = text
        if len(branches) != len(BRANCH_CHARS):
            raise _fail(f'{child.title}: expected every branch')
        result[stem] = {
            'title': child.title,
            'introduction': _one_core(child),
            'branches': {branch: branches[branch] for branch in BRANCH_CHARS},
        }
    return result


def _family(
    node: _Node, size: int, expected: tuple[str, ...], pairings: bool
) -> Family:
    found: dict[str, Paragraph] = {}
    kept: list[Paragraph] = []
    for paragraph in node.paragraphs:
        label = paragraph['label']
        pairing = label.split(' (')[0] if label is not None else None
        if pairings and pairing in PAIRINGS:
            if pairing in found:
                raise _fail(f'{node.title}: pairing {pairing} appears twice')
            found[pairing] = paragraph
        else:
            kept.append(paragraph)
    if pairings and tuple(found) != PAIRINGS:
        raise _fail(f'{node.title}: pairings {tuple(found)!r}, expected {PAIRINGS!r}')
    keyed = _keyed(
        [child for child in node.children if child.level == 3], size, expected
    )
    return {
        'introduction': kept,
        'pairings': {
            pairing: found[pairing] for pairing in PAIRINGS if pairing in found
        },
        'entries': {
            key: {'title': child.title, 'paragraphs': child.paragraphs}
            for key, child in keyed.items()
        },
    }


def _punishments(node: _Node) -> Family:
    entries = [child for child in node.children if child.level == 3]
    keyed: dict[str, _Node] = {}
    for child in entries:
        head = child.title.split(' ')[0]
        key = head if head == '自刑' else head.removesuffix('刑')
        if key in keyed:
            raise _fail(f'{child.title}: punishment appears twice')
        keyed[key] = child
    if tuple(keyed) != _PUNISHMENTS:
        raise _fail(f'punishments {tuple(keyed)!r}, expected {_PUNISHMENTS!r}')
    return {
        'introduction': node.paragraphs,
        'pairings': {},
        'entries': {
            key: {'title': child.title, 'paragraphs': child.paragraphs}
            for key, child in keyed.items()
        },
    }


def _stages(node: _Node) -> tuple[dict[int, Stage], _Node, _Node]:
    stages: dict[int, Stage] = {}
    mapping: _Node | None = None
    reconception: _Node | None = None
    for child in node.children:
        if child.title.startswith('THE MAPPING'):
            mapping = child
            continue
        if child.title.startswith('THE PATTERN OF RECONCEPTION'):
            reconception = child
            continue
        match = re.fullmatch(
            r'(?P<number>\d+)\. (?P<chinese>\S+) (?P<pinyin>.+?) — (?P<name>.+?)( \((?P<alias>.+)\))?',
            child.title,
        )
        if match is None:
            raise _fail(f'unrecognised stage heading {child.title!r}')
        number = int(match.group('number'))
        if number in stages:
            raise _fail(f'stage {number} appears twice')
        labels = _exact_labels(
            child,
            (
                'On the Year Branch',
                'On the Month Branch',
                'On the Day Branch',
                'On the Hour Branch',
            ),
        )
        stages[number] = {
            'number': number,
            'title': child.title,
            'chinese': match.group('chinese'),
            'name': match.group('name'),
            'core': _one_core(child),
            'pillars': {
                pillar: labels[f'On the {pillar.title()} Branch'] for pillar in PILLARS
            },
        }
    if sorted(stages) != list(range(1, 13)):
        raise _fail('expected the twelve stages, numbered 1 to 12')
    if mapping is None or reconception is None:
        raise _fail(
            'THE TWELVE STAGES: missing the mapping or the pattern of reconception'
        )
    return {n: stages[n] for n in range(1, 13)}, mapping, reconception


_TABLE_LINE = re.compile(r'^\*\*(?P<head>[^*]+)\*\*\s*(?P<cells>Birth: .+)$')


def _cycle(introduction: list[Paragraph], mapping: _Node, reconception: _Node) -> Cycle:
    table: dict[str, dict[str, int]] = {}
    narratives: dict[str, str] = {}
    groups = _only(mapping, 2, 'groups of stems')
    for group in groups:
        stems: list[str] = []
        for paragraph in group.paragraphs:
            if paragraph['label'] is not None:
                raise _fail(f'{group.title}: unexpected label {paragraph["label"]!r}')
            line = _TABLE_LINE.match(paragraph['text'])
            if line:
                stems = [
                    char
                    for char in re.findall(
                        r'[甲乙丙丁戊己庚辛壬癸]', line.group('head')
                    )
                ]
                cells = re.findall(r'(\w+): (\S) ', line.group('cells') + ' ')
                names = tuple(name for name, _ in cells)
                branches = [branch for _, branch in cells]
                if names != STAGE_NAMES or sorted(branches) != sorted(BRANCH_CHARS):
                    raise _fail(
                        f'{group.title}: a malformed row for {line.group("head")!r}'
                    )
                for stem in stems:
                    if stem in table:
                        raise _fail(f'the stage row of {stem} appears twice')
                    table[stem] = {
                        branch: STAGE_NAMES.index(name) + 1 for name, branch in cells
                    }
            else:
                if not stems or any(stem in narratives for stem in stems):
                    raise _fail(f'{group.title}: a paragraph outside a stem row')
                for stem in stems:
                    narratives[stem] = paragraph['text']
    if sorted(table) != sorted(STEM_CHARS) or sorted(narratives) != sorted(STEM_CHARS):
        raise _fail('the mapping must give every stem a row and a paragraph')
    return {
        'introduction': introduction,
        'mapping_introduction': _unlabelled(mapping),
        'table': {
            stem: dict(
                sorted(
                    table[stem].items(), key=lambda item: BRANCH_CHARS.index(item[0])
                )
            )
            for stem in STEM_CHARS
        },
        'narratives': {stem: narratives[stem] for stem in STEM_CHARS},
        'reconception': _unlabelled(reconception),
    }


def parse_canon(markdown: str) -> Canon:
    root = _tree(markdown)
    ten_gods = _section(root, 'The Ten Gods (10×3)')
    lens = _section(root, 'The Day Master Lens (10×4)')
    branches = _section(root, 'The Earthly Branches (12×4)')
    grounds = _section(root, 'Stem on Branch (10×12)')
    combinations = _section(root, 'THE FIVE STEM COMBINATIONS (天干五合)')
    stage_section = _section(root, 'THE TWELVE STAGES')
    if len(root.children) != 12:
        raise _fail(f'expected 12 sections, found {len(root.children)}')

    mechanics = [
        c
        for c in combinations.children
        if c.title.startswith('STEM COMBINATION MECHANICS')
    ]
    stage_intro = [
        c for c in combinations.children if c.title.startswith('THE TWELVE LIFE STAGES')
    ]
    if len(mechanics) != 1 or len(stage_intro) != 1:
        raise _fail(
            'THE FIVE STEM COMBINATIONS: missing its mechanics or the life stages introduction'
        )
    stages, mapping, reconception = _stages(stage_section)

    return {
        'introductions': {
            'ten_gods': ten_gods.paragraphs,
            'day_master_lens': lens.paragraphs,
            'branches': branches.paragraphs,
            'stems_on_branches': grounds.paragraphs,
        },
        'ten_gods': _ten_gods(ten_gods),
        'day_masters': {
            stem: {
                'title': child.title,
                'core': _one_core(child),
                'pillars': _pillar_texts(child),
            }
            for stem, child in _by_first_char(
                _only(lens, 10, 'Day Masters'), STEM_CHARS, 'Day Master'
            ).items()
        },
        'branches': {
            branch: {
                'title': child.title,
                'core': _one_core(child),
                'pillars': _pillar_texts(child),
            }
            for branch, child in _by_first_char(
                _only(branches, 12, 'branches'), BRANCH_CHARS, 'branch'
            ).items()
        },
        'stems_on_branches': _stems_on_branches(grounds),
        'six_harmonies': _family(
            _section(root, 'THE SIX HARMONIES (六合)'), 2, _SIX_HARMONIES, pairings=True
        ),
        'three_harmonies': _family(
            _section(root, 'THE THREE HARMONIES (三合)'),
            3,
            _THREE_HARMONIES,
            pairings=False,
        ),
        'directional': _family(
            _section(root, 'THE DIRECTIONAL COMBINATIONS (三会 / 方合)'),
            3,
            _DIRECTIONAL,
            pairings=False,
        ),
        'clashes': _family(
            _section(root, 'THE SIX CLASHES (六冲)'), 2, _CLASHES, pairings=True
        ),
        'punishments': _punishments(_section(root, 'THE THREE PUNISHMENTS (三刑)')),
        'harms': _family(
            _section(root, 'THE SIX HARMS (六害)'), 2, _HARMS, pairings=False
        ),
        'stem_combinations': _family(
            combinations, 2, _STEM_COMBINATIONS, pairings=True
        ),
        'combination_mechanics': mechanics[0].paragraphs,
        'stages': stages,
        'cycle': _cycle(stage_intro[0].paragraphs, mapping, reconception),
    }


@lru_cache(maxsize=1)
def load_canon() -> Canon:
    """The packaged canon, parsed once; a missing or malformed canon raises."""
    if not CANON_PATH.exists():
        raise _fail(f'not found at {CANON_PATH}')
    return parse_canon(CANON_PATH.read_text(encoding='utf-8'))
