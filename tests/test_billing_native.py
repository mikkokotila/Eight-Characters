"""Injected native shapes test refusal boundaries; they are not native receipts."""

import copy
import unittest

import httpx

from eight_characters.accounts.billing_access import BillingHold
from eight_characters.accounts.billing_native import Stripe, captured_coverage
from tests.test_accounts_billing_recovery import NOW
from tests.test_billing_access import authority, configuration


class FundingGraph(unittest.TestCase):
    def setUp(self):
        self.config = configuration()
        self.scope, self.owner = authority()
        offer = self.scope.offers[0]
        self.invoice = dict(
            id='in_one',
            object='invoice',
            livemode=False,
            customer='cus_one',
            currency='usd',
            status='paid',
            collection_method='charge_automatically',
            amount_remaining=0,
            amount_overpaid=0,
            starting_balance=0,
            ending_balance=0,
            pre_payment_credit_notes_amount=0,
            post_payment_credit_notes_amount=0,
            total_discount_amounts=[],
            total_taxes=[],
            total_pretax_credit_amounts=[],
            default_tax_rates=[],
            discounts=[],
            application=None,
            on_behalf_of=None,
            transfer_data=None,
            automatic_tax={'enabled': False},
            billing_reason='subscription_create',
            parent={
                'type': 'subscription_details',
                'subscription_details': {'subscription': 'sub_one'},
            },
            amount_due=1499,
            amount_paid=1499,
            subtotal=1499,
            subtotal_excluding_tax=1499,
            total=1499,
            total_excluding_tax=1499,
            status_transitions={'paid_at': 1792404000},
        )
        price = dict(
            id=offer.price_id,
            object='price',
            livemode=False,
            currency='usd',
            unit_amount=1499,
            unit_amount_decimal='1499',
            billing_scheme='per_unit',
            type='recurring',
            tax_behavior='exclusive',
            product=offer.product_id,
            custom_unit_amount=None,
            transform_quantity=None,
            tiers_mode=None,
            recurring={
                'interval': 'month',
                'interval_count': 1,
                'usage_type': 'licensed',
                'trial_period_days': None,
            },
            active=False,
        )
        self.subscription = dict(
            id='sub_one',
            object='subscription',
            livemode=False,
            customer='cus_one',
            currency='usd',
            collection_method='charge_automatically',
            default_tax_rates=[],
            discounts=[],
            automatic_tax={'enabled': False},
            trial_start=None,
            trial_end=None,
            status='active',
        )
        self.objects = {
            'prices/' + offer.price_id: price,
            'payment_intents/pi_one': dict(
                id='pi_one',
                object='payment_intent',
                livemode=False,
                customer='cus_one',
                currency='usd',
                status='succeeded',
                amount=1499,
                amount_received=1499,
                amount_capturable=0,
                capture_method='automatic_async',
                payment_method_types=['card'],
                latest_charge='ch_one',
            ),
            'charges/ch_one': dict(
                id='ch_one',
                object='charge',
                livemode=False,
                customer='cus_one',
                payment_intent='pi_one',
                currency='usd',
                status='succeeded',
                paid=True,
                captured=True,
                amount=1499,
                amount_captured=1499,
                payment_method_details={'type': 'card'},
            ),
        }
        self.lists = {
            'invoices/in_one/lines': [
                dict(
                    id='il_one',
                    object='line_item',
                    livemode=False,
                    currency='usd',
                    quantity=1,
                    amount=1499,
                    discount_amounts=[],
                    discounts=[],
                    pretax_credit_amounts=[],
                    taxes=[],
                    parent={
                        'type': 'subscription_item_details',
                        'subscription_item_details': {
                            'subscription': 'sub_one',
                            'subscription_item': 'si_one',
                            'proration': False,
                        },
                    },
                    pricing={
                        'type': 'price_details',
                        'price_details': {
                            'price': offer.price_id,
                            'product': offer.product_id,
                        },
                    },
                    period={'start': 1792404000, 'end': 1795082400},
                )
            ],
            'subscription_items': [
                dict(
                    id='si_one',
                    object='subscription_item',
                    subscription='sub_one',
                    quantity=1,
                    price=price,
                )
            ],
            'invoice_payments': [
                dict(
                    id='inpay_one',
                    object='invoice_payment',
                    is_default=True,
                    invoice='in_one',
                    livemode=False,
                    currency='usd',
                    status='paid',
                    amount_paid=1499,
                    amount_requested=1499,
                    payment={'type': 'payment_intent', 'payment_intent': 'pi_one'},
                    status_transitions={'paid_at': 1792404000},
                )
            ],
            'refunds': [],
            'disputes': [],
        }
        self.requests = []

        def response(request):
            self.requests.append(request)
            path = request.url.path.removeprefix('/v1/')
            if path in self.lists:
                body = {'object': 'list', 'has_more': False, 'data': self.lists[path]}
            else:
                body = self.objects[path]
            return httpx.Response(
                200,
                json=body,
                headers={'Stripe-Version': self.config.catalogue.api_version},
            )

        self.client = httpx.Client(transport=httpx.MockTransport(response))
        self.addCleanup(self.client.close)
        self.native = Stripe(self.config, self.client)

    def coverage(self):
        return captured_coverage(
            self.native,
            self.invoice,
            customer_id='cus_one',
            subscriptions={'sub_one': self.subscription},
            offers=self.scope.offers,
            verified_at=NOW,
        )

    def test_archived_historical_offer_and_full_native_chain(self):
        receipt = self.coverage()
        self.assertEqual(
            (receipt.period_start, receipt.period_end, receipt.captured_amount),
            (1792404000, 1795082400, 1499),
        )
        self.assertEqual(receipt.invoice_payment_id, 'inpay_one')
        self.assertTrue(all(request.method == 'GET' for request in self.requests))
        self.assertTrue(
            all(
                request.headers['Stripe-Version'] == self.config.catalogue.api_version
                for request in self.requests
            )
        )
        self.assertEqual(
            {request.url.path for request in self.requests},
            {
                '/v1/invoices/in_one/lines',
                '/v1/subscription_items',
                '/v1/prices/price_plusMonth',
                '/v1/invoice_payments',
                '/v1/payment_intents/pi_one',
                '/v1/charges/ch_one',
                '/v1/refunds',
                '/v1/disputes',
            },
        )

    def test_paid_label_never_substitutes_for_supported_funding(self):
        original = copy.deepcopy(self.invoice)
        for update in (
            {'billing_reason': 'manual'},
            {'starting_balance': -1499},
            {'amount_paid': True},
            {'total': 0},
            {'customer': 'cus_other'},
            {'discounts': ['di_one']},
        ):
            with self.subTest(update=update):
                self.invoice = {**original, **update}
                with self.assertRaises(BillingHold):
                    self.coverage()
        self.invoice = original
        for update in (
            {'status': 'requires_action'},
            {'amount_received': 1400},
            {'customer': 'cus_other'},
            {'capture_method': 'manual'},
        ):
            before = copy.deepcopy(self.objects['payment_intents/pi_one'])
            self.objects['payment_intents/pi_one'].update(update)
            with self.assertRaises(BillingHold):
                self.coverage()
            self.objects['payment_intents/pi_one'] = before

    def test_partial_or_multiple_allocations_are_refused(self):
        payment = self.lists['invoice_payments'][0]
        self.lists['invoice_payments'] = [payment, {**payment, 'id': 'inpay_two'}]
        with self.assertRaises(BillingHold):
            self.coverage()

        self.lists['invoice_payments'] = [{**payment, 'amount_paid': 1498}]
        with self.assertRaises(BillingHold):
            self.coverage()

    def test_missing_required_nullable_fields_are_named_holds(self):
        original = copy.deepcopy(self.invoice)
        for name in ('application', 'on_behalf_of', 'transfer_data'):
            with self.subTest(name=name):
                self.invoice = {
                    key: value for key, value in original.items() if key != name
                }
                with self.assertRaises(BillingHold) as failure:
                    self.coverage()
                self.assertEqual(failure.exception.reason, 'unsupported_funding')

    def test_proration_cannot_grant_a_full_offer_period(self):
        self.lists['invoices/in_one/lines'][0]['parent']['subscription_item_details'][
            'proration'
        ] = True
        with self.assertRaises(BillingHold):
            self.coverage()

    def test_refund_statuses_and_disputes_are_current_facts_not_implicit_money(self):
        self.lists['refunds'] = [
            dict(
                id='re_one',
                object='refund',
                charge='ch_one',
                payment_intent='pi_one',
                currency='usd',
                amount=1499,
                status='pending',
            )
        ]
        self.lists['disputes'] = [
            dict(
                id='du_one',
                object='dispute',
                charge='ch_one',
                currency='usd',
                livemode=False,
                payment_intent='pi_one',
                status='under_review',
            )
        ]
        self.assertEqual(self.coverage().refunds[0].status, 'pending')
        self.lists['refunds'][0]['status'] = 'whsec_DO_NOT_LOG'
        with self.assertRaises(BillingHold) as failure:
            self.coverage()
        self.assertNotIn('DO_NOT_LOG', str(failure.exception))

    def test_pagination_must_reach_a_complete_nonrepeating_end(self):
        calls = []

        def response(request):
            calls.append(request)
            first = 'starting_after' not in request.url.params
            return httpx.Response(
                200,
                json={
                    'object': 'list',
                    'has_more': first,
                    'data': [{'id': 'cus_one' if first else 'cus_two'}],
                },
                headers={'Stripe-Version': self.config.catalogue.api_version},
            )

        with httpx.Client(transport=httpx.MockTransport(response)) as client:
            rows = Stripe(self.config, client).all(
                'customers', {'test_clock': 'clock_one'}
            )
        self.assertEqual([row['id'] for row in rows], ['cus_one', 'cus_two'])
        self.assertEqual(calls[1].url.params['starting_after'], 'cus_one')
        self.assertEqual(calls[1].url.params['test_clock'], 'clock_one')

    def test_unknown_mutations_and_refund_issuance_are_not_runtime_capabilities(self):
        for method, path in (
            ('POST', 'refunds'),
            ('POST', 'invoices/in_one/pay'),
            ('POST', 'payment_intents/pi_one/cancel'),
        ):
            with self.assertRaises(BillingHold):
                self.native.request(method, path, {}, idempotency_key='fixture')
        self.assertEqual(self.requests, [])
