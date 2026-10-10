"""The first chart, for someone without an account: what a date settles alone, with
its place, and with its place and time; the checks on what it is sent; and the
hourly limit per client, directly and through a proxy the app trusts."""

import datetime
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, ClassVar

from fastapi.testclient import TestClient

from eight_characters.accounts.store import AccountStore
from eight_characters.accounts.web import (
    TOO_MANY_CHARTS,
    Accounts,
    get_accounts,
    load_config,
)
from eight_characters.canon import load_canon
from eight_characters.interactions import detect_interactions
from eight_characters.main import _load_ten_gods_lookup, app
from eight_characters.reading import build_reading
from tests.accounts_support import TEST_ORIGIN, Clock, account_environment

CHICAGO: dict[str, Any] = {
    'timezone': 'America/Chicago',
    'latitude': 41.8781,
    'longitude': -87.6298,
}
PROXY_SECRET = 'a proxy secret that is at least 32 bytes long'
PILLARS = ('year', 'month', 'day', 'hour')


def sentences(text: str) -> list[str]:
    # As static/readings.js splits a passage: at a stop, or after a quote closing it.
    return re.split(r'(?<=[.!?])\s+|(?<=[.!?]["”])\s+', text)


def app_lines(chart: dict[str, Any]) -> list[dict[str, Any]]:
    """The Day Master page's lines as the app reads them for this chart: build_reading,
    as POST /api/four_pillars gives it to an account, read as static/readings.js reads
    it. Each line's head is its passage's first sentence; the core's rest follows it."""
    names = [name for name in PILLARS if name in chart['pillars']]
    pillars = {
        name: (
            chart['pillars'][name]['stem']['chinese'],
            chart['pillars'][name]['branch']['chinese'],
        )
        for name in names
    }
    # build_reading needs all four pillars: without a time, the day stands in for the
    # hour, and nothing is read from it, since the lens and the stages are read for the
    # chart's own pillars only.
    full = pillars if 'hour' in pillars else {**pillars, 'hour': pillars['day']}
    reading = build_reading(
        load_canon(), full, _load_ten_gods_lookup(), detect_interactions(full)
    )
    core = [p['text'] for p in reading['day_master']['core']]
    lead, *rest = sentences(core[0])
    grounds = reading['day_master']['grounds'][0]['text']
    lines: list[dict[str, Any]] = [
        {
            'part': 'core',
            'first': lead,
            'rest': ([' '.join(rest)] if rest else []) + core[1:],
        },
        {'part': 'grounds', 'first': sentences(grounds)[0]},
    ]
    lines += [
        {
            'part': name,
            'first': sentences(reading['pillars'][name]['lens'][0]['text'])[0],
        }
        for name in ('hour', 'day', 'month', 'year')
        if name in names
    ]
    lines.append(
        {
            'part': 'cycle',
            'first': ' · '.join(
                reading['pillars'][name]['stage']['name'] for name in names
            ),
        }
    )
    return lines


def four(chart: dict[str, Any]) -> list[str]:
    return [
        pillar['stem']['chinese'] + pillar['branch']['chinese']
        for pillar in chart['pillars'].values()
    ]


def change(chart: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Each change as (pillar, when, before, after)."""
    return [
        (
            entry['pillar'],
            entry.get('at') or entry['at_utc'],
            entry['before']['stem']['chinese'] + entry['before']['branch']['chinese'],
            entry['after']['stem']['chinese'] + entry['after']['branch']['chinese'],
        )
        for entry in chart['changes']
    ]


class FirstChartTestCase(unittest.TestCase):
    """Account services of the test's own, and a client with no account."""

    settings: ClassVar[dict[str, str]] = {
        'EC_CHART_REQUESTS_PER_HOUR_PER_CLIENT': '1000'
    }

    def setUp(self) -> None:
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory)
        config = load_config(account_environment(directory, **self.settings))
        AccountStore.create(config.database)
        self.clock = Clock()
        self.accounts = Accounts.open(config, clock=self.clock)
        app.dependency_overrides[get_accounts] = lambda: self.accounts
        self.addCleanup(app.dependency_overrides.pop, get_accounts, None)
        self.client = TestClient(app, base_url=TEST_ORIGIN)

    def chart(self, status: int = 200, **body: Any) -> Any:
        response = self.client.post('/api/first_chart', json=body)
        self.assertEqual(response.status_code, status, response.text)
        return response.json()


class TestWhatABirthSettles(FirstChartTestCase):
    def test_with_its_place_and_time_four_pillars_without_an_account(self) -> None:
        chart = self.chart(date='1990-03-14', time='07:40', location=CHICAGO)
        self.assertNotIn('ec_session', self.client.cookies)
        self.assertEqual(four(chart), ['庚午', '己卯', '戊寅', '丙辰'])
        self.assertEqual(
            [pillar['branch']['sign'] for pillar in chart['pillars'].values()],
            ['Horse', 'Rabbit', 'Tiger', 'Dragon'],
        )
        self.assertEqual(
            [pillar['name'] for pillar in chart['pillars'].values()],
            ['Life field', 'Inner season', 'Inner light', 'Action gate'],
        )
        self.assertEqual(
            chart['pillars']['year']['branch'],
            {
                'chinese': '午',
                'pinyin': 'Wu',
                'sign': 'Horse',
                'element': 'fire',
                'polarity': 'Yang',
            },
        )
        self.assertEqual(chart['changes'], [])
        self.assertFalse(chart['flags']['solar_term_ambiguous'])
        self.assertEqual(chart['engine']['tzdb_version'], '2026.4')

    def test_the_day_master_is_the_day_stem_with_the_canon_passage_word_for_word(
        self,
    ) -> None:
        chart = self.chart(date='1990-03-14', time='07:40', location=CHICAGO)
        lens = load_canon()['day_masters']['戊']
        self.assertEqual(
            {
                key: value
                for key, value in chart['day_master'].items()
                if key != 'parts'
            },
            {
                'stem': '戊',
                'pinyin': 'Wu',
                'polarity': 'Yang',
                'element': 'earth',
                'title': lens['title'],
                'passage': lens['core'],
            },
        )
        self.assertTrue(chart['day_master']['passage'][0].startswith('The mountain'))

    def test_without_a_time_the_hour_is_left_out_and_the_day_changes_are_named(
        self,
    ) -> None:
        chart = self.chart(date='1990-03-14', location=CHICAGO)
        self.assertEqual(list(chart['pillars']), ['year', 'month', 'day'])
        self.assertEqual(four(chart), ['庚午', '己卯', '戊寅'])
        self.assertNotIn('flags', chart)
        # True solar midnight in Chicago that night is 26 seconds before the clock's.
        self.assertEqual(change(chart), [('day', '23:59:34-06:00', '戊寅', '己卯')])
        self.assertEqual(chart['day_master']['stem'], '戊')

    def test_the_day_follows_the_sun_where_she_was_born_not_the_clock(self) -> None:
        detroit = {
            'timezone': 'America/Detroit',
            'latitude': 42.3314,
            'longitude': -83.0458,
        }
        chart = self.chart(date='1990-07-01', location=detroit)
        # Under summer time, far west of its zone's meridian, the Sun's midnight
        # comes an hour and a half after the clock's: a birth before then has the
        # day before's pillar.
        self.assertEqual(four(chart), ['庚午', '壬午', '丁卯'])
        self.assertEqual(change(chart), [('day', '01:35:54-04:00', '丙寅', '丁卯')])

    def test_a_month_that_changes_on_the_day_is_named_at_its_clock_time(self) -> None:
        new_york = {
            'timezone': 'America/New_York',
            'latitude': 40.7128,
            'longitude': -74.006,
        }
        chart = self.chart(date='2026-11-07', location=new_york)
        # Lidong, the start of winter, is at 09:52:04 UTC: 04:52:04 in New York.
        self.assertEqual(four(chart), ['丙午', '己亥', '乙酉'])
        self.assertEqual(
            change(chart),
            [
                ('month', '04:52:04-05:00', '戊戌', '己亥'),
                ('day', '23:39:44-05:00', '乙酉', '丙戌'),
            ],
        )

    def test_a_change_in_an_hour_the_clocks_repeat_is_placed_on_its_pass(self) -> None:
        detroit = {
            'timezone': 'America/Detroit',
            'latitude': 42.3314,
            'longitude': -83.0458,
        }
        # On 1 November 2026 Detroit's clocks run 01:00 to 02:00 twice: the day changes
        # at 01:15:45 on the first pass, under summer time, so a birth at 01:10 on the
        # second (05:10 standard time, 06:10 UTC) has the new day's pillar.
        chart = self.chart(date='2026-11-01', location=detroit)
        self.assertEqual(change(chart), [('day', '01:15:45-04:00', '戊寅', '己卯')])
        late = self.chart(
            date='2026-11-01', time='01:10', location={**detroit, 'fold': 1}
        )
        self.assertEqual(four(late)[2], '己卯')

    def test_a_date_alone_gives_the_year_and_month_wherever_she_was_born(self) -> None:
        chart = self.chart(date='1990-03-14')
        self.assertEqual(list(chart['pillars']), ['year', 'month'])
        self.assertEqual(four(chart), ['庚午', '己卯'])
        self.assertEqual(chart['changes'], [])
        self.assertNotIn('day_master', chart)

    def test_a_date_on_which_the_year_changes_somewhere_leaves_it_out(self) -> None:
        # Lichun 2027 is at 01:46:18 UTC on 4 February: still 3 February in zones
        # at UTC-2 and further west, so a birth on either date may fall either side.
        for date in ('2027-02-03', '2027-02-04'):
            with self.subTest(date):
                chart = self.chart(date=date)
                self.assertEqual(chart['pillars'], {})
                self.assertEqual(
                    change(chart),
                    [
                        ('year', '2027-02-04T01:46:18Z', '丙午', '丁未'),
                        ('month', '2027-02-04T01:46:18Z', '辛丑', '壬寅'),
                    ],
                )
        self.assertEqual(four(self.chart(date='2027-02-05')), ['丁未', '壬寅'])

    def test_a_date_on_which_only_the_month_changes_keeps_the_year(self) -> None:
        chart = self.chart(date='2026-11-07')
        self.assertEqual(list(chart['pillars']), ['year'])
        self.assertEqual(
            change(chart), [('month', '2026-11-07T09:52:04Z', '戊戌', '己亥')]
        )

    def test_a_time_the_clocks_skip_or_repeat(self) -> None:
        skipped = self.client.post(
            '/api/first_chart',
            json={'date': '2026-03-08', 'time': '02:30', 'location': CHICAGO},
        )
        self.assertEqual(skipped.status_code, 400)
        self.assertEqual(
            skipped.json()['detail'],
            '02:30 did not happen on 2026-03-08 in America/Chicago: the clocks skipped it.',
        )
        repeated = {'date': '2026-11-01', 'time': '01:30', 'location': CHICAGO}
        ambiguous = self.client.post('/api/first_chart', json=repeated)
        self.assertEqual(ambiguous.status_code, 400)
        self.assertEqual(
            ambiguous.json()['detail'],
            '01:30 happened twice on 2026-11-01 in America/Chicago: give fold 0 for '
            'its first pass, or 1 for its second.',
        )
        for fold in (0, 1):
            with self.subTest(fold=fold):
                body = {**repeated, 'location': {**CHICAGO, 'fold': fold}}
                self.chart(**body)


class TestTheDayMastersReading(FirstChartTestCase):
    """Its parts, as the app's Day Master page reads them, each by the line it shows."""

    def test_its_parts_come_in_the_apps_order_each_by_the_line_the_app_shows(
        self,
    ) -> None:
        chart = self.chart(date='1990-03-14', time='07:40', location=CHICAGO)
        parts = chart['day_master']['parts']
        self.assertEqual(parts, app_lines(chart))
        self.assertEqual(
            [(part['part'], part['first']) for part in parts],
            [
                ('core', 'The mountain, the plateau, the great wall.'),
                ('grounds', 'The mountain.'),
                ('hour', 'The mountain in winter.'),
                ('day', "The mountain's core."),
                ('month', "The mountain in the world's view."),
                ('year', "The mountain's bedrock."),
                ('cycle', "Emperor's Peak · Bathing · Birth · Capping"),
            ],
        )
        # The core reads in full: its line and its rest are the passage, word for word.
        core = parts[0]
        self.assertEqual(
            ' '.join([core['first'], *core['rest']]),
            ' '.join(chart['day_master']['passage']),
        )
        self.assertEqual([part for part in parts if 'rest' in part], [core])

    def test_without_a_time_the_hour_has_no_part_and_the_cycle_three_stages(
        self,
    ) -> None:
        chart = self.chart(date='1990-03-14', location=CHICAGO)
        parts = chart['day_master']['parts']
        self.assertEqual(parts, app_lines(chart))
        self.assertEqual(
            [part['part'] for part in parts],
            ['core', 'grounds', 'day', 'month', 'year', 'cycle'],
        )
        self.assertEqual(parts[-1]['first'], "Emperor's Peak · Bathing · Birth")

    def test_every_day_master_reads_as_the_app_reads_it(self) -> None:
        # Ten days in a row hold all ten day stems.
        first = datetime.date(1990, 3, 14)
        stems: set[str] = set()
        for offset in range(10):
            day = (first + datetime.timedelta(days=offset)).isoformat()
            chart = self.chart(date=day, time='07:40', location=CHICAGO)
            stems.add(chart['day_master']['stem'])
            self.assertEqual(chart['day_master']['parts'], app_lines(chart), day)
        self.assertEqual(len(stems), 10)

    def test_a_date_alone_has_no_day_master(self) -> None:
        self.assertNotIn('day_master', self.chart(date='1990-03-14'))


class TestWhatItIsSent(FirstChartTestCase):
    def refused(self, body: Any, detail: str | None = None) -> None:
        response = self.client.post('/api/first_chart', json=body)
        self.assertEqual(response.status_code, 400, response.text)
        if detail is not None:
            self.assertIn(detail, response.json()['detail'])

    def test_a_birth_that_cannot_be_charted_is_refused_saying_why(self) -> None:
        for body, detail in (
            ({'date': '1990-02-30'}, '1990-02-30 is not a date that exists.'),
            ({'date': '1990-3-14'}, 'date must be in YYYY-MM-DD format.'),
            ({'date': '1948-06-01'}, 'Date out of supported range (1949-2100).'),
            ({'date': '2101-06-01'}, 'Date out of supported range (1949-2100).'),
            (
                {'date': '1990-03-14', 'time': '7:5', 'location': CHICAGO},
                'time must be in HH:MM or HH:MM:SS format.',
            ),
            (
                {'date': '1990-03-14', 'time': '24:10', 'location': CHICAGO},
                'time must be in HH:MM or HH:MM:SS format.',
            ),
            (
                {'date': '1990-03-14', 'time': '07:40'},
                'A birth time needs the birth place.',
            ),
            (
                {
                    'date': '1990-03-14',
                    'location': {**CHICAGO, 'timezone': 'Mars/Olympus'},
                },
                'Unrecognized timezone identifier.',
            ),
        ):
            with self.subTest(body=body):
                self.refused(body, detail)

    def test_only_ascii_digits_are_taken(self) -> None:
        # A pattern's \d takes any script's digits; only ASCII ones are taken.
        for body, detail in (
            (
                {'date': '1990-03-14', 'time': '0\u0667:40', 'location': CHICAGO},
                'time must be in HH:MM or HH:MM:SS format.',
            ),
            ({'date': '199\u0660-03-14'}, 'date must be in YYYY-MM-DD format.'),
        ):
            with self.subTest(body=body):
                self.refused(body, detail)

    def test_a_request_that_is_not_one_is_refused(self) -> None:
        for body in (
            {},
            {'date': '1990-03-14', 'include_reading': True},
            {'date': '1990-03-14', 'location': {**CHICAGO, 'city': 'Chicago'}},
            {'date': '1990-03-14', 'location': {**CHICAGO, 'latitude': 95.0}},
            {'date': '1990-03-14', 'location': {**CHICAGO, 'longitude': -181.0}},
            {'date': '1990-03-14', 'location': {**CHICAGO, 'latitude': '41.8781'}},
            {'date': '1990-03-14', 'location': {**CHICAGO, 'fold': 2}},
            {'date': '1990-03-14', 'location': {**CHICAGO, 'fold': True}},
            {'date': 19900314},
        ):
            with self.subTest(body=body):
                self.refused(body)

    def test_a_coordinate_that_is_not_a_number_is_refused(self) -> None:
        for value in ('NaN', 'Infinity', '-Infinity'):
            with self.subTest(value=value):
                response = self.client.post(
                    '/api/first_chart',
                    content=(
                        '{"date": "1990-03-14", "location": {"timezone": '
                        f'"America/Chicago", "latitude": {value}, "longitude": -87.6}}}}'
                    ),
                    headers={'Content-Type': 'application/json'},
                )
                self.assertEqual(response.status_code, 400)


class TestTheHourlyLimit(FirstChartTestCase):
    settings: ClassVar[dict[str, str]] = {'EC_CHART_REQUESTS_PER_HOUR_PER_CLIENT': '2'}

    def test_a_client_may_ask_for_its_limit_an_hour(self) -> None:
        self.chart(date='1990-03-14')
        self.chart(date='1990-03-15')
        refused = self.client.post('/api/first_chart', json={'date': '1990-03-16'})
        self.assertEqual(refused.status_code, 429)
        self.assertEqual(refused.json(), {'detail': TOO_MANY_CHARTS})
        self.assertEqual(refused.headers['Retry-After'], '3600')
        self.clock.advance(3601)
        self.chart(date='1990-03-16')

    def test_a_request_refused_for_what_it_holds_is_not_counted(self) -> None:
        for _ in range(3):
            self.chart(400, date='1990-02-30')
        self.chart(date='1990-03-14')
        self.chart(date='1990-03-15')


class TestThroughATrustedProxy(FirstChartTestCase):
    settings: ClassVar[dict[str, str]] = {
        'EC_CHART_REQUESTS_PER_HOUR_PER_CLIENT': '1',
        'EC_PROXY_SECRET': PROXY_SECRET,
    }

    def through(self, visitor: str, secret: str = PROXY_SECRET) -> Any:
        return self.client.post(
            '/api/first_chart',
            json={'date': '1990-03-14'},
            headers={'X-EC-Proxy-Secret': secret, 'X-EC-Client': visitor},
        )

    def test_each_visitor_the_proxy_names_has_a_limit_of_their_own(self) -> None:
        self.assertEqual(self.through('198.51.100.7').status_code, 200)
        self.assertEqual(self.through('203.0.113.9').status_code, 200)
        self.assertEqual(self.through('198.51.100.7').status_code, 429)

    def test_a_proxy_without_the_secret_is_refused(self) -> None:
        self.assertEqual(self.through('198.51.100.7', 'guessed').status_code, 403)
        alone = self.client.post(
            '/api/first_chart',
            json={'date': '1990-03-14'},
            headers={'X-EC-Client': '198.51.100.7'},
        )
        self.assertEqual(alone.status_code, 403)


if __name__ == '__main__':
    unittest.main()
