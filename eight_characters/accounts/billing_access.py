"""Sold chart allowances, independent of legacy plans and transport state.

The caller supplies a newly observed native clock when the customer has one.
Wall time always remains the security clock. No receipt is extended by replay.
"""

import hashlib
import hmac
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal

from eight_characters.accounts.billing import (
    BillingError,
    SandboxCatalogueConfig,
    load_billing_config,
)
from eight_characters.accounts.billing_records import (
    AccountBillingRecord,
    Coverage,
    ScopeRecord,
)
from eight_characters.accounts.records import canonical_json

Tier = Literal['free', 'basic', 'plus', 'pro']
CAPS: Final[Mapping[Tier, int | None]] = {
    'free': 1,
    'basic': 5,
    'plus': 25,
    'pro': None,
}
_ACTIVE_DISPUTES: Final = frozenset(
    ('warning_needs_response', 'warning_under_review', 'needs_response', 'under_review')
)


class BillingHold(BillingError):
    """A named operational hold, never a paid entitlement or an absence proof."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class BillingBusy(BillingHold):
    """Another live worker owns this account; unrelated accounts can proceed."""

    def __init__(self) -> None:
        super().__init__('uncertain_operation')


@dataclass(frozen=True)
class BillingConfig:
    catalogue: SandboxCatalogueConfig
    namespace: str
    binding_key: bytes = field(repr=False)
    payload_version: str
    webhook_secrets: tuple[bytes, ...] = field(repr=False)
    clock_ids: tuple[str, ...]
    purchase_clock: str | None
    poll_seconds: int
    lease_seconds: int
    payment_method_configuration: str

    @property
    def binding_key_id(self) -> str:
        return hashlib.sha256(self.binding_key).hexdigest()


def _setting(values: Mapping[str, str], name: str, pattern: str) -> str:
    value = values.get(name, '')
    if re.fullmatch(pattern, value) is None:
        raise BillingError(f'{name} is missing or malformed.')
    return value


def load_runtime_config(
    values: Mapping[str, str], *, session_secret: bytes
) -> BillingConfig | None:
    catalogue = load_billing_config(values)
    names = (
        'EC_BILLING_NAMESPACE',
        'EC_BILLING_BINDING_KEY',
        'EC_BILLING_TEST_CLOCK_IDS',
        'EC_BILLING_PURCHASE_CLOCK',
        'EC_BILLING_POLL_SECONDS',
        'EC_BILLING_LEASE_SECONDS',
        'EC_STRIPE_PAYMENT_METHOD_CONFIGURATION',
    )
    if catalogue is None:
        if any(name in values for name in names):
            raise BillingError(
                'Billing authority configuration is present while disabled.'
            )
        return None
    if not catalogue.api_key.startswith('rk_test_'):
        raise BillingError('The runtime requires a restricted sandbox credential.')
    namespace = _setting(values, 'EC_BILLING_NAMESPACE', r'[0-9a-f]{32}')
    key = _setting(values, 'EC_BILLING_BINDING_KEY', r'[A-Za-z0-9_-]{43,256}').encode()
    if hmac.compare_digest(key, session_secret):
        raise BillingError('Billing and session keys must be independently generated.')
    version = _setting(
        values, 'EC_STRIPE_PAYLOAD_VERSION', r'\d{4}-\d{2}-\d{2}\.[a-z]+'
    )
    current = _setting(
        values, 'EC_STRIPE_WEBHOOK_SECRET', r'whsec_[A-Za-z0-9]+'
    ).encode()
    previous = values.get('EC_STRIPE_WEBHOOK_PREVIOUS_SECRET')
    secrets = (current,)
    if previous is not None:
        _setting(values, 'EC_STRIPE_WEBHOOK_PREVIOUS_SECRET', r'whsec_[A-Za-z0-9]+')
        secrets += (previous.encode(),)
    clocks = tuple(filter(None, values.get('EC_BILLING_TEST_CLOCK_IDS', '').split(',')))
    if len(set(clocks)) != len(clocks) or any(
        re.fullmatch(r'clock_[A-Za-z0-9]+', value) is None for value in clocks
    ):
        raise BillingError('EC_BILLING_TEST_CLOCK_IDS is malformed or repeated.')
    purchase_clock = values.get('EC_BILLING_PURCHASE_CLOCK')
    if purchase_clock is not None and purchase_clock not in clocks:
        raise BillingError('The purchase clock must be among the retained clocks.')
    poll = int(_setting(values, 'EC_BILLING_POLL_SECONDS', r'[1-9][0-9]{0,3}'))
    lease = int(_setting(values, 'EC_BILLING_LEASE_SECONDS', r'[1-9][0-9]{0,3}'))
    payment_configuration = _setting(
        values, 'EC_STRIPE_PAYMENT_METHOD_CONFIGURATION', r'pmc_[A-Za-z0-9]+'
    )
    return BillingConfig(
        catalogue,
        namespace,
        key,
        version,
        secrets,
        clocks,
        purchase_clock,
        poll,
        lease,
        payment_configuration,
    )


def binding_mac(
    config: BillingConfig,
    owner: str,
    object_id: str,
    purpose: str,
    operation_id: str,
) -> str:
    message = canonical_json(
        {
            'domain': 'eight-characters-billing-v1',
            'namespace': config.namespace,
            'account': config.catalogue.account_id,
            'owner': owner,
            'object': object_id,
            'purpose': purpose,
            'operation': operation_id,
        }
    )
    return hmac.new(config.binding_key, message, hashlib.sha256).hexdigest()


def check_scope(config: BillingConfig, scope: ScopeRecord) -> None:
    if (
        scope.id != config.namespace
        or scope.account_id != config.catalogue.account_id
        or scope.livemode is not False
        or scope.binding_key_id != config.binding_key_id
        or scope.api_version != config.catalogue.api_version
        or not set(scope.clock_ids) <= set(config.clock_ids)
    ):
        raise BillingHold('scope_mismatch')


def returned_amount(coverage: Coverage) -> int:
    return sum(fact.amount for fact in coverage.refunds if fact.status == 'succeeded')


@dataclass(frozen=True)
class Access:
    tier: Tier
    status: Literal['free', 'paid', 'pending', 'held', 'expired', 'deleting', 'deleted']
    paid_through: int | None
    reason: str | None = None

    @property
    def chart_limit(self) -> int | None:
        return CAPS[self.tier]


def effective_access(
    scope: ScopeRecord,
    owner: AccountBillingRecord | None,
    *,
    now: int,
    ready: bool,
) -> Access:
    """One absolute interval predicate for both display and transactional writes."""
    if not ready:
        raise BillingHold('unverified')
    if owner is None:
        return Access('free', 'free', None)
    if owner.scope_id != scope.id:
        raise BillingHold('scope_mismatch')
    if owner.lifecycle in ('deleting', 'deleted'):
        return Access('free', owner.lifecycle, None, 'deleted_owner')
    if owner.lifecycle == 'held':
        return Access('free', 'held', None, 'unverified')
    offers = {offer.id: offer for offer in scope.offers}
    current: list[tuple[Tier, int]] = []
    held = False
    for coverage in owner.coverage:
        if not coverage.period_start <= now < coverage.period_end:
            continue
        if returned_amount(coverage) == coverage.captured_amount:
            continue
        if any(fact.status == 'lost' for fact in coverage.disputes):
            continue
        if any(fact.status in _ACTIVE_DISPUTES for fact in coverage.disputes):
            held = True
            continue
        offer = offers.get(coverage.offer_id)
        if offer is None or offer.price_id != coverage.price_id:
            raise BillingHold('unsupported_funding')
        current.append((offer.plan, coverage.period_end))
    tiers = {tier for tier, _ in current}
    if len(tiers) > 1:
        return Access('free', 'held', None, 'unsupported_overlap')
    if current:
        return Access(current[0][0], 'paid', max(end for _, end in current))
    if held:
        return Access('free', 'held', None, 'unverified')
    if any(intent.state == 'held' for intent in owner.intents):
        return Access('free', 'held', None, 'uncertain_operation')
    if any(intent.state not in ('expired', 'complete') for intent in owner.intents):
        return Access('free', 'pending', None)
    return Access('free', 'expired' if owner.coverage else 'free', None)
