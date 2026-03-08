import unittest

from eight_characters.evolution import (
    MODE_FOLLOW_WEALTH,
    MODE_STANDARD,
    DerivedState,
    FullTransformationCapture,
    LatentState,
    ObservedState,
    active_mode_center,
    element_to_one_hot,
    recompute_effective_ten_gods,
    resolve_effective_elements,
)


def _active_index(one_hot: tuple[int, ...]) -> int:
    return one_hot.index(1)


def _build_observed_fixture() -> ObservedState:
    return ObservedState(
        branch_ids=(1, 2, 3, 4),
        base_elements=(
            element_to_one_hot(0),  # Wood
            element_to_one_hot(1),  # Fire
            element_to_one_hot(0),  # Day Master: Wood
            element_to_one_hot(3),  # Metal
        ),
        polarities=(1, 1, 1, 0),
        hierarchy_levels=(4, 4, 4, 4),
        positions=(1, 2, 3, 4),
        masks=(1, 1, 1, 1),
        vitality_stages=(5, 5, 5, 5),
        day_master_index=2,
    )


class TestEvolutionModuleAObservedState(unittest.TestCase):
    def test_observed_state_validation_accepts_valid_fixture(self) -> None:
        observed = _build_observed_fixture()
        observed.validate()

    def test_observed_state_rejects_invalid_one_hot(self) -> None:
        observed = _build_observed_fixture()
        bad_state = ObservedState(
            branch_ids=observed.branch_ids,
            base_elements=(
                (1, 0, 1, 0, 0),
                observed.base_elements[1],
                observed.base_elements[2],
                observed.base_elements[3],
            ),
            polarities=observed.polarities,
            hierarchy_levels=observed.hierarchy_levels,
            positions=observed.positions,
            masks=observed.masks,
            vitality_stages=observed.vitality_stages,
            day_master_index=observed.day_master_index,
        )
        with self.assertRaises(ValueError):
            bad_state.validate()


class TestEvolutionModuleALatentState(unittest.TestCase):
    def test_latent_state_rejects_invalid_mode(self) -> None:
        latent = LatentState(
            switches=(0,) * 34,
            omegas=(0.5,) * 34,
            mode='BadMode',
        )
        with self.assertRaises(ValueError):
            latent.validate()

    def test_latent_state_rejects_invalid_switch_domain(self) -> None:
        switches = list((0,) * 34)
        switches[17] = 3  # r=18 is frame domain {0,1,2}
        latent = LatentState(
            switches=tuple(switches),
            omegas=(0.5,) * 34,
            mode=MODE_STANDARD,
        )
        with self.assertRaises(ValueError):
            latent.validate()


class TestEvolutionModuleARewritesAndTenGods(unittest.TestCase):
    def test_resolve_effective_elements_applies_capture(self) -> None:
        observed = _build_observed_fixture()
        transformed = resolve_effective_elements(
            observed_state=observed,
            full_captures=(
                FullTransformationCapture(
                    rule_index=1,
                    entity_index=1,
                    target_element_index=2,
                ),
            ),
        )
        self.assertEqual(_active_index(transformed[1]), 2)

    def test_resolve_effective_elements_rejects_exclusivity_conflict(self) -> None:
        observed = _build_observed_fixture()
        with self.assertRaises(ValueError):
            resolve_effective_elements(
                observed_state=observed,
                full_captures=(
                    FullTransformationCapture(
                        rule_index=1,
                        entity_index=1,
                        target_element_index=2,
                    ),
                    FullTransformationCapture(
                        rule_index=2,
                        entity_index=1,
                        target_element_index=3,
                    ),
                ),
            )

    def test_recompute_ten_gods_under_standard_mode(self) -> None:
        observed = _build_observed_fixture()
        ten_gods = recompute_effective_ten_gods(
            observed_state=observed,
            effective_elements=observed.base_elements,
            mode=MODE_STANDARD,
        )
        self.assertEqual(_active_index(ten_gods[0]), 0)  # Companion (wood vs wood, same polarity)
        self.assertEqual(_active_index(ten_gods[1]), 2)  # Eating God (wood produces fire)
        self.assertEqual(_active_index(ten_gods[3]), 7)  # Direct Officer (metal controls wood, opposite polarity)

    def test_follow_wealth_mode_shifts_potential_center(self) -> None:
        observed = _build_observed_fixture()
        ten_gods = recompute_effective_ten_gods(
            observed_state=observed,
            effective_elements=observed.base_elements,
            mode=MODE_FOLLOW_WEALTH,
        )
        self.assertEqual(active_mode_center(day_master_element_index=0, mode=MODE_FOLLOW_WEALTH), 2)
        self.assertEqual(_active_index(ten_gods[2]), 6)  # DM appears as Seven Killings vs Earth center


class TestEvolutionModuleADerivedState(unittest.TestCase):
    def test_derived_state_validation_rejects_bad_amplitude(self) -> None:
        derived = DerivedState(
            effective_elements=(
                element_to_one_hot(0),
                element_to_one_hot(1),
            ),
            effective_ten_gods=(
                (1, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                (0, 1, 0, 0, 0, 0, 0, 0, 0, 0),
            ),
            dynamic_vitality_amplitudes=(0.5, 1.2),
            pillar_temperatures=(0.0, 0.0, 0.0, 0.0),
            pillar_saturations=(0.0, 0.0, 0.0, 0.0),
            chart_temperature=0.0,
            chart_saturation=0.0,
        )
        with self.assertRaises(ValueError):
            derived.validate(expected_entity_count=2)


if __name__ == '__main__':
    unittest.main()

