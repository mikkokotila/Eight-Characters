import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from eight_characters.main import (
    CityLookupServiceError,
    LocationInput,
    ResolvedCity,
    app,
)


class TestApiFourPillarsEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_canonical_case_returns_expected_pillars(self) -> None:
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

    def test_zi_convention_changes_day_hour_at_23(self) -> None:
        base_request = {
            'date': '2024-06-01',
            'time': '23:30:00',
            'location': {
                'timezone': 'Asia/Shanghai',
                'longitude': 116.4074,
                'latitude': 39.9042,
            },
            'conventions': {
                'zi_convention': 'split_midnight',
                'hour_basis': 'civil',
                'day_boundary_basis': 'civil',
            },
        }
        split_payload = self.client.post('/api/four_pillars', json=base_request).json()
        base_request['conventions']['zi_convention'] = 'whole_zi_23'
        whole_payload = self.client.post('/api/four_pillars', json=base_request).json()

        split_day = (
            split_payload['four_pillars']['day']['stem']['chinese']
            + split_payload['four_pillars']['day']['branch']['chinese']
        )
        whole_day = (
            whole_payload['four_pillars']['day']['stem']['chinese']
            + whole_payload['four_pillars']['day']['branch']['chinese']
        )
        self.assertNotEqual(split_day, whole_day)

    def test_civil_vs_true_solar_hour_basis_can_differ(self) -> None:
        base_request = {
            'date': '2024-06-01',
            'time': '14:00:00',
            'location': {
                'timezone': 'Asia/Shanghai',
                'longitude': 87.6,
                'latitude': 43.8,
            },
            'conventions': {
                'zi_convention': 'split_midnight',
                'hour_basis': 'civil',
                'day_boundary_basis': 'civil',
            },
        }
        civil_payload = self.client.post('/api/four_pillars', json=base_request).json()
        base_request['conventions']['hour_basis'] = 'true_solar'
        solar_payload = self.client.post('/api/four_pillars', json=base_request).json()
        civil_hour = civil_payload['four_pillars']['hour']['branch']['chinese']
        solar_hour = solar_payload['four_pillars']['hour']['branch']['chinese']
        self.assertNotEqual(civil_hour, solar_hour)

    def test_dst_ambiguous_requires_fold(self) -> None:
        response = self.client.post(
            '/api/four_pillars',
            json={
                'date': '2023-11-05',
                'time': '01:30:00',
                'location': {
                    'timezone': 'America/New_York',
                    'longitude': -74.006,
                    'latitude': 40.7128,
                },
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_dst_gap_rejected(self) -> None:
        response = self.client.post(
            '/api/four_pillars',
            json={
                'date': '2023-03-12',
                'time': '02:30:00',
                'location': {
                    'timezone': 'America/New_York',
                    'longitude': -74.006,
                    'latitude': 40.7128,
                },
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_date_format(self) -> None:
        response = self.client.post(
            '/api/four_pillars',
            json={
                'date': '1988/02/04',
                'time': '16:30:00',
                'location': {
                    'timezone': 'Asia/Shanghai',
                    'longitude': 104.066,
                    'latitude': 30.658,
                },
            },
        )
        self.assertEqual(response.status_code, 400)

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
        payload = response.json()
        self.assertIn('detail', payload)
        self.assertIsInstance(payload['detail'], str)
        self.assertIn('time', payload['detail'])

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
        self.assertEqual(
            set(payload.keys()),
            {'resolved_location', 'solar_time', 'four_pillars', 'flags', 'engine'},
        )
        self.assertEqual(payload['resolved_location']['city'], 'Helsinki')
        self.assertEqual(payload['resolved_location']['country'], 'Finland')
        self.assertEqual(payload['resolved_location']['timezone'], 'Europe/Helsinki')
        self.assertIn('true_solar_time', payload['solar_time'])
        self.assertIn('year', payload['four_pillars'])
        self.assertIn('month', payload['four_pillars'])
        self.assertIn('day', payload['four_pillars'])
        self.assertIn('hour', payload['four_pillars'])
        self.assertIn('zi_hour_window', payload['flags'])
        self.assertIn('version', payload['engine'])

    def test_four_pillars_rejects_mixed_location_and_city_country(self) -> None:
        response = self.client.post(
            '/api/four_pillars',
            json={
                'date': '1990-06-12',
                'time': '09:40',
                'location': {
                    'timezone': 'Europe/Helsinki',
                    'longitude': 24.9384,
                    'latitude': 60.1699,
                },
                'city': 'Helsinki',
                'country': 'Finland',
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_four_pillars_rejects_city_without_country(self) -> None:
        response = self.client.post(
            '/api/four_pillars',
            json={
                'date': '1990-06-12',
                'time': '09:40',
                'city': 'Helsinki',
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_four_pillars_can_embed_chart_and_hidden_stems(self) -> None:
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
                'include_chart': True,
                'include_hidden_stems': True,
                'lang': 'en',
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('chart', payload)
        self.assertIn('hidden_stems', payload)
        self.assertIn('header', payload['chart'])
        self.assertIn('year', payload['hidden_stems'])

    def test_bazi_endpoint_removed(self) -> None:
        response = self.client.post(
            '/api/bazi',
            json={
                'date': '1990-06-12',
                'time': '09:40',
                'city': 'Helsinki',
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_location_suggest_returns_suggestions(self) -> None:
        response = self.client.post(
            '/api/location_suggest',
            json={
                'query': 'Hels',
                'limit': 3,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('suggestions', payload)
        self.assertIsInstance(payload['suggestions'], list)

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
                json={
                    'query': 'Hels',
                    'limit': 3,
                },
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()['detail'], 'City lookup service unavailable.')


if __name__ == '__main__':
    unittest.main()
