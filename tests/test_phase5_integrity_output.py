import json
import unittest

from eight_characters import __version__
from eight_characters.conventions import ConventionSettings
from eight_characters.engine import compute_engine_json, compute_engine_payload
from eight_characters.integrity import model_uncertainty_seconds_for_year
from eight_characters.output import dumps_deterministic
from eight_characters.time_convert import BirthInput


class TestIntegrityAndOutputContract(unittest.TestCase):
    def test_model_uncertainty_routing(self) -> None:
        self.assertEqual(model_uncertainty_seconds_for_year(1960), 1.5)
        self.assertEqual(model_uncertainty_seconds_for_year(2024), 0.5)

    def test_engine_payload_contains_required_sections(self) -> None:
        payload = compute_engine_payload(
            BirthInput(
                year=1988,
                month=2,
                day=4,
                hour=16,
                minute=30,
                second=0,
                timezone_name='Asia/Shanghai',
                longitude=104.066,
                latitude=30.658,
                conventions=ConventionSettings(),
            )
        )
        self.assertIn('engine', payload)
        self.assertIn('input', payload)
        self.assertIn('intermediate', payload)
        self.assertIn('pillars', payload)
        self.assertIn('flags', payload)
        self.assertIn('year', payload['pillars'])
        self.assertIn('month', payload['pillars'])
        self.assertIn('day', payload['pillars'])
        self.assertIn('hour', payload['pillars'])

    def test_deterministic_json_sorting(self) -> None:
        payload = {
            'z': 1,
            'a': {
                'd': 2.123456789,
                'c': 1,
            },
            'engine': {'version': '0.6.0'},
            'intermediate': {
                'solar_longitude_deg': 123.123456789,
                'equation_of_time_minutes': -13.854,
                'delta_t_seconds': 55.83,
                'tt_julian_date': 2447198.85481481,
            },
            'pillars': {
                'year': {'boundary': {'distance_seconds': -1536.044}},
                'month': {'boundary': {'distance_seconds': 2592000.033}},
            },
            'flags': {
                'hour_boundary_proximity_seconds': 4344.0444,
                'model_uncertainty_seconds': 0.5123,
            },
        }
        serialized = dumps_deterministic(payload)
        self.assertTrue(serialized.startswith('{"a"'))

    def test_compute_engine_json_is_valid_json(self) -> None:
        output_json = compute_engine_json(
            BirthInput(
                year=1988,
                month=2,
                day=4,
                hour=16,
                minute=30,
                second=0,
                timezone_name='Asia/Shanghai',
                longitude=104.066,
                latitude=30.658,
            )
        )
        parsed = json.loads(output_json)
        self.assertEqual(parsed['engine']['version'], __version__)
        self.assertIn('tt_julian_date', parsed['intermediate'])


if __name__ == '__main__':
    unittest.main()
