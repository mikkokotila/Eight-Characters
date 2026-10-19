"""Persist original request identity and fences on both sides of native HTTP.

A Work belongs to one lease. It never owns a SQL transaction across a provider
call. Discovery must precede replay; expired create uncertainty cannot be rotated.
"""

from dataclasses import dataclass, replace

from eight_characters.accounts.billing_access import BillingHold
from eight_characters.accounts.billing_authority import Authority, Lease
from eight_characters.accounts.billing_native import Native, Stripe, identity, require
from eight_characters.accounts.billing_operations import (
    customer_mac,
    deletion_mac,
    operation_key,
    operation_kind,
    prepare_request,
    read_customer_binding,
    request_for,
    sealed_checkout,
)
from eight_characters.accounts.billing_records import (
    AccountBillingRecord,
    Binding,
    Operation,
    ScopeRecord,
)
from eight_characters.accounts.records import new_id, parse_timestamp, timestamp


@dataclass
class Work:
    authority: Authority
    native: Stripe
    origin: str
    scope: ScopeRecord
    lease: Lease
    owner: AccountBillingRecord
    discovered: bool = False

    def __post_init__(self) -> None:
        self.native = Stripe(
            self.native.config, self.native.client, before_request=self.renew
        )

    def renew(self) -> None:
        self.authority.renew(self.lease)

    def save(self, owner: AccountBillingRecord) -> None:
        self.owner = self.authority.apply(self.lease, owner, keep_lease=True)
        self.lease = replace(
            self.lease, revision=self.owner.revision, lifecycle=self.owner.lifecycle
        )

    def refresh_unsent_checkout(self, intent_id: str) -> None:
        """Renew only a proven never-submitted deadline after complete discovery."""
        if not self.discovered or not self.authority.unsent_is_proven(self.lease):
            raise BillingHold('uncertain_operation')
        intent = next(value for value in self.owner.intents if value.id == intent_id)
        if intent.checkout_id is not None:
            raise BillingHold('uncertain_operation')
        creators = [
            operation
            for operation in self.owner.operations
            if operation.kind == 'checkout_create' and operation.intent_id == intent_id
        ]
        if len(creators) > 1 or any(
            operation.state != 'prepared' or operation.sent_at is not None
            for operation in creators
        ):
            raise BillingHold('uncertain_operation')
        changed = intent.model_copy(
            update={'expires_at': int(self.authority.clock().timestamp()) + 3600}
        )
        owner = self.owner.model_copy(
            update={
                'intents': tuple(
                    changed if value.id == intent_id else value
                    for value in self.owner.intents
                )
            }
        )
        operations: list[Operation] = []
        for operation in owner.operations:
            if operation in creators:
                request = prepare_request(
                    self.authority.config,
                    self.origin,
                    self.scope,
                    owner,
                    purpose='checkout_create',
                    operation_id=operation.id,
                    intent_id=intent_id,
                    subject_id=None,
                )
                operation = operation.model_copy(
                    update={'request_sha256': request.digest}
                )
            operations.append(operation)
        self.save(owner.model_copy(update={'operations': tuple(operations)}))

    def execute(
        self,
        purpose: str,
        *,
        intent_id: str | None = None,
        subject_id: str | None = None,
    ) -> Native:
        config = self.authority.config
        kind = operation_kind(purpose)
        matches = [
            operation
            for operation in self.owner.operations
            if operation.kind == kind
            and operation.intent_id == intent_id
            and operation.subject_id == subject_id
            and operation.idempotency_key
            == operation_key(config, self.owner.id, purpose, operation.id)
        ]
        if len(matches) > 1:
            raise BillingHold('uncertain_operation')
        now = self.authority.clock()
        if matches:
            operation = matches[0]
            if operation.state in ('done', 'recovered'):
                result_id = operation.result_id
                if result_id is None:
                    raise BillingHold('uncertain_operation')
                collection = (
                    'customers'
                    if kind
                    in (
                        'customer_create',
                        'customer_seal',
                        'delete_mark',
                        'customer_redact',
                    )
                    else 'checkout/sessions'
                    if kind in ('checkout_create', 'expire')
                    else 'subscriptions'
                    if kind == 'cancel'
                    else 'invoices'
                )
                return self.native.request('GET', collection + '/' + result_id)
            never_sent = (
                operation.state == 'prepared'
                and operation.sent_at is None
                and self.authority.unsent_is_proven(self.lease)
            )
            if not self.discovered or (
                not never_sent
                and int(now.timestamp())
                - int(
                    parse_timestamp(
                        operation.sent_at or operation.created_at
                    ).timestamp()
                )
                >= 24 * 3600
            ):
                raise BillingHold('uncertain_operation')
            request = request_for(
                config, self.origin, self.scope, self.owner, operation
            )
        else:
            operation_id = new_id()
            request = prepare_request(
                config,
                self.origin,
                self.scope,
                self.owner,
                purpose=purpose,
                operation_id=operation_id,
                intent_id=intent_id,
                subject_id=subject_id,
            )
            operation = Operation.model_validate(
                dict(
                    id=operation_id,
                    intent_id=intent_id,
                    kind=kind,
                    subject_id=subject_id,
                    request_sha256=request.digest,
                    idempotency_key=operation_key(
                        config, self.owner.id, purpose, operation_id
                    ),
                    created_at=timestamp(now),
                    sent_at=None,
                    state='prepared',
                    result_id=None,
                    reason=None,
                ),
                strict=True,
            )
            self.save(
                self.owner.model_copy(
                    update={'operations': (*self.owner.operations, operation)}
                )
            )
        operation = operation.model_copy(
            update={
                'state': 'sent',
                'sent_at': operation.sent_at or timestamp(now),
                'reason': operation.reason,
            }
        )
        self.save(
            self.owner.model_copy(
                update={
                    'operations': tuple(
                        operation if value.id == operation.id else value
                        for value in self.owner.operations
                    )
                }
            )
        )
        result = self.native.request(
            request.method,
            request.path,
            request.parameters,
            idempotency_key=operation.idempotency_key,
        )
        result_id = identity(
            result.get('id'),
            'cus'
            if kind
            in ('customer_create', 'customer_seal', 'delete_mark', 'customer_redact')
            else 'cs_test'
            if kind in ('checkout_create', 'expire')
            else 'sub'
            if kind == 'cancel'
            else 'in',
        )
        require(result, {'livemode': False})
        if subject_id is not None and result_id != subject_id:
            raise BillingHold('ownership_conflict')
        owner = self.owner
        if kind == 'customer_create':
            if (
                read_customer_binding(config, result)[:2] != (owner.id, operation.id)
                or result.get('test_clock') != owner.test_clock_id
            ):
                raise BillingHold('ownership_conflict')
            changes: dict[str, object] = {
                'customer_id': result_id,
                'binding': Binding(
                    operation_id=operation.id,
                    object_id=result_id,
                    state='unsealed',
                    mac=customer_mac(config, owner.id, result_id, operation.id),
                ),
            }
            if owner.deletion is not None:
                changes['deletion'] = owner.deletion.model_copy(
                    update={
                        'native_object_id': result_id,
                        'native_marker': deletion_mac(
                            config,
                            owner.id,
                            result_id,
                            owner.deletion.nonce,
                            owner.deletion.requested_at,
                        ),
                    }
                )
            owner = owner.model_copy(update=changes)
        elif kind == 'customer_seal':
            if owner.binding is None or read_customer_binding(config, result) != (
                owner.id,
                owner.binding.operation_id,
                True,
            ):
                raise BillingHold('ownership_conflict')
            owner = owner.model_copy(
                update={'binding': owner.binding.model_copy(update={'state': 'sealed'})}
            )
        elif purpose == 'checkout_create':
            require(
                result,
                {
                    'object': 'checkout.session',
                    'customer': owner.customer_id,
                    'mode': 'subscription',
                },
            )
            intent = next(value for value in owner.intents if value.id == intent_id)
            if result.get('expires_at') != intent.expires_at or result.get(
                'status'
            ) not in ('open', 'complete', 'expired'):
                raise BillingHold('uncertain_operation')
            owner = owner.model_copy(
                update={
                    'intents': tuple(
                        value.model_copy(
                            update={
                                'checkout_id': result_id,
                                'state': result['status'],
                                'subscription_id': None
                                if result.get('subscription') is None
                                else identity(result.get('subscription'), 'sub'),
                            }
                        )
                        if value.id == intent_id
                        else value
                        for value in owner.intents
                    )
                }
            )
        elif purpose == 'checkout_seal':
            if sealed_checkout(config, owner, result)[0] != intent_id:
                raise BillingHold('ownership_conflict')
        operation = operation.model_copy(
            update={'state': 'done', 'result_id': result_id, 'reason': operation.reason}
        )
        self.save(
            owner.model_copy(
                update={
                    'operations': tuple(
                        operation if value.id == operation.id else value
                        for value in owner.operations
                    )
                }
            )
        )
        return result
