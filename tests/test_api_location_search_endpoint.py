import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from eight_characters.main import LocationInput, ResolvedCity, app


class TestApiLocationSearchEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_location_search_resolves_city_and_country(self) -> None:
        with patch(
            'eight_characters.main._resolve_city_location',
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
        ) as resolve_mock:
            response = self.client.post(
                '/api/location_search',
                json={'city': 'Helsinki', 'country': 'Finland'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                'resolved_location': {
                    'city': 'Helsinki',
                    'country': 'Finland',
                    'timezone': 'Europe/Helsinki',
                }
            },
        )
        resolve_mock.assert_awaited_once_with('Helsinki', 'Finland')

    def test_location_search_accepts_city_without_country(self) -> None:
        with patch(
            'eight_characters.main._resolve_city_location',
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
        ) as resolve_mock:
            response = self.client.post('/api/location_search', json={'city': 'Helsinki'})

        self.assertEqual(response.status_code, 200)
        resolve_mock.assert_awaited_once_with('Helsinki', None)

    def test_location_search_returns_400_on_resolution_error(self) -> None:
        with patch(
            'eight_characters.main._resolve_city_location',
            new=AsyncMock(side_effect=ValueError('Could not resolve city')),
        ):
            response = self.client.post('/api/location_search', json={'city': 'Nowhere'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('Could not resolve city', response.json()['detail'])


if __name__ == '__main__':
    unittest.main()
