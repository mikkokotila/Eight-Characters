import unittest
from copy import deepcopy
from datetime import datetime

from eight_characters.architecture import MODULE_CONTRACTS, validate_module_contracts
from eight_characters.conventions import (
    ConventionSettings,
    all_supported_convention_combinations,
)
from eight_characters.policy import (
    EnginePolicy,
    decision_ids,
    route_time_conversion,
    validate_core_input_scope,
)


class TestPhase1Policy(unittest.TestCase):
    def test_decisions_cover_expected_count(self) -> None:
        self.assertEqual(len(decision_ids()), 26)
        self.assertIn('D-007a', decision_ids())

    def test_year_range_validation(self) -> None:
        policy = EnginePolicy()
        policy.validate_year(1949)
        policy.validate_year(2100)
        with self.assertRaises(ValueError):
            policy.validate_year(1948)
        with self.assertRaises(ValueError):
            policy.validate_year(2101)

    def test_calendar_and_scope_enforcement(self) -> None:
        with self.assertRaises(ValueError):
            validate_core_input_scope(
                year=1988,
                calendar='julian',
                conventions=ConventionSettings(),
            )
        with self.assertRaises(ValueError):
            validate_core_input_scope(
                year=1988,
                calendar='gregorian',
                conventions=ConventionSettings(),
                include_interpretive_layers=True,
            )

    def test_forbidden_dependency_policy(self) -> None:
        policy = EnginePolicy()
        with self.assertRaises(ValueError):
            policy.validate_dependency_policy(['fastapi', 'scipy'])
        policy.validate_dependency_policy(['fastapi', 'jinja2'])

    def test_conversion_routing(self) -> None:
        self.assertEqual(
            route_time_conversion(datetime(1972, 1, 1)),
            'post_1972_leap_seconds',
        )
        self.assertEqual(
            route_time_conversion(datetime(1971, 12, 31, 23, 59, 59)),
            'pre_1972_delta_t',
        )


class TestPhase1Conventions(unittest.TestCase):
    def test_default_conventions_are_valid(self) -> None:
        ConventionSettings().validate()

    def test_invalid_convention_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ConventionSettings(zi_convention='bad').validate()

    def test_all_convention_combinations(self) -> None:
        combos = all_supported_convention_combinations()
        self.assertEqual(len(combos), 8)
        for combo in combos:
            combo.validate()


class TestPhase1Architecture(unittest.TestCase):
    def test_module_contracts_have_no_cycles(self) -> None:
        validate_module_contracts()

    def test_cycle_detection_raises(self) -> None:
        bad_graph = deepcopy(MODULE_CONTRACTS)
        bad_graph['conventions'] = bad_graph['conventions'].__class__(
            name='conventions',
            responsibility='bad cycle fixture',
            dependencies=('engine',),
        )
        with self.assertRaises(ValueError):
            validate_module_contracts(bad_graph)

    def test_unknown_dependency_raises(self) -> None:
        bad_graph = deepcopy(MODULE_CONTRACTS)
        bad_graph['engine'] = bad_graph['engine'].__class__(
            name='engine',
            responsibility='bad dependency fixture',
            dependencies=('not_a_real_module',),
        )
        with self.assertRaises(ValueError):
            validate_module_contracts(bad_graph)


if __name__ == '__main__':
    unittest.main()
