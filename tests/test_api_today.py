"""POST /api/today, POST /api/today/days and GET /api/schools (docs/Today.md)."""

import re
import unittest
from datetime import date, datetime, timedelta
from itertools import pairwise
from typing import Any, ClassVar

from fastapi.testclient import TestClient

from eight_characters.accounts.web import Accounts, account_key
from eight_characters.data import build_branch_data, build_stem_data
from eight_characters.engine import pillars_at
from eight_characters.sexagenary import BRANCHES as BRANCH_CHARS
from eight_characters.time_convert import BirthInput
from tests.accounts_support import install_accounts, sign_in, site_client

HELSINKI = {
    'name': 'Helsinki, Uusimaa, Finland',
    'city': 'Helsinki',
    'timezone': 'Europe/Helsinki',
    'latitude': 60.16952,
    'longitude': 24.93545,
}
LISBON = {
    'name': 'Lisbon, Lisbon, Portugal',
    'city': 'Lisbon',
    'timezone': 'Europe/Lisbon',
    'latitude': 38.71667,
    'longitude': -9.13333,
}
# Made-up births, of nobody: the chart the page is on, and a partner's.
CHART = {'date': '1990-05-17', 'time': '08:30', 'place': HELSINKI, 'gender': 'female'}
PARTNER = {
    'name': 'Partner',
    'date': '1988-11-02',
    'time': '21:05:30',
    'place': LISBON,
    'gender': 'male',
}
DAY = '2026-10-11'
# What the page sends for the chart it is on, with what the account keeps for Today.
BODY: dict[str, Any] = {
    'date': DAY,
    'lang': 'en',
    'place': HELSINKI,
    'charts': {'self': CHART, 'partner': PARTNER},
}


def _keys(value: Any) -> set[str]:
    """Every key anywhere in a JSON value."""
    if isinstance(value, dict):
        found: set[str] = set()
        for key, item in value.items():
            found.add(str(key))
            found |= _keys(item)
        return found
    if isinstance(value, list):
        found = set()
        for item in value:
            found |= _keys(item)
        return found
    return set()


def _relationships(answer: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for layer in answer['layers'].values():
        if layer is not None:
            found.extend(layer['relationships'])
    return found


class TestToday(unittest.TestCase):
    accounts: ClassVar[Accounts]
    client: ClassVar[TestClient]
    key: ClassVar[str]
    english: ClassVar[dict[str, Any]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.accounts = install_accounts(cls)
        cls.client = site_client()
        sign_in(cls.client, cls.accounts, 'today@example.com')
        user = cls.accounts.store.user_by_email('today@example.com')
        assert user is not None
        cls.key = account_key(user)
        reply = cls.client.post('/api/today', json=BODY)
        if reply.status_code != 200:
            raise AssertionError(reply.text)
        cls.english = reply.json()
        cls.english_headers = reply.headers

    def test_the_schools_need_no_account(self) -> None:
        reply = site_client().get('/api/schools')
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(
            [setting['id'] for setting in reply.json()['settings']],
            ['favourable', 'season', 'transits'],
        )

    def test_today_needs_the_chart_and_a_place(self) -> None:
        for refused in (
            {key: value for key, value in BODY.items() if key != 'charts'},
            {key: value for key, value in BODY.items() if key != 'place'},
            {**BODY, 'charts': {'partner': PARTNER}},
            {**BODY, 'charts': {'self': CHART}, 'chart': 'partner'},
        ):
            with self.subTest(refused=refused):
                reply = self.client.post('/api/today', json=refused)
                self.assertEqual(reply.status_code, 400, reply.text)

    def test_what_the_account_keeps_is_what_the_page_sends(self) -> None:
        # The page sends the chart it is on and, when that chart is in a couple, the
        # other chart of the couple, with the place and the schools the account keeps.
        read = self.client.get('/api/account/settings').json()['updated_at']
        saved: list[str] = []
        for birth in (CHART, PARTNER):
            kept = self.client.post(
                '/api/account/charts',
                json={**birth, 'key': self.key, 'updated_at': read},
            )
            self.assertEqual(kept.status_code, 201, kept.text)
            saved.append(kept.json()['saved'])
            read = kept.json()['updated_at']
        for method, path, body in (
            ('POST', '/api/account/couples', {'charts': saved}),
            ('PUT', '/api/account/place', {'place': LISBON}),
            ('PATCH', '/api/account/schools', {'transits': 'whole'}),
        ):
            kept = self.client.request(
                method, path, json={**body, 'key': self.key, 'updated_at': read}
            )
            self.assertIn(kept.status_code, (200, 201), kept.text)
            read = kept.json()['updated_at']
        settings = kept.json()
        (couple,) = settings['couples']
        births = {
            chart['id']: {
                key: value
                for key, value in chart.items()
                if key not in ('id', 'pillars', 'problem')
            }
            for chart in settings['charts']
        }
        on_screen, other = couple['charts']
        for chart, partner in ((on_screen, other), (other, on_screen)):
            with self.subTest(chart=chart):
                reply = self.client.post(
                    '/api/today',
                    json={
                        'date': DAY,
                        'lang': 'en',
                        'place': settings['place'],
                        'charts': {'self': births[chart], 'partner': births[partner]},
                        'schools': settings['chosen'],
                    },
                )
                self.assertEqual(reply.status_code, 200, reply.text)
                answer = reply.json()
                self.assertEqual(answer['place']['name'], LISBON['name'])
                self.assertEqual(answer['schools'], settings['schools'])
                self.assertIsNotNone(answer['marriage'])

    def test_a_date_is_refused_unless_the_run_fits_the_engines_years(self) -> None:
        for text in (
            '2026-1-1',
            '2026-02-30',
            '\u0662\u0660\u0662\u0666-\u0661\u0660-\u0661\u0661',
            '0001-01-01',
            '9999-12-31',
            '1949-01-07',
            '2100-12-18',
        ):
            with self.subTest(date=text):
                reply = self.client.post('/api/today', json={**BODY, 'date': text})
                self.assertEqual(reply.status_code, 400, reply.text)
        reply = self.client.post('/api/today', json={**BODY, 'lang': 'sv'})
        self.assertEqual(reply.status_code, 400)

    def test_every_combination_of_schools(self) -> None:
        # 2 x 4 x 3 = 24: each answers, with each element weighed once, and a luck
        # pillar in its branch phase acts by phase only through its branch.
        for favourable in ('support', 'climate'):
            for season in ('eighteen', 'months', 'late_summer', 'commander'):
                for transits in ('phases', 'whole', 'seasoned'):
                    with self.subTest(f'{favourable}/{season}/{transits}'):
                        reply = self.client.post(
                            '/api/today',
                            json={
                                'date': DAY,
                                'lang': 'en',
                                'place': HELSINKI,
                                'charts': {'self': CHART, 'partner': PARTNER},
                                'schools': {
                                    'favourable': favourable,
                                    'season': season,
                                    'transits': transits,
                                },
                            },
                        )
                        self.assertEqual(reply.status_code, 200, reply.text)
                        answer = reply.json()
                        self.assertEqual(
                            sorted(answer['favourable']['weights'].values()),
                            [-1.2, -1.0, 0.0, 1.0, 1.2],
                        )
                        luck = answer['layers']['luck']
                        if luck is not None and luck['luck']['phase'] == 'branch':
                            acting = transits != 'phases'
                            stems = [
                                r
                                for r in luck['relationships']
                                if r['component'] == 'stem'
                            ]
                            if not acting:
                                self.assertEqual(stems, [])
                            roles = [part['role'] for part in luck['pull']['parts']]
                            self.assertEqual('stem' in roles, acting)

    def test_a_day_the_clocks_skipped(self) -> None:
        # Samoa moved across the date line and skipped 30 December 2011 entirely.
        apia = {
            'name': 'Apia, Tuamasaga, Samoa',
            'city': 'Apia',
            'timezone': 'Pacific/Apia',
            'latitude': -13.83333,
            'longitude': -171.76666,
        }
        body = {'lang': 'fi', 'place': apia, 'charts': {'self': CHART}}
        skipped = self.client.post('/api/today', json={**body, 'date': '2011-12-30'})
        self.assertEqual(skipped.status_code, 400)
        after = self.client.post('/api/today', json={**body, 'date': '2011-12-31'})
        self.assertEqual(after.status_code, 200, after.text)
        dates = [day['date'] for day in after.json()['run']]
        self.assertNotIn('2011-12-30', dates)
        self.assertEqual(len(dates), 21)
        self.assertIn('2011-12-29', dates)
        # Apia's clock runs a day ahead of its sun: the hours are those of the solar
        # date the day pillar is, and noon on the clock falls within them.
        hours = after.json()['hours']
        noon = datetime.fromisoformat('2011-12-31T12:00:00+14:00')
        self.assertLessEqual(
            datetime.fromisoformat(hours[0]['spans'][0]['start']), noon
        )
        self.assertLess(noon, datetime.fromisoformat(hours[0]['spans'][1]['end']))

    def test_the_answer_is_the_accounts_own(self) -> None:
        self.assertEqual(self.english_headers['cache-control'], 'private, no-cache')
        self.assertEqual(self.english['policy'], 'today_v1')
        self.assertEqual(
            self.english['schools'],
            {'favourable': 'support', 'season': 'eighteen', 'transits': 'phases'},
        )

    def test_the_days_pillars_are_the_first_charts_at_noon(self) -> None:
        first = self.client.post(
            '/api/first_chart',
            json={
                'date': DAY,
                'location': {
                    k: v for k, v in HELSINKI.items() if k not in ('name', 'city')
                },
            },
        ).json()
        for layer in ('day', 'month', 'year'):
            with self.subTest(layer=layer):
                shown = self.english['layers'][layer]['pillar']
                for part in ('stem', 'branch'):
                    # The first chart's view, and the lines of Today's card.
                    self.assertEqual(
                        {k: v for k, v in shown[part].items() if k != 'lines'},
                        first['pillars'][layer][part],
                    )
        self.assertEqual(self.english['changes'], first['changes'])

    def test_the_chart_reads_its_own_four_pillars(self) -> None:
        # The chart read, as /api/four_pillars charts its birth: the partner's with
        # chart: partner.
        as_partner = self.client.post(
            '/api/today', json={**BODY, 'chart': 'partner'}
        ).json()
        for answer, birth in ((self.english, CHART), (as_partner, PARTNER)):
            place = birth['place']
            four = self.client.post(
                '/api/four_pillars',
                json={
                    'date': birth['date'],
                    'time': birth['time'],
                    'location': {
                        'timezone': place['timezone'],
                        'latitude': place['latitude'],
                        'longitude': place['longitude'],
                    },
                },
            ).json()['four_pillars']
            natal = answer['natal']
            with self.subTest(chart=answer['chart']):
                self.assertEqual(list(natal), ['year', 'month', 'day', 'hour'])
                for name, pillar in natal.items():
                    charted = four[name]
                    self.assertEqual(
                        (pillar['stem']['chinese'], pillar['branch']['chinese']),
                        (charted['stem']['chinese'], charted['branch']['chinese']),
                    )

    def test_every_pillar_has_its_cards_lines(self) -> None:
        # The lines Standard mode's card draws: the stem's trigram and the branch's
        # hexagram, top first.
        answer = self.english
        pillars = [layer['pillar'] for layer in answer['layers'].values() if layer]
        pillars += [day['pillar'] for day in answer['run']]
        pillars += list(answer['natal'].values())
        luck = answer['marriage']['partner']['luck']
        if luck is not None:
            pillars.append(luck['pillar'])
        for pillar in pillars:
            stem, branch = pillar['stem'], pillar['branch']
            with self.subTest(pillar=stem['chinese'] + branch['chinese']):
                trigram = build_stem_data(stem['chinese'])['lines']
                hexagram = build_branch_data(branch['chinese'])['lines']
                self.assertEqual(stem['lines'], trigram)
                self.assertEqual(branch['lines'], hexagram)
        # 甲 Jia is ☳ Zhen, a whole line under two broken ones.
        self.assertEqual(build_stem_data('甲')['lines'], ['B', 'B', 'L'])

    def test_the_run_is_seven_days_back_and_fourteen_ahead(self) -> None:
        run = self.english['run']
        self.assertEqual([day['offset'] for day in run], list(range(-7, 15)))
        start = date.fromisoformat(DAY) - timedelta(days=7)
        self.assertEqual(
            [day['date'] for day in run],
            [(start + timedelta(days=n)).isoformat() for n in range(22)],
        )
        today = run[7]
        self.assertEqual(today['score'], self.english['layers']['day']['pull']['score'])

    def test_the_twelve_hours_follow_each_other_through_the_day(self) -> None:
        hours = self.english['hours']
        self.assertEqual([hour['branch'] for hour in hours], list(BRANCH_CHARS))
        self.assertEqual(len(hours[0]['spans']), 2)
        spans = [hours[0]['spans'][0]]
        for hour in hours[1:]:
            self.assertEqual(len(hour['spans']), 1)
            spans.append(hour['spans'][0])
        spans.append(hours[0]['spans'][1])
        for earlier, later in pairwise(spans):
            self.assertEqual(earlier['end'], later['start'])
        for start, end in ((span['start'], span['end']) for span in spans):
            self.assertLess(datetime.fromisoformat(start), datetime.fromisoformat(end))
        # The day's moment, noon on the date at the place, lies within its hours.
        noon = datetime.fromisoformat(f'{DAY}T12:00:00+03:00')
        self.assertLessEqual(datetime.fromisoformat(spans[0]['start']), noon)
        self.assertLess(noon, datetime.fromisoformat(spans[-1]['end']))
        weights = self.english['favourable']['weights']
        for hour in hours:
            with self.subTest(branch=hour['branch']):
                weight = weights[hour['element']]
                if not hour['ties']:
                    self.assertIsNone(hour['call'])
                elif hour['call'] == 'protect':
                    self.assertGreater(weight, 0)
                elif hour['call'] == 'avoid':
                    self.assertLess(weight, 0)

    def test_readings_are_english_only(self) -> None:
        self.assertEqual(
            set(self.english['readings']),
            {name for name, layer in self.english['layers'].items() if layer},
        )
        lines = [r['line'] for r in _relationships(self.english)]
        self.assertTrue(lines)
        self.assertTrue(all(isinstance(line, str) and line for line in lines))
        finnish = self.client.post('/api/today', json={**BODY, 'lang': 'fi'}).json()
        self.assertIsNone(finnish['readings'])
        self.assertTrue(all(r['line'] is None for r in _relationships(finnish)))
        self.assertEqual(
            finnish['layers']['day']['pull'], self.english['layers']['day']['pull']
        )

    def test_no_symbolic_stars_and_no_void(self) -> None:
        forbidden = re.compile(r'(^|_)(stars?|void|kong_wang)($|_)')
        keys = {key.lower() for key in _keys(self.english)}
        self.assertFalse({key for key in keys if forbidden.search(key)})

    def test_marriage_reads_both_charts(self) -> None:
        marriage = self.english['marriage']
        own = self.english['layers']['day']['pull']['score']
        theirs = marriage['partner']['pull']['score']
        self.assertEqual(
            marriage['pull_apart'],
            (own >= 0.5 and theirs <= -0.5) or (theirs >= 0.5 and own <= -0.5),
        )
        self.assertTrue(
            all(
                any(member['pillar'] == 'day' for member in relationship['members'])
                for relationship in marriage['spouse_palace']['relationships']
            )
        )
        partner_luck = marriage['partner']['luck']
        if partner_luck is not None:
            # The partner's relationships carry the canon's lines in English too.
            self.assertTrue(
                all(isinstance(r['line'], str) for r in partner_luck['relationships'])
            )
        self.assertTrue(
            all(isinstance(r['line'], str) for r in marriage['partner_chart'])
        )
        as_partner = self.client.post(
            '/api/today', json={**BODY, 'chart': 'partner'}
        ).json()
        self.assertEqual(as_partner['chart'], 'partner')
        self.assertEqual(
            as_partner['layers']['day']['pull'], marriage['partner']['pull']
        )

    def test_post_reads_what_it_is_sent(self) -> None:
        body = {
            'date': DAY,
            'lang': 'en',
            'place': LISBON,
            'charts': {'self': CHART},
            'schools': {
                'favourable': 'climate',
                'season': 'commander',
                'transits': 'whole',
            },
        }
        reply = self.client.post('/api/today', json=body)
        self.assertEqual(reply.status_code, 200, reply.text)
        answer = reply.json()
        self.assertEqual(
            answer['schools'],
            {'favourable': 'climate', 'season': 'commander', 'transits': 'whole'},
        )
        self.assertEqual(answer['favourable']['school'], 'climate')
        self.assertTrue(answer['favourable']['named'])
        self.assertIsNotNone(answer['season']['commander'])
        self.assertIsNone(answer['marriage'])
        for refused in (
            {**body, 'charts': {'self': CHART}, 'chart': 'partner'},
            {**body, 'charts': {'self': {**CHART, 'zi': 'midnight'}}},
            {**body, 'charts': {'self': CHART}, 'weights': {'wood': 1.2}},
            {**body, 'schools': {'favourable': 'structure'}},
            {
                **body,
                'charts': {'self': {**CHART, 'time': '03:30', 'date': '2021-03-28'}},
            },
        ):
            with self.subTest(refused=refused):
                self.assertEqual(
                    self.client.post('/api/today', json=refused).status_code, 400
                )


# What the page sends for days: a day's body, without its date and language.
DAYS_BODY: dict[str, Any] = {
    'place': HELSINKI,
    'charts': {'self': CHART, 'partner': PARTNER},
}
# Samoa moved across the date line and skipped 30 December 2011 entirely.
APIA = {
    'name': 'Apia, Tuamasaga, Samoa',
    'city': 'Apia',
    'timezone': 'Pacific/Apia',
    'latitude': -13.83333,
    'longitude': -171.76666,
}


def _dates(first: date, count: int) -> list[str]:
    return [(first + timedelta(days=n)).isoformat() for n in range(count)]


class TestDays(unittest.TestCase):
    accounts: ClassVar[Accounts]
    client: ClassVar[TestClient]

    @classmethod
    def setUpClass(cls) -> None:
        cls.accounts = install_accounts(cls)
        cls.client = site_client()
        sign_in(cls.client, cls.accounts, 'days@example.com')

    def days(self, body: dict[str, Any] = DAYS_BODY, **parts: Any) -> dict[str, Any]:
        reply = self.client.post('/api/today/days', json={**body, **parts})
        self.assertEqual(reply.status_code, 200, reply.text)
        return reply.json()

    def test_each_day_is_the_runs_own(self) -> None:
        # A day a run and a request for days both read is the same day, but for the
        # run's offset: for either chart, by two sets of schools.
        climate = {'favourable': 'climate', 'season': 'commander', 'transits': 'whole'}
        for chart, schools in (('self', {}), ('partner', climate)):
            with self.subTest(chart=chart, schools=schools):
                today = self.client.post(
                    '/api/today', json={**BODY, 'chart': chart, 'schools': schools}
                )
                self.assertEqual(today.status_code, 200, today.text)
                known = {
                    day['date']: {k: v for k, v in day.items() if k != 'offset'}
                    for day in today.json()['run']
                }
                for asked in ({'after': '2026-10-10'}, {'before': '2026-10-12'}):
                    answer = self.days(chart=chart, schools=schools, **asked)
                    self.assertEqual(answer['policy'], 'today_days_v1')
                    self.assertEqual(answer['chart'], chart)
                    shared = [day for day in answer['days'] if day['date'] in known]
                    self.assertGreaterEqual(len(shared), 8)
                    for day in shared:
                        self.assertEqual(day, known[day['date']])

    def test_three_weeks_after_or_before_a_date(self) -> None:
        ahead = self.days(after='2026-10-11')
        self.assertEqual(ahead['after'], '2026-10-11')
        self.assertNotIn('before', ahead)
        self.assertEqual((ahead['through'], ahead['end']), ('2026-11-01', False))
        self.assertEqual(
            [day['date'] for day in ahead['days']], _dates(date(2026, 10, 12), 21)
        )
        self.assertNotIn('offset', ahead['days'][0])
        back = self.days(before='2026-10-11')
        self.assertEqual(back['before'], '2026-10-11')
        self.assertNotIn('after', back)
        self.assertEqual((back['through'], back['end']), ('2026-09-20', False))
        self.assertEqual(
            [day['date'] for day in back['days']], _dates(date(2026, 9, 20), 21)
        )

    def test_a_day_the_clocks_skipped_is_covered_and_left_out(self) -> None:
        body = {'place': APIA, 'charts': {'self': CHART}}
        ahead = self.days(body, after='2011-12-22')
        back = self.days(body, before='2012-01-13')
        self.assertEqual(ahead['through'], '2012-01-12')
        self.assertEqual(back['through'], '2011-12-23')
        for answer in (ahead, back):
            dates = [day['date'] for day in answer['days']]
            self.assertNotIn('2011-12-30', dates)
            self.assertEqual(len(dates), 20)
            self.assertIn('2011-12-29', dates)
            self.assertIn('2011-12-31', dates)

    def test_the_engines_first_and_last_dates_end_them(self) -> None:
        last = self.days(after='2100-12-20')
        self.assertEqual((last['through'], last['end']), ('2100-12-31', True))
        self.assertEqual(
            [day['date'] for day in last['days']], _dates(date(2100, 12, 21), 11)
        )
        first = self.days(before='1949-01-10')
        self.assertEqual((first['through'], first['end']), ('1949-01-01', True))
        self.assertEqual(
            [day['date'] for day in first['days']], _dates(date(1949, 1, 1), 9)
        )
        # Asked at the end itself: nothing more that way.
        for asked, through in (
            ({'after': '2100-12-31'}, '2100-12-31'),
            ({'before': '1949-01-01'}, '1949-01-01'),
        ):
            with self.subTest(asked=asked):
                none = self.days(**asked)
                self.assertEqual(
                    (none['through'], none['end'], none['days']), (through, True, [])
                )
        # A day short of the end is not the end.
        self.assertFalse(self.days(after='2100-12-09')['end'])
        self.assertFalse(self.days(before='1949-01-23')['end'])

    def test_days_are_asked_for_after_or_before_one_readable_date(self) -> None:
        for refused in (
            DAYS_BODY,
            {**DAYS_BODY, 'after': '2026-10-11', 'before': '2026-10-11'},
            {**DAYS_BODY, 'after': '2026-02-30'},
            {**DAYS_BODY, 'after': '2026-1-1'},
            {**DAYS_BODY, 'after': 20261011},
            {**DAYS_BODY, 'after': '1948-12-31'},
            {**DAYS_BODY, 'before': '2101-01-01'},
            {**DAYS_BODY, 'after': '9999-12-31'},
            {**DAYS_BODY, 'charts': {'self': CHART}, 'chart': 'partner', 'after': DAY},
            {**DAYS_BODY, 'after': DAY, 'lang': 'en'},
            {**DAYS_BODY, 'after': DAY, 'date': DAY},
            {**DAYS_BODY, 'after': DAY, 'schools': {'favourable': 'structure'}},
        ):
            with self.subTest(refused=refused):
                reply = self.client.post('/api/today/days', json=refused)
                self.assertEqual(reply.status_code, 400, reply.text)

    def test_a_malformed_date_is_said_by_the_field_it_is_in(self) -> None:
        for field in ('after', 'before'):
            with self.subTest(field=field):
                reply = self.client.post(
                    '/api/today/days', json={**DAYS_BODY, field: '2026-1-1'}
                )
                self.assertEqual(reply.status_code, 400, reply.text)
                self.assertEqual(
                    reply.json()['detail'], f'{field} must be in YYYY-MM-DD format.'
                )
        reply = self.client.post('/api/today', json={**BODY, 'date': '2026-1-1'})
        self.assertEqual(reply.json()['detail'], 'date must be in YYYY-MM-DD format.')

    def test_days_need_an_account_and_are_its_own(self) -> None:
        asked = {**DAYS_BODY, 'after': DAY}
        self.assertEqual(
            site_client().post('/api/today/days', json=asked).status_code, 401
        )
        reply = self.client.post('/api/today/days', json=asked)
        self.assertEqual(reply.headers['cache-control'], 'private, no-cache')


# ── A year of days, against the daily briefing's own formula ──

# The briefing's standings, its multipliers and its Earth months (Earth months school).
_DECREE = ('Prosperous', 'Mutual Generation', 'Dead', 'Imprisoned', 'Rest')
_MULTIPLIER = {
    'Prosperous': 1.2,
    'Mutual Generation': 1.0,
    'Rest': 0.6,
    'Imprisoned': 0.4,
    'Dead': 0.2,
}
_ELEMENTS = ('wood', 'fire', 'earth', 'metal', 'water')
_SEASON = {2: 'wood', 3: 'wood', 4: 'wood', 5: 'fire', 6: 'fire', 7: 'fire'}
_SEASON.update(
    {8: 'metal', 9: 'metal', 10: 'metal', 11: 'water', 0: 'water', 1: 'water'}
)
_HIDDEN = {
    0: [9],
    1: [5, 9, 7],
    2: [0, 2, 4],
    3: [1],
    4: [4, 1, 9],
    5: [2, 6, 4],
    6: [3, 5],
    7: [5, 3, 1],
    8: [6, 8, 4],
    9: [7],
    10: [4, 7, 3],
    11: [8, 0],
}


def _briefing_day_pull(
    stem: int, branch: int, weights: dict[str, float], month_branch: int
) -> float:
    ruler = 'earth' if month_branch in (4, 10, 1, 7) else _SEASON[month_branch]
    start = _ELEMENTS.index(ruler)

    def counts(element: str) -> float:
        return _MULTIPLIER[_DECREE[(_ELEMENTS.index(element) - start) % 5]]

    def element(index: int) -> str:
        return _ELEMENTS[index // 2]

    total = weights[element(stem)] * counts(element(stem))
    for rank, hidden in enumerate(_HIDDEN[branch]):
        total += (
            weights[element(hidden)] * (1.0, 0.4, 0.2)[rank] * counts(element(hidden))
        )
    return total


def _briefing_day_pillar(day: date) -> tuple[int, int]:
    a = (14 - day.month) // 12
    y, m = day.year + 4800 - a, day.month + 12 * a - 3
    jdn = day.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    return (jdn + 9) % 10, (jdn + 1) % 12


class TestAgainstTheBriefingsFormula(unittest.TestCase):
    """With the Earth months school, the briefing's own season rule, a day's pull is
    the briefing's formula, and its pillar the briefing's day pillar, over a year."""

    accounts: ClassVar[Accounts]
    client: ClassVar[TestClient]

    @classmethod
    def setUpClass(cls) -> None:
        cls.accounts = install_accounts(cls)
        cls.client = site_client()
        sign_in(cls.client, cls.accounts, 'year@example.com')

    def test_a_year_of_days(self) -> None:
        stem_index = '甲乙丙丁戊己庚辛壬癸'
        checked = 0
        center = date(2026, 1, 8)
        while center <= date(2026, 12, 31) + timedelta(days=7):
            answer = self.client.post(
                '/api/today',
                json={
                    'date': center.isoformat(),
                    'lang': 'fi',
                    'place': HELSINKI,
                    'charts': {'self': CHART},
                    'schools': {'season': 'months'},
                },
            ).json()
            weights = answer['favourable']['weights']
            for day in answer['run']:
                when = date.fromisoformat(day['date'])
                at = pillars_at(
                    BirthInput(
                        year=when.year,
                        month=when.month,
                        day=when.day,
                        hour=12,
                        minute=0,
                        second=0,
                        timezone_name=HELSINKI['timezone'],
                        longitude=HELSINKI['longitude'],
                        latitude=HELSINKI['latitude'],
                        fold=0,
                    )
                )
                stem = stem_index.index(day['pillar']['stem']['chinese'])
                branch = BRANCH_CHARS.index(day['pillar']['branch']['chinese'])
                self.assertEqual((stem, branch), _briefing_day_pillar(when))
                expected = _briefing_day_pull(
                    stem, branch, weights, at.month.branch_idx
                )
                self.assertAlmostEqual(day['score'], expected, delta=0.005 + 1e-9)
                checked += 1
            center += timedelta(days=22)
        self.assertGreaterEqual(checked, 365)


if __name__ == '__main__':
    unittest.main()
