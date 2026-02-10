import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from eight_characters.solar_position import julian_date_from_datetime_utc
from eight_characters.solar_term_solver import find_solar_term


UTC = timezone.utc
HKT = timezone(timedelta(hours=8))
FIXTURE_PATH = Path('tests/fixtures/hko_solar_terms_2019_2028.json')


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
            computed_utc = datetime.fromtimestamp((computed_jd - 2440587.5) * 86400, tz=UTC)
            errors_seconds.append(abs((computed_utc - hko_utc).total_seconds()))

        self.assertEqual(len(errors_seconds), 240)
        self.assertLessEqual(max(errors_seconds), 420.0)
        self.assertLessEqual(sum(errors_seconds) / len(errors_seconds), 180.0)


if __name__ == '__main__':
    unittest.main()
