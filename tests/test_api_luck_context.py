import unittest

from fastapi.testclient import TestClient

from eight_characters.interactions import detect_interactions
from eight_characters.luck_context import ELEMENTS, PHASES, build_luck_context
from eight_characters.main import _load_hidden_stems_lookup, _load_ten_gods_lookup, app
from eight_characters.ten_gods import TEN_GOD_NAMES

# The sample of the luck pillar design: 14 August 1975, 07:45, Helsinki, female.
# Natal 乙卯 Yi Mao, 甲申 Jia Shen, 壬辰 Ren Chen, 甲辰 Jia Chen; Day Master 壬 Ren.
SAMPLE = {
    'year': ('乙', '卯'),
    'month': ('甲', '申'),
    'day': ('壬', '辰'),
    'hour': ('甲', '辰'),
}
SAMPLE_DECADES = (
    '乙酉',
    '丙戌',
    '丁亥',
    '戊子',
    '己丑',
    '庚寅',
    '辛卯',
    '壬辰',
    '癸巳',
    '甲午',
)
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
}


def decade(sequence, pillar):
    """A luck pillar with what the context reads of it: its sequence and characters."""
    return {
        'sequence': sequence,
        'stem': {'chinese': pillar[0]},
        'branch': {'chinese': pillar[1]},
    }


def context(pillars, *luck):
    return build_luck_context(
        pillars,
        [decade(sequence, pillar) for sequence, pillar in enumerate(luck, start=1)],
        _load_hidden_stems_lookup(),
        _load_ten_gods_lookup(),
    )


def counts(elements, ten_gods):
    return {
        'elements': {element: elements.get(element, 0) for element in ELEMENTS},
        'ten_gods': {name: ten_gods.get(name, 0) for name in TEN_GOD_NAMES},
    }


# The sample's own counts: eight characters, and its thirteen stem occurrences (three
# visible beside the Day Master, ten hidden).
NATAL_ELEMENTS = {'wood': 4, 'earth': 2, 'metal': 1, 'water': 1}
NATAL_TEN_GODS = {
    'friend': 1,
    'rob_wealth': 2,
    'eating_god': 2,
    'hurting_officer': 4,
    'seven_killings': 3,
    'indirect_resource': 1,
}


class TestLuckContext(unittest.TestCase):
    def test_the_natal_counts(self):
        found = context(SAMPLE)
        self.assertEqual(found['policy'], 'luck_context_v1')
        self.assertEqual(found['natal_counts'], counts(NATAL_ELEMENTS, NATAL_TEN_GODS))
        self.assertEqual(found['decades'], [])

    def test_a_branch_that_completes_two_frames(self):
        # 戊子 Wu Zi: Zi completes Shen-Zi-Chen with the Month and each Chen.
        (found,) = context(SAMPLE, '戊子')['decades']
        self.assertEqual(found['sequence'], 1)
        self.assertEqual(
            [
                (
                    r['char'],
                    r['component'],
                    r['qi_type'],
                    r['ten_god'],
                    r['new_to_chart'],
                    r['phases'],
                )
                for r in found['occurrences']
            ],
            [
                ('戊', 'stem', None, 'seven_killings', False, ['stem']),
                ('癸', 'hidden_stem', 'main', 'rob_wealth', False, ['stem', 'branch']),
            ],
        )
        self.assertEqual({r['pillar'] for r in found['occurrences']}, {'luck'})
        # Ren on Zi: Emperor's Peak, the fifth of the twelve stages.
        self.assertEqual(found['day_master_stage'], 5)
        self.assertEqual(
            [
                (r['char'], r['qi_type'], r['match'], r['phases'])
                for r in found['roots']
            ],
            [('癸', 'main', 'opposite_polarity', ['stem', 'branch'])],
        )
        self.assertEqual(
            [(r['id'], r['phases']) for r in found['interactions']],
            [
                ('harmony_frame:18:month-day-luck', ['stem', 'branch']),
                ('harmony_frame:18:month-hour-luck', ['stem', 'branch']),
                ('punishment:34:year-luck', ['stem', 'branch']),
            ],
        )
        self.assertEqual(found['absorbed'], [])
        self.assertEqual(
            found['counts'],
            {
                'stem': counts(
                    {**NATAL_ELEMENTS, 'earth': 3, 'water': 2},
                    {**NATAL_TEN_GODS, 'seven_killings': 4, 'rob_wealth': 3},
                ),
                'branch': counts(
                    {**NATAL_ELEMENTS, 'water': 2},
                    {**NATAL_TEN_GODS, 'rob_wealth': 3},
                ),
            },
        )

    def test_a_stem_acts_only_in_its_stem_phase(self):
        # 己丑 Ji Chou: Ji combines with the Jia of Month and Hour, for five years.
        (found,) = context(SAMPLE, '己丑')['decades']
        self.assertEqual(
            [(r['id'], r['phases']) for r in found['interactions']],
            [
                ('stem_combination:1:month-luck', ['stem']),
                ('stem_combination:1:hour-luck', ['stem']),
            ],
        )
        # The chart has no Direct Officer and no Direct Resource of its own.
        self.assertEqual(
            [
                (r['char'], r['ten_god'], r['new_to_chart'])
                for r in found['occurrences']
            ],
            [
                ('己', 'direct_officer', True),
                ('己', 'direct_officer', True),
                ('癸', 'rob_wealth', False),
                ('辛', 'direct_resource', True),
            ],
        )
        # Ren on Chou: Decline, the sixth stage.
        self.assertEqual(found['day_master_stage'], 6)
        self.assertEqual(
            [(r['char'], r['qi_type'], r['match']) for r in found['roots']],
            [('癸', 'middle', 'opposite_polarity')],
        )
        self.assertEqual(
            found['counts']['stem'],
            counts(
                {**NATAL_ELEMENTS, 'earth': 4},
                {
                    **NATAL_TEN_GODS,
                    'direct_officer': 2,
                    'rob_wealth': 3,
                    'direct_resource': 1,
                },
            ),
        )
        self.assertEqual(
            found['counts']['branch'],
            counts(
                {**NATAL_ELEMENTS, 'earth': 3},
                {
                    **NATAL_TEN_GODS,
                    'direct_officer': 1,
                    'rob_wealth': 3,
                    'direct_resource': 1,
                },
            ),
        )

    def test_an_exact_root(self):
        # 丁亥 Ding Hai: Hai holds Ren itself.
        (found,) = context(SAMPLE, '丁亥')['decades']
        self.assertEqual(
            [
                (r['char'], r['ten_god'], r['new_to_chart'])
                for r in found['occurrences']
            ],
            [
                ('丁', 'direct_wealth', True),
                ('壬', 'friend', False),
                ('甲', 'eating_god', False),
            ],
        )
        self.assertEqual(found['day_master_stage'], 4)
        self.assertEqual(
            [(r['char'], r['match']) for r in found['roots']], [('壬', 'exact_stem')]
        )
        self.assertEqual(
            [(r['id'], r['phases']) for r in found['interactions']],
            [
                ('stem_combination:4:day-luck', ['stem']),
                ('half_frame:23:year-luck', ['stem', 'branch']),
                ('harm:43:month-luck', ['stem', 'branch']),
            ],
        )

    def test_a_natal_half_absorbed_for_the_decade(self):
        natal = {
            name: ('甲', branch)
            for name, branch in zip(SAMPLE, '申子戌戌', strict=True)
        }
        self.assertEqual(
            [r['id'] for r in detect_interactions(natal)], ['half_frame:22:year-month']
        )
        (found,) = context(natal, '甲辰')['decades']
        self.assertEqual(
            found['absorbed'],
            [
                {
                    'id': 'half_frame:22:year-month',
                    'by': ['harmony_frame:18:year-month-luck'],
                    'phases': ['stem', 'branch'],
                }
            ],
        )

    def test_every_decade_counts_ten_then_nine_characters(self):
        found = context(SAMPLE, *SAMPLE_DECADES)
        self.assertEqual([d['sequence'] for d in found['decades']], list(range(1, 11)))
        for d in found['decades']:
            occurrences = len(d['occurrences'])
            for phase, characters, stems in (
                ('stem', 10, 13 + occurrences),
                ('branch', 9, 13 + occurrences - 1),
            ):
                self.assertEqual(
                    sum(d['counts'][phase]['elements'].values()), characters
                )
                self.assertEqual(sum(d['counts'][phase]['ten_gods'].values()), stems)
            self.assertEqual(list(d['counts']), list(PHASES))

    def test_invalid_luck_pillars_fail_explicitly(self):
        for pillar in ('甲X', 'X子'):
            with self.assertRaises(ValueError):
                context(SAMPLE, pillar)


class TestLuckContextAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_the_sample_chart_through_the_api(self):
        response = self.client.post(
            '/api/four_pillars', json={**SAMPLE_REQUEST, 'include_luck_context': True}
        )
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        natal = {
            name: (pillar['stem']['chinese'], pillar['branch']['chinese'])
            for name, pillar in result['four_pillars'].items()
        }
        self.assertEqual(natal, SAMPLE)
        luck = result['luck_pillars']['pillars']
        self.assertEqual(
            tuple(p['stem']['chinese'] + p['branch']['chinese'] for p in luck),
            SAMPLE_DECADES,
        )
        self.assertEqual(result['luck_context'], context(SAMPLE, *SAMPLE_DECADES))

    def test_the_context_is_opt_in_and_needs_the_luck_pillars(self):
        response = self.client.post('/api/four_pillars', json=SAMPLE_REQUEST)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('luck_context', response.json())
        response = self.client.post(
            '/api/four_pillars',
            json={
                **SAMPLE_REQUEST,
                'include_luck_pillars': False,
                'include_luck_context': True,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            'include_luck_context requires include_luck_pillars',
            response.json()['detail'],
        )

    def test_openapi_describes_the_flag(self):
        schema = self.client.get('/openapi.json').json()['components']['schemas'][
            'FourPillarsRequest'
        ]
        flag = schema['properties']['include_luck_context']
        self.assertEqual((flag['type'], flag['default']), ('boolean', False))


if __name__ == '__main__':
    unittest.main()
