"""Bounded native Stripe reads and the supported captured-card funding graph.

Webhooks and redirect claims are wake-ups, never payment evidence. Raw objects and
provider errors stay in memory; exceptions expose only stable operational reasons.
"""

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

import httpx
from pydantic import ValidationError

from eight_characters.accounts.billing_access import BillingConfig, BillingHold
from eight_characters.accounts.billing_records import (
    Coverage,
    DisputeFact,
    OfferSnapshot,
    RefundFact,
)
from eight_characters.accounts.records import canonical_json

Native = dict[str, Any]
Parameters = Mapping[str, str]


def mapping(value: object) -> Native:
    if not isinstance(value, dict):
        raise BillingHold('unsupported_funding')
    if any(not isinstance(key, str) for key in cast(dict[object, object], value)):
        raise BillingHold('unsupported_funding')
    return cast(Native, value)


def identity(value: object, prefix: str) -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(prefix + r'_[A-Za-z0-9_]+', value) is None
    ):
        raise BillingHold('unsupported_funding')
    return value


def integer(value: object, *, positive: bool = False) -> int:
    if type(value) is not int or not (1 if positive else 0) <= value < 2**63:
        raise BillingHold('unsupported_funding')
    return value


def require(value: Native, expected: Mapping[str, object]) -> None:
    if any(
        k not in value or type(value[k]) is not type(v) or value[k] != v
        for k, v in expected.items()
    ):
        raise BillingHold('unsupported_funding')


def empty(value: Native, *names: str) -> None:
    # These native array fields explicitly allow null. Missing fields are not
    # evidence of an empty collection, and embedded paginated lists are not used.
    if any(name not in value or value[name] not in (None, []) for name in names):
        raise BillingHold('unsupported_funding')


def request_digest(method: str, path: str, parameters: Parameters) -> str:
    return hashlib.sha256(
        canonical_json({'method': method, 'path': path, 'parameters': dict(parameters)})
    ).hexdigest()


class Stripe:
    def __init__(self, config: BillingConfig, client: httpx.Client, *, before_request: Callable[[], None] | None = None) -> None:
        self.config = config
        self.client = client
        self.before_request = before_request

    def request(
        self,
        method: str,
        path: str,
        parameters: Parameters | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> Native:
        read = r'(?:account|prices/[A-Za-z0-9_]+|customers(?:/[A-Za-z0-9_]+)?|checkout/sessions(?:/[A-Za-z0-9_]+)?|subscriptions(?:/[A-Za-z0-9_]+)?|subscription_items|invoices(?:/[A-Za-z0-9_]+(?:/lines)?)?|invoice_payments|payment_intents/[A-Za-z0-9_]+|charges/[A-Za-z0-9_]+|refunds|disputes|events|test_helpers/test_clocks(?:/[A-Za-z0-9_]+)?)'
        post = r'(?:customers(?:/cus_[A-Za-z0-9]+)?|checkout/sessions(?:/cs_test_[A-Za-z0-9]+(?:/expire)?)?|subscriptions/sub_[A-Za-z0-9]+|invoices/in_[A-Za-z0-9]+(?:/void)?)'
        allowed = (
            (method == 'GET' and re.fullmatch(read, path) is not None)
            or (method == 'POST' and re.fullmatch(post, path) is not None)
            or (
                method == 'DELETE'
                and re.fullmatch(r'subscriptions/sub_[A-Za-z0-9]+', path) is not None
            )
        )
        if not allowed or (method != 'GET' and not idempotency_key):
            raise BillingHold('processing_failed')
        if self.before_request is not None:
            self.before_request()
        headers = {
            'Authorization': f'Bearer {self.config.catalogue.api_key}',
            'Stripe-Version': self.config.catalogue.api_version,
        }
        if idempotency_key is not None:
            headers['Idempotency-Key'] = idempotency_key
        try:
            response = self.client.request(
                method,
                'https://api.stripe.com/v1/' + path,
                headers=headers,
                params=parameters if method == 'GET' else None,
                data=parameters if method != 'GET' else None,
                timeout=10,
                follow_redirects=False,
            )
        except httpx.HTTPError:
            raise BillingHold('native_unavailable') from None
        if response.status_code == 403:
            raise BillingHold('permission_missing')
        if response.status_code != 200:
            raise BillingHold(
                'native_unavailable'
                if response.status_code >= 500
                or response.status_code in (404, 409, 429)
                else 'processing_failed'
            )
        if response.headers.get('Stripe-Version') != self.config.catalogue.api_version:
            raise BillingHold('unsupported_version')
        try:
            value: object = response.json()
        except ValueError:
            raise BillingHold('native_unavailable') from None
        return mapping(value)

    def account(self) -> None:
        value = self.request('GET', 'account')
        if (
            value.get('id') != self.config.catalogue.account_id
            or value.get('object') != 'account'
        ):
            raise BillingHold('scope_mismatch')

    def all(
        self, path: str, parameters: Parameters | None = None
    ) -> tuple[Native, ...]:
        params = {**(parameters or {}), 'limit': '100'}
        found: list[Native] = []
        seen: set[str] = set()
        while True:
            page = self.request('GET', path, params)
            if (
                page.get('object') != 'list'
                or type(page.get('has_more')) is not bool
                or not isinstance(page.get('data'), list)
            ):
                raise BillingHold('native_unavailable')
            data = cast(list[object], page['data'])
            for item in data:
                row = mapping(item)
                key = row.get('id')
                if not isinstance(key, str) or key in seen:
                    raise BillingHold('native_unavailable')
                seen.add(key)
                found.append(row)
            if page['has_more'] is False:
                return tuple(found)
            if not data:
                raise BillingHold('native_unavailable')
            params['starting_after'] = cast(str, found[-1]['id'])

    def clock(self, clock_id: str) -> int:
        clock = self.request(
            'GET', 'test_helpers/test_clocks/' + identity(clock_id, 'clock')
        )
        if (
            clock.get('object') != 'test_helpers.test_clock'
            or clock.get('id') != clock_id
            or clock.get('status') != 'ready'
            or clock.get('livemode') is not False
        ):
            raise BillingHold('clock_unavailable')
        return integer(clock.get('frozen_time'))


def _historical_price(price: Native, offer: OfferSnapshot) -> None:
    # Archiving a once-approved offer cannot invalidate an independently funded
    # service interval. The terms and identity must still match exactly.
    require(
        price,
        {
            'id': offer.price_id,
            'object': 'price',
            'livemode': False,
            'currency': 'usd',
            'unit_amount': offer.amount,
            'unit_amount_decimal': str(offer.amount),
            'billing_scheme': 'per_unit',
            'type': 'recurring',
            'tax_behavior': 'exclusive',
            'product': offer.product_id,
            'custom_unit_amount': None,
            'transform_quantity': None,
            'tiers_mode': None,
        },
    )
    recurring = mapping(price.get('recurring'))
    require(
        recurring,
        {
            'interval': offer.interval,
            'interval_count': 1,
            'usage_type': 'licensed',
            'trial_period_days': None,
        },
    )


def captured_coverage(
    native: Stripe,
    invoice: Native,
    *,
    customer_id: str,
    subscriptions: Mapping[str, Native],
    offers: Sequence[OfferSnapshot],
    verified_at: str,
) -> Coverage:
    """Independently fetch every link; unsupported money is never a paid grant."""
    invoice_id = identity(invoice.get('id'), 'in')
    require(
        invoice,
        {
            'object': 'invoice',
            'livemode': False,
            'customer': customer_id,
            'currency': 'usd',
            'status': 'paid',
            'collection_method': 'charge_automatically',
            'amount_remaining': 0,
            'amount_overpaid': 0,
            'starting_balance': 0,
            'ending_balance': 0,
            'pre_payment_credit_notes_amount': 0,
            'post_payment_credit_notes_amount': 0,
            'application': None,
            'on_behalf_of': None,
            'transfer_data': None,
        },
    )
    empty(
        invoice,
        'discounts',
        'total_discount_amounts',
        'total_pretax_credit_amounts',
        'total_taxes',
        'default_tax_rates',
    )
    if invoice.get('billing_reason') not in (
        'subscription_create',
        'subscription_cycle',
    ):
        raise BillingHold('unsupported_funding')
    require(mapping(invoice.get('automatic_tax')), {'enabled': False})
    parent = mapping(invoice.get('parent'))
    require(parent, {'type': 'subscription_details'})
    details = mapping(parent.get('subscription_details'))
    subscription_id = identity(details.get('subscription'), 'sub')
    subscription = subscriptions.get(subscription_id)
    if subscription is None:
        raise BillingHold('ownership_conflict')
    require(
        subscription,
        {
            'id': subscription_id,
            'object': 'subscription',
            'livemode': False,
            'customer': customer_id,
            'currency': 'usd',
            'collection_method': 'charge_automatically',
            'trial_start': None,
            'trial_end': None,
        },
    )
    empty(subscription, 'default_tax_rates', 'discounts')
    if subscription.get('status') not in (
        'active',
        'past_due',
        'unpaid',
        'canceled',
        'incomplete',
        'incomplete_expired',
        'paused',
    ):
        raise BillingHold('unsupported_funding')
    require(mapping(subscription.get('automatic_tax')), {'enabled': False})
    lines = native.all('invoices/' + invoice_id + '/lines')
    if len(lines) != 1:
        raise BillingHold('unsupported_funding')
    line = lines[0]
    line_id = identity(line.get('id'), 'il')
    require(
        line,
        {'object': 'line_item', 'livemode': False, 'currency': 'usd', 'quantity': 1},
    )
    empty(line, 'discount_amounts', 'discounts', 'pretax_credit_amounts', 'taxes')
    line_parent = mapping(line.get('parent'))
    require(line_parent, {'type': 'subscription_item_details'})
    line_details = mapping(line_parent.get('subscription_item_details'))
    require(line_details, {'subscription': subscription_id, 'proration': False})
    item_id = identity(line_details.get('subscription_item'), 'si')
    pricing = mapping(line.get('pricing'))
    require(pricing, {'type': 'price_details'})
    price_details = mapping(pricing.get('price_details'))
    price_id = identity(price_details.get('price'), 'price')
    offer = next((value for value in offers if value.price_id == price_id), None)
    if offer is None or price_details.get('product') != offer.product_id:
        raise BillingHold('unsupported_funding')
    amount = offer.amount
    require(
        invoice,
        {
            'amount_due': amount,
            'amount_paid': amount,
            'subtotal': amount,
            'subtotal_excluding_tax': amount,
            'total': amount,
            'total_excluding_tax': amount,
        },
    )
    require(line, {'amount': amount})
    items = native.all('subscription_items', {'subscription': subscription_id})
    if len(items) != 1:
        raise BillingHold('unsupported_funding')
    require(
        items[0],
        {
            'id': item_id,
            'object': 'subscription_item',
            'quantity': 1,
            'subscription': subscription_id,
        },
    )
    _historical_price(mapping(items[0].get('price')), offer)
    _historical_price(native.request('GET', 'prices/' + price_id), offer)
    payments = native.all('invoice_payments', {'invoice': invoice_id})
    if len(payments) != 1:
        raise BillingHold('unsupported_funding')
    payment = payments[0]
    payment_id = identity(payment.get('id'), 'inpay')
    require(
        payment,
        {
            'object': 'invoice_payment',
            'is_default': True,
            'invoice': invoice_id,
            'livemode': False,
            'currency': 'usd',
            'status': 'paid',
            'amount_paid': amount,
            'amount_requested': amount,
        },
    )
    funding = mapping(payment.get('payment'))
    require(funding, {'type': 'payment_intent'})
    pi_id = identity(funding.get('payment_intent'), 'pi')
    pi = native.request('GET', 'payment_intents/' + pi_id)
    require(
        pi,
        {
            'id': pi_id,
            'object': 'payment_intent',
            'livemode': False,
            'customer': customer_id,
            'currency': 'usd',
            'status': 'succeeded',
            'amount': amount,
            'amount_received': amount,
            'amount_capturable': 0,
            'payment_method_types': ['card'],
        },
    )
    if pi.get('capture_method') not in ('automatic', 'automatic_async'):
        raise BillingHold('unsupported_funding')
    charge_id = identity(pi.get('latest_charge'), 'ch')
    charge = native.request('GET', 'charges/' + charge_id)
    require(
        charge,
        {
            'id': charge_id,
            'object': 'charge',
            'livemode': False,
            'customer': customer_id,
            'payment_intent': pi_id,
            'currency': 'usd',
            'status': 'succeeded',
            'paid': True,
            'captured': True,
            'amount': amount,
            'amount_captured': amount,
        },
    )
    require(mapping(charge.get('payment_method_details')), {'type': 'card'})
    refunds: list[RefundFact] = []
    for refund in native.all('refunds', {'charge': charge_id}):
        require(
            refund,
            {
                'object': 'refund',
                'charge': charge_id,
                'payment_intent': pi_id,
                'currency': 'usd',
            },
        )
        try:
            refunds.append(
                RefundFact.model_validate(
                    {
                        'id': identity(refund.get('id'), 're'),
                        'amount': integer(refund.get('amount'), positive=True),
                        'status': refund.get('status'),
                    },
                    strict=True,
                )
            )
        except ValidationError:
            raise BillingHold('unsupported_funding') from None
    disputes: list[DisputeFact] = []
    for dispute in native.all('disputes', {'charge': charge_id}):
        require(
            dispute,
            {
                'object': 'dispute',
                'livemode': False,
                'charge': charge_id,
                'currency': 'usd',
            },
        )
        if dispute.get('payment_intent') not in (None, pi_id):
            raise BillingHold('ownership_conflict')
        try:
            disputes.append(
                DisputeFact.model_validate(
                    {
                        'id': identity(dispute.get('id'), 'du'),
                        'status': dispute.get('status'),
                    },
                    strict=True,
                )
            )
        except ValidationError:
            raise BillingHold('unsupported_funding') from None
    period = mapping(line.get('period'))
    paid_at = max(
        integer(mapping(invoice.get('status_transitions')).get('paid_at')),
        integer(mapping(payment.get('status_transitions')).get('paid_at')),
    )
    try:
        return Coverage(
            invoice_id=invoice_id,
            line_id=line_id,
            invoice_payment_id=payment_id,
            subscription_id=subscription_id,
            subscription_item_id=item_id,
            price_id=price_id,
            offer_id=offer.id,
            payment_intent_id=pi_id,
            charge_id=charge_id,
            currency='usd',
            period_start=integer(period.get('start')),
            period_end=integer(period.get('end'), positive=True),
            paid_at=paid_at,
            allocated_amount=amount,
            captured_amount=amount,
            base_amount=amount,
            tax_amount=0,
            refunds=tuple(refunds),
            disputes=tuple(disputes),
            verified_at=verified_at,
        )
    except ValidationError:
        raise BillingHold('unsupported_funding') from None
