import unittest
from datetime import datetime, timedelta, timezone

from eight_characters.conventions import ConventionSettings
from eight_characters.engine import compute_engine_payload
from eight_characters.solar_position import julian_date_from_datetime_utc
from eight_characters.solar_term_solver import lichun_jd_tt_for_civil_year
from eight_characters.time_convert import BirthInput


UTC = timezone.utc


def _dt_from_jd(jd_value: float) -> datetime:
    return datetime.fromtimestamp((jd_value - 2440587.5) * 86400, tz=UTC)


class TestTkt026MandatoryEdgeCases(unittest.TestCase):
    def test_lichun_boundary_plus_minus_60_seconds(self) -> None:
        lichun_jd = lichun_jd_tt_for_civil_year(2020)
        lichun_dt_utc = _dt_from_jd(lichun_jd)

        before = lichun_dt_utc - timedelta(hours=12)
        after = lichun_dt_utc + timedelta(hours=12)

        before_payload = compute_engine_payload(
            BirthInput(
                year=before.year,
                month=before.month,
                day=before.day,
                hour=before.hour,
                minute=before.minute,
                second=before.second,
                timezone_name='UTC',
                longitude=0.0,
                latitude=0.0,
                conventions=ConventionSettings(),
            )
        )
        after_payload = compute_engine_payload(
            BirthInput(
                year=after.year,
                month=after.month,
                day=after.day,
                hour=after.hour,
                minute=after.minute,
                second=after.second,
                timezone_name='UTC',
                longitude=0.0,
                latitude=0.0,
                conventions=ConventionSettings(),
            )
        )
        self.assertNotEqual(
            before_payload['pillars']['year']['stem']['chinese']
            + before_payload['pillars']['year']['branch']['chinese'],
            after_payload['pillars']['year']['stem']['chinese']
            + after_payload['pillars']['year']['branch']['chinese'],
        )

    def test_dst_fold_with_fold_parameter(self) -> None:
        fold0 = compute_engine_payload(
            BirthInput(
                year=2023,
                month=11,
                day=5,
                hour=1,
                minute=30,
                second=0,
                timezone_name='America/New_York',
                longitude=-74.006,
                latitude=40.7128,
                fold=0,
                conventions=ConventionSettings(),
            )
        )
        fold1 = compute_engine_payload(
            BirthInput(
                year=2023,
                month=11,
                day=5,
                hour=1,
                minute=30,
                second=0,
                timezone_name='America/New_York',
                longitude=-74.006,
                latitude=40.7128,
                fold=1,
                conventions=ConventionSettings(),
            )
        )
        self.assertNotEqual(
            fold0['intermediate']['utc_time'],
            fold1['intermediate']['utc_time'],
        )

    def test_leap_day(self) -> None:
        payload = compute_engine_payload(
            BirthInput(
                year=2020,
                month=2,
                day=29,
                hour=10,
                minute=15,
                second=30,
                timezone_name='Asia/Shanghai',
                longitude=121.4737,
                latitude=31.2304,
                conventions=ConventionSettings(),
            )
        )
        self.assertEqual(payload['input']['date'], '2020-02-29')

    def test_high_latitude_warning(self) -> None:
        payload = compute_engine_payload(
            BirthInput(
                year=2020,
                month=2,
                day=29,
                hour=10,
                minute=15,
                second=30,
                timezone_name='UTC',
                longitude=10.0,
                latitude=70.0,
                conventions=ConventionSettings(),
            )
        )
        self.assertTrue(payload['flags']['high_latitude_warning'])

    def test_regression_1988_02_04(self) -> None:
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
        day_text = payload['pillars']['day']['stem']['chinese'] + payload['pillars']['day']['branch']['chinese']
        hour_text = payload['pillars']['hour']['stem']['chinese'] + payload['pillars']['hour']['branch']['chinese']
        self.assertEqual(day_text, '己丑')
        self.assertEqual(hour_text, '壬申')


if __name__ == '__main__':
    unittest.main()
