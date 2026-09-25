import json
import random
import unittest
from datetime import UTC, datetime, timedelta
from math import pi
from pathlib import Path
from unittest import mock

from eight_characters.embedded_data import ENGINE_MODEL_IDS
from eight_characters.engine import (
    MONTH_BOUNDARIES,
    _nearest_month_term_jds,  # pyright: ignore[reportPrivateUsage]
    _seed_jd_for_target,  # pyright: ignore[reportPrivateUsage]
)
from eight_characters.nutation import nutation_arcseconds
from eight_characters.obliquity import mean_obliquity_arcseconds_iau2006
from eight_characters.solar_position import (
    J2000_JD,
    compute_apparent_solar_longitude,
    compute_solar_position_and_tst,
    julian_date_from_datetime_utc,
)
from eight_characters.solar_term_solver import (
    find_solar_term,
    nearest_jie_distance_seconds,
)
from eight_characters.vsop87d import (
    DEG_PER_RAD,
    VSOP87D_EARTH_TERM_COUNTS,
    Series,
    astronomy_resource_text,
    earth_heliocentric_lbr,
    earth_series,
)

VSOP87_CHECK_PATH = Path('tests/fixtures/vsop87d_earth_check.json')
ARCSEC_PER_DEG = 3600.0
# Meeus, Astronomical Algorithms (2nd ed.), Appendix III, keeps the largest terms of
# each VSOP87D Earth series: this many for each power of time, of L, B and R.
MEEUS_APPENDIX_III_TERM_COUNTS = {
    1: (64, 34, 20, 7, 3, 1),
    2: (5, 2),
    3: (40, 10, 6, 2, 1),
}


def meeus_appendix_iii_series() -> dict[int, Series]:
    full = earth_series()
    return {
        variable: tuple(
            tuple(sorted(full[variable][power], key=lambda term: -term[0])[:count])
            for power, count in enumerate(counts)
        )
        for variable, counts in MEEUS_APPENDIX_III_TERM_COUNTS.items()
    }


UTC = UTC


class TestVsop87dEvaluator(unittest.TestCase):
    def test_earth_lbr_ranges(self) -> None:
        l_deg, b_deg, r_au = earth_heliocentric_lbr(0.0)
        self.assertGreaterEqual(l_deg, 0.0)
        self.assertLess(l_deg, 360.0)
        self.assertGreater(r_au, 0.9)
        self.assertLess(r_au, 1.1)
        self.assertLess(abs(b_deg), 1.0)

    def test_full_series_as_published(self) -> None:
        series = earth_series()
        for variable, counts in VSOP87D_EARTH_TERM_COUNTS.items():
            self.assertEqual(tuple(len(terms) for terms in series[variable]), counts)

    def test_matches_imcce_check_values(self) -> None:
        # IMCCE's own check values for VSOP87D Earth, printed to 1e-10.
        fixture = json.loads(VSOP87_CHECK_PATH.read_text(encoding='utf-8'))
        self.assertEqual(len(fixture['records']), 10)
        for record in fixture['records']:
            tau = (record['jd_tdb'] - J2000_JD) / 365250.0
            l_deg, b_deg, r_au = earth_heliocentric_lbr(tau)
            with self.subTest(jd=record['jd_tdb']):
                self.assertAlmostEqual(
                    l_deg / DEG_PER_RAD, record['l'] % (2 * pi), delta=1e-10
                )
                self.assertAlmostEqual(b_deg / DEG_PER_RAD, record['b'], delta=1e-10)
                self.assertAlmostEqual(r_au, record['r'], delta=1e-10)

    def test_altered_model_table_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, 'is not the published table'):
            astronomy_resource_text('VSOP87D.ear', '0' * 64)


class TestNutationModel(unittest.TestCase):
    def test_matches_meeus_example_22a(self) -> None:
        # 1987 April 10, 0h TD. Meeus gives -3.788" and +9.443" from the IAU 1980
        # series; IAU 2000A (R06) differs from it by 0.007" and 0.002" here.
        t_centuries = (2446895.5 - J2000_JD) / 36525.0
        delta_psi, delta_epsilon = nutation_arcseconds(t_centuries)
        self.assertAlmostEqual(delta_psi, -3.788, delta=0.01)
        self.assertAlmostEqual(delta_epsilon, 9.443, delta=0.01)

    def test_engine_reports_the_models_it_runs(self) -> None:
        self.assertEqual(ENGINE_MODEL_IDS['vsop87_series'], 'VSOP87D_full_Earth')
        self.assertEqual(ENGINE_MODEL_IDS['nutation_model'], 'IAU_2000A_R06')
        self.assertEqual(ENGINE_MODEL_IDS['mean_obliquity_model'], 'IAU_2006')


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

    def test_apparent_longitude_matches_meeus_example_25b(self) -> None:
        # 1992 October 13.0 TD: Meeus gives 199 deg 54' 21.818" and R = 0.99760775.
        # He evaluates the VSOP87D terms of his Appendix III, which put the Sun 0.27"
        # east of the full series. On those terms the engine reproduces both.
        with mock.patch(
            'eight_characters.vsop87d.earth_series', meeus_appendix_iii_series
        ):
            lambda_deg, _beta, radius_au, _dpsi, _deps, _t = (
                compute_apparent_solar_longitude(2448908.5)
            )
        meeus_deg = 199 + 54 / 60 + 21.818 / ARCSEC_PER_DEG
        self.assertAlmostEqual(
            (lambda_deg - meeus_deg) * ARCSEC_PER_DEG, 0.0, delta=0.01
        )
        self.assertAlmostEqual(radius_au, 0.99760775, delta=5e-9)


class TestSolarTermSearch(unittest.TestCase):
    def test_nearest_seeds_find_the_nearest_term(self) -> None:
        # Solving only the four seeds nearest the birth gives the same nearest jie
        # as solving all 36 jie of the civil year and the years around it.
        rng = random.Random(24)
        births = [
            datetime(1949, 1, 1, tzinfo=UTC)
            + timedelta(seconds=rng.randrange(0, 152 * 365 * 86400))
            for _ in range(24)
        ]
        # Right at each jie of 1988 and midway to the next: the hardest cases.
        for target in MONTH_BOUNDARIES:
            term_jd = find_solar_term(target, _seed_jd_for_target(1988, target))
            term = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
                days=term_jd - 2440587.5
            )
            births += [term - timedelta(seconds=1), term + timedelta(seconds=1)]
            births.append(term + timedelta(days=15))
        for birth in births:
            birth_jd = julian_date_from_datetime_utc(birth)
            everything = [
                find_solar_term(target, _seed_jd_for_target(year, target))
                for year in (birth.year - 1, birth.year, birth.year + 1)
                for target in MONTH_BOUNDARIES
            ]
            with self.subTest(birth=birth.isoformat()):
                self.assertEqual(
                    nearest_jie_distance_seconds(
                        birth_jd, _nearest_month_term_jds(birth.year, birth_jd)
                    ),
                    nearest_jie_distance_seconds(birth_jd, everything),
                )


if __name__ == '__main__':
    unittest.main()
