"""Native account/catalogue reads must be safe before any purchase can start."""

import copy
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import httpx

from eight_characters.accounts.__main__ import main
from eight_characters.accounts.billing import (
    OFFERS,
    BillingError,
    load_billing_config,
    verify_sandbox_catalogue,
)

VERSION = '2026-09-30.endive'
KEY = 'rk_test_OnlySyntheticCredential'
ENV = {
    'EC_BILLING_MODE': 'sandbox', 'EC_STRIPE_API_KEY': KEY,
    'EC_STRIPE_API_VERSION': VERSION, 'EC_STRIPE_ACCOUNT_ID': 'acct_example',
    **{f'EC_STRIPE_PRICE_{offer.key.upper()}': f'price_example{index}' for index, offer in enumerate(OFFERS)},
    **{f'EC_STRIPE_PRODUCT_{plan.upper()}': f'example_{plan}' for plan in ('basic', 'plus', 'pro')},
}


def catalogue() -> dict[str, dict[str, object]]:
    objects: dict[str, dict[str, object]] = {'/v1/account': {'id': 'acct_example', 'object': 'account'}}
    for index, offer in enumerate(OFFERS):
        objects[f'/v1/prices/price_example{index}'] = {
            'id': f'price_example{index}', 'object': 'price', 'active': True, 'livemode': False,
            'currency': 'usd', 'unit_amount': offer.amount, 'unit_amount_decimal': str(offer.amount),
            'type': 'recurring', 'billing_scheme': 'per_unit', 'tax_behavior': 'exclusive',
            'custom_unit_amount': None, 'transform_quantity': None, 'tiers_mode': None,
            'recurring': {'interval': offer.interval, 'interval_count': 1, 'usage_type': 'licensed', 'trial_period_days': None},
            'product': {'id': f'example_{offer.plan}', 'object': 'product', 'active': True, 'livemode': False},
        }
    return objects


class TestBillingConfiguration(unittest.TestCase):
    def test_disabled_is_explicit_and_never_enables_billing(self) -> None:
        self.assertIsNone(load_billing_config({}))
        self.assertIsNone(load_billing_config({'EC_BILLING_MODE': 'disabled'}))
        with self.assertRaises(BillingError):
            load_billing_config({'EC_STRIPE_API_KEY': KEY})

    def test_every_required_value_is_checked_without_echoing_it(self) -> None:
        for name in ENV:
            with self.subTest(name=name), self.assertRaises(BillingError):
                load_billing_config({key: value for key, value in ENV.items() if key != name})
        for name, value in (
            ('EC_BILLING_MODE', 'live'), ('EC_STRIPE_API_KEY', 'sk_live_Secret'),
            ('EC_STRIPE_API_KEY', KEY + '\n'), ('EC_STRIPE_API_VERSION', ''),
            ('EC_STRIPE_ACCOUNT_ID', 'acct_example/other'),
            ('EC_STRIPE_PRICE_BASIC_MONTHLY', 'price_example1'),
            ('EC_STRIPE_PRODUCT_BASIC', 'example_plus'),
        ):
            with self.subTest(name=name, value=value), self.assertRaises(BillingError) as caught:
                load_billing_config({**ENV, name: value})
            self.assertNotIn(KEY, str(caught.exception))
            self.assertNotIn('sk_live_Secret', str(caught.exception))
        config = load_billing_config(ENV)
        self.assertIsNotNone(config)
        self.assertNotIn(KEY, repr(config))


class TestNativeCatalogue(unittest.TestCase):
    def verify(self, objects: dict[str, dict[str, object]]) -> tuple[dict[str, object], list[httpx.Request]]:
        requests: list[httpx.Request] = []
        def read(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            self.assertEqual(request.method, 'GET')
            self.assertEqual(str(request.url).split('?')[0].split('/v1/')[0], 'https://api.stripe.com')
            self.assertEqual(request.headers['Authorization'], f'Bearer {KEY}')
            self.assertEqual(request.headers['Stripe-Version'], VERSION)
            if request.url.path != '/v1/account':
                self.assertEqual(request.url.params['expand[]'], 'product')
            return httpx.Response(200, json=objects[request.url.path], headers={'Stripe-Version': VERSION})
        config = load_billing_config(ENV)
        assert config is not None
        with httpx.Client(transport=httpx.MockTransport(read)) as client:
            report = verify_sandbox_catalogue(config, client)
        return report, requests

    def test_all_six_offers_are_verified_without_writes_or_readiness_claims(self) -> None:
        report, requests = self.verify(catalogue())
        self.assertEqual(len(requests), 7)
        self.assertEqual(report['status'], 'catalogue_verified')
        self.assertEqual(report['mode'], 'sandbox')
        self.assertEqual([item['unit_amount'] for item in report['offers']], [699, 5900, 1499, 12900, 2900, 24900])
        for key in ('checkout_available', 'payment_verified', 'paid_access_verified', 'tax_calculation_verified'):
            self.assertIs(report[key], False)
        self.assertNotIn(KEY, json.dumps(report))

    def test_wrong_account_and_every_price_or_product_mismatch_fail(self) -> None:
        objects = catalogue()
        objects['/v1/account']['id'] = 'acct_other'
        with self.assertRaises(BillingError):
            self.verify(objects)
        mutations = [
            ('id', 'price_other'), ('object', 'product'), ('active', False), ('livemode', True),
            ('currency', 'eur'), ('unit_amount', 700), ('unit_amount', 699.0),
            ('unit_amount_decimal', '699.5'), ('type', 'one_time'), ('billing_scheme', 'tiered'),
            ('tax_behavior', 'inclusive'), ('custom_unit_amount', {}), ('transform_quantity', {}),
            ('tiers_mode', 'volume'), ('product', 'example_basic'), ('recurring', None),
        ]
        for index in range(len(OFFERS)):
            path = f'/v1/prices/price_example{index}'
            for name, value in mutations:
                with self.subTest(index=index, field=name, value=value):
                    changed = catalogue()
                    changed[path][name] = value
                    with self.assertRaises(BillingError):
                        self.verify(changed)
            for group, changes in (
                ('recurring', {'interval': 'week', 'interval_count': True, 'usage_type': 'metered', 'trial_period_days': 7}),
                ('product', {'id': 'other', 'object': 'price', 'active': False, 'livemode': True}),
            ):
                for name, value in changes.items():
                    with self.subTest(index=index, group=group, field=name):
                        changed = catalogue()
                        changed[path][group] = {**changed[path][group], name: value}
                        with self.assertRaises(BillingError):
                            self.verify(changed)
            for name in catalogue()[path]:
                with self.subTest(index=index, missing=name):
                    changed = catalogue()
                    del changed[path][name]
                    with self.assertRaises(BillingError):
                        self.verify(changed)

    def test_native_errors_are_sanitized_and_redirects_are_not_followed(self) -> None:
        config = load_billing_config(ENV)
        assert config is not None
        responses = [
            httpx.Response(403, text=KEY), httpx.Response(302, headers={'Location': 'https://other.example'}),
            httpx.Response(200, text=KEY, headers={'Stripe-Version': VERSION}),
            httpx.Response(200, json=[], headers={'Stripe-Version': VERSION}),
            httpx.Response(200, json={}, headers={'Stripe-Version': 'different'}),
        ]
        for response in responses:
            seen = []
            def read(request: httpx.Request) -> httpx.Response:
                seen.append(request)
                return response
            with self.subTest(status=response.status_code), httpx.Client(transport=httpx.MockTransport(read)) as client:
                with self.assertRaises(BillingError) as caught:
                    verify_sandbox_catalogue(config, client)
                self.assertEqual(len(seen), 1)
                self.assertNotIn(KEY, str(caught.exception))
        def unavailable(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError(KEY, request=request)
        with httpx.Client(transport=httpx.MockTransport(unavailable)) as client:
            with self.assertRaises(BillingError) as caught:
                verify_sandbox_catalogue(config, client)
            self.assertNotIn(KEY, str(caught.exception))

    def test_cli_is_explicitly_disabled_or_emits_only_verified_nonsecret_evidence(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with patch.dict('os.environ', {}, clear=True), redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(main(['billing-preflight']), 2)
        self.assertEqual(json.loads(out.getvalue())['status'], 'disabled')
        objects = catalogue()
        def read(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=copy.deepcopy(objects[request.url.path]), headers={'Stripe-Version': VERSION})
        client = httpx.Client(transport=httpx.MockTransport(read))
        out = io.StringIO()
        with patch.dict('os.environ', ENV, clear=True), patch('eight_characters.accounts.__main__.httpx.Client', return_value=client), redirect_stdout(out):
            self.assertEqual(main(['billing-preflight']), 0)
        self.assertEqual(json.loads(out.getvalue())['status'], 'catalogue_verified')
        self.assertNotIn(KEY, out.getvalue() + err.getvalue())
        out, err = io.StringIO(), io.StringIO()
        with patch.dict('os.environ', {**ENV, 'EC_STRIPE_API_KEY': 'sk_live_Secret'}, clear=True), redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(main(['billing-preflight']), 1)
        self.assertEqual(out.getvalue(), '')
        self.assertNotIn('sk_live_Secret', err.getvalue())
