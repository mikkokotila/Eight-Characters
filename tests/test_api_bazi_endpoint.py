import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from eight_characters.main import (
    CityLookupServiceError,
    LocationInput,
    ResolvedCity,
    app,
)


class TestApiBaziCompatibility(unittest.TestCase):
    """Compatibility-focused API tests after bazi->four_pillars migration."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_bazi_endpoint_removed(self) -> None:
        response = self.client.post(
            '/api/bazi',
            json={
                'date': '1988-02-04',
                'time': '16:30:00',
                'location': {
                    'timezone': 'Asia/Shanghai',
                    'longitude': 104.066,
                    'latitude': 30.658,
                },
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_four_pillars_canonical_case_returns_expected_pillars(self) -> None:
        response = self.client.post(
            '/api/four_pillars',
            json={
                'date': '1988-02-04',
                'time': '16:30:00',
                'location': {
                    'timezone': 'Asia/Shanghai',
                    'longitude': 104.066,
                    'latitude': 30.658,
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        pillars = payload['four_pillars']
        self.assertEqual(
            pillars['year']['stem']['chinese'] + pillars['year']['branch']['chinese'],
            '丁卯',
        )
        self.assertEqual(
            pillars['month']['stem']['chinese'] + pillars['month']['branch']['chinese'],
            '癸丑',
        )
        self.assertEqual(
            pillars['day']['stem']['chinese'] + pillars['day']['branch']['chinese'],
            '己丑',
        )
        self.assertEqual(
            pillars['hour']['stem']['chinese'] + pillars['hour']['branch']['chinese'],
            '壬申',
        )

    def test_four_pillars_accepts_time_without_seconds(self) -> None:
        response = self.client.post(
            '/api/four_pillars',
            json={
                'date': '1988-02-04',
                'time': '16:30',
                'location': {
                    'timezone': 'Asia/Shanghai',
                    'longitude': 104.066,
                    'latitude': 30.658,
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('solar_time', payload)
        self.assertIn('four_pillars', payload)

    def test_four_pillars_validation_errors_are_normalized(self) -> None:
        response = self.client.post(
            '/api/four_pillars',
            json={
                'date': '1988-02-04',
                'location': {
                    'timezone': 'Asia/Shanghai',
                    'longitude': 104.066,
                    'latitude': 30.658,
                },
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('detail', response.json())

    def test_four_pillars_accepts_city_country_and_exposes_resolved_location(
        self,
    ) -> None:
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
        ):
            response = self.client.post(
                '/api/four_pillars',
                json={
                    'date': '1990-06-12',
                    'time': '09:40',
                    'city': 'Helsinki',
                    'country': 'Finland',
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('resolved_location', payload)
        self.assertEqual(payload['resolved_location']['city'], 'Helsinki')
        self.assertEqual(payload['resolved_location']['country'], 'Finland')
        self.assertEqual(payload['resolved_location']['timezone'], 'Europe/Helsinki')

    def test_location_suggest_returns_suggestions(self) -> None:
        with patch(
            'eight_characters.main._search_city_candidates',
            new=AsyncMock(
                return_value=[
                    {
                        'name': 'Helsinki',
                        'country': 'Finland',
                        'timezone': 'Europe/Helsinki',
                        'longitude': 24.9384,
                        'latitude': 60.1699,
                    }
                ]
            ),
        ):
            response = self.client.post(
                '/api/location_suggest',
                json={'query': 'Hels', 'limit': 3},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('suggestions', payload)
        self.assertEqual(len(payload['suggestions']), 1)
        suggestion = payload['suggestions'][0]
        self.assertEqual(suggestion['city'], 'Helsinki')
        self.assertEqual(suggestion['country'], 'Finland')
        self.assertEqual(suggestion['timezone'], 'Europe/Helsinki')

    def test_location_suggest_returns_500_on_lookup_service_error(self) -> None:
        with patch(
            'eight_characters.main._search_city_candidates',
            new=AsyncMock(
                side_effect=CityLookupServiceError(
                    'City lookup service request failed.'
                )
            ),
        ):
            response = self.client.post(
                '/api/location_suggest',
                json={'query': 'Hels', 'limit': 3},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()['detail'], 'City lookup service unavailable.')


if __name__ == '__main__':
    unittest.main()
