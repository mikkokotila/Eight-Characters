import json
import random
import unittest
from datetime import datetime
from pathlib import Path

from lunar_python import Solar

from eight_characters.conventions import (
    DAY_BOUNDARY_BASIS_CIVIL,
    HOUR_BASIS_CIVIL,
    ZI_CONVENTION_SPLIT_MIDNIGHT,
    ConventionSettings,
)
from eight_characters.engine import compute_engine_payload
from eight_characters.time_convert import BirthInput


REPORT_PATH = Path('tests/fixtures/tkt025_cross_verification_report.json')


def _pillar_as_text(pillar: dict) -> str:
    return f"{pillar['stem']['chinese']}{pillar['branch']['chinese']}"


class TestTkt025CrossVerification(unittest.TestCase):
    def test_cross_verify_1000_random_cases(self) -> None:
        rng = random.Random(25)
        conventions = ConventionSettings(
            zi_convention=ZI_CONVENTION_SPLIT_MIDNIGHT,
            hour_basis=HOUR_BASIS_CIVIL,
            day_boundary_basis=DAY_BOUNDARY_BASIS_CIVIL,
        )

        mismatch_examples: list[dict] = []
        mismatch_count = 0
        total = 1000

        for _ in range(total):
            year_value = rng.randint(1950, 2050)
            month_value = rng.randint(1, 12)
            day_value = rng.randint(1, 28)
            hour_value = rng.randint(0, 23)
            minute_value = rng.randint(0, 59)
            second_value = rng.randint(0, 59)

            payload = compute_engine_payload(
                BirthInput(
                    year=year_value,
                    month=month_value,
                    day=day_value,
                    hour=hour_value,
                    minute=minute_value,
                    second=second_value,
                    timezone_name='Asia/Shanghai',
                    longitude=116.4074,
                    latitude=39.9042,
                    conventions=conventions,
                )
            )
            our_year = _pillar_as_text(payload['pillars']['year'])
            our_month = _pillar_as_text(payload['pillars']['month'])
            our_day = _pillar_as_text(payload['pillars']['day'])
            our_hour = _pillar_as_text(payload['pillars']['hour'])

            solar = Solar.fromYmdHms(
                year_value,
                month_value,
                day_value,
                hour_value,
                minute_value,
                second_value,
            )
            ec = solar.getLunar().getEightChar()
            ref_year = ec.getYear()
            ref_month = ec.getMonth()
            ref_day = ec.getDay()
            ref_hour = ec.getTime()

            mismatch_fields = []
            if our_year != ref_year:
                mismatch_fields.append('year')
            if our_month != ref_month:
                mismatch_fields.append('month')
            if our_day != ref_day:
                mismatch_fields.append('day')
            if our_hour != ref_hour:
                mismatch_fields.append('hour')

            if mismatch_fields:
                mismatch_count += 1
                if len(mismatch_examples) < 25:
                    mismatch_examples.append(
                        {
                            'input': {
                                'year': year_value,
                                'month': month_value,
                                'day': day_value,
                                'hour': hour_value,
                                'minute': minute_value,
                                'second': second_value,
                            },
                            'mismatch_fields': mismatch_fields,
                            'ours': {
                                'year': our_year,
                                'month': our_month,
                                'day': our_day,
                                'hour': our_hour,
                            },
                            'reference': {
                                'year': ref_year,
                                'month': ref_month,
                                'day': ref_day,
                                'hour': ref_hour,
                            },
                        }
                    )

        report = {
            'total': total,
            'mismatch_count': mismatch_count,
            'mismatch_ratio': mismatch_count / total,
            'examples': mismatch_examples,
        }
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

        self.assertEqual(total, 1000)
        self.assertLessEqual(mismatch_count, 100)


if __name__ == '__main__':
    unittest.main()
