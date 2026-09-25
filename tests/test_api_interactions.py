import copy
import itertools
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from eight_characters.interactions import (
    INTERACTION_RULES,
    PILLAR_NAMES,
    detect_interactions,
)
from eight_characters.main import app

# Independent character-level reference, not derived from the runtime catalog.
# San Ming Tong Hui, vol. 2: ten-stem combinations, six branch combinations,
# branch clashes (opposite positions), and the four three-harmony frames.
REFERENCE = {
    'stem_combination': ('甲己', '乙庚', '丙辛', '丁壬', '戊癸'),
    'branch_combination': ('子丑', '寅亥', '卯戌', '辰酉', '巳申', '午未'),
    'branch_clash': ('子午', '丑未', '寅申', '卯酉', '辰戌', '巳亥'),
    'harmony_frame': ('申子辰', '亥卯未', '寅午戌', '巳酉丑'),
}
CANONICAL = {
    'year': ('丁', '卯'),
    'month': ('癸', '丑'),
    'day': ('己', '丑'),
    'hour': ('壬', '申'),
}


def pillars(stems='甲甲甲甲', branches='子子子子'):
    return dict(zip(PILLAR_NAMES, zip(stems, branches, strict=True), strict=True))


class TestInteractionRecognition(unittest.TestCase):
    def test_shared_catalog_matches_independent_reference(self):
        for kind, expected in REFERENCE.items():
            actual = [
                ''.join(rule.members) for rule in INTERACTION_RULES if rule.kind == kind
            ]
            self.assertEqual(actual, list(expected))

    def test_canonical_chart_has_non_adjacent_ding_ren_pair_only(self):
        self.assertEqual(
            detect_interactions(CANONICAL),
            [
                {
                    'id': 'stem_combination:4:year-hour',
                    'kind': 'stem_combination',
                    'component': 'stem',
                    'members': [
                        {'pillar': 'year', 'char': '丁', 'pinyin': 'Ding'},
                        {'pillar': 'hour', 'char': '壬', 'pinyin': 'Ren'},
                    ],
                    'adjacent': False,
                    'completeness': 'pair',
                    'potential_element': 'wood',
                    'transformation': 'not_assessed',
                }
            ],
        )

    def test_every_pair_in_every_position_and_orientation(self):
        for kind in ('stem_combination', 'branch_combination', 'branch_clash'):
            for pattern in REFERENCE[kind]:
                for positions in itertools.combinations(range(4), 2):
                    for ordered in (pattern, pattern[::-1]):
                        chars = list(
                            '甲甲甲甲' if kind == 'stem_combination' else '子子子子'
                        )
                        for pos, char in zip(positions, ordered, strict=True):
                            chars[pos] = char
                        source = (
                            pillars(stems=chars)
                            if kind == 'stem_combination'
                            else pillars(branches=chars)
                        )
                        found = [
                            r
                            for r in detect_interactions(source)
                            if r['kind'] == kind
                            and [m['pillar'] for m in r['members']]
                            == [PILLAR_NAMES[p] for p in positions]
                        ]
                        with self.subTest(
                            kind=kind,
                            pattern=pattern,
                            positions=positions,
                            ordered=ordered,
                        ):
                            self.assertEqual(len(found), 1)
                            self.assertEqual(
                                found[0]['adjacent'], positions[1] - positions[0] == 1
                            )

    def test_complete_frames_in_all_positions_and_permutations(self):
        for pattern in REFERENCE['harmony_frame']:
            filler = next(c for c in '子丑寅卯辰巳午未申酉戌亥' if c not in pattern)
            for positions in itertools.combinations(range(4), 3):
                for ordered in itertools.permutations(pattern):
                    chars = [filler] * 4
                    for pos, char in zip(positions, ordered, strict=True):
                        chars[pos] = char
                    found = [
                        r
                        for r in detect_interactions(pillars(branches=chars))
                        if r['kind'] == 'harmony_frame'
                    ]
                    self.assertEqual(len(found), 1)
                    self.assertEqual(found[0]['completeness'], 'complete')
                    self.assertEqual(
                        found[0]['adjacent'], positions[-1] - positions[0] == 2
                    )
                    self.assertEqual(found[0]['transformation'], 'not_assessed')

    def test_no_incomplete_frames_even_with_repeated_members(self):
        for pattern in REFERENCE['harmony_frame']:
            for a, b in itertools.combinations(pattern, 2):
                for chars in itertools.product((a, b), repeat=4):
                    found = detect_interactions(pillars(branches=chars))
                    self.assertFalse(any(r['kind'] == 'harmony_frame' for r in found))

    def test_repeated_occurrences_are_not_reduced_to_nearest_pair(self):
        found = detect_interactions(pillars(stems='甲己甲己'))
        self.assertEqual(len(found), 4)
        self.assertEqual(len({r['id'] for r in found}), 4)
        self.assertEqual(sum(r['adjacent'] for r in found), 3)
        branches = detect_interactions(pillars(branches='子午子午'))
        self.assertEqual(len(branches), 4)
        self.assertTrue(all(r['kind'] == 'branch_clash' for r in branches))

    def test_duplicate_third_member_produces_two_complete_occurrences(self):
        found = [
            r
            for r in detect_interactions(pillars(branches='申子辰辰'))
            if r['kind'] == 'harmony_frame'
        ]
        self.assertEqual(len(found), 2)
        self.assertNotEqual(found[0]['id'], found[1]['id'])

    def test_overlapping_combination_and_clash_both_survive(self):
        found = detect_interactions(pillars(branches='子丑午午'))
        self.assertEqual(
            [r['kind'] for r in found],
            ['branch_combination', 'branch_clash', 'branch_clash'],
        )
        self.assertIsNone(found[0]['potential_element'])
        self.assertEqual(found[0]['transformation'], 'not_assessed')
        self.assertTrue(all(r['transformation'] == 'not_applicable' for r in found[1:]))

    def test_no_matches_is_empty_not_a_fallback(self):
        self.assertEqual(detect_interactions(pillars()), [])

    def test_no_hidden_stem_combinations(self):
        # 丑 contains 己; only visible 甲 stems are compared here.
        self.assertEqual(detect_interactions(pillars(branches='丑丑丑丑')), [])

    def test_deterministic_order_and_no_input_mutation(self):
        source = pillars(stems='甲己甲己', branches='子丑午午')
        original = copy.deepcopy(source)
        expected = detect_interactions(source)
        self.assertEqual(source, original)
        self.assertEqual(
            detect_interactions(dict(reversed(list(source.items())))), expected
        )
        self.assertEqual(detect_interactions(source), expected)

    def test_rejects_missing_extra_or_invalid_pillars(self):
        for source in (
            {},
            {**CANONICAL, 'extra': ('甲', '子')},
            {**CANONICAL, 'day': ('x', '子')},
            {**CANONICAL, 'hour': ('甲', 'x')},
            {**CANONICAL, 'month': ('甲',)},
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                detect_interactions(source)


class TestInteractionsAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def request(self, **flags):
        return self.client.post(
            '/api/four_pillars',
            json={
                'date': '1988-02-04',
                'time': '16:30:00',
                'location': {
                    'timezone': 'Asia/Shanghai',
                    'longitude': 104.066,
                    'latitude': 30.658,
                },
                **flags,
            },
        )

    def test_opt_in_and_no_unrequested_enrichments(self):
        baseline = self.request()
        enriched = self.request(include_interactions=True)
        self.assertEqual(baseline.status_code, 200)
        self.assertEqual(enriched.status_code, 200)
        result = enriched.json()
        self.assertEqual(result.pop('interactions'), detect_interactions(CANONICAL))
        self.assertEqual(result, baseline.json())
        self.assertEqual(
            self.request(include_interactions=False).json(), baseline.json()
        )

    def test_all_other_payloads_remain_unchanged(self):
        for flags in itertools.product((False, True), repeat=3):
            kwargs = dict(
                zip(
                    ('include_chart', 'include_hidden_stems', 'include_ten_gods'),
                    flags,
                    strict=True,
                )
            )
            baseline = self.request(**kwargs).json()
            result = self.request(**kwargs, include_interactions=True).json()
            self.assertEqual(result.pop('interactions'), detect_interactions(CANONICAL))
            self.assertEqual(result, baseline)

    def test_internal_recognition_errors_are_not_silently_empty(self):
        with patch(
            'eight_characters.main.detect_interactions',
            side_effect=ValueError('broken input'),
        ):
            response = self.request(include_interactions=True)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()['detail'], 'Internal engine error.')

    def test_opt_out_does_not_run_detector(self):
        with patch(
            'eight_characters.main.detect_interactions',
            side_effect=AssertionError('must not run'),
        ):
            self.assertEqual(self.request().status_code, 200)


if __name__ == '__main__':
    unittest.main()
