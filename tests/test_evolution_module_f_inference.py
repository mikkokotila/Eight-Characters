import unittest

from eight_characters.evolution.families import evaluate_all_families
from eight_characters.evolution.inference import (
    InferenceConfig,
    run_tempered_smc,
    temperature_ladder,
)
from eight_characters.evolution.primitives import OMEGA_MIN_R, element_to_one_hot, stem_element_polarity
from eight_characters.evolution.state import ObservedState


def _observed_from_stems(
    stem_ids: tuple[int, int, int, int],
    branch_ids: tuple[int, int, int, int],
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


class TestEvolutionModuleFInference(unittest.TestCase):
    def test_temperature_ladder_shape(self) -> None:
        config = InferenceConfig(particles=8, temperature_steps=4, sweeps_per_step=1)
        ladder = temperature_ladder(config)
        self.assertEqual(len(ladder), 5)
        self.assertAlmostEqual(ladder[0], config.omega_start, places=12)
        self.assertAlmostEqual(ladder[-1], config.omega_end, places=12)

    def test_smc_is_deterministic_with_fixed_seed(self) -> None:
        observed = _observed_from_stems(
            stem_ids=(1, 3, 1, 8),
            branch_ids=(1, 2, 3, 4),
        )
        config = InferenceConfig(
            particles=24,
            temperature_steps=4,
            sweeps_per_step=1,
            seed=42,
        )
        result_a = run_tempered_smc(observed_state=observed, config=config)
        result_b = run_tempered_smc(observed_state=observed, config=config)

        self.assertEqual(result_a.weights, result_b.weights)
        modes_a = tuple(p.latent_state.mode for p in result_a.particles)
        modes_b = tuple(p.latent_state.mode for p in result_b.particles)
        self.assertEqual(modes_a, modes_b)
        energies_a = tuple(p.energy_breakdown.total for p in result_a.particles)
        energies_b = tuple(p.energy_breakdown.total for p in result_b.particles)
        self.assertEqual(energies_a, energies_b)

    def test_weight_normalization_history(self) -> None:
        observed = _observed_from_stems(
            stem_ids=(1, 2, 3, 4),
            branch_ids=(1, 2, 3, 4),
        )
        config = InferenceConfig(
            particles=16,
            temperature_steps=3,
            sweeps_per_step=1,
            seed=42,
        )
        result = run_tempered_smc(observed_state=observed, config=config)
        for weight_sum in result.weight_sum_history:
            self.assertAlmostEqual(weight_sum, 1.0, places=12)
        self.assertEqual(len(result.ess_history), config.temperature_steps + 1)

    def test_applicability_lock_is_preserved(self) -> None:
        observed = _observed_from_stems(
            stem_ids=(1, 2, 3, 4),
            branch_ids=(3, 4, 5, 6),  # no Zi+Chou (r6) applicability
        )
        config = InferenceConfig(
            particles=20,
            temperature_steps=3,
            sweeps_per_step=2,
            seed=42,
        )
        result = run_tempered_smc(observed_state=observed, config=config)
        for particle in result.particles:
            self.assertEqual(particle.latent_state.switches[5], 0)

    def test_omega_bounds_respected(self) -> None:
        observed = _observed_from_stems(
            stem_ids=(1, 3, 1, 8),
            branch_ids=(1, 2, 3, 4),
        )
        evaluations = evaluate_all_families(observed)
        omega_max_values = tuple(1.0 + evaluation.proximity_weight for evaluation in evaluations)

        config = InferenceConfig(
            particles=18,
            temperature_steps=3,
            sweeps_per_step=1,
            seed=42,
        )
        result = run_tempered_smc(observed_state=observed, config=config)
        for particle in result.particles:
            for idx, omega_value in enumerate(particle.latent_state.omegas):
                self.assertGreaterEqual(omega_value, OMEGA_MIN_R)
                self.assertLessEqual(omega_value, omega_max_values[idx])


if __name__ == '__main__':
    unittest.main()

