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
    StoreError,
    UnknownUser,
)
from tests.accounts_support import Clock

COMMIT = '8f3c1e0b5d2a4c6e9f1b3d5a7c9e1f3b5d7a9c1e'
SQUASH = '1d2c3b4a5f6e7d8c9b0a1f2e3d4c5b6a7f8e9d0c'


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

    def test_the_backup_commit_is_remembered(self) -> None:
        def progress() -> tuple[str | None, str | None, str | None]:
            snapshot = self.store.backup_snapshot()
            return snapshot.head, snapshot.pending_head, snapshot.squash_of

        self.assertEqual(progress(), (None, None, None))
        self.store.record_pending_head(COMMIT)
        self.assertEqual(progress(), (None, COMMIT, None))
        self.store.record_backup_head(COMMIT)
        self.assertEqual(progress(), (COMMIT, None, None))
        self.store.record_pending_squash(SQUASH, COMMIT)
        self.assertEqual(progress(), (COMMIT, SQUASH, COMMIT))
        self.store.record_backup_head(SQUASH)
        self.assertEqual(progress(), (SQUASH, None, None))

    def test_a_squash_is_never_recorded_without_its_commit(self) -> None:
        connection = sqlite3.connect(self.store.path)
        with self.assertRaises(sqlite3.IntegrityError), connection:
            connection.execute(
                'UPDATE backup_progress SET squash_of = ? WHERE id = 1', (COMMIT,)
            )
        connection.close()

    def test_progress_never_goes_back(self) -> None:
        self.store.create_user('reader@example.com', 'fi')
        self.store.mark_backed_up(1)
        with self.assertRaises(StoreError):
            self.store.mark_backed_up(0)


class TestRestore(StoreTestCase):
    def test_restores_exactly_the_users_with_nothing_left_to_back_up(self) -> None:
        users = [self.store.create_user(f'u{n}@example.com', 'fi') for n in range(3)]
        target = self.directory / 'restored.sqlite3'
        restored = AccountStore.restore(target, users, head=COMMIT)
        self.assertEqual(restored.users(), sorted(users, key=lambda user: user.id))
        self.assertEqual(restored.backup_snapshot().changes, ())
        self.assertEqual(restored.backup_snapshot().head, COMMIT)
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
            AccountStore.restore(target, [user, twin], head=COMMIT)
        self.assertFalse(target.exists())
        self.assertFalse(target.with_name('restored.sqlite3.partial').exists())

    def test_refuses_an_existing_path(self) -> None:
        with self.assertRaises(StoreError):
            AccountStore.restore(self.path, [], head=COMMIT)


if __name__ == '__main__':
    unittest.main()
