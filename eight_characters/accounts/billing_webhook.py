"""Raw-body signature verification before parsing provider delivery JSON."""

import hashlib
import hmac
import json
import re
from dataclasses import dataclass

from eight_characters.accounts.billing_access import BillingConfig, BillingHold
from eight_characters.accounts.billing_native import identity, integer, mapping

MAX_BODY = 1024 * 1024
EVENT_TYPES = frozenset(
    (
        'checkout.session.completed',
        'checkout.session.expired',
        'checkout.session.async_payment_succeeded',
        'checkout.session.async_payment_failed',
        'invoice.paid',
        'invoice.payment_failed',
        'invoice.voided',
        'customer.subscription.updated',
        'customer.subscription.deleted',
        'charge.refunded',
        'refund.updated',
        'refund.failed',
        'charge.dispute.created',
        'charge.dispute.updated',
        'charge.dispute.closed',
    )
)


class InvalidDelivery(Exception):
    def __init__(self, status: int = 400) -> None:
        self.status = status
        super().__init__('Invalid Stripe delivery.')


@dataclass(frozen=True)
class Delivery:
    event_id: str
    event_type: str
    object_id: str
    related_id: str | None
    body_sha256: str
    supported: bool


def verify_delivery(
    raw: bytes, signature: str | None, config: BillingConfig, *, wall_time: int
) -> Delivery:
    if len(raw) > MAX_BODY:
        raise InvalidDelivery(413)
    if signature is None or len(signature) > 4096:
        raise InvalidDelivery()
    parts = [part.strip().split('=', 1) for part in signature.split(',')]
    if any(len(part) != 2 for part in parts):
        raise InvalidDelivery()
    times = [part[1] for part in parts if part[0] == 't']
    macs = [part[1] for part in parts if part[0] == 'v1']
    if (
        len(times) != 1
        or re.fullmatch(r'[0-9]{1,12}', times[0]) is None
        or abs(wall_time - int(times[0])) > 300
        or not macs
        or any(re.fullmatch(r'[0-9a-f]{64}', mac) is None for mac in macs)
    ):
        raise InvalidDelivery()
    message = times[0].encode() + b'.' + raw
    verified = False
    for secret in config.webhook_secrets:
        expected = hmac.new(secret, message, hashlib.sha256).hexdigest()
        for mac in macs:
            verified |= hmac.compare_digest(expected, mac)
    if not verified:
        raise InvalidDelivery()
    try:
        value: object = json.loads(raw)
        event = mapping(value)
        if (
            event.get('object') != 'event'
            or event.get('api_version') != config.payload_version
            or event.get('livemode') is not False
            or event.get('account') not in (None, config.catalogue.account_id)
            or event.get('context') is not None
        ):
            raise InvalidDelivery()
        integer(event.get('created'))
        event_type = event.get('type')
        if (
            not isinstance(event_type, str)
            or re.fullmatch(r'[a-z][a-z0-9_.]{1,100}', event_type) is None
        ):
            raise InvalidDelivery()
        native = mapping(mapping(event.get('data')).get('object'))
        object_id = native.get('id')
        if (
            not isinstance(object_id, str)
            or re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{1,200}', object_id) is None
        ):
            raise InvalidDelivery()
        related = next(
            (
                native.get(name)
                for name in ('customer', 'charge', 'payment_intent')
                if isinstance(native.get(name), str)
            ),
            None,
        )
        if related is not None and (
            not isinstance(related, str)
            or re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{1,200}', related) is None
        ):
            raise InvalidDelivery()
        return Delivery(
            identity(event.get('id'), 'evt'),
            event_type,
            object_id,
            related,
            hashlib.sha256(raw).hexdigest(),
            event_type in EVENT_TYPES,
        )
    except (ValueError, TypeError, BillingHold):
        raise InvalidDelivery() from None
