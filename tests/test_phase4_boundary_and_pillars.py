import unittest
from datetime import datetime, timezone

from eight_characters.conventions import (
    DAY_BOUNDARY_BASIS_CIVIL,
    DAY_BOUNDARY_BASIS_TRUE_SOLAR,
    HOUR_BASIS_CIVIL,
    HOUR_BASIS_TRUE_SOLAR,
    ZI_CONVENTION_SPLIT_MIDNIGHT,
    ZI_CONVENTION_WHOLE_ZI_23,
    ConventionSettings,
)
from eight_characters.root_finding import brentq, find_bracket
from eight_characters.sexagenary import (
    day_pillar,
    gregorian_to_jdn,
    hour_branch_index,
    hour_pillar,
    month_branch_index_from_longitude,
    month_pillar,
    year_pillar,
)
from eight_characters.solar_term_solver import nearest_jie_distance_seconds


UTC = timezone.utc


class TestRootFinding(unittest.TestCase):
    def test_find_bracket_simple_linear(self) -> None:
        def longitude_fn(jd_value: float) -> float:
            return jd_value

        a, b = find_bracket(10.0, 9.0, longitude_fn, step_days=0.25, max_steps=10)
        self.assertLessEqual(a, 10.0)
        self.assertGreaterEqual(b, 10.0)

    def test_brentq_simple_linear(self) -> None:
        root = brentq(lambda x: x - 2.0, 0.0, 5.0, xtol=1e-12)
        self.assertAlmostEqual(root, 2.0, places=9)


class TestBoundaryDistance(unittest.TestCase):
    def test_nearest_distance_seconds(self) -> None:
        distance = nearest_jie_distance_seconds(100.0, [99.99, 100.5, 98.0])
        self.assertAlmostEqual(distance, 0.01 * 86400.0, places=6)


class TestYearAndMonthPillars(unittest.TestCase):
    def test_year_pillar_boundary_before_after(self) -> None:
        before, bazi_year_before = year_pillar(civil_year=2020, birth_jd_tt=2458883.0, lichun_jd_tt=2458883.5)
        after, bazi_year_after = year_pillar(civil_year=2020, birth_jd_tt=2458884.0, lichun_jd_tt=2458883.5)
        self.assertEqual(bazi_year_before, 2019)
        self.assertEqual(bazi_year_after, 2020)
        before.validate_polarity()
        after.validate_polarity()

    def test_month_branch_mapping_wrap(self) -> None:
        self.assertEqual(month_branch_index_from_longitude(350.0), 3)
        self.assertEqual(month_branch_index_from_longitude(10.0), 3)
        self.assertEqual(month_branch_index_from_longitude(315.0), 2)
        self.assertEqual(month_branch_index_from_longitude(285.0), 1)

    def test_month_pillar_polarity(self) -> None:
        pillar = month_pillar(lambda_apparent_deg=320.0, year_stem_idx=3)
        pillar.validate_polarity()


class TestDayAndHourPillars(unittest.TestCase):
    def test_jdn_anchor_dates(self) -> None:
        self.assertEqual(gregorian_to_jdn(2019, 1, 27), 2458511)
        self.assertEqual(gregorian_to_jdn(2016, 10, 31), 2457693)
        self.assertEqual(gregorian_to_jdn(1949, 10, 1), 2433191)

    def test_day_pillar_anchor_idx0_values(self) -> None:
        conv = ConventionSettings(
            zi_convention=ZI_CONVENTION_SPLIT_MIDNIGHT,
            hour_basis=HOUR_BASIS_TRUE_SOLAR,
            day_boundary_basis=DAY_BOUNDARY_BASIS_CIVIL,
        )
        for anchor_date, expected_idx in (
            (datetime(2019, 1, 27, 12, 0, 0), 0),
            (datetime(2016, 10, 31, 12, 0, 0), 22),
            (datetime(1949, 10, 1, 12, 0, 0), 0),
            (datetime(1988, 2, 4, 12, 0, 0), 25),
        ):
            result = day_pillar(anchor_date, anchor_date, conv)
            self.assertEqual(result.idx0, expected_idx)

    def test_effective_date_divergence_with_true_solar_basis(self) -> None:
        conv = ConventionSettings(
            zi_convention=ZI_CONVENTION_SPLIT_MIDNIGHT,
            hour_basis=HOUR_BASIS_TRUE_SOLAR,
            day_boundary_basis=DAY_BOUNDARY_BASIS_TRUE_SOLAR,
        )
        civil_dt = datetime(2024, 6, 1, 0, 15, 0)
        tst_dt = datetime(2024, 5, 31, 23, 50, 0)
        result = day_pillar(civil_dt, tst_dt, conv)
        self.assertEqual(str(result.effective_date), '2024-05-31')

    def test_whole_zi_adjustment(self) -> None:
        conv = ConventionSettings(
            zi_convention=ZI_CONVENTION_WHOLE_ZI_23,
            hour_basis=HOUR_BASIS_CIVIL,
            day_boundary_basis=DAY_BOUNDARY_BASIS_CIVIL,
        )
        civil_dt = datetime(2024, 6, 1, 23, 10, 0)
        result = day_pillar(civil_dt, civil_dt, conv)
        self.assertEqual(str(result.effective_date), '2024-06-02')

    def test_hour_branch_mapping(self) -> None:
        self.assertEqual(hour_branch_index(23), 0)
        self.assertEqual(hour_branch_index(0), 0)
        self.assertEqual(hour_branch_index(1), 1)
        self.assertEqual(hour_branch_index(2), 1)
        self.assertEqual(hour_branch_index(21), 11)

    def test_hour_pillar_uses_selected_basis(self) -> None:
        conv = ConventionSettings(
            zi_convention=ZI_CONVENTION_SPLIT_MIDNIGHT,
            hour_basis=HOUR_BASIS_TRUE_SOLAR,
            day_boundary_basis=DAY_BOUNDARY_BASIS_CIVIL,
        )
        civil_dt = datetime(2024, 1, 1, 14, 0, 0)
        tst_dt = datetime(2024, 1, 1, 12, 30, 0)
        pillar = hour_pillar(day_stem_idx=5, civil_dt_local=civil_dt, tst_dt=tst_dt, conventions=conv)
        pillar.validate_polarity()


if __name__ == '__main__':
    unittest.main()
