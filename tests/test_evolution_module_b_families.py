import unittest

from eight_characters.evolution.families import (
    applicability_mask,
    enforce_applicability_lock,
    evaluate_all_families,
    evaluate_family,
)
from eight_characters.evolution.primitives import (
    element_to_one_hot,
    stage_amplitude,
    stem_element_polarity,
)
from eight_characters.evolution.state import LatentState, ObservedState


def _observed_from_pillars(
    stem_ids: tuple[int, int, int, int],
    branch_ids: tuple[int, int, int, int],
    vitality_stages: tuple[int, int, int, int] = (5, 5, 5, 5),
) -> ObservedState:
    base_elements = []
    polarities = []
    for stem_id in stem_ids:
        element_index, polarity = stem_element_polarity(stem_id)
        base_elements.append(element_to_one_hot(element_index))
        polarities.append(polarity)

    return ObservedState(
        branch_ids=branch_ids,
        base_elements=tuple(base_elements),
        polarities=tuple(polarities),
        hierarchy_levels=(4, 4, 4, 4),
        positions=(1, 2, 3, 4),
        masks=(1, 1, 1, 1),
        vitality_stages=vitality_stages,
        day_master_index=2,
    )


class TestEvolutionModuleBFamilies(unittest.TestCase):
    def test_stem_combination_day_stem_tie_break(self) -> None:
        # Stems: Jia, Ji, Jia, Xin.
        observed = _observed_from_pillars(
            stem_ids=(1, 6, 1, 8),
            branch_ids=(1, 2, 3, 4),
            vitality_stages=(5, 4, 5, 5),
        )
        evaluation = evaluate_family(1, observed)  # Jia+Ji
        self.assertEqual(evaluation.applicability, 1)
        self.assertEqual(evaluation.selected_positions, (2, 3))
        self.assertEqual(evaluation.proximity_weight, 1.0)
        expected_support = (stage_amplitude(4) + stage_amplitude(5)) / 2.0
        self.assertAlmostEqual(evaluation.support, expected_support)

    def test_branch_pair_lexicographic_tie_break(self) -> None:
        observed = _observed_from_pillars(
            stem_ids=(1, 2, 3, 4),
            branch_ids=(1, 2, 1, 2),  # Zi, Chou, Zi, Chou
        )
        evaluation = evaluate_family(6, observed)  # Zi+Chou harmony
        self.assertEqual(evaluation.applicability, 1)
        self.assertEqual(evaluation.selected_positions, (1, 2))
        self.assertEqual(evaluation.proximity_weight, 1.0)

    def test_three_member_family_applicability_and_support(self) -> None:
        observed = _observed_from_pillars(
            stem_ids=(1, 2, 3, 4),
            branch_ids=(9, 1, 4, 4),  # Shen, Zi present for r18 frame
        )
        evaluation = evaluate_family(18, observed)
        self.assertEqual(evaluation.applicability, 1)
        self.assertEqual(evaluation.presence_state, 2)
        self.assertEqual(evaluation.selected_positions, (1, 2))
        self.assertEqual(evaluation.proximity_weight, 1.0)
        self.assertAlmostEqual(evaluation.support, 1.0)

    def test_three_member_family_off_when_only_one_unique_member(self) -> None:
        observed = _observed_from_pillars(
            stem_ids=(1, 2, 3, 4),
            branch_ids=(9, 9, 4, 4),  # only Shen from r18 members
        )
        evaluation = evaluate_family(18, observed)
        self.assertEqual(evaluation.applicability, 0)
        self.assertEqual(evaluation.selected_positions, ())
        self.assertEqual(evaluation.support, 0.0)

    def test_self_punishment_selects_nearest_duplicate_pair(self) -> None:
        observed = _observed_from_pillars(
            stem_ids=(1, 2, 3, 4),
            branch_ids=(1, 4, 1, 1),  # Zi at positions 1,3,4
        )
        evaluation = evaluate_family(25, observed)  # Zi-Zi
        self.assertEqual(evaluation.applicability, 1)
        self.assertEqual(evaluation.selected_positions, (3, 4))
        self.assertEqual(evaluation.proximity_weight, 1.0)

    def test_applicability_mask_and_lock(self) -> None:
        observed = _observed_from_pillars(
            stem_ids=(1, 2, 3, 4),
            branch_ids=(3, 4, 5, 6),  # No Zi+Chou for r6
        )
        evaluations = evaluate_all_families(observed)
        mask = applicability_mask(observed)
        self.assertEqual(len(mask), 34)
        self.assertEqual(mask[5], 0)  # r6 index

        switches = [0] * 34
        switches[5] = 1  # r6 enabled despite A_r(Y)=0
        latent = LatentState(
            switches=tuple(switches),
            omegas=(0.5,) * 34,
            mode='Standard',
        )
        with self.assertRaises(ValueError):
            enforce_applicability_lock(latent, evaluations)


if __name__ == '__main__':
    unittest.main()
