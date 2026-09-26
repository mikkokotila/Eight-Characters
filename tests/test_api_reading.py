import copy
import itertools
import re
import unittest

from fastapi.testclient import TestClient
from lunar_python.util import LunarUtil

from eight_characters.canon import BRANCH_CHARS, STEM_CHARS, CanonError, load_canon
from eight_characters.interactions import detect_interactions
from eight_characters.main import _load_ten_gods_lookup, app
from eight_characters.reading import build_reading, check_reading_canon

PILLARS = ('year', 'month', 'day', 'hour')
GODS = dict(
    zip(
        (
            '比肩',
            '劫财',
            '食神',
            '伤官',
            '偏财',
            '正财',
            '七杀',
            '正官',
            '偏印',
            '正印',
        ),
        (
            'friend',
            'rob_wealth',
            'eating_god',
            'hurting_officer',
            'indirect_wealth',
            'direct_wealth',
            'seven_killings',
            'direct_officer',
            'indirect_resource',
            'direct_resource',
        ),
        strict=True,
    )
)
# The chart canon/Background.md reads: Helsinki, 29 June 1976, 07:02 by the clock.
HELSINKI = {
    'date': '1976-06-29',
    'time': '07:02:00',
    'location': {
        'timezone': 'Europe/Helsinki',
        'latitude': 60.1699,
        'longitude': 24.9384,
    },
}
SEASONS = {
    '寅卯辰': 'spring',
    '巳午未': 'summer',
    '申酉戌': 'autumn',
    '亥子丑': 'winter',
}
SEASON_OF = {char: name for chars, name in SEASONS.items() for char in chars}


def sentences(text):
    return re.split(r'(?<=[.!?])\s+', text)


def texts(paragraphs):
    return [p['text'] for p in paragraphs]


def reading(pillars):
    return build_reading(
        load_canon(), pillars, _load_ten_gods_lookup(), detect_interactions(pillars)
    )


def same_polarity_stem(branch):
    return '甲' if BRANCH_CHARS.index(branch) % 2 == 0 else '乙'


class TestReadingApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def post(self, **flags):
        response = self.client.post('/api/four_pillars', json={**HELSINKI, **flags})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_the_reading_is_asked_for_separately(self):
        self.assertNotIn('reading', self.post())
        flags = {
            'include_hidden_stems': True,
            'include_ten_gods': True,
            'include_interactions': True,
            'include_day_master_context': True,
            'include_role_profile': True,
        }
        without = self.post(**flags)
        with_reading = self.post(**flags, include_reading=True)
        self.assertEqual(with_reading.pop('reading')['policy'], 'canon_taxonomy_v1')
        self.assertEqual(with_reading, without)

    def test_the_example_chart_reads_as_canon_background_reads_it(self):
        result = self.post(include_reading=True)['reading']
        self.assertEqual(result['language'], 'en')
        self.assertEqual(result['day_master']['stem'], '壬')
        pillars = result['pillars']
        self.assertEqual(
            {name: pillars[name]['stem'] + pillars[name]['branch'] for name in PILLARS},
            {'year': '丙辰', 'month': '甲午', 'day': '壬子', 'hour': '癸卯'},
        )
        # "On the Dragon, Yang Water is in its Tomb. On the Horse, its Embryo. On the
        # Rat, its Emperor's Peak. On the Rabbit, its Death."
        self.assertEqual(
            {name: pillars[name]['stage']['name'] for name in PILLARS},
            {
                'year': 'Tomb',
                'month': 'Embryo',
                'day': "Emperor's Peak",
                'hour': 'Death',
            },
        )
        # "Yang Wood's own Death point"; "Yang Fire is at its Capping stage on the
        # Dragon"; "the Rabbit is Yin Water's Birth Branch".
        self.assertEqual(pillars['month']['own_stage']['name'], 'Death')
        self.assertEqual(pillars['year']['own_stage']['name'], 'Capping')
        self.assertEqual(pillars['hour']['own_stage']['name'], 'Birth')
        self.assertIsNone(pillars['day']['own_stage'])
        self.assertEqual(
            {name: pillars[name]['stem_reading']['ten_god'] for name in PILLARS},
            {
                'year': 'indirect_wealth',
                'month': 'eating_god',
                'day': None,
                'hour': 'rob_wealth',
            },
        )
        (clash,) = result['relationships'].values()
        self.assertEqual(clash['pairing']['label'], 'Month–Day')
        self.assertEqual(clash['condition']['season'], 'summer')
        self.assertTrue(
            clash['condition']['sentence'].startswith('The seasonal question matters')
        )


class TestReadingSelection(unittest.TestCase):
    def setUp(self):
        self.canon = load_canon()

    def test_every_day_master_in_every_pillar_on_every_branch(self):
        for day_master, pillar, branch in itertools.product(
            STEM_CHARS, PILLARS, BRANCH_CHARS
        ):
            if pillar == 'day' and same_polarity_stem(branch) != same_polarity_stem(
                BRANCH_CHARS[STEM_CHARS.index(day_master) % 2]
            ):
                continue
            stem = day_master if pillar == 'day' else same_polarity_stem(branch)
            pillars = {name: ('甲', '子') for name in PILLARS}
            pillars['day'] = (
                day_master,
                '子' if STEM_CHARS.index(day_master) % 2 == 0 else '丑',
            )
            pillars[pillar] = (stem, branch)
            with self.subTest(day_master=day_master, pillar=pillar, branch=branch):
                self.check_pillar(reading(pillars), pillars, pillar)

    def check_pillar(self, result, pillars, pillar):
        canon = self.canon
        day_master = pillars['day'][0]
        stem, branch = pillars[pillar]
        got = result['pillars'][pillar]
        self.assertEqual(
            texts(got['lens']), [canon['day_masters'][day_master]['pillars'][pillar]]
        )
        if pillar == 'day':
            self.assertEqual(got['stem_reading']['kind'], 'day_master')
            self.assertEqual(
                texts(got['stem_reading']['paragraphs']),
                canon['day_masters'][day_master]['core'],
            )
            self.assertIsNone(got['own_stage'])
        else:
            god = GODS[LunarUtil.SHI_SHEN[day_master + stem]]
            self.assertEqual(got['stem_reading']['ten_god'], god)
            self.assertEqual(
                texts(got['stem_reading']['paragraphs']),
                [canon['ten_gods'][god]['stems'][pillar]],
            )
            own = canon['cycle']['table'][stem][branch]
            self.assertEqual(got['own_stage']['stage'], own)
            self.assertEqual(
                texts(got['own_stage']['paragraphs']), canon['stages'][own]['core']
            )
            self.assertEqual(
                result['roles'][god]['stems'][pillar], got['stem_reading']['paragraphs']
            )
        self.assertEqual(
            texts(got['ground']), [canon['branches'][branch]['pillars'][pillar]]
        )
        self.assertEqual(texts(got['ground_about']), canon['branches'][branch]['core'])
        meets = canon['stems_on_branches'][day_master]['branches'][branch]
        if pillar != 'day':
            meets = ' '.join(
                s for s in sentences(meets) if not s.startswith('As a Day Pillar')
            )
        self.assertEqual(texts(got['meets']), [meets])
        stage = canon['cycle']['table'][day_master][branch]
        self.assertEqual(got['stage']['stage'], stage)
        self.assertEqual(
            texts(got['stage']['paragraphs']),
            [canon['stages'][stage]['pillars'][pillar]],
        )

    def test_the_day_pillar_sentences_stay_on_the_day_only(self):
        found = 0
        for day_master, branch in itertools.product(STEM_CHARS, BRANCH_CHARS):
            text = self.canon['stems_on_branches'][day_master]['branches'][branch]
            if 'As a Day Pillar' not in text:
                continue
            found += 1
            as_day = reading(
                {
                    'year': ('甲', '子'),
                    'month': ('甲', '子'),
                    'day': (day_master, branch),
                    'hour': ('甲', '子'),
                }
            )
            self.assertIn(
                'As a Day Pillar', as_day['pillars']['day']['meets'][0]['text']
            )
            as_hour = reading(
                {
                    'year': ('甲', '子'),
                    'month': ('甲', '子'),
                    'day': (
                        day_master,
                        '子' if STEM_CHARS.index(day_master) % 2 == 0 else '丑',
                    ),
                    'hour': (same_polarity_stem(branch), branch),
                }
            )
            self.assertNotIn(
                'As a Day Pillar', as_hour['pillars']['hour']['meets'][0]['text']
            )
        self.assertEqual(found, 6)

    def test_every_relationship_the_engine_finds_is_read(self):
        families = {
            'stem_combination': 'stem_combinations',
            'branch_combination': 'six_harmonies',
            'branch_clash': 'clashes',
            'harmony_frame': 'three_harmonies',
        }
        seen = set()
        for stems in itertools.product('甲己丁壬', repeat=4):
            for branches in (
                ('子', '午', '丑', '未'),
                ('申', '子', '辰', '巳'),
                ('寅', '亥', '卯', '戌'),
            ):
                pillars = dict(
                    zip(PILLARS, zip(stems, branches, strict=True), strict=True)
                )
                result = reading(pillars)
                for interaction in detect_interactions(pillars):
                    got = result['relationships'][interaction['id']]
                    family = self.canon[families[interaction['kind']]]
                    members = [m['pillar'] for m in interaction['members']]
                    chars = {m['char'] for m in interaction['members']}
                    self.assertEqual(got['kind'], interaction['kind'])
                    self.assertEqual(
                        set(got['entry']['title'].split(' — ')[0]) & chars, chars
                    )
                    if interaction['kind'] == 'harmony_frame':
                        self.assertIsNone(got['pairing'])
                    else:
                        first, second = sorted(members, key=PILLARS.index)
                        self.assertEqual(
                            got['pairing'],
                            family['pairings'][f'{first.title()}–{second.title()}'],
                        )
                    if interaction['kind'] == 'stem_combination':
                        if 'day' in members:
                            self.assertIn(
                                'is the Day Master combining',
                                got['with_day_master']['label'],
                            )
                            self.assertIsNone(got['neither_day_master'])
                        else:
                            self.assertIsNone(got['with_day_master'])
                            self.assertEqual(
                                got['neither_day_master']['label'],
                                'When neither Stem is the Day Master',
                            )
                        self.assertEqual(
                            got['dynamic']['label'], 'The relational dynamic'
                        )
                        self.assertEqual(
                            got['mechanics'], self.canon['combination_mechanics']
                        )
                    seen.add(interaction['kind'])
        self.assertEqual(seen, set(families))

    def test_the_zi_wu_clash_says_what_its_season_decides(self):
        for month in BRANCH_CHARS:
            pillars = {
                'year': ('甲', '子'),
                'month': (same_polarity_stem(month), month),
                'day': ('甲', '午'),
                'hour': ('甲', '寅'),
            }
            clash = next(
                r
                for key, r in reading(pillars)['relationships'].items()
                if key.startswith('branch_clash') and key.endswith('year-day')
            )
            season = SEASON_OF[month]
            self.assertEqual(clash['condition']['season'], season)
            expected = {
                'summer': 'in summer',
                'winter': 'In winter',
                'spring': 'In neutral seasons',
                'autumn': 'In neutral seasons',
            }[season]
            self.assertIn(expected, clash['condition']['sentence'])


class TestReadingCanonChecks(unittest.TestCase):
    def test_the_canon_as_packaged_passes(self):
        check_reading_canon(load_canon())

    def test_a_changed_sentence_or_table_is_refused(self):
        canon = copy.deepcopy(load_canon())
        canon['stems_on_branches']['壬']['branches']['午'] = canon['stems_on_branches'][
            '壬'
        ]['branches']['午'].replace('As a Day Pillar', 'As the Day Pillar')
        with self.assertRaises(CanonError):
            check_reading_canon(canon)
        canon = copy.deepcopy(load_canon())
        canon['cycle']['table']['甲']['亥'] = 2
        with self.assertRaises(CanonError):
            check_reading_canon(canon)


if __name__ == '__main__':
    unittest.main()
