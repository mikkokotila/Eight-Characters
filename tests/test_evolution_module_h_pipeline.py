import unittest

from eight_characters.evolution.inference import InferenceConfig
from eight_characters.evolution.pipeline import (
    EvolutionInput,
    run_natal_mvp,
)
from eight_characters.evolution.postprocess import PostprocessConfig
from eight_characters.evolution.primitives import (
    element_to_one_hot,
    stem_element_polarity,
)


def _input_from_stems(
    stem_ids: tuple[int, int, int, int],
    branch_ids: tuple[int, int, int, int],
) -> EvolutionInput:
    elements = []
    polarities = []
    for stem_id in stem_ids:
        element_index, polarity = stem_element_polarity(stem_id)
        elements.append(element_to_one_hot(element_index))
        polarities.append(polarity)
    return EvolutionInput(
        branch_ids=branch_ids,
        base_elements=tuple(elements),
        polarities=tuple(polarities),
        hierarchy_levels=(4, 4, 4, 4),
        positions=(1, 2, 3, 4),
        masks=(1, 1, 1, 1),
        vitality_stages=(5, 5, 5, 5),
        day_master_index=2,
    )


class TestEvolutionModuleHPipeline(unittest.TestCase):
    def test_pipeline_output_shape(self) -> None:
        evolution_input = _input_from_stems(
            stem_ids=(1, 3, 1, 8),
            branch_ids=(1, 2, 3, 4),
        )
        output = run_natal_mvp(
            evolution_input=evolution_input,
            inference_config=InferenceConfig(
                particles=24,
                temperature_steps=3,
                sweeps_per_step=1,
                seed=42,
            ),
            postprocess_config=PostprocessConfig(
                discrete_relax_max_passes=2,
                continuous_passes=2,
                dbscan_eps=0.25,
                dbscan_min_samples=3,
            ),
        )
        self.assertEqual(output.particle_count, 24)
        self.assertEqual(len(output.labels), 24)
        mass_sum = sum(basin.mass for basin in output.basins) + output.noise_probability
        self.assertAlmostEqual(mass_sum, 1.0, places=9)
        for basin in output.basins:
            self.assertEqual(len(basin.map_switches), 34)
            self.assertEqual(len(basin.map_omegas), 34)
            self.assertEqual(len(basin.map_effective_elements), 4)
            self.assertEqual(len(basin.map_effective_ten_gods), 4)

    def test_pipeline_is_deterministic(self) -> None:
        evolution_input = _input_from_stems(
            stem_ids=(1, 2, 3, 4),
            branch_ids=(1, 2, 8, 4),
        )
        cfg_inference = InferenceConfig(
            particles=20,
            temperature_steps=2,
            sweeps_per_step=1,
            seed=42,
        )
        cfg_post = PostprocessConfig(
            discrete_relax_max_passes=2,
            continuous_passes=2,
            dbscan_eps=0.25,
            dbscan_min_samples=3,
        )
        output_a = run_natal_mvp(
            evolution_input=evolution_input,
            inference_config=cfg_inference,
            postprocess_config=cfg_post,
        )
        output_b = run_natal_mvp(
            evolution_input=evolution_input,
            inference_config=cfg_inference,
            postprocess_config=cfg_post,
        )

        self.assertEqual(output_a.labels, output_b.labels)
        self.assertEqual(output_a.temperature_ladder, output_b.temperature_ladder)
        masses_a = tuple(basin.mass for basin in output_a.basins)
        masses_b = tuple(basin.mass for basin in output_b.basins)
        self.assertEqual(masses_a, masses_b)
        self.assertAlmostEqual(
            output_a.noise_probability,
            output_b.noise_probability,
            places=12,
        )


if __name__ == '__main__':
    unittest.main()
