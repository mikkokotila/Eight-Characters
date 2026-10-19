"""Read-only proof of the native sandbox catalogue, before purchases are possible.

The offer is product policy; Stripe identifiers, credentials and API version are
operator configuration. This module creates no customer, checkout or entitlement.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final, cast

import httpx


class BillingError(Exception):
    """The configured sandbox catalogue could not be independently verified."""


@dataclass(frozen=True)
class Offer:
    plan: str
    period: str
    interval: str
    amount: int

    @property
    def key(self) -> str:
        return f'{self.plan}_{self.period}'


OFFERS: Final = (
    Offer('basic', 'monthly', 'month', 699),
    Offer('basic', 'yearly', 'year', 5900),
    Offer('plus', 'monthly', 'month', 1499),
    Offer('plus', 'yearly', 'year', 12900),
    Offer('pro', 'monthly', 'month', 2900),
    Offer('pro', 'yearly', 'year', 24900),
)


@dataclass(frozen=True)
class SandboxCatalogueConfig:
    api_key: str = field(repr=False)
    api_version: str
    account_id: str
    price_ids: tuple[str, ...]
    product_ids: tuple[str, ...]


def _required(values: Mapping[str, str], name: str, pattern: str) -> str:
    value = values.get(name, '')
    if re.fullmatch(pattern, value) is None:
        # Never repeat configuration values: they may contain credentials.
        raise BillingError(f'{name} is missing or malformed.')
    return value


def load_billing_config(values: Mapping[str, str]) -> SandboxCatalogueConfig | None:
    """None is explicitly disabled; incomplete or live configuration is an error."""
    mode = values.get('EC_BILLING_MODE', 'disabled')
    if mode == 'disabled':
        if any(name.startswith('EC_STRIPE_') for name in values):
            raise BillingError(
                'Stripe configuration is present while billing is disabled.'
            )
        return None
    if mode != 'sandbox':
        raise BillingError(
            'EC_BILLING_MODE must be disabled or sandbox; live billing is unavailable.'
        )
    key = _required(values, 'EC_STRIPE_API_KEY', r'(?:sk|rk)_test_[A-Za-z0-9]+')
    version = _required(values, 'EC_STRIPE_API_VERSION', r'\d{4}-\d{2}-\d{2}\.[a-z]+')
    account = _required(values, 'EC_STRIPE_ACCOUNT_ID', r'acct_[A-Za-z0-9]+')
    prices = tuple(
        _required(values, f'EC_STRIPE_PRICE_{offer.key.upper()}', r'price_[A-Za-z0-9]+')
        for offer in OFFERS
    )
    products = tuple(
        _required(values, f'EC_STRIPE_PRODUCT_{plan.upper()}', r'[A-Za-z0-9_-]{1,128}')
        for plan in ('basic', 'plus', 'pro')
    )
    if len(set(prices)) != len(prices) or len(set(products)) != len(products):
        raise BillingError(
            'Each offer needs its own price; each plan needs its own product.'
        )
    return SandboxCatalogueConfig(key, version, account, prices, products)


def _native_get(
    client: httpx.Client,
    config: SandboxCatalogueConfig,
    path: str,
    *,
    expanded_product: bool = False,
    before_request: Callable[[], None] | None = None,
) -> dict[str, Any]:
    if before_request is not None:
        before_request()
    try:
        response = client.get(
            f'https://api.stripe.com/v1/{path}',
            headers={
                'Authorization': f'Bearer {config.api_key}',
                'Stripe-Version': config.api_version,
            },
            params={'expand[]': 'product'} if expanded_product else None,
            timeout=10.0,
            follow_redirects=False,
        )
    except httpx.HTTPError:
        raise BillingError(
            'Stripe could not be reached; catalogue remains unverified.'
        ) from None
    if response.status_code != 200:
        raise BillingError(
            f'Stripe catalogue read failed (HTTP {response.status_code}).'
        )
    if response.headers.get('Stripe-Version') != config.api_version:
        raise BillingError(
            'Stripe response API version differs from the configured version.'
        )
    try:
        value = response.json()
    except ValueError:
        raise BillingError('Stripe returned invalid catalogue JSON.') from None
    if not isinstance(value, dict):
        raise BillingError('Stripe returned a malformed catalogue object.')
    return cast(dict[str, Any], value)


def _verify_price(
    price: dict[str, Any], offer: Offer, price_id: str, product_id: str
) -> None:
    recurring = price.get('recurring')
    product = price.get('product')
    if not isinstance(recurring, dict) or not isinstance(product, dict):
        raise BillingError(f'Native catalogue mismatch for {offer.key}.')
    recurring = cast(dict[str, Any], recurring)
    product = cast(dict[str, Any], product)
    expected = {
        'id': price_id,
        'object': 'price',
        'active': True,
        'livemode': False,
        'currency': 'usd',
        'unit_amount': offer.amount,
        'type': 'recurring',
        'unit_amount_decimal': str(offer.amount),
        'billing_scheme': 'per_unit',
        'tax_behavior': 'exclusive',
    }
    if (
        any(
            type(price.get(key)) is not type(value) or price[key] != value
            for key, value in expected.items()
        )
        or not {'custom_unit_amount', 'transform_quantity', 'tiers_mode'}
        <= price.keys()
        or 'trial_period_days' not in recurring
        or recurring.get('interval') != offer.interval
        or type(recurring.get('interval_count')) is not int
        or recurring['interval_count'] != 1
        or recurring.get('usage_type') != 'licensed'
        or recurring.get('trial_period_days') is not None
        or price.get('custom_unit_amount') is not None
        or price.get('transform_quantity') is not None
        or price.get('tiers_mode') is not None
        or product.get('id') != product_id
        or product.get('object') != 'product'
        or product.get('active') is not True
        or product.get('livemode') is not False
    ):
        raise BillingError(f'Native catalogue mismatch for {offer.key}.')


def verify_sandbox_catalogue(
    config: SandboxCatalogueConfig,
    client: httpx.Client,
    *,
    before_request: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Only GET: bind the key's own account, then independently inspect all prices."""
    account = _native_get(client, config, 'account', before_request=before_request)
    if account.get('object') != 'account' or account.get('id') != config.account_id:
        raise BillingError('The Stripe credential belongs to a different account.')
    verified: list[dict[str, Any]] = []
    for index, offer in enumerate(OFFERS):
        price_id = config.price_ids[index]
        product_id = config.product_ids[index // 2]
        price = _native_get(
            client,
            config,
            f'prices/{price_id}',
            expanded_product=True,
            before_request=before_request,
        )
        _verify_price(price, offer, price_id, product_id)
        verified.append(
            {
                'plan': offer.plan,
                'period': offer.period,
                'price_id': price_id,
                'product_id': product_id,
                'currency': 'usd',
                'unit_amount': offer.amount,
                'interval': offer.interval,
                'interval_count': 1,
                'required_quantity': 1,
                'tax_behavior': 'exclusive',
            }
        )
    return {
        'status': 'catalogue_verified',
        'mode': 'sandbox',
        'account_id': config.account_id,
        'api_version': config.api_version,
        'offers': verified,
        'checkout_available': False,
        'payment_verified': False,
        'paid_access_verified': False,
        'tax_calculation_verified': False,
    }
