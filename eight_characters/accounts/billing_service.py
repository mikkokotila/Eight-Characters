"""Account-owned sandbox purchase, current-money reconciliation and erasure.

Native facts, original operation identities and a fresh recovery epoch control
access. Browser redirects and webhook bodies never supply financial authority.
"""

import asyncio
import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from urllib.parse import urlsplit

from eight_characters.accounts.billing import BillingError, verify_sandbox_catalogue
from eight_characters.accounts.billing_access import (
    BillingConfig,
    BillingHold,
    effective_access,
    returned_amount,
)
from eight_characters.accounts.billing_authority import Authority
from eight_characters.accounts.billing_executor import Work
from eight_characters.accounts.billing_native import (
    Stripe,
    identity,
    integer,
    mapping,
)
from eight_characters.accounts.billing_operations import (
    customer_mac,
    deletion_mac,
    operation_key,
    operation_purpose,
    prepare_request,
    read_deletion,
    sealed_checkout,
)
from eight_characters.accounts.billing_reconciliation import (
    CustomerProof,
    Observation,
    discover_customers,
    observe_owner,
)
from eight_characters.accounts.billing_records import (
    AccountBillingRecord,
    Binding,
    EventRecord,
    Intent,
    Operation,
    ScopeRecord,
)
from eight_characters.accounts.records import new_id, timestamp
from eight_characters.accounts.store import AccountStore

logger = logging.getLogger(__name__)


class PurchaseConflict(Exception):
    """An existing purchase or paid period occupies this account."""


class BillingService:
    def __init__(
        self,
        store: AccountStore,
        config: BillingConfig,
        origin: str,
        native: Stripe,
        *,
        clock: Callable[[], datetime],
    ) -> None:
        self.store, self.config, self.origin, self.native, self.clock = (
            store,
            config,
            origin,
            native,
            clock,
        )
        self.authority = Authority(store, config, clock=clock)
        # No native HTTP has occurred when this gate commits.
        self.epoch = self.authority.begin_recovery()

    def _snapshot(self) -> tuple[ScopeRecord, tuple[AccountBillingRecord, ...], bool]:
        records, epoch, ready = self.authority.snapshot()
        if epoch != self.epoch:
            raise BillingHold('uncertain_operation')
        return (
            self.authority.scope(records),
            tuple(
                record for record in records if isinstance(record, AccountBillingRecord)
            ),
            ready,
        )

    def _claim(self, owner_id: str) -> Work:
        scope, _, _ = self._snapshot()
        lease, owner = self.authority.claim(owner_id, recovery_epoch=self.epoch)
        return Work(self.authority, self.native, self.origin, scope, lease, owner)

    def _adopt(self, scope: ScopeRecord, proof: CustomerProof) -> None:
        if not proof.creation_proven:
            raise BillingHold('uncertain_operation')
        present = self.store.user_by_id(proof.owner_id) is not None
        now = timestamp(self.clock())
        operation = Operation(
            id=proof.operation_id,
            intent_id=None,
            kind='customer_create',
            subject_id=None,
            request_sha256=None,
            idempotency_key=operation_key(
                self.config, proof.owner_id, 'customer_create', proof.operation_id
            ),
            created_at=now,
            sent_at=None,
            state='recovered',
            result_id=proof.customer_id,
            reason=None,
        )
        owner = AccountBillingRecord(
            schema=2,
            id=proof.owner_id,
            owner_id=proof.owner_id,
            scope_id=scope.id,
            revision=0,
            created_at=now,
            updated_at=now,
            customer_id=proof.customer_id,
            test_clock_id=proof.clock_id,
            lifecycle='deleting' if proof.deletion else 'active' if present else 'held',
            binding=Binding(
                operation_id=proof.operation_id,
                object_id=proof.customer_id,
                state='sealed' if proof.sealed else 'unsealed',
                mac=customer_mac(
                    self.config, proof.owner_id, proof.customer_id, proof.operation_id
                ),
            ),
            intents=(),
            operations=(operation,),
            coverage=(),
            deletion=proof.deletion,
        )
        self.authority.adopt(owner, epoch=self.epoch)

    def _customer(self, work: Work, proofs: Sequence[CustomerProof]) -> None:
        proof = next(
            (value for value in proofs if value.owner_id == work.owner.id), None
        )
        owner = work.owner
        if proof is not None:
            known_create = next(
                (
                    operation
                    for operation in owner.operations
                    if operation.id == proof.operation_id
                    and operation.kind == 'customer_create'
                    and operation.state in ('done', 'recovered')
                    and operation.result_id == proof.customer_id
                ),
                None,
            )
            if not proof.creation_proven and known_create is None:
                raise BillingHold('uncertain_operation')
            if (
                owner.customer_id not in (None, proof.customer_id)
                or owner.test_clock_id != proof.clock_id
            ):
                raise BillingHold('ownership_conflict')
            binding = Binding(
                operation_id=proof.operation_id,
                object_id=proof.customer_id,
                state='sealed' if proof.sealed else 'unsealed',
                mac=customer_mac(
                    self.config, owner.id, proof.customer_id, proof.operation_id
                ),
            )
            operations = tuple(
                operation.model_copy(
                    update={
                        'state': 'recovered',
                        'result_id': proof.customer_id,
                        'reason': operation.reason,
                    }
                )
                if operation.id == proof.operation_id
                or (
                    operation.kind == 'customer_seal'
                    and operation.subject_id == proof.customer_id
                    and proof.sealed
                )
                else operation
                for operation in owner.operations
            )
            deletion = owner.deletion
            if proof.deletion is not None:
                if deletion is not None and deletion.nonce != proof.deletion.nonce:
                    raise BillingHold('ownership_conflict')
                deletion = proof.deletion if deletion is None else deletion
            if deletion is not None and deletion.native_object_id is None:
                deletion = deletion.model_copy(
                    update={
                        'native_object_id': proof.customer_id,
                        'native_marker': deletion_mac(
                            self.config,
                            owner.id,
                            proof.customer_id,
                            deletion.nonce,
                            deletion.requested_at,
                        ),
                    }
                )
            changes: dict[str, object] = {
                'schema_version': 2,
                'customer_id': proof.customer_id,
                'binding': binding,
                'operations': operations,
                'deletion': deletion,
            }
            if deletion is not None and owner.lifecycle != 'deleted':
                changes['lifecycle'] = 'deleting'
            work.save(owner.model_copy(update=changes))
        elif owner.customer_id is not None:
            raise BillingHold('uncertain_operation')
        work.discovered = True
        if work.owner.customer_id is None:
            creates = [
                operation
                for operation in work.owner.operations
                if operation.kind == 'customer_create'
            ]
            if creates or (
                work.owner.lifecycle == 'active'
                and any(
                    intent.state not in ('complete', 'expired')
                    for intent in work.owner.intents
                )
            ):
                work.execute('customer_create')
        if work.owner.binding is not None and work.owner.binding.state != 'sealed':
            work.execute('customer_seal', subject_id=work.owner.customer_id)

    def _sessions(self, work: Work) -> None:
        if work.owner.customer_id is None:
            return
        sessions = self.native.all(
            'checkout/sessions', {'customer': work.owner.customer_id}
        )
        for session in sessions:
            metadata = mapping(session.get('metadata'))
            intent_id = metadata.get('ec_intent')
            intent = next(
                (value for value in work.owner.intents if value.id == intent_id), None
            )
            try:
                recovered_id, offer_id = sealed_checkout(
                    self.config, work.owner, session
                )
            except BillingHold:
                if intent is None:
                    raise
                create = next(
                    (
                        operation
                        for operation in work.owner.operations
                        if operation.kind == 'checkout_create'
                        and operation.subject_id is None
                        and operation.intent_id == intent.id
                    ),
                    None,
                )
                if create is None or create.id != metadata.get('ec_operation'):
                    raise
                # Replaying a recent original create obtains native request
                # provenance. An unsealed list match alone authorizes nothing.
                work.execute('checkout_create', intent_id=intent.id)
                current = next(
                    value for value in work.owner.intents if value.id == intent.id
                )
                session = work.execute(
                    'checkout_seal', intent_id=intent.id, subject_id=current.checkout_id
                )
                recovered_id, offer_id = sealed_checkout(
                    self.config, work.owner, session
                )
            if not any(offer.id == offer_id for offer in work.scope.offers):
                raise BillingHold('unsupported_funding')
            checkout_id = identity(session.get('id'), 'cs_test')
            state = session.get('status')
            if state not in ('open', 'complete', 'expired'):
                raise BillingHold('unsupported_funding')
            sub_id = session.get('subscription')
            sub_id = None if sub_id is None else identity(sub_id, 'sub')
            if intent is None:
                intent = Intent(
                    id=recovered_id,
                    offer_id=offer_id,
                    created_at=timestamp(
                        datetime.fromtimestamp(
                            integer(session.get('created')), self.clock().tzinfo
                        )
                    ),
                    expires_at=integer(session.get('expires_at'), positive=True),
                    state=state,
                    checkout_id=checkout_id,
                    subscription_id=sub_id,
                )
                work.save(
                    work.owner.model_copy(
                        update={'intents': (*work.owner.intents, intent)}
                    )
                )
            else:
                if (
                    intent.offer_id != offer_id
                    or intent.checkout_id not in (None, checkout_id)
                    or intent.expires_at != session.get('expires_at')
                ):
                    raise BillingHold('ownership_conflict')
                changed = intent.model_copy(
                    update={
                        'checkout_id': checkout_id,
                        'subscription_id': sub_id,
                        'state': state,
                    }
                )
                work.save(
                    work.owner.model_copy(
                        update={
                            'intents': tuple(
                                changed if value.id == intent.id else value
                                for value in work.owner.intents
                            )
                        }
                    )
                )
            original_id = metadata.get('ec_operation')
            work.save(
                work.owner.model_copy(
                    update={
                        'operations': tuple(
                            operation.model_copy(
                                update={
                                    'state': 'recovered',
                                    'result_id': checkout_id,
                                    'reason': None,
                                }
                            )
                            if operation.kind == 'checkout_create'
                            and operation.intent_id == recovered_id
                            and (
                                operation.subject_id == checkout_id
                                or operation.id == original_id
                            )
                            else operation
                            for operation in work.owner.operations
                        )
                    }
                )
            )
        # A reservation may have committed just before process death, before the
        # first Session request. Resume only its original intent and frozen terms.
        for intent in work.owner.intents:
            if (
                intent.checkout_id is None
                and intent.state not in ('complete', 'expired')
                and work.owner.lifecycle == 'active'
            ):
                work.execute('checkout_create', intent_id=intent.id)
                current = next(
                    value for value in work.owner.intents if value.id == intent.id
                )
                work.execute(
                    'checkout_seal', intent_id=intent.id, subject_id=current.checkout_id
                )

    def _commands(self, work: Work, observation: Observation) -> None:
        objects = {
            value['id']: value
            for value in (
                *observation.sessions,
                *observation.subscriptions,
                *observation.invoices,
                observation.customer,
            )
        }
        for operation in work.owner.operations:
            if (
                operation.state in ('done', 'recovered')
                or operation.kind
                in ('customer_create', 'customer_seal', 'checkout_create')
                or (
                    operation.kind == 'customer_redact'
                    and work.owner.lifecycle in ('deleting', 'deleted')
                )
            ):
                continue
            purpose = operation_purpose(self.config, work.owner.id, operation)
            current = objects.get(operation.subject_id)
            if current is None:
                raise BillingHold('uncertain_operation')
            resolved = (
                (
                    purpose == 'cancel_period'
                    and (
                        current.get('cancel_at_period_end') is True
                        or current.get('status') == 'canceled'
                    )
                )
                or (purpose == 'cancel_delete' and current.get('status') == 'canceled')
                or (
                    purpose == 'expire'
                    and current.get('status') in ('complete', 'expired')
                )
                or (purpose == 'invoice_stop' and current.get('auto_advance') is False)
                or (purpose == 'invoice_void' and current.get('status') == 'void')
                or (
                    purpose == 'delete_mark'
                    and read_deletion(self.config, current) is not None
                )
                or (
                    purpose == 'customer_redact'
                    and all(
                        current.get(name) in (None, '')
                        for name in (
                            'email',
                            'name',
                            'phone',
                            'address',
                            'shipping',
                            'description',
                        )
                    )
                )
            )
            if resolved:
                work.save(
                    work.owner.model_copy(
                        update={
                            'operations': tuple(
                                value.model_copy(
                                    update={
                                        'state': 'recovered',
                                        'result_id': operation.subject_id,
                                        'reason': operation.reason,
                                    }
                                )
                                if value.id == operation.id
                                else value
                                for value in work.owner.operations
                            )
                        }
                    )
                )
            else:
                work.execute(
                    purpose,
                    intent_id=operation.intent_id,
                    subject_id=operation.subject_id,
                )

    def _events(self, owner_id: str) -> tuple[str, ...]:
        return tuple(
            record.event_id
            for record in self.authority.snapshot()[0]
            if isinstance(record, EventRecord)
            and record.owner_id == owner_id
            and record.state == 'pending'
        )

    def _observe(self, work: Work) -> Observation:
        return observe_owner(
            self.native,
            work.scope,
            work.owner,
            wall_time=int(self.clock().timestamp()),
            verified_at=timestamp(self.clock()),
            allow_funding_hold=work.owner.lifecycle in ('deleting', 'deleted'),
        )

    def _reserve_command(self, work: Work, owner: AccountBillingRecord, purpose: str, subject_id: str, *, reason: str | None = None) -> Operation:
        identifier = new_id()
        request = prepare_request(self.config, self.origin, work.scope, owner, purpose=purpose, operation_id=identifier, intent_id=None, subject_id=subject_id)
        return Operation.model_validate(dict(id=identifier, intent_id=None, kind='cancel' if purpose == 'cancel_period' else 'customer_redact', subject_id=subject_id, request_sha256=request.digest, idempotency_key=operation_key(self.config, owner.id, purpose, identifier), created_at=timestamp(self.clock()), sent_at=None, state='prepared', result_id=None, reason=reason), strict=True)

    def _save_money(self, work: Work, observation: Observation) -> None:
        owner = work.owner
        operations = list(owner.operations)
        for fact in observation.coverage:
            if returned_amount(fact) == fact.captured_amount and not any(operation.kind == 'cancel' and operation.subject_id == fact.subscription_id and operation_purpose(self.config, owner.id, operation) == 'cancel_period' for operation in operations):
                operations.append(self._reserve_command(work, owner, 'cancel_period', fact.subscription_id))
        previous = {fact.invoice_id for fact in owner.coverage}
        late = owner.lifecycle in ('deleting', 'deleted') and any(fact.invoice_id not in previous for fact in observation.coverage)
        if late:
            redactions = [operation for operation in operations if operation.kind == 'customer_redact']
            if redactions:
                operations = [operation.model_copy(update={'reason': 'late_settlement'}) if operation.kind == 'customer_redact' else operation for operation in operations]
            else:
                operations.append(self._reserve_command(work, owner, 'customer_redact', identity(owner.customer_id, 'cus'), reason='late_settlement'))
        lifecycle = owner.lifecycle
        deletion = owner.deletion
        if late and lifecycle == 'deleted' and deletion is not None:
            lifecycle = 'deleting'
            deletion = deletion.model_copy(update={'completed_at': None})
        if lifecycle == 'held' and self.store.user_by_id(owner.id) is not None and deletion is None:
            lifecycle = 'active'
        coverage = observation.coverage
        if observation.funding_hold is not None:
            verified = {fact.invoice_id for fact in coverage}
            coverage = (*coverage, *(fact for fact in owner.coverage if fact.invoice_id not in verified))
        work.save(owner.model_copy(update={'coverage': coverage, 'operations': tuple(operations), 'lifecycle': lifecycle, 'deletion': deletion}))

    def _reconcile(self, work: Work, proofs: Sequence[CustomerProof]) -> Observation | None:
        self._customer(work, proofs)
        if work.owner.customer_id is None and work.owner.lifecycle == 'held' and work.owner.deletion is None and self.store.user_by_id(work.owner.id) is not None:
            # No Customer/coverage exists after complete discovery. A temporary
            # pre-reservation read failure must not become a permanent hold.
            work.save(work.owner.model_copy(update={'lifecycle': 'active'}))
            self._customer(work, proofs)
        if work.owner.customer_id is None:
            return None
        self._sessions(work)
        observation = self._observe(work)
        # Money changes, revocation commands and late-settlement disposition
        # commit together. A crash cannot forget why erasure remained pending.
        self._save_money(work, observation)
        self._commands(work, observation)
        return observation

    def _delete(self, work: Work, observation: Observation | None) -> bool:
        if work.owner.lifecycle not in ('deleting', 'deleted'):
            return False
        if observation is not None:
            customer_id = work.owner.customer_id
            if read_deletion(self.config, observation.customer) is None:
                work.execute('delete_mark', subject_id=customer_id)
            for session in observation.sessions:
                if session.get('status') == 'open':
                    work.execute(
                        'expire', subject_id=identity(session.get('id'), 'cs_test')
                    )
            # Re-observe expiration races before choosing subscriptions to close.
            self._sessions(work)
            observation = self._observe(work)
            for subscription in observation.subscriptions:
                if subscription.get('status') not in ('canceled', 'incomplete_expired'):
                    work.execute(
                        'cancel_delete',
                        subject_id=identity(subscription.get('id'), 'sub'),
                    )
            observation = self._observe(work)
            for invoice in observation.invoices:
                status = invoice.get('status')
                if status in ('draft', 'open'):
                    invoice_id = identity(invoice.get('id'), 'in')
                    work.execute('invoice_stop', subject_id=invoice_id)
                    if status == 'open':
                        work.execute('invoice_void', subject_id=invoice_id)
            observation = self._observe(work)
            if (
                any(session.get('status') == 'open' for session in observation.sessions)
                or any(
                    subscription.get('status') not in ('canceled', 'incomplete_expired')
                    for subscription in observation.subscriptions
                )
                or any(
                    invoice.get('status') == 'open'
                    or (
                        invoice.get('status') == 'draft'
                        and invoice.get('auto_advance') is not False
                    )
                    for invoice in observation.invoices
                )
            ):
                raise BillingHold('uncertain_operation')
            for invoice in observation.invoices:
                if invoice.get('status') in ('draft', 'open', 'void', 'uncollectible'):
                    for payment in self.native.all(
                        'invoice_payments',
                        {'invoice': identity(invoice.get('id'), 'in')},
                    ):
                        funding = mapping(payment.get('payment'))
                        if funding.get('type') != 'payment_intent':
                            raise BillingHold('unsupported_funding')
                        attempt = self.native.request(
                            'GET',
                            'payment_intents/'
                            + identity(funding.get('payment_intent'), 'pi'),
                        )
                        if attempt.get('status') not in (
                            'canceled',
                            'requires_payment_method',
                        ):
                            raise BillingHold(
                                'late_settlement'
                                if attempt.get('status') == 'succeeded'
                                else 'uncertain_operation'
                            )
            self._save_money(work, observation)
            work.execute('customer_redact', subject_id=customer_id)
            customer = self.native.request(
                'GET', 'customers/' + identity(customer_id, 'cus')
            )
            if read_deletion(self.config, customer) is None or any(
                customer.get(name) not in (None, '')
                for name in (
                    'email',
                    'name',
                    'phone',
                    'address',
                    'shipping',
                    'description',
                )
            ):
                raise BillingHold('uncertain_operation')
        elif any(
            operation.state not in ('done', 'recovered')
            for operation in work.owner.operations
        ):
            raise BillingHold('uncertain_operation')
        if observation is not None and observation.funding_hold is not None:
            raise BillingHold(observation.funding_hold)
        if any(operation.reason == 'late_settlement' for operation in work.owner.operations):
            raise BillingHold('late_settlement')
        deletion = work.owner.deletion
        if deletion is None:
            raise BillingHold('deleted_owner')
        final = work.owner.model_copy(
            update={
                'lifecycle': 'deleted',
                'deletion': deletion.model_copy(
                    update={
                        'completed_at': deletion.completed_at or timestamp(self.clock())
                    }
                ),
            }
        )
        self.authority.apply(
            work.lease,
            final,
            applied_events=self._events(work.owner.id),
            remove_user=True,
        )
        return True

    def recover(self) -> None:
        scope, owners, _ = self._snapshot()
        started_at = int(self.clock().timestamp())
        proofs = discover_customers(self.native, scope)
        existing = {owner.id for owner in owners}
        for proof in proofs:
            if proof.owner_id not in existing:
                self._adopt(scope, proof)
        _, owners, _ = self._snapshot()
        for owner in owners:
            self.reconcile(owner.id, proofs=proofs)
        self.authority.finish_recovery(self.epoch, started_at=started_at)

    def reconcile(
        self, owner_id: str, *, proofs: Sequence[CustomerProof] | None = None
    ) -> Observation | None:
        work = self._claim(owner_id)
        try:
            if proofs is None:
                proofs = discover_customers(self.native, work.scope)
            observation = self._reconcile(work, proofs)
            if not self._delete(work, observation):
                self.authority.apply(
                    work.lease, work.owner, applied_events=self._events(owner_id)
                )
            return observation
        except BillingHold as exc:
            self.authority.defer(work.lease, exc.reason)
            raise

    def checkout(self, owner_id: str, plan: str, period: str) -> dict[str, object]:
        _, _, ready = self._snapshot()
        if not ready:
            raise BillingHold('unverified')
        self.authority.ensure_owner(owner_id, clock_id=self.config.purchase_clock)
        work = self._claim(owner_id)
        try:
            observation = self._reconcile(
                work, discover_customers(self.native, work.scope)
            )
            if work.owner.lifecycle != 'active':
                raise BillingHold('deleted_owner')
            unresolved = next(
                (
                    intent
                    for intent in work.owner.intents
                    if intent.state not in ('complete', 'expired')
                ),
                None,
            )
            if unresolved is not None:
                offer = next(
                    offer
                    for offer in work.scope.offers
                    if offer.id == unresolved.offer_id
                )
                if (offer.plan, offer.period) != (plan, period):
                    raise PurchaseConflict(
                        'An existing purchase occupies this account.'
                    )
                return self._checkout_reply(work, unresolved.id)
            if observation is not None:
                access = effective_access(
                    work.scope, work.owner, now=observation.now, ready=True
                )
                if (
                    access.status == 'held'
                    or access.tier != 'free'
                    or any(
                        subscription.get('status')
                        not in ('canceled', 'incomplete_expired')
                        for subscription in observation.subscriptions
                    )
                    or any(
                        invoice.get('status') in ('draft', 'open')
                        for invoice in observation.invoices
                    )
                ):
                    raise PurchaseConflict(
                        'Existing paid time or collection must finish before another purchase.'
                    )
            try:
                verify_sandbox_catalogue(self.config.catalogue, self.native.client)
            except BillingError:
                raise BillingHold('native_unavailable') from None
            offer = next(
                (
                    offer
                    for offer in work.scope.offers
                    if offer.plan == plan
                    and offer.period == period
                    and offer.price_id in self.config.catalogue.price_ids
                ),
                None,
            )
            if offer is None:
                raise BillingHold('unsupported_funding')
            now = self.clock()
            intent = Intent(
                id=new_id(),
                offer_id=offer.id,
                created_at=timestamp(now),
                expires_at=int(now.timestamp()) + 3600,
                state='reserved',
                checkout_id=None,
                subscription_id=None,
            )
            work.save(
                work.owner.model_copy(update={'intents': (*work.owner.intents, intent)})
            )
            if work.owner.customer_id is None:
                work.execute('customer_create')
                work.execute('customer_seal', subject_id=work.owner.customer_id)
            work.execute('checkout_create', intent_id=intent.id)
            current = next(
                value for value in work.owner.intents if value.id == intent.id
            )
            work.execute(
                'checkout_seal', intent_id=intent.id, subject_id=current.checkout_id
            )
            return self._checkout_reply(work, intent.id)
        except BillingHold as exc:
            self.authority.defer(work.lease, exc.reason)
            raise
        finally:
            # A successful reply or a harmless purchase conflict releases its
            # lease. Deferred or concurrently fenced work has already lost it.
            records, epoch, _ = self.authority.snapshot()
            current = next(
                record
                for record in records
                if isinstance(record, AccountBillingRecord) and record.id == owner_id
            )
            if epoch == work.lease.epoch and (current.revision, current.lifecycle) == (
                work.lease.revision,
                work.lease.lifecycle,
            ):
                self.authority.release(work.lease)

    def _checkout_reply(self, work: Work, intent_id: str) -> dict[str, object]:
        intent = next(value for value in work.owner.intents if value.id == intent_id)
        if intent.checkout_id is None:
            raise BillingHold('uncertain_operation')
        session = self.native.request('GET', 'checkout/sessions/' + intent.checkout_id)
        sealed_checkout(self.config, work.owner, session)
        reply: dict[str, object] = {
            'intent_id': intent.id,
            'status': session.get('status'),
        }
        if session.get('status') == 'open':
            url = session.get('url')
            if (
                not isinstance(url, str)
                or urlsplit(url).scheme != 'https'
                or urlsplit(url).hostname != 'checkout.stripe.com'
            ):
                raise BillingHold('uncertain_operation')
            reply['checkout_url'] = url
        return reply

    def cancel(self, owner_id: str) -> None:
        self.authority.ensure_owner(owner_id, clock_id=self.config.purchase_clock)
        self.reconcile(owner_id)
        work = self._claim(owner_id)
        if work.owner.customer_id is None:
            self.authority.release(work.lease)
            return
        try:
            observation = self._observe(work)
            for subscription in observation.subscriptions:
                if (
                    subscription.get('status') not in ('canceled', 'incomplete_expired')
                    and subscription.get('cancel_at_period_end') is not True
                ):
                    work.execute(
                        'cancel_period',
                        subject_id=identity(subscription.get('id'), 'sub'),
                    )
            self.authority.apply(work.lease, work.owner)
        except BillingHold as exc:
            self.authority.defer(work.lease, exc.reason)
            raise

    def delete(self, owner_id: str) -> bool:
        self.authority.ensure_owner(owner_id, clock_id=self.config.purchase_clock)
        self.authority.request_deletion(owner_id)
        self.reconcile(owner_id)
        return self.store.user_by_id(owner_id) is None

    async def run(self) -> None:
        delay = self.config.poll_seconds
        try:
            while True:
                try:
                    _, owners, ready = self._snapshot()
                    if not ready:
                        await asyncio.to_thread(self.recover)
                    else:
                        records = self.authority.snapshot()[0]
                        now = int(self.clock().timestamp())
                        for owner in owners:
                            pending = [
                                record
                                for record in records
                                if isinstance(record, EventRecord)
                                and record.owner_id == owner.id
                                and record.state == 'pending'
                            ]
                            if pending and all(
                                record.next_attempt_at is not None
                                and record.next_attempt_at > now
                                for record in pending
                            ):
                                continue
                            await asyncio.to_thread(self.reconcile, owner.id)
                    delay = self.config.poll_seconds
                except asyncio.CancelledError:
                    raise
                except BillingHold as exc:
                    self.authority.hold_runtime(self.epoch, exc.reason)
                    logger.warning('Billing reconciliation held: %s', exc.reason)
                    delay = min(300, max(5, delay * 2))
                except BaseException:
                    self.authority.hold_runtime(self.epoch, 'processing_failed')
                    raise
                await asyncio.sleep(delay)
        finally:
            self.authority.stop(self.epoch)
