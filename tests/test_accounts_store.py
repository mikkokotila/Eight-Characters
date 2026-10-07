import shutil
import sqlite3
import stat
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from eight_characters.accounts import store as store_module
from eight_characters.accounts.records import RecordError, User, user_path
from eight_characters.accounts.store import (
    APPLICATION_ID,
    SCHEMA_VERSION,
    AccountStore,
    EmailTaken,
    RecordChange,
    Session,
    SignInCode,
    StoreError,
    UnknownUser,
)
from tests.accounts_support import Clock

TREE = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'


def _sql(path: Path, query: str) -> list[tuple[object, ...]]:
    connection = sqlite3.connect(path)
    try:
        return connection.execute(query).fetchall()
    finally:
        connection.close()


class StoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory)
        self.path = self.directory / 'accounts.sqlite3'
        self.clock = Clock()
        self.store = AccountStore.create(self.path, clock=self.clock)


class TestCreateAndOpen(StoreTestCase):
    def test_a_new_database_is_private_logged_and_current(self) -> None:
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(_sql(self.path, 'PRAGMA journal_mode'), [('wal',)])
        self.assertEqual(_sql(self.path, 'PRAGMA user_version'), [(SCHEMA_VERSION,)])
        self.assertEqual(_sql(self.path, 'PRAGMA application_id'), [(APPLICATION_ID,)])
        self.assertFalse(self.path.with_name('accounts.sqlite3.partial').exists())

    def test_create_refuses_an_existing_path(self) -> None:
        with self.assertRaises(StoreError):
            AccountStore.create(self.path)

    def test_create_refuses_a_left_over_partial_build(self) -> None:
        other = self.directory / 'other.sqlite3'
        partial = other.with_name('other.sqlite3.partial')
        partial.write_bytes(b'')
        with self.assertRaises(StoreError):
            AccountStore.create(other)
        self.assertFalse(other.exists())
        # Another build's file, or one to look into: never removed by this build.
        self.assertTrue(partial.exists())

    def test_open_refuses_a_missing_database_and_creates_none(self) -> None:
        missing = self.directory / 'missing.sqlite3'
        with self.assertRaises(StoreError):
            AccountStore.open(missing)
        self.assertFalse(missing.exists())

    def test_a_vanished_database_is_not_recreated_empty(self) -> None:
        self.path.unlink()
        with self.assertRaises(sqlite3.OperationalError):
            self.store.users()
        self.assertFalse(self.path.exists())

    def test_open_refuses_a_file_that_is_no_account_database(self) -> None:
        other = self.directory / 'other.sqlite3'
        _sql(other, 'CREATE TABLE notes (text TEXT)')
        with self.assertRaises(StoreError):
            AccountStore.open(other)
        # Another application's database, at a version this one also has.
        _sql(other, 'PRAGMA user_version = 1')
        with self.assertRaises(StoreError):
            AccountStore.open(other)

    def test_open_refuses_a_newer_schema(self) -> None:
        _sql(self.path, f'PRAGMA user_version = {SCHEMA_VERSION + 1}')
        with self.assertRaises(StoreError) as caught:
            AccountStore.open(self.path)
        self.assertIn(str(SCHEMA_VERSION + 1), str(caught.exception))

    def test_open_runs_the_migrations_a_database_lacks(self) -> None:
        later = (
            *store_module.MIGRATIONS,
            ('CREATE TABLE later (id INTEGER PRIMARY KEY) STRICT',),
        )
        with (
            patch.object(store_module, 'MIGRATIONS', later),
            patch.object(store_module, 'SCHEMA_VERSION', SCHEMA_VERSION + 1),
        ):
            AccountStore.open(self.path)
        self.assertEqual(
            _sql(self.path, 'PRAGMA user_version'), [(SCHEMA_VERSION + 1,)]
        )
        self.assertEqual(_sql(self.path, 'SELECT COUNT(*) FROM later'), [(0,)])

    def test_a_migration_already_run_by_another_process_is_not_run_again(self) -> None:
        # What a second process finds if it read the version before the first one
        # finished: the version is read again under the write lock.
        connection = sqlite3.connect(self.path, isolation_level=None)
        try:
            store_module._migrate(connection)
        finally:
            connection.close()
        self.assertEqual(_sql(self.path, 'PRAGMA user_version'), [(SCHEMA_VERSION,)])

    def test_processes_opening_an_older_database_at_once_all_succeed(self) -> None:
        older = self.directory / 'older.sqlite3'
        with (
            patch.object(store_module, 'MIGRATIONS', store_module.MIGRATIONS[:1]),
            patch.object(store_module, 'SCHEMA_VERSION', 1),
        ):
            AccountStore.create(older)
        barrier = threading.Barrier(8)
        failures: list[BaseException] = []

        def open_it() -> None:
            barrier.wait()
            try:
                AccountStore.open(older)
            except BaseException as exc:
                failures.append(exc)

        threads = [threading.Thread(target=open_it) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(failures, [])
        self.assertEqual(_sql(older, 'PRAGMA user_version'), [(SCHEMA_VERSION,)])

    def test_a_failing_migration_leaves_the_database_as_it_was(self) -> None:
        broken = (
            *store_module.MIGRATIONS,
            ('CREATE TABLE half (id INTEGER) STRICT', 'NOT SQL'),
        )
        with (
            patch.object(store_module, 'MIGRATIONS', broken),
            patch.object(store_module, 'SCHEMA_VERSION', SCHEMA_VERSION + 1),
            self.assertRaises(sqlite3.OperationalError),
        ):
            AccountStore.open(self.path)
        self.assertEqual(_sql(self.path, 'PRAGMA user_version'), [(SCHEMA_VERSION,)])
        tables = _sql(self.path, "SELECT name FROM sqlite_master WHERE name = 'half'")
        self.assertEqual(tables, [])


class TestUsers(StoreTestCase):
    def test_a_new_account_is_free_and_keyed_by_its_normalized_email(self) -> None:
        user = self.store.create_user('  Reader@Example.COM ', 'en')
        self.assertEqual(user.email, 'reader@example.com')
        self.assertEqual((user.language, user.plan), ('en', 'free'))
        self.assertEqual(user.created_at, '2026-10-07T12:00:00Z')
        self.assertEqual(user.updated_at, user.created_at)
        self.assertEqual(self.store.user_by_email('READER@example.com'), user)
        self.assertEqual(self.store.user_by_id(user.id), user)

    def test_one_account_per_address(self) -> None:
        self.store.create_user('reader@example.com', 'fi')
        with self.assertRaises(EmailTaken):
            self.store.create_user('Reader@Example.com', 'en')
        self.assertEqual(len(self.store.users()), 1)

    def test_one_account_per_address_when_both_arrive_at_once(self) -> None:
        barrier = threading.Barrier(8)
        outcomes: list[str] = []

        def sign_up() -> None:
            barrier.wait()
            try:
                self.store.create_user('reader@example.com', 'fi')
                outcomes.append('created')
            except EmailTaken:
                outcomes.append('taken')

        threads = [threading.Thread(target=sign_up) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(outcomes), ['created'] + ['taken'] * 7)
        self.assertEqual(len(self.store.users()), 1)

    def test_refuses_an_unknown_language_or_address(self) -> None:
        with self.assertRaises(RecordError):
            self.store.create_user('reader@example.com', 'sv')
        with self.assertRaises(RecordError):
            self.store.create_user('reader', 'fi')
        self.assertEqual(self.store.users(), [])

    def test_lookups_of_what_does_not_exist(self) -> None:
        self.assertIsNone(self.store.user_by_email('nobody@example.com'))
        self.assertIsNone(self.store.user_by_id('0' * 32))
        self.assertIsNone(self.store.user_by_id('not an id'))

    def test_users_in_id_order(self) -> None:
        made = [self.store.create_user(f'u{n}@example.com', 'fi') for n in range(5)]
        self.assertEqual(self.store.users(), sorted(made, key=lambda user: user.id))

    def test_language_and_plan_change(self) -> None:
        user = self.store.create_user('reader@example.com', 'fi')
        self.clock.advance(60)
        changed = self.store.set_language(user.id, 'en')
        self.assertEqual(
            changed, replace(user, language='en', updated_at='2026-10-07T12:01:00Z')
        )
        self.clock.advance(60)
        upgraded = self.store.set_plan(user.id, 'pro')
        self.assertEqual(upgraded.plan, 'pro')
        self.assertEqual(self.store.user_by_id(user.id), upgraded)

    def test_a_change_to_the_same_value_writes_nothing(self) -> None:
        user = self.store.create_user('reader@example.com', 'fi')
        self.store.mark_backed_up(self.store.backup_snapshot().through_seq)
        self.clock.advance(60)
        self.assertEqual(self.store.set_language(user.id, 'fi'), user)
        self.assertEqual(self.store.backup_snapshot().changes, ())

    def test_updated_at_never_goes_back_with_the_clock(self) -> None:
        user = self.store.create_user('reader@example.com', 'fi')
        self.clock.advance(-3600)
        self.assertEqual(
            self.store.set_plan(user.id, 'basic').updated_at, user.created_at
        )

    def test_changes_refuse_unknown_values_and_users(self) -> None:
        user = self.store.create_user('reader@example.com', 'fi')
        with self.assertRaises(RecordError):
            self.store.set_language(user.id, 'sv')
        with self.assertRaises(RecordError):
            self.store.set_plan(user.id, 'gold')
        with self.assertRaises(UnknownUser):
            self.store.set_plan('0' * 32, 'pro')
        with self.assertRaises(UnknownUser):
            self.store.delete_user('0' * 32)

    def test_delete(self) -> None:
        user = self.store.create_user('reader@example.com', 'fi')
        self.store.delete_user(user.id)
        self.assertIsNone(self.store.user_by_id(user.id))
        # The address is free again.
        self.store.create_user('reader@example.com', 'en')


class TestBackupLog(StoreTestCase):
    def test_every_change_is_logged_once_per_record(self) -> None:
        first = self.store.create_user('first@example.com', 'fi')
        second = self.store.create_user('second@example.com', 'en')
        self.store.set_plan(first.id, 'pro')
        self.store.set_language(first.id, 'en')
        snapshot = self.store.backup_snapshot()
        self.assertEqual((snapshot.after_seq, snapshot.through_seq), (0, 4))
        self.assertEqual(snapshot.user_count, 2)
        expected = {
            user_path(first.id): self.store.user_by_id(first.id),
            user_path(second.id): second,
        }
        self.assertEqual(
            {change.path: change.user for change in snapshot.changes}, expected
        )
        self.assertEqual([change.path for change in snapshot.changes], sorted(expected))

    def test_a_deleted_record_is_logged_as_gone(self) -> None:
        user = self.store.create_user('reader@example.com', 'fi')
        self.store.delete_user(user.id)
        snapshot = self.store.backup_snapshot()
        self.assertEqual(
            snapshot.changes, (RecordChange(path=user_path(user.id), user=None),)
        )
        self.assertEqual(snapshot.user_count, 0)

    def test_backed_up_changes_are_done_with(self) -> None:
        user = self.store.create_user('reader@example.com', 'fi')
        through = self.store.backup_snapshot().through_seq
        self.store.mark_backed_up(through)
        self.assertEqual(_sql(self.path, 'SELECT COUNT(*) FROM changes'), [(0,)])
        empty = self.store.backup_snapshot()
        self.assertEqual(
            (empty.after_seq, empty.through_seq, empty.changes), (through, through, ())
        )
        self.store.set_plan(user.id, 'max')
        later = self.store.backup_snapshot()
        self.assertEqual((later.after_seq, later.through_seq), (through, through + 1))

    def test_a_change_made_after_the_snapshot_waits_for_the_next(self) -> None:
        self.store.create_user('first@example.com', 'fi')
        snapshot = self.store.backup_snapshot()
        late = self.store.create_user('late@example.com', 'fi')
        self.store.mark_backed_up(snapshot.through_seq)
        self.assertEqual(
            [change.user for change in self.store.backup_snapshot().changes], [late]
        )

    def test_the_backup_tree_is_remembered(self) -> None:
        self.assertIsNone(self.store.backup_snapshot().tree)
        self.store.record_pending_tree(TREE)
        snapshot = self.store.backup_snapshot()
        self.assertEqual((snapshot.tree, snapshot.pending_tree), (None, TREE))
        self.store.record_backup_tree(TREE)
        snapshot = self.store.backup_snapshot()
        self.assertEqual((snapshot.tree, snapshot.pending_tree), (TREE, None))

    def test_progress_never_goes_back(self) -> None:
        self.store.create_user('reader@example.com', 'fi')
        self.store.mark_backed_up(1)
        with self.assertRaises(StoreError):
            self.store.mark_backed_up(0)


class TestSessionsAndCodes(StoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = self.store.create_user('reader@example.com', 'fi')

    def session(self, name: str, user_id: str | None = None) -> Session:
        return Session(
            token_hash=name,
            user_id=user_id or self.user.id,
            created_at='2026-10-07T12:00:00Z',
            expires_at='2026-11-06T12:00:00Z',
        )

    def code(self, **changes: object) -> SignInCode:
        base = SignInCode(
            email='reader@example.com',
            code_hash='right',
            new_language=None,
            created_at='2026-10-07T12:00:00Z',
            expires_at='2026-10-07T12:10:00Z',
            attempts=0,
        )
        return replace(base, **changes)

    def test_sessions_are_kept_extended_and_ended(self) -> None:
        self.store.create_session(self.session('a'))
        self.assertEqual(self.store.session('a'), self.session('a'))
        self.store.extend_session('a', '2026-12-01T00:00:00Z')
        self.assertEqual(
            self.store.session('a'),
            replace(self.session('a'), expires_at='2026-12-01T00:00:00Z'),
        )
        self.store.delete_session('a')
        self.assertIsNone(self.store.session('a'))

    def test_signing_out_everywhere_ends_only_that_account(self) -> None:
        other = self.store.create_user('other@example.com', 'en')
        for name in ('a', 'b'):
            self.store.create_session(self.session(name))
        self.store.create_session(self.session('c', other.id))
        self.assertEqual(self.store.delete_sessions(self.user.id), 2)
        self.assertIsNone(self.store.session('a'))
        self.assertIsNotNone(self.store.session('c'))

    def test_a_session_and_its_account_are_read_together(self) -> None:
        self.store.create_session(self.session('a'))
        self.assertEqual(
            self.store.session_and_user('a'), (self.session('a'), self.user)
        )
        self.store.delete_user(self.user.id)
        self.assertIsNone(self.store.session_and_user('a'))
        self.assertIsNone(self.store.session_and_user('unknown'))

    def test_everything_kept_for_an_account(self) -> None:
        self.store.create_session(self.session('a'))
        self.store.put_code(self.code(attempts=2))
        for email, client in (
            (self.user.email, '192.0.2.1'),
            (self.user.email, '198.51.100.7'),
            ('other@example.com', '192.0.2.9'),
        ):
            self.store.allow_code_request(
                email,
                client,
                '2026-10-07T12:00:00Z',
                '2026-10-07T11:00:00Z',
                5,
                20,
            )
        account = {
            'created_at': self.user.created_at,
            'email': 'reader@example.com',
            'id': self.user.id,
            'language': 'fi',
            'plan': 'free',
            'updated_at': self.user.updated_at,
        }
        requests = [
            {'client': client, 'requested_at': '2026-10-07T12:00:00Z'}
            for client in ('192.0.2.1', '198.51.100.7')
        ]
        session = {
            'created_at': '2026-10-07T12:00:00Z',
            'expires_at': '2026-11-06T12:00:00Z',
        }
        code = {
            'attempts': 2,
            'created_at': '2026-10-07T12:00:00Z',
            'expires_at': '2026-10-07T12:10:00Z',
        }
        data = self.store.account_data(self.user.id)
        expected = {
            'account': account,
            'code_requests': requests,
            'sessions': [session],
            'sign_in_code': code,
        }
        self.assertEqual(data, expected)
        # Hashes are not the account's data, and would only help a guesser.
        self.assertNotIn('right', str(data))
        with self.assertRaises(UnknownUser):
            self.store.account_data('0' * 32)

    def test_a_session_needs_an_account(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.create_session(self.session('a', '0' * 32))

    def test_deleting_the_account_takes_its_sessions_codes_and_requests(self) -> None:
        self.store.create_session(self.session('a'))
        self.store.put_code(self.code())
        self.assertTrue(
            self.store.allow_code_request(
                self.user.email,
                'client',
                '2026-10-07T12:00:00Z',
                '2026-10-07T11:00:00Z',
                5,
                20,
            )
        )
        self.store.delete_user(self.user.id)
        self.assertIsNone(self.store.session('a'))
        self.assertIsNone(self.store.code(self.user.email))
        self.assertEqual(_sql(self.path, 'SELECT COUNT(*) FROM code_requests'), [(0,)])

    def test_a_new_code_replaces_the_last(self) -> None:
        self.store.put_code(self.code(code_hash='first'))
        self.store.put_code(self.code(code_hash='second', new_language='en'))
        self.assertEqual(
            self.store.code('reader@example.com'),
            self.code(code_hash='second', new_language='en'),
        )

    def test_taking_the_right_code_uses_it_up(self) -> None:
        self.store.put_code(self.code())
        taken = self.store.take_code(
            'reader@example.com', 'right', '2026-10-07T12:05:00Z', 5
        )
        self.assertEqual(taken, self.code())
        self.assertIsNone(self.store.code('reader@example.com'))
        self.assertIsNone(
            self.store.take_code(
                'reader@example.com', 'right', '2026-10-07T12:05:00Z', 5
            )
        )

    def test_wrong_tries_are_counted_and_the_last_drops_the_code(self) -> None:
        self.store.put_code(self.code())
        for tries in range(1, 5):
            self.assertIsNone(
                self.store.take_code(
                    'reader@example.com', 'wrong', '2026-10-07T12:01:00Z', 5
                )
            )
            self.assertEqual(
                self.store.code('reader@example.com'), self.code(attempts=tries)
            )
        self.assertIsNone(
            self.store.take_code(
                'reader@example.com', 'wrong', '2026-10-07T12:01:00Z', 5
            )
        )
        self.assertIsNone(self.store.code('reader@example.com'))
        self.assertIsNone(
            self.store.take_code(
                'reader@example.com', 'right', '2026-10-07T12:01:00Z', 5
            )
        )

    def test_an_expired_code_is_dropped_unused(self) -> None:
        self.store.put_code(self.code())
        self.assertIsNone(
            self.store.take_code(
                'reader@example.com', 'right', '2026-10-07T12:10:00Z', 5
            )
        )
        self.assertIsNone(self.store.code('reader@example.com'))

    def test_expired_sessions_and_codes_are_dropped(self) -> None:
        self.store.create_session(self.session('a'))
        self.store.put_code(self.code())
        self.store.delete_expired('2026-10-07T12:10:00Z')
        self.assertIsNone(self.store.code('reader@example.com'))
        self.assertIsNotNone(self.store.session('a'))
        self.store.delete_expired('2026-11-06T12:00:00Z')
        self.assertIsNone(self.store.session('a'))

    def test_code_requests_are_limited_per_address_and_per_client(self) -> None:
        def ask(email: str, client: str, now: str = '2026-10-07T12:00:00Z') -> bool:
            return self.store.allow_code_request(
                email, client, now, '2026-10-07T11:00:00Z', 2, 3
            )

        self.assertTrue(ask('a@example.com', 'one'))
        self.assertTrue(ask('a@example.com', 'two'))
        self.assertFalse(ask('a@example.com', 'three'))
        self.assertTrue(ask('b@example.com', 'one'))
        # The client's third request is allowed, its fourth is not.
        self.assertTrue(ask('c@example.com', 'one'))
        self.assertFalse(ask('d@example.com', 'one'))
        self.assertEqual(_sql(self.path, 'SELECT COUNT(*) FROM code_requests'), [(4,)])

    def test_requests_older_than_the_window_no_longer_count(self) -> None:
        old = '2026-10-07T10:00:00Z'
        for _ in range(2):
            self.store.allow_code_request(
                'a@example.com', 'one', old, '2026-10-07T09:00:00Z', 2, 9
            )
        self.assertTrue(
            self.store.allow_code_request(
                'a@example.com',
                'one',
                '2026-10-07T12:00:00Z',
                '2026-10-07T11:00:00Z',
                2,
                9,
            )
        )
        self.assertEqual(_sql(self.path, 'SELECT COUNT(*) FROM code_requests'), [(1,)])


class TestRestore(StoreTestCase):
    def test_restores_exactly_the_users_with_nothing_left_to_back_up(self) -> None:
        users = [self.store.create_user(f'u{n}@example.com', 'fi') for n in range(3)]
        target = self.directory / 'restored.sqlite3'
        restored = AccountStore.restore(target, users, tree=TREE)
        self.assertEqual(restored.users(), sorted(users, key=lambda user: user.id))
        self.assertEqual(restored.backup_snapshot().changes, ())
        self.assertEqual(restored.backup_snapshot().tree, TREE)
        self.assertEqual(
            stat.S_IMODE((self.directory / 'restored.sqlite3').stat().st_mode), 0o600
        )

    def test_refuses_records_that_cannot_form_one_database(self) -> None:
        user = self.store.create_user('reader@example.com', 'fi')
        twin = User(
            id='0' * 32,
            email=user.email,
            language='en',
            plan='free',
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        target = self.directory / 'restored.sqlite3'
        with self.assertRaises(StoreError):
            AccountStore.restore(target, [user, twin], tree=TREE)
        self.assertFalse(target.exists())
        self.assertFalse(target.with_name('restored.sqlite3.partial').exists())

    def test_refuses_an_existing_path(self) -> None:
        with self.assertRaises(StoreError):
            AccountStore.restore(self.path, [], tree=TREE)


if __name__ == '__main__':
    unittest.main()
