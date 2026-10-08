import unittest
from unittest.mock import AsyncMock, patch

from eight_characters.data import build_branch_data, build_stem_data
from eight_characters.main import LocationInput, ResolvedCity
from tests.accounts_support import signed_in_client


class TestApiLuckPillars(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = signed_in_client(cls)
        cls.base = {
            'date': '1988-02-04',
            'time': '16:30:00',
            'location': {
                'timezone': 'Asia/Shanghai',
                'longitude': 104.066,
                'latitude': 30.658,
            },
        }

    def test_opt_in_preserves_all_existing_natal_sections(self):
        base = {
            **self.base,
            'include_chart': True,
            'include_hidden_stems': True,
            'include_ten_gods': True,
            'include_interactions': True,
            'include_day_master_context': True,
            'include_role_profile': True,
            'include_reading': True,
        }
        response = self.client.post('/api/four_pillars', json=base)
        self.assertEqual(response.status_code, 200)
        legacy = response.json()
        self.assertNotIn('luck_pillars', legacy)
        for gender in ('male', 'female'):
            response = self.client.post(
                '/api/four_pillars',
                json={**base, 'gender': gender, 'include_luck_pillars': True},
            )
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            luck = result.pop('luck_pillars')
            # The luck pillars' own cards come with the chart; the natal chart is unchanged.
            luck_chart = result.pop('luck_chart')
            self.assertEqual(result, legacy)
            self.assertEqual(
                [
                    (entry['sequence'], entry['stem']['char'] + entry['branch']['char'])
                    for entry in luck_chart['pillars']
                ],
                [
                    (
                        pillar['sequence'],
                        pillar['stem']['chinese'] + pillar['branch']['chinese'],
                    )
                    for pillar in luck['pillars']
                ],
            )
            self.assertEqual(luck['gender'], gender)
            self.assertEqual(
                luck['direction'], 'backward' if gender == 'male' else 'forward'
            )
            self.assertEqual(len(luck['pillars']), 10)
            first = luck['pillars'][0]
            self.assertEqual(
                first['stem']['chinese'] + first['branch']['chinese'],
                '壬子' if gender == 'male' else '甲寅',
            )

    def test_luck_chart_draws_each_luck_pillar_as_the_chart_draws_natal_ones(self):
        # The sample of the luck design: 14 August 1975, 07:45, Helsinki, female.
        request = {
            'date': '1975-08-14',
            'time': '07:45',
            'location': {
                'timezone': 'Europe/Helsinki',
                'longitude': 24.94,
                'latitude': 60.17,
            },
            'gender': 'female',
            'include_luck_pillars': True,
            'include_chart': True,
        }
        for lang in ('fi', 'en'):
            with self.subTest(lang=lang):
                response = self.client.post(
                    '/api/four_pillars', json={**request, 'lang': lang}
                )
                self.assertEqual(response.status_code, 200, response.text)
                result = response.json()
                cards = result['luck_chart']['pillars']
                self.assertEqual(
                    [
                        entry['stem']['char'] + entry['branch']['char']
                        for entry in cards
                    ],
                    [
                        '乙酉',
                        '丙戌',
                        '丁亥',
                        '戊子',
                        '己丑',
                        '庚寅',
                        '辛卯',
                        '壬辰',
                        '癸巳',
                        '甲午',
                    ],
                )
                self.assertEqual(
                    [entry['sequence'] for entry in cards], list(range(1, 11))
                )
                for entry in cards:
                    self.assertEqual(
                        entry['stem'], build_stem_data(entry['stem']['char'], lang=lang)
                    )
                    self.assertEqual(
                        entry['branch'],
                        build_branch_data(entry['branch']['char'], lang=lang),
                    )
                # A character the natal chart shares is drawn as the natal chart draws it:
                # the seventh decade's 卯 Mao is the Year's branch, the eighth's 辰 Chen the Day's.
                natal = {
                    pillar['branch']['char']: pillar['branch']
                    for pillar in result['chart']['pillars']
                }
                self.assertEqual(cards[6]['branch'], natal['卯'])
                self.assertEqual(cards[7]['branch'], natal['辰'])
                self.assertEqual(
                    cards[7]['branch']['animal_name'],
                    'Lohikäärme' if lang == 'fi' else 'Dragon',
                )
        # Only a chart with its luck pillars has them.
        for extras in ({'include_chart': False}, {'include_luck_pillars': False}):
            response = self.client.post('/api/four_pillars', json={**request, **extras})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn('luck_chart', response.json())

    def test_gender_is_required_only_when_cycles_requested(self):
        for extras, expected in (
            ({}, 200),
            ({'gender': 'female'}, 200),
            ({'include_luck_pillars': True}, 400),
        ):
            response = self.client.post(
                '/api/four_pillars', json={**self.base, **extras}
            )
            self.assertEqual(response.status_code, expected)
            if expected == 400:
                self.assertIn('gender is required', response.json()['detail'])
            else:
                self.assertNotIn('luck_pillars', response.json())

    def test_invalid_gender_rejected_before_geocoding(self):
        with patch(
            'eight_characters.main._resolve_city_location', new=AsyncMock()
        ) as resolver:
            for gender in ('unknown', 'Male', '', 1, 0, True):
                response = self.client.post(
                    '/api/four_pillars',
                    json={
                        'date': '1988-02-04',
                        'time': '16:30',
                        'city': 'Chengdu',
                        'country': 'China',
                        'gender': gender,
                        'include_luck_pillars': True,
                    },
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn('gender', response.json()['detail'])
            resolver.assert_not_awaited()

    def test_count_is_bounded_strict_integer(self):
        for count in (1, 12):
            response = self.client.post(
                '/api/four_pillars',
                json={
                    **self.base,
                    'gender': 'male',
                    'include_luck_pillars': True,
                    'luck_pillar_count': count,
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(len(response.json()['luck_pillars']['pillars']), count)
        for count in (0, -1, 13, 1.5, True, '10'):
            response = self.client.post(
                '/api/four_pillars',
                json={
                    **self.base,
                    'gender': 'male',
                    'include_luck_pillars': True,
                    'luck_pillar_count': count,
                },
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn('luck_pillar_count', response.json()['detail'])

    def test_city_resolution_supplies_same_cycles_as_explicit_location(self):
        location = LocationInput(**self.base['location'])
        city = ResolvedCity(
            city='Chengdu', region='Sichuan', country='China', timezone='Asia/Shanghai'
        )
        with patch(
            'eight_characters.main._resolve_city_location',
            new=AsyncMock(return_value=(location, city)),
        ):
            resolved = self.client.post(
                '/api/four_pillars',
                json={
                    'date': self.base['date'],
                    'time': self.base['time'],
                    'city': 'Chengdu',
                    'country': 'China',
                    'gender': 'female',
                    'include_luck_pillars': True,
                },
            )
        explicit = self.client.post(
            '/api/four_pillars',
            json={**self.base, 'gender': 'female', 'include_luck_pillars': True},
        )
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(
            resolved.json()['luck_pillars'], explicit.json()['luck_pillars']
        )
        self.assertEqual(resolved.json()['resolved_location']['city'], 'Chengdu')

    def test_dst_fold_remains_explicit_and_different_instants_have_different_onsets(
        self,
    ):
        request = {
            **self.base,
            'date': '2023-11-05',
            'time': '01:30:00',
            'location': {
                'timezone': 'America/New_York',
                'longitude': -74.006,
                'latitude': 40.7128,
            },
            'gender': 'male',
            'include_luck_pillars': True,
        }
        self.assertEqual(
            self.client.post('/api/four_pillars', json=request).status_code, 400
        )
        results = []
        for fold in (0, 1):
            r = self.client.post(
                '/api/four_pillars',
                json={**request, 'location': {**request['location'], 'fold': fold}},
            )
            self.assertEqual(r.status_code, 200, r.text)
            results.append(r.json()['luck_pillars'])
        self.assertEqual(results[0]['direction'], results[1]['direction'])
        self.assertNotEqual(results[0]['start_utc'], results[1]['start_utc'])
        gap = {**request, 'date': '2023-03-12', 'time': '02:30:00'}
        self.assertEqual(
            self.client.post('/api/four_pillars', json=gap).status_code, 400
        )

    def test_negative_uncertainty_is_rejected(self):
        r = self.client.post(
            '/api/four_pillars',
            json={
                **self.base,
                'gender': 'male',
                'include_luck_pillars': True,
                'birth_time_uncertainty_seconds': -1,
            },
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn('uncertainty', r.json()['detail'])

    def test_internal_cycle_failure_surfaces_as_server_error(self):
        with patch(
            'eight_characters.engine.build_luck_pillars',
            side_effect=RuntimeError('broken ephemeris'),
        ):
            r = self.client.post(
                '/api/four_pillars',
                json={**self.base, 'gender': 'male', 'include_luck_pillars': True},
            )
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.json(), {'detail': 'Internal engine error.'})

    def test_finite_uncertainty_that_overflows_age_scaling_is_rejected(self):
        r = self.client.post(
            '/api/four_pillars',
            json={
                **self.base,
                'gender': 'male',
                'include_luck_pillars': True,
                'birth_time_uncertainty_seconds': 1e308,
            },
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn('uncertainty_seconds is too large', r.json()['detail'])

    def test_openapi_describes_gender_and_count(self):
        schema = self.client.get('/openapi.json').json()['components']['schemas'][
            'FourPillarsRequest'
        ]
        gender = schema['properties']['gender']['anyOf'][0]
        self.assertEqual(gender['enum'], ['male', 'female'])
        count = schema['properties']['luck_pillar_count']
        self.assertEqual(
            (count['minimum'], count['maximum'], count['default']), (1, 12, 10)
        )


if __name__ == '__main__':
    unittest.main()
