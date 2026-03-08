import unittest
from pathlib import Path

from eight_characters.conventions import ConventionSettings
from eight_characters.engine import compute_engine_json
from eight_characters.time_convert import BirthInput
from eight_characters.verification import fixture_roundtrip_matches


class TestVerificationHarness(unittest.TestCase):
    def test_regression_fixture_roundtrip(self) -> None:
        payload_json = compute_engine_json(
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
        fixture_path = Path('tests') / 'fixtures' / 'phase5-regression-1988-02-04.json'
        self.assertTrue(
            fixture_roundtrip_matches(
                str(fixture_path),
                payload_json,
                update_fixture=False,
            )
        )

    def test_regression_fixture_roundtrip_does_not_write_by_default(self) -> None:
        fixture_path = Path('tests') / 'fixtures' / 'phase5-regression-1988-02-04.json'
        before = fixture_path.read_text(encoding='utf-8')
        self.assertTrue(fixture_roundtrip_matches(str(fixture_path), before))
        after = fixture_path.read_text(encoding='utf-8')
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
