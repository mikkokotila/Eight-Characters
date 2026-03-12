import unittest

from fastapi.testclient import TestClient

from eight_characters.main import app


class TestApiEvolutionControlsEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_evolution_controls_returns_control_payload(self) -> None:
        response = self.client.get('/api/evolution_controls')
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertIn('controls', payload)
        controls = payload['controls']
        self.assertIn('main_view_controls', controls)
        self.assertIn('evolution_reading_controls', controls)
        self.assertIn('input_convention_controls', controls)

        particles = controls['main_view_controls']['particles']
        self.assertEqual(particles['value'], 24)
        self.assertEqual(particles['ui_label'], 'Particles')

        lambda_mode = controls['evolution_reading_controls']['scalar_constants'][
            'LAMBDA_MODE'
        ]
        self.assertEqual(lambda_mode['ui_label'], 'Structure-Mode Fidelity Weight')
        self.assertEqual(lambda_mode['value'], 4.0)
        self.assertNotIn('read_only', lambda_mode)


if __name__ == '__main__':
    unittest.main()
