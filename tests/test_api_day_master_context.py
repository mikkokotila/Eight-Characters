import copy
import itertools
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from lunar_python.util import LunarUtil

from eight_characters.day_master_context import build_day_master_context
from eight_characters.main import (
    _load_hidden_stems_lookup,
    _load_ten_gods_lookup,
    app,
)

NAMES = ('year', 'month', 'day', 'hour')
STEMS = '甲乙丙丁戊己庚辛壬癸'
BRANCHES = '子丑寅卯辰巳午未申酉戌亥'
# Independent character-level reference: no runtime element or seasonal helpers.
ELEMENT = dict(
    zip(
        STEMS,
        (
            'wood',
            'wood',
            'fire',
            'fire',
            'earth',
            'earth',
            'metal',
            'metal',
            'water',
            'water',
        ),
        strict=True,
    )
)
QI = ('main', 'middle', 'residual')
CANONICAL = dict(
    zip(NAMES, [('丁', '卯'), ('癸', '丑'), ('己', '丑'), ('壬', '申')], strict=True)
)
LOCATION = {'timezone': 'Asia/Shanghai', 'longitude': 104.066, 'latitude': 30.658}


def context(pillars):
    return build_day_master_context(
        pillars, _load_hidden_stems_lookup(), _load_ten_gods_lookup()
    )


class TestDayMasterContext(unittest.TestCase):
    def test_canonical_identity_season_and_exact_root_evidence(self):
        result = context(CANONICAL)
        self.assertEqual(result['policy'], 'natal_presence_v1')
        self.assertEqual(
            result['day_master'],
            {'char': '己', 'pinyin': 'Ji', 'element': 'earth', 'polarity': 'Yin'},
        )
        self.assertEqual(result['season']['name'], 'winter')
        self.assertEqual(result['season']['element'], 'water')
        self.assertEqual(result['season']['month_branch']['element'], 'earth')
        self.assertEqual(
            [e['char'] for e in result['season']['hidden_stems']], ['己', '癸', '辛']
        )
        self.assertEqual(
            [
                (e['pillar'], e['branch'], e['char'], e['qi_type'], e['match'])
                for e in result['roots']
            ],
            [
                ('month', '丑', '己', 'main', 'exact_stem'),
                ('day', '丑', '己', 'main', 'exact_stem'),
                ('hour', '申', '戊', 'residual', 'opposite_polarity'),
            ],
        )
        self.assertEqual(
            [
                (e['pillar'], e['char'], e['component'])
                for e in result['support']['resources']
            ],
            [('year', '丁', 'stem')],
        )
        self.assertEqual(len(result['support']['companions']), 3)

    def test_roots_for_all_ten_day_masters_twelve_branches_and_four_positions(self):
        for dm, branch, pillar in itertools.product(STEMS, BRANCHES, NAMES):
            source = {name: (dm, '子') for name in NAMES}
            source[pillar] = (dm, branch)
            result = [e for e in context(source)['roots'] if e['pillar'] == pillar]
            expected = [
                (c, QI[i], 'exact_stem' if c == dm else 'opposite_polarity')
                for i, c in enumerate(LunarUtil.ZHI_HIDE_GAN[branch])
                if ELEMENT[c] == ELEMENT[dm]
            ]
            with self.subTest(dm=dm, branch=branch, pillar=pillar):
                self.assertEqual(
                    [(e['char'], e['qi_type'], e['match']) for e in result], expected
                )
                self.assertTrue(
                    all(
                        e['component'] == 'hidden_stem' and e['branch'] == branch
                        for e in result
                    )
                )

    def test_support_roles_against_lunar_reference_for_all_visible_pairs(self):
        for dm, target in itertools.product(STEMS, repeat=2):
            source = {name: (target, '子') for name in NAMES}
            source['day'] = (dm, '子')
            result = context(source)['support']
            reference = LunarUtil.SHI_SHEN[dm + target]
            for group, allowed in [
                ('companions', ('比肩', '劫财')),
                ('resources', ('正印', '偏印')),
            ]:
                visible = [e for e in result[group] if e['component'] == 'stem']
                self.assertEqual(
                    [e['pillar'] for e in visible],
                    ['year', 'month', 'hour'] if reference in allowed else [],
                )
                self.assertTrue(
                    all(e['qi_type'] is None and e['branch'] is None for e in visible)
                )

    def test_hidden_support_against_lunar_reference(self):
        for dm, branch in itertools.product(STEMS, BRANCHES):
            source = {name: (dm, branch) for name in NAMES}
            support = context(source)['support']
            for group, allowed in [
                ('companions', ('比肩', '劫财')),
                ('resources', ('正印', '偏印')),
            ]:
                expected = [
                    (name, char, QI[i])
                    for name in NAMES
                    for i, char in enumerate(LunarUtil.ZHI_HIDE_GAN[branch])
                    if LunarUtil.SHI_SHEN[dm + char] in allowed
                ]
                self.assertEqual(
                    [
                        (e['pillar'], e['char'], e['qi_type'])
                        for e in support[group]
                        if e['component'] == 'hidden_stem'
                    ],
                    expected,
                )

    def test_all_months_use_declared_season_groups_not_branch_elements(self):
        for chars, name, element in [
            ('寅卯辰', 'spring', 'wood'),
            ('巳午未', 'summer', 'fire'),
            ('申酉戌', 'autumn', 'metal'),
            ('亥子丑', 'winter', 'water'),
        ]:
            for char in chars:
                source = {**CANONICAL, 'month': ('甲', char)}
                season = context(source)['season']
                self.assertEqual((season['name'], season['element']), (name, element))
                self.assertEqual(season['basis'], 'traditional_month_branch_groups')
                self.assertEqual(season['month_branch']['char'], char)
                self.assertEqual(
                    [e['char'] for e in season['hidden_stems']],
                    LunarUtil.ZHI_HIDE_GAN[char],
                )
                if char in '辰未戌丑':
                    self.assertEqual(season['month_branch']['element'], 'earth')
                    self.assertEqual(season['hidden_stems'][0]['element'], 'earth')

    def test_self_is_excluded_but_other_identical_stems_and_repeated_roots_remain(self):
        result = context({name: ('甲', '寅') for name in NAMES})
        self.assertEqual(len(result['roots']), 4)
        self.assertEqual(len(result['support']['companions']), 7)
        self.assertFalse(
            any(
                e['pillar'] == 'day' and e['component'] == 'stem'
                for e in result['support']['companions']
            )
        )

    def test_resource_is_not_a_root_and_visible_companions_are_not_roots(self):
        result = context({name: ('甲', '子') for name in NAMES})
        self.assertEqual(result['roots'], [])
        self.assertEqual(len(result['support']['resources']), 4)
        self.assertEqual(len(result['support']['companions']), 3)

    def test_absence_is_explicit_without_fabricated_support(self):
        source = {name: ('戊', '戌') for name in NAMES}
        source['day'] = ('甲', '戌')
        result = context(source)
        self.assertEqual(result['roots'], [])
        self.assertEqual(result['support'], {'companions': [], 'resources': []})

    def test_relationships_do_not_remove_or_transform_natal_evidence(self):
        # 寅/申 clash and 甲/己 combination: no roots are removed or repainted.
        source = dict(
            zip(
                NAMES,
                [('甲', '寅'), ('己', '申'), ('甲', '寅'), ('己', '申')],
                strict=True,
            )
        )
        self.assertEqual(
            [(e['pillar'], e['char']) for e in context(source)['roots']],
            [('year', '甲'), ('day', '甲')],
        )

    def test_deterministic_non_mutating_and_independently_owned_records(self):
        source = copy.deepcopy(CANONICAL)
        hidden = copy.deepcopy(_load_hidden_stems_lookup())
        gods = copy.deepcopy(_load_ten_gods_lookup())
        original = copy.deepcopy((source, hidden, gods))
        result = build_day_master_context(source, hidden, gods)
        self.assertEqual((source, hidden, gods), original)
        self.assertEqual(result, context(dict(reversed(list(source.items())))))
        result['season']['hidden_stems'][0]['char'] = '甲'
        self.assertEqual(result['roots'][0]['char'], '己')
        self.assertEqual(result['support']['companions'][0]['char'], '己')
        self.assertEqual(context(source)['season']['hidden_stems'][0]['char'], '己')

    def test_invalid_inputs_and_missing_mappings_fail(self):
        for source in [
            {},
            {**CANONICAL, 'extra': ('甲', '子')},
            {**CANONICAL, 'day': ('?', '子')},
            {**CANONICAL, 'day': ('甲', '?')},
            {**CANONICAL, 'day': ('甲',)},
        ]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                context(source)
        for replacement in [[], ['?'], ['己', '己'], ['己', '癸', '辛', '甲']]:
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                build_day_master_context(
                    CANONICAL,
                    {**_load_hidden_stems_lookup(), '丑': replacement},
                    _load_ten_gods_lookup(),
                )
        with self.assertRaises(ValueError):
            build_day_master_context(CANONICAL, {}, _load_ten_gods_lookup())
        with self.assertRaises(ValueError):
            build_day_master_context(CANONICAL, _load_hidden_stems_lookup(), {})


class TestDayMasterContextAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def request(self, **flags):
        return self.client.post(
            '/api/four_pillars',
            json={
                'date': '1988-02-04',
                'time': '16:30',
                'location': LOCATION,
                **flags,
            },
        )

    def test_opt_in_independent_of_other_enrichments(self):
        baseline = self.request()
        result = self.request(include_day_master_context=True)
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data.pop('day_master_context'), context(CANONICAL))
        self.assertEqual(data, baseline.json())
        self.assertEqual(
            self.request(include_day_master_context=False).json(), baseline.json()
        )

    def test_all_sixteen_existing_flag_combinations_are_unchanged(self):
        for values in itertools.product((False, True), repeat=4):
            flags = dict(
                zip(
                    (
                        'include_chart',
                        'include_hidden_stems',
                        'include_ten_gods',
                        'include_interactions',
                    ),
                    values,
                    strict=True,
                )
            )
            baseline = self.request(**flags)
            response = self.request(**flags, include_day_master_context=True)
            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertEqual(result.pop('day_master_context'), context(CANONICAL))
            self.assertEqual(result, baseline.json())

    def test_resolved_solar_month_not_gregorian_month_controls_season(self):
        before = self.request(include_day_master_context=True).json()
        after = self.request(time='23:30', include_day_master_context=True).json()
        self.assertEqual(
            before['day_master_context']['season']['month_branch']['char'], '丑'
        )
        self.assertEqual(
            after['day_master_context']['season']['month_branch']['char'], '寅'
        )
        self.assertEqual(after['day_master_context']['season']['name'], 'spring')
        for payload in (before, after):
            self.assertEqual(
                payload['day_master_context']['day_master']['char'],
                payload['four_pillars']['day']['stem']['chinese'],
            )

    def test_language_does_not_change_evidence(self):
        self.assertEqual(
            self.request(lang='fi', include_day_master_context=True).json()[
                'day_master_context'
            ],
            self.request(lang='en', include_day_master_context=True).json()[
                'day_master_context'
            ],
        )

    def test_opt_out_never_calls_context_builder(self):
        with patch(
            'eight_characters.main.build_day_master_context',
            side_effect=AssertionError('must not run'),
        ):
            self.assertEqual(self.request().status_code, 200)

    def test_internal_errors_are_not_silently_empty(self):
        with patch(
            'eight_characters.main.build_day_master_context',
            side_effect=ValueError('bad mapping'),
        ):
            response = self.request(include_day_master_context=True)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()['detail'], 'Internal engine error.')


if __name__ == '__main__':
    unittest.main()
