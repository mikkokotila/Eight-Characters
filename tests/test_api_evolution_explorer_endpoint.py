import unittest
from typing import Any
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from eight_characters.evolution.pipeline import EvolutionInput
from eight_characters.main import (
    CityLookupServiceError,
    LocationInput,
    ResolvedCity,
    app,
)


class TestApiEvolutionExplorerEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_evolution_explorer_returns_graph_payload(self) -> None:
        fake_four_pillars = {
            'year': {'stem': {'chinese': '甲'}, 'branch': {'chinese': '子'}},
            'month': {'stem': {'chinese': '乙'}, 'branch': {'chinese': '丑'}},
            'day': {'stem': {'chinese': '丙'}, 'branch': {'chinese': '寅'}},
            'hour': {'stem': {'chinese': '丁'}, 'branch': {'chinese': '卯'}},
        }
        fake_hidden_stems: dict[str, dict[str, list[dict[str, str]]]] = {
            'year': {'hidden_stems': []},
            'month': {'hidden_stems': []},
            'day': {'hidden_stems': []},
            'hour': {'hidden_stems': []},
        }
        fake_graph_data: dict[str, Any] = {
            'meta': {'basin_id': 0, 'basin_count': 1},
            'nodes': [],
            'edges': [],
            'ghost_edges': [],
            'topology_modifiers': [],
            'motifs': {
                'chains': [],
                'loops': [],
                'cascades': [],
                'bottlenecks': [],
                'pulses': [],
                'absences': [],
            },
        }
        fake_evolution_input = EvolutionInput(
            branch_ids=(1, 2, 3, 4),
            base_elements=((1, 0, 0, 0, 0), (0, 1, 0, 0, 0), (0, 0, 1, 0, 0)),
            polarities=(1, 0, 1),
            hierarchy_levels=(4, 4, 4),
            positions=(1, 2, 3),
            masks=(1, 1, 1),
            vitality_stages=(1, 1, 1),
            day_master_index=2,
        )

        with patch(
            'eight_characters.main._resolve_four_pillars_location',
            new=AsyncMock(
                return_value=(
                    LocationInput(
                        timezone='Europe/Helsinki',
                        longitude=24.9384,
                        latitude=60.1699,
                    ),
                    ResolvedCity(
                        city='Helsinki',
                        country='Finland',
                        timezone='Europe/Helsinki',
                    ),
                )
            ),
        ) as resolve_mock, patch(
            'eight_characters.main._build_four_pillars_result',
            return_value={
                'solar_time': {},
                'four_pillars': fake_four_pillars,
                'flags': {},
                'engine': {},
            },
        ), patch(
            'eight_characters.main._build_hidden_stems_result',
            return_value=fake_hidden_stems,
        ), patch(
            'eight_characters.main._build_evolution_input_from_four_pillars',
            return_value=fake_evolution_input,
        ), patch(
            'eight_characters.main.run_natal_mvp',
            return_value=object(),
        ) as evolution_mock, patch(
            'eight_characters.main.asdict',
            return_value={},
        ), patch(
            'eight_characters.main.build_multi_basin_graph_data',
            return_value=fake_graph_data,
        ) as graph_mock:
            response = self.client.post(
                '/api/evolution_explorer',
                json={
                    'date': '1988-02-04',
                    'time': '16:30',
                    'city': 'Helsinki',
                    'country': 'Finland',
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['graph_data'], fake_graph_data)
        self.assertEqual(
            body['resolved_location'],
            {
                'city': 'Helsinki',
                'country': 'Finland',
                'timezone': 'Europe/Helsinki',
            },
        )
        resolve_mock.assert_awaited_once()
        evolution_mock.assert_called_once()
        graph_mock.assert_called_once()

    def test_evolution_explorer_returns_400_on_resolution_error(self) -> None:
        with patch(
            'eight_characters.main._resolve_four_pillars_location',
            new=AsyncMock(side_effect=ValueError('Could not resolve city')),
        ):
            response = self.client.post(
                '/api/evolution_explorer',
                json={
                    'date': '1988-02-04',
                    'time': '16:30',
                    'city': 'Nowhere',
                    'country': 'Nowhere',
                },
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Could not resolve city', response.json()['detail'])

    def test_evolution_explorer_returns_500_on_lookup_service_error(self) -> None:
        with patch(
            'eight_characters.main._resolve_four_pillars_location',
            new=AsyncMock(
                side_effect=CityLookupServiceError(
                    'City lookup service request failed.'
                )
            ),
        ):
            response = self.client.post(
                '/api/evolution_explorer',
                json={
                    'date': '1988-02-04',
                    'time': '16:30',
                    'city': 'Helsinki',
                    'country': 'Finland',
                },
            )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()['detail'], 'City lookup service unavailable.')


if __name__ == '__main__':
    unittest.main()
