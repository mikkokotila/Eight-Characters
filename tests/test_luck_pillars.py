import json
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast

from lunar_python import Solar

from eight_characters.engine import compute_engine_json, compute_engine_payload
from eight_characters.luck_pillars import (
    build_luck_pillars,
    luck_direction,
    start_age_from_interval,
)
from eight_characters.sexagenary import Pillar
from eight_characters.solar_position import julian_date_from_datetime_utc
from eight_characters.solar_term_solver import lichun_jd_tt_for_civil_year
from eight_characters.time_convert import (
    BirthInput,
    Gender,
    TimeResolutionError,
    convert_utc_to_tt,
    utc_from_jd_tt,
)
from tests.test_tkt023_hko_solar_term_verification import lunar_python_term_tt


def birth(gender: Gender = 'male') -> BirthInput:
    return BirthInput(
        year=1988,
        month=2,
        day=4,
        hour=16,
        minute=30,
        second=0,
        timezone_name='Asia/Shanghai',
        longitude=104.066,
        latitude=30.658,
        gender=gender,
    )


def tt_jd(instant: datetime) -> float:
    return (
        julian_date_from_datetime_utc(instant)
        + convert_utc_to_tt(instant).tt_minus_utc_seconds / 86400
    )


def synthetic(
    born: datetime, days_to_jie: float, gender: Gender = 'male', count: int = 10
):
    jd = tt_jd(born)
    return build_luck_pillars(
        gender=gender,
        birth_utc=born,
        birth_jd_tt=jd,
        year_pillar=Pillar(0, 0),
        month_pillar=Pillar(9, 11),
        terms=[(315.0, jd - days_to_jie), (345.0, jd + days_to_jie)],
        labels={315.0: 'lichun_315', 345.0: 'jingzhe_345'},
        count=count,
    )


class TestLuckArithmetic(unittest.TestCase):
    def test_all_year_stems_and_both_genders(self):
        for stem in range(10):
            for gender in ('male', 'female'):
                expected = 1 if (stem in (0, 2, 4, 6, 8)) == (gender == 'male') else -1
                self.assertEqual(luck_direction(cast(Gender, gender), stem), expected)

    def test_classical_conversion_ratios_preserve_seconds(self):
        self.assertEqual(
            start_age_from_interval(3 * 86400),
            {
                'years': 1,
                'months': 0,
                'days': 0,
                'hours': 0,
                'minutes': 0,
                'seconds': 0.0,
            },
        )
        self.assertEqual(start_age_from_interval(86400)['months'], 4)
        self.assertEqual(start_age_from_interval(7200)['days'], 10)
        self.assertEqual(start_age_from_interval(60)['hours'], 2)
        self.assertEqual(start_age_from_interval(1)['minutes'], 2)
        self.assertEqual(start_age_from_interval(0.25)['seconds'], 30.0)

    def test_sequence_starts_after_month_and_wraps_both_cycles(self):
        for gender, expected in (
            ('male', [(0, 0), (1, 1), (2, 2)]),
            ('female', [(8, 10), (7, 9), (6, 8)]),
        ):
            payload = synthetic(
                datetime(2020, 1, 15, tzinfo=UTC), 3, cast(Gender, gender), 12
            )
            pillars = payload['pillars']
            self.assertEqual(
                [(p['stem']['index'], p['branch']['index']) for p in pillars[:3]],
                expected,
            )
            self.assertEqual([p['sequence'] for p in pillars], list(range(1, 13)))
            for p in pillars:
                self.assertEqual(p['stem']['index'] % 2, p['branch']['index'] % 2)

    def test_decades_are_contiguous_and_pre_luck_has_no_pillar(self):
        payload = synthetic(datetime(2020, 1, 15, tzinfo=UTC), 3)
        self.assertEqual(payload['start_utc'], '2021-01-15T00:00:00.000000Z')
        self.assertEqual(
            payload['pre_luck_period']['end_utc'], payload['pillars'][0]['start_utc']
        )
        self.assertNotIn('stem', payload['pre_luck_period'])
        for earlier, later in zip(payload['pillars'], payload['pillars'][1:]):
            self.assertEqual(earlier['end_utc'], later['start_utc'])
            self.assertEqual(earlier['end_age'], later['start_age'])

    def test_leap_birth_clamps_to_last_day(self):
        p = synthetic(datetime(2020, 2, 29, 12, tzinfo=UTC), 3)
        self.assertEqual(p['start_utc'], '2021-02-28T12:00:00.000000Z')

    def test_leap_onset_anniversaries_do_not_accumulate_clamping(self):
        # One age year plus one age day = 3 birth days plus 12 minutes.
        p = synthetic(datetime(2023, 2, 28, 12, tzinfo=UTC), 3 + 1 / 120)
        self.assertTrue(p['start_utc'].startswith('2024-02-29T12:00:'))
        self.assertTrue(p['pillars'][1]['start_utc'].startswith('2034-02-28T12:00:'))
        self.assertTrue(p['pillars'][2]['start_utc'].startswith('2044-02-29T12:00:'))

    def test_exact_jie_is_inclusive_backward_and_exclusive_forward(self):
        born = datetime(2020, 1, 15, tzinfo=UTC)
        jd = tt_jd(born)
        for gender, target, years in (('male', 345.0, 1), ('female', 315.0, 0)):
            p = build_luck_pillars(
                gender=cast(Gender, gender),
                birth_utc=born,
                birth_jd_tt=jd,
                year_pillar=Pillar(0, 0),
                month_pillar=Pillar(9, 11),
                terms=[(315.0, jd), (345.0, jd + 3)],
                labels={315.0: 'lichun_315', 345.0: 'jingzhe_345'},
            )
            self.assertEqual(p['reference_jie']['longitude_deg'], target)
            self.assertEqual(p['start_age']['years'], years)
            self.assertTrue(p['uncertainty']['boundary_ambiguous'])
        with self.assertRaises(RuntimeError):
            synthetic(born, 0)

    def test_invalid_inputs_fail_explicitly(self):
        for value in (-1.0, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                start_age_from_interval(value)
        for count in (0, 13, True, 1.5):
            with self.assertRaises(ValueError):
                synthetic(datetime(2020, 1, 15, tzinfo=UTC), 3, count=count)
        with self.assertRaises(ValueError):
            luck_direction(cast(Gender, 'unknown'), 0)


class TestLuckEngine(unittest.TestCase):
    def test_natal_payload_unchanged_and_gender_required_for_opt_in(self):
        old = compute_engine_payload(replace(birth(), gender=None))
        enriched = compute_engine_payload(birth(), include_luck_pillars=True)
        enriched.pop('luck_pillars')
        enriched['input'].pop('gender')
        self.assertEqual(old, enriched)
        with self.assertRaisesRegex(ValueError, 'gender is required'):
            compute_engine_payload(
                replace(birth(), gender=None), include_luck_pillars=True
            )

    def test_same_instant_has_same_luck_in_every_timezone(self):
        shanghai = compute_engine_payload(birth(), include_luck_pillars=True)[
            'luck_pillars'
        ]
        helsinki = compute_engine_payload(
            replace(
                birth(),
                hour=10,
                minute=30,
                timezone_name='Europe/Helsinki',
                longitude=24.9384,
                latitude=60.1699,
            ),
            include_luck_pillars=True,
        )['luck_pillars']
        utc = compute_engine_payload(
            BirthInput(
                utc_timestamp='1988-02-04T08:30:00Z',
                gender='male',
            ),
            include_luck_pillars=True,
        )['luck_pillars']
        self.assertEqual(shanghai, helsinki)
        self.assertEqual(shanghai, utc)

    def test_direction_and_month_anchor_change_at_lichun(self):
        term = lichun_jd_tt_for_civil_year(2023)
        for gender in ('male', 'female'):
            results = []
            for delta in (-300, 300):
                timestamp = (
                    utc_from_jd_tt(term) + timedelta(seconds=delta)
                ).isoformat()
                results.append(
                    compute_engine_payload(
                        BirthInput(
                            utc_timestamp=timestamp,
                            gender=cast(Gender, gender),
                        ),
                        include_luck_pillars=True,
                    )['luck_pillars']
                )
            self.assertNotEqual(results[0]['direction'], results[1]['direction'])
            self.assertNotEqual(
                results[0]['pillars'][0]['stem'], results[1]['pillars'][0]['stem']
            )
            self.assertNotEqual(
                results[0]['year_stem_polarity'], results[1]['year_stem_polarity']
            )
            if gender == 'male':
                # Yang male approaches Lichun forward; Yin male leaves it backward.
                self.assertEqual(
                    results[0]['reference_jie']['term'],
                    results[1]['reference_jie']['term'],
                )
            else:
                self.assertNotEqual(
                    results[0]['reference_jie']['term'],
                    results[1]['reference_jie']['term'],
                )

    def test_uncertainty_overlapping_jie_is_visible(self):
        term = lichun_jd_tt_for_civil_year(2023)
        value = BirthInput(
            utc_timestamp=(utc_from_jd_tt(term) + timedelta(seconds=10)).isoformat(),
            gender='male',
            birth_time_uncertainty_seconds=20,
        )
        p = compute_engine_payload(value, include_luck_pillars=True)['luck_pillars']
        self.assertTrue(p['uncertainty']['boundary_ambiguous'])
        self.assertEqual(p['uncertainty']['scaled_age_seconds'], 23 * 120)
        for uncertainty in (-1.0, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                compute_engine_payload(
                    replace(value, birth_time_uncertainty_seconds=uncertainty)
                )

    def test_both_supported_birth_endpoints_allow_full_lifetime_cycles(self):
        for year in (1949, 2100):
            p = compute_engine_payload(
                BirthInput(
                    utc_timestamp=f'{year}-12-31T12:00:00Z',
                    gender='male',
                ),
                include_luck_pillars=True,
                luck_pillar_count=12,
            )['luck_pillars']
            self.assertEqual(len(p['pillars']), 12)
            self.assertGreater(p['pillars'][-1]['end_utc'], f'{year + 100}-01-01')

    def test_json_is_deterministic(self):
        first = compute_engine_json(birth(), include_luck_pillars=True)
        self.assertEqual(first, compute_engine_json(birth(), include_luck_pillars=True))
        self.assertEqual(len(json.loads(first)['luck_pillars']['pillars']), 10)


class TestIndependentLuckReference(unittest.TestCase):
    def test_published_example_and_continuous_age_against_minute_method(self):
        # 6tail/lunar-python test/YunTest.py test5: male 2022-03-09 20:51,
        # sect=2 gives 8 years, 9 months, 2 days; starts 2030-12-12.
        value = BirthInput(
            year=2022,
            month=3,
            day=9,
            hour=20,
            minute=51,
            second=0,
            timezone_name='Asia/Shanghai',
            gender='male',
        )
        p = compute_engine_payload(value, include_luck_pillars=True)['luck_pillars']
        age = p['start_age']
        self.assertEqual((age['years'], age['months'], age['days']), (8, 9, 2))
        start = datetime.fromisoformat(p['start_utc']) + timedelta(hours=8)
        self.assertEqual(start.date().isoformat(), '2030-12-12')
        ref = (
            Solar.fromYmdHms(2022, 3, 9, 20, 51, 0)
            .getLunar()
            .getEightChar()
            .getYun(1, 2)
        )
        reference_start = datetime.fromisoformat(
            ref.getStartSolar().toYmdHms()
        ).replace(tzinfo=UTC)
        # The upstream method uses whole minutes; at 120x amplification, its
        # quantization plus the independent ephemeris difference is under 2h10m.
        self.assertLess(abs((start - reference_start).total_seconds()), 7800)

    def test_direction_sequences_and_jie_instants_against_package(self):
        for year in (1949, 1960, 1981, 1988, 2022, 2024, 2050, 2100):
            for gender in ('male', 'female'):
                with self.subTest(year=year, gender=gender):
                    value = BirthInput(
                        year=year,
                        month=6,
                        day=15,
                        hour=12,
                        minute=37,
                        second=29,
                        timezone_name='Asia/Shanghai',
                        gender=cast(Gender, gender),
                    )
                    p = compute_engine_payload(
                        value, include_luck_pillars=True, luck_pillar_count=12
                    )['luck_pillars']
                    ref = (
                        Solar.fromYmdHms(year, 6, 15, 12, 37, 29)
                        .getLunar()
                        .getEightChar()
                        .getYun(1 if gender == 'male' else 0, 2)
                    )
                    self.assertEqual(
                        p['direction'], 'forward' if ref.isForward() else 'backward'
                    )
                    self.assertEqual(
                        [
                            x['stem']['chinese'] + x['branch']['chinese']
                            for x in p['pillars']
                        ],
                        [x.getGanZhi() for x in ref.getDaYun(13)[1:]],
                    )
                    tt = p['reference_jie']['tt_julian_date'] - 2451545.0
                    self.assertLessEqual(
                        abs(tt - lunar_python_term_tt(tt)) * 86400, 3.0
                    )


class TestTimeScaleInversion(unittest.TestCase):
    def test_roundtrip_historical_modern_and_future(self):
        for instant in (
            datetime(1949, 1, 1, tzinfo=UTC),
            datetime(1971, 12, 31, 23, 58, tzinfo=UTC),
            datetime(1972, 1, 1, tzinfo=UTC),
            datetime(2017, 1, 1, tzinfo=UTC),
            datetime(2100, 12, 31, tzinfo=UTC),
        ):
            self.assertLess(
                abs((utc_from_jd_tt(tt_jd(instant)) - instant).total_seconds()), 0.0001
            )

    def test_unrepresentable_leap_second_fails(self):
        # 2016-12-31 inserted second, between TAI-UTC=36 and 37.
        transition = datetime(2017, 1, 1, tzinfo=UTC)
        with self.assertRaises(TimeResolutionError):
            utc_from_jd_tt(tt_jd(transition) - 0.5 / 86400)


if __name__ == '__main__':
    unittest.main()
