"""Reader-to-writer migration preserves actual personal/auth/backup state."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from eight_characters.accounts import store as store_module
from eight_characters.accounts.backup import read_manifest
from eight_characters.accounts.billing_schema import BILLING_SCHEMA_5
from eight_characters.accounts.records import timestamp
from eight_characters.accounts.restore import restore_backup
from eight_characters.accounts.store import LEGACY_MIGRATIONS, AccountStore, Session
from tests.test_accounts_backup import BackupTestCase
from tests.test_accounts_settings import BIRTH


class WriterMigration(BackupTestCase):
    def rows(self):
        with sqlite3.connect(self.store.path) as connection:
            return {
                name: connection.execute(
                    f'SELECT * FROM {name} ORDER BY rowid'
                ).fetchall()
                for name in (
                    'users',
                    'settings',
                    'sessions',
                    'sign_in_codes',
                    'code_requests',
                    'chart_requests',
                    'backup_progress',
                    'changes',
                    'sqlite_sequence',
                )
            }

    def test_preserves_personal_auth_pending_and_pruned_highwater_then_backs_up(self):
        user = self.store.create_user('fixture@example.invalid', 'fi')
        self.store.set_plan(user.id, 'pro')  # Disabled legacy meaning is unchanged.
        settings, _ = self.store.save_chart(user.id, BIRTH, None)
        self.store.create_session(
            Session(
                'a' * 64,
                user.id,
                timestamp(self.clock()),
                timestamp(self.clock() + timedelta(days=10)),
            )
        )
        self.backup()
        with sqlite3.connect(self.store.path) as connection:
            connection.execute("UPDATE sqlite_sequence SET seq=80 WHERE name='changes'")
        self.store.set_language(user.id, 'en')
        before = self.rows()
        migrated = AccountStore.open(self.store.path, clock=self.clock)
        self.assertEqual(before, self.rows())
        self.assertEqual(migrated.schema_version(), 5)
        self.assertEqual(migrated.settings(user.id), settings)
        with sqlite3.connect(self.store.path) as connection:
            self.assertEqual(
                connection.execute('SELECT ready FROM billing_runtime').fetchone()[0], 0
            )
        migrated.set_language(user.id, 'fi')
        with sqlite3.connect(self.store.path) as connection:
            self.assertEqual(
                connection.execute('SELECT max(seq) FROM changes').fetchone()[0], 82
            )
        self.backup()
        manifest = read_manifest(self.checkout)
        self.assertEqual(
            (manifest.user_count, manifest.billing_count, manifest.sequence), (1, 0, 82)
        )
        target = self.directory / 'migrated-recovery.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        recovered = AccountStore.open(target)
        self.assertEqual(recovered.user_by_id(user.id).plan, 'pro')
        self.assertEqual(recovered.settings(user.id), settings)
        self.assertEqual(recovered.backup_snapshot().sequence, 82)

    def test_failure_rolls_back_all_migration_tables_and_sequence_changes(self):
        self.store.create_user('fixture@example.invalid', 'fi')
        before = self.rows()
        migrations = (*LEGACY_MIGRATIONS, (*BILLING_SCHEMA_5, 'THIS IS NOT SQL'))
        with patch.object(store_module, 'MIGRATIONS', migrations):
            with self.assertRaises(sqlite3.OperationalError):
                AccountStore.open(self.store.path)
        self.assertEqual(before, self.rows())
        with sqlite3.connect(self.store.path) as connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 4)
            self.assertEqual(
                connection.execute(
                    "SELECT count(*) FROM sqlite_master WHERE name='billing_records'"
                ).fetchone()[0],
                0,
            )

    def test_two_opens_apply_one_identical_migration_and_runtime_epoch(self):
        self.store.create_user('fixture@example.invalid', 'fi')
        barrier = Barrier(2)

        def open_database():
            barrier.wait()
            opened = AccountStore.open(self.store.path)
            with opened.read_transaction() as connection:
                epoch = connection.execute(
                    'SELECT epoch FROM billing_runtime'
                ).fetchone()[0]
            return opened.schema_version(), epoch

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: open_database(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], 5)
