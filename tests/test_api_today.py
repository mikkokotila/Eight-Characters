"""GET /api/today, POST /api/today and GET /api/schools (docs/Today.md)."""

import re
import unittest
from datetime import date, datetime, timedelta
from itertools import pairwise
from typing import Any, ClassVar

from fastapi.testclient import TestClient

from eight_characters.accounts.web import Accounts, account_key
from eight_characters.engine import pillars_at
from eight_characters.sexagenary import BRANCHES as BRANCH_CHARS
from eight_characters.time_convert import BirthInput
from tests.accounts_support import install_accounts, sign_in, site_client

HELSINKI = {
    'name': 'Helsinki, Uusimaa, Finland',
    'timezone': 'Europe/Helsinki',
    'latitude': 60.16952,
    'longitude': 24.93545,
}
LISBON = {
    'name': 'Lisbon, Lisbon, Portugal',
    'timezone': 'Europe/Lisbon',
    'latitude': 38.71667,
    'longitude': -9.13333,
}
# Made-up births, of nobody.
OWN = {'date': '1990-05-17', 'time': '08:30', 'place': HELSINKI, 'gender': 'female'}
PARTNER = {
    'name': 'Partner',
    'date': '1988-11-02',
    'time': '21:05:30',
    'place': LISBON,
    'gender': 'male',
}
DAY = '2026-10-11'


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
        for path, body in (
            ('/api/account/charts/self', OWN),
            ('/api/account/charts/partner', PARTNER),
            ('/api/account/place', {'place': HELSINKI}),
        ):
            reply = cls.client.put(path, json={**body, 'key': cls.key})
            if reply.status_code != 200:
                raise AssertionError(f'{path}: {reply.text}')
        reply = cls.client.get('/api/today', params={'date': DAY, 'lang': 'en'})
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

    def test_today_needs_a_chart_and_a_place(self) -> None:
        client = site_client()
        sign_in(client, self.accounts, 'nothing-yet@example.com')
        user = self.accounts.store.user_by_email('nothing-yet@example.com')
        assert user is not None
        key = account_key(user)
        asked = {'date': DAY, 'lang': 'en'}
        self.assertEqual(client.get('/api/today', params=asked).status_code, 404)
        client.put('/api/account/charts/self', json={**OWN, 'key': key})
        reply = client.get('/api/today', params=asked)
        self.assertEqual(reply.status_code, 404)
        self.assertEqual(reply.json()['detail'], 'Where you are is not set.')
        client.put('/api/account/place', json={'place': LISBON, 'key': key})
        partner = client.get('/api/today', params={**asked, 'chart': 'partner'})
        self.assertEqual(partner.status_code, 404)

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
                reply = self.client.get(
                    '/api/today', params={'date': text, 'lang': 'en'}
                )
                self.assertEqual(reply.status_code, 400, reply.text)
        reply = self.client.get('/api/today', params={'date': DAY, 'lang': 'sv'})
        self.assertEqual(reply.status_code, 400)

    def test_a_day_the_clocks_skipped(self) -> None:
        # Samoa moved across the date line and skipped 30 December 2011 entirely.
        apia = {
            'name': 'Apia, Tuamasaga, Samoa',
            'timezone': 'Pacific/Apia',
            'latitude': -13.83333,
            'longitude': -171.76666,
        }
        body = {'lang': 'fi', 'place': apia, 'charts': {'self': OWN}}
        skipped = self.client.post('/api/today', json={**body, 'date': '2011-12-30'})
        self.assertEqual(skipped.status_code, 400)
        after = self.client.post('/api/today', json={**body, 'date': '2011-12-31'})
        self.assertEqual(after.status_code, 200, after.text)
        dates = [day['date'] for day in after.json()['run']]
        self.assertNotIn('2011-12-30', dates)
        self.assertEqual(len(dates), 21)
        self.assertIn('2011-12-29', dates)

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
                'location': {k: v for k, v in HELSINKI.items() if k != 'name'},
            },
        ).json()
        for layer in ('day', 'month', 'year'):
            with self.subTest(layer=layer):
                shown = self.english['layers'][layer]['pillar']
                self.assertEqual(shown['stem'], first['pillars'][layer]['stem'])
                self.assertEqual(shown['branch'], first['pillars'][layer]['branch'])
        self.assertEqual(self.english['changes'], first['changes'])

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
        finnish = self.client.get(
            '/api/today', params={'date': DAY, 'lang': 'fi'}
        ).json()
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
        as_partner = self.client.get(
            '/api/today', params={'date': DAY, 'lang': 'en', 'chart': 'partner'}
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
            'charts': {'self': OWN},
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
            {**body, 'charts': {'self': OWN}, 'chart': 'partner'},
            {**body, 'charts': {'self': {**OWN, 'zi': 'midnight'}}},
            {**body, 'charts': {'self': OWN}, 'weights': {'wood': 1.2}},
            {**body, 'schools': {'favourable': 'structure'}},
            {
                **body,
                'charts': {'self': {**OWN, 'time': '03:30', 'date': '2021-03-28'}},
            },
        ):
            with self.subTest(refused=refused):
                self.assertEqual(
                    self.client.post('/api/today', json=refused).status_code, 400
                )


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
                    'charts': {'self': OWN},
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
