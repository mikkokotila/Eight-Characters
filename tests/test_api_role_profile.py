import copy
import itertools
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from lunar_python.util import LunarUtil

from eight_characters.day_master_context import build_day_master_context
from eight_characters.main import _load_hidden_stems_lookup, _load_ten_gods_lookup, app
from eight_characters.role_profile import build_role_profile

NAMES = ('year', 'month', 'day', 'hour')
STEMS = '甲乙丙丁戊己庚辛壬癸'
BRANCHES = '子丑寅卯辰巳午未申酉戌亥'
ELEMENTS = dict(
    zip(
        STEMS,
        [
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
        ],
        strict=True,
    )
)
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
GROUPS = ('companion', 'output', 'wealth', 'authority', 'resource')
CANONICAL = dict(
    zip(NAMES, [('丁', '卯'), ('癸', '丑'), ('己', '丑'), ('壬', '申')], strict=True)
)
LOCATION = {'timezone': 'Asia/Shanghai', 'longitude': 104.066, 'latitude': 30.658}


def profile(source=CANONICAL):
    return build_role_profile(
        source, _load_hidden_stems_lookup(), _load_ten_gods_lookup()
    )


def roles(result):
    return {r['ten_god']: r for g in result['groups'] for r in g['roles']}


class TestRoleProfile(unittest.TestCase):
    def test_canonical_five_groups_and_all_ten_individual_roles(self):
        result = profile()
        self.assertEqual(result['policy'], 'natal_roles_v1')
        self.assertEqual([g['group'] for g in result['groups']], list(GROUPS))
        self.assertEqual(
            [g['element'] for g in result['groups']],
            ['earth', 'metal', 'water', 'wood', 'fire'],
        )
        self.assertEqual(
            [g['presence'] for g in result['groups']],
            [
                'hidden_only',
                'hidden_only',
                'visible_and_hidden',
                'hidden_only',
                'visible_only',
            ],
        )
        self.assertEqual(list(roles(result)), list(GODS.values()))
        self.assertEqual(
            [name for name, r in roles(result).items() if r['presence'] == 'absent'],
            ['direct_officer', 'direct_resource'],
        )

    def test_canonical_visible_stems_roots_and_exact_hidden_matches(self):
        visible = {e['pillar']: e for e in profile()['visible_stems']}
        self.assertEqual(visible['year']['roots'], [])
        self.assertEqual(visible['year']['exact_hidden_matches'], [])
        self.assertEqual(visible['day']['ten_god'], 'day_master')
        self.assertEqual(
            [(r['char'], r['match']) for r in visible['month']['roots']],
            [('癸', 'exact_stem'), ('癸', 'exact_stem'), ('壬', 'opposite_polarity')],
        )
        self.assertEqual(
            visible['month']['exact_hidden_matches'],
            ['hidden:month:癸', 'hidden:day:癸'],
        )
        self.assertEqual(visible['hour']['exact_hidden_matches'], ['hidden:hour:壬'])
        self.assertEqual(
            [r['ten_god'] for r in visible['hour']['roots']],
            ['indirect_wealth', 'indirect_wealth', 'direct_wealth'],
        )

    def test_every_occurrence_is_partitioned_once_and_dm_never_a_visible_companion(
        self,
    ):
        for dm, branch in itertools.product(STEMS, BRANCHES):
            source = {name: (dm, branch) for name in NAMES}
            result = profile(source)
            entries = [
                e for r in roles(result).values() for e in r['visible'] + r['hidden']
            ]
            self.assertEqual(len(entries), 3 + 4 * len(LunarUtil.ZHI_HIDE_GAN[branch]))
            self.assertEqual(len({e['id'] for e in entries}), len(entries))
            self.assertFalse(any(e['id'] == 'visible:day' for e in entries))
            self.assertEqual(
                [e['pillar'] for e in roles(result)['friend']['visible']],
                ['year', 'month', 'hour'],
            )
            self.assertEqual(len(result['visible_stems']), 4)

    def test_all_ten_day_masters_and_targets_against_independent_lunar_roles(self):
        for dm, target in itertools.product(STEMS, repeat=2):
            source = {name: (target, '寅') for name in NAMES}
            source['day'] = (dm, '寅')
            by_role = roles(profile(source))
            expected_god = GODS[LunarUtil.SHI_SHEN[dm + target]]
            for god, entry in by_role.items():
                self.assertEqual(
                    [e['char'] for e in entry['visible']],
                    [target] * 3 if god == expected_god else [],
                )
                expected_hidden = [
                    c
                    for c in LunarUtil.ZHI_HIDE_GAN['寅']
                    if GODS[LunarUtil.SHI_SHEN[dm + c]] == god
                ]
                self.assertEqual(
                    [e['char'] for e in entry['hidden']], expected_hidden * 4
                )

    def test_each_visible_stem_gets_roots_in_every_branch_position(self):
        for target, branch, position in itertools.product(STEMS, BRANCHES, NAMES):
            source = {name: (target, '子') for name in NAMES}
            source['day'] = ('己', source['day'][1])
            source[position] = (source[position][0], branch)
            result = profile(source)
            for visible in result['visible_stems']:
                stem = visible['char']
                matches = [r for r in visible['roots'] if r['pillar'] == position]
                expected = [
                    (
                        c,
                        ('main', 'middle', 'residual')[i],
                        'exact_stem' if c == stem else 'opposite_polarity',
                    )
                    for i, c in enumerate(LunarUtil.ZHI_HIDE_GAN[branch])
                    if ELEMENTS[c] == ELEMENTS[stem]
                ]
                self.assertEqual(
                    [(r['char'], r['qi_type'], r['match']) for r in matches], expected
                )
                self.assertEqual(
                    visible['exact_hidden_matches'],
                    [r['id'] for r in visible['roots'] if r['char'] == stem],
                )

    def test_group_elements_are_correct_even_if_roles_are_absent(self):
        for dm in STEMS:
            source = {name: ('甲', '子') for name in NAMES}
            source['day'] = (dm, '子')
            for group in profile(source)['groups']:
                for role in group['roles']:
                    targets = [
                        c
                        for c in STEMS
                        if GODS[LunarUtil.SHI_SHEN[dm + c]] == role['ten_god']
                    ]
                    self.assertEqual(group['element'], ELEMENTS[targets[0]])

    def test_all_four_presence_states_follow_occurrences_not_weights(self):
        found = set()
        for dm in STEMS:
            source = {name: ('甲', '寅') for name in NAMES}
            source['day'] = (dm, '寅')
            source['year'] = ('丁', '寅')
            for entry in roles(profile(source)).values():
                expected = (
                    'visible_and_hidden'
                    if entry['visible'] and entry['hidden']
                    else 'visible_only'
                    if entry['visible']
                    else 'hidden_only'
                    if entry['hidden']
                    else 'absent'
                )
                self.assertEqual(entry['presence'], expected)
                found.add(expected)
        self.assertEqual(
            found, {'visible_only', 'hidden_only', 'visible_and_hidden', 'absent'}
        )

    def test_opposite_polarity_root_is_never_an_exact_hidden_match(self):
        result = profile({name: ('甲', '卯') for name in NAMES})
        for e in result['visible_stems']:
            self.assertEqual(len(e['roots']), 4)
            self.assertTrue(all(r['match'] == 'opposite_polarity' for r in e['roots']))
            self.assertEqual(e['exact_hidden_matches'], [])

    def test_exact_match_to_day_master_does_not_create_another_visible_role(self):
        source = {name: ('戊', '寅') for name in NAMES}
        source['day'] = ('甲', '寅')
        result = profile(source)
        self.assertEqual(roles(result)['friend']['presence'], 'hidden_only')
        self.assertEqual(len(result['visible_stems'][2]['exact_hidden_matches']), 4)

    def test_resource_occurrences_do_not_become_roots_for_the_supported_element(self):
        source = {name: ('甲', '子') for name in NAMES}
        result = profile(source)
        self.assertEqual(roles(result)['direct_resource']['presence'], 'hidden_only')
        self.assertTrue(all(not e['roots'] for e in result['visible_stems']))

    def test_old_day_master_context_is_an_identical_view_of_shared_evidence(self):
        for dm, branch in itertools.product(STEMS, BRANCHES):
            source = {name: (dm, branch) for name in NAMES}
            old = build_day_master_context(
                source, _load_hidden_stems_lookup(), _load_ten_gods_lookup()
            )
            new = profile(source)
            dm_roots = [
                {k: v for k, v in r.items() if k != 'id'}
                for r in new['visible_stems'][2]['roots']
            ]
            self.assertEqual(dm_roots, old['roots'])
            self.assertEqual(new['day_master'], old['day_master'])

    def test_roots_preserve_repeated_occurrences_clashes_and_natal_roles(self):
        source = dict(
            zip(
                NAMES,
                [('甲', '寅'), ('己', '申'), ('甲', '寅'), ('己', '申')],
                strict=True,
            )
        )
        result = profile(source)
        self.assertEqual(
            [r['id'] for r in result['visible_stems'][0]['roots']],
            ['hidden:year:甲', 'hidden:day:甲'],
        )
        self.assertEqual(
            [r['ten_god'] for r in result['visible_stems'][1]['roots']],
            ['indirect_wealth'] * 4,
        )

    def test_determinism_input_immutability_and_independent_record_ownership(self):
        source = copy.deepcopy(CANONICAL)
        hidden = copy.deepcopy(_load_hidden_stems_lookup())
        gods = copy.deepcopy(_load_ten_gods_lookup())
        before = copy.deepcopy((source, hidden, gods))
        result = build_role_profile(source, hidden, gods)
        self.assertEqual((source, hidden, gods), before)
        self.assertEqual(profile(dict(reversed(list(source.items())))), result)
        roots = result['visible_stems'][1]['roots']
        roots[0]['char'] = '甲'
        self.assertEqual(roles(result)['indirect_wealth']['hidden'][0]['char'], '癸')
        self.assertEqual(result['visible_stems'][3]['roots'][0]['char'], '癸')
        self.assertEqual(profile(), profile())

    def test_invalid_inputs_and_incomplete_role_mapping_raise(self):
        for source in (
            {},
            {**CANONICAL, 'extra': ('甲', '子')},
            {**CANONICAL, 'day': ('?', '子')},
            {**CANONICAL, 'day': ('甲',)},
            {**CANONICAL, 'hour': ('甲', '?')},
        ):
            with self.assertRaises(ValueError):
                profile(source)
        for hidden in (
            {},
            {**_load_hidden_stems_lookup(), '丑': []},
            {**_load_hidden_stems_lookup(), '丑': ['己', '己']},
        ):
            with self.assertRaises(ValueError):
                build_role_profile(CANONICAL, hidden, _load_ten_gods_lookup())
        gods = copy.deepcopy(_load_ten_gods_lookup())
        del gods[('己', '丙')]
        with self.assertRaises(ValueError):
            build_role_profile(CANONICAL, _load_hidden_stems_lookup(), gods)


class TestRoleProfileAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def request(self, **flags):
        return self.client.post(
            '/api/four_pillars',
            json={'date': '1988-02-04', 'time': '16:30', 'location': LOCATION, **flags},
        )

    def test_independent_opt_in_and_all_thirty_two_flag_combinations_unchanged(self):
        names = (
            'include_chart',
            'include_hidden_stems',
            'include_ten_gods',
            'include_interactions',
            'include_day_master_context',
        )
        for flags in itertools.product((False, True), repeat=5):
            options = dict(zip(names, flags, strict=True))
            baseline = self.request(**options)
            response = self.request(**options, include_role_profile=True)
            self.assertEqual(response.status_code, 200)
            actual = response.json()
            self.assertEqual(actual.pop('role_profile'), profile())
            self.assertEqual(actual, baseline.json())
        self.assertEqual(
            self.request(include_role_profile=False).json(), self.request().json()
        )

    def test_errors_are_explicit_and_opt_out_does_not_run_builder(self):
        with patch(
            'eight_characters.main.build_role_profile',
            side_effect=ValueError('bad data'),
        ):
            self.assertEqual(self.request().status_code, 200)
            response = self.request(include_role_profile=True)
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.json()['detail'], 'Internal engine error.')

    def test_natal_profile_is_language_invariant(self):
        self.assertEqual(
            self.request(include_role_profile=True, lang='fi').json()['role_profile'],
            self.request(include_role_profile=True, lang='en').json()['role_profile'],
        )

    def test_profile_tracks_the_actual_computed_day_master_at_a_day_boundary(self):
        for time in ('00:30', '23:30'):
            result = self.request(
                time=time, include_role_profile=True, include_day_master_context=True
            ).json()
            self.assertEqual(
                result['role_profile']['day_master'],
                result['day_master_context']['day_master'],
            )
            self.assertEqual(
                result['role_profile']['visible_stems'][2]['char'],
                result['four_pillars']['day']['stem']['chinese'],
            )


if __name__ == '__main__':
    unittest.main()
