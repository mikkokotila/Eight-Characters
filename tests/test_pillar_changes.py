import json
import random
import unittest
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from eight_characters.conventions import (
    DAY_BOUNDARY_BASIS_CIVIL,
    DAY_BOUNDARY_BASIS_TRUE_SOLAR,
    HOUR_BASIS_CIVIL,
    ZI_CONVENTION_WHOLE_ZI_23,
    ConventionSettings,
    all_supported_convention_combinations,
)
from eight_characters.engine import compute_engine_payload
from eight_characters.time_convert import BirthInput, load_timezone

PILLARS = ('year', 'month', 'day', 'hour')
HKT = timezone(timedelta(hours=8))
HKO_PATH = Path('tests/fixtures/hko_solar_terms_2019_2028.json')


def _text(pillar: dict[str, Any]) -> str:
    return pillar['stem']['chinese'] + pillar['branch']['chinese']


def _local_input(
    instant: datetime,
    timezone_name: str | None,
    longitude: float,
    latitude: float,
    conventions: ConventionSettings,
) -> BirthInput:
    """The public engine input for a real instant, read on the zone's wall clock."""
    if timezone_name is None:
        return BirthInput(
            utc_timestamp=instant.astimezone(UTC).isoformat(),
            longitude=longitude,
            latitude=latitude,
            conventions=conventions,
        )
    wall = instant.astimezone(load_timezone(timezone_name))
    return BirthInput(
        year=wall.year,
        month=wall.month,
        day=wall.day,
        hour=wall.hour,
        minute=wall.minute,
        second=wall.second,
        timezone_name=timezone_name,
        fold=wall.fold,
        longitude=longitude,
        latitude=latitude,
        conventions=conventions,
    )


def _pillars_at(
    instant: datetime,
    timezone_name: str | None,
    longitude: float,
    latitude: float,
    conventions: ConventionSettings,
) -> dict[str, str]:
    payload = compute_engine_payload(
        _local_input(instant, timezone_name, longitude, latitude, conventions)
    )
    return {name: _text(payload['pillars'][name]) for name in PILLARS}


class TestCanonicalChart(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = compute_engine_payload(
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
            )
        )

    def changes(self, name: str) -> dict[str, Any]:
        return self.payload['pillars'][name]['changes']

    def test_year_changes_at_lichun_on_either_side(self) -> None:
        year = self.changes('year')
        self.assertEqual(year['previous']['term'], 'lichun_315')
        self.assertEqual(year['next']['term'], 'lichun_315')
        # The birth is 6 h 12 min before 1988's Lichun: the year boundary already says so.
        self.assertAlmostEqual(
            year['next']['seconds'],
            -self.payload['pillars']['year']['boundary']['distance_seconds'],
            places=6,
        )
        self.assertEqual(_text(year['previous']['pillar']), '丙寅')
        self.assertEqual(_text(year['next']['pillar']), '戊辰')

    def test_month_changes_at_the_surrounding_jie(self) -> None:
        month = self.changes('month')
        self.assertEqual(month['previous']['term'], 'xiaohan_285')
        self.assertEqual(month['next']['term'], 'lichun_315')
        self.assertAlmostEqual(
            month['next']['seconds'],
            self.payload['pillars']['month']['boundary']['distance_seconds'],
            places=6,
        )
        # Before Xiaohan: the Zi month of the Ding year; after Lichun: the Yin month of Wu.
        self.assertEqual(_text(month['previous']['pillar']), '壬子')
        self.assertEqual(_text(month['next']['pillar']), '甲寅')

    def test_day_changes_at_true_solar_midnight(self) -> None:
        day = self.changes('day')
        self.assertEqual(day['previous']['clock'], 'true_solar')
        self.assertEqual(day['previous']['clock_time'], '1988-02-04T00:00:00')
        self.assertEqual(day['next']['clock_time'], '1988-02-05T00:00:00')
        # True solar time is 15:12:24; the equation of time drifts a few seconds a day.
        self.assertAlmostEqual(
            day['previous']['seconds'], 15 * 3600 + 12 * 60 + 24, delta=10
        )
        self.assertEqual(_text(day['previous']['pillar']), '戊子')
        self.assertEqual(_text(day['next']['pillar']), '庚寅')

    def test_hour_changes_at_odd_true_solar_hours(self) -> None:
        hour = self.changes('hour')
        self.assertEqual(hour['previous']['clock_time'], '1988-02-04T15:00:00')
        self.assertEqual(hour['next']['clock_time'], '1988-02-04T17:00:00')
        self.assertAlmostEqual(hour['previous']['seconds'], 12 * 60 + 24, delta=1)
        self.assertAlmostEqual(hour['next']['seconds'], 60 * 60 + 47 * 60 + 36, delta=1)
        self.assertEqual(_text(hour['previous']['pillar']), '辛未')
        self.assertEqual(_text(hour['next']['pillar']), '癸酉')


class TestHourChangesAreDoubleHours(unittest.TestCase):
    def test_even_hours_are_not_hour_pillar_changes(self) -> None:
        # True solar time 16:09: the flag measures the 9 minutes to 16:00, a whole hour
        # inside the Shen double hour; the hour pillar changes at 15:00 and 17:00.
        payload = compute_engine_payload(
            BirthInput(
                year=1988,
                month=6,
                day=15,
                hour=17,
                minute=30,
                second=0,
                timezone_name='Europe/Helsinki',
                longitude=24.94,
                latitude=60.17,
            )
        )
        self.assertTrue(
            payload['intermediate']['true_solar_time'].endswith('T16:09:15')
        )
        self.assertAlmostEqual(
            payload['flags']['hour_boundary_proximity_seconds'], 555, delta=1
        )
        hour = payload['pillars']['hour']['changes']
        self.assertEqual(hour['previous']['clock_time'], '1988-06-15T15:00:00')
        self.assertEqual(hour['next']['clock_time'], '1988-06-15T17:00:00')
        self.assertAlmostEqual(hour['previous']['seconds'], 69 * 60 + 15, delta=2)
        self.assertAlmostEqual(hour['next']['seconds'], 50 * 60 + 45, delta=2)


class TestZiHourChanges(unittest.TestCase):
    def payload(self, zi_convention: str) -> dict[str, Any]:
        # Helsinki at 00:50 in summer is true solar 23:29 the evening before.
        return compute_engine_payload(
            BirthInput(
                year=1988,
                month=6,
                day=15,
                hour=0,
                minute=50,
                second=0,
                timezone_name='Europe/Helsinki',
                longitude=24.94,
                latitude=60.17,
                conventions=ConventionSettings(zi_convention=zi_convention),
            )
        )

    def test_split_midnight_changes_day_and_hour_stem_at_midnight(self) -> None:
        pillars = self.payload('split_midnight')['pillars']
        self.assertEqual(_text(pillars['day']), '庚子')
        self.assertEqual(
            pillars['day']['changes']['next']['clock_time'], '1988-06-15T00:00:00'
        )
        self.assertEqual(_text(pillars['day']['changes']['next']['pillar']), '辛丑')
        # The Zi hour continues past midnight, but its stem follows the new day.
        self.assertEqual(_text(pillars['hour']), '丙子')
        self.assertEqual(
            pillars['hour']['changes']['next']['clock_time'], '1988-06-15T00:00:00'
        )
        self.assertEqual(_text(pillars['hour']['changes']['next']['pillar']), '戊子')
        self.assertEqual(
            pillars['hour']['changes']['previous']['clock_time'], '1988-06-14T23:00:00'
        )

    def test_whole_zi_changes_the_day_at_23(self) -> None:
        pillars = self.payload(ZI_CONVENTION_WHOLE_ZI_23)['pillars']
        self.assertEqual(_text(pillars['day']), '辛丑')
        self.assertEqual(
            pillars['day']['changes']['previous']['clock_time'], '1988-06-14T23:00:00'
        )
        self.assertEqual(
            pillars['day']['changes']['next']['clock_time'], '1988-06-15T23:00:00'
        )
        self.assertEqual(
            pillars['hour']['changes']['previous']['clock_time'], '1988-06-14T23:00:00'
        )
        self.assertEqual(
            pillars['hour']['changes']['next']['clock_time'], '1988-06-15T01:00:00'
        )


class TestMixedClocks(unittest.TestCase):
    def test_hour_pillar_changes_when_the_day_changes_on_the_other_clock(self) -> None:
        # Shanghai in November: true solar time runs about 22 minutes ahead of the
        # civil clock, so the true solar day begins at civil 23:38, inside the civil Zi
        # hour, and changes the hour stem before the next civil double hour at 01:00.
        payload = compute_engine_payload(
            BirthInput(
                year=2020,
                month=11,
                day=3,
                hour=23,
                minute=30,
                second=0,
                timezone_name='Asia/Shanghai',
                longitude=121.47,
                latitude=31.23,
                conventions=ConventionSettings(
                    hour_basis=HOUR_BASIS_CIVIL,
                    day_boundary_basis=DAY_BOUNDARY_BASIS_TRUE_SOLAR,
                ),
            )
        )
        hour_next = payload['pillars']['hour']['changes']['next']
        self.assertEqual(hour_next['clock'], 'true_solar')
        self.assertEqual(hour_next['clock_time'], '2020-11-04T00:00:00')
        self.assertLess(hour_next['seconds'], 30 * 60)
        self.assertEqual(hour_next['pillar']['branch']['chinese'], '子')


class TestDaylightSaving(unittest.TestCase):
    def test_spring_forward_starts_the_hour_at_the_jump(self) -> None:
        # New York, 2021-03-14: civil 02:00 EST becomes 03:00 EDT, starting Yin (03-05).
        payload = compute_engine_payload(
            BirthInput(
                year=2021,
                month=3,
                day=14,
                hour=1,
                minute=30,
                second=0,
                timezone_name='America/New_York',
                longitude=-74.0,
                latitude=40.71,
                conventions=ConventionSettings(
                    hour_basis=HOUR_BASIS_CIVIL,
                    day_boundary_basis=DAY_BOUNDARY_BASIS_CIVIL,
                ),
            )
        )
        hour_next = payload['pillars']['hour']['changes']['next']
        self.assertEqual(hour_next['clock'], 'civil')
        self.assertEqual(hour_next['clock_time'], '2021-03-14T03:00:00')
        self.assertAlmostEqual(hour_next['seconds'], 30 * 60, delta=1)
        self.assertEqual(hour_next['pillar']['branch']['chinese'], '寅')

    def test_fall_back_hour_changes_once_at_the_first_three_oclock(self) -> None:
        # Helsinki, 2021-10-31: 04:00 EEST becomes 03:00 EET, so 03:00-04:00 happens
        # twice. Yin (03-05) starts at the first 03:00 and is not restarted.
        payload = compute_engine_payload(
            BirthInput(
                year=2021,
                month=10,
                day=31,
                hour=2,
                minute=30,
                second=0,
                timezone_name='Europe/Helsinki',
                longitude=24.94,
                latitude=60.17,
                conventions=ConventionSettings(
                    hour_basis=HOUR_BASIS_CIVIL,
                    day_boundary_basis=DAY_BOUNDARY_BASIS_CIVIL,
                ),
            )
        )
        hour = payload['pillars']['hour']['changes']
        self.assertEqual(hour['next']['clock_time'], '2021-10-31T03:00:00')
        self.assertAlmostEqual(hour['next']['seconds'], 30 * 60, delta=1)
        self.assertEqual(hour['next']['pillar']['branch']['chinese'], '寅')


class TestChangesFollowTheEngine(unittest.TestCase):
    """Every reported change is where the public engine really changes, and the first."""

    def test_random_births_under_every_convention(self) -> None:
        rng = random.Random(1716)
        places = [
            ('Asia/Shanghai', 104.066, 30.658),
            ('Europe/Helsinki', 24.94, 60.17),
            ('America/New_York', -74.0, 40.71),
            ('Australia/Sydney', 151.21, -33.87),
            ('America/Sao_Paulo', -46.63, -23.55),
            (None, 10.0, 50.0),
        ]
        conventions = all_supported_convention_combinations()
        for case in range(48):
            timezone_name, longitude, latitude = places[case % len(places)]
            convention = conventions[case % len(conventions)]
            birth = datetime(1955, 1, 1, tzinfo=UTC) + timedelta(
                seconds=rng.randrange(0, 70 * 365 * 86400)
            )
            with self.subTest(case=case, birth=birth.isoformat(), zone=timezone_name):
                self.assert_changes_follow_engine(
                    birth, timezone_name, longitude, latitude, convention
                )

    def assert_changes_follow_engine(
        self,
        birth: datetime,
        timezone_name: str | None,
        longitude: float,
        latitude: float,
        conventions: ConventionSettings,
    ) -> None:
        birth_input = _local_input(
            birth, timezone_name, longitude, latitude, conventions
        )
        payload = compute_engine_payload(birth_input)
        # The instant the engine actually computed for (wall clocks keep whole seconds).
        exact_birth = birth.replace(microsecond=0)

        def at(instant: datetime) -> dict[str, str]:
            return _pillars_at(instant, timezone_name, longitude, latitude, conventions)

        margin = 3.0
        for name in PILLARS:
            natal = _text(payload['pillars'][name])
            changes = payload['pillars'][name]['changes']
            for side, sign in (('previous', -1), ('next', 1)):
                change = changes[side]
                seconds = change['seconds']
                self.assertGreaterEqual(seconds, 0.0)
                instant = exact_birth + timedelta(seconds=sign * seconds)
                far = _text(change['pillar'])
                self.assertNotEqual(far, natal, f'{name} {side}')
                if seconds > margin + 1:
                    self.assertEqual(
                        at(instant - sign * timedelta(seconds=margin))[name],
                        natal,
                        f'{name} {side} near side',
                    )
                self.assertEqual(
                    at(instant + sign * timedelta(seconds=margin))[name],
                    far,
                    f'{name} {side} far side',
                )
                # No change hides between the birth and the reported one. Solar terms
                # only advance, so a year or month pillar cannot change and change back;
                # a civil clock can repeat itself across a daylight-saving fold.
                if name in ('day', 'hour') and seconds > 60:
                    for step in range(1, 8):
                        probe = exact_birth + timedelta(
                            seconds=sign * seconds * step / 8
                        )
                        self.assertEqual(
                            at(probe)[name], natal, f'{name} {side} at {step}/8'
                        )


class TestTermsMatchHongKongObservatory(unittest.TestCase):
    def test_month_changes_fall_on_the_published_jie(self) -> None:
        fixture = json.loads(HKO_PATH.read_text(encoding='utf-8'))
        published: dict[float, list[datetime]] = {}
        for record in fixture['records']:
            hour, minute = map(int, record['time_hm'].split(':'))
            instant = datetime(
                record['year'], record['month'], record['day'], hour, minute, tzinfo=HKT
            ).astimezone(UTC)
            published.setdefault(float(record['target_longitude_deg']), []).append(
                instant
            )
        labels = {
            'lichun_315': 315.0,
            'jingzhe_345': 345.0,
            'qingming_15': 15.0,
            'lixia_45': 45.0,
            'mangzhong_75': 75.0,
            'xiaoshu_105': 105.0,
            'liqiu_135': 135.0,
            'bailu_165': 165.0,
            'hanlu_195': 195.0,
            'lidong_225': 225.0,
            'daxue_255': 255.0,
            'xiaohan_285': 285.0,
        }
        rng = random.Random(23)
        errors: list[float] = []
        for _ in range(60):
            birth = datetime(2019, 3, 1, tzinfo=UTC) + timedelta(
                seconds=rng.randrange(0, 9 * 365 * 86400)
            )
            payload = compute_engine_payload(
                _local_input(
                    birth, 'Asia/Hong_Kong', 114.17, 22.32, ConventionSettings()
                )
            )
            for side, sign in (('previous', -1), ('next', 1)):
                change = payload['pillars']['month']['changes'][side]
                # No leap second was inserted in 2019-2028, so TT and UTC keep pace.
                instant = birth.replace(microsecond=0) + timedelta(
                    seconds=sign * change['seconds']
                )
                nearest = min(
                    published[labels[change['term']]],
                    key=lambda published_instant: abs(published_instant - instant),
                )
                errors.append(abs((nearest - instant).total_seconds()))
        # The Observatory publishes to the nearest minute, up to 30 s from the instant,
        # and the engine's instants lie within about a second of its own.
        self.assertLessEqual(max(errors), 30.0 + 1.5)


if __name__ == '__main__':
    unittest.main()
