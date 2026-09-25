import json
import statistics
import unittest
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from lunar_python.util.ShouXingUtil import ShouXingUtil

from eight_characters.engine import MONTH_BOUNDARIES, TERM_SEED_MONTH_DAY
from eight_characters.solar_position import J2000_JD, julian_date_from_datetime_utc
from eight_characters.solar_term_solver import find_solar_term
from eight_characters.time_convert import convert_utc_to_tt

UTC = UTC
HKT = timezone(timedelta(hours=8))
FIXTURE_PATH = Path('tests/fixtures/hko_solar_terms_2019_2028.json')


def term_utc(jd_tt: float) -> datetime:
    """A term's instant in UTC: the solver works in Terrestrial Time."""
    instant = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(days=jd_tt - 2440587.5)
    return instant - timedelta(seconds=convert_utc_to_tt(instant).tt_minus_utc_seconds)


def lunar_python_term_tt(days_from_j2000_tt: float) -> float:
    """lunar-python's instant of the solar term nearest a day, in TT days from J2000.

    Its `qiAccurate2` gives Beijing time, TT less its own Delta T plus 8 hours.
    """
    beijing = ShouXingUtil.qiAccurate2(days_from_j2000_tt)
    tt = beijing - ShouXingUtil.ONE_THIRD
    for _ in range(3):
        tt = beijing - ShouXingUtil.ONE_THIRD + ShouXingUtil.dtT(tt)
    return tt


class TestTkt023HkoSolarTermVerification(unittest.TestCase):
    def test_fixture_exists_and_has_expected_shape(self) -> None:
        self.assertTrue(FIXTURE_PATH.exists())
        fixture = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
        self.assertEqual(fixture['dataset'], 'hko_solar_terms')
        self.assertEqual(fixture['count'], 240)
        self.assertEqual(len(fixture['records']), 240)

    def test_hko_verification_statistics(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))
        errors_seconds: list[float] = []

        for record in fixture['records']:
            year_value = record['year']
            month_value = record['month']
            day_value = record['day']
            hour_value, minute_value = map(int, record['time_hm'].split(':'))
            target_longitude_deg = float(record['target_longitude_deg'])

            hko_utc = datetime(
                year_value,
                month_value,
                day_value,
                hour_value,
                minute_value,
                tzinfo=HKT,
            ).astimezone(UTC)
            seed_jd = julian_date_from_datetime_utc(
                datetime(year_value, month_value, day_value, 0, 0, 0, tzinfo=UTC)
            )
            computed_jd = find_solar_term(target_longitude_deg, seed_jd)
            errors_seconds.append(
                abs((term_utc(computed_jd) - hko_utc).total_seconds())
            )

        self.assertEqual(len(errors_seconds), 240)
        # The Observatory publishes to the nearest minute, up to 30 s from the
        # instant, and the engine's instants lie within about a second of its own.
        self.assertLessEqual(max(errors_seconds), 30.0 + 1.5)
        self.assertLessEqual(statistics.mean(errors_seconds), 20.0)

    def test_every_jie_1950_2100_matches_lunar_python(self) -> None:
        # Compared in TT: lunar-python turns TT into civil time with its own Delta T
        # for UT1, extrapolated into the future, where the engine uses UTC.
        errors_seconds: list[float] = []
        for year in range(1950, 2101):
            for target in MONTH_BOUNDARIES:
                month, day = TERM_SEED_MONTH_DAY[target]
                seed_jd = julian_date_from_datetime_utc(
                    datetime(year, month, day, tzinfo=UTC)
                )
                computed = find_solar_term(target, seed_jd) - J2000_JD
                reference = lunar_python_term_tt(computed)
                errors_seconds.append(abs(computed - reference) * 86400.0)
        self.assertEqual(len(errors_seconds), 1812)
        self.assertLessEqual(max(errors_seconds), 3.0)
        self.assertLessEqual(statistics.median(errors_seconds), 1.0)


if __name__ == '__main__':
    unittest.main()
