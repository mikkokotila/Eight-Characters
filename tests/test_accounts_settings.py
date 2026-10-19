"""The settings an account keeps: its saved charts, which of them is the person's own,
the couples they form, where the person is, and the schools chosen for Today. Their
record, their database, their backup and the API that sets them."""

import json
import shutil
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any, ClassVar, cast
from unittest.mock import patch

import pyrage

from eight_characters.accounts import store as store_module
from eight_characters.accounts.backup import run_backup
from eight_characters.accounts.plans import LIMITS, PlanLimits, check_limits
from eight_characters.accounts.records import (
    CHART_LIMIT,
    DEFAULT_SCHOOLS,
    NO_CHOICE,
    PLANS,
    Birth,
    ChosenSchools,
    Couple,
    Place,
    RecordError,
    SavedChart,
    Schools,
    Settings,
    User,
    canonical_json,
    decode_settings,
    decode_user,
    encode_settings,
    encode_user,
    partner_chart_id,
    settings_value,
)
from eight_characters.accounts.restore import restore_backup
from eight_characters.accounts.store import (
    AccountStore,
    ChartLimit,
    CoupleLimit,
    DuplicateChart,
    DuplicateCouple,
    SettingsChanged,
    UnknownChart,
    UnknownCouple,
    UnknownUser,
)
from eight_characters.accounts.web import Accounts, account_key, get_accounts
from eight_characters.main import app
from tests.accounts_support import (
    Clock,
    code_in,
    git,
    install_accounts,
    mails_to,
    make_remote_and_checkout,
    sign_in,
    site_client,
)

HELSINKI = Place(
    name='Helsinki, Uusimaa, Finland',
    city='Helsinki',
    timezone='Europe/Helsinki',
    latitude=60.16952,
    longitude=24.93545,
)
LISBON = Place(
    name='Lisbon, Lisbon, Portugal',
    city='Lisbon',
    timezone='Europe/Lisbon',
    latitude=38.71667,
    longitude=-9.13333,
)
# Made-up births, of nobody.
BIRTH = Birth(
    name=None,
    date='1990-05-17',
    time='08:30',
    place=HELSINKI,
    fold=None,
    gender='female',
    zi='split_midnight',
)
PARTNER = Birth(
    name='Partner',
    date='1988-11-02',
    time='21:05:30',
    place=LISBON,
    fold=None,
    gender='male',
    zi='whole_zi_23',
)


def born(number: int) -> Birth:
    """Made-up births, each charting differently: a day of January 1990 and an hour."""
    return replace(
        BIRTH, date=f'1990-01-{1 + number % 28:02d}', time=f'{number // 28:02d}:45'
    )


MINE_ID = '1' * 32
PARTNER_ID = '2' * 32
COUPLE_ID = '3' * 32
SETTINGS = Settings(
    charts=(SavedChart(MINE_ID, BIRTH), SavedChart(PARTNER_ID, PARTNER)),
    my_chart=MINE_ID,
    couples=(Couple(COUPLE_ID, (MINE_ID, PARTNER_ID)),),
    pending_partner=None,
    place=LISBON,
    schools=ChosenSchools(favourable='climate', season='commander', transits=None),
    updated_at='2026-10-07T12:00:00Z',
)
# Settings as accounts kept them before they kept charts: one partner's chart.
PARTNER_SETTINGS: dict[str, Any] = {
    'partner': {
        'date': PARTNER.date,
        'fold': PARTNER.fold,
        'gender': PARTNER.gender,
        'name': PARTNER.name,
        'place': {
            'city': LISBON.city,
            'latitude': LISBON.latitude,
            'longitude': LISBON.longitude,
            'name': LISBON.name,
            'timezone': LISBON.timezone,
        },
        'time': PARTNER.time,
        'zi': PARTNER.zi,
    },
    'place': None,
    'schools': {'favourable': None, 'season': 'months', 'transits': None},
    'updated_at': '2026-10-07T12:00:00Z',
}
USER = User(
    id='3f9c2a7d0b8e4c51a6f2d9e0b7c4a1e5',
    email='reader@example.com',
    language='fi',
    plan='free',
    created_at='2026-10-07T12:00:00Z',
    updated_at='2026-10-07T12:30:00Z',
)


def large_library() -> Settings:
    """A future writer's retained library, above this release's write allowance."""
    charts = tuple(SavedChart(f'{n:032x}', born(n)) for n in range(CHART_LIMIT + 1))
    return replace(
        SETTINGS,
        charts=charts,
        my_chart=charts[0].id,
        couples=(Couple(COUPLE_ID, (charts[0].id, charts[-1].id)),),
    )


def keep_large_library(store: AccountStore, user: User) -> Settings:
    """Seed a future writer's row; production save_chart still stops at 50."""
    settings = large_library()
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            'INSERT INTO settings (user_id, record) VALUES (?, ?)',
            (user.id, encode_settings(settings)),
        )
    return settings


def _place_json(place: Place) -> dict[str, Any]:
    return {
        'name': place.name,
        'city': place.city,
        'timezone': place.timezone,
        'latitude': place.latitude,
        'longitude': place.longitude,
    }


def _birth_json(birth: Birth, key: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        'key': key,
        'date': birth.date,
        'time': birth.time,
        'place': _place_json(birth.place),
        'gender': birth.gender,
        'zi': birth.zi,
    }
    if birth.name is not None:
        body['name'] = birth.name
    if birth.fold is not None:
        body['fold'] = birth.fold
    return body


class TestSettingsRecords(unittest.TestCase):
    def test_each_part_is_checked(self) -> None:
        for changes in (
            {'city': ''},
            {'name': ''},
            {'name': ' Helsinki'},
            {'name': 'Hel\nsinki'},
            {'name': 'x' * 201},
            {'timezone': 'Europe/Nowhere'},
            {'timezone': '../../etc/passwd'},
            {'latitude': 90.5},
            {'longitude': -180.5},
            {'latitude': float('nan')},
            {'latitude': 60},
        ):
            with self.subTest(changes=changes), self.assertRaises(RecordError):
                replace(HELSINKI, **changes)
        for changes in (
            {'name': ''},
            {'name': 'x' * 81},
            {'date': '1990-5-17'},
            {'date': '1990-02-30'},
            {'date': '1948-12-31'},
            {'date': '2101-01-01'},
            {'time': '8:30'},
            {'time': '24:00'},
            {'time': '٠٨:٣٠'},
            {'fold': 2},
            {'fold': True},
            {'gender': 'other'},
            {'zi': 'zi_at_midnight'},
        ):
            with self.subTest(changes=changes), self.assertRaises(RecordError):
                replace(BIRTH, **changes)
        for changes in (
            {'favourable': 'structure'},
            {'season': 'seasons'},
            {'transits': 'modern'},
        ):
            with self.subTest(changes=changes), self.assertRaises(RecordError):
                replace(DEFAULT_SCHOOLS, **changes)
            with self.subTest(chosen=changes), self.assertRaises(RecordError):
                replace(NO_CHOICE, **changes)
        with self.assertRaises(RecordError):
            replace(SETTINGS, updated_at='2026-10-07 12:00')
        for name, change in {
            'a chart id that is not one': lambda: SavedChart('x', BIRTH),
            'a couple of one chart': lambda: Couple(COUPLE_ID, (MINE_ID, MINE_ID)),
            'two charts with one id': lambda: replace(
                SETTINGS,
                charts=(SavedChart(MINE_ID, BIRTH), SavedChart(MINE_ID, PARTNER)),
            ),
            'one birth saved twice, under two names': lambda: replace(
                SETTINGS,
                charts=(
                    SavedChart(MINE_ID, BIRTH),
                    SavedChart(
                        PARTNER_ID, replace(BIRTH, name='Again', time='08:30:00')
                    ),
                ),
                couples=(),
            ),
            'my chart not kept': lambda: replace(SETTINGS, my_chart='4' * 32),
            'a couple of a chart not kept': lambda: replace(
                SETTINGS, couples=(Couple(COUPLE_ID, (MINE_ID, '4' * 32)),)
            ),
            'one pair twice': lambda: replace(
                SETTINGS,
                couples=(
                    Couple(COUPLE_ID, (MINE_ID, PARTNER_ID)),
                    Couple('5' * 32, (PARTNER_ID, MINE_ID)),
                ),
            ),
            'a waiting partner beside my chart': lambda: replace(
                SETTINGS, pending_partner=PARTNER_ID
            ),
            'a waiting partner not kept': lambda: replace(
                SETTINGS, my_chart=None, pending_partner='4' * 32
            ),
        }.items():
            with self.subTest(name), self.assertRaises(RecordError):
                change()

    def test_the_defaults(self) -> None:
        self.assertEqual(
            DEFAULT_SCHOOLS,
            Schools(favourable='support', season='eighteen', transits='phases'),
        )
        self.assertEqual(NO_CHOICE.effective(), DEFAULT_SCHOOLS)
        self.assertEqual(
            SETTINGS.schools.effective(),
            Schools(favourable='climate', season='commander', transits='phases'),
        )

    def test_a_retained_library_is_not_limited_on_read(self) -> None:
        settings = large_library()
        self.assertEqual(decode_settings(encode_settings(settings)), settings)
        self.assertEqual(decode_user(encode_user(USER, settings)), (USER, settings))
        # Validation also covers the charts beyond the current write allowance.
        with self.assertRaises(RecordError):
            replace(settings, charts=(*settings.charts, settings.charts[-1]))

    def test_canonical_bytes(self) -> None:
        self.assertEqual(
            encode_settings(replace(SETTINGS, charts=(), my_chart=None, couples=())),
            b'{\n'
            b'  "charts": [],\n'
            b'  "couples": [],\n'
            b'  "my_chart": null,\n'
            b'  "pending_partner": null,\n'
            b'  "place": {\n'
            b'    "city": "Lisbon",\n'
            b'    "latitude": 38.71667,\n'
            b'    "longitude": -9.13333,\n'
            b'    "name": "Lisbon, Lisbon, Portugal",\n'
            b'    "timezone": "Europe/Lisbon"\n'
            b'  },\n'
            b'  "schools": {\n'
            b'    "favourable": "climate",\n'
            b'    "season": "commander",\n'
            b'    "transits": null\n'
            b'  },\n'
            b'  "updated_at": "2026-10-07T12:00:00Z"\n'
            b'}\n',
        )

    def test_round_trip(self) -> None:
        for settings in (
            SETTINGS,
            replace(SETTINGS, charts=(), my_chart=None, couples=(), place=None),
            replace(
                SETTINGS,
                charts=(SavedChart(MINE_ID, replace(BIRTH, fold=1, name='Äiti')),),
                couples=(),
            ),
            replace(SETTINGS, my_chart=None, couples=(), pending_partner=PARTNER_ID),
        ):
            with self.subTest(settings=settings):
                self.assertEqual(decode_settings(encode_settings(settings)), settings)

    def _variant(self, change: Any) -> bytes:
        value = settings_value(SETTINGS)
        change(value)
        return canonical_json(value)

    def test_refuses_anything_but_valid_canonical_settings(self) -> None:
        canonical = encode_settings(SETTINGS)
        cases: dict[str, bytes] = {
            'not JSON': b'{',
            'not an object': b'[]\n',
            'an extra field': self._variant(lambda v: v.update(admin=True)),
            'a missing library': self._variant(lambda v: v.pop('charts')),
            'a partner beside the library': self._variant(
                lambda v: v.update(partner=None)
            ),
            'a chart without its id': self._variant(lambda v: v['charts'][0].pop('id')),
            'a couple of three': self._variant(
                lambda v: v['couples'][0]['charts'].append(MINE_ID)
            ),
            'a coordinate as a whole number': self._variant(
                lambda v: v['place'].update(latitude=38)
            ),
            'a coordinate as text': self._variant(
                lambda v: v['place'].update(latitude='38.7')
            ),
            'a name that is not text': self._variant(
                lambda v: v['charts'][1]['birth'].update(name=1)
            ),
            'an unknown school': self._variant(
                lambda v: v['schools'].update(season='modern')
            ),
            'a fold of true': self._variant(
                lambda v: v['charts'][1]['birth'].update(fold=True)
            ),
            'a place that is not an object': self._variant(
                lambda v: v['charts'][1]['birth'].update(place=[])
            ),
            'a time zone that is not text': self._variant(
                lambda v: v['place'].update(timezone=[])
            ),
            'no final newline': canonical.rstrip(b'\n'),
        }
        for name, data in cases.items():
            with self.subTest(name), self.assertRaises(RecordError):
                decode_settings(data)

    def test_settings_kept_with_a_partner_read_it_as_a_saved_chart(self) -> None:
        # The settings of an account from before accounts kept charts: its partner is
        # a saved chart, under the same id every time, waiting to pair with the
        # person's own.
        settings = decode_settings(canonical_json(PARTNER_SETTINGS))
        chart_id = partner_chart_id(PARTNER_SETTINGS['partner'])
        self.assertEqual(
            settings,
            Settings(
                charts=(SavedChart(chart_id, PARTNER),),
                my_chart=None,
                couples=(),
                pending_partner=chart_id,
                place=None,
                schools=replace(NO_CHOICE, season='months'),
                updated_at='2026-10-07T12:00:00Z',
            ),
        )
        self.assertEqual(decode_settings(canonical_json(PARTNER_SETTINGS)), settings)
        none = decode_settings(canonical_json({**PARTNER_SETTINGS, 'partner': None}))
        self.assertEqual((none.charts, none.pending_partner), ((), None))
        with self.assertRaises(RecordError):
            decode_settings(canonical_json(PARTNER_SETTINGS).rstrip(b'\n'))

    def test_the_account_record_carries_its_settings(self) -> None:
        data = encode_user(USER, SETTINGS)
        self.assertEqual(json.loads(data)['schema'], 3)
        self.assertEqual(json.loads(data)['settings'], settings_value(SETTINGS))
        self.assertEqual(decode_user(data), (USER, SETTINGS))

    def test_a_schema_1_record_is_an_account_without_settings(self) -> None:
        old = canonical_json(
            {
                'created_at': USER.created_at,
                'email': USER.email,
                'id': USER.id,
                'kind': 'user',
                'language': USER.language,
                'plan': USER.plan,
                'schema': 1,
                'updated_at': USER.updated_at,
            }
        )
        self.assertEqual(decode_user(old), (USER, None))

    def test_a_schema_2_record_reads_its_partner_as_a_saved_chart(self) -> None:
        old = {
            'created_at': USER.created_at,
            'email': USER.email,
            'id': USER.id,
            'kind': 'user',
            'language': USER.language,
            'plan': USER.plan,
            'schema': 2,
            'settings': PARTNER_SETTINGS,
            'updated_at': USER.updated_at,
        }
        user, settings = decode_user(canonical_json(old))
        self.assertEqual(user, USER)
        assert settings is not None
        self.assertEqual(
            settings.pending_partner, partner_chart_id(PARTNER_SETTINGS['partner'])
        )
        # A schema 2 record holds the settings it was written with, and a schema 3
        # record today's.
        with self.assertRaises(RecordError):
            decode_user(canonical_json({**old, 'settings': settings_value(SETTINGS)}))
        with self.assertRaises(RecordError):
            decode_user(canonical_json({**old, 'schema': 3}))

    def test_a_record_with_broken_settings_is_refused(self) -> None:
        value = json.loads(encode_user(USER, SETTINGS))
        value['settings']['schools']['favourable'] = 'modern'
        with self.assertRaises(RecordError):
            decode_user(canonical_json(value))


class TestSeveralCouples(unittest.TestCase):
    def test_a_chart_can_be_in_several_couples(self) -> None:
        # Any number of couples per chart: a plan's cap is checked when a couple is
        # asked for, never when settings are read (plans.py).
        third = '4' * 32
        settings = replace(
            SETTINGS,
            charts=(*SETTINGS.charts, SavedChart(third, born(1))),
            couples=(
                Couple(COUPLE_ID, (MINE_ID, PARTNER_ID)),
                Couple('5' * 32, (third, MINE_ID)),
            ),
        )
        # In the order formed, whichever side the chart is on.
        self.assertEqual(settings.couples_of(MINE_ID), settings.couples)
        self.assertEqual(settings.couples_of(PARTNER_ID), settings.couples[:1])
        self.assertEqual(
            settings.couple_between(PARTNER_ID, MINE_ID), settings.couples[0]
        )
        self.assertIsNone(settings.couple_between(PARTNER_ID, third))
        self.assertEqual(decode_settings(encode_settings(settings)), settings)


class TestPlans(unittest.TestCase):
    def test_every_plan_has_its_limits_and_none_caps_couples_now(self) -> None:
        self.assertEqual(set(LIMITS), set(PLANS))
        for plan in PLANS:
            with self.subTest(plan=plan):
                self.assertIsNone(LIMITS[plan].couples_per_chart)
                self.assertEqual(LIMITS[plan].charts_per_account, CHART_LIMIT)

    def test_a_table_that_misses_or_adds_a_plan_is_refused(self) -> None:
        missing = {plan: LIMITS[plan] for plan in PLANS if plan != 'basic'}
        added: dict[Any, PlanLimits] = {**LIMITS, 'gold': LIMITS['pro']}
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory)
        path = directory / 'accounts.sqlite3'
        for table in (missing, added):
            with self.subTest(plans=sorted(table)):
                with self.assertRaises(ValueError):
                    check_limits(table)
                # Nor does a store start with it, and it builds nothing.
                with self.assertRaises(ValueError):
                    AccountStore.create(path, limits=table)
                self.assertFalse(path.exists())
        AccountStore.create(path)
        with self.assertRaises(ValueError):
            AccountStore.open(path, limits=missing)

    def test_a_cap_is_one_couple_at_least(self) -> None:
        for cap in (0, -1):
            with self.subTest(cap=cap), self.assertRaises(ValueError):
                PlanLimits(couples_per_chart=cap)

    def test_chart_allowances_are_positive_integers_or_unlimited(self) -> None:
        for cap in (1, 5, 25, None):
            self.assertEqual(PlanLimits(None, cap).charts_per_account, cap)
        for cap in (0, -1, True, False, 1.5, '5'):
            with self.subTest(cap=cap), self.assertRaises(ValueError):
                PlanLimits(None, cast(Any, cap))


class StoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory)
        self.path = self.directory / 'accounts.sqlite3'
        self.clock = Clock()
        self.store = AccountStore.create(self.path, clock=self.clock)
        self.user = self.store.create_user('reader@example.com', 'fi')

    def read(self) -> str | None:
        """The version of the reader's settings a change is made from."""
        settings = self.store.settings(self.user.id)
        return None if settings is None else settings.updated_at

    def keep_several_couples(self) -> Settings:
        """Gives the reader a chart in two couples, kept as #96's release writes them:
        this release reads them, and does not pair them (#98)."""
        ids = []
        for birth in (BIRTH, PARTNER, born(5)):
            _, chart_id = self.store.save_chart(self.user.id, birth, self.read())
            ids.append(chart_id)
        kept = self.store.settings(self.user.id)
        assert kept is not None
        mine, partner, third = ids
        several = replace(
            kept,
            couples=(
                Couple('5' * 32, (mine, partner)),
                Couple('6' * 32, (third, mine)),
            ),
        )
        connection = sqlite3.connect(self.path)
        try:
            connection.execute(
                'UPDATE settings SET record = ? WHERE user_id = ?',
                (encode_settings(several), self.user.id),
            )
            connection.commit()
        finally:
            connection.close()
        return several


class TestSettingsStore(StoreCase):
    def test_allowances_control_additions_without_limiting_retained_data(self) -> None:
        kept = 0
        for cap in (1, 5, 25, None):
            with self.subTest(cap=cap):
                store = AccountStore.open(
                    self.path, clock=self.clock,
                    limits={**LIMITS, 'free': PlanLimits(None, cap)},
                )
                target = 52 if cap is None else cap
                for number in range(kept, target):
                    store.save_chart(self.user.id, born(number), self.read())
                kept = target
                if cap is not None:
                    before = store.backup_snapshot()
                    with self.assertRaises(ChartLimit):
                        store.save_chart(self.user.id, born(target), self.read())
                    self.assertEqual(store.backup_snapshot(), before)
        settings = self.store.settings(self.user.id)
        assert settings is not None
        first, last = settings.charts[0].id, settings.charts[-1].id
        store.add_couple(self.user.id, (first, last), self.read())
        store.set_my_chart(self.user.id, first, self.read())
        low = AccountStore.open(
            self.path, clock=self.clock, limits={**LIMITS, 'free': PlanLimits(None, 1)},
        )
        retained = low.settings(self.user.id)
        assert retained is not None
        self.assertEqual(len(retained.charts), 52)
        self.assertEqual(low.account_data(self.user.id)['settings'], settings_value(retained))
        renamed = low.rename_chart(self.user.id, last, 'Still here', self.read())
        assert renamed is not None
        corrected = low.update_chart(self.user.id, last, born(80), self.read())
        assert corrected is not None
        self.assertEqual(corrected.couples, retained.couples)
        self.assertEqual(corrected.my_chart, first)
        removed = low.delete_chart(self.user.id, retained.charts[1].id, self.read())
        assert removed is not None
        self.assertEqual((len(removed.charts), removed.couples), (51, retained.couples))
        with self.assertRaises(ChartLimit):
            low.save_chart(self.user.id, born(90), self.read())

    def test_two_writers_cannot_race_past_the_allowance(self) -> None:
        def save(number: int) -> str:
            store = AccountStore.open(
                self.path, clock=self.clock,
                limits={**LIMITS, 'free': PlanLimits(None, 1)},
            )
            try:
                store.save_chart(self.user.id, born(number), None)
            except (ChartLimit, SettingsChanged):
                return 'refused'
            return 'saved'

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(pool.map(save, (0, 1)), ['saved', 'refused'])
        settings = self.store.settings(self.user.id)
        assert settings is not None
        self.assertEqual(len(settings.charts), 1)

    def test_a_retained_library_can_be_read_exported_and_edited(self) -> None:
        settings = keep_large_library(self.store, self.user)
        self.assertEqual(self.store.settings(self.user.id), settings)
        self.assertEqual(
            self.store.account_data(self.user.id)['settings'], settings_value(settings)
        )
        with self.assertRaises(ChartLimit):
            self.store.save_chart(self.user.id, born(60), settings.updated_at)
        self.assertEqual(self.store.settings(self.user.id), settings)
        changed = self.store.rename_chart(
            self.user.id, settings.charts[-1].id, 'Retained', settings.updated_at
        )
        assert changed is not None
        self.assertEqual(len(changed.charts), CHART_LIMIT + 1)
        self.assertEqual(changed.charts[-1].birth.name, 'Retained')
        self.assertEqual(changed.couples, settings.couples)

    def save(self, birth: Birth) -> tuple[Settings, str]:
        """Keeps a birth in the reader's library: the settings after, and its id."""
        settings, chart_id = self.store.save_chart(self.user.id, birth, self.read())
        assert settings is not None
        return settings, chart_id

    def test_an_account_starts_with_none(self) -> None:
        self.assertIsNone(self.store.settings(self.user.id))
        self.assertIsNone(self.store.account_data(self.user.id)['settings'])

    def test_each_setting_is_kept(self) -> None:
        _, chart_id = self.save(PARTNER)
        self.store.put_place(self.user.id, LISBON, self.read())
        kept = self.store.set_schools(self.user.id, {'season': 'months'}, self.read())
        expected = Settings(
            charts=(SavedChart(chart_id, PARTNER),),
            my_chart=None,
            couples=(),
            pending_partner=None,
            place=LISBON,
            schools=replace(NO_CHOICE, season='months'),
            updated_at='2026-10-07T12:00:02Z',
        )
        self.assertEqual(kept, expected)
        self.assertEqual(self.store.settings(self.user.id), expected)
        self.assertEqual(
            self.store.account_data(self.user.id)['settings'],
            settings_value(expected),
        )

    def test_the_library_keeps_charts_in_the_order_saved(self) -> None:
        _, mine = self.save(BIRTH)
        _, partner = self.save(PARTNER)
        _, again = self.save(born(2))
        self.assertEqual(len({mine, partner, again}), 3)
        renamed = replace(PARTNER, name='Renamed')
        self.store.set_my_chart(self.user.id, mine, self.read())
        self.store.add_couple(self.user.id, (mine, partner), self.read())
        kept = self.store.update_chart(self.user.id, partner, renamed, self.read())
        assert kept is not None
        # A changed chart keeps its id, its place, its mark and its couple.
        self.assertEqual(
            kept.charts,
            (
                SavedChart(mine, BIRTH),
                SavedChart(partner, renamed),
                SavedChart(again, born(2)),
            ),
        )
        self.assertEqual(kept.my_chart, mine)
        couple = kept.couple_between(mine, partner)
        assert couple is not None
        self.assertEqual(couple.charts, (mine, partner))

    def test_a_birth_is_saved_once(self) -> None:
        # The chart on screen is matched to the library by its birth, so a birth that
        # charts the same is one saved chart, whatever its name or place label.
        _, mine = self.save(BIRTH)
        _, partner = self.save(PARTNER)
        self.store.mark_backed_up(self.store.backup_snapshot().through_seq)
        before = self.store.settings(self.user.id)
        same = replace(
            BIRTH,
            name='Again',
            time='08:30:00',
            place=replace(HELSINKI, name='Helsingfors', city='Helsingfors'),
        )
        for change in (
            lambda: self.store.save_chart(self.user.id, same, self.read()),
            lambda: self.store.update_chart(self.user.id, partner, same, self.read()),
        ):
            with self.assertRaises(DuplicateChart):
                change()
        self.assertEqual(self.store.settings(self.user.id), before)
        self.assertEqual(self.store.backup_snapshot().changes, ())
        # A chart corrected to its own birth again is no duplicate of itself.
        self.assertEqual(
            self.store.update_chart(self.user.id, mine, BIRTH, self.read()), before
        )
        # Another Zi-hour convention, gender or pass charts differently.
        for other in (
            replace(BIRTH, zi='whole_zi_23'),
            replace(BIRTH, gender='male'),
            replace(BIRTH, fold=1, date='2021-10-31', time='03:30'),
        ):
            with self.subTest(other=other):
                self.save(other)

    def test_a_new_chart_can_be_mine_or_paired_in_the_same_write(self) -> None:
        _, partner = self.save(PARTNER)
        self.store.mark_backed_up(self.store.backup_snapshot().through_seq)
        kept, mine = self.store.save_chart(
            self.user.id, BIRTH, self.read(), mine=True, couple_with=partner
        )
        assert kept is not None
        self.assertEqual(kept.my_chart, mine)
        (couple,) = kept.couples
        self.assertEqual(couple.charts, (partner, mine))
        # One write: one change for the backup.
        self.assertEqual(len(self.store.backup_snapshot().changes), 1)
        # A pairing that cannot be made saves nothing either.
        before = self.store.settings(self.user.id)
        with self.assertRaises(UnknownChart):
            self.store.save_chart(
                self.user.id, born(3), self.read(), couple_with='4' * 32
            )
        self.assertEqual(self.store.settings(self.user.id), before)

    def test_a_new_chart_marked_mine_pairs_with_a_partner_kept_before_charts(
        self,
    ) -> None:
        self._keep_as_before_charts(PARTNER_SETTINGS['partner'])
        waiting = partner_chart_id(PARTNER_SETTINGS['partner'])
        kept, mine = self.store.save_chart(self.user.id, BIRTH, self.read(), mine=True)
        assert kept is not None
        (couple,) = kept.couples
        self.assertEqual(couple.charts, (mine, waiting))
        self.assertIsNone(kept.pending_partner)

    def test_a_rename_keeps_the_birth_and_charts_nothing(self) -> None:
        # Kept with a time the clocks skip (as a time zone update can leave one), the
        # chart can still be renamed: a rename does not chart the birth again.
        skipped = replace(PARTNER, date='2021-03-28', time='03:30', place=HELSINKI)
        _, chart_id = self.save(skipped)
        renamed = self.store.rename_chart(
            self.user.id, chart_id, 'Renamed', self.read()
        )
        assert renamed is not None
        self.assertEqual(
            renamed.charts, (SavedChart(chart_id, replace(skipped, name='Renamed')),)
        )
        unnamed = self.store.rename_chart(self.user.id, chart_id, None, self.read())
        assert unnamed is not None
        self.assertIsNone(unnamed.charts[0].birth.name)
        with self.assertRaises(UnknownChart):
            self.store.rename_chart(self.user.id, '4' * 32, 'Nobody', self.read())

    def test_a_removed_chart_leaves_its_couple_and_its_mark(self) -> None:
        _, mine = self.save(BIRTH)
        _, partner = self.save(PARTNER)
        self.store.set_my_chart(self.user.id, mine, self.read())
        self.store.add_couple(self.user.id, (mine, partner), self.read())
        kept = self.store.delete_chart(self.user.id, partner, self.read())
        assert kept is not None
        self.assertEqual(kept.charts, (SavedChart(mine, BIRTH),))
        self.assertEqual((kept.my_chart, kept.couples), (mine, ()))
        gone = self.store.delete_chart(self.user.id, mine, self.read())
        assert gone is not None
        self.assertEqual((gone.charts, gone.my_chart), ((), None))

    def test_my_chart_is_marked_and_cleared(self) -> None:
        _, mine = self.save(BIRTH)
        marked = self.store.set_my_chart(self.user.id, mine, self.read())
        assert marked is not None
        self.assertEqual(marked.my_chart, mine)
        cleared = self.store.clear_my_chart(self.user.id, self.read())
        assert cleared is not None
        self.assertIsNone(cleared.my_chart)
        # The chart stays in the library.
        self.assertEqual(cleared.charts, (SavedChart(mine, BIRTH),))

    def test_a_couple_is_parted_and_both_charts_stay(self) -> None:
        _, mine = self.save(BIRTH)
        _, partner = self.save(PARTNER)
        paired = self.store.add_couple(self.user.id, (partner, mine), self.read())
        assert paired is not None
        (couple,) = paired.couples
        # The couple keeps the order it was formed in.
        self.assertEqual(couple.charts, (partner, mine))
        parted = self.store.delete_couple(self.user.id, couple.id, self.read())
        assert parted is not None
        self.assertEqual(parted.couples, ())
        self.assertEqual(len(parted.charts), 2)

    def test_a_chart_can_be_in_any_number_of_couples(self) -> None:
        _, first = self.save(BIRTH)
        _, second = self.save(PARTNER)
        _, third = self.save(born(5))
        _, fourth = self.save(born(6))
        for charts in (
            (first, second),
            (third, first),
            (first, fourth),
            (second, third),
        ):
            self.store.add_couple(self.user.id, charts, self.read())
        kept = self.store.settings(self.user.id)
        assert kept is not None
        self.assertEqual(
            [couple.charts for couple in kept.couples_of(first)],
            [(first, second), (third, first), (first, fourth)],
        )
        # A chart saved as a partner of one in couples pairs with it too.
        saved, fifth = self.store.save_chart(
            self.user.id, born(7), self.read(), couple_with=first
        )
        assert saved is not None
        self.assertEqual(
            [couple.charts for couple in saved.couples_of(fifth)], [(first, fifth)]
        )
        self.assertEqual(len(saved.couples_of(first)), 4)
        # Ending one couple ends it alone; removing a chart ends each of its own and
        # keeps the others.
        parted = self.store.delete_couple(
            self.user.id, saved.couples[0].id, self.read()
        )
        assert parted is not None
        self.assertEqual(len(parted.couples_of(first)), 3)
        self.assertEqual(len(parted.couples), 4)
        removed = self.store.delete_chart(self.user.id, first, self.read())
        assert removed is not None
        self.assertEqual(
            [couple.charts for couple in removed.couples], [(second, third)]
        )

    def test_the_same_two_charts_are_one_couple(self) -> None:
        _, first = self.save(BIRTH)
        _, second = self.save(PARTNER)
        self.store.add_couple(self.user.id, (first, second), self.read())
        self.store.mark_backed_up(self.store.backup_snapshot().through_seq)
        before = self.store.settings(self.user.id)
        for charts in ((first, second), (second, first)):
            with self.subTest(charts=charts):
                with self.assertRaises(DuplicateCouple) as refused:
                    self.store.add_couple(self.user.id, charts, self.read())
                self.assertEqual(
                    str(refused.exception), 'These two charts are a couple already.'
                )
        self.assertEqual(self.store.settings(self.user.id), before)
        self.assertEqual(self.store.backup_snapshot().changes, ())

    def capped(self, cap: int) -> AccountStore:
        """The reader's database, as a store whose basic plan keeps `cap` couples per
        chart, as a plan may once plans are sold."""
        return AccountStore.open(
            self.path,
            clock=self.clock,
            limits={**LIMITS, 'basic': PlanLimits(couples_per_chart=cap)},
        )

    def assertRefused(
        self, store: AccountStore, change: Any, kind: type[Exception], detail: str
    ) -> None:
        """The change is refused as `kind`, saying `detail`, and changes nothing: not
        the settings, nor what the backup has to write."""
        before = store.settings(self.user.id)
        changes = store.backup_snapshot().changes
        with self.assertRaises(kind) as refused:
            change()
        self.assertEqual(str(refused.exception), detail)
        self.assertEqual(store.settings(self.user.id), before)
        self.assertEqual(store.backup_snapshot().changes, changes)

    def test_a_plan_that_caps_couples_refuses_one_more_by_name(self) -> None:
        capped = self.capped(1)
        _, first = self.save(BIRTH)
        _, second = self.save(PARTNER)
        _, third = self.save(born(5))
        _, fourth = self.save(born(6))
        capped.set_plan(self.user.id, 'basic')
        capped.add_couple(self.user.id, (first, second), self.read())
        capped.mark_backed_up(capped.backup_snapshot().through_seq)
        unnamed = 'An unnamed chart is in as many couples as the plan allows (1).'
        named = 'Partner is in as many couples as the plan allows (1).'
        for name, change, detail in (
            (
                'a chart at the cap, second',
                lambda: capped.add_couple(self.user.id, (third, first), self.read()),
                unnamed,
            ),
            (
                'a chart at the cap, first',
                lambda: capped.add_couple(self.user.id, (first, third), self.read()),
                unnamed,
            ),
            (
                'its partner, paired again',
                lambda: capped.add_couple(self.user.id, (fourth, second), self.read()),
                named,
            ),
            (
                'a new chart saved as its partner',
                lambda: capped.save_chart(
                    self.user.id, born(7), self.read(), couple_with=first
                ),
                unnamed,
            ),
        ):
            with self.subTest(name):
                self.assertRefused(capped, change, CoupleLimit, detail)
        # A chart the account does not keep is said first, on either side.
        for charts in ((first, '4' * 32), ('4' * 32, first)):
            with self.subTest(charts=charts):
                self.assertRefused(
                    capped,
                    lambda charts=charts: capped.add_couple(
                        self.user.id, charts, self.read()
                    ),
                    UnknownChart,
                    'The account keeps no chart with that id.',
                )
        # The same two charts are a couple already, whatever the cap.
        self.assertRefused(
            capped,
            lambda: capped.add_couple(self.user.id, (second, first), self.read()),
            DuplicateCouple,
            'These two charts are a couple already.',
        )
        # Two charts in no couple still pair, and on an unrestricted plan the same
        # chart pairs again.
        capped.add_couple(self.user.id, (third, fourth), self.read())
        capped.set_plan(self.user.id, 'free')
        kept = capped.add_couple(self.user.id, (first, third), self.read())
        assert kept is not None
        self.assertEqual(len(kept.couples_of(first)), 2)

    def test_a_cap_of_two_is_two(self) -> None:
        capped = self.capped(2)
        _, first = self.save(BIRTH)
        _, second = self.save(PARTNER)
        _, third = self.save(born(5))
        _, fourth = self.save(born(6))
        capped.set_plan(self.user.id, 'basic')
        capped.add_couple(self.user.id, (first, second), self.read())
        capped.add_couple(self.user.id, (third, first), self.read())
        self.assertRefused(
            capped,
            lambda: capped.add_couple(self.user.id, (fourth, first), self.read()),
            CoupleLimit,
            'An unnamed chart is in as many couples as the plan allows (2).',
        )
        kept = capped.add_couple(self.user.id, (second, fourth), self.read())
        assert kept is not None
        self.assertEqual(len(kept.couples_of(second)), 2)

    def test_an_account_over_its_plan_keeps_everything_and_pairs_within_it(
        self,
    ) -> None:
        _, first = self.save(BIRTH)
        _, second = self.save(PARTNER)
        _, third = self.save(born(5))
        _, fourth = self.save(born(6))
        _, fifth = self.save(born(7))
        self.store.add_couple(self.user.id, (first, second), self.read())
        held = self.store.add_couple(self.user.id, (first, third), self.read())
        assert held is not None
        # Moved to a plan that keeps one couple per chart: everything stays, read as
        # it was, exported as it was.
        capped = self.capped(1)
        capped.set_plan(self.user.id, 'basic')
        self.assertEqual(capped.settings(self.user.id), held)
        self.assertEqual(
            capped.account_data(self.user.id)['settings'], settings_value(held)
        )
        # A new couple for a chart at or over the cap is refused by name; two charts
        # under it still pair.
        self.assertRefused(
            capped,
            lambda: capped.add_couple(self.user.id, (first, fourth), self.read()),
            CoupleLimit,
            'An unnamed chart is in as many couples as the plan allows (1).',
        )
        self.assertRefused(
            capped,
            lambda: capped.add_couple(self.user.id, (fourth, second), self.read()),
            CoupleLimit,
            'Partner is in as many couples as the plan allows (1).',
        )
        capped.add_couple(self.user.id, (fourth, fifth), self.read())
        # Ending a couple always works; under the cap again, the chart pairs.
        for couple in held.couples_of(first):
            parted = capped.delete_couple(self.user.id, couple.id, self.read())
            assert parted is not None
        kept = capped.add_couple(self.user.id, (first, third), self.read())
        assert kept is not None
        self.assertEqual(
            [couple.charts for couple in kept.couples_of(first)], [(first, third)]
        )

    def test_a_chart_in_several_couples_is_read_exported_and_kept(self) -> None:
        several = self.keep_several_couples()
        self.assertEqual(self.store.settings(self.user.id), several)
        self.assertEqual(
            self.store.account_data(self.user.id)['settings'], settings_value(several)
        )
        # A change to something else keeps every couple.
        changed = self.store.put_place(self.user.id, LISBON, self.read())
        assert changed is not None
        self.assertEqual(changed.couples, several.couples)
        # And a chart in a couple pairs with another.
        partner, third = several.charts[1].id, several.charts[2].id
        paired = self.store.add_couple(self.user.id, (partner, third), self.read())
        assert paired is not None
        self.assertEqual(paired.couples[:2], several.couples)
        self.assertEqual(paired.couples[2].charts, (partner, third))

    def test_an_id_the_account_does_not_keep_changes_nothing(self) -> None:
        _, mine = self.save(BIRTH)
        self.store.mark_backed_up(self.store.backup_snapshot().through_seq)
        before = self.store.settings(self.user.id)
        unknown = '4' * 32
        for name, change in {
            'change': lambda: self.store.update_chart(
                self.user.id, unknown, PARTNER, self.read()
            ),
            'remove': lambda: self.store.delete_chart(
                self.user.id, unknown, self.read()
            ),
            'mark': lambda: self.store.set_my_chart(self.user.id, unknown, self.read()),
            'pair': lambda: self.store.add_couple(
                self.user.id, (mine, unknown), self.read()
            ),
        }.items():
            with self.subTest(name), self.assertRaises(UnknownChart):
                change()
        with self.assertRaises(UnknownCouple):
            self.store.delete_couple(self.user.id, unknown, self.read())
        self.assertEqual(self.store.settings(self.user.id), before)
        self.assertEqual(self.store.backup_snapshot().changes, ())

    def test_the_library_holds_a_limited_number_of_charts(self) -> None:
        for number in range(CHART_LIMIT):
            self.save(born(number))
        before = self.store.settings(self.user.id)
        with self.assertRaises(ChartLimit):
            self.store.save_chart(self.user.id, BIRTH, self.read())
        self.assertEqual(self.store.settings(self.user.id), before)

    def _keep_as_before_charts(self, partner: dict[str, Any] | None) -> None:
        """Gives the reader settings as an account kept them before it kept charts."""
        self.store.put_place(self.user.id, LISBON, None)
        connection = sqlite3.connect(self.path)
        try:
            connection.execute(
                'UPDATE settings SET record = ? WHERE user_id = ?',
                (
                    canonical_json({**PARTNER_SETTINGS, 'partner': partner}),
                    self.user.id,
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def test_a_partner_kept_before_charts_pairs_with_my_chart(self) -> None:
        self._keep_as_before_charts(PARTNER_SETTINGS['partner'])
        kept = self.store.settings(self.user.id)
        assert kept is not None
        waiting = partner_chart_id(PARTNER_SETTINGS['partner'])
        self.assertEqual(kept.charts, (SavedChart(waiting, PARTNER),))
        self.assertEqual(kept.pending_partner, waiting)
        # Read again, the partner keeps its id: the page names it by that id.
        self.assertEqual(self.store.settings(self.user.id), kept)
        _, mine = self.save(BIRTH)
        marked = self.store.set_my_chart(self.user.id, mine, self.read())
        assert marked is not None
        (couple,) = marked.couples
        self.assertEqual(couple.charts, (mine, waiting))
        self.assertIsNone(marked.pending_partner)
        # Written back in today's shape.
        connection = sqlite3.connect(self.path)
        try:
            (record,) = connection.execute(
                'SELECT record FROM settings WHERE user_id = ?', (self.user.id,)
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(record, encode_settings(marked))

    def test_a_partner_kept_before_charts_pairs_with_my_chart_in_other_couples(
        self,
    ) -> None:
        self._keep_as_before_charts(PARTNER_SETTINGS['partner'])
        waiting = partner_chart_id(PARTNER_SETTINGS['partner'])
        _, mine = self.save(BIRTH)
        _, other = self.save(born(5))
        self.store.add_couple(self.user.id, (other, mine), self.read())
        marked = self.store.set_my_chart(self.user.id, mine, self.read())
        assert marked is not None
        self.assertEqual(
            [couple.charts for couple in marked.couples],
            [(other, mine), (mine, waiting)],
        )
        self.assertIsNone(marked.pending_partner)

    def test_a_partner_kept_before_charts_waits_no_longer_past_the_cap(self) -> None:
        capped = self.capped(1)
        self._keep_as_before_charts(PARTNER_SETTINGS['partner'])
        waiting = partner_chart_id(PARTNER_SETTINGS['partner'])
        _, mine = self.save(BIRTH)
        _, other = self.save(born(5))
        capped.set_plan(self.user.id, 'basic')
        capped.add_couple(self.user.id, (mine, other), self.read())
        # My chart is in as many couples as the plan allows: it is marked all the
        # same, and the partner kept from before stays saved, unpaired, and waits no
        # longer.
        kept = capped.set_my_chart(self.user.id, mine, self.read())
        assert kept is not None
        self.assertEqual(kept.my_chart, mine)
        self.assertIsNone(kept.pending_partner)
        self.assertIsNotNone(kept.chart(waiting))
        self.assertEqual([couple.charts for couple in kept.couples], [(mine, other)])

    def test_mine_and_a_partner_in_one_write_pair_with_both(self) -> None:
        self._keep_as_before_charts(PARTNER_SETTINGS['partner'])
        waiting = partner_chart_id(PARTNER_SETTINGS['partner'])
        _, other = self.save(born(5))
        kept, mine = self.store.save_chart(
            self.user.id, BIRTH, self.read(), mine=True, couple_with=other
        )
        assert kept is not None
        self.assertEqual(
            [couple.charts for couple in kept.couples],
            [(other, mine), (mine, waiting)],
        )
        self.assertIsNone(kept.pending_partner)

    def test_mine_and_a_partner_in_one_write_within_a_cap(self) -> None:
        capped = self.capped(1)
        self._keep_as_before_charts(PARTNER_SETTINGS['partner'])
        waiting = partner_chart_id(PARTNER_SETTINGS['partner'])
        _, other = self.save(born(5))
        _, taken = self.save(born(6))
        _, third = self.save(born(7))
        capped.set_plan(self.user.id, 'basic')
        capped.add_couple(self.user.id, (taken, third), self.read())
        # A partner at the cap refuses the whole write: nothing is saved, and the
        # partner kept from before still waits.
        self.assertRefused(
            capped,
            lambda: capped.save_chart(
                self.user.id, BIRTH, self.read(), mine=True, couple_with=taken
            ),
            CoupleLimit,
            'An unnamed chart is in as many couples as the plan allows (1).',
        )
        # Paired with a partner under the cap, the new chart is then at it: it is
        # marked, and the partner kept from before stays saved and waits no longer.
        kept, mine = capped.save_chart(
            self.user.id, BIRTH, self.read(), mine=True, couple_with=other
        )
        assert kept is not None
        self.assertEqual(kept.my_chart, mine)
        self.assertEqual(
            [couple.charts for couple in kept.couples], [(taken, third), (other, mine)]
        )
        self.assertIsNone(kept.pending_partner)
        self.assertIsNotNone(kept.chart(waiting))

    def test_a_waiting_partner_marked_as_my_chart_pairs_with_nothing(self) -> None:
        self._keep_as_before_charts(PARTNER_SETTINGS['partner'])
        waiting = partner_chart_id(PARTNER_SETTINGS['partner'])
        marked = self.store.set_my_chart(self.user.id, waiting, self.read())
        assert marked is not None
        self.assertEqual((marked.my_chart, marked.couples), (waiting, ()))
        self.assertIsNone(marked.pending_partner)

    def test_a_waiting_partner_already_in_a_couple_is_left_there(self) -> None:
        self._keep_as_before_charts(PARTNER_SETTINGS['partner'])
        waiting = partner_chart_id(PARTNER_SETTINGS['partner'])
        _, other = self.save(born(4))
        _, mine = self.save(BIRTH)
        paired = self.store.add_couple(self.user.id, (other, waiting), self.read())
        assert paired is not None
        # Paired by hand, the partner waits no longer.
        self.assertIsNone(paired.pending_partner)
        marked = self.store.set_my_chart(self.user.id, mine, self.read())
        assert marked is not None
        (couple,) = marked.couples
        self.assertEqual(couple.charts, (other, waiting))
        self.assertIsNone(marked.pending_partner)

    def test_an_account_with_no_partner_before_charts_keeps_an_empty_library(
        self,
    ) -> None:
        self._keep_as_before_charts(None)
        kept = self.store.settings(self.user.id)
        assert kept is not None
        self.assertEqual((kept.charts, kept.pending_partner), ((), None))
        self.assertEqual(kept.schools, replace(NO_CHOICE, season='months'))

    def test_a_choice_of_one_school_keeps_the_others(self) -> None:
        self.store.set_schools(
            self.user.id, {'favourable': 'climate', 'transits': 'whole'}, self.read()
        )
        kept = self.store.set_schools(
            self.user.id, {'season': 'late_summer'}, self.read()
        )
        assert kept is not None
        self.assertEqual(
            kept.schools,
            ChosenSchools(favourable='climate', season='late_summer', transits='whole'),
        )
        # None follows the default again.
        again = self.store.set_schools(self.user.id, {'favourable': None}, self.read())
        assert again is not None
        self.assertIsNone(again.schools.favourable)
        self.assertEqual(again.schools.effective().favourable, 'support')
        for chosen in (
            {'weights': 'support'},
            {'season': 'modern'},
            {'favourable': ''},
        ):
            with self.subTest(chosen=chosen), self.assertRaises(RecordError):
                self.store.set_schools(self.user.id, chosen, self.read())
        self.assertEqual(self.store.settings(self.user.id), again)

    def test_each_change_is_logged_for_the_backup_and_moves_its_time_on(self) -> None:
        self.store.mark_backed_up(self.store.backup_snapshot().through_seq)
        first, _ = self.save(BIRTH)
        second = self.store.put_place(self.user.id, HELSINKI, self.read())
        assert second is not None
        # Within one second, or with the clock gone back, a change still comes later.
        self.assertEqual(first.updated_at, '2026-10-07T12:00:00Z')
        self.assertEqual(second.updated_at, '2026-10-07T12:00:01Z')
        snapshot = self.store.backup_snapshot()
        self.assertEqual(len(snapshot.changes), 1)
        self.assertEqual(snapshot.changes[0].user, self.user)
        self.assertEqual(snapshot.changes[0].settings, second)

    def test_a_change_that_changes_nothing_writes_nothing(self) -> None:
        _, mine = self.save(BIRTH)
        self.store.set_my_chart(self.user.id, mine, self.read())
        self.store.mark_backed_up(self.store.backup_snapshot().through_seq)
        self.clock.advance(60)
        before = self.store.settings(self.user.id)
        assert before is not None
        for change in (
            lambda: self.store.update_chart(self.user.id, mine, BIRTH, self.read()),
            lambda: self.store.set_my_chart(self.user.id, mine, self.read()),
        ):
            self.assertEqual(change(), before)
        self.assertEqual(self.store.backup_snapshot().changes, ())
        # An account that keeps no settings keeps none after clearing no chart of its
        # own, removing no place, or choosing the default schools.
        other = self.store.create_user('other@example.com', 'en')
        self.store.mark_backed_up(self.store.backup_snapshot().through_seq)
        self.assertIsNone(self.store.clear_my_chart(other.id, None))
        self.assertIsNone(self.store.delete_place(other.id, None))
        self.assertIsNone(self.store.set_schools(other.id, {'favourable': None}, None))
        self.assertIsNone(self.store.settings(other.id))
        self.assertEqual(self.store.backup_snapshot().changes, ())

    def test_a_change_from_settings_changed_since_changes_nothing(self) -> None:
        # Two tabs read the same settings; the second to save made its change from
        # settings that are no longer the account's.
        first = self.store.put_place(self.user.id, HELSINKI, None)
        assert first is not None
        later = self.store.put_place(self.user.id, LISBON, first.updated_at)
        self.store.mark_backed_up(self.store.backup_snapshot().through_seq)
        for change in (
            lambda: self.store.save_chart(self.user.id, PARTNER, first.updated_at),
            lambda: self.store.clear_my_chart(self.user.id, first.updated_at),
            lambda: self.store.delete_place(self.user.id, first.updated_at),
            lambda: self.store.set_schools(
                self.user.id, {'season': 'months'}, first.updated_at
            ),
            lambda: self.store.put_place(self.user.id, HELSINKI, None),
        ):
            with self.assertRaises(SettingsChanged):
                change()
        self.assertEqual(self.store.settings(self.user.id), later)
        self.assertEqual(self.store.backup_snapshot().changes, ())

    def test_the_place_is_forgotten(self) -> None:
        self.store.put_place(self.user.id, HELSINKI, self.read())
        kept = self.store.delete_place(self.user.id, self.read())
        assert kept is not None
        self.assertIsNone(kept.place)
        self.assertEqual(self.store.settings(self.user.id), kept)

    def test_settings_go_with_the_account(self) -> None:
        self.save(BIRTH)
        self.store.delete_user(self.user.id)
        connection = sqlite3.connect(self.path)
        try:
            rows = connection.execute('SELECT COUNT(*) FROM settings').fetchone()
        finally:
            connection.close()
        self.assertEqual(rows, (0,))
        with self.assertRaises(UnknownUser):
            self.store.put_place(self.user.id, HELSINKI, self.read())

    def test_a_restore_holds_each_account_with_its_settings(self) -> None:
        self.save(BIRTH)
        other = self.store.create_user('other@example.com', 'en')
        settings = self.store.settings(self.user.id)
        target = self.directory / 'restored.sqlite3'
        restored = AccountStore.restore(
            target, [(self.user, settings), (other, None)], head='0' * 40
        )
        self.assertEqual(restored.settings(self.user.id), settings)
        self.assertIsNone(restored.settings(other.id))
        self.assertEqual(restored.backup_snapshot().changes, ())

    def test_a_database_from_before_settings_gains_them(self) -> None:
        older = self.directory / 'older.sqlite3'
        with (
            patch.object(store_module, 'MIGRATIONS', store_module.MIGRATIONS[:3]),
            patch.object(store_module, 'SCHEMA_VERSION', 3),
        ):
            AccountStore.create(older).create_user('kept@example.com', 'fi')
        store = AccountStore.open(older)
        kept = store.user_by_email('kept@example.com')
        assert kept is not None
        self.assertIsNone(store.settings(kept.id))
        self.assertIsNotNone(store.save_chart(kept.id, BIRTH, None)[0])

    def test_a_corrupt_settings_row_stops_the_store(self) -> None:
        self.save(BIRTH)
        connection = sqlite3.connect(self.path)
        try:
            connection.execute(
                'UPDATE settings SET record = ?', (b'{"partner": null}\n',)
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(store_module.StoreError):
            self.store.settings(self.user.id)


class TestSettingsBackup(StoreCase):
    def setUp(self) -> None:
        super().setUp()
        self.identity = pyrage.x25519.Identity.generate()
        self.recipient = self.identity.to_public()
        _remote, self.checkout = make_remote_and_checkout(self.directory)

    def _path(self, user_id: str) -> Path:
        return self.checkout / 'users' / user_id[:2] / user_id / 'user.json.age'

    def _record(self, user_id: str) -> bytes:
        return pyrage.decrypt(self._path(user_id).read_bytes(), [self.identity])

    def test_unlimited_writes_survive_a_lower_allowance_and_encrypted_restore(self) -> None:
        unlimited = AccountStore.open(
            self.path, clock=self.clock, limits={**LIMITS, 'free': PlanLimits(None, None)},
        )
        for number in range(52):
            unlimited.save_chart(self.user.id, born(number), self.read())
        settings = unlimited.settings(self.user.id)
        assert settings is not None
        settings = unlimited.add_couple(
            self.user.id, (settings.charts[0].id, settings.charts[-1].id), self.read()
        )
        run_backup(unlimited, self.checkout, self.recipient)
        target = self.directory / 'restored.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        low = AccountStore.open(
            target, clock=self.clock, limits={**LIMITS, 'free': PlanLimits(None, 1)},
        )
        self.assertEqual(low.settings(self.user.id), settings)
        self.assertEqual(low.account_data(self.user.id)['settings'], settings_value(settings))
        before = low.backup_snapshot()
        with self.assertRaises(ChartLimit):
            low.save_chart(self.user.id, born(60), settings.updated_at)
        self.assertEqual(low.backup_snapshot(), before)
        moved = low.put_place(self.user.id, HELSINKI, settings.updated_at)
        assert moved is not None
        self.assertEqual((moved.charts, moved.couples), (settings.charts, settings.couples))
        self.assertEqual(run_backup(low, self.checkout, self.recipient).written, 1)
        self.assertEqual(decode_user(self._record(self.user.id)), (self.user, moved))

    def test_a_retained_library_survives_encrypted_backup_and_restore(self) -> None:
        settings = keep_large_library(self.store, self.user)
        self.assertEqual(
            run_backup(self.store, self.checkout, self.recipient).written, 1
        )
        self.assertEqual(decode_user(self._record(self.user.id)), (self.user, settings))
        target = self.directory / 'restored.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        restored = AccountStore.open(target)
        self.assertEqual(restored.user_by_id(self.user.id), self.user)
        self.assertEqual(restored.settings(self.user.id), settings)
        self.assertEqual(
            restored.account_data(self.user.id)['settings'], settings_value(settings)
        )
        with self.assertRaises(ChartLimit):
            restored.save_chart(self.user.id, born(60), settings.updated_at)
        moved = restored.put_place(self.user.id, HELSINKI, settings.updated_at)
        assert moved is not None
        self.assertEqual(
            (moved.charts, moved.couples), (settings.charts, settings.couples)
        )
        self.assertEqual(run_backup(restored, self.checkout, self.recipient).written, 1)
        self.assertEqual(decode_user(self._record(self.user.id)), (self.user, moved))

    def test_the_backup_keeps_the_settings_in_the_account_record(self) -> None:
        settings, chart_id = self.store.save_chart(self.user.id, BIRTH, self.read())
        run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual(self._record(self.user.id), encode_user(self.user, settings))
        changed = self.store.update_chart(self.user.id, chart_id, PARTNER, self.read())
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual(result.written, 1)
        self.assertEqual(decode_user(self._record(self.user.id)), (self.user, changed))

    def test_a_restore_brings_the_settings_back(self) -> None:
        _, mine = self.store.save_chart(self.user.id, BIRTH, self.read())
        run_backup(self.store, self.checkout, self.recipient)
        # A change to the settings alone, after a backup, reaches the next one.
        self.store.put_place(self.user.id, LISBON, self.read())
        self.store.set_schools(self.user.id, {'season': 'commander'}, self.read())
        _, partner = self.store.save_chart(self.user.id, PARTNER, self.read())
        self.store.set_my_chart(self.user.id, mine, self.read())
        settings = self.store.add_couple(self.user.id, (mine, partner), self.read())
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual(result.written, 1)
        target = self.directory / 'restored.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        self.assertEqual(AccountStore.open(target).settings(self.user.id), settings)

    def test_a_chart_in_several_couples_backs_up_and_restores(self) -> None:
        several = self.keep_several_couples()
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual(result.written, 1)
        self.assertEqual(decode_user(self._record(self.user.id)), (self.user, several))
        target = self.directory / 'restored.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        restored = AccountStore.open(target)
        self.assertEqual(restored.settings(self.user.id), several)
        # And the restored database goes on with the same backup: once the account
        # changes, its next run writes it with every couple kept.
        moved = restored.put_place(self.user.id, LISBON, several.updated_at)
        assert moved is not None
        self.assertEqual(moved.couples, several.couples)
        self.assertEqual(run_backup(restored, self.checkout, self.recipient).written, 1)
        self.assertEqual(decode_user(self._record(self.user.id)), (self.user, moved))

    def test_a_backup_from_before_charts_restores_its_partner_as_a_saved_chart(
        self,
    ) -> None:
        run_backup(self.store, self.checkout, self.recipient)
        old = canonical_json(
            {
                'created_at': self.user.created_at,
                'email': self.user.email,
                'id': self.user.id,
                'kind': 'user',
                'language': self.user.language,
                'plan': self.user.plan,
                'schema': 2,
                'settings': PARTNER_SETTINGS,
                'updated_at': self.user.updated_at,
            }
        )
        self._path(self.user.id).write_bytes(pyrage.encrypt(old, [self.recipient]))
        git(self.checkout, 'commit', '--quiet', '-am', 'a backup from before charts')
        target = self.directory / 'restored.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        restored = AccountStore.open(target).settings(self.user.id)
        assert restored is not None
        waiting = partner_chart_id(PARTNER_SETTINGS['partner'])
        self.assertEqual(restored.charts, (SavedChart(waiting, PARTNER),))
        self.assertEqual(restored.pending_partner, waiting)

    def test_a_backup_of_schema_1_records_still_restores(self) -> None:
        run_backup(self.store, self.checkout, self.recipient)
        old = canonical_json(
            {
                'created_at': self.user.created_at,
                'email': self.user.email,
                'id': self.user.id,
                'kind': 'user',
                'language': self.user.language,
                'plan': self.user.plan,
                'schema': 1,
                'updated_at': self.user.updated_at,
            }
        )
        self._path(self.user.id).write_bytes(pyrage.encrypt(old, [self.recipient]))
        git(self.checkout, 'commit', '--quiet', '-am', 'a backup from before settings')
        target = self.directory / 'restored.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        restored = AccountStore.open(target)
        self.assertEqual(restored.users(), [self.user])
        self.assertIsNone(restored.settings(self.user.id))


class TestSettingsApi(unittest.TestCase):
    accounts: ClassVar[Accounts]

    @classmethod
    def setUpClass(cls) -> None:
        # Each test signs in a different account through this one test client.
        # Sign-in rate limits have their own suite; do not share its hourly budget.
        cls.accounts = install_accounts(cls, EC_CODE_REQUESTS_PER_HOUR_PER_CLIENT='100')

    def setUp(self) -> None:
        self.client = site_client()
        email = f'reader{self.id().rsplit(".", 1)[-1][-40:]}@example.com'
        sign_in(self.client, self.accounts, email)
        user = self.accounts.store.user_by_email(email)
        assert user is not None
        self.user = user
        self.key = account_key(user)

    def read(self) -> str | None:
        """The version of the settings the page has read."""
        return self.client.get('/api/account/settings').json()['updated_at']

    def write(self, method: str, path: str, body: dict[str, Any]) -> Any:
        """A change made from the settings as they are now."""
        return self.client.request(
            method, path, json={**body, 'updated_at': self.read()}
        )

    def save(self, birth: Birth) -> str:
        """Keeps a birth in the library through the API; its id."""
        reply = self.write('POST', '/api/account/charts', _birth_json(birth, self.key))
        self.assertEqual(reply.status_code, 201, reply.text)
        return reply.json()['saved']

    def writes(self, chart: str, couple: str) -> list[tuple[str, str, dict[str, Any]]]:
        """Every write the settings API takes, naming a chart and a couple."""
        return [
            ('POST', '/api/account/charts', _birth_json(born(6), self.key)),
            ('PUT', f'/api/account/charts/{chart}', _birth_json(born(7), self.key)),
            (
                'PUT',
                f'/api/account/charts/{chart}/name',
                {'key': self.key, 'name': 'B'},
            ),
            ('PUT', '/api/account/my-chart', {'key': self.key, 'chart': chart}),
            ('DELETE', '/api/account/my-chart', {'key': self.key}),
            (
                'POST',
                '/api/account/couples',
                {'key': self.key, 'charts': [chart, '5' * 32]},
            ),
            ('DELETE', f'/api/account/couples/{couple}', {'key': self.key}),
            ('DELETE', f'/api/account/charts/{chart}', {'key': self.key}),
            (
                'PUT',
                '/api/account/place',
                {'key': self.key, 'place': _place_json(HELSINKI)},
            ),
            ('DELETE', '/api/account/place', {'key': self.key}),
            ('PATCH', '/api/account/schools', {'key': self.key, 'season': 'months'}),
        ]

    def test_settings_need_an_account(self) -> None:
        signed_out = site_client()
        self.assertEqual(signed_out.get('/api/account/settings').status_code, 401)
        for method, path, body in self.writes('4' * 32, '6' * 32):
            with self.subTest(method=method, path=path):
                reply = signed_out.request(
                    method, path, json={**body, 'updated_at': None}
                )
                self.assertEqual(reply.status_code, 401)

    def test_an_account_that_has_set_nothing_has_the_defaults(self) -> None:
        reply = self.client.get('/api/account/settings')
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(
            reply.json(),
            {
                'charts': [],
                'my_chart': None,
                'couples': [],
                'pending_partner': None,
                'chart_limit': CHART_LIMIT,
                'couples_per_chart': None,
                'place': None,
                'schools': {
                    'favourable': 'support',
                    'season': 'eighteen',
                    'transits': 'phases',
                },
                'chosen': {'favourable': None, 'season': None, 'transits': None},
                'updated_at': None,
                'key': self.key,
            },
        )

    def test_a_saved_chart_has_the_pillars_of_the_four_pillars(self) -> None:
        # 00:47 in Helsinki on 18 May 1990 is about 23:30 true solar time on the 17th.
        late = replace(BIRTH, date='1990-05-18', time='00:47', zi='whole_zi_23')
        for birth in (BIRTH, PARTNER, late):
            with self.subTest(birth=birth):
                chart_id = self.save(birth)
                charts = self.client.get('/api/account/settings').json()['charts']
                (chart,) = [chart for chart in charts if chart['id'] == chart_id]
                place = birth.place
                four = self.client.post(
                    '/api/four_pillars',
                    json={
                        'date': birth.date,
                        'time': birth.time,
                        'location': {
                            'timezone': place.timezone,
                            'latitude': place.latitude,
                            'longitude': place.longitude,
                        },
                        'conventions': {'zi_convention': birth.zi},
                    },
                ).json()['four_pillars']
                for pillar in ('year', 'month', 'day', 'hour'):
                    self.assertEqual(
                        [
                            chart['pillars'][pillar]['stem']['chinese'],
                            chart['pillars'][pillar]['branch']['chinese'],
                        ],
                        [
                            four[pillar]['stem']['chinese'],
                            four[pillar]['branch']['chinese'],
                        ],
                    )
                self.assertEqual(chart['date'], birth.date)
                self.assertEqual(chart['name'], birth.name)
                self.assertEqual(chart['zi'], birth.zi)
                self.assertEqual(chart['place']['name'], place.name)
        # The Zi-hour convention moves a birth late in the evening to the next day: the
        # same birth with the other convention is another chart.
        self.save(replace(late, zi='split_midnight'))
        charts = self.client.get('/api/account/settings').json()['charts']
        days = {
            chart['zi']: chart['pillars']['day']
            for chart in charts
            if chart['date'] == late.date
        }
        self.assertNotEqual(days['split_midnight'], days['whole_zi_23'])

    def test_a_birth_is_checked_by_the_first_charts_rules(self) -> None:
        body = _birth_json(BIRTH, self.key)
        cases: dict[str, dict[str, Any]] = {
            'no time': {k: v for k, v in body.items() if k != 'time'},
            'a time in another form': {**body, 'time': '8.30'},
            'a date that does not exist': {**body, 'date': '1990-02-30'},
            'a date out of range': {**body, 'date': '1948-06-01'},
            'an unknown field': {**body, 'hour': 8},
            'an unknown gender': {**body, 'gender': 'other'},
            'an unknown zone': {
                **body,
                'place': {**body['place'], 'timezone': 'Europe/Nowhere'},
            },
            'a place without its name': {
                **body,
                'place': {k: v for k, v in body['place'].items() if k != 'name'},
            },
            'a latitude off the globe': {
                **body,
                'place': {**body['place'], 'latitude': 91.0},
            },
            'a time the clocks skipped': {
                **body,
                'date': '2021-03-28',
                'time': '03:30',
            },
            'a time the clocks repeated, without its pass': {
                **body,
                'date': '2021-10-31',
                'time': '03:30',
            },
        }
        for name, case in cases.items():
            with self.subTest(name):
                reply = self.write('POST', '/api/account/charts', case)
                self.assertEqual(reply.status_code, 400, reply.text)
        self.assertIsNone(self.accounts.store.settings(self.user.id))
        chart_id = self.save(BIRTH)
        for name, case in cases.items():
            with self.subTest(f'changed to {name}'):
                reply = self.write('PUT', f'/api/account/charts/{chart_id}', case)
                self.assertEqual(reply.status_code, 400, reply.text)
        repeated = {**body, 'date': '2021-10-31', 'time': '03:30', 'fold': 1}
        reply = self.write('PUT', f'/api/account/charts/{chart_id}', repeated)
        self.assertEqual(reply.status_code, 200, reply.text)
        self.assertEqual(reply.json()['charts'][0]['fold'], 1)

    def test_a_saved_chart_that_no_longer_computes_shows_why(self) -> None:
        # As a time zone update can leave a saved time one the clocks skipped: the
        # settings still answer, and say what is wrong with that chart.
        skipped = replace(BIRTH, date='2021-03-28', time='03:30')
        self.accounts.store.save_chart(self.user.id, skipped, None)
        reply = self.client.get('/api/account/settings')
        self.assertEqual(reply.status_code, 200)
        (chart,) = reply.json()['charts']
        self.assertIsNone(chart['pillars'])
        self.assertIn('skipped', chart['problem'])

    def test_my_chart_and_a_couple_are_kept_by_their_ids(self) -> None:
        mine = self.save(BIRTH)
        partner = self.save(PARTNER)
        marked = self.write(
            'PUT', '/api/account/my-chart', {'key': self.key, 'chart': mine}
        )
        self.assertEqual(marked.status_code, 200, marked.text)
        self.assertEqual(marked.json()['my_chart'], mine)
        paired = self.write(
            'POST', '/api/account/couples', {'key': self.key, 'charts': [mine, partner]}
        )
        self.assertEqual(paired.status_code, 201, paired.text)
        (couple,) = paired.json()['couples']
        self.assertEqual(couple['charts'], [mine, partner])
        self.assertEqual(
            [chart['id'] for chart in paired.json()['charts']], [mine, partner]
        )
        parted = self.write(
            'DELETE', f'/api/account/couples/{couple["id"]}', {'key': self.key}
        )
        self.assertEqual(parted.json()['couples'], [])
        cleared = self.write('DELETE', '/api/account/my-chart', {'key': self.key})
        self.assertIsNone(cleared.json()['my_chart'])
        removed = self.write(
            'DELETE', f'/api/account/charts/{partner}', {'key': self.key}
        )
        self.assertEqual([chart['id'] for chart in removed.json()['charts']], [mine])

    def test_what_the_library_cannot_do_is_refused(self) -> None:
        first = self.save(BIRTH)
        second = self.save(PARTNER)
        third = self.save(born(5))
        self.write(
            'POST', '/api/account/couples', {'key': self.key, 'charts': [first, second]}
        )
        unknown = '4' * 32
        refused: list[tuple[int, str, str, dict[str, Any]]] = [
            (
                404,
                'PUT',
                f'/api/account/charts/{unknown}',
                _birth_json(BIRTH, self.key),
            ),
            (404, 'DELETE', f'/api/account/charts/{unknown}', {'key': self.key}),
            (404, 'PUT', '/api/account/my-chart', {'key': self.key, 'chart': unknown}),
            (
                404,
                'POST',
                '/api/account/couples',
                {'key': self.key, 'charts': [third, unknown]},
            ),
            (404, 'DELETE', f'/api/account/couples/{unknown}', {'key': self.key}),
            # The same two charts are one couple, in either order: refused with 400,
            # as a 409 says another account is signed in now.
            (
                400,
                'POST',
                '/api/account/couples',
                {'key': self.key, 'charts': [second, first]},
            ),
            (
                400,
                'POST',
                '/api/account/couples',
                {'key': self.key, 'charts': [first, second]},
            ),
            # A birth is saved once.
            (
                400,
                'POST',
                '/api/account/charts',
                _birth_json(replace(BIRTH, name='Again'), self.key),
            ),
            (
                400,
                'PUT',
                f'/api/account/charts/{third}',
                _birth_json(PARTNER, self.key),
            ),
            # Ids are 32 lowercase hex digits.
            (400, 'PUT', '/api/account/charts/x', _birth_json(born(9), self.key)),
            (400, 'DELETE', f'/api/account/charts/{third.upper()}', {'key': self.key}),
            (400, 'PUT', '/api/account/my-chart', {'key': self.key, 'chart': 'x'}),
            (
                400,
                'POST',
                '/api/account/couples',
                {'key': self.key, 'charts': [third, 'x']},
            ),
            (
                400,
                'POST',
                '/api/account/charts',
                {**_birth_json(born(9), self.key), 'couple_with': 'x'},
            ),
            # A name is one line of at most 80 characters.
            (
                400,
                'PUT',
                f'/api/account/charts/{third}/name',
                {'key': self.key, 'name': 'two\nlines'},
            ),
            (
                400,
                'PUT',
                f'/api/account/charts/{third}/name',
                {'key': self.key, 'name': 'x' * 81},
            ),
            (
                404,
                'PUT',
                f'/api/account/charts/{unknown}/name',
                {'key': self.key, 'name': 'A'},
            ),
            # A couple is two charts.
            (
                400,
                'POST',
                '/api/account/couples',
                {'key': self.key, 'charts': [third, third]},
            ),
            (400, 'POST', '/api/account/couples', {'key': self.key, 'charts': [third]}),
            (400, 'PUT', '/api/account/my-chart', {'key': self.key}),
        ]
        before = self.client.get('/api/account/settings').json()
        for status, method, path, body in refused:
            with self.subTest(method=method, path=path, body=body):
                reply = self.write(method, path, body)
                self.assertEqual(reply.status_code, status, reply.text)
        self.assertEqual(self.client.get('/api/account/settings').json(), before)

    def test_a_chart_pairs_with_any_number_of_charts(self) -> None:
        first = self.save(BIRTH)
        second = self.save(PARTNER)
        third = self.save(born(5))
        for charts in ([first, second], [third, first]):
            paired = self.write(
                'POST', '/api/account/couples', {'key': self.key, 'charts': charts}
            )
            self.assertEqual(paired.status_code, 201, paired.text)
        saved = self.write(
            'POST',
            '/api/account/charts',
            {**_birth_json(born(8), self.key), 'couple_with': first},
        )
        self.assertEqual(saved.status_code, 201, saved.text)
        self.assertEqual(
            [couple['charts'] for couple in saved.json()['couples']],
            [[first, second], [third, first], [first, saved.json()['saved']]],
        )
        # Download my data carries every couple; deleting the account removes them.
        exported = self.client.post('/api/account/export', json={'key': self.key})
        self.assertEqual(exported.status_code, 200, exported.text)
        self.assertEqual(
            exported.json()['settings']['couples'],
            [
                {'id': couple['id'], 'charts': couple['charts']}
                for couple in saved.json()['couples']
            ],
        )
        gone = self.client.request(
            'DELETE',
            '/api/account',
            json={'key': self.key, 'email': self.user.email},
        )
        self.assertEqual(gone.status_code, 204, gone.text)
        self.assertIsNone(self.accounts.store.settings(self.user.id))

    def capped(self) -> Accounts:
        """The services with a store whose basic plan keeps one couple per chart, in
        place of the app's own for this test; the reader's account is on that plan."""
        capped = replace(
            self.accounts,
            store=AccountStore.open(
                self.accounts.store.path,
                clock=self.accounts.clock,
                limits={**LIMITS, 'basic': PlanLimits(couples_per_chart=1)},
            ),
        )
        capped.store.set_plan(self.user.id, 'basic')
        app.dependency_overrides[get_accounts] = lambda: capped
        self.addCleanup(
            app.dependency_overrides.__setitem__, get_accounts, lambda: self.accounts
        )
        return capped

    def test_every_settings_answer_says_how_many_couples_a_chart_may_be_in(
        self,
    ) -> None:
        # No cap on any plan for now.
        self.assertIsNone(
            self.client.get('/api/account/settings').json()['couples_per_chart']
        )
        self.capped()
        self.assertEqual(
            self.client.get('/api/account/settings').json()['couples_per_chart'], 1
        )
        mine = self.save(BIRTH)
        partner = self.save(PARTNER)
        paired = self.write(
            'POST', '/api/account/couples', {'key': self.key, 'charts': [mine, partner]}
        )
        (couple,) = paired.json()['couples']
        for method, path, body in (
            ('POST', '/api/account/charts', _birth_json(born(6), self.key)),
            ('PUT', f'/api/account/charts/{partner}', _birth_json(born(7), self.key)),
            (
                'PUT',
                f'/api/account/charts/{partner}/name',
                {'key': self.key, 'name': 'B'},
            ),
            ('PUT', '/api/account/my-chart', {'key': self.key, 'chart': mine}),
            ('DELETE', '/api/account/my-chart', {'key': self.key}),
            ('DELETE', f'/api/account/couples/{couple["id"]}', {'key': self.key}),
            ('DELETE', f'/api/account/charts/{partner}', {'key': self.key}),
            (
                'PUT',
                '/api/account/place',
                {'key': self.key, 'place': _place_json(HELSINKI)},
            ),
            ('DELETE', '/api/account/place', {'key': self.key}),
            ('PATCH', '/api/account/schools', {'key': self.key, 'season': 'months'}),
        ):
            with self.subTest(method=method, path=path):
                reply = self.write(method, path, body)
                self.assertIn(reply.status_code, (200, 201), reply.text)
                self.assertEqual(reply.json()['couples_per_chart'], 1)

    def test_a_plan_that_caps_couples_refuses_one_more_by_name(self) -> None:
        first = self.save(BIRTH)
        second = self.save(PARTNER)
        third = self.save(born(5))
        self.capped()
        paired = self.write(
            'POST', '/api/account/couples', {'key': self.key, 'charts': [first, second]}
        )
        self.assertEqual(paired.status_code, 201, paired.text)
        before = self.client.get('/api/account/settings').json()
        for path, body, detail in (
            (
                '/api/account/couples',
                {'key': self.key, 'charts': [third, first]},
                'An unnamed chart is in as many couples as the plan allows (1).',
            ),
            (
                '/api/account/charts',
                {**_birth_json(born(8), self.key), 'couple_with': second},
                'Partner is in as many couples as the plan allows (1).',
            ),
        ):
            with self.subTest(path):
                refused = self.write('POST', path, body)
                self.assertEqual(refused.status_code, 400, refused.text)
                self.assertEqual(refused.json()['detail'], detail)
        self.assertEqual(self.client.get('/api/account/settings').json(), before)

    def test_a_retained_library_is_available_through_the_authenticated_api(
        self,
    ) -> None:
        settings = keep_large_library(self.accounts.store, self.user)
        kept = self.client.get('/api/account/settings')
        self.assertEqual(kept.status_code, 200)
        self.assertEqual(len(kept.json()['charts']), CHART_LIMIT + 1)
        self.assertEqual(
            kept.json()['couples'][0]['charts'], list(settings.couples[0].charts)
        )
        exported = self.client.post('/api/account/export', json={'key': self.key})
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported.json()['settings'], settings_value(settings))
        renamed = self.write(
            'PUT',
            f'/api/account/charts/{settings.charts[-1].id}/name',
            {'key': self.key, 'name': 'Retained'},
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(len(renamed.json()['charts']), CHART_LIMIT + 1)
        refused = self.write(
            'POST', '/api/account/charts', _birth_json(born(60), self.key)
        )
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(
            self.client.get('/api/account/settings').json(), renamed.json()
        )

    def test_settings_and_additions_share_the_configured_chart_allowance(self) -> None:
        self.addCleanup(
            app.dependency_overrides.__setitem__, get_accounts, lambda: self.accounts
        )
        kept = 0
        for cap in (1, 5, 25, None):
            with self.subTest(cap=cap):
                current = replace(
                    self.accounts,
                    store=AccountStore.open(
                        self.accounts.store.path, clock=self.accounts.clock,
                        limits={**LIMITS, 'free': PlanLimits(None, cap)},
                    ),
                )
                app.dependency_overrides[get_accounts] = lambda: current
                self.assertEqual(self.client.get('/api/account/settings').json()['chart_limit'], cap)
                target = 52 if cap is None else cap
                for number in range(kept, target):
                    self.save(born(number))
                kept = target
                before = self.client.get('/api/account/settings').json()
                self.assertEqual((before['chart_limit'], len(before['charts'])), (cap, target))
                if cap is not None:
                    changes = current.store.backup_snapshot().changes
                    refused = self.write('POST', '/api/account/charts', _birth_json(born(target), self.key))
                    self.assertEqual(refused.status_code, 400)
                    self.assertEqual(refused.json()['detail'], f'An account keeps at most {cap} charts.')
                    self.assertEqual(self.client.get('/api/account/settings').json(), before)
                    self.assertEqual(current.store.backup_snapshot().changes, changes)
                    injected = self.write('POST', '/api/account/charts', {**_birth_json(born(target), self.key), 'chart_limit': None})
                    self.assertEqual(injected.status_code, 400)
                    self.assertEqual(current.store.backup_snapshot().changes, changes)
        low = replace(
            current,
            store=AccountStore.open(
                current.store.path, clock=self.accounts.clock,
                limits={**LIMITS, 'free': PlanLimits(None, 1)},
            ),
        )
        app.dependency_overrides[get_accounts] = lambda: low
        retained = self.client.get('/api/account/settings').json()
        self.assertEqual((retained['chart_limit'], len(retained['charts'])), (1, 52))
        exported = self.client.post('/api/account/export', json={'key': self.key})
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(len(exported.json()['settings']['charts']), 52)
        renamed = self.write(
            'PUT', f'/api/account/charts/{retained["charts"][-1]["id"]}/name',
            {'key': self.key, 'name': 'Retained'},
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual((renamed.json()['chart_limit'], len(renamed.json()['charts'])), (1, 52))

    def test_a_full_library_saves_no_more(self) -> None:
        for number in range(CHART_LIMIT):
            self.accounts.store.save_chart(self.user.id, born(number), self.read())
        # The settings say how many charts the account keeps, so a page can say the
        # library is full before it asks.
        kept = self.client.get('/api/account/settings').json()
        self.assertEqual(kept['chart_limit'], CHART_LIMIT)
        self.assertEqual(len(kept['charts']), CHART_LIMIT)
        reply = self.write('POST', '/api/account/charts', _birth_json(BIRTH, self.key))
        self.assertEqual(reply.status_code, 400, reply.text)
        self.assertEqual(
            reply.json()['detail'], f'An account keeps at most {CHART_LIMIT} charts.'
        )

    def test_a_new_birth_is_saved_as_mine_or_paired_at_once(self) -> None:
        partner = self.save(PARTNER)
        mine = self.write(
            'POST',
            '/api/account/charts',
            {**_birth_json(BIRTH, self.key), 'mine': True, 'couple_with': partner},
        )
        self.assertEqual(mine.status_code, 201, mine.text)
        settings = mine.json()
        self.assertEqual(settings['my_chart'], settings['saved'])
        (couple,) = settings['couples']
        self.assertEqual(couple['charts'], [partner, settings['saved']])

    def test_a_chart_is_renamed_without_its_birth(self) -> None:
        chart_id = self.save(PARTNER)
        renamed = self.write(
            'PUT',
            f'/api/account/charts/{chart_id}/name',
            {'key': self.key, 'name': 'Ö'},
        )
        self.assertEqual(renamed.status_code, 200, renamed.text)
        (chart,) = renamed.json()['charts']
        self.assertEqual((chart['id'], chart['name']), (chart_id, 'Ö'))
        self.assertEqual((chart['date'], chart['time']), (PARTNER.date, PARTNER.time))
        unnamed = self.write(
            'PUT',
            f'/api/account/charts/{chart_id}/name',
            {'key': self.key, 'name': None},
        )
        self.assertIsNone(unnamed.json()['charts'][0]['name'])

    def test_no_cache_keeps_what_the_account_api_answers(self) -> None:
        # Saved charts are people's births: a shared or browser cache keeps no copy.
        self.save(BIRTH)
        for reply in (
            self.client.get('/api/account/settings'),
            self.write(
                'PUT',
                '/api/account/place',
                {'key': self.key, 'place': _place_json(LISBON)},
            ),
            self.client.post('/api/account/export', json={'key': self.key}),
            self.client.get('/api/account'),
        ):
            with self.subTest(path=reply.request.url.path):
                self.assertEqual(reply.status_code, 200, reply.text)
                self.assertEqual(reply.headers['cache-control'], 'no-store')

    def test_where_you_are_is_kept_and_forgotten(self) -> None:
        kept = self.write(
            'PUT', '/api/account/place', {'key': self.key, 'place': _place_json(LISBON)}
        )
        self.assertEqual(kept.status_code, 200)
        self.assertEqual(kept.json()['place'], _place_json(LISBON))
        forgotten = self.write('DELETE', '/api/account/place', {'key': self.key})
        self.assertEqual(forgotten.status_code, 200)
        self.assertIsNone(forgotten.json()['place'])
        self.assertIsNone(self.client.get('/api/account/settings').json()['place'])

    def test_writes_come_from_the_site_and_name_the_account(self) -> None:
        other_key = 'f' * 64
        for method, path, written in self.writes('4' * 32, '6' * 32):
            body = {**written, 'updated_at': None}
            with self.subTest(method=method, path=path):
                elsewhere = self.client.request(
                    method,
                    path,
                    json=body,
                    headers={'Origin': 'https://elsewhere.example'},
                )
                self.assertEqual(elsewhere.status_code, 403)
                stale = self.client.request(
                    method, path, json={**body, 'key': other_key}
                )
                self.assertEqual(stale.status_code, 409)
                malformed = self.client.request(
                    method, path, json={**body, 'key': 'not a key'}
                )
                self.assertEqual(malformed.status_code, 400)
        self.assertIsNone(self.accounts.store.settings(self.user.id))
        # Each is taken from the site, naming the account.
        mine = self.save(BIRTH)
        second = self.save(PARTNER)
        couple = self.write(
            'POST', '/api/account/couples', {'key': self.key, 'charts': [mine, second]}
        ).json()['couples'][0]['id']
        self.write('DELETE', f'/api/account/couples/{couple}', {'key': self.key})
        for method, path, body in self.writes(mine, '6' * 32):
            if path.startswith('/api/account/couples'):
                continue
            with self.subTest(method=method, path=path):
                reply = self.write(method, path, body)
                self.assertIn(reply.status_code, (200, 201), reply.text)
        settings = self.client.get('/api/account/settings').json()
        self.assertEqual(
            [chart['id'] for chart in settings['charts']],
            [second, settings['charts'][1]['id']],
        )
        self.assertIsNone(settings['my_chart'])
        self.assertIsNone(settings['place'])
        self.assertEqual(settings['schools']['season'], 'months')

    def test_a_write_from_settings_changed_since_is_refused(self) -> None:
        # Two tabs read the same settings; the second to save is told, and its change
        # is not made.
        mine = self.save(BIRTH)
        read = self.read()
        first = self.client.put(
            '/api/account/place',
            json={'key': self.key, 'updated_at': read, 'place': _place_json(LISBON)},
        )
        self.assertEqual(first.status_code, 200)
        for method, path, body in self.writes(mine, '6' * 32):
            with self.subTest(method=method, path=path):
                stale = self.client.request(
                    method, path, json={**body, 'updated_at': read}
                )
                self.assertEqual(stale.status_code, 412)
                self.assertEqual(
                    stale.json()['detail'],
                    'Your settings changed elsewhere since this page read them.',
                )
        self.assertEqual(self.client.get('/api/account/settings').json(), first.json())
        # A write must say which settings it was made from.
        missing = self.client.request(
            'DELETE', '/api/account/place', json={'key': self.key}
        )
        self.assertEqual(missing.status_code, 400)

    def test_schools_are_chosen_from_the_presets(self) -> None:
        reply = self.write(
            'PATCH',
            '/api/account/schools',
            {'key': self.key, 'favourable': 'climate', 'transits': 'seasoned'},
        )
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(
            reply.json()['schools'],
            {'favourable': 'climate', 'season': 'eighteen', 'transits': 'seasoned'},
        )
        self.assertEqual(
            reply.json()['chosen'],
            {'favourable': 'climate', 'season': None, 'transits': 'seasoned'},
        )
        back = self.write(
            'PATCH', '/api/account/schools', {'key': self.key, 'favourable': None}
        )
        self.assertEqual(back.json()['chosen']['favourable'], None)
        self.assertEqual(back.json()['schools']['favourable'], 'support')
        for body in (
            {'favourable': 'structure'},
            {'season': 'modern'},
            {'transits': 1},
            {'weights': {'wood': 1.2}},
        ):
            with self.subTest(body=body):
                refused = self.write(
                    'PATCH', '/api/account/schools', {'key': self.key, **body}
                )
                self.assertEqual(refused.status_code, 400)

    def test_settings_survive_signing_out_and_go_with_the_account(self) -> None:
        mine = self.save(BIRTH)
        self.write('PUT', '/api/account/my-chart', {'key': self.key, 'chart': mine})
        self.write(
            'PUT', '/api/account/place', {'key': self.key, 'place': _place_json(LISBON)}
        )
        before = self.client.get('/api/account/settings').json()
        self.client.delete('/api/account/session')
        self.assertEqual(self.client.get('/api/account/settings').status_code, 401)
        sign_in_again = site_client()
        email = self.user.email
        asked = sign_in_again.post(
            '/api/account/code',
            json={
                'email': email,
                'purpose': 'sign_in',
                'page_language': 'en',
                'turnstile': 'token',
            },
        )
        self.assertEqual(asked.status_code, 202)
        folder = self.accounts.config.mail_directory
        assert folder is not None
        code = code_in(mails_to(folder.parent, email)[-1])
        signed = sign_in_again.post(
            '/api/account/session', json={'email': email, 'code': code}
        )
        self.assertEqual(signed.status_code, 200)
        self.assertEqual(sign_in_again.get('/api/account/settings').json(), before)
        exported = sign_in_again.post(
            '/api/account/export', json={'key': self.key}
        ).json()
        self.assertEqual(exported['settings']['place'], _place_json(LISBON))
        self.assertEqual(exported['settings']['my_chart'], mine)
        (chart,) = exported['settings']['charts']
        self.assertEqual((chart['id'], chart['birth']['date']), (mine, BIRTH.date))
        deleted = sign_in_again.request(
            'DELETE', '/api/account', json={'key': self.key, 'email': email}
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertIsNone(self.accounts.store.settings(self.user.id))


if __name__ == '__main__':
    unittest.main()
