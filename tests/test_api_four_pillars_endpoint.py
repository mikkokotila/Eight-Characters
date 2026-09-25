import unittest
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from eight_characters.main import (
    CityLookupServiceError,
    LocationInput,
    ResolvedCity,
    app,
)

# The first geocoder results for 'Chengdu' (open-meteo, 2026-09-25): three places
# with the same name, two of them in the same province.
CHENGDU_GEOCODER_RESULTS: list[dict[str, Any]] = [
    {
        'name': 'Chengdu',
        'admin1': 'Sichuan',
        'country': 'China',
        'timezone': 'Asia/Shanghai',
        'latitude': 30.66667,
        'longitude': 104.06667,
    },
    {
        'name': 'Chengdu',
        'admin1': 'Jiangxi',
        'country': 'China',
        'timezone': 'Asia/Shanghai',
        'latitude': 26.36828,
        'longitude': 115.34289,
    },
    {
        'name': 'Chengdu',
        'admin1': 'Jiangxi',
        'country': 'China',
        'timezone': 'Asia/Shanghai',
        'latitude': 26.983,
        'longitude': 114.207,
    },
]


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
                        region='Uusimaa',
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
        self.assertEqual(
            payload['resolved_location'],
            {
                'city': 'Helsinki',
                'region': 'Uusimaa',
                'country': 'Finland',
                'timezone': 'Europe/Helsinki',
                'latitude': 60.1699,
                'longitude': 24.9384,
            },
        )
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

    def _suggestions_for_chengdu(self) -> list[dict[str, Any]]:
        with patch(
            'eight_characters.main._search_city_candidates',
            new=AsyncMock(return_value=CHENGDU_GEOCODER_RESULTS),
        ):
            response = self.client.post(
                '/api/location_suggest', json={'query': 'Chengdu', 'limit': 8}
            )
        self.assertEqual(response.status_code, 200)
        return response.json()['suggestions']

    def test_location_suggest_tells_apart_places_that_share_a_name(self) -> None:
        self.assertEqual(
            self._suggestions_for_chengdu(),
            [
                {
                    'city': 'Chengdu',
                    'region': 'Sichuan',
                    'country': 'China',
                    'timezone': 'Asia/Shanghai',
                    'latitude': 30.66667,
                    'longitude': 104.06667,
                    'display': 'Chengdu, Sichuan, China',
                },
                {
                    'city': 'Chengdu',
                    'region': 'Jiangxi',
                    'country': 'China',
                    'timezone': 'Asia/Shanghai',
                    'latitude': 26.36828,
                    'longitude': 115.34289,
                    'display': 'Chengdu, Jiangxi, China',
                },
                {
                    'city': 'Chengdu',
                    'region': 'Jiangxi',
                    'country': 'China',
                    'timezone': 'Asia/Shanghai',
                    'latitude': 26.983,
                    'longitude': 114.207,
                    'display': 'Chengdu, Jiangxi, China',
                },
            ],
        )

    def test_location_suggest_label_leaves_out_missing_region_and_country(
        self,
    ) -> None:
        with patch(
            'eight_characters.main._search_city_candidates',
            new=AsyncMock(
                return_value=[
                    {
                        'name': 'Hong Kong',
                        'timezone': 'Asia/Hong_Kong',
                        'latitude': 22.27832,
                        'longitude': 114.17469,
                    }
                ]
            ),
        ):
            response = self.client.post(
                '/api/location_suggest', json={'query': 'Hong Kong', 'limit': 8}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()['suggestions'],
            [
                {
                    'city': 'Hong Kong',
                    'region': '',
                    'country': '',
                    'timezone': 'Asia/Hong_Kong',
                    'latitude': 22.27832,
                    'longitude': 114.17469,
                    'display': 'Hong Kong',
                }
            ],
        )

    def test_four_pillars_computes_for_the_picked_suggestion(self) -> None:
        suggestions = self._suggestions_for_chengdu()

        def pillars_for(suggestion: dict[str, Any]) -> dict[str, Any]:
            # The page sends the picked place as `location`; nothing is looked up again.
            with patch(
                'eight_characters.main._search_city_candidates', new=AsyncMock()
            ) as lookup:
                response = self.client.post(
                    '/api/four_pillars',
                    json={
                        'date': '1988-02-04',
                        'time': '15:40',
                        'location': {
                            key: suggestion[key]
                            for key in ('timezone', 'latitude', 'longitude')
                        },
                    },
                )
            lookup.assert_not_awaited()
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertNotIn('resolved_location', payload)
            return payload

        def hour_pillar(payload: dict[str, Any]) -> str:
            hour = payload['four_pillars']['hour']
            return hour['stem']['chinese'] + hour['branch']['chinese']

        sichuan = pillars_for(suggestions[0])
        jiangxi = pillars_for(suggestions[1])
        # Local mean solar time runs 4 minutes ahead of UTC (07:40) per degree east.
        for payload, longitude in ((sichuan, 104.06667), (jiangxi, 115.34289)):
            local_mean_solar_time = datetime.fromisoformat(
                payload['solar_time']['local_mean_solar_time']
            )
            expected = datetime(1988, 2, 4, 7, 40) + timedelta(minutes=4 * longitude)
            self.assertLess(
                abs((local_mean_solar_time - expected).total_seconds()), 1.0
            )
        # True solar time 14:22 falls in the 未 hour, 15:07 in the 申 hour.
        self.assertEqual(hour_pillar(sichuan), '辛未')
        self.assertEqual(hour_pillar(jiangxi), '壬申')

    def test_four_pillars_city_country_reports_the_place_it_resolved_to(
        self,
    ) -> None:
        with patch(
            'eight_characters.main._search_city_candidates',
            new=AsyncMock(return_value=CHENGDU_GEOCODER_RESULTS),
        ):
            response = self.client.post(
                '/api/four_pillars',
                json={
                    'date': '1988-02-04',
                    'time': '15:40',
                    'city': 'Chengdu',
                    'country': 'China',
                },
            )

        self.assertEqual(response.status_code, 200)
        # A name resolves to the first match in that country, and the response says which.
        self.assertEqual(
            response.json()['resolved_location'],
            {
                'city': 'Chengdu',
                'region': 'Sichuan',
                'country': 'China',
                'timezone': 'Asia/Shanghai',
                'latitude': 30.66667,
                'longitude': 104.06667,
            },
        )


if __name__ == '__main__':
    unittest.main()
