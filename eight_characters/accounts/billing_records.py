"""Strict, separately encrypted billing authority; these records grant no access.

Legacy user plans retain their meaning. Native fulfillment belongs to the writer;
the reader validates bytes, historical terms and ownership before recovery.
"""

import hashlib
import re
from collections.abc import Sequence
from typing import Annotated, Final, Literal, Self, TypeAlias, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from eight_characters.accounts.records import (
    RecordError,
    User,
    canonical_json,
    parse_timestamp,
)

Identifier = Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{32}$')]
Digest = Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{64}$')]
NativeId = Annotated[str, StringConstraints(pattern=r'^[A-Za-z][A-Za-z0-9_]{1,200}$')]
CustomerId = Annotated[str, StringConstraints(pattern=r'^cus_[A-Za-z0-9]+$')]
ClockId = Annotated[str, StringConstraints(pattern=r'^clock_[A-Za-z0-9]+$')]
SubscriptionId = Annotated[str, StringConstraints(pattern=r'^sub_[A-Za-z0-9]+$')]
CheckoutId = Annotated[str, StringConstraints(pattern=r'^cs_test_[A-Za-z0-9]+$')]
Natural = Annotated[int, Field(ge=0, lt=2**63 - 1)]
Positive = Annotated[int, Field(gt=0, lt=2**63 - 1)]
_SECRET: Final = re.compile(r'(?:sk|rk|pk)_(?:test|live)_|whsec_')
REASONS: Final = (
    'unverified',
    'native_unavailable',
    'permission_missing',
    'unknown_owner',
    'unsupported_event',
    'unsupported_version',
    'ownership_conflict',
    'uncertain_operation',
    'scope_mismatch',
    'clock_unavailable',
    'unsupported_funding',
    'unsupported_overlap',
    'deleted_owner',
    'legacy_identity_ambiguous',
    'processing_failed',
    'late_settlement',
)


def _secrets(value: object) -> None:
    if isinstance(value, str) and (_SECRET.search(value) or '://' in value):
        raise ValueError('Billing records cannot contain credentials or URLs.')
    if isinstance(value, dict):
        for nested in cast(dict[object, object], value).values():
            _secrets(nested)
    elif isinstance(value, (list, tuple)):
        for nested in cast(Sequence[object], value):
            _secrets(nested)


def _unique(values: Sequence[object]) -> None:
    if len(set(values)) != len(values):
        raise ValueError('A billing record repeats an identity.')


class StrictRecord(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
        strict=True,
        frozen=True,
        revalidate_instances='always',
        populate_by_name=True,
    )

    @model_validator(mode='after')
    def no_secrets(self) -> Self:
        # Keep JSON validation in JSON mode until arrays have become typed tuples.
        _secrets(self.model_dump(mode='python', by_alias=True))
        return self


class OfferSnapshot(StrictRecord):
    id: Digest
    plan: Literal['basic', 'plus', 'pro']
    period: Literal['monthly', 'yearly']
    price_id: Annotated[str, StringConstraints(pattern=r'^price_[A-Za-z0-9]+$')]
    product_id: Annotated[str, StringConstraints(pattern=r'^[A-Za-z0-9_-]{1,128}$')]
    currency: Literal['usd']
    amount: Positive
    interval: Literal['month', 'year']
    interval_count: Literal[1]
    tax_behavior: Literal['exclusive']

    @field_validator('interval_count', mode='before')
    @classmethod
    def integer_count(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError('An interval count must be an integer.')
        return value

    @model_validator(mode='after')
    def terms(self) -> Self:
        if self.interval != ('month' if self.period == 'monthly' else 'year'):
            raise ValueError('Offer period and interval disagree.')
        terms = self.model_dump(mode='json', exclude={'id'})
        if hashlib.sha256(canonical_json(terms)).hexdigest() != self.id:
            raise ValueError('An offer identifier does not match its frozen terms.')
        return self


class Binding(StrictRecord):
    operation_id: Identifier
    object_id: CustomerId
    state: Literal['unsealed', 'sealed']
    mac: Digest


class Intent(StrictRecord):
    id: Identifier
    offer_id: Digest
    created_at: str
    expires_at: Positive
    state: Literal[
        'reserved',
        'customer_pending',
        'checkout_pending',
        'open',
        'complete',
        'expired',
        'held',
    ]
    checkout_id: CheckoutId | None
    subscription_id: SubscriptionId | None

    @field_validator('created_at')
    @classmethod
    def real_timestamp(cls, value: str) -> str:
        parse_timestamp(value)
        return value

    @model_validator(mode='after')
    def native_state(self) -> Self:
        if self.state in ('open', 'complete', 'expired') and self.checkout_id is None:
            raise ValueError('A native checkout state needs its Session identity.')
        if self.subscription_id is not None and self.checkout_id is None:
            raise ValueError('A purchase subscription needs its Session identity.')
        return self


class Operation(StrictRecord):
    id: Identifier
    intent_id: Identifier | None
    kind: Literal[
        'customer_create',
        'customer_seal',
        'checkout_create',
        'cancel',
        'expire',
        'void_invoice',
        'delete_mark',
        'customer_redact',
    ]
    subject_id: NativeId | None
    request_sha256: Digest | None
    idempotency_key: Annotated[
        str, StringConstraints(pattern=r'^[A-Za-z0-9_-]{1,255}$')
    ]
    created_at: str
    sent_at: str | None
    state: Literal['prepared', 'sent', 'done', 'held', 'recovered']
    result_id: NativeId | None
    reason: str | None

    @field_validator('created_at', 'sent_at')
    @classmethod
    def real_timestamp(cls, value: str | None) -> str | None:
        if value is not None:
            parse_timestamp(value)
        return value

    @field_validator('reason')
    @classmethod
    def known_reason(cls, value: str | None) -> str | None:
        if value is not None and value not in REASONS:
            raise ValueError('Unknown billing outcome reason.')
        return value

    @model_validator(mode='after')
    def request_state(self) -> Self:
        if self.state != 'recovered' and self.request_sha256 is None:
            raise ValueError('An original operation needs its request fingerprint.')
        if self.state == 'sent' and self.sent_at is None:
            raise ValueError('A sent operation needs its send time.')
        if self.state in ('done', 'recovered') and self.result_id is None:
            raise ValueError('A completed operation needs a native result.')
        if self.sent_at is not None and self.sent_at < self.created_at:
            raise ValueError('An operation cannot be sent before reservation.')
        return self


class RefundFact(StrictRecord):
    id: Annotated[str, StringConstraints(pattern=r'^re_[A-Za-z0-9]+$')]
    amount: Positive
    status: Literal['pending', 'requires_action', 'succeeded', 'failed', 'canceled']


class DisputeFact(StrictRecord):
    id: Annotated[str, StringConstraints(pattern=r'^du_[A-Za-z0-9]+$')]
    status: Literal[
        'warning_needs_response',
        'warning_under_review',
        'warning_closed',
        'needs_response',
        'under_review',
        'won',
        'lost',
    ]


class Coverage(StrictRecord):
    invoice_id: Annotated[str, StringConstraints(pattern=r'^in_[A-Za-z0-9]+$')]
    line_id: Annotated[str, StringConstraints(pattern=r'^il_[A-Za-z0-9_]+$')]
    invoice_payment_id: Annotated[
        str, StringConstraints(pattern=r'^inpay_[A-Za-z0-9]+$')
    ]
    subscription_id: SubscriptionId
    subscription_item_id: Annotated[
        str, StringConstraints(pattern=r'^si_[A-Za-z0-9]+$')
    ]
    price_id: Annotated[str, StringConstraints(pattern=r'^price_[A-Za-z0-9]+$')]
    offer_id: Digest
    payment_intent_id: Annotated[str, StringConstraints(pattern=r'^pi_[A-Za-z0-9]+$')]
    charge_id: Annotated[str, StringConstraints(pattern=r'^ch_[A-Za-z0-9]+$')]
    currency: Literal['usd']
    period_start: Natural
    period_end: Positive
    paid_at: Natural
    allocated_amount: Positive
    captured_amount: Positive
    base_amount: Positive
    tax_amount: Natural
    refunds: tuple[RefundFact, ...]
    disputes: tuple[DisputeFact, ...]
    verified_at: str

    @field_validator('verified_at')
    @classmethod
    def real_timestamp(cls, value: str) -> str:
        parse_timestamp(value)
        return value

    @model_validator(mode='after')
    def amounts_and_period(self) -> Self:
        if self.period_end <= self.period_start:
            raise ValueError('A coverage interval must have positive duration.')
        if self.allocated_amount != self.captured_amount or (
            self.base_amount + self.tax_amount != self.captured_amount
        ):
            raise ValueError('Allocated, captured and invoice amounts disagree.')
        _unique([item.id for item in self.refunds])
        _unique([item.id for item in self.disputes])
        if (
            sum(r.amount for r in self.refunds if r.status == 'succeeded')
            > self.captured_amount
        ):
            raise ValueError('Returned money exceeds the capture.')
        return self


class Deletion(StrictRecord):
    requested_at: str
    completed_at: str | None
    nonce: Identifier
    native_object_id: CustomerId
    native_marker: Digest
    retain_until: str | None

    @field_validator('requested_at', 'completed_at', 'retain_until')
    @classmethod
    def real_timestamp(cls, value: str | None) -> str | None:
        if value is not None:
            parse_timestamp(value)
        return value

    @model_validator(mode='after')
    def ordered(self) -> Self:
        if self.completed_at is not None and self.completed_at < self.requested_at:
            raise ValueError('Deletion cannot finish before its request.')
        if self.retain_until is not None and self.retain_until < self.requested_at:
            raise ValueError('Retention cannot end before deletion.')
        return self


class BillingRecord(StrictRecord):
    kind: Literal['billing'] = 'billing'
    schema_version: Annotated[int, Field(ge=1, le=1)] = Field(default=1, alias='schema')
    id: Identifier
    scope_id: Identifier
    revision: Natural
    created_at: str
    updated_at: str

    @field_validator('created_at', 'updated_at')
    @classmethod
    def real_timestamp(cls, value: str) -> str:
        parse_timestamp(value)
        return value

    @model_validator(mode='after')
    def ordered(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError('A billing record cannot change before creation.')
        return self


class ScopeRecord(BillingRecord):
    record_type: Literal['scope'] = 'scope'
    account_id: Annotated[str, StringConstraints(pattern=r'^acct_[A-Za-z0-9]+$')]
    livemode: Literal[False]
    api_version: Annotated[
        str, StringConstraints(pattern=r'^\d{4}-\d{2}-\d{2}\.[a-z]+$')
    ]
    binding_key_id: Digest
    clock_ids: tuple[ClockId, ...]
    offers: tuple[OfferSnapshot, ...]
    reconciled_started_at: Natural | None

    @field_validator('livemode', mode='before')
    @classmethod
    def boolean_mode(cls, value: object) -> object:
        if type(value) is not bool:
            raise ValueError('Native mode must be a boolean.')
        return value

    @model_validator(mode='after')
    def identities(self) -> Self:
        if self.id != self.scope_id:
            raise ValueError('A billing scope must identify itself.')
        _unique(self.clock_ids)
        _unique([offer.id for offer in self.offers])
        _unique([offer.price_id for offer in self.offers])
        return self


class AccountBillingRecord(BillingRecord):
    record_type: Literal['account'] = 'account'
    owner_id: Identifier
    customer_id: CustomerId | None
    test_clock_id: ClockId | None
    lifecycle: Literal['active', 'held', 'deleting', 'deleted']
    binding: Binding | None
    intents: tuple[Intent, ...]
    operations: tuple[Operation, ...]
    coverage: tuple[Coverage, ...]
    deletion: Deletion | None

    @model_validator(mode='after')
    def ownership(self) -> Self:
        if self.id != self.owner_id:
            raise ValueError('A financial record must name its immutable owner.')
        if self.binding is not None and self.binding.object_id != self.customer_id:
            raise ValueError('Native binding and customer identity disagree.')
        if self.coverage and (self.binding is None or self.binding.state != 'sealed'):
            raise ValueError('Payment evidence needs a sealed customer binding.')
        if self.customer_id is None and any(i.checkout_id for i in self.intents):
            raise ValueError('A Checkout Session needs its customer binding.')
        _unique([i.id for i in self.intents])
        _unique([o.id for o in self.operations])
        intent_ids = {i.id for i in self.intents}
        if any(
            o.intent_id is not None and o.intent_id not in intent_ids
            for o in self.operations
        ):
            raise ValueError('An operation refers to an unknown purchase intent.')
        if sum(i.state not in ('complete', 'expired') for i in self.intents) > 1:
            raise ValueError('An owner has more than one unresolved purchase.')
        for key in (
            'invoice_id',
            'invoice_payment_id',
            'payment_intent_id',
            'charge_id',
        ):
            _unique([getattr(c, key) for c in self.coverage])
        if self.lifecycle in ('deleting', 'deleted') and self.deletion is None:
            raise ValueError('Deleting an owner needs its durable deletion decision.')
        if self.deletion is not None:
            if self.deletion.native_object_id != self.customer_id:
                raise ValueError('Deletion marker names another customer.')
            if (self.lifecycle == 'deleted') != (
                self.deletion.completed_at is not None
            ):
                raise ValueError('Deletion lifecycle and completion disagree.')
        return self


class EventRecord(BillingRecord):
    record_type: Literal['event'] = 'event'
    event_id: Annotated[str, StringConstraints(pattern=r'^evt_[A-Za-z0-9]+$')]
    event_type: Annotated[str, StringConstraints(pattern=r'^[a-z][a-z0-9_.]{1,100}$')]
    object_id: NativeId
    owner_id: Identifier | None
    state: Literal['pending', 'applied', 'quarantined']
    attempts: Natural
    next_attempt_at: Natural | None
    body_sha256: Digest
    reason: str | None

    @field_validator('reason')
    @classmethod
    def known_reason(cls, value: str | None) -> str | None:
        if value is not None and value not in REASONS:
            raise ValueError('Unknown delivery outcome reason.')
        return value

    @model_validator(mode='after')
    def quarantine(self) -> Self:
        if self.state == 'quarantined' and self.reason is None:
            raise ValueError('A quarantined delivery needs its visible reason.')
        return self


BillingDocument: TypeAlias = ScopeRecord | AccountBillingRecord | EventRecord
_ADAPTER: Final = TypeAdapter(
    Annotated[BillingDocument, Field(discriminator='record_type')]
)


def billing_path(identifier: str) -> str:
    if re.fullmatch(r'[0-9a-f]{32}', identifier) is None:
        raise RecordError('A billing record id must be 32 lowercase hex digits.')
    return f'billing/{identifier[:2]}/{identifier}/billing.json'


def encode_billing(record: BillingDocument) -> bytes:
    try:
        validated = _ADAPTER.validate_python(record, strict=True)
    except (ValidationError, ValueError, TypeError):
        raise RecordError(
            'A billing instance does not match the strict schema 1.'
        ) from None
    return canonical_json(validated.model_dump(mode='json', by_alias=True))


def decode_billing(data: bytes) -> BillingDocument:
    try:
        record = _ADAPTER.validate_json(data, strict=True)
    except ValidationError as exc:
        codes = sorted(
            {
                str(item['type'])
                for item in exc.errors(include_input=False, include_context=False)
            }
        )
        raise RecordError(
            'Billing record validation failed: ' + ', '.join(codes) + '.'
        ) from None
    except (ValueError, TypeError):
        raise RecordError(
            'A billing record does not match the strict schema 1.'
        ) from None
    if encode_billing(record) != data:
        raise RecordError('A billing record is not in canonical form.')
    return record


def resource_claims(record: AccountBillingRecord) -> dict[str, str]:
    """Native identifiers are exclusively owned, including deleted owners."""
    found: dict[str, str] = {}

    def keep(native_id: str | None, kind: str) -> None:
        if native_id is not None:
            if native_id in found and found[native_id] != kind:
                raise RecordError('A native resource has inconsistent kinds.')
            found[native_id] = kind

    keep(record.customer_id, 'customer')
    for intent in record.intents:
        keep(intent.checkout_id, 'checkout')
        keep(intent.subscription_id, 'subscription')
    for fact in record.coverage:
        for name, kind in (
            ('invoice_id', 'invoice'),
            ('invoice_payment_id', 'invoice_payment'),
            ('subscription_id', 'subscription'),
            ('payment_intent_id', 'payment_intent'),
            ('charge_id', 'charge'),
        ):
            keep(getattr(fact, name), kind)
        for refund in fact.refunds:
            keep(refund.id, 'refund')
        for dispute in fact.disputes:
            keep(dispute.id, 'dispute')
    return found


def validate_billing_graph(
    records: Sequence[BillingDocument], users: Sequence[User]
) -> None:
    if not records:
        return
    by_id = {r.id: r for r in records}
    scopes = [r for r in records if isinstance(r, ScopeRecord)]
    if len(by_id) != len(records) or len(scopes) != 1:
        raise RecordError(
            'Billing records need unique identities and exactly one scope.'
        )
    scope = scopes[0]
    if any(r.scope_id != scope.id for r in records):
        raise RecordError('Billing records mix different native scopes.')
    user_ids = {u.id for u in users}
    if scope.id in user_ids:
        raise RecordError('A scope collides with an account identity.')
    offers = {offer.id: offer for offer in scope.offers}
    owners: set[str] = set()
    claims: dict[str, str] = {}
    events: set[str] = set()
    for record in records:
        if isinstance(record, AccountBillingRecord):
            owners.add(record.owner_id)
            if (record.owner_id in user_ids) == (record.lifecycle == 'deleted'):
                raise RecordError('A financial owner and its personal record disagree.')
            if (
                record.test_clock_id is not None
                and record.test_clock_id not in scope.clock_ids
            ):
                raise RecordError('A financial owner names an unretained clock.')
            for intent in record.intents:
                if intent.offer_id not in offers:
                    raise RecordError('A purchase refers to unknown historical terms.')
            for fact in record.coverage:
                offer = offers.get(fact.offer_id)
                if offer is None or (offer.price_id, offer.amount) != (
                    fact.price_id,
                    fact.base_amount,
                ):
                    raise RecordError(
                        'A receipt differs from its approved historical terms.'
                    )
            for native_id in resource_claims(record):
                if native_id in claims and claims[native_id] != record.owner_id:
                    raise RecordError(
                        'A native financial resource belongs to two owners.'
                    )
                claims[native_id] = record.owner_id
        elif isinstance(record, EventRecord):
            if record.event_id in events:
                raise RecordError('A native event is repeated.')
            events.add(record.event_id)
    for record in records:
        if (
            isinstance(record, EventRecord)
            and record.owner_id is not None
            and record.owner_id not in owners
        ):
            raise RecordError('A delivery names an unknown financial owner.')
