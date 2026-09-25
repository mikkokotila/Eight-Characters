import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from eight_characters.main import (
    CityLookupServiceError,
    LocationInput,
    ResolvedCity,
    app,
)


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
                        region='Uusimaa',
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
                    'region': 'Uusimaa',
                    'country': 'Finland',
                    'timezone': 'Europe/Helsinki',
                    'latitude': 60.1699,
                    'longitude': 24.9384,
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
                        region='Uusimaa',
                        country='Finland',
                        timezone='Europe/Helsinki',
                    ),
                )
            ),
        ) as resolve_mock:
            response = self.client.post(
                '/api/location_search', json={'city': 'Helsinki'}
            )

        self.assertEqual(response.status_code, 200)
        resolve_mock.assert_awaited_once_with('Helsinki', None)

    def test_location_search_returns_400_on_resolution_error(self) -> None:
        with patch(
            'eight_characters.main._resolve_city_location',
            new=AsyncMock(side_effect=ValueError('Could not resolve city')),
        ):
            response = self.client.post(
                '/api/location_search', json={'city': 'Nowhere'}
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Could not resolve city', response.json()['detail'])

    def test_location_search_returns_500_on_lookup_service_error(self) -> None:
        with patch(
            'eight_characters.main._resolve_city_location',
            new=AsyncMock(
                side_effect=CityLookupServiceError(
                    'City lookup service request failed.'
                )
            ),
        ):
            response = self.client.post(
                '/api/location_search', json={'city': 'Helsinki'}
            )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()['detail'], 'City lookup service unavailable.')


def _geocoded(
    name: str,
    admin1: str | None,
    country: str | None,
    timezone: str,
    latitude: float,
    longitude: float,
    feature_code: str,
) -> dict[str, object]:
    return {
        'name': name,
        'admin1': admin1,
        'country': country,
        'timezone': timezone,
        'latitude': latitude,
        'longitude': longitude,
        'feature_code': feature_code,
    }


# Open-Meteo answers (2026-09-25), in the geocoder's order.
HELSINKI_ANSWER = [
    _geocoded(
        'Helsinki', 'Uusimaa', 'Finland', 'Europe/Helsinki', 60.16952, 24.93545, 'PPLC'
    ),
    _geocoded(
        'Helsinkibreen',
        'Svalbard',
        None,
        'Arctic/Longyearbyen',
        78.95583,
        16.83507,
        'GLCR',
    ),
    _geocoded(
        'Helsinkisaari',
        'Kymenlaakso',
        'Finland',
        'Europe/Helsinki',
        60.53756,
        27.10173,
        'ISL',
    ),
    _geocoded(
        'Helsinki Airport',
        'Uusimaa',
        'Finland',
        'Europe/Helsinki',
        60.31722,
        24.96333,
        'AIRP',
    ),
    _geocoded(
        'Helsinki-Malmi Airport',
        'Uusimaa',
        'Finland',
        'Europe/Helsinki',
        60.25456,
        25.04283,
        'AIRP',
    ),
]
LUXEMBOURG_ANSWER = [
    _geocoded(
        'Luxembourg', None, 'Luxembourg', 'Europe/Luxembourg', 49.75, 6.16667, 'PCLI'
    ),
    _geocoded(
        'Luxembourg',
        'Luxembourg',
        'Luxembourg',
        'Europe/Luxembourg',
        49.60982,
        6.13268,
        'PPLC',
    ),
    _geocoded(
        'Luxemburg',
        'Wisconsin',
        'United States',
        'America/Chicago',
        44.53861,
        -87.70398,
        'PPL',
    ),
    _geocoded(
        'Luxembourg Findel Airport',
        'Luxembourg',
        'Luxembourg',
        'Europe/Luxembourg',
        49.62658,
        6.21152,
        'AIRP',
    ),
]
HONG_KONG_ANSWER = [
    _geocoded('Hong Kong', None, None, 'Asia/Hong_Kong', 22.27832, 114.17469, 'PPLC'),
    _geocoded('Hong Kong', None, None, 'Asia/Hong_Kong', 22.26686, 114.17885, 'ISL'),
    _geocoded('Hong Kong', None, None, 'Asia/Hong_Kong', 22.25, 114.16667, 'PCLS'),
    _geocoded(
        'Hong Kong',
        'Baja California Sur',
        'Mexico',
        'America/Mazatlan',
        22.95805,
        -109.93898,
        'PPL',
    ),
]


class TestApiLocationSuggestEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def suggest(
        self, answer: list[dict[str, object]], query: str, limit: int
    ) -> list[str]:
        with patch(
            'eight_characters.main._search_city_candidates',
            new=AsyncMock(return_value=answer),
        ) as search_mock:
            response = self.client.post(
                '/api/location_suggest', json={'query': query, 'limit': limit}
            )
        self.assertEqual(response.status_code, 200)
        search_mock.assert_awaited_once_with(query, count=20)
        return [suggestion['display'] for suggestion in response.json()['suggestions']]

    def test_only_settlements_are_suggested(self) -> None:
        self.assertEqual(
            self.suggest(HELSINKI_ANSWER, 'Helsinki', 8), ['Helsinki, Uusimaa, Finland']
        )

    def test_a_country_is_not_suggested_in_place_of_its_capital(self) -> None:
        self.assertEqual(
            self.suggest(LUXEMBOURG_ANSWER, 'Luxembourg', 8),
            [
                'Luxembourg, Luxembourg, Luxembourg',
                'Luxemburg, Wisconsin, United States',
            ],
        )

    def test_a_city_state_without_a_country_is_still_suggested(self) -> None:
        self.assertEqual(
            self.suggest(HONG_KONG_ANSWER, 'Hong Kong', 8),
            ['Hong Kong', 'Hong Kong, Baja California Sur, Mexico'],
        )

    def test_administrative_areas_are_settlements(self) -> None:
        # Hypothetical row: the geocoder rarely returns ADM* for place names.
        municipality = _geocoded(
            'Vantaa',
            'Uusimaa',
            'Finland',
            'Europe/Helsinki',
            60.29414,
            25.04099,
            'ADM3',
        )
        self.assertEqual(
            self.suggest([municipality], 'Vantaa', 8), ['Vantaa, Uusimaa, Finland']
        )

    def test_a_result_without_a_feature_code_is_not_suggested(self) -> None:
        unclassified = {**HELSINKI_ANSWER[0]}
        del unclassified['feature_code']
        self.assertEqual(self.suggest([unclassified], 'Helsinki', 8), [])

    def test_the_limit_counts_settlements_only(self) -> None:
        answer = [HONG_KONG_ANSWER[2], *LUXEMBOURG_ANSWER, HELSINKI_ANSWER[0]]
        self.assertEqual(
            self.suggest(answer, 'Lux', 2),
            [
                'Luxembourg, Luxembourg, Luxembourg',
                'Luxemburg, Wisconsin, United States',
            ],
        )
        self.assertEqual(len(self.suggest(answer, 'Lux', 3)), 3)


if __name__ == '__main__':
    unittest.main()
