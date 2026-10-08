import copy
import itertools
import unittest
from unittest.mock import patch

from eight_characters.canon import load_canon
from eight_characters.data import BRANCHES
from eight_characters.interactions import (
    CANON_DIRECTIONAL,
    CANON_HALF_FRAMES,
    CANON_HARMS,
    CANON_PUNISHMENT_PAIR,
    CANON_PUNISHMENT_TRIANGLES,
    CANON_SELF_PUNISHMENTS,
    INTERACTION_RULES,
    LUCK,
    PILLAR_NAMES,
    detect_interactions,
    detect_luck_interactions,
)
from tests.accounts_support import signed_in_client

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


BRANCH_PINYIN = {char: info['pinyin'] for char, info in BRANCHES.items()}


def pillars(stems='甲甲甲甲', branches='子子子子'):
    return dict(zip(PILLAR_NAMES, zip(stems, branches, strict=True), strict=True))


class TestInteractionRecognition(unittest.TestCase):
    def test_shared_catalog_matches_independent_reference(self):
        for kind, expected in REFERENCE.items():
            actual = [
                ''.join(rule.members) for rule in INTERACTION_RULES if rule.kind == kind
            ]
            self.assertEqual(actual, list(expected))

    def test_potential_targets_are_explicit_and_never_applied(self):
        expected = {
            'stem_combination': ['earth', 'metal', 'water', 'wood', 'fire'],
            'harmony_frame': ['water', 'wood', 'fire', 'metal'],
        }
        for kind, elements in expected.items():
            self.assertEqual(
                [
                    rule.potential_element
                    for rule in INTERACTION_RULES
                    if rule.kind == kind
                ],
                elements,
            )
        self.assertTrue(
            all(
                rule.potential_element is None
                for rule in INTERACTION_RULES
                if rule.kind in ('branch_combination', 'branch_clash')
            )
        )

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
        # Four clashes, and the two Horses punish themselves (the canon's 午午).
        branches = detect_interactions(pillars(branches='子午子午'))
        self.assertEqual(
            [r['id'] for r in branches],
            [
                'branch_clash:12:year-month',
                'branch_clash:12:year-hour',
                'branch_clash:12:month-day',
                'branch_clash:12:day-hour',
                'self_punishment:36:month-hour',
            ],
        )

    def test_duplicate_third_member_produces_two_complete_occurrences(self):
        found = [
            r
            for r in detect_interactions(pillars(branches='申子辰辰'))
            if r['kind'] == 'harmony_frame'
        ]
        self.assertEqual(len(found), 2)
        self.assertNotEqual(found[0]['id'], found[1]['id'])

    def test_overlapping_combination_and_clash_both_survive(self):
        # Beside them, the canon's other findings on these branches: the two Horses'
        # self-punishment, and the Ox harming each Horse.
        found = detect_interactions(pillars(branches='子丑午午'))
        self.assertEqual(
            [r['kind'] for r in found],
            [
                'branch_combination',
                'branch_clash',
                'branch_clash',
                'self_punishment',
                'harm',
                'harm',
            ],
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


# The chart draws each relationship as an arc (static/relationships.js, arcLayout).
# Each relationship of the shared families has an arc of its own. One of the canon's
# added families joins an arc that already spans the same columns, as a strand inside
# it, and stands alone only where none does. An arc rises one level for each column it
# spans, and at least one level above every narrower arc it overlaps; arcs that only
# meet at a card may share a level. The arcs' rows in the page hold four levels.
DISPLAY_COLUMNS = {'hour': 0, 'day': 1, 'month': 2, 'year': 3}
ARC_LEVELS = 4
ARC_STRANDS = 3
SHARED_KINDS = {
    'stem_combination',
    'branch_combination',
    'branch_clash',
    'harmony_frame',
}


def arc_slots(interactions):
    slots = []
    for interaction in interactions:
        columns = sorted(
            DISPLAY_COLUMNS[member['pillar']] for member in interaction['members']
        )
        span = (columns[0], columns[-1])
        if interaction['kind'] not in SHARED_KINDS:
            host = next((slot for slot in slots if slot['span'] == span), None)
            if host is not None:
                host['strands'].append(interaction)
                continue
        slots.append({'span': span, 'strands': [interaction]})
    return slots


def arc_levels(interactions):
    slots = sorted(
        arc_slots(interactions),
        key=lambda slot: (slot['span'][1] - slot['span'][0], slot['span'][0]),
    )
    placed: list[tuple[int, int, int]] = []
    for slot in slots:
        start, end = slot['span']
        overlapped = [
            level
            for (other_start, other_end, level) in placed
            if max(start, other_start) < min(end, other_end)
        ]
        placed.append((start, end, max(end - start, 1 + max(overlapped, default=0))))
    return [level for (_, _, level) in placed]


class TestRelationshipArcLevels(unittest.TestCase):
    def test_every_combination_of_stems_or_branches_fits_four_levels(self):
        for component, chars in (
            ('stem', '甲乙丙丁戊己庚辛壬癸'),
            ('branch', '子丑寅卯辰巳午未申酉戌亥'),
        ):
            deepest = 0
            strands = 0
            for combination in itertools.product(chars, repeat=4):
                stems, branches = (
                    (''.join(combination), '子子子子')
                    if component == 'stem'
                    else ('甲甲甲甲', ''.join(combination))
                )
                interactions = [
                    interaction
                    for interaction in detect_interactions(pillars(stems, branches))
                    if interaction['component'] == component
                ]
                deepest = max(deepest, *arc_levels(interactions), 0)
                strands = max(
                    strands,
                    *(len(slot['strands']) for slot in arc_slots(interactions)),
                    0,
                )
            with self.subTest(component=component):
                # Reached, and never exceeded.
                self.assertEqual(deepest, ARC_LEVELS)
                self.assertLessEqual(strands, ARC_STRANDS)

    def test_the_shared_families_keep_an_arc_each(self):
        # Their arcs, and so every chart that has only them, are laid out as before:
        # a strand of the added families never displaces one of them.
        for combination in itertools.product('子丑寅卯辰巳午未申酉戌亥', repeat=4):
            for slot in arc_slots(
                detect_interactions(pillars('甲甲甲甲', combination))
            ):
                shared = [s for s in slot['strands'] if s['kind'] in SHARED_KINDS]
                self.assertLessEqual(len(shared), 1)
                if shared:
                    self.assertIs(slot['strands'][0], shared[0])

    def test_levels_follow_span_and_overlap(self):
        # Hour, day, month and year: 丁丁壬壬 combine month-day, month-hour,
        # year-day and year-hour, each arc over the last.
        interactions = [
            interaction
            for interaction in detect_interactions(pillars('壬壬丁丁', '子子子子'))
            if interaction['component'] == 'stem'
        ]
        self.assertEqual(sorted(arc_levels(interactions)), [1, 2, 3, 4])
        # One arc across all four pillars rises three levels.
        self.assertEqual(arc_levels(detect_interactions(CANONICAL)), [3])

    def test_relationships_on_the_same_columns_share_one_arc(self):
        # 寅巳 in Year and Day is both a harm and two of the Ingratitude triangle: one
        # arc, the harm's strand inside the half-punishment's.
        found = detect_interactions(pillars('甲甲甲甲', '寅子巳子'))
        self.assertEqual(
            [[s['id'] for s in slot['strands']] for slot in arc_slots(found)],
            [['half_punishment:32:year-day', 'harm:41:year-day']],
        )


# The luck pillar's arcs (static/luck.js, arcsFor) ride an outer band: the luck pillar
# is a fifth column after the natal four, every one of its arcs ends on it, and the
# layout is the natal arcs' with that column added. They overlap one another, so each
# arc stands at its own level, the narrower lower; the band holds four levels and an arc
# four strands.
NATAL_PILLARS = ('hour', 'day', 'month', 'year')
LUCK_COLUMNS = {**DISPLAY_COLUMNS, 'luck': 4}
LUCK_ARC_LEVELS = 4
LUCK_ARC_STRANDS = 4


def luck_arc_slots(interactions):
    slots = []
    for interaction in interactions:
        columns = sorted(
            LUCK_COLUMNS[member['pillar']] for member in interaction['members']
        )
        span = (columns[0], columns[-1])
        if interaction['kind'] not in SHARED_KINDS:
            host = next((slot for slot in slots if slot['span'] == span), None)
            if host is not None:
                host['strands'].append(interaction)
                continue
        slots.append({'span': span, 'strands': [interaction]})
    return slots


class TestLuckArcLayout(unittest.TestCase):
    def test_every_luck_pillar_with_four_natal_pillars_fits_the_outer_band(self):
        for component, chars in (
            ('stem', '甲乙丙丁戊己庚辛壬癸'),
            ('branch', '子丑寅卯辰巳午未申酉戌亥'),
        ):
            most_slots = 0
            most_strands = 0
            for combination in itertools.product(chars, repeat=5):
                natal, luck = combination[:4], combination[4]
                if component == 'stem':
                    natal_pillars = dict(zip(NATAL_PILLARS, ((c, '子') for c in natal)))
                    luck_pillar = (luck, '子')
                else:
                    natal_pillars = dict(zip(NATAL_PILLARS, (('甲', c) for c in natal)))
                    luck_pillar = ('甲', luck)
                found = detect_luck_interactions(natal_pillars, luck_pillar)
                slots = luck_arc_slots(
                    [i for i in found['interactions'] if i['component'] == component]
                )
                # Every arc ends on the luck pillar.
                self.assertTrue(all(slot['span'][1] == 4 for slot in slots))
                most_slots = max(most_slots, len(slots))
                most_strands = max(
                    most_strands, *(len(slot['strands']) for slot in slots), 0
                )
            with self.subTest(component=component):
                self.assertEqual(most_slots, LUCK_ARC_LEVELS)
                self.assertLessEqual(most_strands, LUCK_ARC_STRANDS)
        # Reached: a branch combination with three directional combinations.
        found = detect_luck_interactions(
            dict(zip(NATAL_PILLARS, (('甲', c) for c in '子亥亥亥'))), ('甲', '丑')
        )
        self.assertEqual(
            [len(slot['strands']) for slot in luck_arc_slots(found['interactions'])],
            [LUCK_ARC_STRANDS],
        )


# The canon's families beyond the shared catalog, written out from canon/Taxonomy.md
# here rather than taken from the runtime tables.
CANON_REFERENCE = {
    # Each frame and its Peak Branch: a half-frame is two of three, one of them the peak.
    'half_frame': (
        ('申子辰', '子'),
        ('亥卯未', '卯'),
        ('寅午戌', '午'),
        ('巳酉丑', '酉'),
    ),
    'directional_combination': ('亥子丑', '寅卯辰', '巳午未', '申酉戌'),
    'punishment': ('寅巳申', '丑未戌', '子卯'),
    'half_punishment': ('寅巳申', '丑未戌'),
    'self_punishment': ('辰辰', '午午', '酉酉', '亥亥'),
    'harm': ('子未', '丑午', '寅巳', '卯辰', '申亥', '酉戌'),
}
ADDED_KINDS = tuple(CANON_REFERENCE)


# The whole relationships' keys as sorted characters: a combination of branches is one
# when its sorted branches are one of these.
WHOLE_KEYS = {
    kind: {tuple(sorted(key)) for key in CANON_REFERENCE[kind]}
    for kind in ('directional_combination', 'punishment', 'self_punishment', 'harm')
}
FRAME_KEYS = {tuple(sorted(key)) for key, _ in CANON_REFERENCE['half_frame']}


def canon_reading(branches):
    """The added families' findings on four branches (five with a luck pillar), by
    brute force: (kind, positions)."""
    found = []
    for size in (2, 3):
        for positions in itertools.combinations(range(len(branches)), size):
            chars = [branches[p] for p in positions]
            distinct = set(chars)
            for kind, keys in WHOLE_KEYS.items():
                if tuple(sorted(chars)) in keys:
                    found.append((kind, positions))
            if size == 2 and len(distinct) == 2:
                for key, peak in CANON_REFERENCE['half_frame']:
                    if distinct <= set(key) and peak in distinct:
                        found.append(('half_frame', positions))
                for key in CANON_REFERENCE['half_punishment']:
                    if distinct <= set(key):
                        found.append(('half_punishment', positions))
    # A complete frame or triangle absorbs the halves among its members.
    frames = [
        set(positions)
        for positions in itertools.combinations(range(len(branches)), 3)
        if tuple(sorted(branches[p] for p in positions)) in FRAME_KEYS
    ]
    triangles = [
        set(positions)
        for kind, positions in found
        if kind == 'punishment' and len(positions) == 3
    ]

    def absorbed(kind, positions):
        if kind == 'half_frame':
            within = [held for held in frames if set(positions) <= held]
            return any(
                {branches[p] for p in held} >= {branches[p] for p in positions}
                for held in within
            )
        if kind == 'half_punishment':
            return any(set(positions) <= held for held in triangles)
        return False

    return sorted((k, p) for k, p in found if not absorbed(k, p))


# The pillars in the order each relationship's id names them, a luck pillar last.
ID_ORDER = ('year', 'month', 'day', 'hour', 'luck')


def old_shared_detection(stems, branches):
    """The shared families exactly as Standard found them before the canon's were added,
    on four pillars or five with a luck pillar: each finding's id, in order. The ids
    number the rules 1-21 in REFERENCE's order."""
    found = []
    rules = ((kind, key) for kind, keys in REFERENCE.items() for key in keys)
    for rule_index, (kind, key) in enumerate(rules, start=1):
        chars = stems if kind == 'stem_combination' else branches
        for positions in itertools.combinations(range(len(chars)), len(key)):
            if {chars[p] for p in positions} == set(key):
                found.append(
                    f'{kind}:{rule_index}:' + '-'.join(ID_ORDER[p] for p in positions)
                )
    return found


class TestCanonFamilies(unittest.TestCase):
    def test_rules_follow_the_canons_own_entries(self):
        canon = load_canon()
        self.assertEqual(tuple(canon['harms']['entries']), CANON_HARMS)
        self.assertEqual(tuple(canon['harms']['entries']), CANON_REFERENCE['harm'])
        self.assertEqual(
            tuple(canon['directional']['entries']),
            tuple(members for members, _ in CANON_DIRECTIONAL),
        )
        self.assertEqual(
            tuple(canon['punishments']['entries']),
            (*CANON_PUNISHMENT_TRIANGLES, CANON_PUNISHMENT_PAIR, '自刑'),
        )
        labels = [
            p['label'][:2]
            for p in canon['punishments']['entries']['自刑']['paragraphs']
            if p['label'] is not None
        ]
        self.assertEqual(labels, [branch * 2 for branch in CANON_SELF_PUNISHMENTS])
        # Each frame names its Peak Branch; that is the one a half-frame must hold.
        for members, peak in CANON_HALF_FRAMES:
            entry = canon['three_harmonies']['entries'][members]
            peaks = [
                p['label']
                for p in entry['paragraphs']
                if p['label'] is not None and p['label'].startswith('Peak point')
            ]
            self.assertEqual(peaks, [f'Peak point ({BRANCH_PINYIN[peak]})'])

    def test_every_branch_combination_matches_an_independent_reading_of_the_canon(self):
        for branches in itertools.product('子丑寅卯辰巳午未申酉戌亥', repeat=4):
            found = [
                (
                    r['kind'],
                    tuple(PILLAR_NAMES.index(m['pillar']) for m in r['members']),
                )
                for r in detect_interactions(pillars('甲甲甲甲', branches))
                if r['kind'] in ADDED_KINDS
            ]
            self.assertEqual(sorted(found), canon_reading(branches), ''.join(branches))

    def test_the_shared_families_keep_their_findings_ids_and_order(self):
        for stems, branches in (
            *(
                (('甲甲甲甲'), b)
                for b in itertools.product('子丑寅卯辰巳午未申酉戌亥', repeat=4)
            ),
            *(
                (s, '子子子子')
                for s in itertools.product('甲乙丙丁戊己庚辛壬癸', repeat=4)
            ),
        ):
            shared = [
                r['id']
                for r in detect_interactions(pillars(stems, branches))
                if r['kind'] in REFERENCE
            ]
            self.assertEqual(shared, old_shared_detection(stems, branches))

    def test_half_frames_hold_their_peak(self):
        # Shen and Chen without Zi only cradle the absent middle: no half-frame.
        self.assertEqual(detect_interactions(pillars(branches='申辰丑丑')), [])
        found = detect_interactions(pillars(branches='申子戌戌'))
        self.assertEqual(
            [
                (
                    r['id'],
                    r['completeness'],
                    r['potential_element'],
                    r['transformation'],
                )
                for r in found
                if r['kind'] == 'half_frame'
            ],
            [('half_frame:22:year-month', 'half', 'water', 'not_assessed')],
        )

    def test_a_complete_frame_or_triangle_absorbs_its_halves(self):
        # With the whole frame, none of its halves (beside it, Chen clashes the Dog).
        self.assertEqual(
            [r['id'] for r in detect_interactions(pillars(branches='申子辰戌'))],
            ['branch_clash:16:day-hour', 'harmony_frame:18:year-month-day'],
        )
        found = detect_interactions(pillars(branches='寅巳申卯'))
        self.assertNotIn('half_punishment', [r['kind'] for r in found])
        self.assertIn('punishment:30:year-month-day', [r['id'] for r in found])
        # Without the Monkey, two of three: each pair of the triangle that is present.
        found = detect_interactions(pillars(branches='寅巳寅卯'))
        self.assertEqual(
            [r['id'] for r in found if r['kind'] == 'half_punishment'],
            ['half_punishment:32:year-month', 'half_punishment:32:month-day'],
        )

    def test_directional_combinations_need_all_three(self):
        self.assertEqual(detect_interactions(pillars(branches='亥子戌戌')), [])
        found = detect_interactions(pillars(branches='亥子丑卯'))
        self.assertEqual(
            [
                (
                    r['id'],
                    r['completeness'],
                    r['potential_element'],
                    r['transformation'],
                )
                for r in found
                if r['kind'] == 'directional_combination'
            ],
            [
                (
                    'directional_combination:26:year-month-day',
                    'complete',
                    'water',
                    'not_assessed',
                )
            ],
        )

    def test_self_punishment_needs_one_of_the_canons_four_branches(self):
        self.assertEqual(detect_interactions(pillars(branches='子子寅寅')), [])
        found = detect_interactions(pillars(branches='午午午丑'))
        self.assertEqual(
            [r['id'] for r in found if r['kind'] == 'self_punishment'],
            [
                'self_punishment:36:year-month',
                'self_punishment:36:year-day',
                'self_punishment:36:month-day',
            ],
        )

    def test_punishments_and_harms_carry_no_target_or_transformation(self):
        found = detect_interactions(pillars(branches='子卯未丑'))
        self.assertEqual(
            [(r['id'], r['completeness']) for r in found],
            [
                ('branch_combination:6:year-hour', 'pair'),
                ('branch_clash:13:day-hour', 'pair'),
                ('half_frame:23:month-day', 'half'),
                ('half_punishment:33:day-hour', 'half'),
                ('punishment:34:year-month', 'pair'),
                ('harm:39:year-day', 'pair'),
            ],
        )
        for r in found:
            if r['kind'] in (
                'punishment',
                'half_punishment',
                'self_punishment',
                'harm',
            ):
                self.assertIsNone(r['potential_element'])
                self.assertEqual(r['transformation'], 'not_applicable')


LUCK_NAMES = (*PILLAR_NAMES, LUCK)
BRANCH_CHARS = '子丑寅卯辰巳午未申酉戌亥'


def positions_of(relationship):
    return tuple(
        LUCK_NAMES.index(member['pillar']) for member in relationship['members']
    )


def parsed(identifier):
    """(kind, positions) of an id such as half_frame:22:year-month."""
    kind, _, names = identifier.split(':')
    return kind, tuple(LUCK_NAMES.index(name) for name in names.split('-'))


class TestLuckInteractions(unittest.TestCase):
    # The sample of the luck pillar design: 14 August 1975, 07:45, Helsinki, female.
    # Natal 乙卯 Yi Mao, 甲申 Jia Shen, 壬辰 Ren Chen, 甲辰 Jia Chen; its ten decades
    # run forward from 乙酉 Yi You.
    SAMPLE = pillars('乙甲壬甲', '卯申辰辰')
    SAMPLE_DECADES = (
        (
            '乙酉',
            [
                'branch_combination:9:day-luck',
                'branch_combination:9:hour-luck',
                'branch_clash:15:year-luck',
            ],
        ),
        (
            '丙戌',
            [
                'branch_combination:8:year-luck',
                'branch_clash:16:day-luck',
                'branch_clash:16:hour-luck',
            ],
        ),
        (
            '丁亥',
            [
                'stem_combination:4:day-luck',
                'half_frame:23:year-luck',
                'harm:43:month-luck',
            ],
        ),
        (
            '戊子',
            [
                'harmony_frame:18:month-day-luck',
                'harmony_frame:18:month-hour-luck',
                'punishment:34:year-luck',
            ],
        ),
        ('己丑', ['stem_combination:1:month-luck', 'stem_combination:1:hour-luck']),
        (
            '庚寅',
            [
                'stem_combination:2:year-luck',
                'branch_clash:14:month-luck',
                'directional_combination:27:year-day-luck',
                'directional_combination:27:year-hour-luck',
                'half_punishment:32:month-luck',
            ],
        ),
        ('辛卯', ['harm:42:day-luck', 'harm:42:hour-luck']),
        (
            '壬辰',
            [
                'self_punishment:35:day-luck',
                'self_punishment:35:hour-luck',
                'harm:42:year-luck',
            ],
        ),
        ('癸巳', ['branch_combination:10:month-luck', 'half_punishment:32:month-luck']),
        ('甲午', []),
    )

    def test_the_sample_chart_decade_by_decade(self):
        for (stem, branch), ids in self.SAMPLE_DECADES:
            found = detect_luck_interactions(self.SAMPLE, (stem, branch))
            self.assertEqual(
                [r['id'] for r in found['interactions']], ids, stem + branch
            )
            self.assertEqual(found['absorbed'], [], stem + branch)

    def test_the_luck_pillar_is_adjacent_to_every_natal_pillar(self):
        found = detect_luck_interactions(self.SAMPLE, ('戊', '子'))['interactions']
        self.assertEqual(
            [(r['id'], r['adjacent'], r['completeness']) for r in found],
            [
                # Month and Day stand side by side; Month and Hour do not.
                ('harmony_frame:18:month-day-luck', True, 'complete'),
                ('harmony_frame:18:month-hour-luck', False, 'complete'),
                ('punishment:34:year-luck', True, 'pair'),
            ],
        )
        self.assertEqual(
            found[0]['members'],
            [
                {'pillar': 'month', 'char': '申', 'pinyin': 'Shen'},
                {'pillar': 'day', 'char': '辰', 'pinyin': 'Chen'},
                {'pillar': 'luck', 'char': '子', 'pinyin': 'Zi'},
            ],
        )
        self.assertEqual(found[0]['potential_element'], 'water')
        self.assertEqual(found[0]['transformation'], 'not_assessed')

    def test_a_whole_with_the_luck_pillar_absorbs_the_natal_halves_among_its_members(
        self,
    ):
        natal = pillars(branches='申子戌戌')
        self.assertEqual(
            [r['id'] for r in detect_interactions(natal)], ['half_frame:22:year-month']
        )
        found = detect_luck_interactions(natal, ('甲', '辰'))
        self.assertEqual(
            [r['id'] for r in found['interactions']],
            [
                'branch_clash:16:day-luck',
                'branch_clash:16:hour-luck',
                'harmony_frame:18:year-month-luck',
            ],
        )
        self.assertEqual(
            found['absorbed'],
            [
                {
                    'id': 'half_frame:22:year-month',
                    'by': ['harmony_frame:18:year-month-luck'],
                }
            ],
        )

    def test_a_half_a_natal_whole_absorbs_is_not_the_luck_pillars_to_absorb(self):
        natal = pillars(branches='申子辰戌')
        found = detect_luck_interactions(natal, ('甲', '子'))
        self.assertEqual(
            [(r['id'], r['adjacent']) for r in found['interactions']],
            [('harmony_frame:18:year-day-luck', False)],
        )
        self.assertEqual(found['absorbed'], [])

    def test_a_luck_branch_repeating_one_of_the_four_is_a_self_punishment(self):
        found = detect_luck_interactions(pillars(branches='午子子子'), ('甲', '午'))
        self.assertEqual(
            [r['id'] for r in found['interactions'] if r['kind'] == 'self_punishment'],
            ['self_punishment:36:year-luck'],
        )
        found = detect_luck_interactions(pillars(branches='寅子子子'), ('甲', '寅'))
        self.assertNotIn('self_punishment', [r['kind'] for r in found['interactions']])

    def test_invalid_luck_pillars_fail_explicitly(self):
        for luck in (('甲', 'X'), ('X', '子'), ('甲',), ('甲', '子', '子')):
            with self.assertRaises(ValueError):
                detect_luck_interactions(pillars(), luck)
        with self.assertRaises(ValueError):
            detect_luck_interactions({'year': ('甲', '子')}, ('甲', '子'))

    def test_every_branch_combination_matches_the_independent_readings(self):
        # Each natal four with each luck branch. What the luck pillar takes part in is
        # the canon's reading of all five that holds the luck pillar; a natal half the
        # reading of five no longer lists is absorbed, by wholes with the luck pillar.
        for natal in itertools.product(BRANCH_CHARS, repeat=4):
            on_four = set(canon_reading(natal))
            for luck in BRANCH_CHARS:
                branches = (*natal, luck)
                on_five = canon_reading(branches)
                natal_part = {(kind, p) for kind, p in on_five if 4 not in p}
                self.assertLessEqual(natal_part, on_four)
                found = detect_luck_interactions(
                    pillars('甲甲甲甲', natal), ('甲', luck)
                )
                label = ''.join(branches)
                self.assertEqual(
                    sorted(
                        (r['kind'], positions_of(r))
                        for r in found['interactions']
                        if r['kind'] in ADDED_KINDS
                    ),
                    sorted((kind, p) for kind, p in on_five if 4 in p),
                    label,
                )
                self.assertEqual(
                    [r['id'] for r in found['interactions'] if r['kind'] in REFERENCE],
                    [
                        identifier
                        for identifier in old_shared_detection('甲甲甲甲甲', branches)
                        if identifier.endswith('-luck')
                    ],
                    label,
                )
                self.assertEqual(
                    sorted(parsed(a['id']) for a in found['absorbed']),
                    sorted(on_four - natal_part),
                    label,
                )
                for absorbed in found['absorbed']:
                    held = set(parsed(absorbed['id'])[1])
                    for whole in absorbed['by']:
                        self.assertIn(4, parsed(whole)[1])
                        self.assertLessEqual(held, set(parsed(whole)[1]))

    def test_every_stem_combination_with_a_luck_stem_matches_the_reference(self):
        for natal in itertools.product('甲乙丙丁戊己庚辛壬癸', repeat=4):
            for luck in '甲乙丙丁戊己庚辛壬癸':
                found = detect_luck_interactions(
                    pillars(natal, '子子子子'), (luck, '子')
                )
                self.assertEqual(
                    [
                        r['id']
                        for r in found['interactions']
                        if r['component'] == 'stem'
                    ],
                    [
                        identifier
                        for identifier in old_shared_detection(
                            (*natal, luck), '子子子子子'
                        )
                        if identifier.startswith('stem_combination:')
                        and identifier.endswith('-luck')
                    ],
                )


class TestInteractionsAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = signed_in_client(cls)

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

    def test_real_chart_with_no_matches_returns_an_empty_list(self):
        response = self.client.post(
            '/api/four_pillars',
            json={
                # 己巳 丁丑 庚辰 辛巳: no relationship of any family.
                'date': '1990-01-15',
                'time': '12:00',
                'include_interactions': True,
                'location': {
                    'timezone': 'Asia/Shanghai',
                    'longitude': 104.066,
                    'latitude': 30.658,
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['interactions'], [])

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
