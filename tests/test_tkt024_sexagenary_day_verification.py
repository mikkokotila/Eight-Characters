import unittest
from datetime import date, datetime, timedelta

from lunar_python import Solar

from eight_characters.conventions import (
    DAY_BOUNDARY_BASIS_CIVIL,
    HOUR_BASIS_CIVIL,
    ZI_CONVENTION_SPLIT_MIDNIGHT,
    ConventionSettings,
)
from eight_characters.sexagenary import BRANCHES, STEMS, day_pillar


class TestTkt024SexagenaryDayVerification(unittest.TestCase):
    def _idx0_from_ganzhi(self, ganzhi: str) -> int:
        stem_char = ganzhi[0]
        branch_char = ganzhi[1]
        stem_idx = STEMS.index(stem_char)
        branch_idx = BRANCHES.index(branch_char)
        for idx0 in range(60):
            if idx0 % 10 == stem_idx and idx0 % 12 == branch_idx:
                return idx0
        raise AssertionError('Invalid ganzhi mapping.')

    def test_anchor_dates(self) -> None:
        conventions = ConventionSettings(
            zi_convention=ZI_CONVENTION_SPLIT_MIDNIGHT,
            hour_basis=HOUR_BASIS_CIVIL,
            day_boundary_basis=DAY_BOUNDARY_BASIS_CIVIL,
        )
        anchors = [
            (datetime(2019, 1, 27, 12, 0, 0), 0),
            (datetime(2016, 10, 31, 12, 0, 0), 22),
            (datetime(1949, 10, 1, 12, 0, 0), 0),
            (datetime(1988, 2, 4, 12, 0, 0), 25),
        ]
        for anchor_dt, expected_idx in anchors:
            result = day_pillar(anchor_dt, anchor_dt, conventions)
            self.assertEqual(result.idx0, expected_idx)

    def test_full_year_against_lunar_python_2024(self) -> None:
        conventions = ConventionSettings(
            zi_convention=ZI_CONVENTION_SPLIT_MIDNIGHT,
            hour_basis=HOUR_BASIS_CIVIL,
            day_boundary_basis=DAY_BOUNDARY_BASIS_CIVIL,
        )
        start = date(2024, 1, 1)
        mismatches = 0
        total_days = 366

        for offset in range(total_days):
            day_value = start + timedelta(days=offset)
            dt_noon = datetime(day_value.year, day_value.month, day_value.day, 12, 0, 0)
            our_idx0 = day_pillar(dt_noon, dt_noon, conventions).idx0

            solar = Solar.fromYmdHms(day_value.year, day_value.month, day_value.day, 12, 0, 0)
            lunar_day_ganzhi = solar.getLunar().getDayInGanZhi()
            ref_idx0 = self._idx0_from_ganzhi(lunar_day_ganzhi)
            if our_idx0 != ref_idx0:
                mismatches += 1

        self.assertLessEqual(mismatches, 0)


if __name__ == '__main__':
    unittest.main()
