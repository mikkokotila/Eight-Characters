"""Sold access decisions from strict fixture authority, not native payment proof."""

import hashlib
import unittest

from eight_characters.accounts.billing import BillingError
from eight_characters.accounts.billing_access import (
    BillingHold,
    binding_mac,
    effective_access,
    load_runtime_config,
)
from eight_characters.accounts.billing_records import (
    DisputeFact,
    OfferSnapshot,
    RefundFact,
)
from eight_characters.accounts.records import User, canonical_json, new_id
from tests.test_accounts_billing_recovery import NOW, records


def configuration(**updates):
    values = {
        'EC_BILLING_MODE': 'sandbox',
        'EC_STRIPE_API_KEY': 'rk_test_fixtureOnly',
        'EC_STRIPE_API_VERSION': '2026-09-30.endive',
        'EC_STRIPE_PAYLOAD_VERSION': '2026-09-30.endive',
        'EC_STRIPE_ACCOUNT_ID': 'acct_sandbox',
        'EC_BILLING_NAMESPACE': 'a' * 32,
        'EC_BILLING_BINDING_KEY': 'B' * 43,
        'EC_STRIPE_WEBHOOK_SECRET': 'whsec_fixtureOnly',
        'EC_STRIPE_PAYMENT_METHOD_CONFIGURATION': 'pmc_fixtureOnly',
        'EC_BILLING_TEST_CLOCK_IDS': 'clock_one,clock_two',
        'EC_BILLING_PURCHASE_CLOCK': 'clock_one',
        'EC_BILLING_POLL_SECONDS': '5',
        'EC_BILLING_LEASE_SECONDS': '120',
    }
    for plan in ('basic', 'plus', 'pro'):
        values['EC_STRIPE_PRODUCT_' + plan.upper()] = 'product_' + plan
        for period in ('monthly', 'yearly'):
            values['EC_STRIPE_PRICE_' + plan.upper() + '_' + period.upper()] = (
                'price_' + plan + period
            )
    values.update(updates)
    config = load_runtime_config(values, session_secret=b'S' * 43)
    if config is None:
        raise AssertionError('fixture configuration is enabled')
    return config


def authority():
    user = User(
        id=new_id(),
        email='fixture@example.invalid',
        language='fi',
        plan='free',
        created_at=NOW,
        updated_at=NOW,
    )
    scope, owner, _ = records(user)
    return scope, owner


class SoldAccess(unittest.TestCase):
    def setUp(self):
        self.scope, self.owner = authority()
        self.receipt = self.owner.coverage[0]

    def access(self, *, receipt=None, owner=None, now=None):
        value = owner or self.owner.model_copy(
            update={'coverage': (receipt or self.receipt,)}
        )
        return effective_access(
            self.scope,
            value,
            now=self.receipt.period_start if now is None else now,
            ready=True,
        )

    def test_absolute_period_no_grace_and_no_arrival_extension(self):
        self.assertEqual(self.access(now=self.receipt.period_start - 1).chart_limit, 1)
        self.assertEqual((self.access().tier, self.access().chart_limit), ('plus', 25))
        self.assertEqual(self.access(now=self.receipt.period_end - 1).status, 'paid')
        self.assertEqual(self.access(now=self.receipt.period_end).chart_limit, 1)
        for _ in range(3):
            self.assertEqual(self.access(now=self.receipt.period_end).status, 'expired')

    def test_cumulative_returned_money_only_and_reversed_refund(self):
        partial = self.receipt.model_copy(
            update={
                'refunds': (
                    RefundFact(id='re_one', amount=500, status='succeeded'),
                    RefundFact(id='re_two', amount=999, status='pending'),
                )
            }
        )
        self.assertEqual(self.access(receipt=partial).tier, 'plus')
        full = partial.model_copy(
            update={
                'refunds': (
                    partial.refunds[0],
                    partial.refunds[1].model_copy(update={'status': 'succeeded'}),
                )
            }
        )
        self.assertEqual(self.access(receipt=full).chart_limit, 1)
        reversed_refund = full.model_copy(
            update={
                'refunds': (
                    full.refunds[0],
                    full.refunds[1].model_copy(update={'status': 'failed'}),
                )
            }
        )
        self.assertEqual(self.access(receipt=reversed_refund).tier, 'plus')
        self.assertEqual(
            self.access(
                receipt=reversed_refund, now=self.receipt.period_end
            ).chart_limit,
            1,
        )

    def test_dispute_inquiries_hold_only_affected_coverage(self):
        for status in (
            'needs_response',
            'under_review',
            'warning_needs_response',
            'warning_under_review',
            'lost',
        ):
            with self.subTest(status=status):
                held = self.receipt.model_copy(
                    update={'disputes': (DisputeFact(id='du_one', status=status),)}
                )
                self.assertEqual(self.access(receipt=held).chart_limit, 1)
        for status in ('won', 'warning_closed'):
            restored = self.receipt.model_copy(
                update={'disputes': (DisputeFact(id='du_one', status=status),)}
            )
            self.assertEqual(self.access(receipt=restored).tier, 'plus')
        refunded = restored.model_copy(
            update={
                'refunds': (RefundFact(id='re_full', amount=1499, status='succeeded'),)
            }
        )
        self.assertEqual(self.access(receipt=refunded).chart_limit, 1)

    def test_independent_period_survives_an_older_refund_and_overlap_is_not_summed(
        self,
    ):
        old = self.receipt.model_copy(
            update={
                'refunds': (RefundFact(id='re_full', amount=1499, status='succeeded'),)
            }
        )
        later = self.receipt.model_copy(
            update={
                'invoice_id': 'in_later',
                'line_id': 'il_later',
                'invoice_payment_id': 'inpay_later',
                'payment_intent_id': 'pi_later',
                'charge_id': 'ch_later',
            }
        )
        owner = self.owner.model_copy(update={'coverage': (old, later)})
        self.assertEqual(
            (
                self.access(owner=owner).chart_limit,
                self.access(owner=owner).paid_through,
            ),
            (25, later.period_end),
        )

    def test_sold_pro_is_unlimited_and_different_tier_overlap_is_held(self):
        terms = self.scope.offers[0].model_dump(mode='json', exclude={'id'})
        terms.update(plan='pro', price_id='price_pro', amount=2900)
        offer = OfferSnapshot(
            id=hashlib.sha256(canonical_json(terms)).hexdigest(), **terms
        )
        scope = self.scope.model_copy(update={'offers': (*self.scope.offers, offer)})
        receipt = self.receipt.model_copy(
            update={
                'price_id': offer.price_id,
                'offer_id': offer.id,
                'invoice_id': 'in_pro',
                'line_id': 'il_pro',
                'invoice_payment_id': 'inpay_pro',
                'payment_intent_id': 'pi_pro',
                'charge_id': 'ch_pro',
                'allocated_amount': 2900,
                'captured_amount': 2900,
                'base_amount': 2900,
                'refunds': (),
            }
        )
        owner = self.owner.model_copy(update={'coverage': (receipt,)})
        access = effective_access(scope, owner, now=receipt.period_start, ready=True)
        self.assertEqual(access.tier, 'pro')
        self.assertIsNone(access.chart_limit)
        owner = owner.model_copy(update={'coverage': (self.receipt, receipt)})
        self.assertEqual(
            effective_access(scope, owner, now=receipt.period_start, ready=True).reason,
            'unsupported_overlap',
        )

    def test_closed_recovery_gate_never_uses_a_cached_paid_receipt(self):
        with self.assertRaises(BillingHold) as error:
            effective_access(
                self.scope, self.owner, now=self.receipt.period_start, ready=False
            )
        self.assertEqual(error.exception.reason, 'unverified')

    def test_held_purchase_is_visible_as_held_instead_of_pending(self):
        intent = self.owner.intents[0].model_copy(update={'state': 'held'})
        owner = self.owner.model_copy(update={'coverage': (), 'intents': (intent,)})
        access = self.access(owner=owner)
        self.assertEqual(
            (access.status, access.reason), ('held', 'uncertain_operation')
        )
        self.assertEqual(access.chart_limit, 1)

    def test_configuration_and_binding_domains_do_not_broaden_authority(self):
        config = configuration()
        self.assertNotIn('fixtureOnly', repr(config))
        for update in (
            {'EC_STRIPE_API_KEY': 'sk_test_fixtureOnly'},
            {'EC_BILLING_PURCHASE_CLOCK': 'clock_unknown'},
            {'EC_BILLING_POLL_SECONDS': '0'},
        ):
            with self.assertRaises(BillingError):
                configuration(**update)
        values = [binding_mac(config, 'owner', 'cus_one', 'sealed', 'operation')]
        for args in (
            ('other', 'cus_one', 'sealed', 'operation'),
            ('owner', 'cus_two', 'sealed', 'operation'),
            ('owner', 'cus_one', 'creation', 'operation'),
            ('owner', 'cus_one', 'sealed', 'other'),
        ):
            values.append(binding_mac(config, *args))
        self.assertEqual(len(set(values)), 5)
