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
from tests.test_canon import parsed_texts

PILLARS = ('year', 'month', 'day', 'hour')
# A sentence ends at its stop, or just after a closing quote that follows it.
SENTENCE_END = re.compile(r'(?<=[.!?])\s+|(?<=[.!?]["”])\s+')
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
# The branches' pinyin as the app writes them, with no diacritics.
BRANCH_PINYIN = dict(
    zip(
        BRANCH_CHARS,
        'Zi Chou Yin Mao Chen Si Wu Wei Shen You Xu Hai'.split(),
        strict=True,
    )
)


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
        # Beside the Zi-Wu clash: Zi and Chen half a Water frame, Zi punishes Mao,
        # and Mao and Chen harm each other.
        self.assertEqual(
            sorted(r['kind'] for r in result['relationships'].values()),
            ['branch_clash', 'half_frame', 'harm', 'punishment'],
        )
        (clash,) = [
            r for r in result['relationships'].values() if r['kind'] == 'branch_clash'
        ]
        self.assertEqual(clash['pairing']['label'], 'Month–Day')
        self.assertEqual(clash['condition']['season'], 'summer')
        self.assertTrue(
            clash['condition']['sentence'].startswith('The seasonal question matters')
        )
        # Its ring runs from Yang Water's Birth on the Monkey, each branch with its pinyin.
        self.assertEqual(
            [
                (s['stage'], s['branch'], s['pinyin'])
                for s in result['day_master']['cycle']['ring']
            ],
            [
                (1, '申', 'Shen'),
                (2, '酉', 'You'),
                (3, '戌', 'Xu'),
                (4, '亥', 'Hai'),
                (5, '子', 'Zi'),
                (6, '丑', 'Chou'),
                (7, '寅', 'Yin'),
                (8, '卯', 'Mao'),
                (9, '辰', 'Chen'),
                (10, '巳', 'Si'),
                (11, '午', 'Wu'),
                (12, '未', 'Wei'),
            ],
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

    def test_the_ring_names_every_branch_by_its_pinyin(self):
        # The ring pairs each branch's character with its pinyin, which carries no
        # diacritics, for every Day Master.
        for day_master in STEM_CHARS:
            pillars = {name: ('甲', '子') for name in PILLARS}
            pillars['day'] = (
                day_master,
                '子' if STEM_CHARS.index(day_master) % 2 == 0 else '丑',
            )
            ring = reading(pillars)['day_master']['cycle']['ring']
            with self.subTest(day_master=day_master):
                self.assertEqual([s['stage'] for s in ring], list(range(1, 13)))
                self.assertEqual(
                    sorted(s['branch'] for s in ring), sorted(BRANCH_CHARS)
                )
                for s in ring:
                    table = self.canon['cycle']['table'][day_master]
                    self.assertEqual(s['stage'], table[s['branch']])
                    self.assertEqual(s['pinyin'], BRANCH_PINYIN[s['branch']])
                    self.assertRegex(s['pinyin'], r'^[A-Z][a-z]+$')

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
            'half_frame': 'three_harmonies',
            'directional_combination': 'directional',
            'punishment': 'punishments',
            'half_punishment': 'punishments',
            'self_punishment': 'punishments',
            'harm': 'harms',
        }
        seen = set()
        for stems in itertools.product('甲己丁壬', repeat=4):
            for branches in (
                ('子', '午', '丑', '未'),
                ('申', '子', '辰', '巳'),
                ('寅', '亥', '卯', '戌'),
                ('寅', '巳', '申', '辰'),
                ('亥', '子', '丑', '午'),
                ('辰', '辰', '卯', '酉'),
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
                    head = got['entry']['title'].split(' — ')[0]
                    if interaction['kind'] == 'self_punishment':
                        self.assertEqual(head, '自刑')
                    else:
                        self.assertEqual(set(head) & chars, chars)
                    # Only the canon's pairs with pairing passages read one.
                    if len(members) == 3 or not family['pairings']:
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
                    # The list's line is one whole sentence of what the reading says:
                    # its pairing where it has one, else its own paragraphs.
                    said = [
                        sentence
                        for p in (
                            [got['pairing']]
                            if got['pairing']
                            else got['entry']['paragraphs']
                        )
                        for sentence in SENTENCE_END.split(p['text'])
                    ]
                    self.assertIn(got['line'], said)
                    seen.add(interaction['kind'])
        self.assertEqual(seen, set(families))

    def test_the_list_reads_the_canons_sentence_about_each_form(self):
        def line(branches, kind):
            pillars = dict(
                zip(PILLARS, zip('甲甲甲甲', branches, strict=True), strict=True)
            )
            (found,) = [
                r['line']
                for r in reading(pillars)['relationships'].values()
                if r['kind'] == kind
            ]
            return found

        # A half-frame: the sentence on its own pair, which names the branch it lacks.
        self.assertEqual(
            line('申子戌戌', 'half_frame'),
            'The half-frames: Shen-Zi without Chen creates a powerful current with no'
            " reservoir — intelligence that flows but isn't stored.",
        )
        self.assertEqual(
            line('子辰戌戌', 'half_frame'),
            'Zi-Chen without Shen creates a deep reservoir with no source — depth'
            ' without the generating mechanism to refill it.',
        )
        # Two of a punishment triangle: that pair's sentence.
        self.assertEqual(
            line('寅申卯卯', 'half_punishment'),
            'Yin-Shen creates a friction between growth and cutting — the person builds'
            ' and destroys in alternating cycles.',
        )
        self.assertEqual(
            line('丑戌卯卯', 'half_punishment'),
            'Chou-Xu is the cold vault versus the hot vault — both guarding, neither'
            ' trusting the other.',
        )
        # A whole punishment: its character. The Zi-Mao sentence ends inside quotes.
        self.assertEqual(
            line('寅巳申卯', 'punishment'),
            'The character of this punishment is ingratitude — the classical name means'
            ' the punishment without kindness.',
        )
        self.assertEqual(
            line('丑未戌卯', 'punishment'),
            'The character of this punishment is bullying by strength — the classical'
            ' name means the punishment of relying on power.',
        )
        self.assertEqual(
            line('子卯戌戌', 'punishment'),
            'The character of this punishment is specifically about the violation of'
            ' proper relationships — hence "uncivilized."',
        )
        # A self-punishment: its own branch.
        self.assertEqual(line('辰辰戌戌', 'self_punishment'), 'Too much stored Water.')
        # A harm: what it does in practice, which runs both ways.
        self.assertEqual(
            line('寅巳卯卯', 'harm'),
            'In practice: the ambitious growth domain and the transformative intensity'
            ' domain interfere with each other through their opposing relationships to'
            ' the deep creative source.',
        )
        # A directional combination: its entry's first sentence.
        self.assertEqual(
            line('亥子丑戌', 'directional_combination'), 'The full winter.'
        )
        # A family with pairings: the pairing's first sentence, as before.
        self.assertEqual(
            line('子午戌戌', 'branch_clash'), 'The ancestry collides with the career.'
        )

    def test_each_form_of_a_relationship_reads_its_own_paragraphs(self):
        def read(branches, kind):
            pillars = dict(
                zip(PILLARS, zip('甲甲甲甲', branches, strict=True), strict=True)
            )
            return next(
                r['entry']['paragraphs']
                for r in reading(pillars)['relationships'].values()
                if r['kind'] == kind
            )

        def labels(paragraphs):
            return [p['label'] for p in paragraphs]

        frame = self.canon['three_harmonies']['entries']['申子辰']['paragraphs']
        # Shen and Zi: the frame's opening, their two points and the half-frames;
        # not Chen's point, nor what the whole frame does.
        half = read('申子戌戌', 'half_frame')
        self.assertEqual(
            labels(half), [None, 'Birth point (Shen)', 'Peak point (Zi)', None]
        )
        self.assertEqual(half[0], frame[0])
        self.assertTrue(half[-1]['text'].startswith('The half-frames:'))
        self.assertEqual(len(read('申子辰戌', 'harmony_frame')), len(frame))
        # The Ingratitude triangle whole, and two of its three.
        self.assertEqual(
            labels(read('寅巳申卯', 'punishment')),
            [None, None, None, 'Across pillar positions'],
        )
        self.assertEqual(
            labels(read('寅巳卯卯', 'half_punishment')),
            [None, None, None, 'When two of three are present (half-punishment)'],
        )
        # Bullying by Strength has no pillar paragraph; Zi-Mao has no half.
        self.assertEqual(labels(read('丑未戌卯', 'punishment')), [None, None, None])
        self.assertEqual(
            labels(read('丑未卯卯', 'half_punishment')),
            [None, None, None, 'When two of three are present'],
        )
        self.assertEqual(
            labels(read('子卯戌戌', 'punishment')),
            [None, None, None, 'Across pillar positions'],
        )
        # A self-punishment reads its own branch between the entry's opening and close.
        self.assertEqual(
            labels(read('辰辰戌戌', 'self_punishment')),
            [None, '辰辰 Chen-Chen (Dragon meets Dragon)', None],
        )
        # Harms and directional combinations read their whole entry.
        self.assertEqual(
            read('子未戌戌', 'harm'),
            self.canon['harms']['entries']['子未']['paragraphs'],
        )
        self.assertEqual(
            read('亥子丑戌', 'directional_combination'),
            self.canon['directional']['entries']['亥子丑']['paragraphs'],
        )

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


def every_selection():
    """Pillars for every path a reading takes: every Day Master under every stem on every
    branch, in every pillar; every stem pair and branch pair in every pillar pairing; and
    every frame, directional combination and punishment triangle in every placement."""
    for day_master, stem, branch, pillar in itertools.product(
        STEM_CHARS, STEM_CHARS, BRANCH_CHARS, PILLARS
    ):
        pillars = {name: ('甲', '子') for name in PILLARS}
        pillars['day'] = (day_master, branch if pillar == 'day' else '子')
        if pillar != 'day':
            pillars[pillar] = (stem, branch)
        yield pillars
    for first, second in itertools.combinations(PILLARS, 2):
        for a, b in itertools.product(STEM_CHARS, repeat=2):
            pillars = {name: ('甲', '子') for name in PILLARS}
            pillars[first], pillars[second] = (a, '子'), (b, '子')
            yield pillars
        for a, b in itertools.product(BRANCH_CHARS, repeat=2):
            pillars = {name: ('甲', '寅') for name in PILLARS}
            pillars[first], pillars[second] = ('甲', a), ('甲', b)
            yield pillars
    for frame in (
        *('申子辰', '亥卯未', '寅午戌', '巳酉丑'),
        *('亥子丑', '寅卯辰', '巳午未', '申酉戌'),
        *('寅巳申', '丑未戌'),
    ):
        for members in itertools.permutations(PILLARS, 3):
            pillars = {name: ('甲', '寅') for name in PILLARS}
            for name, branch in zip(members, frame, strict=True):
                pillars[name] = ('甲', branch)
            yield pillars


def paragraph_texts(value, found):
    if isinstance(value, dict):
        if set(value) == {'label', 'text'}:
            found.add(value['text'])
        for inner in value.values():
            paragraph_texts(inner, found)
    elif isinstance(value, list):
        for inner in value:
            paragraph_texts(inner, found)
    return found


class TestWhatTheReadingsCover(unittest.TestCase):
    def test_every_paragraph_is_read_by_some_chart(self):
        # Every family the canon defines is detected, so every paragraph the canon's
        # parser reads is in some chart's reading.
        canon = load_canon()
        shown = set()
        for pillars in every_selection():
            paragraph_texts(reading(pillars), shown)
        self.assertEqual(set(parsed_texts(canon)) - shown, set())


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

    def test_a_form_without_its_sentence_is_refused(self):
        def without(family, key, words, instead):
            canon = copy.deepcopy(load_canon())
            paragraphs = canon[family]['entries'][key]['paragraphs']
            (index,) = [i for i, p in enumerate(paragraphs) if words in p['text']]
            paragraphs[index] = {
                **paragraphs[index],
                'text': paragraphs[index]['text'].replace(words, instead),
            }
            return canon

        for canon in (
            without('harms', '寅巳', 'In practice:', 'In effect:'),
            without(
                'punishments', '丑未戌', 'The character of this', 'The nature of this'
            ),
            without(
                'three_harmonies', '巳酉丑', 'You-Chou without Si', 'You-Chou alone'
            ),
            without('punishments', '寅巳申', 'Si-Shen creates', 'Si and Shen create'),
        ):
            with self.assertRaises(CanonError):
                check_reading_canon(canon)


if __name__ == '__main__':
    unittest.main()
