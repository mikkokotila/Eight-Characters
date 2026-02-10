import unittest
from datetime import datetime, timezone

from eight_characters.conventions import ConventionSettings
from eight_characters.embedded_data import (
    DELTA_T_SEGMENTS,
    evaluate_delta_t_seconds,
    get_leap_second_offset_seconds,
)
from eight_characters.time_convert import (
    AmbiguousTimeError,
    BirthInput,
    NonexistentTimeError,
    convert_utc_to_tt,
    decimal_year,
    normalize_birth_input,
)


UTC = timezone.utc


class TestEmbeddedDataLayer(unittest.TestCase):
    def test_delta_t_segments_exist(self) -> None:
        self.assertEqual(len(DELTA_T_SEGMENTS), 5)

    def test_delta_t_1950_reference_variable(self) -> None:
        value = evaluate_delta_t_seconds(1950.0)
        self.assertAlmostEqual(value, 29.07, places=2)

    def test_leap_second_offsets(self) -> None:
        before_1972 = get_leap_second_offset_seconds(datetime(1971, 12, 31, 12, tzinfo=UTC))
        at_2017 = get_leap_second_offset_seconds(datetime(2017, 1, 1, 0, 0, 0, tzinfo=UTC))
        self.assertEqual(before_1972, 0)
        self.assertEqual(at_2017, 37)


class TestInputAndTimeResolution(unittest.TestCase):
    def test_utc_timestamp_mode(self) -> None:
        normalized = normalize_birth_input(
            BirthInput(
                utc_timestamp='1988-02-04T08:30:00Z',
                timezone_name='Asia/Shanghai',
                longitude=104.066,
                latitude=30.658,
                conventions=ConventionSettings(),
            )
        )
        self.assertEqual(normalized.utc_datetime, datetime(1988, 2, 4, 8, 30, tzinfo=UTC))
        self.assertIsNone(normalized.civil_datetime_local)

    def test_high_latitude_warning(self) -> None:
        normalized = normalize_birth_input(
            BirthInput(
                year=1988,
                month=2,
                day=4,
                hour=16,
                minute=30,
                second=0,
                timezone_name='Asia/Shanghai',
                longitude=104.066,
                latitude=70.0,
            )
        )
        self.assertTrue(normalized.high_latitude_warning)

    def test_dst_gap_rejected(self) -> None:
        with self.assertRaises(NonexistentTimeError):
            normalize_birth_input(
                BirthInput(
                    year=2023,
                    month=3,
                    day=12,
                    hour=2,
                    minute=30,
                    second=0,
                    timezone_name='America/New_York',
                    longitude=-74.006,
                    latitude=40.7128,
                )
            )

    def test_dst_fold_requires_explicit_fold(self) -> None:
        with self.assertRaises(AmbiguousTimeError):
            normalize_birth_input(
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
                )
            )

    def test_dst_fold_uses_distinct_utc_values(self) -> None:
        first = normalize_birth_input(
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
            )
        )
        second = normalize_birth_input(
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
            )
        )
        self.assertNotEqual(first.utc_datetime, second.utc_datetime)


class TestTTConversion(unittest.TestCase):
    def test_decimal_year_exact_fraction(self) -> None:
        value = decimal_year(datetime(2000, 7, 2, 12, 0, 0, tzinfo=UTC))
        self.assertGreater(value, 2000.49)
        self.assertLess(value, 2000.51)

    def test_post_1972_conversion_method(self) -> None:
        result = convert_utc_to_tt(datetime(2017, 1, 1, 0, 0, 0, tzinfo=UTC))
        self.assertEqual(result.conversion_method, 'leap_seconds')
        self.assertAlmostEqual(result.tt_minus_utc_seconds, 69.184, places=3)

    def test_pre_1972_conversion_method(self) -> None:
        result = convert_utc_to_tt(datetime(1950, 1, 1, 0, 0, 0, tzinfo=UTC))
        self.assertEqual(result.conversion_method, 'delta_t')
        self.assertAlmostEqual(result.delta_t_seconds, 29.07, places=1)


if __name__ == '__main__':
    unittest.main()
