"""Explicit private acceptance: real Stripe reads, local HTTP and trace evidence.

Run with EC_BILLING_ACCEPTANCE_PROFILE pointing to the protected isolated-run
profile. Missing credentials, native scenarios or signed delivery fail, never
skip. Ordinary CI does not discover this opt-in, non-test-prefixed module.
"""

import hashlib
import json
import os
import unittest
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from eight_characters.accounts.billing import OFFERS
from eight_characters.accounts.billing_access import check_scope, effective_access
from eight_characters.accounts.billing_authority import Authority
from eight_characters.accounts.billing_native import Stripe, captured_coverage
from eight_characters.accounts.billing_reconciliation import discover_customers
from eight_characters.accounts.billing_records import AccountBillingRecord, EventRecord
from eight_characters.accounts.store import AccountStore
from eight_characters.accounts.web import load_config

REQUIRED_TRACES = frozenset(
    (
        'six_offers',
        'wrong_owner',
        'failed_and_sca_payment',
        'renewal_gap_and_recovery',
        'sequential_and_concurrent_offers',
        'uncertain_customer_before_and_after_retention',
        'uncertain_session_before_and_after_retention',
        'late_success_and_paginated_discovery',
        'multiple_clocks_and_customer_limit',
        'historical_archived_and_replaced_prices',
        'unsupported_funding',
        'cumulative_and_reversed_refunds',
        'dispute_inquiry_won_and_lost',
        'expiry_without_webhook',
        'worker_crash_and_lease_takeover',
        'stale_paid_after_refund',
        'equal_second_events',
        'two_process_contention',
        'restore_before_purchase_refund_and_deletion',
        'delete_before_customer_identity',
        'delete_racing_checkout_and_collection',
        'mode_account_namespace_and_key_refusal',
        'clock_disappearance',
    )
)


class NativeBillingAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile_path = Path(os.environ['EC_BILLING_ACCEPTANCE_PROFILE'])
        if profile_path.stat().st_mode & 0o077:
            raise RuntimeError('The native acceptance profile must be private.')
        cls.profile = json.loads(profile_path.read_text())
        cls.folder = Path(cls.profile['directory']).resolve()
        address = urlsplit(cls.profile['origin'])
        if address.scheme != 'http' or address.hostname not in ('127.0.0.1', '::1'):
            raise RuntimeError('Native acceptance requires an isolated loopback app.')
        if cls.profile['production_billing_enabled'] is not False:
            raise RuntimeError('This acceptance run cannot enable production billing.')
        config = load_config(cls.profile['environment'])
        if config.billing is None:
            raise RuntimeError('Native acceptance requires sandbox billing.')
        cls.config = config.billing
        cls.http = httpx.Client(timeout=20)
        cls.addClassCleanup(cls.http.close)
        cls.native = Stripe(cls.config, cls.http)
        cls.store = AccountStore.open(
            config.database,
            billing_config=cls.config,
            billing_clock=cls.native.clock,
        )
        authority = Authority(cls.store, cls.config, clock=lambda: datetime.now(UTC))
        cls.records, _, cls.ready = authority.snapshot()
        cls.scope = authority.scope(cls.records)
        cls.owners = {
            record.id: record
            for record in cls.records
            if isinstance(record, AccountBillingRecord)
        }

    def test_native_scope_and_two_immutable_bindings(self):
        self.native.account()
        check_scope(self.config, self.scope)
        self.assertTrue(self.ready, 'Native startup recovery remains incomplete.')
        self.assertEqual(set(self.profile['accounts']), {'A', 'B'})
        expected = {value['owner_id'] for value in self.profile['accounts'].values()}
        self.assertEqual(set(self.owners), expected)
        proofs = discover_customers(self.native, self.scope)
        self.assertEqual({proof.owner_id for proof in proofs}, expected)
        self.assertTrue(all(proof.sealed for proof in proofs))
        self.assertEqual(len({proof.customer_id for proof in proofs}), 2)

    def test_all_six_offers_have_fresh_native_captured_card_evidence(self):
        funded = set()
        for owner in self.owners.values():
            subscriptions = self.native.all(
                'subscriptions', {'customer': owner.customer_id, 'status': 'all'}
            )
            for retained in owner.coverage:
                invoice = self.native.request('GET', 'invoices/' + retained.invoice_id)
                fact = captured_coverage(
                    self.native,
                    invoice,
                    customer_id=owner.customer_id,
                    subscriptions={item['id']: item for item in subscriptions},
                    offers=self.scope.offers,
                    verified_at=datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
                )
                self.assertEqual(
                    fact.model_dump(exclude={'verified_at'}),
                    retained.model_dump(exclude={'verified_at'}),
                )
                offer = next(
                    item for item in self.scope.offers if item.id == fact.offer_id
                )
                funded.add((offer.plan, offer.period))
        self.assertEqual(funded, {(offer.plan, offer.period) for offer in OFFERS})

    def test_actual_account_status_uses_the_verified_authority(self):
        for account in self.profile['accounts'].values():
            owner = self.owners[account['owner_id']]
            now = (
                int(datetime.now(UTC).timestamp())
                if owner.test_clock_id is None
                else self.native.clock(owner.test_clock_id)
            )
            expected = effective_access(self.scope, owner, now=now, ready=self.ready)
            response = self.http.get(
                self.profile['origin'] + '/api/account/settings',
                cookies=account['session_cookies'],
            )
            if owner.lifecycle == 'deleted':
                self.assertEqual(response.status_code, 401)
            else:
                self.assertEqual(response.status_code, 200)
                value = response.json()
                self.assertEqual(value['billing']['tier'], expected.tier)
                self.assertEqual(value['billing']['status'], expected.status)
                self.assertEqual(value['chart_limit'], expected.chart_limit)

    def test_native_signed_deliveries_are_durable_and_applied(self):
        self.assertTrue(
            self.profile['native_webhook_configured'],
            'Actual provider-signed CLI forwarding has not been verified.',
        )
        for event_type in (
            'checkout.session.completed',
            'invoice.paid',
            'charge.refunded',
        ):
            native_events = {
                event['id']: event
                for event in self.native.all('events', {'type': event_type})
            }
            applied = [
                record
                for record in self.records
                if isinstance(record, EventRecord)
                and record.state == 'applied'
                and record.event_type == event_type
                and record.owner_id in self.owners
            ]
            self.assertTrue(applied, 'No applied native delivery for ' + event_type)
            for record in applied:
                event = native_events[record.event_id]
                self.assertIs(event['livemode'], False)
                self.assertEqual(event['api_version'], self.config.payload_version)
                self.assertIn(
                    event.get('account'), (None, self.config.catalogue.account_id)
                )
                self.assertIsNone(event.get('context'))
                self.assertEqual(
                    event['data']['object']['customer'],
                    self.owners[record.owner_id].customer_id,
                )

    def test_every_agreed_native_trace_has_its_actual_evidence(self):
        # Native rereads above establish money/bindings. These protected trace
        # artifacts preserve transient refusal, crash and restore observations
        # that cannot be reconstructed from the final provider state alone.
        manifest_path = self.folder / 'native-trace-manifest.json'
        self.assertTrue(
            manifest_path.is_file(), 'The full native trace run is incomplete.'
        )
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest['namespace'], self.config.namespace)
        self.assertEqual(set(manifest['cases']), REQUIRED_TRACES)
        for name, evidence in manifest['cases'].items():
            path = (self.folder / evidence['file']).resolve()
            self.assertTrue(path.is_relative_to(self.folder))
            body = path.read_bytes()
            self.assertEqual(hashlib.sha256(body).hexdigest(), evidence['sha256'], name)
            trace = json.loads(body)
            self.assertEqual(trace['case'], name)
            self.assertEqual(trace['namespace'], self.config.namespace)
            self.assertTrue(trace['native_request_ids'], name)
            self.assertTrue(trace['assertions'], name)
            for assertion in trace['assertions']:
                self.assertEqual(assertion['observed'], assertion['expected'], name)


if __name__ == '__main__':
    unittest.main()
