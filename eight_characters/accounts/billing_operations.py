"""Immutable native requests and object-bound ownership/deletion seals.

Preparation is pure. The executor must persist the exact digest/key before HTTP,
and recover uncertain outcomes before replaying an original operation.
"""

import hmac
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from eight_characters.accounts.billing_access import (
    BillingConfig,
    BillingHold,
    binding_mac,
    check_scope,
)
from eight_characters.accounts.billing_native import Native, mapping, request_digest
from eight_characters.accounts.billing_records import (
    AccountBillingRecord,
    Deletion,
    Operation,
    ScopeRecord,
)
from eight_characters.accounts.records import RecordError, parse_timestamp

_PURPOSES = {
    'customer_create': ('customer_create',),
    'customer_seal': ('customer_seal',),
    'checkout_create': ('checkout_create', 'checkout_seal'),
    'cancel': ('cancel_period', 'cancel_delete'),
    'expire': ('expire',),
    'void_invoice': ('invoice_stop', 'invoice_void'),
    'delete_mark': ('delete_mark',),
    'customer_redact': ('customer_redact',),
}


def operation_kind(purpose: str) -> str:
    for kind, purposes in _PURPOSES.items():
        if purpose in purposes:
            return kind
    raise BillingHold('processing_failed')


@dataclass(frozen=True)
class NativeRequest:
    method: str
    path: str
    parameters: Mapping[str, str] = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'parameters', MappingProxyType(dict(self.parameters)))

    @property
    def digest(self) -> str:
        return request_digest(self.method, self.path, self.parameters)


def operation_key(
    config: BillingConfig, owner_id: str, purpose: str, operation_id: str
) -> str:
    if (
        purpose not in {value for values in _PURPOSES.values() for value in values}
        or re.fullmatch(r'[0-9a-f]{32}', owner_id) is None
        or re.fullmatch(r'[0-9a-f]{32}', operation_id) is None
    ):
        raise BillingHold('processing_failed')
    return f'ec_{config.namespace}_{owner_id}_{purpose}_{operation_id}'


def customer_mac(
    config: BillingConfig, owner_id: str, customer_id: str, operation_id: str
) -> str:
    return binding_mac(config, owner_id, customer_id, 'customer-sealed', operation_id)


def deletion_mac(
    config: BillingConfig,
    owner_id: str,
    customer_id: str,
    nonce: str,
    requested_at: str,
) -> str:
    try:
        parse_timestamp(requested_at)
    except RecordError:
        raise BillingHold('ownership_conflict') from None
    return binding_mac(
        config, owner_id, customer_id, 'customer-delete:' + requested_at, nonce
    )


def _metadata(values: dict[str, str], *, prefix: str = 'metadata') -> dict[str, str]:
    return {f'{prefix}[{name}]': value for name, value in values.items()}


def _native_id(value: str | None, prefix: str) -> str:
    if value is None or re.fullmatch(prefix + r'_[A-Za-z0-9_]+', value) is None:
        raise BillingHold('uncertain_operation')
    return value


def prepare_request(
    config: BillingConfig,
    origin: str,
    scope: ScopeRecord,
    owner: AccountBillingRecord,
    *,
    purpose: str,
    operation_id: str,
    intent_id: str | None,
    subject_id: str | None,
) -> NativeRequest:
    check_scope(config, scope)
    operation_key(config, owner.id, purpose, operation_id)
    shared = {'ec_scope': scope.id, 'ec_owner': owner.id}
    if purpose == 'customer_create':
        values = {
            **shared,
            'ec_operation': operation_id,
            'ec_creation_mac': binding_mac(
                config, owner.id, 'new-customer', 'customer-create', operation_id
            ),
        }
        parameters = _metadata(values)
        if owner.test_clock_id is not None:
            parameters['test_clock'] = owner.test_clock_id
        return NativeRequest('POST', 'customers', parameters)
    customer_id = _native_id(owner.customer_id, 'cus')
    if purpose == 'customer_seal':
        if owner.binding is None or subject_id != customer_id:
            raise BillingHold('ownership_conflict')
        original_id = owner.binding.operation_id
        values = {
            **shared,
            'ec_operation': original_id,
            'ec_creation_mac': binding_mac(
                config, owner.id, 'new-customer', 'customer-create', original_id
            ),
            'ec_customer_mac': customer_mac(config, owner.id, customer_id, original_id),
        }
        return NativeRequest('POST', 'customers/' + customer_id, _metadata(values))
    if purpose in ('checkout_create', 'checkout_seal'):
        binding = owner.binding
        if (
            binding is None
            or binding.state != 'sealed'
            or not hmac.compare_digest(
                binding.mac,
                customer_mac(config, owner.id, customer_id, binding.operation_id),
            )
        ):
            raise BillingHold('ownership_conflict')
        intent = next((value for value in owner.intents if value.id == intent_id), None)
        if intent is None:
            raise BillingHold('uncertain_operation')
        offer = next(
            (value for value in scope.offers if value.id == intent.offer_id), None
        )
        if offer is None:
            raise BillingHold('unsupported_funding')
        create_id = operation_id
        if purpose == 'checkout_seal':
            creators = [
                value
                for value in owner.operations
                if value.kind == 'checkout_create'
                and value.intent_id == intent_id
                and value.subject_id is None
            ]
            if len(creators) != 1 or subject_id != intent.checkout_id:
                raise BillingHold('uncertain_operation')
            create_id = creators[0].id
        values = {
            **shared,
            'ec_operation': create_id,
            'ec_intent': intent.id,
            'ec_offer': offer.id,
            'ec_creation_mac': binding_mac(
                config,
                owner.id,
                f'{customer_id}:{intent.id}:{offer.id}',
                'checkout-create',
                create_id,
            ),
        }
        if purpose == 'checkout_seal':
            checkout_id = _native_id(subject_id, 'cs_test')
            values['ec_checkout_mac'] = binding_mac(
                config, owner.id, checkout_id, 'checkout-sealed', create_id
            )
            return NativeRequest(
                'POST', 'checkout/sessions/' + checkout_id, _metadata(values)
            )
        parameters = {
            'mode': 'subscription',
            'customer': customer_id,
            'payment_method_types[0]': 'card',
            'line_items[0][price]': offer.price_id,
            'line_items[0][quantity]': '1',
            'expires_at': str(intent.expires_at),
            'success_url': origin + '/account/billing/return',
            'cancel_url': origin + '/account/billing/return',
            'automatic_tax[enabled]': 'false',
            'allow_promotion_codes': 'false',
            **_metadata(values),
            **_metadata(
                {**shared, 'ec_intent': intent.id, 'ec_offer': offer.id},
                prefix='subscription_data[metadata]',
            ),
        }
        return NativeRequest('POST', 'checkout/sessions', parameters)
    if purpose in ('cancel_period', 'cancel_delete'):
        subscription = _native_id(subject_id, 'sub')
        if purpose == 'cancel_period':
            return NativeRequest(
                'POST',
                'subscriptions/' + subscription,
                {'cancel_at_period_end': 'true'},
            )
        return NativeRequest(
            'DELETE',
            'subscriptions/' + subscription,
            {'invoice_now': 'false', 'prorate': 'false'},
        )
    if purpose == 'expire':
        return NativeRequest(
            'POST',
            'checkout/sessions/' + _native_id(subject_id, 'cs_test') + '/expire',
            {},
        )
    if purpose in ('invoice_stop', 'invoice_void'):
        invoice = _native_id(subject_id, 'in')
        return NativeRequest(
            'POST',
            'invoices/' + invoice + ('/void' if purpose == 'invoice_void' else ''),
            {} if purpose == 'invoice_void' else {'auto_advance': 'false'},
        )
    if purpose == 'delete_mark':
        decision = owner.deletion
        if (
            decision is None
            or decision.native_object_id != customer_id
            or subject_id != customer_id
        ):
            raise BillingHold('uncertain_operation')
        marker = deletion_mac(
            config, owner.id, customer_id, decision.nonce, decision.requested_at
        )
        if decision.native_marker != marker:
            raise BillingHold('ownership_conflict')
        return NativeRequest(
            'POST',
            'customers/' + customer_id,
            _metadata(
                {
                    **shared,
                    'ec_delete_nonce': decision.nonce,
                    'ec_delete_requested': decision.requested_at,
                    'ec_delete_mac': marker,
                }
            ),
        )
    if purpose == 'customer_redact':
        if subject_id != customer_id:
            raise BillingHold('ownership_conflict')
        return NativeRequest(
            'POST',
            'customers/' + customer_id,
            {
                name: ''
                for name in (
                    'email',
                    'name',
                    'phone',
                    'address',
                    'shipping',
                    'description',
                )
            },
        )
    raise BillingHold('processing_failed')


def request_for(
    config: BillingConfig,
    origin: str,
    scope: ScopeRecord,
    owner: AccountBillingRecord,
    operation: Operation,
) -> NativeRequest:
    purpose = operation_purpose(config, owner.id, operation)
    if operation.state in ('done', 'recovered') or operation.request_sha256 is None:
        raise BillingHold('uncertain_operation')
    request = prepare_request(
        config,
        origin,
        scope,
        owner,
        purpose=purpose,
        operation_id=operation.id,
        intent_id=operation.intent_id,
        subject_id=operation.subject_id,
    )
    if request.digest != operation.request_sha256:
        raise BillingHold('uncertain_operation')
    return request


def operation_purpose(
    config: BillingConfig, owner_id: str, operation: Operation
) -> str:
    purpose = next(
        (
            value
            for value in _PURPOSES[operation.kind]
            if operation.idempotency_key
            == operation_key(config, owner_id, value, operation.id)
        ),
        None,
    )
    if purpose is None:
        raise BillingHold('uncertain_operation')
    return purpose


def read_customer_binding(
    config: BillingConfig, customer: Native
) -> tuple[str, str, bool]:
    if (
        customer.get('object') != 'customer'
        or customer.get('livemode') is not False
        or customer.get('deleted') is True
    ):
        raise BillingHold('ownership_conflict')
    customer_id = customer.get('id')
    if not isinstance(customer_id, str):
        raise BillingHold('ownership_conflict')
    customer_id = _native_id(customer_id, 'cus')
    values = mapping(customer.get('metadata'))
    owner, original_id = values.get('ec_owner'), values.get('ec_operation')
    if (
        values.get('ec_scope') != config.namespace
        or not isinstance(owner, str)
        or re.fullmatch(r'[0-9a-f]{32}', owner) is None
        or not isinstance(original_id, str)
        or re.fullmatch(r'[0-9a-f]{32}', original_id) is None
    ):
        raise BillingHold('ownership_conflict')
    tag = values.get('ec_creation_mac')
    expected = binding_mac(
        config, owner, 'new-customer', 'customer-create', original_id
    )
    if not isinstance(tag, str) or not hmac.compare_digest(tag, expected):
        raise BillingHold('ownership_conflict')
    seal = values.get('ec_customer_mac')
    sealed = isinstance(seal, str) and hmac.compare_digest(
        seal, customer_mac(config, owner, customer_id, original_id)
    )
    return owner, original_id, sealed


def read_deletion(
    config: BillingConfig, customer: Native
) -> tuple[str, Deletion] | None:
    values = mapping(customer.get('metadata'))
    names = ('ec_delete_nonce', 'ec_delete_requested', 'ec_delete_mac')
    if not any(name in values for name in names):
        return None
    owner, nonce, requested, marker = (
        values.get(name) for name in ('ec_owner', *names)
    )
    customer_id = customer.get('id')
    if (
        customer.get('object') != 'customer'
        or customer.get('livemode') is not False
        or values.get('ec_scope') != config.namespace
        or not isinstance(customer_id, str)
        or not isinstance(owner, str)
        or re.fullmatch(r'[0-9a-f]{32}', owner) is None
        or not isinstance(nonce, str)
        or re.fullmatch(r'[0-9a-f]{32}', nonce) is None
        or not isinstance(requested, str)
        or not isinstance(marker, str)
    ):
        raise BillingHold('ownership_conflict')
    expected = deletion_mac(config, owner, customer_id, nonce, requested)
    if not hmac.compare_digest(marker, expected):
        raise BillingHold('ownership_conflict')
    return owner, Deletion(
        requested_at=requested,
        completed_at=None,
        nonce=nonce,
        native_object_id=customer_id,
        native_marker=marker,
        retain_until=None,
    )


def sealed_checkout(
    config: BillingConfig, owner: AccountBillingRecord, session: Native
) -> tuple[str, str]:
    values = mapping(session.get('metadata'))
    checkout_id = session.get('id')
    intent_id, original_id, offer_id, seal = (
        values.get(name)
        for name in ('ec_intent', 'ec_operation', 'ec_offer', 'ec_checkout_mac')
    )
    if (
        session.get('object') != 'checkout.session'
        or session.get('livemode') is not False
        or session.get('customer') != owner.customer_id
        or values.get('ec_scope') != config.namespace
        or values.get('ec_owner') != owner.id
        or not all(
            isinstance(value, str)
            for value in (checkout_id, intent_id, original_id, offer_id, seal)
        )
    ):
        raise BillingHold('ownership_conflict')
    if (
        not isinstance(checkout_id, str)
        or not isinstance(original_id, str)
        or not isinstance(seal, str)
        or not isinstance(intent_id, str)
        or not isinstance(offer_id, str)
    ):
        raise BillingHold('ownership_conflict')
    if not hmac.compare_digest(
        seal, binding_mac(config, owner.id, checkout_id, 'checkout-sealed', original_id)
    ):
        raise BillingHold('ownership_conflict')
    if (
        re.fullmatch(r'[0-9a-f]{32}', intent_id) is None
        or re.fullmatch(r'[0-9a-f]{32}', original_id) is None
        or re.fullmatch(r'[0-9a-f]{64}', offer_id) is None
    ):
        raise BillingHold('ownership_conflict')
    tag = values.get('ec_creation_mac')
    expected_tag = binding_mac(
        config,
        owner.id,
        f'{owner.customer_id}:{intent_id}:{offer_id}',
        'checkout-create',
        original_id,
    )
    if not isinstance(tag, str) or not hmac.compare_digest(tag, expected_tag):
        raise BillingHold('ownership_conflict')
    return intent_id, offer_id
