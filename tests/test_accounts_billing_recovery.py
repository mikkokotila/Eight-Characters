"""Future producer fixtures exercise the reader; no native payment is simulated."""

import hashlib
import json
import sqlite3
import unittest
from dataclasses import replace
from unittest.mock import patch

import pyrage
from pydantic import ValidationError

from eight_characters.accounts.backup import (
    BackupError,
    billing_files,
    manifest_bytes,
    read_manifest,
    run_backup,
    squash_history,
)
from eight_characters.accounts.billing_records import (
    AccountBillingRecord,
    Binding,
    Deletion,
    EventRecord,
    OfferSnapshot,
    ScopeRecord,
    billing_path,
    decode_billing,
    encode_billing,
    validate_billing_graph,
)
from eight_characters.accounts.billing_schema import BILLING_SCHEMA_5
from eight_characters.accounts.billing_storage import restore_billing
from eight_characters.accounts.records import RecordError, canonical_json, new_id
from eight_characters.accounts.restore import RestoreError, restore_backup
from eight_characters.accounts.store import AccountStore, BillingReadOnly, StoreError
from eight_characters.accounts.web import Accounts, ConfigError, load_config
from tests.accounts_support import account_environment, all_object_contents, git
from tests.test_accounts_backup import BackupTestCase

NOW = '2026-10-19T10:00:00Z'


def offer():
    value = dict(
        plan='plus',
        period='monthly',
        price_id='price_plusMonth',
        product_id='product_plus',
        currency='usd',
        amount=1499,
        interval='month',
        interval_count=1,
        tax_behavior='exclusive',
    )
    return OfferSnapshot(id=hashlib.sha256(canonical_json(value)).hexdigest(), **value)


def records(owner):
    shared = dict(revision=0, created_at=NOW, updated_at=NOW)
    scope_id = new_id()
    scope = ScopeRecord(
        id=scope_id,
        scope_id=scope_id,
        **shared,
        account_id='acct_sandbox',
        livemode=False,
        api_version='2026-09-30.endive',
        binding_key_id='a' * 64,
        clock_ids=('clock_one',),
        offers=(offer(),),
        reconciled_started_at=None,
    )
    account = AccountBillingRecord(
        id=owner.id,
        owner_id=owner.id,
        scope_id=scope.id,
        **shared,
        customer_id='cus_one',
        test_clock_id='clock_one',
        lifecycle='active',
        binding=Binding(
            operation_id=new_id(), object_id='cus_one', state='sealed', mac='b' * 64
        ),
        intents=(),
        operations=(),
        coverage=(),
        deletion=None,
    )
    event = EventRecord(
        id=new_id(),
        scope_id=scope.id,
        **shared,
        event_id='evt_one',
        event_type='invoice.paid',
        object_id='in_one',
        owner_id=owner.id,
        state='pending',
        attempts=0,
        next_attempt_at=None,
        body_sha256='c' * 64,
        reason=None,
    )
    return scope, account, event


class BillingRecovery(BackupTestCase):
    def future(self, *, tombstone=False, sequence=100):
        user = self.store.create_user('private.person@example.invalid', 'fi')
        self.backup()
        data = records(user)
        if tombstone:
            value = data[1].model_dump(mode='json', by_alias=True)
            value.update(
                lifecycle='deleted',
                deletion=dict(
                    requested_at=NOW,
                    completed_at=NOW,
                    nonce=new_id(),
                    native_object_id='cus_one',
                    native_marker='d' * 64,
                    retain_until=None,
                ),
            )
            data = (data[0], decode_billing(canonical_json(value)), data[2])
        connection = sqlite3.connect(self.store.path)
        try:
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('BEGIN IMMEDIATE')
            for statement in BILLING_SCHEMA_5:
                connection.execute(statement)
            connection.execute('PRAGMA user_version=5')
            if tombstone:
                connection.execute('DELETE FROM users WHERE id=?', (user.id,))
                connection.execute(
                    'INSERT INTO changes(kind,record_id,path) VALUES (?,?,?)',
                    ('user', user.id, f'users/{user.id[:2]}/{user.id}/user.json'),
                )
            restore_billing(connection, data)
            # Model a future producer after pruning at a nonzero high-water.
            connection.execute('DELETE FROM changes')
            connection.execute(
                "UPDATE sqlite_sequence SET seq=? WHERE name='changes'", (sequence,)
            )
            connection.execute(
                'UPDATE backup_progress SET backed_up_seq=? WHERE id=1', (sequence,)
            )
            if tombstone:
                connection.execute(
                    'INSERT INTO changes(kind,record_id,path) VALUES (?,?,?)',
                    ('user', user.id, f'users/{user.id[:2]}/{user.id}/user.json'),
                )
            for record in data:
                connection.execute(
                    'INSERT INTO changes(kind,record_id,path) VALUES (?,?,?)',
                    ('billing', record.id, billing_path(record.id)),
                )
            connection.commit()
        finally:
            connection.close()
        return user, data

    def test_normal_open_and_backup_stay_schema4_manifest1(self):
        self.store.create_user('legacy@example.invalid', 'fi')
        self.backup()
        before = git(self.checkout, 'rev-parse', 'HEAD^{tree}')
        AccountStore.open(self.store.path)
        self.backup()
        self.assertEqual(before, git(self.checkout, 'rev-parse', 'HEAD^{tree}'))
        self.assertEqual(self.store.schema_version(), 4)
        self.assertIsNone(read_manifest(self.checkout).billing_count)
        self.assertFalse((self.checkout / 'billing').exists())

    def test_preopened_handle_fences_future_business_writes_and_unknown_reads(self):
        user, _ = self.future()
        for action in [
            lambda: self.store.delete_user(user.id),
            lambda: self.store.set_plan(user.id, 'pro'),
            lambda: self.store.set_language(user.id, 'en'),
        ]:
            with self.assertRaises(BillingReadOnly):
                action()
        self.assertEqual(self.store.user_by_id(user.id), user)
        self.backup()  # Progress commits remain permitted.
        with sqlite3.connect(self.store.path) as connection:
            connection.execute('PRAGMA user_version=6')
        with self.assertRaises(StoreError):
            self.store.users()

    def test_exact_future_layout_required_not_just_version(self):
        self.future()
        AccountStore.open(self.store.path)
        with sqlite3.connect(self.store.path) as connection:
            connection.execute('CREATE INDEX unreviewed ON users(language)')
        with self.assertRaises(StoreError):
            AccountStore.open(self.store.path)
        with self.assertRaises(StoreError):
            self.store.backup_snapshot()

    def test_future_roundtrip_keeps_all_families_highwater_and_next_update(self):
        user, data = self.future()
        result = run_backup(self.store, self.checkout, self.recipient)
        manifest = read_manifest(self.checkout)
        self.assertEqual((manifest.user_count, manifest.billing_count), (1, 3))
        self.assertEqual((manifest.backup_seq, manifest.sequence), (103, 103))
        self.assertEqual(result.written, 3)
        for record in data:
            ciphertext = (
                self.checkout / (billing_path(record.id) + '.age')
            ).read_bytes()
            self.assertEqual(
                pyrage.decrypt(ciphertext, [self.identity]), encode_billing(record)
            )
        target = self.directory / 'recovered.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        recovered = AccountStore.open(target)
        self.assertEqual(
            recovered.billing_records(), tuple(sorted(data, key=lambda r: r.id))
        )
        self.assertEqual(recovered.backup_snapshot().after_seq, 103)
        self.assertEqual(recovered.backup_snapshot().sequence, 103)
        with sqlite3.connect(target) as connection:
            ready, epoch = connection.execute(
                'SELECT ready,epoch FROM billing_runtime'
            ).fetchone()
            self.assertEqual(ready, 0)
            self.assertEqual(
                connection.execute('SELECT COUNT(*) FROM billing_leases').fetchone()[0],
                0,
            )
        repeated = run_backup(recovered, self.checkout, self.recipient)
        self.assertEqual(
            (repeated.written, repeated.removed, repeated.commit), (0, 0, None)
        )
        with sqlite3.connect(target) as connection:
            connection.execute(
                'UPDATE users SET language=? WHERE id=?', ('en', user.id)
            )
            connection.execute(
                'INSERT INTO changes(kind,record_id,path) VALUES (?,?,?)',
                ('user', user.id, f'users/{user.id[:2]}/{user.id}/user.json'),
            )
        written = run_backup(recovered, self.checkout, self.recipient)
        self.assertEqual((written.written, written.backed_up_seq), (1, 104))
        second = self.directory / 'again.sqlite3'
        restore_backup(self.checkout, self.identity, second)
        again = AccountStore.open(second)
        self.assertEqual(again.user_by_id(user.id).language, 'en')
        with sqlite3.connect(second) as connection:
            self.assertNotEqual(
                connection.execute('SELECT epoch FROM billing_runtime').fetchone()[0],
                epoch,
            )

    def test_tombstone_only_backup_survives_squash_and_restore(self):
        user, data = self.future(tombstone=True)
        self.backup()
        self.assertFalse((self.checkout / f'users/{user.id[:2]}/{user.id}').exists())
        squash_history(self.store, self.checkout)
        target = self.directory / 'deleted.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        recovered = AccountStore.open(target)
        self.assertEqual(recovered.users(), [])
        self.assertEqual(
            recovered.billing_records(), tuple(sorted(data, key=lambda r: r.id))
        )
        self.assertEqual(
            (
                read_manifest(self.checkout).user_count,
                len(billing_files(self.checkout)),
            ),
            (0, 3),
        )

    def test_sequence_corruption_is_loud_before_a_change_can_be_skipped(self):
        self.store.create_user('one@example.invalid', 'fi')
        self.backup()
        with sqlite3.connect(self.store.path) as connection:
            connection.execute("UPDATE sqlite_sequence SET seq=0 WHERE name='changes'")
        with self.assertRaisesRegex(StoreError, 'high-water'):
            self.store.backup_snapshot()

    def test_legacy_restore_resets_sequence_and_financial_writer_is_absent(self):
        self.store.create_user('one@example.invalid', 'fi')
        self.backup()
        target = self.directory / 'legacy.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        recovered = AccountStore.open(target)
        self.assertEqual(
            (recovered.schema_version(), recovered.backup_snapshot().after_seq), (4, 0)
        )
        self.assertEqual(recovered.billing_records(), ())

    def test_canonical_types_fields_and_secret_values_are_refused(self):
        user = self.store.create_user('one@example.invalid', 'fi')
        data = records(user)
        for record in data:
            self.assertEqual(decode_billing(encode_billing(record)), record)
        value = json.loads(encode_billing(data[0]))
        for key, bad in [
            ('schema', True),
            ('revision', True),
            ('livemode', 0),
            ('record_type', 'unknown'),
            ('account_id', 'sk_test_DO_NOT_LOG'),
        ]:
            malformed = {**value, key: bad}
            with self.assertRaises(RecordError) as failure:
                decode_billing(canonical_json(malformed))
            self.assertNotIn('DO_NOT_LOG', str(failure.exception))
        with self.assertRaises(RecordError):
            decode_billing(
                canonical_json({**value, 'raw_webhook': {'secret': 'never'}})
            )
        with self.assertRaises(RecordError):
            decode_billing(encode_billing(data[0]).rstrip())

    def test_cross_owner_native_claim_and_resurrected_tombstone_are_refused(self):
        first = self.store.create_user('a@example.invalid', 'fi')
        second = self.store.create_user('b@example.invalid', 'fi')
        scope, owner, event = records(first)
        other = owner.model_copy(update={'id': second.id, 'owner_id': second.id})
        with self.assertRaises(RecordError):
            validate_billing_graph((scope, owner, other, event), (first, second))
        deleted = owner.model_copy(
            update={
                'lifecycle': 'deleted',
                'deletion': Deletion(
                    requested_at=NOW,
                    completed_at=NOW,
                    nonce=new_id(),
                    native_object_id='cus_one',
                    native_marker='a' * 64,
                    retain_until=None,
                ),
            }
        )
        with self.assertRaises(RecordError):
            validate_billing_graph((scope, deleted, event), (first,))

    def test_corrupt_projection_halts_backup_and_no_private_data_enters_git(self):
        self.future()
        self.backup()
        for repository in (self.checkout, self.remote):
            content = all_object_contents(repository)
            for forbidden in [
                b'private.person',
                b'cus_one',
                b'"customer_id"',
                b'whsec_',
            ]:
                self.assertNotIn(forbidden, content)
        with sqlite3.connect(self.store.path) as connection:
            connection.execute('DELETE FROM billing_jobs')
        with self.assertRaises(StoreError):
            self.backup()

    def test_schema5_http_service_refuses_legacy_allowance_fallback(self):
        self.future()
        environment = account_environment(self.directory)
        with self.assertRaisesRegex(ConfigError, 'cannot serve'):
            Accounts.open(load_config(environment))

    def test_late_bad_encrypted_record_publishes_no_restored_database(self):
        _, data = self.future()
        self.backup()
        bad = self.checkout / (billing_path(data[-1].id) + '.age')
        bad.write_bytes(pyrage.encrypt(b'{"invalid":true}', [self.recipient]))
        self.commit_by_hand('invalid final billing record')
        target = self.directory / 'bad.sqlite3'
        with self.assertRaises(RestoreError):
            restore_backup(self.checkout, self.identity, target)
        self.assertFalse(target.exists())
        self.assertFalse(target.with_name(target.name + '.partial').exists())

    def test_interrupted_mixed_family_write_recovers_without_partial_success(self):
        self.future()
        original = pyrage.encrypt
        calls = 0

        def interrupted(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('interrupted between billing records')
            return original(*args, **kwargs)

        with patch(
            'eight_characters.accounts.backup.pyrage.encrypt', side_effect=interrupted
        ):
            with self.assertRaises(OSError):
                self.backup()
        self.backup()
        target = self.directory / 'after-interruption.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        self.assertEqual(len(AccountStore.open(target).billing_records()), 3)

    def test_future_journal_failure_publishes_no_database(self):
        user = self.store.create_user('one@example.invalid', 'fi')
        target = self.directory / 'never.sqlite3'
        with patch(
            'eight_characters.accounts.store.restore_billing',
            side_effect=StoreError('injected'),
        ):
            with self.assertRaises(StoreError):
                AccountStore.restore(
                    target, [(user, None)], head='a' * 40, billing=records(user)
                )
        self.assertFalse(target.exists())
        self.assertFalse(target.with_name(target.name + '.partial').exists())


if __name__ == '__main__':
    unittest.main()
