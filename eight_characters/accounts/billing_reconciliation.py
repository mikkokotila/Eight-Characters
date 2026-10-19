"""Complete native discovery and current financial observations, without writes.

Positive native creation provenance may recover an unsealed Customer. A copied
creation tag is insufficient. Session ownership requires its object-bound seal.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from eight_characters.accounts.billing_access import BillingConfig, BillingHold
from eight_characters.accounts.billing_native import (
    Native,
    Stripe,
    captured_coverage,
    identity,
    integer,
    mapping,
    require,
)
from eight_characters.accounts.billing_operations import (
    operation_key,
    read_customer_binding,
    read_deletion,
    sealed_checkout,
)
from eight_characters.accounts.billing_records import (
    AccountBillingRecord,
    Coverage,
    Deletion,
    ScopeRecord,
)


@dataclass(frozen=True)
class CustomerProof:
    owner_id: str
    customer_id: str
    operation_id: str
    clock_id: str | None
    sealed: bool
    creation_proven: bool
    deletion: Deletion | None


@dataclass(frozen=True)
class Observation:
    customer: Native
    sessions: tuple[Native, ...]
    subscriptions: tuple[Native, ...]
    invoices: tuple[Native, ...]
    coverage: tuple[Coverage, ...]
    now: int


def _creation_proven(
    config: BillingConfig, proof: CustomerProof, events: Sequence[Native]
) -> bool:
    key = operation_key(config, proof.owner_id, 'customer_create', proof.operation_id)
    for event in events:
        if event.get('type') != 'customer.created':
            continue
        require(event, {'object': 'event', 'livemode': False})
        if (
            event.get('account') not in (None, config.catalogue.account_id)
            or event.get('context') is not None
        ):
            raise BillingHold('scope_mismatch')
        request = event.get('request')
        if not isinstance(request, dict):
            continue
        if mapping(request).get('idempotency_key') != key:
            continue
        customer = mapping(mapping(event.get('data')).get('object'))
        if customer.get('id') == proof.customer_id and read_customer_binding(
            config, customer
        )[:2] == (proof.owner_id, proof.operation_id):
            return True
    return False


def discover_customers(native: Stripe, scope: ScopeRecord) -> tuple[CustomerProof, ...]:
    """Enumerate every current/retained clock and non-clock Customer, never Search."""
    native.account()
    config = native.config
    clocks = native.all('test_helpers/test_clocks')
    clock_ids = {identity(clock.get('id'), 'clock') for clock in clocks}
    if not set(scope.clock_ids) <= clock_ids:
        raise BillingHold('clock_unavailable')
    customers = list(native.all('customers'))
    for clock_id in sorted(clock_ids | set(scope.clock_ids)):
        customers.extend(native.all('customers', {'test_clock': clock_id}))
    found: dict[str, CustomerProof] = {}
    owners: set[str] = set()
    for customer in customers:
        metadata = mapping(customer.get('metadata'))
        if metadata.get('ec_scope') != config.namespace:
            continue
        owner, operation, sealed = read_customer_binding(config, customer)
        customer_id = identity(customer.get('id'), 'cus')
        clock_id = customer.get('test_clock')
        if clock_id is not None:
            clock_id = identity(clock_id, 'clock')
            if clock_id not in scope.clock_ids:
                raise BillingHold('clock_unavailable')
            native.clock(clock_id)
        decision = read_deletion(config, customer)
        if decision is not None and decision[0] != owner:
            raise BillingHold('ownership_conflict')
        proof = CustomerProof(
            owner,
            customer_id,
            operation,
            clock_id,
            sealed,
            False,
            None if decision is None else decision[1],
        )
        if customer_id in found:
            if found[customer_id] != proof:
                raise BillingHold('ownership_conflict')
            continue
        if owner in owners:
            raise BillingHold('ownership_conflict')
        owners.add(owner)
        found[customer_id] = proof
    # Events provide only positive request provenance inside their retention.
    # Their absence is never used to release uncertainty or create another object.
    events = (
        native.all('events', {'type': 'customer.created'})
        if any(not proof.sealed for proof in found.values())
        else ()
    )
    return tuple(
        CustomerProof(
            proof.owner_id,
            proof.customer_id,
            proof.operation_id,
            proof.clock_id,
            proof.sealed,
            proof.sealed or _creation_proven(config, proof, events),
            proof.deletion,
        )
        for proof in found.values()
    )


def observe_owner(
    native: Stripe,
    scope: ScopeRecord,
    owner: AccountBillingRecord,
    *,
    wall_time: int,
    verified_at: str,
) -> Observation:
    customer_id = identity(owner.customer_id, 'cus')
    customer = native.request('GET', 'customers/' + customer_id)
    proof_owner, operation, sealed = read_customer_binding(native.config, customer)
    if (
        proof_owner != owner.id
        or not sealed
        or owner.binding is None
        or owner.binding.operation_id != operation
        or owner.binding.state != 'sealed'
        or customer.get('test_clock') != owner.test_clock_id
    ):
        raise BillingHold('ownership_conflict')
    now = (
        wall_time if owner.test_clock_id is None else native.clock(owner.test_clock_id)
    )
    sessions = native.all('checkout/sessions', {'customer': customer_id})
    proven_subscriptions: set[str] = set()
    seen_intents: set[str] = set()
    for session in sessions:
        intent_id, offer_id = sealed_checkout(native.config, owner, session)
        if intent_id in seen_intents or not any(
            offer.id == offer_id for offer in scope.offers
        ):
            raise BillingHold('ownership_conflict')
        seen_intents.add(intent_id)
        require(
            session,
            {
                'mode': 'subscription',
                'customer': customer_id,
                'livemode': False,
                'payment_method_types': ['card'],
            },
        )
        created = integer(session.get('created'))
        expires = integer(session.get('expires_at'), positive=True)
        if not 0 < expires - created <= 3600 or session.get('status') not in (
            'open',
            'complete',
            'expired',
        ):
            raise BillingHold('unsupported_funding')
        known = next(
            (intent for intent in owner.intents if intent.id == intent_id), None
        )
        if known is not None and (
            known.checkout_id != session.get('id')
            or known.expires_at != expires
            or known.offer_id != offer_id
        ):
            raise BillingHold('ownership_conflict')
        if session.get('subscription') is not None:
            proven_subscriptions.add(identity(session.get('subscription'), 'sub'))
    if any(
        intent.checkout_id is not None and intent.id not in seen_intents
        for intent in owner.intents
    ):
        raise BillingHold('uncertain_operation')
    subscriptions = native.all(
        'subscriptions', {'customer': customer_id, 'status': 'all'}
    )
    by_id: dict[str, Native] = {}
    for subscription in subscriptions:
        identifier = identity(subscription.get('id'), 'sub')
        require(
            subscription,
            {'object': 'subscription', 'livemode': False, 'customer': customer_id},
        )
        if identifier not in proven_subscriptions or subscription.get('status') not in (
            'active',
            'past_due',
            'unpaid',
            'canceled',
            'incomplete',
            'incomplete_expired',
            'paused',
            'trialing',
        ):
            raise BillingHold('ownership_conflict')
        by_id[identifier] = subscription
    if proven_subscriptions != by_id.keys():
        raise BillingHold('uncertain_operation')
    invoices = native.all('invoices', {'customer': customer_id})
    coverage: list[Coverage] = []
    for invoice in invoices:
        require(
            invoice, {'object': 'invoice', 'livemode': False, 'customer': customer_id}
        )
        if invoice.get('status') not in (
            'draft',
            'open',
            'paid',
            'void',
            'uncollectible',
        ):
            raise BillingHold('unsupported_funding')
        if invoice['status'] == 'paid':
            coverage.append(
                captured_coverage(
                    native,
                    invoice,
                    customer_id=customer_id,
                    subscriptions=by_id,
                    offers=scope.offers,
                    verified_at=verified_at,
                )
            )
    if any(
        old.invoice_id not in {fact.invoice_id for fact in coverage}
        for old in owner.coverage
    ):
        raise BillingHold('uncertain_operation')
    return Observation(
        customer, sessions, subscriptions, invoices, tuple(coverage), now
    )
