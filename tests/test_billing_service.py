"""Actual account HTTP and SQLite against an injected provider, not native proof."""

import asyncio
import copy
import hashlib
import hmac
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs

import httpx
from fastapi.testclient import TestClient

import tests.test_billing_native as native_fixtures
from eight_characters.accounts.billing import OFFERS, BillingError
from eight_characters.accounts.billing_access import BillingBusy, BillingHold
from eight_characters.accounts.billing_executor import Work
from eight_characters.accounts.billing_records import AccountBillingRecord, EventRecord
from eight_characters.accounts.billing_webhook import Delivery
from eight_characters.accounts.store import AccountStore, ChartLimit
from eight_characters.accounts.web import (
    Accounts,
    account_key,
    get_accounts,
    load_config,
)
from eight_characters.main import app
from tests.accounts_support import (
    Clock,
    FakePersonCheck,
    account_environment,
    sign_in,
    site_client,
)
from tests.test_billing_access import configuration
from tests.test_billing_capacity import birth


class Provider:
    def __init__(self, config, clock):
        self.config, self.clock = config, clock
        self.customers, self.sessions, self.subscriptions, self.invoices = (
            {},
            {},
            {},
            {},
        )
        self.objects, self.collections = {}, {}
        self.calls = []
        self.slow_sessions = False
        self.session_pages = 0
        self.payment_methods = ['card']
        self.closed = False
        self.client = httpx.Client(transport=httpx.MockTransport(self.respond))

    def price(self, index, *, expand=False):
        offer = OFFERS[index]
        product = self.config.catalogue.product_ids[index // 2]
        return dict(
            id=self.config.catalogue.price_ids[index],
            object='price',
            livemode=False,
            active=True,
            currency='usd',
            unit_amount=offer.amount,
            unit_amount_decimal=str(offer.amount),
            type='recurring',
            billing_scheme='per_unit',
            tax_behavior='exclusive',
            custom_unit_amount=None,
            transform_quantity=None,
            tiers_mode=None,
            recurring={
                'interval': offer.interval,
                'interval_count': 1,
                'usage_type': 'licensed',
                'trial_period_days': None,
            },
            product={
                'id': product,
                'object': 'product',
                'active': True,
                'livemode': False,
            }
            if expand
            else product,
        )

    def respond(self, request):
        self.calls.append((request.method, request.url.path))
        path = request.url.path.removeprefix('/v1/')
        params = {
            key: values[0]
            for key, values in parse_qs(
                request.content.decode(), keep_blank_values=True
            ).items()
        }
        metadata = {
            key[9:-1]: value
            for key, value in params.items()
            if key.startswith('metadata[')
        }
        if path == 'account':
            value = {'object': 'account', 'id': self.config.catalogue.account_id}
        elif path.startswith('prices/'):
            index = self.config.catalogue.price_ids.index(path.split('/')[1])
            value = self.price(index, expand='expand[]' in request.url.params)
        elif path == 'customers' and request.method == 'POST':
            key = 'cus_' + str(len(self.customers) + 1)
            value = dict(
                id=key,
                object='customer',
                livemode=False,
                test_clock=params.get('test_clock'),
                metadata=metadata,
                email=None,
                name=None,
                phone=None,
                address=None,
                shipping=None,
                description=None,
            )
            self.customers[key] = value
        elif path.startswith('customers/'):
            value = self.customers[path.split('/')[1]]
            if request.method == 'POST':
                value['metadata'].update(metadata)
                for name in (
                    'email',
                    'name',
                    'phone',
                    'address',
                    'shipping',
                    'description',
                ):
                    if name in params:
                        value[name] = params[name] or None
        elif path == 'checkout/sessions' and request.method == 'POST':
            key = 'cs_test_' + str(len(self.sessions) + 1)
            value = dict(
                id=key,
                object='checkout.session',
                livemode=False,
                customer=params['customer'],
                metadata=metadata,
                mode='subscription',
                payment_method_types=self.payment_methods,
                subscription=None,
                status='open',
                created=int(self.clock().timestamp()),
                expires_at=int(params['expires_at']),
                url='https://checkout.stripe.com/c/pay/' + key,
            )
            self.sessions[key] = value
        elif path.startswith('checkout/sessions/'):
            value = self.sessions[path.split('/')[2]]
            if path.endswith('/expire'):
                value['status'] = 'expired'
            elif request.method == 'POST':
                value['metadata'].update(metadata)
        elif path.startswith('subscriptions/'):
            value = self.subscriptions[path.split('/')[1]]
            if request.method == 'DELETE':
                value['status'] = 'canceled'
            elif request.method == 'POST':
                value['cancel_at_period_end'] = (
                    params.get('cancel_at_period_end') == 'true'
                )
        elif path in self.objects:
            value = self.objects[path]
        else:
            rows = {
                'test_helpers/test_clocks': (),
                'events': (),
                'customers': tuple(self.customers.values()),
                'checkout/sessions': tuple(self.sessions.values()),
                'subscriptions': tuple(self.subscriptions.values()),
                'invoices': tuple(self.invoices.values()),
                **self.collections,
            }[path]
            customer = request.url.params.get('customer')
            if customer is not None:
                rows = tuple(row for row in rows if row.get('customer') == customer)
            value = {'object': 'list', 'has_more': False, 'data': rows}
            if path == 'checkout/sessions' and self.slow_sessions:
                self.clock.advance(self.config.lease_seconds - 1)
                self.session_pages += 1
                value = {
                    'object': 'list',
                    'has_more': 'starting_after' not in request.url.params,
                    'data': rows if 'starting_after' not in request.url.params else (),
                }
        return httpx.Response(
            200,
            json=value,
            headers={'Stripe-Version': self.config.catalogue.api_version},
        )

    def complete(self):
        graph = native_fixtures.FundingGraph(
            'test_archived_historical_offer_and_full_native_chain'
        )
        graph.setUp()
        try:
            self.objects = copy.deepcopy(graph.objects)
            self.collections = copy.deepcopy(graph.lists)
            invoice = copy.deepcopy(graph.invoice)
            subscription = copy.deepcopy(graph.subscription)
        finally:
            graph.doCleanups()
        session = next(iter(self.sessions.values()))
        customer = session['customer']
        session.update(status='complete', subscription='sub_one')
        subscription.update(customer=customer, cancel_at_period_end=False)
        invoice['customer'] = customer
        now = int(self.clock().timestamp())
        invoice['status_transitions']['paid_at'] = now
        line = self.collections['invoices/in_one/lines'][0]
        line['period'] = {'start': now, 'end': now + 3600}
        line['pricing']['price_details'].update(
            price=self.config.catalogue.price_ids[2],
            product=self.config.catalogue.product_ids[1],
        )
        self.collections['subscription_items'][0]['price'] = self.price(2)
        for key in ('payment_intents/pi_one', 'charges/ch_one'):
            self.objects[key]['customer'] = customer
        self.collections['invoice_payments'][0]['status_transitions']['paid_at'] = now
        self.invoices[invoice['id']] = invoice
        self.subscriptions[subscription['id']] = subscription


class ServiceApi(unittest.TestCase):
    def test_second_service_is_refused_without_invalidating_the_serving_epoch(self):
        before = self.service.authority.snapshot()[1:]
        with self.assertRaises(BillingBusy):
            Accounts.open(
                self.accounts.config,
                person_check=FakePersonCheck(),
                clock=self.clock,
                billing_client=self.provider.client,
            )
        self.assertEqual(self.service.authority.snapshot()[1:], before)
        self.assertEqual(self.checkout().status_code, 200)
        self.provider.complete()
        self.service.reconcile(self.user.id)
        self.assertEqual(self.accounts.store.capacity(self.user.id)[0].tier, 'plus')
        self.service.close()
        with self.assertRaises(BillingHold):
            self.service.tick()
        replacement = Accounts.open(
            self.accounts.config,
            person_check=FakePersonCheck(),
            clock=self.clock,
            billing_client=self.provider.client,
        ).billing
        self.addCleanup(replacement.close)
        self.assertNotEqual(replacement.epoch, self.service.epoch)
        replacement.recover()
        self.assertEqual(self.accounts.store.capacity(self.user.id)[0].tier, 'plus')
        self.assertEqual(len(self.provider.sessions), 1)

    def test_runtime_lock_is_held_across_processes_and_released_on_stop(self):
        script = (
            'import fcntl,sys; '
            'from pathlib import Path; '
            "p=Path(sys.argv[1]); f=p.with_name(p.name+'.billing.lock').open('ab'); "
            'fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)'
        )
        argv = [sys.executable, '-c', script, str(self.accounts.store.path.resolve())]
        refused = subprocess.run(argv, capture_output=True, text=True, check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('BlockingIOError', refused.stderr)
        self.assertTrue(self.service.authority.snapshot()[2])
        self.service.close()
        acquired = subprocess.run(argv, capture_output=True, text=True, check=False)
        self.assertEqual(acquired.returncode, 0, acquired.stderr)

    def test_cancel_stops_proven_subscription_while_unsupported_money_stays_held(self):
        self.assertEqual(self.checkout().status_code, 200)
        self.provider.complete()
        self.service.reconcile(self.user.id)
        settings, _ = self.accounts.store.save_chart(self.user.id, birth(0), None)
        settings, _ = self.accounts.store.save_chart(
            self.user.id, birth(1), settings.updated_at
        )
        self.provider.invoices['in_one']['billing_reason'] = 'manual'
        self.service.authority.enqueue(
            Delivery(
                'evt_unsupported', 'invoice.paid', 'in_one', 'cus_1', 'f' * 64, True
            )
        )
        for _ in range(2):
            response = self.client.post(
                '/api/account/billing/cancel', json={'key': self.key}
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['status'], 'held')
            self.assertTrue(
                self.provider.subscriptions['sub_one']['cancel_at_period_end']
            )
        self.assertEqual(
            self.provider.calls.count(('POST', '/v1/subscriptions/sub_one')), 1
        )
        current = self.client.get('/api/account/settings').json()
        self.assertEqual(
            (current['billing']['tier'], current['chart_limit']), ('free', 1)
        )
        with self.assertRaises(ChartLimit):
            self.accounts.store.save_chart(self.user.id, birth(2), settings.updated_at)
        event = next(
            record
            for record in self.accounts.store.billing_records()
            if isinstance(record, EventRecord) and record.event_id == 'evt_unsupported'
        )
        self.assertEqual(event.state, 'pending')

    def test_cancel_cannot_control_an_unproven_subscription(self):
        self.assertEqual(self.checkout().status_code, 200)
        self.provider.complete()
        extra = copy.deepcopy(self.provider.subscriptions['sub_one'])
        extra['id'] = 'sub_unproven'
        self.provider.subscriptions[extra['id']] = extra
        response = self.client.post(
            '/api/account/billing/cancel', json={'key': self.key}
        )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(self.provider.subscriptions['sub_one']['cancel_at_period_end'])
        self.assertFalse(
            self.provider.subscriptions['sub_unproven']['cancel_at_period_end']
        )

    def prepared_checkout_before_send(self):
        original = Work.save

        def crash(work, owner):
            if any(
                op.kind == 'checkout_create' and op.state == 'sent'
                for op in owner.operations
            ):
                raise RuntimeError('injected before Checkout sent commit')
            original(work, owner)

        with patch.object(Work, 'save', crash):
            with self.assertRaises(RuntimeError):
                self.checkout()
        return next(
            record
            for record in self.accounts.store.billing_records()
            if isinstance(record, AccountBillingRecord) and record.id == self.user.id
        )

    def test_delete_disables_proven_unsent_checkout_without_creating_a_session(self):
        before = self.prepared_checkout_before_send()
        response = self.client.request(
            'DELETE', '/api/account', json={'key': self.key, 'email': self.user.email}
        )
        self.assertEqual(response.status_code, 204, response.text)
        self.assertIsNone(self.accounts.store.user_by_id(self.user.id))
        self.assertFalse(self.provider.sessions)
        after = next(
            record
            for record in self.accounts.store.billing_records()
            if isinstance(record, AccountBillingRecord) and record.id == self.user.id
        )
        original = next(op for op in before.operations if op.kind == 'checkout_create')
        disabled = next(op for op in after.operations if op.id == original.id)
        self.assertEqual((disabled.state, disabled.reason), ('held', 'deleted_owner'))
        self.assertEqual(disabled.idempotency_key, original.idempotency_key)
        self.assertEqual(disabled.request_sha256, original.request_sha256)
        self.assertIsNone(disabled.sent_at)
        self.assertIsNone(disabled.result_id)
        self.service.authority.hold_runtime(self.service.epoch, 'unverified')
        self.service.recover()
        self.assertTrue(self.service.authority.snapshot()[2])
        self.assertFalse(self.provider.sessions)

    def test_unproven_prepared_checkout_keeps_erasure_and_recovery_pending(self):
        self.prepared_checkout_before_send()
        with patch.object(
            self.service.authority, 'unsent_is_proven', return_value=False
        ):
            response = self.client.request(
                'DELETE',
                '/api/account',
                json={'key': self.key, 'email': self.user.email},
            )
            self.assertEqual(response.status_code, 503)
            self.assertIsNotNone(self.accounts.store.user_by_id(self.user.id))
            self.assertFalse(self.provider.sessions)
            self.service.authority.hold_runtime(self.service.epoch, 'unverified')
            with self.assertRaises(BillingHold):
                self.service.recover()
            self.assertFalse(self.service.authority.snapshot()[2])

    def test_busy_return_redirects_without_granting_an_unreconciled_payment(self):
        self.assertEqual(self.checkout().status_code, 200)
        self.provider.complete()
        lease, _ = self.service.authority.claim(self.user.id)
        returned = self.client.get(
            '/account/billing/return?payment_status=paid&customer=cus_forged',
            follow_redirects=False,
        )
        self.assertEqual(returned.status_code, 303)
        self.assertEqual(
            returned.headers['location'], self.accounts.config.origin + '/'
        )
        self.assertEqual(
            returned.headers['retry-after'], str(self.service.config.poll_seconds)
        )
        view = self.client.get('/api/account/settings').json()
        self.assertEqual((view['billing']['tier'], view['chart_limit']), ('free', 1))
        self.service.authority.release(lease)
        self.assertEqual(
            self.client.get(
                '/account/billing/return', follow_redirects=False
            ).status_code,
            303,
        )
        view = self.client.get('/api/account/settings').json()
        self.assertEqual((view['billing']['tier'], view['chart_limit']), ('plus', 25))
        with patch.object(
            self.service, 'reconcile', side_effect=BillingHold('native_unavailable')
        ):
            self.assertEqual(
                self.client.get(
                    '/account/billing/return', follow_redirects=False
                ).status_code,
                503,
            )

    def test_unsupported_checkout_methods_never_return_a_bearer_url(self):
        self.provider.payment_methods = ['card', 'link']
        response = self.checkout()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['billing']['reason'], 'unsupported_funding')
        self.assertNotIn('checkout_url', response.json())
        self.assertEqual(len(self.provider.sessions), 1)

    def test_long_paginated_session_discovery_renews_the_current_owner_lease(self):
        self.assertEqual(self.checkout().status_code, 200)
        self.provider.slow_sessions = True
        self.service.reconcile(self.user.id)
        self.assertGreaterEqual(self.provider.session_pages, 4)
        self.assertTrue(self.service.authority.snapshot()[2])
        owner = next(
            record
            for record in self.accounts.store.billing_records()
            if isinstance(record, AccountBillingRecord) and record.id == self.user.id
        )
        self.assertEqual(owner.lifecycle, 'active')
        self.assertEqual(len(self.provider.sessions), 1)

    def other_deleting_owner(self, *, native=False):
        other_client = site_client()
        self.addCleanup(other_client.close)
        sign_in(other_client, self.accounts, 'other-cleanup@example.invalid')
        other = self.accounts.store.user_by_email('other-cleanup@example.invalid')
        if native:
            response = other_client.post(
                '/api/account/billing/checkout',
                json={'key': account_key(other), 'plan': 'basic', 'period': 'monthly'},
            )
            self.assertEqual(response.status_code, 200, response.text)
        else:
            self.service.authority.ensure_owner(other.id)
        self.service.authority.request_deletion(other.id)
        return other

    def test_live_owner_contention_does_not_close_every_accounts_paid_access(self):
        self.assertEqual(self.checkout().status_code, 200)
        self.provider.complete()
        self.service.reconcile(self.user.id)
        other = self.other_deleting_owner()
        lease, _ = self.service.authority.claim(self.user.id)
        self.service.tick()
        self.assertTrue(self.service.authority.snapshot()[2])
        self.assertEqual(self.accounts.store.capacity(self.user.id)[0].tier, 'plus')
        self.assertIsNone(self.accounts.store.user_by_id(other.id))
        self.service.authority.release(lease)

    def test_one_persistent_financial_hold_does_not_starve_another_native_erasure(self):
        self.assertEqual(self.checkout().status_code, 200)
        self.provider.complete()
        self.service.reconcile(self.user.id)
        other = self.other_deleting_owner(native=True)
        self.provider.invoices['in_one']['billing_reason'] = 'manual'
        self.service.tick()
        self.assertTrue(self.service.authority.snapshot()[2])
        self.assertEqual(self.accounts.store.capacity(self.user.id)[0].status, 'held')
        self.assertIsNone(self.accounts.store.user_by_id(other.id))
        self.assertEqual(self.provider.sessions['cs_test_2']['status'], 'expired')

    def test_startup_stays_closed_but_attempts_other_owners_cleanup_before_reporting_hold(
        self,
    ):
        self.assertEqual(self.checkout().status_code, 200)
        self.provider.complete()
        self.service.reconcile(self.user.id)
        other = self.other_deleting_owner(native=True)
        self.provider.invoices['in_one']['billing_reason'] = 'manual'
        self.service.authority.hold_runtime(self.service.epoch, 'unverified')
        with self.assertRaises(BillingHold):
            self.service.recover()
        self.assertFalse(self.service.authority.snapshot()[2])
        self.assertIsNone(self.accounts.store.user_by_id(other.id))

    def interrupted_checkout(self, *, prepared=False):
        original_execute = Work.execute
        original_save = Work.save

        def crash_before_send(work, owner):
            if any(
                operation.kind == 'checkout_create' and operation.state == 'sent'
                for operation in owner.operations
            ):
                raise RuntimeError('injected before Session sent commit')
            original_save(work, owner)

        def crash_before_reservation(work, purpose, **kwargs):
            if purpose == 'checkout_create':
                raise RuntimeError('injected before Session reservation')
            return original_execute(work, purpose, **kwargs)

        with (
            patch.object(Work, 'save', crash_before_send)
            if prepared
            else patch.object(Work, 'execute', crash_before_reservation)
        ):
            with self.assertRaises(RuntimeError):
                self.checkout()
        owner = next(
            record
            for record in self.accounts.store.billing_records()
            if isinstance(record, AccountBillingRecord)
        )
        self.assertFalse(self.provider.sessions)
        self.clock.advance(3601)
        self.service.recover()
        current = next(
            record
            for record in self.accounts.store.billing_records()
            if isinstance(record, AccountBillingRecord)
        )
        self.assertEqual(current.intents[0].id, owner.intents[0].id)
        self.assertEqual(current.intents[0].offer_id, owner.intents[0].offer_id)
        self.assertEqual(len(self.provider.sessions), 1)
        session = next(iter(self.provider.sessions.values()))
        self.assertEqual(session['expires_at'] - session['created'], 3600)
        if prepared:
            old = next(
                operation
                for operation in owner.operations
                if operation.kind == 'checkout_create'
            )
            resumed = next(
                operation for operation in current.operations if operation.id == old.id
            )
            self.assertEqual(resumed.idempotency_key, old.idempotency_key)
            self.assertNotEqual(resumed.request_sha256, old.request_sha256)
            self.assertIsNone(old.sent_at)

    def test_expired_unsent_reservation_recovers_before_first_session_request(self):
        self.interrupted_checkout()

    def test_expired_prepared_but_proven_unsent_session_refreshes_only_its_deadline(
        self,
    ):
        self.interrupted_checkout(prepared=True)

    def setUp(self):
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory)
        self.clock = Clock(datetime(2026, 10, 19, 10, tzinfo=UTC))
        billing = replace(configuration(), clock_ids=(), purchase_clock=None)
        config = replace(
            load_config(account_environment(self.directory)), billing=billing
        )
        AccountStore.create(config.database)
        self.provider = Provider(billing, self.clock)
        self.addCleanup(self.provider.client.close)
        self.accounts = Accounts.open(
            config,
            person_check=FakePersonCheck(),
            clock=self.clock,
            billing_client=self.provider.client,
        )
        self.service = self.accounts.billing
        self.addCleanup(self.service.close)
        self.service.recover()
        app.dependency_overrides[get_accounts] = lambda: self.accounts
        self.addCleanup(app.dependency_overrides.pop, get_accounts)
        self.client = site_client()
        self.addCleanup(self.client.close)
        sign_in(self.client, self.accounts, 'one@example.invalid')
        self.user = self.accounts.store.user_by_email('one@example.invalid')
        self.key = account_key(self.user)

    def checkout(self, **changes):
        return self.client.post(
            '/api/account/billing/checkout',
            json={'key': self.key, 'plan': 'plus', 'period': 'monthly', **changes},
        )

    def assert_customerless_recovery(self, failure):
        with failure:
            response = self.checkout()
        self.assertEqual(response.status_code, 503, response.text)
        owner = next(
            record
            for record in self.accounts.store.billing_records()
            if isinstance(record, AccountBillingRecord)
        )
        self.assertEqual(owner.lifecycle, 'held')
        self.assertIsNone(owner.customer_id)
        self.assertFalse(owner.operations)
        self.service.authority.hold_runtime(self.service.epoch, 'native_unavailable')
        self.service.recover()
        self.assertTrue(self.service.authority.snapshot()[2])
        self.assertEqual(self.checkout().status_code, 200)
        self.assertEqual(len(self.provider.customers), 1)
        self.assertEqual(len(self.provider.sessions), 1)

    def test_customerless_discovery_failure_recovers_without_a_permanent_hold(self):
        self.assert_customerless_recovery(
            patch(
                'eight_characters.accounts.billing_service.discover_customers',
                side_effect=BillingHold('native_unavailable'),
            )
        )

    def test_customerless_catalogue_failure_recovers_without_a_permanent_hold(self):
        self.assert_customerless_recovery(
            patch(
                'eight_characters.accounts.billing_service.verify_sandbox_catalogue',
                side_effect=BillingError('injected unavailable catalogue'),
            )
        )

    def test_actual_managed_api_checkout_resume_and_recovery_never_fall_back_to_fifty(
        self,
    ):
        with patch(
            'eight_characters.accounts.web.accounts_from_environment',
            return_value=self.accounts,
        ):
            self.assertIs(get_accounts(), self.accounts)
        self.assertEqual(
            self.client.get('/api/account/settings').json()['chart_limit'], 1
        )
        first = self.checkout()
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()['status'], 'open')
        second = self.checkout()
        self.assertEqual(second.json(), first.json())
        self.assertEqual(len(self.provider.customers), 1)
        self.assertEqual(len(self.provider.sessions), 1)
        self.assertEqual(self.checkout(plan='basic').status_code, 409)
        with closing(sqlite3.connect(self.accounts.store.path)) as connection:
            authority = b''.join(
                bytes(row[0])
                for row in connection.execute('SELECT record FROM billing_records')
            )
        self.assertNotIn(b'https://', authority)
        self.assertNotIn(b'checkout_url', authority)

    def test_paid_native_fixture_changes_actual_store_and_api_then_refund_retains_library(
        self,
    ):
        self.assertEqual(self.checkout().status_code, 200)
        self.provider.complete()
        returned = self.client.get(
            '/account/billing/return?payment_status=unpaid&customer=cus_forged',
            follow_redirects=False,
        )
        self.assertEqual(returned.status_code, 303, returned.text)
        view = self.client.get('/api/account/settings').json()
        self.assertEqual((view['billing']['tier'], view['chart_limit']), ('plus', 25))
        self.assertEqual(self.accounts.store.user_by_id(self.user.id).plan, 'free')
        settings = None
        for index in range(25):
            settings, _ = self.accounts.store.save_chart(
                self.user.id,
                birth(index),
                None if settings is None else settings.updated_at,
            )
        with self.assertRaises(ChartLimit):
            self.accounts.store.save_chart(self.user.id, birth(25), settings.updated_at)
        self.provider.collections['refunds'] = [
            {
                'id': 're_full',
                'object': 'refund',
                'livemode': False,
                'charge': 'ch_one',
                'payment_intent': 'pi_one',
                'currency': 'usd',
                'amount': 1499,
                'status': 'succeeded',
            }
        ]
        self.service.reconcile(self.user.id)
        view = self.client.get('/api/account/settings').json()
        self.assertEqual(
            (view['billing']['tier'], view['chart_limit'], len(view['charts'])),
            ('free', 1, 25),
        )
        self.assertTrue(self.provider.subscriptions['sub_one']['cancel_at_period_end'])
        export = self.client.post('/api/account/export', json={'key': self.key}).json()
        self.assertEqual(export['billing']['invoices'][0]['charge_id'], 'ch_one')
        self.assertNotIn('ec_customer_mac', json.dumps(export))
        self.assertEqual(self.checkout().status_code, 409)

    def test_anonymous_cross_origin_stale_owner_and_untrusted_fields_cannot_create(
        self,
    ):
        anonymous = TestClient(
            app,
            base_url=self.accounts.config.origin,
            headers={'Origin': self.accounts.config.origin},
        )
        self.addCleanup(anonymous.close)
        self.assertEqual(
            anonymous.post(
                '/api/account/billing/checkout',
                json={'key': self.key, 'plan': 'plus', 'period': 'monthly'},
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                '/api/account/billing/checkout',
                headers={'Origin': 'https://elsewhere.invalid'},
                json={'key': self.key, 'plan': 'plus', 'period': 'monthly'},
            ).status_code,
            403,
        )
        other = site_client()
        self.addCleanup(other.close)
        sign_in(other, self.accounts, 'two@example.invalid')
        self.assertEqual(
            other.post(
                '/api/account/billing/checkout',
                json={'key': self.key, 'plan': 'plus', 'period': 'monthly'},
            ).status_code,
            409,
        )
        self.assertEqual(self.checkout(customer='cus_forged').status_code, 400)
        self.assertFalse(self.provider.customers)
        self.assertEqual(
            other.get(
                '/account/billing/return?session_id=cs_forged', follow_redirects=False
            ).status_code,
            503,
        )

    def test_webhook_requires_signature_and_committed_queue_without_origin_or_session(
        self,
    ):
        self.assertEqual(self.checkout().status_code, 200)
        raw = json.dumps(
            {
                'id': 'evt_delivery',
                'object': 'event',
                'created': int(self.clock().timestamp()),
                'api_version': self.service.config.payload_version,
                'livemode': False,
                'type': 'invoice.paid',
                'data': {'object': {'id': 'in_one', 'customer': 'cus_1'}},
            }
        ).encode()
        when = str(int(self.clock().timestamp()))
        signature = hmac.new(
            self.service.config.webhook_secrets[0],
            when.encode() + b'.' + raw,
            hashlib.sha256,
        ).hexdigest()
        headers = {'Stripe-Signature': 't=' + when + ',v1=' + signature}
        anonymous = TestClient(app, base_url=self.accounts.config.origin)
        self.addCleanup(anonymous.close)
        self.assertEqual(
            anonymous.post('/api/billing/stripe/webhook', content=raw).status_code, 400
        )
        first = anonymous.post(
            '/api/billing/stripe/webhook', content=raw, headers=headers
        )
        self.assertEqual(
            (first.status_code, first.json()), (202, {'status': 'pending'})
        )
        self.assertEqual(
            anonymous.post(
                '/api/billing/stripe/webhook', content=raw, headers=headers
            ).json(),
            first.json(),
        )
        self.assertEqual(
            len(
                [
                    record
                    for record in self.accounts.store.billing_records()
                    if isinstance(record, EventRecord)
                ]
            ),
            1,
        )
        with patch(
            'eight_characters.accounts.billing_authority.log_record_change',
            side_effect=sqlite3.OperationalError('injected'),
        ):
            other = raw.replace(b'evt_delivery', b'evt_other')
            mac = hmac.new(
                self.service.config.webhook_secrets[0],
                when.encode() + b'.' + other,
                hashlib.sha256,
            ).hexdigest()
            self.assertEqual(
                anonymous.post(
                    '/api/billing/stripe/webhook',
                    content=other,
                    headers={'Stripe-Signature': 't=' + when + ',v1=' + mac},
                ).status_code,
                503,
            )
        self.assertEqual(
            anonymous.post(
                '/api/billing/stripe/webhook',
                content=b'x' * (1024 * 1024 + 1),
                headers=headers,
            ).status_code,
            413,
        )

    def test_deleting_open_checkout_completes_only_after_native_cleanup(self):
        self.assertEqual(self.checkout().status_code, 200)
        response = self.client.request(
            'DELETE', '/api/account', json={'key': self.key, 'email': self.user.email}
        )
        self.assertEqual(response.status_code, 204, response.text)
        self.assertIsNone(self.accounts.store.user_by_id(self.user.id))
        self.assertEqual(self.provider.sessions['cs_test_1']['status'], 'expired')
        customer = self.provider.customers['cus_1']
        self.assertIn('ec_delete_mac', customer['metadata'])
        owner = next(
            record
            for record in self.accounts.store.billing_records()
            if isinstance(record, AccountBillingRecord)
        )
        self.assertEqual(owner.lifecycle, 'deleted')
        self.assertIsNotNone(owner.deletion.completed_at)

    def test_capture_discovered_during_erasure_stops_billing_but_stays_pending_across_retry(
        self,
    ):
        self.assertEqual(self.checkout().status_code, 200)
        self.provider.complete()
        for _ in range(2):
            response = self.client.request(
                'DELETE',
                '/api/account',
                json={'key': self.key, 'email': self.user.email},
            )
            self.assertEqual(response.status_code, 503, response.text)
            self.assertEqual(response.json()['billing']['reason'], 'late_settlement')
            self.assertIsNotNone(self.accounts.store.user_by_id(self.user.id))
            owner = next(
                record
                for record in self.accounts.store.billing_records()
                if isinstance(record, AccountBillingRecord)
            )
            self.assertEqual(owner.lifecycle, 'deleting')
            self.assertIsNone(owner.deletion.completed_at)
            self.assertTrue(
                any(
                    operation.reason == 'late_settlement'
                    for operation in owner.operations
                )
            )
        self.assertEqual(self.provider.subscriptions['sub_one']['status'], 'canceled')
        self.assertEqual(
            self.client.get('/api/account/settings').json()['billing']['status'],
            'deleting',
        )

    def test_worker_recovers_then_shutdown_fences_its_epoch(self):
        async def exercise():
            self.service.authority.hold_runtime(self.service.epoch, 'unverified')
            task = asyncio.create_task(self.service.run())
            for _ in range(100):
                if self.service.authority.snapshot()[2]:
                    break
                await asyncio.sleep(0.01)
            self.assertTrue(self.service.authority.snapshot()[2])
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertFalse(self.service.authority.snapshot()[2])
            self.assertNotEqual(
                self.service.authority.snapshot()[1], self.service.epoch
            )

        asyncio.run(exercise())

    def test_unsupported_payment_holds_erasure_after_closing_proven_renewal(self):
        self.assertEqual(self.checkout().status_code, 200)
        self.provider.complete()
        self.service.reconcile(self.user.id)
        self.provider.invoices['in_one']['billing_reason'] = 'manual'
        response = self.client.request(
            'DELETE', '/api/account', json={'key': self.key, 'email': self.user.email}
        )
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json()['billing']['reason'], 'unsupported_funding')
        self.assertEqual(self.provider.subscriptions['sub_one']['status'], 'canceled')
        self.assertIsNotNone(self.accounts.store.user_by_id(self.user.id))
        owner = next(
            record
            for record in self.accounts.store.billing_records()
            if isinstance(record, AccountBillingRecord)
        )
        self.assertEqual(len(owner.coverage), 1)
        self.assertIsNone(owner.deletion.completed_at)
