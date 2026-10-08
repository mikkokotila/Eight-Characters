import copy
import re
import unittest

from eight_characters.canon import BRANCH_CHARS, STEM_CHARS, CanonError, load_canon
from eight_characters.interactions import detect_interactions
from eight_characters.life_stages import life_stage
from eight_characters.luck_context import build_luck_context
from eight_characters.main import _load_hidden_stems_lookup, _load_ten_gods_lookup
from eight_characters.reading import (
    DAY_PILLAR_ONLY,
    SETTLE_SENTENCES,
    build_luck_reading,
    check_reading_canon,
)
from tests.accounts_support import signed_in_client

# The sample of the luck pillar design: 14 August 1975, 07:45, Helsinki, female.
# Natal 乙卯 Yi Mao, 甲申 Jia Shen, 壬辰 Ren Chen, 甲辰 Jia Chen; Day Master 壬 Ren.
SAMPLE = {
    'year': ('乙', '卯'),
    'month': ('甲', '申'),
    'day': ('壬', '辰'),
    'hour': ('甲', '辰'),
}
SAMPLE_REQUEST = {
    'date': '1975-08-14',
    'time': '07:45:00',
    'location': {
        'timezone': 'Europe/Helsinki',
        'latitude': 60.1699,
        'longitude': 24.9384,
    },
    'gender': 'female',
    'include_luck_pillars': True,
    'include_luck_context': True,
    'include_reading': True,
}
# The docs' example: Chengdu, 4 February 1988, 16:30, male. Natal 丁卯 Ding Mao,
# 癸丑 Gui Chou, 己丑 Ji Chou, 壬申 Ren Shen: a Year–Hour Ding–Ren combination, which
# its first luck pillar, 壬子 Ren Zi, settles by bringing Ren.
CHENGDU_REQUEST = {
    'date': '1988-02-04',
    'time': '16:30:00',
    'location': {
        'timezone': 'Asia/Shanghai',
        'latitude': 30.658,
        'longitude': 104.066,
    },
    'gender': 'male',
    'include_luck_pillars': True,
    'include_luck_context': True,
    'include_reading': True,
}


def sentences(text):
    return re.split(r'(?<=[.!?])\s+|(?<=[.!?]["”])\s+', text)


def plain(texts):
    return [{'label': None, 'text': text} for text in texts]


def decade(sequence, pillar):
    """A luck pillar with what the context and the reading read of it."""
    return {
        'sequence': sequence,
        'stem': {'chinese': pillar[0]},
        'branch': {'chinese': pillar[1]},
    }


def luck_reading(pillars, *luck):
    luck_pillars = [
        decade(sequence, pillar) for sequence, pillar in enumerate(luck, start=1)
    ]
    context = build_luck_context(
        pillars, luck_pillars, _load_hidden_stems_lookup(), _load_ten_gods_lookup()
    )
    return build_luck_reading(
        load_canon(),
        pillars,
        _load_ten_gods_lookup(),
        detect_interactions(pillars),
        luck_pillars,
        context['decades'],
    )


def luck_interactions(pillars, *luck):
    luck_pillars = [
        decade(sequence, pillar) for sequence, pillar in enumerate(luck, start=1)
    ]
    return build_luck_context(
        pillars, luck_pillars, _load_hidden_stems_lookup(), _load_ten_gods_lookup()
    )['decades']


class TestApiLuckReading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = signed_in_client(cls)
        cls.canon = load_canon()

    def four_pillars(self, body):
        response = self.client.post('/api/four_pillars', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_it_comes_with_the_reading_and_the_luck_context(self):
        payload = self.four_pillars(SAMPLE_REQUEST)
        reading = payload['luck_reading']
        self.assertEqual(reading['policy'], 'canon_taxonomy_v1')
        self.assertEqual(reading['language'], 'en')
        self.assertEqual(
            [d['sequence'] for d in reading['decades']],
            [p['sequence'] for p in payload['luck_pillars']['pillars']],
        )
        for missing in ('include_reading', 'include_luck_context'):
            body = {**SAMPLE_REQUEST, missing: False}
            self.assertNotIn('luck_reading', self.four_pillars(body), missing)
        natal = {
            key: value
            for key, value in SAMPLE_REQUEST.items()
            if key not in ('gender', 'include_luck_pillars', 'include_luck_context')
        }
        self.assertNotIn('luck_reading', self.four_pillars(natal))

    def test_a_luck_pillar_reads_its_stem_and_branch_from_the_day_masters_seat(self):
        # 己丑 Ji Chou, the fifth: its 己 is the Direct Officer of the Day Master 壬 Ren,
        # and 壬 stands at its sixth stage, Decline, on 丑 Chou.
        fifth = self.four_pillars(SAMPLE_REQUEST)['luck_reading']['decades'][4]
        role = self.canon['ten_gods']['direct_officer']
        self.assertEqual(
            fifth['stem'],
            {
                'ten_god': 'direct_officer',
                'name': role['name'],
                'relation': role['relation'],
                'core': plain(role['core']),
            },
        )
        self.assertEqual(
            fifth['branch']['about'], plain(self.canon['branches']['丑']['core'])
        )
        self.assertEqual(
            fifth['branch']['meets'],
            plain([self.canon['stems_on_branches']['壬']['branches']['丑']]),
        )
        stage = self.canon['stages'][6]
        self.assertEqual(
            fifth['branch']['stage'],
            {
                'stage': 6,
                'name': stage['name'],
                'chinese': stage['chinese'],
                'paragraphs': plain(stage['core']),
            },
        )

    def test_the_day_pillar_sentences_stay_off_a_luck_pillar(self):
        # 戊子 Wu Zi under a 戊 Day Master: its Day-Pillar sentence is left out.
        pillars = {**SAMPLE, 'day': ('戊', '辰')}
        meets = luck_reading(pillars, ('戊', '子'))['decades'][0]['branch']['meets']
        whole = self.canon['stems_on_branches']['戊']['branches']['子']
        self.assertIn(DAY_PILLAR_ONLY['戊子'], sentences(whole))
        self.assertEqual(len(meets), 1)
        self.assertNotIn(DAY_PILLAR_ONLY['戊子'], sentences(meets[0]['text']))
        self.assertEqual(
            meets[0]['text'],
            ' '.join(s for s in sentences(whole) if s != DAY_PILLAR_ONLY['戊子']),
        )

    def test_its_relationships_read_as_their_entries_read_without_pairing(self):
        fifth = self.four_pillars(SAMPLE_REQUEST)['luck_reading']['decades'][4]
        self.assertEqual(
            sorted(fifth['relationships']),
            ['stem_combination:1:hour-luck', 'stem_combination:1:month-luck'],
        )
        entry = self.canon['stem_combinations']['entries']['甲己']
        for read in fifth['relationships'].values():
            self.assertIsNone(read['pairing'])
            self.assertIsNone(read['with_day_master'])
            self.assertEqual(
                read['neither_day_master']['label'],
                'When neither Stem is the Day Master',
            )
            unlabelled = [p for p in entry['paragraphs'] if p['label'] is None]
            self.assertEqual(read['entry']['paragraphs'], unlabelled)
            # Without a pairing, the list's line is the entry's own first sentence.
            self.assertEqual(read['line'], sentences(unlabelled[0]['text'])[0])
        # A luck stem that combines with the Day Master reads the Day Master's paragraph.
        # 丁酉 Ding You: its 丁 Ding combines with 壬 Ren, and its 酉 You with the Day's
        # 辰 Chen, one of the six harmonies; only a stem combination has that paragraph.
        with_dm = luck_reading(SAMPLE, ('丁', '酉'))['decades'][0]['relationships']
        own = [
            r
            for key, r in with_dm.items()
            if key.startswith('stem_combination:') and key.endswith(':day-luck')
        ]
        self.assertEqual(len(own), 1)
        self.assertEqual(
            own[0]['with_day_master']['label'],
            'When Ren is the Day Master combining with Ding',
        )

    def test_the_luck_pillar_brings_the_peak_the_natal_birth_and_storage_cradle(self):
        # 戊子 Wu Zi, the fourth: Zi is the Peak of 申子辰, whose Birth 申 and Storage 辰
        # the natal chart holds without it, twice: Day and Hour each hold 辰.
        fourth = self.four_pillars(SAMPLE_REQUEST)['luck_reading']['decades'][3]
        self.assertEqual(
            fourth['settles'],
            [
                {
                    'source': 'cradle',
                    'natal': None,
                    'by': [
                        'harmony_frame:18:month-day-luck',
                        'harmony_frame:18:month-hour-luck',
                    ],
                    'sentence': SETTLE_SENTENCES['cradle'],
                }
            ],
        )
        # A natal chart that holds the Peak already cradles nothing.
        held = {**SAMPLE, 'year': ('甲', '子')}
        self.assertEqual(
            [
                s
                for s in luck_reading(held, ('戊', '子'))['decades'][0]['settles']
                if s['source'] == 'cradle'
            ],
            [],
        )

    def test_a_natal_year_hour_stem_combination_becomes_real(self):
        payload = self.four_pillars(CHENGDU_REQUEST)
        self.assertEqual(payload['luck_pillars']['pillars'][0]['stem']['chinese'], '壬')
        natal = [
            r
            for r in payload['luck_context']['decades'][0]['interactions']
            if r['kind'] == 'stem_combination'
        ]
        self.assertEqual([m['pillar'] for m in natal[0]['members']], ['year', 'luck'])
        year_hour = next(
            r['id']
            for r in detect_interactions(
                {
                    'year': ('丁', '卯'),
                    'month': ('癸', '丑'),
                    'day': ('己', '丑'),
                    'hour': ('壬', '申'),
                }
            )
            if r['kind'] == 'stem_combination'
        )
        self.assertTrue(year_hour.endswith(':year-hour'), year_hour)
        settles = payload['luck_reading']['decades'][0]['settles']
        self.assertIn(
            {
                'source': 'year_hour_stems',
                'natal': year_hour,
                'by': [natal[0]['id']],
                'sentence': SETTLE_SENTENCES['year_hour_stems'],
            },
            settles,
        )
        # Only a luck stem that is one of the two settles it.
        luck_pillars = payload['luck_pillars']['pillars']
        for later in payload['luck_reading']['decades'][1:]:
            stem = luck_pillars[later['sequence'] - 1]['stem']['chinese']
            settled = [s for s in later['settles'] if s['source'] == 'year_hour_stems']
            self.assertEqual(bool(settled), stem in ('丁', '壬'), stem)

    def test_a_natal_year_hour_branch_relationship_is_taken_up(self):
        # Year 子 and Hour 午 clash, too far apart to count; a luck 子 clashes the Hour's 午.
        pillars = {
            'year': ('甲', '子'),
            'month': ('丙', '寅'),
            'day': ('戊', '辰'),
            'hour': ('庚', '午'),
        }
        natal = next(
            r['id'] for r in detect_interactions(pillars) if r['kind'] == 'branch_clash'
        )
        self.assertTrue(natal.endswith(':year-hour'), natal)
        clash = next(
            r['id']
            for r in luck_interactions(pillars, ('丙', '子'))[0]['interactions']
            if r['kind'] == 'branch_clash'
        )
        self.assertTrue(clash.endswith(':hour-luck'), clash)
        self.assertIn(
            {
                'source': 'year_hour_branches',
                'natal': natal,
                'by': [clash],
                'sentence': SETTLE_SENTENCES['year_hour_branches'],
            },
            luck_reading(pillars, ('丙', '子'))['decades'][0]['settles'],
        )
        # A luck branch that is neither end settles nothing of it.
        self.assertEqual(
            [
                s
                for s in luck_reading(pillars, ('丙', '戌'))['decades'][0]['settles']
                if s['source'] == 'year_hour_branches'
            ],
            [],
        )

    def test_a_natal_half_frame_is_completed(self):
        # Year 申 and Month 子 hold the half-frame Shen-Zi; a luck 辰 completes 申子辰 and
        # takes the half in for the decade.
        pillars = {
            'year': ('甲', '申'),
            'month': ('丙', '子'),
            'day': ('戊', '午'),
            'hour': ('庚', '午'),
        }
        half = next(
            r['id'] for r in detect_interactions(pillars) if r['kind'] == 'half_frame'
        )
        luck = luck_interactions(pillars, ('戊', '辰'))[0]
        absorbed = next(a for a in luck['absorbed'] if a['id'] == half)
        self.assertIn(
            {
                'source': 'half_frame',
                'natal': half,
                'by': absorbed['by'],
                'sentence': SETTLE_SENTENCES['half_frame'],
            },
            luck_reading(pillars, ('戊', '辰'))['decades'][0]['settles'],
        )

    def test_every_luck_pillar_reads_for_every_day_master(self):
        # Each of the sixty pillars as the luck pillar of a chart of each Day Master.
        sixty = [(STEM_CHARS[n % 10], BRANCH_CHARS[n % 12]) for n in range(60)]
        for day_master in STEM_CHARS:
            pillars = {**SAMPLE, 'day': (day_master, '辰')}
            read = luck_reading(pillars, *sixty)
            for d, (stem, branch) in zip(read['decades'], sixty, strict=True):
                stage = life_stage(day_master, branch)
                self.assertEqual(
                    d['branch']['stage']['stage'], stage, (day_master, stem, branch)
                )
                self.assertEqual(
                    d['branch']['stage']['paragraphs'],
                    plain(self.canon['stages'][stage]['core']),
                )
                self.assertEqual(
                    d['branch']['about'], plain(self.canon['branches'][branch]['core'])
                )
                for r in d['relationships'].values():
                    self.assertIsNone(r['pairing'])
                    self.assertTrue(r['line'])
                for s in d['settles']:
                    self.assertEqual(s['sentence'], SETTLE_SENTENCES[s['source']])
                    self.assertTrue(s['by'])
                    self.assertTrue(all(i in d['relationships'] for i in s['by']))

    def test_a_canon_without_a_sentence_it_waits_on_is_refused(self):
        check_reading_canon(self.canon)
        canon = copy.deepcopy(self.canon)
        pairing = canon['stem_combinations']['pairings']['Year–Hour']
        pairing['text'] = pairing['text'].replace('Luck Pillar', 'luck pillar')
        with self.assertRaisesRegex(CanonError, 'waits for a luck pillar'):
            check_reading_canon(canon)
        canon = copy.deepcopy(self.canon)
        paragraph = canon['three_harmonies']['introduction'][1]
        paragraph['text'] = paragraph['text'].replace('cradle (拱)', 'cradle')
        with self.assertRaisesRegex(CanonError, r'waits for a luck pillar \(cradle\)'):
            check_reading_canon(canon)


if __name__ == '__main__':
    unittest.main()
