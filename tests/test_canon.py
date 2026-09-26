import re
import unittest
from collections import Counter
from pathlib import Path

from eight_characters.canon import (
    BRANCH_CHARS,
    CANON_PATH,
    PAIRINGS,
    STEM_CHARS,
    CanonError,
    load_canon,
    parse_canon,
)
from eight_characters.ten_gods import TEN_GOD_NAMES

REPO_CANON = Path(__file__).resolve().parents[1] / 'canon' / 'Taxonomy.md'
PILLARS = ('year', 'month', 'day', 'hour')
LABEL = re.compile(r'^\*\*([^*]+?):\*\*\s*(.*)$')
TABLE_LINE = re.compile(r'^\*\*[^*]+\*\*\s*Birth: ')


def raw_paragraphs(markdown):
    """Every paragraph of the Markdown, split independently of the parser."""
    paragraphs = []
    for block in re.split(r'\n\s*\n', markdown):
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        body = [line for line in lines if not line.startswith('#')]
        if not body or body == ['---']:
            continue
        paragraphs.append(' '.join(body))
    return paragraphs


def parsed_texts(canon):
    """Every paragraph text the parse holds, each once (Earth shares Fire's story)."""
    texts = []
    for paragraphs in canon['introductions'].values():
        texts += [p['text'] for p in paragraphs]
    for god in canon['ten_gods'].values():
        texts += god['core'] + list(god['stems'].values())
    for entry in list(canon['day_masters'].values()) + list(canon['branches'].values()):
        texts += entry['core'] + list(entry['pillars'].values())
    for grounds in canon['stems_on_branches'].values():
        texts += grounds['introduction'] + list(grounds['branches'].values())
    for family in (
        'six_harmonies',
        'three_harmonies',
        'directional',
        'clashes',
        'punishments',
        'harms',
        'stem_combinations',
    ):
        texts += [p['text'] for p in canon[family]['introduction']]
        texts += [p['text'] for p in canon[family]['pairings'].values()]
        for entry in canon[family]['entries'].values():
            texts += [p['text'] for p in entry['paragraphs']]
    texts += [p['text'] for p in canon['combination_mechanics']]
    for stage in canon['stages'].values():
        texts += stage['core'] + list(stage['pillars'].values())
    cycle = canon['cycle']
    texts += [p['text'] for p in cycle['introduction']]
    texts += cycle['mapping_introduction'] + cycle['reconception']
    texts += list(dict.fromkeys(cycle['narratives'].values()))
    return texts


class TestCanon(unittest.TestCase):
    def setUp(self):
        self.canon = load_canon()
        self.markdown = REPO_CANON.read_text(encoding='utf-8')

    def test_the_package_carries_the_canon_unchanged(self):
        self.assertEqual(
            CANON_PATH.read_bytes(),
            REPO_CANON.read_bytes(),
            'Copy canon/Taxonomy.md to eight_characters/resources/canon/Taxonomy.md.',
        )

    def test_every_paragraph_is_read_once(self):
        raw = [p for p in raw_paragraphs(self.markdown) if not TABLE_LINE.match(p)]
        expected = Counter(
            LABEL.match(p).group(2) if LABEL.match(p) else p for p in raw
        )
        self.assertEqual(Counter(parsed_texts(self.canon)), expected)

    def test_every_table_row_is_read(self):
        rows = [p for p in raw_paragraphs(self.markdown) if TABLE_LINE.match(p)]
        self.assertEqual(len(rows), 8)
        self.assertEqual(sorted(self.canon['cycle']['table']), sorted(STEM_CHARS))

    def test_every_entry_has_every_placement(self):
        self.assertEqual(tuple(self.canon['ten_gods']), TEN_GOD_NAMES)
        for god in self.canon['ten_gods'].values():
            self.assertEqual(tuple(god['stems']), ('year', 'month', 'hour'))
            self.assertTrue(god['core'] and god['name'] and god['relation'])
        self.assertEqual(''.join(self.canon['day_masters']), STEM_CHARS)
        self.assertEqual(''.join(self.canon['branches']), BRANCH_CHARS)
        for entry in list(self.canon['day_masters'].values()) + list(
            self.canon['branches'].values()
        ):
            self.assertEqual(tuple(entry['pillars']), PILLARS)
        self.assertEqual(''.join(self.canon['stems_on_branches']), STEM_CHARS)
        for grounds in self.canon['stems_on_branches'].values():
            self.assertEqual(''.join(grounds['branches']), BRANCH_CHARS)
        self.assertEqual(list(self.canon['stages']), list(range(1, 13)))
        for stage in self.canon['stages'].values():
            self.assertEqual(tuple(stage['pillars']), PILLARS)

    def test_relationship_families(self):
        counts = {
            'six_harmonies': 6,
            'three_harmonies': 4,
            'directional': 4,
            'clashes': 6,
            'punishments': 4,
            'harms': 6,
            'stem_combinations': 5,
        }
        for family, count in counts.items():
            self.assertEqual(len(self.canon[family]['entries']), count, family)
        for family in ('six_harmonies', 'clashes', 'stem_combinations'):
            self.assertEqual(tuple(self.canon[family]['pairings']), PAIRINGS, family)
        self.assertEqual(
            self.canon['stem_combinations']['pairings']['Year–Hour']['label'],
            'Year–Hour (separated by two pillars — no bond in the natal chart)',
        )

    def test_stage_table_follows_the_canon_rows(self):
        table = self.canon['cycle']['table']
        # Yang Wood is born in the Pig; Yin Wood in the Horse; Earth follows Fire.
        self.assertEqual(table['甲']['亥'], 1)
        self.assertEqual(table['乙']['午'], 1)
        self.assertEqual(table['戊'], table['丙'])
        self.assertEqual(table['己'], table['丁'])
        self.assertEqual(
            self.canon['cycle']['narratives']['戊'],
            self.canon['cycle']['narratives']['丙'],
        )
        for stem in STEM_CHARS:
            self.assertEqual(sorted(table[stem].values()), list(range(1, 13)))

    def test_inline_marks_are_kept_as_marks(self):
        self.assertIn(
            '*relational structure*', self.canon['introductions']['ten_gods'][0]['text']
        )
        self.assertTrue(
            any('**Embryo**' in p['text'] for p in self.canon['cycle']['introduction'])
        )


class TestMalformedCanon(unittest.TestCase):
    def setUp(self):
        self.markdown = REPO_CANON.read_text(encoding='utf-8')

    def assertRefused(self, markdown):
        with self.assertRaises(CanonError):
            parse_canon(markdown)

    def test_a_missing_placement_is_refused(self):
        self.assertRefused(
            self.markdown.replace('**Month Stem:**', '**Month Stems:**', 1)
        )

    def test_a_repeated_entry_is_refused(self):
        self.assertRefused(self.markdown.replace('### **丑未冲', '### **子午冲', 1))

    def test_a_missing_section_is_refused(self):
        self.assertRefused(
            self.markdown.replace('# THE SIX HARMS (六害)', '# THE SIX HARMS', 1)
        )

    def test_other_markdown_in_a_passage_is_refused(self):
        self.assertRefused(
            self.markdown.replace('Your exact double.', 'Your `exact` double.', 1)
        )

    def test_a_broken_stage_row_is_refused(self):
        self.assertRefused(
            self.markdown.replace(
                'Birth: 亥 Hai (Pig) · Bathing', 'Birth: 子 Hai (Pig) · Bathing', 1
            )
        )


if __name__ == '__main__':
    unittest.main()
