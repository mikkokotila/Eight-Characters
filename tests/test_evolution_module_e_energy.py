import unittest
from math import isinf

from eight_characters.evolution.energy import compute_energy_breakdown
from eight_characters.evolution.families import evaluate_all_families
from eight_characters.evolution.mechanics import compute_dynamic_vitality_amplitudes
from eight_characters.evolution.primitives import (
    LAMBDA_COR,
    LAMBDA_INTER,
    LAMBDA_INTRA,
    element_to_one_hot,
    stem_element_polarity,
)
from eight_characters.evolution.state import (
    FullTransformationCapture,
    LatentState,
    ObservedState,
    recompute_effective_ten_gods,
)


def _observed_from_stems(
    stem_ids: tuple[int, int, int, int],
    branch_ids: tuple[int, int, int, int] = (1, 2, 3, 4),
    vitality_stages: tuple[int, int, int, int] = (5, 5, 5, 5),
) -> ObservedState:
    elements = []
    polarities = []
    for stem_id in stem_ids:
        element_index, polarity = stem_element_polarity(stem_id)
        elements.append(element_to_one_hot(element_index))
        polarities.append(polarity)
    return ObservedState(
        branch_ids=branch_ids,
        base_elements=tuple(elements),
        polarities=tuple(polarities),
        hierarchy_levels=(4, 4, 4, 4),
        positions=(1, 2, 3, 4),
        masks=(1, 1, 1, 1),
        vitality_stages=vitality_stages,
        day_master_index=2,
    )


def _latent(mode: str = 'Standard') -> LatentState:
    return LatentState(
        switches=(0,) * 34,
        omegas=(0.5,) * 34,
        mode=mode,
    )


class TestEvolutionModuleEEnergy(unittest.TestCase):
    def test_total_energy_decomposition(self) -> None:
        observed = _observed_from_stems((1, 3, 1, 8))
        latent = _latent('Standard')
        evaluations = evaluate_all_families(observed)
        effective_elements = observed.base_elements
        effective_ten_gods = recompute_effective_ten_gods(
            observed_state=observed,
            effective_elements=effective_elements,
            mode=latent.mode,
        )
        amplitudes = compute_dynamic_vitality_amplitudes(
            observed_state=observed,
            latent_state=latent,
        )
        breakdown = compute_energy_breakdown(
            observed_state=observed,
            latent_state=latent,
            effective_elements=effective_elements,
            effective_ten_gods=effective_ten_gods,
            dynamic_amplitudes=amplitudes,
            family_evaluations=evaluations,
        )
        self.assertFalse(isinf(breakdown.total))
        recomposed = (
            breakdown.e_act
            + LAMBDA_INTRA * breakdown.e_intra
            + LAMBDA_INTER * breakdown.e_inter
            + breakdown.e_clim
            + breakdown.e_dom
            + breakdown.e_mode
            + breakdown.e_clash
            + breakdown.e_frame
            + breakdown.e_pun
            + breakdown.e_cor
            + breakdown.e_cross
        )
        self.assertAlmostEqual(breakdown.total, recomposed, places=9)

    def test_exclusivity_conflict_returns_infinite_energy(self) -> None:
        observed = _observed_from_stems((1, 3, 1, 8))
        latent = _latent('Standard')
        effective_elements = observed.base_elements
        effective_ten_gods = recompute_effective_ten_gods(
            observed_state=observed,
            effective_elements=effective_elements,
            mode=latent.mode,
        )
        amplitudes = compute_dynamic_vitality_amplitudes(
            observed_state=observed,
            latent_state=latent,
        )
        breakdown = compute_energy_breakdown(
            observed_state=observed,
            latent_state=latent,
            effective_elements=effective_elements,
            effective_ten_gods=effective_ten_gods,
            dynamic_amplitudes=amplitudes,
            full_captures=(
                FullTransformationCapture(1, 0, 2),
                FullTransformationCapture(2, 0, 3),
            ),
        )
        self.assertTrue(isinf(breakdown.e_excl))
        self.assertTrue(isinf(breakdown.total))

    def test_corrosion_gate_requires_threatened_harmony_full(self) -> None:
        observed = _observed_from_stems(
            stem_ids=(1, 2, 3, 4),
            branch_ids=(1, 2, 8, 4),  # Zi, Chou, Wei, Mao
        )
        base_switches = [0] * 34
        base_switches[28] = 1  # r29 harm active

        full_harmony_switches = base_switches.copy()
        full_harmony_switches[5] = 3  # r6 harmony at full state
        latent_full = LatentState(
            switches=tuple(full_harmony_switches),
            omegas=(0.5,) * 34,
            mode='Standard',
        )

        partial_harmony_switches = base_switches.copy()
        partial_harmony_switches[5] = 2
        latent_partial = LatentState(
            switches=tuple(partial_harmony_switches),
            omegas=(0.5,) * 34,
            mode='Standard',
        )

        effective_elements = observed.base_elements
        evaluations = evaluate_all_families(observed)

        tg_full = recompute_effective_ten_gods(
            observed_state=observed,
            effective_elements=effective_elements,
            mode=latent_full.mode,
        )
        amp_full = compute_dynamic_vitality_amplitudes(
            observed_state=observed,
            latent_state=latent_full,
        )
        breakdown_full = compute_energy_breakdown(
            observed_state=observed,
            latent_state=latent_full,
            effective_elements=effective_elements,
            effective_ten_gods=tg_full,
            dynamic_amplitudes=amp_full,
            family_evaluations=evaluations,
        )

        tg_partial = recompute_effective_ten_gods(
            observed_state=observed,
            effective_elements=effective_elements,
            mode=latent_partial.mode,
        )
        amp_partial = compute_dynamic_vitality_amplitudes(
            observed_state=observed,
            latent_state=latent_partial,
        )
        breakdown_partial = compute_energy_breakdown(
            observed_state=observed,
            latent_state=latent_partial,
            effective_elements=effective_elements,
            effective_ten_gods=tg_partial,
            dynamic_amplitudes=amp_partial,
            family_evaluations=evaluations,
        )

        expected_cor = LAMBDA_COR * (0.5**2)
        self.assertAlmostEqual(breakdown_full.e_cor, expected_cor, places=9)
        self.assertAlmostEqual(breakdown_partial.e_cor, 0.0, places=9)

    def test_mode_changes_mode_energy(self) -> None:
        observed = _observed_from_stems((1, 1, 1, 2))  # self-heavy profile
        effective_elements = observed.base_elements

        latent_standard = _latent('Standard')
        latent_follow_strength = _latent('FollowStrength')

        evals = evaluate_all_families(observed)
        tg_standard = recompute_effective_ten_gods(
            observed_state=observed,
            effective_elements=effective_elements,
            mode=latent_standard.mode,
        )
        tg_follow = recompute_effective_ten_gods(
            observed_state=observed,
            effective_elements=effective_elements,
            mode=latent_follow_strength.mode,
        )
        amp_standard = compute_dynamic_vitality_amplitudes(observed, latent_standard)
        amp_follow = compute_dynamic_vitality_amplitudes(observed, latent_follow_strength)

        e_standard = compute_energy_breakdown(
            observed_state=observed,
            latent_state=latent_standard,
            effective_elements=effective_elements,
            effective_ten_gods=tg_standard,
            dynamic_amplitudes=amp_standard,
            family_evaluations=evals,
        )
        e_follow = compute_energy_breakdown(
            observed_state=observed,
            latent_state=latent_follow_strength,
            effective_elements=effective_elements,
            effective_ten_gods=tg_follow,
            dynamic_amplitudes=amp_follow,
            family_evaluations=evals,
        )
        self.assertNotEqual(e_standard.e_mode, e_follow.e_mode)


if __name__ == '__main__':
    unittest.main()

