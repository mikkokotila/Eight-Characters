"""Actual SQLite reservations around injected HTTP, without native proof claims."""

from urllib.parse import parse_qs

import httpx

from eight_characters.accounts.billing_access import BillingHold
from eight_characters.accounts.billing_executor import Work
from eight_characters.accounts.billing_native import Stripe
from tests.test_billing_authority import AuthorityCase


class NativeExecution(AuthorityCase):
    def work(self, callback):
        client = httpx.Client(transport=httpx.MockTransport(callback))
        self.addCleanup(client.close)
        lease, owner = self.authority.claim(self.user.id)
        return Work(self.authority, Stripe(self.config, client), 'https://testserver', self.authority.scope(self.authority.snapshot()[0]), lease, owner, True)

    def response(self, request, *, customer_id='cus_created'):
        params = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
        metadata = {key[9:-1]: value for key, value in params.items() if key.startswith('metadata[')}
        return httpx.Response(200, json={'id': customer_id, 'object': 'customer', 'livemode': False, 'test_clock': None, 'metadata': metadata}, headers={'Stripe-Version': self.config.catalogue.api_version})

    def test_request_is_durable_before_http_and_unrelated_owner_can_write(self):
        def callback(request):
            owner = next(record for record in self.store.billing_records() if record.id == self.user.id)
            self.assertEqual(owner.operations[0].state, 'sent')
            self.assertEqual(owner.operations[0].idempotency_key, request.headers['Idempotency-Key'])
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

    def test_lost_response_reuses_exact_parameters_and_original_key_after_discovery(self):
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
        owner = next(record for record in self.store.billing_records() if record.id == self.user.id)
        self.assertEqual(owner.lifecycle, 'deleting')
        self.assertIsNone(owner.customer_id)
        self.assertEqual(owner.operations[0].state, 'sent')
