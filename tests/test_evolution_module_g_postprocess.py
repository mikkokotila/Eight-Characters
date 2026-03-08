import unittest

from eight_characters.evolution.inference import InferenceConfig, run_tempered_smc
from eight_characters.evolution.postprocess import (
    PostprocessConfig,
    postprocess_inference,
)
from eight_characters.evolution.primitives import element_to_one_hot, stem_element_polarity
from eight_characters.evolution.state import ObservedState


def _observed_from_stems(
    stem_ids: tuple[int, int, int, int],
    branch_ids: tuple[int, int, int, int],
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
        vitality_stages=(5, 5, 5, 5),
        day_master_index=2,
    )


class TestEvolutionModuleGPostprocess(unittest.TestCase):
    def test_postprocess_output_shapes_and_normalization(self) -> None:
        observed = _observed_from_stems(
            stem_ids=(1, 3, 1, 8),
            branch_ids=(1, 2, 3, 4),
        )
        inference = run_tempered_smc(
            observed_state=observed,
            config=InferenceConfig(
                particles=20,
                temperature_steps=3,
                sweeps_per_step=1,
                seed=42,
            ),
        )
        result = postprocess_inference(
            observed_state=observed,
            inference_result=inference,
            config=PostprocessConfig(
                discrete_relax_max_passes=3,
                continuous_passes=3,
                dbscan_eps=0.25,
                dbscan_min_samples=3,
            ),
        )

        self.assertEqual(len(result.labels), 20)
        self.assertEqual(len(result.relaxed_particles), 20)
        basin_mass_total = sum(basin.mass for basin in result.basins)
        self.assertAlmostEqual(
            basin_mass_total + result.noise_probability,
            1.0,
            places=9,
        )
        for basin in result.basins:
            self.assertGreaterEqual(basin.mass, 0.0)
            self.assertLess(basin.map_particle_index, len(result.relaxed_particles))

    def test_postprocess_is_deterministic(self) -> None:
        observed = _observed_from_stems(
            stem_ids=(1, 2, 3, 4),
            branch_ids=(1, 2, 8, 4),
        )
        inference = run_tempered_smc(
            observed_state=observed,
            config=InferenceConfig(
                particles=18,
                temperature_steps=2,
                sweeps_per_step=1,
                seed=42,
            ),
        )
        config = PostprocessConfig(
            discrete_relax_max_passes=2,
            continuous_passes=2,
            dbscan_eps=0.25,
            dbscan_min_samples=3,
        )
        result_a = postprocess_inference(
            observed_state=observed,
            inference_result=inference,
            config=config,
        )
        result_b = postprocess_inference(
            observed_state=observed,
            inference_result=inference,
            config=config,
        )

        self.assertEqual(result_a.labels, result_b.labels)
        masses_a = tuple(basin.mass for basin in result_a.basins)
        masses_b = tuple(basin.mass for basin in result_b.basins)
        self.assertEqual(masses_a, masses_b)
        self.assertAlmostEqual(
            result_a.noise_probability,
            result_b.noise_probability,
            places=12,
        )


if __name__ == '__main__':
    unittest.main()

