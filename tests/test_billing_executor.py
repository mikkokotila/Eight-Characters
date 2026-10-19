"""Actual SQLite reservations around injected HTTP, without native proof claims."""

from unittest.mock import patch
from urllib.parse import parse_qs

import httpx

from eight_characters.accounts.billing_access import BillingHold
from eight_characters.accounts.billing_authority import Authority
from eight_characters.accounts.billing_executor import Work
from eight_characters.accounts.billing_native import Stripe
from eight_characters.accounts.restore import restore_backup
from eight_characters.accounts.store import AccountStore
from tests.test_billing_authority import AuthorityCase


class NativeExecution(AuthorityCase):
    def prepared_before_send(self):
        work = self.work(self.response)
        original = work.save
        writes = 0

        def crash(owner):
            nonlocal writes
            writes += 1
            if writes == 2:
                raise RuntimeError('injected crash before sent commit')
            original(owner)

        with patch.object(work, 'save', side_effect=crash):
            with self.assertRaises(RuntimeError):
                work.execute('customer_create')
        self.assertEqual(work.owner.operations[0].state, 'prepared')
        self.assertIsNone(work.owner.operations[0].sent_at)
        self.authority.release(work.lease)
        self.clock.advance(86401)
        return work

    def test_proven_unsent_work_survives_normal_restart_after_key_retention(self):
        old = self.prepared_before_send()
        authority = Authority(self.store, self.config, clock=self.clock)
        epoch = authority.begin_recovery()
        lease, owner = authority.claim(self.user.id, recovery_epoch=epoch)
        work = Work(authority, old.native, old.origin, old.scope, lease, owner, True)
        work.execute('customer_create')
        self.assertEqual(work.owner.customer_id, 'cus_created')
        self.assertEqual(
            work.owner.operations[0].idempotency_key,
            old.owner.operations[0].idempotency_key,
        )
        self.assertEqual(
            work.owner.operations[0].request_sha256,
            old.owner.operations[0].request_sha256,
        )
        authority.release(work.lease)

    def test_restored_prepared_flag_is_not_proof_that_native_http_never_happened(self):
        old = self.prepared_before_send()
        self.backup()
        target = self.directory / 'restored-prepared.sqlite3'
        restore_backup(self.checkout, self.identity, target)
        authority = Authority(AccountStore.open(target), self.config, clock=self.clock)
        epoch = authority.begin_recovery()
        lease, owner = authority.claim(self.user.id, recovery_epoch=epoch)
        work = Work(authority, old.native, old.origin, old.scope, lease, owner, True)
        self.assertFalse(authority.unsent_is_proven(lease))
        with self.assertRaises(BillingHold):
            work.execute('customer_create')
        self.assertIsNone(work.owner.customer_id)
        authority.release(work.lease)

    def test_native_history_longer_than_one_lease_keeps_a_live_fenced_claim(self):
        calls = []

        def slow(request):
            calls.append(request.url.path)
            self.clock.advance(self.config.lease_seconds - 1)
            if request.method == 'GET':
                return httpx.Response(
                    200,
                    json={'object': 'account', 'id': self.config.catalogue.account_id},
                    headers={'Stripe-Version': self.config.catalogue.api_version},
                )
            return self.response(request)

        work = self.work(slow)
        for _ in range(5):
            work.native.account()
        work.execute('customer_create')
        self.assertEqual(work.owner.customer_id, 'cus_created')
        self.assertEqual(len(calls), 6)
        self.authority.release(work.lease)

    def test_renewal_cannot_revive_expired_or_replaced_work(self):
        work = self.work(self.response)
        self.clock.advance(self.config.lease_seconds + 1)
        with self.assertRaises(BillingHold):
            work.renew()
        lease, _ = self.authority.claim(self.user.id)
        with self.assertRaises(BillingHold):
            work.renew()
        self.authority.release(lease)

    def work(self, callback):
        client = httpx.Client(transport=httpx.MockTransport(callback))
        self.addCleanup(client.close)
        lease, owner = self.authority.claim(self.user.id)
        return Work(
            self.authority,
            Stripe(self.config, client),
            'https://testserver',
            self.authority.scope(self.authority.snapshot()[0]),
            lease,
            owner,
            True,
        )

    def response(self, request, *, customer_id='cus_created'):
        params = {
            key: values[0] for key, values in parse_qs(request.content.decode()).items()
        }
        metadata = {
            key[9:-1]: value
            for key, value in params.items()
            if key.startswith('metadata[')
        }
        return httpx.Response(
            200,
            json={
                'id': customer_id,
                'object': 'customer',
                'livemode': False,
                'test_clock': None,
                'metadata': metadata,
            },
            headers={'Stripe-Version': self.config.catalogue.api_version},
        )

    def test_request_is_durable_before_http_and_unrelated_owner_can_write(self):
        def callback(request):
            owner = next(
                record
                for record in self.store.billing_records()
                if record.id == self.user.id
            )
            self.assertEqual(owner.operations[0].state, 'sent')
            self.assertEqual(
                owner.operations[0].idempotency_key, request.headers['Idempotency-Key']
            )
            other_lease, other_owner = self.authority.claim(self.other.id)
            self.authority.apply(other_lease, other_owner)
            return self.response(request)

        self.authority.ensure_owner(self.other.id)
        work = self.work(callback)
        result = work.execute('customer_create')
        self.assertEqual(work.owner.customer_id, result['id'])
        self.assertEqual(work.owner.binding.state, 'unsealed')
        self.assertEqual(work.owner.operations[0].state, 'done')
        self.authority.release(work.lease)

    def test_lost_response_reuses_exact_parameters_and_original_key_after_discovery(
        self,
    ):
        calls = []

        def callback(request):
            calls.append((request.headers['Idempotency-Key'], request.content))
            if len(calls) == 1:
                raise httpx.ReadTimeout('injected lost response')
            return self.response(request)

        work = self.work(callback)
        with self.assertRaises(BillingHold):
            work.execute('customer_create')
        work.discovered = False
        with self.assertRaises(BillingHold):
            work.execute('customer_create')
        self.assertEqual(len(calls), 1)
        work.discovered = True
        work.execute('customer_create')
        self.assertEqual(calls[0], calls[1])
        self.assertEqual(len(work.owner.operations), 1)
        self.authority.release(work.lease)

    def test_no_replay_or_new_key_after_retention_and_no_late_attach_after_delete(self):
        calls = []

        def timeout(request):
            calls.append(request.headers['Idempotency-Key'])
            raise httpx.ReadTimeout('injected')

        work = self.work(timeout)
        with self.assertRaises(BillingHold):
            work.execute('customer_create')
        self.clock.advance(86401)
        lease, owner = self.authority.claim(self.user.id)
        work.lease, work.owner = lease, owner
        with self.assertRaises(BillingHold):
            work.execute('customer_create')
        self.assertEqual(len(calls), 1)
        self.authority.release(work.lease)

        def deleting(request):
            self.authority.request_deletion(self.user.id)
            return self.response(request)

        other = self.work(deleting)
        # A distinct owner is unnecessary: this retained operation is expired and
        # must not send. Exercise a fresh reservation in a new local fixture below.
        with self.assertRaises(BillingHold):
            other.execute('customer_create')
        self.authority.release(other.lease)

    def test_delete_gate_committed_during_http_rejects_the_late_customer_response(self):
        def callback(request):
            self.authority.request_deletion(self.user.id)
            return self.response(request)

        work = self.work(callback)
        with self.assertRaises(BillingHold):
            work.execute('customer_create')
        owner = next(
            record
            for record in self.store.billing_records()
            if record.id == self.user.id
        )
        self.assertEqual(owner.lifecycle, 'deleting')
        self.assertIsNone(owner.customer_id)
        self.assertEqual(owner.operations[0].state, 'sent')
