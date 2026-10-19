"""Actual SQLite/age/Git durability with injected provider work boundaries."""

import sqlite3
from unittest.mock import patch

from eight_characters.accounts.billing_access import BillingHold
from eight_characters.accounts.billing_authority import Authority
from eight_characters.accounts.billing_records import Binding, Deletion, RefundFact
from eight_characters.accounts.billing_schema import BILLING_SCHEMA_5
from eight_characters.accounts.billing_storage import restore_billing
from eight_characters.accounts.billing_webhook import Delivery
from eight_characters.accounts.records import new_id, timestamp
from eight_characters.accounts.restore import restore_backup
from eight_characters.accounts.store import AccountStore
from tests.test_accounts_backup import BackupTestCase
from tests.test_accounts_billing_recovery import records
from tests.test_billing_access import configuration


class AuthorityCase(BackupTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.store.create_user('fixture@example.invalid', 'fi')
        self.other = self.store.create_user('other@example.invalid', 'en')
        with sqlite3.connect(self.store.path) as connection:
            for statement in BILLING_SCHEMA_5:
                connection.execute(statement)
            connection.execute('PRAGMA user_version=5')
            restore_billing(connection, ())
        self.config = configuration()
        self.authority = Authority(self.store, self.config, clock=self.clock)
        self.epoch = self.authority.begin_recovery()
        self.owner = self.authority.ensure_owner(self.user.id)
        self.authority.finish_recovery(
            self.epoch, started_at=int(self.clock().timestamp())
        )

    def bound(self):
        lease, owner = self.authority.claim(self.user.id)
        binding = Binding(
            operation_id=new_id(), object_id='cus_one', state='sealed', mac='a' * 64
        )
        self.authority.apply(
            lease,
            owner.model_copy(update={'customer_id': 'cus_one', 'binding': binding}),
        )
        return self.authority.claim(self.user.id)

    def receipt(self):
        scope = self.authority.scope(self.authority.snapshot()[0])
        offer = next(
            offer
            for offer in scope.offers
            if offer.plan == 'plus' and offer.period == 'monthly'
        )
        return (
            records(self.user)[1]
            .coverage[0]
            .model_copy(update={'price_id': offer.price_id, 'offer_id': offer.id})
        )


class FencedAuthority(AuthorityCase):
    def test_delete_during_unknown_customer_creation_fences_the_original_worker(self):
        lease, owner = self.authority.claim(self.user.id)
        deleting = self.authority.request_deletion(self.user.id)
        self.assertEqual(deleting.schema_version, 2)
        self.assertEqual(deleting.lifecycle, 'deleting')
        self.assertIsNone(deleting.deletion.native_object_id)
        self.assertIsNone(deleting.deletion.native_marker)
        self.assertEqual(self.authority.request_deletion(self.user.id), deleting)
        with self.assertRaises(BillingHold):
            self.authority.apply(lease, owner)
        self.assertIsNotNone(self.store.user_by_id(self.user.id))
        self.backup()
        target = self.directory / 'pending-delete.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        restored = next(
            record
            for record in AccountStore.open(target).billing_records()
            if record.id == self.user.id
        )
        self.assertEqual(restored, deleting)

    def test_retry_is_durable_and_pending_delivery_never_becomes_applied(self):
        lease, _ = self.bound()
        self.authority.release(lease)
        self.authority.enqueue(
            Delivery('evt_retry', 'invoice.paid', 'in_one', 'cus_one', 'e' * 64, True)
        )
        for attempt in range(1, 9):
            lease, owner = self.authority.claim(self.user.id)
            self.authority.defer(lease, 'native_unavailable')
            event = next(
                record
                for record in self.store.billing_records()
                if getattr(record, 'event_id', None) == 'evt_retry'
            )
            self.assertEqual(
                (event.state, event.attempts, event.reason),
                ('pending', attempt, 'native_unavailable'),
            )
            self.assertEqual(
                event.next_attempt_at - int(self.clock().timestamp()),
                min(300, 5 * 2 ** (attempt - 1)),
            )
            owner = next(
                record
                for record in self.store.billing_records()
                if record.id == owner.id
            )
            self.assertEqual(owner.lifecycle, 'held')
        self.authority.hold_runtime(self.epoch, 'permission_missing')
        self.assertFalse(self.authority.snapshot()[2])
        with self.assertRaises(BillingHold):
            self.authority.claim(self.user.id)

    def test_closed_startup_gate_and_restored_epoch_refuse_old_work(self):
        lease, owner = self.bound()
        epoch = self.authority.begin_recovery()
        self.assertNotEqual(epoch, lease.epoch)
        with self.assertRaises(BillingHold):
            self.authority.apply(lease, owner)
        with self.assertRaises(BillingHold):
            self.authority.claim(self.user.id)
        self.backup()
        target = self.directory / 'restored.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        recovered = Authority(AccountStore.open(target), self.config, clock=self.clock)
        self.assertFalse(recovered.snapshot()[2])
        with self.assertRaises(BillingHold):
            recovered.apply(lease, owner)

    def test_takeover_prevents_late_paid_apply_after_refund(self):
        stale, owner = self.bound()
        paid = self.receipt()
        other_process = Authority(
            AccountStore.open(self.store.path), self.config, clock=self.clock
        )
        with self.assertRaises(BillingHold):
            other_process.claim(self.user.id)
        self.clock.advance(self.config.lease_seconds + 1)
        current, same_owner = other_process.claim(self.user.id)
        refunded = paid.model_copy(
            update={
                'refunds': (RefundFact(id='re_full', amount=1499, status='succeeded'),)
            }
        )
        other_process.apply(
            current, same_owner.model_copy(update={'coverage': (refunded,)})
        )
        with self.assertRaises(BillingHold):
            self.authority.apply(stale, owner.model_copy(update={'coverage': (paid,)}))
        owner = next(
            record
            for record in self.authority.snapshot()[0]
            if record.id == self.user.id
        )
        self.assertEqual(owner.coverage[0].refunds[0].status, 'succeeded')

    def test_duplicate_pending_delivery_stays_pending_and_apply_commits_its_log(self):
        lease, owner = self.bound()
        delivery = Delivery(
            'evt_one', 'invoice.paid', 'in_one', 'cus_one', 'e' * 64, True
        )
        first = self.authority.enqueue(delivery)
        pending = self.authority.enqueue(delivery)
        self.assertEqual(first, pending)
        self.assertEqual(pending.state, 'pending')
        with self.assertRaises(BillingHold):
            self.authority.apply(lease, owner)
        lease, owner = self.authority.claim(self.user.id)
        self.authority.apply(
            lease,
            owner.model_copy(update={'coverage': (self.receipt(),)}),
            applied_events=('evt_one',),
        )
        snapshot = self.store.backup_snapshot()
        event = next(
            record for record in self.store.billing_records() if record.id == first.id
        )
        self.assertEqual(event.state, 'applied')
        self.assertEqual(self.authority.enqueue(delivery).state, 'applied')
        self.assertTrue(any(change.billing is not None for change in snapshot.changes))

    def test_queue_commit_failure_keeps_no_false_acknowledgment_record(self):
        self.bound()
        delivery = Delivery(
            'evt_abort', 'invoice.paid', 'in_one', 'cus_one', 'e' * 64, True
        )
        with patch(
            'eight_characters.accounts.billing_authority.log_record_change',
            side_effect=sqlite3.OperationalError('injected commit boundary'),
        ):
            with self.assertRaises(sqlite3.OperationalError):
                self.authority.enqueue(delivery)
        self.assertFalse(
            any(
                getattr(record, 'event_id', None) == 'evt_abort'
                for record in self.store.billing_records()
            )
        )

    def test_deletion_tombstone_and_personal_removal_share_one_transaction(self):
        lease, owner = self.bound()
        now = timestamp(self.clock())
        deletion = Deletion(
            requested_at=now,
            completed_at=None,
            nonce=new_id(),
            native_object_id='cus_one',
            native_marker='d' * 64,
            retain_until=None,
        )
        self.authority.apply(
            lease,
            owner.model_copy(update={'lifecycle': 'deleting', 'deletion': deletion}),
        )
        lease, deleting = self.authority.claim(self.user.id)
        self.authority.apply(
            lease,
            deleting.model_copy(
                update={
                    'lifecycle': 'deleted',
                    'deletion': deletion.model_copy(update={'completed_at': now}),
                }
            ),
            remove_user=True,
        )
        self.assertIsNone(self.store.user_by_id(self.user.id))
        self.assertIsNotNone(self.store.user_by_id(self.other.id))
        self.backup()
        target = self.directory / 'deleted.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        recovered = AccountStore.open(target)
        tombstone = next(
            record
            for record in recovered.billing_records()
            if record.id == self.user.id
        )
        self.assertEqual(tombstone.lifecycle, 'deleted')
        self.assertIsNone(recovered.user_by_id(self.user.id))

    def test_unknown_signed_events_are_durable_explicit_quarantines(self):
        event = self.authority.enqueue(
            Delivery('evt_unknown', 'invoice.paid', 'in_other', None, 'e' * 64, True)
        )
        self.assertEqual((event.state, event.reason), ('quarantined', 'unknown_owner'))
