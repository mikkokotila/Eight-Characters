"""The settings for Today an account keeps: its own chart, a partner's, where the
person is, and the schools chosen. Their record, their database, their backup and
the API that sets them."""

import json
import shutil
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import patch

import pyrage

from eight_characters.accounts import store as store_module
from eight_characters.accounts.backup import run_backup
from eight_characters.accounts.records import (
    DEFAULT_SCHOOLS,
    NO_CHOICE,
    Birth,
    ChosenSchools,
    Place,
    RecordError,
    Schools,
    Settings,
    User,
    canonical_json,
    decode_settings,
    decode_user,
    encode_settings,
    encode_user,
    settings_value,
)
from eight_characters.accounts.restore import restore_backup
from eight_characters.accounts.store import AccountStore, UnknownUser
from eight_characters.accounts.web import Accounts, account_key
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
OWN = Birth(
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
SETTINGS = Settings(
    own=OWN,
    partner=PARTNER,
    place=LISBON,
    schools=ChosenSchools(favourable='climate', season='commander', transits=None),
    updated_at='2026-10-07T12:00:00Z',
)
USER = User(
    id='3f9c2a7d0b8e4c51a6f2d9e0b7c4a1e5',
    email='reader@example.com',
    language='fi',
    plan='free',
    created_at='2026-10-07T12:00:00Z',
    updated_at='2026-10-07T12:30:00Z',
)


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
                replace(OWN, **changes)
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

    def test_canonical_bytes(self) -> None:
        self.assertEqual(
            encode_settings(replace(SETTINGS, partner=None, own=None)),
            b'{\n'
            b'  "charts": {\n'
            b'    "partner": null,\n'
            b'    "self": null\n'
            b'  },\n'
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
            replace(SETTINGS, own=None, partner=None, place=None),
            replace(SETTINGS, own=replace(OWN, fold=1, name='Äiti')),
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
            'a missing chart': self._variant(lambda v: v['charts'].pop('partner')),
            'an extra chart': self._variant(lambda v: v['charts'].update(mother=None)),
            'a coordinate as a whole number': self._variant(
                lambda v: v['place'].update(latitude=38)
            ),
            'a coordinate as text': self._variant(
                lambda v: v['place'].update(latitude='38.7')
            ),
            'a name that is not text': self._variant(
                lambda v: v['charts']['self'].update(name=1)
            ),
            'an unknown school': self._variant(
                lambda v: v['schools'].update(season='modern')
            ),
            'a fold of true': self._variant(
                lambda v: v['charts']['self'].update(fold=True)
            ),
            'a place that is not an object': self._variant(
                lambda v: v['charts']['self'].update(place=[])
            ),
            'a time zone that is not text': self._variant(
                lambda v: v['place'].update(timezone=[])
            ),
            'no final newline': canonical.rstrip(b'\n'),
        }
        for name, data in cases.items():
            with self.subTest(name), self.assertRaises(RecordError):
                decode_settings(data)

    def test_the_account_record_carries_its_settings(self) -> None:
        data = encode_user(USER, SETTINGS)
        self.assertEqual(json.loads(data)['schema'], 2)
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

    def test_a_record_with_broken_settings_is_refused(self) -> None:
        value = json.loads(encode_user(USER, SETTINGS))
        value['settings']['schools']['favourable'] = 'modern'
        with self.assertRaises(RecordError):
            decode_user(canonical_json(value))


class StoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory)
        self.path = self.directory / 'accounts.sqlite3'
        self.clock = Clock()
        self.store = AccountStore.create(self.path, clock=self.clock)
        self.user = self.store.create_user('reader@example.com', 'fi')


class TestSettingsStore(StoreCase):
    def test_an_account_starts_with_none(self) -> None:
        self.assertIsNone(self.store.settings(self.user.id))
        self.assertIsNone(self.store.account_data(self.user.id)['settings'])

    def test_each_setting_is_kept(self) -> None:
        self.store.put_chart(self.user.id, 'self', OWN)
        self.store.put_chart(self.user.id, 'partner', PARTNER)
        self.store.put_place(self.user.id, LISBON)
        kept = self.store.set_schools(self.user.id, {'season': 'months'})
        expected = Settings(
            own=OWN,
            partner=PARTNER,
            place=LISBON,
            schools=replace(NO_CHOICE, season='months'),
            updated_at='2026-10-07T12:00:03Z',
        )
        self.assertEqual(kept, expected)
        self.assertEqual(self.store.settings(self.user.id), expected)
        self.assertEqual(
            self.store.account_data(self.user.id)['settings'],
            settings_value(expected),
        )

    def test_a_choice_of_one_school_keeps_the_others(self) -> None:
        self.store.set_schools(
            self.user.id, {'favourable': 'climate', 'transits': 'whole'}
        )
        kept = self.store.set_schools(self.user.id, {'season': 'late_summer'})
        assert kept is not None
        self.assertEqual(
            kept.schools,
            ChosenSchools(favourable='climate', season='late_summer', transits='whole'),
        )
        # None follows the default again.
        again = self.store.set_schools(self.user.id, {'favourable': None})
        assert again is not None
        self.assertIsNone(again.schools.favourable)
        self.assertEqual(again.schools.effective().favourable, 'support')
        for chosen in (
            {'weights': 'support'},
            {'season': 'modern'},
            {'favourable': ''},
        ):
            with self.subTest(chosen=chosen), self.assertRaises(RecordError):
                self.store.set_schools(self.user.id, chosen)
        self.assertEqual(self.store.settings(self.user.id), again)

    def test_each_change_is_logged_for_the_backup_and_moves_its_time_on(self) -> None:
        self.store.mark_backed_up(self.store.backup_snapshot().through_seq)
        first = self.store.put_chart(self.user.id, 'self', OWN)
        second = self.store.put_place(self.user.id, HELSINKI)
        assert first is not None and second is not None
        # Within one second, or with the clock gone back, a change still comes later.
        self.assertEqual(first.updated_at, '2026-10-07T12:00:00Z')
        self.assertEqual(second.updated_at, '2026-10-07T12:00:01Z')
        snapshot = self.store.backup_snapshot()
        self.assertEqual(len(snapshot.changes), 1)
        self.assertEqual(snapshot.changes[0].user, self.user)
        self.assertEqual(snapshot.changes[0].settings, second)

    def test_a_change_that_changes_nothing_writes_nothing(self) -> None:
        self.store.put_chart(self.user.id, 'self', OWN)
        self.store.mark_backed_up(self.store.backup_snapshot().through_seq)
        self.clock.advance(60)
        kept = self.store.put_chart(self.user.id, 'self', OWN)
        assert kept is not None
        self.assertEqual(kept.updated_at, '2026-10-07T12:00:00Z')
        self.assertEqual(self.store.backup_snapshot().changes, ())
        # An account that keeps no settings keeps none after removing no partner, or
        # choosing the default schools.
        other = self.store.create_user('other@example.com', 'en')
        self.store.mark_backed_up(self.store.backup_snapshot().through_seq)
        self.assertIsNone(self.store.delete_chart(other.id, 'partner'))
        self.assertIsNone(self.store.set_schools(other.id, {'favourable': None}))
        self.assertIsNone(self.store.settings(other.id))
        self.assertEqual(self.store.backup_snapshot().changes, ())

    def test_a_partner_is_removed(self) -> None:
        self.store.put_chart(self.user.id, 'partner', PARTNER)
        kept = self.store.delete_chart(self.user.id, 'partner')
        assert kept is not None
        self.assertIsNone(kept.partner)
        self.assertEqual(self.store.settings(self.user.id), kept)

    def test_settings_go_with_the_account(self) -> None:
        self.store.put_chart(self.user.id, 'self', OWN)
        self.store.delete_user(self.user.id)
        connection = sqlite3.connect(self.path)
        try:
            rows = connection.execute('SELECT COUNT(*) FROM settings').fetchone()
        finally:
            connection.close()
        self.assertEqual(rows, (0,))
        with self.assertRaises(UnknownUser):
            self.store.put_place(self.user.id, HELSINKI)

    def test_a_restore_holds_each_account_with_its_settings(self) -> None:
        self.store.put_chart(self.user.id, 'self', OWN)
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
        self.assertIsNotNone(store.put_chart(kept.id, 'self', OWN))

    def test_a_corrupt_settings_row_stops_the_store(self) -> None:
        self.store.put_chart(self.user.id, 'self', OWN)
        connection = sqlite3.connect(self.path)
        try:
            connection.execute(
                'UPDATE settings SET record = ?', (b'{"charts": null}\n',)
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

    def _record(self, user_id: str) -> bytes:
        path = self.checkout / 'users' / user_id[:2] / user_id / 'user.json.age'
        return pyrage.decrypt(path.read_bytes(), [self.identity])

    def test_the_backup_keeps_the_settings_in_the_account_record(self) -> None:
        settings = self.store.put_chart(self.user.id, 'self', OWN)
        run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual(self._record(self.user.id), encode_user(self.user, settings))
        changed = self.store.put_chart(self.user.id, 'partner', PARTNER)
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual(result.written, 1)
        self.assertEqual(decode_user(self._record(self.user.id)), (self.user, changed))

    def test_a_restore_brings_the_settings_back(self) -> None:
        self.store.put_chart(self.user.id, 'self', OWN)
        run_backup(self.store, self.checkout, self.recipient)
        # A change to the settings alone, after a backup, reaches the next one.
        self.store.put_place(self.user.id, LISBON)
        self.store.set_schools(self.user.id, {'season': 'commander'})
        settings = self.store.put_chart(self.user.id, 'partner', PARTNER)
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual(result.written, 1)
        target = self.directory / 'restored.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        self.assertEqual(AccountStore.open(target).settings(self.user.id), settings)

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
        path = (
            self.checkout / 'users' / self.user.id[:2] / self.user.id / 'user.json.age'
        )
        path.write_bytes(pyrage.encrypt(old, [self.recipient]))
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
        cls.accounts = install_accounts(cls)

    def setUp(self) -> None:
        self.client = site_client()
        email = f'reader{self.id().rsplit(".", 1)[-1][-40:]}@example.com'
        sign_in(self.client, self.accounts, email)
        user = self.accounts.store.user_by_email(email)
        assert user is not None
        self.user = user
        self.key = account_key(user)

    def test_settings_need_an_account(self) -> None:
        signed_out = site_client()
        self.assertEqual(signed_out.get('/api/account/settings').status_code, 401)
        for method, path, body in (
            ('PUT', '/api/account/charts/self', _birth_json(OWN, self.key)),
            ('DELETE', '/api/account/charts/partner', {'key': self.key}),
            (
                'PUT',
                '/api/account/place',
                {'key': self.key, 'place': _place_json(HELSINKI)},
            ),
            ('PATCH', '/api/account/schools', {'key': self.key}),
        ):
            with self.subTest(path=path):
                reply = signed_out.request(method, path, json=body)
                self.assertEqual(reply.status_code, 401)

    def test_an_account_that_has_set_nothing_has_the_defaults(self) -> None:
        reply = self.client.get('/api/account/settings')
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(
            reply.json(),
            {
                'charts': {'self': None, 'partner': None},
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
        late = replace(OWN, date='1990-05-18', time='00:47', zi='whole_zi_23')
        for role, birth in (('self', OWN), ('partner', PARTNER), ('self', late)):
            with self.subTest(role=role):
                reply = self.client.put(
                    f'/api/account/charts/{role}', json=_birth_json(birth, self.key)
                )
                self.assertEqual(reply.status_code, 200)
                chart = reply.json()['charts'][role]
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
        # The Zi-hour convention moves a birth late in the evening to the next day.
        split = self.client.put(
            '/api/account/charts/self',
            json=_birth_json(replace(late, zi='split_midnight'), self.key),
        ).json()['charts']['self']['pillars']['day']
        whole = self.client.put(
            '/api/account/charts/self', json=_birth_json(late, self.key)
        ).json()['charts']['self']['pillars']['day']
        self.assertNotEqual(split, whole)

    def test_a_birth_is_checked_by_the_first_charts_rules(self) -> None:
        body = _birth_json(OWN, self.key)
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
                reply = self.client.put('/api/account/charts/self', json=case)
                self.assertEqual(reply.status_code, 400, reply.text)
        self.assertIsNone(self.accounts.store.settings(self.user.id))
        repeated = {**body, 'date': '2021-10-31', 'time': '03:30', 'fold': 1}
        reply = self.client.put('/api/account/charts/self', json=repeated)
        self.assertEqual(reply.status_code, 200, reply.text)
        self.assertEqual(reply.json()['charts']['self']['fold'], 1)

    def test_a_saved_chart_that_no_longer_computes_shows_why(self) -> None:
        # As a time zone update can leave a saved time one the clocks skipped: the
        # settings still answer, and say what is wrong with that chart.
        skipped = replace(OWN, date='2021-03-28', time='03:30')
        self.accounts.store.put_chart(self.user.id, 'self', skipped)
        reply = self.client.get('/api/account/settings')
        self.assertEqual(reply.status_code, 200)
        chart = reply.json()['charts']['self']
        self.assertIsNone(chart['pillars'])
        self.assertIn('skipped', chart['problem'])

    def test_an_unknown_role_is_refused(self) -> None:
        reply = self.client.put(
            '/api/account/charts/mother', json=_birth_json(OWN, self.key)
        )
        self.assertEqual(reply.status_code, 400)

    def test_writes_come_from_the_site_and_name_the_account(self) -> None:
        writes: list[tuple[str, str, dict[str, Any]]] = [
            ('PUT', '/api/account/charts/self', _birth_json(OWN, self.key)),
            ('PUT', '/api/account/charts/partner', _birth_json(PARTNER, self.key)),
            ('DELETE', '/api/account/charts/partner', {'key': self.key}),
            (
                'PUT',
                '/api/account/place',
                {'key': self.key, 'place': _place_json(HELSINKI)},
            ),
            ('PATCH', '/api/account/schools', {'key': self.key, 'season': 'months'}),
        ]
        other_key = 'f' * 64
        for method, path, body in writes:
            with self.subTest(path=path):
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
        for method, path, body in writes:
            with self.subTest(path=path):
                reply = self.client.request(method, path, json=body)
                self.assertEqual(reply.status_code, 200, reply.text)
        settings = self.client.get('/api/account/settings').json()
        self.assertIsNotNone(settings['charts']['self'])
        self.assertIsNone(settings['charts']['partner'])
        self.assertEqual(settings['place'], _place_json(HELSINKI))
        self.assertEqual(settings['schools']['season'], 'months')

    def test_schools_are_chosen_from_the_presets(self) -> None:
        reply = self.client.patch(
            '/api/account/schools',
            json={'key': self.key, 'favourable': 'climate', 'transits': 'seasoned'},
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
        back = self.client.patch(
            '/api/account/schools', json={'key': self.key, 'favourable': None}
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
                refused = self.client.patch(
                    '/api/account/schools', json={'key': self.key, **body}
                )
                self.assertEqual(refused.status_code, 400)

    def test_settings_survive_signing_out_and_go_with_the_account(self) -> None:
        self.client.put('/api/account/charts/self', json=_birth_json(OWN, self.key))
        self.client.put(
            '/api/account/place',
            json={'key': self.key, 'place': _place_json(LISBON)},
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
        self.assertEqual(exported['settings']['charts']['self']['date'], OWN.date)
        deleted = sign_in_again.request(
            'DELETE', '/api/account', json={'key': self.key, 'email': email}
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertIsNone(self.accounts.store.settings(self.user.id))


if __name__ == '__main__':
    unittest.main()
