import unittest

from eight_characters.evolution.primitives import (
    ELEMENT_EARTH,
    ELEMENT_FIRE,
    ELEMENT_METAL,
    ELEMENT_WATER,
    ELEMENT_WOOD,
    authority_element,
    domain_resonance,
    life_stage_anchor,
    moisture_contribution,
    output_element,
    partial_state_weight,
    polarity_multiplier,
    season_score,
    stage_amplitude,
    temperature_contribution,
    ten_god_distance,
    ten_god_group,
    ten_god_to_one_hot,
    wealth_element,
    wuxing_interaction,
)


class TestEvolutionModuleCPrimitives(unittest.TestCase):
    def test_wuxing_matrix_values(self) -> None:
        self.assertEqual(wuxing_interaction(ELEMENT_WOOD, ELEMENT_FIRE), 1.0)
        self.assertEqual(wuxing_interaction(ELEMENT_WATER, ELEMENT_FIRE), -1.0)

    def test_polarity_multiplier(self) -> None:
        self.assertEqual(polarity_multiplier(1, 1), 1.2)
        self.assertEqual(polarity_multiplier(1, 0), 1.0)

    def test_element_operators(self) -> None:
        self.assertEqual(output_element(ELEMENT_WOOD), ELEMENT_FIRE)
        self.assertEqual(wealth_element(ELEMENT_WOOD), ELEMENT_EARTH)
        self.assertEqual(authority_element(ELEMENT_WOOD), ELEMENT_METAL)

    def test_life_stage_anchor(self) -> None:
        # Jia on Hai is Birth (1), Jia on Mao is Peak (5).
        self.assertEqual(life_stage_anchor(ELEMENT_WOOD, 1, 12), 1)
        self.assertEqual(life_stage_anchor(ELEMENT_WOOD, 1, 4), 5)

    def test_climate_contributions(self) -> None:
        self.assertEqual(temperature_contribution(ELEMENT_EARTH, 1), 0.5)
        self.assertEqual(temperature_contribution(ELEMENT_EARTH, 0), -0.5)
        self.assertEqual(moisture_contribution(ELEMENT_EARTH, 1), -1.0)
        self.assertEqual(moisture_contribution(ELEMENT_EARTH, 0), 0.5)

    def test_domain_resonance_values(self) -> None:
        # Day x Self
        self.assertEqual(domain_resonance(3, 0), 1.0)
        # Hour x Resource
        self.assertEqual(domain_resonance(4, 4), -1.0)

    def test_fixed_arrays(self) -> None:
        self.assertEqual(stage_amplitude(5), 1.0)
        self.assertEqual(stage_amplitude(10), 0.05)
        self.assertEqual(partial_state_weight(0), 0.0)
        self.assertEqual(partial_state_weight(2), 1.0)

    def test_season_score(self) -> None:
        # Spring sovereign Wood.
        self.assertEqual(season_score(ELEMENT_WOOD, ELEMENT_WOOD), 2)
        self.assertEqual(season_score(ELEMENT_FIRE, ELEMENT_WOOD), 1)
        self.assertEqual(season_score(ELEMENT_WATER, ELEMENT_WOOD), 0)
        self.assertEqual(season_score(ELEMENT_METAL, ELEMENT_WOOD), -1)
        self.assertEqual(season_score(ELEMENT_EARTH, ELEMENT_WOOD), -2)

    def test_ten_god_group_and_distance(self) -> None:
        self.assertEqual(ten_god_group(0), 0)
        self.assertEqual(ten_god_group(9), 4)
        a = ten_god_to_one_hot(0)
        b = ten_god_to_one_hot(0)
        c = ten_god_to_one_hot(1)
        self.assertEqual(ten_god_distance(a, b), 0)
        self.assertEqual(ten_god_distance(a, c), 1)


if __name__ == '__main__':
    unittest.main()

