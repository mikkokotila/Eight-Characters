import unittest
from datetime import datetime, timezone

from eight_characters.obliquity import mean_obliquity_arcseconds_iau2006
from eight_characters.solar_position import (
    J2000_JD,
    compute_apparent_solar_longitude,
    compute_solar_position_and_tst,
    julian_date_from_datetime_utc,
)
from eight_characters.vsop87d import earth_heliocentric_lbr


UTC = timezone.utc


class TestVsop87dEvaluator(unittest.TestCase):
    def test_earth_lbr_ranges(self) -> None:
        l_deg, b_deg, r_au = earth_heliocentric_lbr(0.0)
        self.assertGreaterEqual(l_deg, 0.0)
        self.assertLess(l_deg, 360.0)
        self.assertGreater(r_au, 0.9)
        self.assertLess(r_au, 1.1)
        self.assertLess(abs(b_deg), 1.0)


class TestObliquityModel(unittest.TestCase):
    def test_iau2006_mean_obliquity_at_j2000(self) -> None:
        value = mean_obliquity_arcseconds_iau2006(0.0)
        self.assertAlmostEqual(value, 84381.406, places=3)


class TestSolarPositionKernel(unittest.TestCase):
    def test_julian_date_reference(self) -> None:
        jd = julian_date_from_datetime_utc(datetime(2000, 1, 1, 12, 0, 0, tzinfo=UTC))
        self.assertAlmostEqual(jd, J2000_JD, places=6)

    def test_apparent_longitude_is_normalized(self) -> None:
        (
            lambda_apparent_deg,
            beta_deg,
            radius_au,
            _delta_psi,
            _delta_epsilon,
            _t_centuries,
        ) = compute_apparent_solar_longitude(J2000_JD)
        self.assertGreaterEqual(lambda_apparent_deg, 0.0)
        self.assertLess(lambda_apparent_deg, 360.0)
        self.assertGreater(radius_au, 0.9)
        self.assertLess(abs(beta_deg), 1.0)

    def test_tst_pipeline(self) -> None:
        result = compute_solar_position_and_tst(
            utc_datetime=datetime(1988, 2, 4, 8, 30, 0, tzinfo=UTC),
            longitude_deg=104.066,
            tt_minus_utc_seconds=55.8,
        )
        self.assertGreaterEqual(result.lambda_apparent_deg, 0.0)
        self.assertLess(result.lambda_apparent_deg, 360.0)
        self.assertGreater(result.radius_au, 0.9)
        self.assertLess(result.radius_au, 1.1)
        self.assertIsNone(result.local_mean_solar_time.tzinfo)
        self.assertIsNone(result.true_solar_time.tzinfo)


if __name__ == '__main__':
    unittest.main()
