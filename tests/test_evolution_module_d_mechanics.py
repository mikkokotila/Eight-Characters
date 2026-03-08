import unittest

from eight_characters.evolution.mechanics import (
    compute_dynamic_vitality_amplitudes,
    pillar_climate_summaries,
    pillar_retention,
    realized_flux,
    transport_capacity,
)
from eight_characters.evolution.primitives import (
    element_to_one_hot,
    stem_element_polarity,
)
from eight_characters.evolution.state import LatentState, ObservedState


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


class TestEvolutionModuleDMechanics(unittest.TestCase):
    def test_dynamic_vitality_with_clash_and_punishment_damage(self) -> None:
        observed = _observed_from_stems((1, 3, 1, 4))
        switches = [0] * 34
        switches[11] = 1  # r12 clash
        switches[21] = 1  # r22 punishment
        latent = LatentState(
            switches=tuple(switches),
            omegas=(1.0,) * 34,
            mode='Standard',
        )
        amplitudes = compute_dynamic_vitality_amplitudes(
            observed_state=observed,
            latent_state=latent,
            clash_participation={(12, 0): 1.0},
            punishment_participation={(22, 0): 1.0},
        )
        self.assertAlmostEqual(amplitudes[0], 0.6)

    def test_transport_and_flux(self) -> None:
        observed = _observed_from_stems((1, 3, 1, 4))  # Wood, Fire, Wood, Fire
        amplitudes = (1.0, 1.0, 1.0, 1.0)
        t_value = transport_capacity(
            observed_state=observed,
            dynamic_amplitudes=amplitudes,
            source_index=0,
            target_index=1,
        )
        self.assertAlmostEqual(t_value, 8.0)

        flux = realized_flux(
            observed_state=observed,
            effective_elements=observed.base_elements,
            dynamic_amplitudes=amplitudes,
        )
        self.assertAlmostEqual(flux[0][1], 9.6)

    def test_climate_summaries(self) -> None:
        observed = _observed_from_stems((1, 3, 9, 7))  # Wood, Fire, Water, Metal
        theta_k, sat_k, theta_chart, sat_chart = pillar_climate_summaries(
            observed_state=observed,
            effective_elements=observed.base_elements,
        )
        self.assertAlmostEqual(theta_k[0], 0.5, places=4)
        self.assertAlmostEqual(theta_k[1], 1.0, places=4)
        self.assertAlmostEqual(theta_k[2], -1.0, places=4)
        self.assertAlmostEqual(theta_k[3], -0.5, places=4)
        self.assertAlmostEqual(theta_chart, 0.0, places=4)

        self.assertAlmostEqual(sat_k[0], 0.5, places=4)
        self.assertAlmostEqual(sat_k[1], -1.0, places=4)
        self.assertAlmostEqual(sat_k[2], 1.0, places=4)
        self.assertAlmostEqual(sat_k[3], -1.0, places=4)
        self.assertAlmostEqual(sat_chart, -0.125, places=4)

    def test_pillar_retention(self) -> None:
        observed = _observed_from_stems((1, 3, 9, 7))
        flux = realized_flux(
            observed_state=observed,
            effective_elements=observed.base_elements,
            dynamic_amplitudes=(1.0, 1.0, 1.0, 1.0),
        )
        retention = pillar_retention(observed_state=observed, flux_matrix=flux)
        for value in retention:
            self.assertAlmostEqual(value, 0.0, places=6)


if __name__ == '__main__':
    unittest.main()

