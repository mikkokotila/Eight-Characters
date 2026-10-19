"""Durable billing records, transactional delivery and fenced native work.

No provider call belongs inside these transactions. Applying a fetched result
requires the same recovery epoch, lease, generation, owner revision and lifecycle.
"""

import hashlib
import secrets
import sqlite3
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from eight_characters.accounts.billing import OFFERS
from eight_characters.accounts.billing_access import (
    BillingConfig,
    BillingHold,
    check_scope,
)
from eight_characters.accounts.billing_records import (
    AccountBillingRecord,
    BillingDocument,
    EventRecord,
    OfferSnapshot,
    ScopeRecord,
    billing_path,
    decode_billing,
    encode_billing,
    resource_claims,
    validate_billing_graph,
)
from eight_characters.accounts.billing_webhook import Delivery
from eight_characters.accounts.records import (
    canonical_json,
    new_id,
    parse_timestamp,
    timestamp,
)
from eight_characters.accounts.store import (
    AccountStore,
    account_connection,
    billing_records_in,
    check_database_version,
    log_record_change,
    user_in,
    users_in,
)


@dataclass(frozen=True)
class Lease:
    owner_id: str
    epoch: str
    token: str
    generation: int
    revision: int
    lifecycle: str


def _next_time(previous: str, now: datetime) -> str:
    return max(
        timestamp(now), timestamp(parse_timestamp(previous) + timedelta(seconds=1))
    )


def _offers(config: BillingConfig) -> tuple[OfferSnapshot, ...]:
    found: list[OfferSnapshot] = []
    for index, offer in enumerate(OFFERS):
        terms = dict(
            plan=offer.plan,
            period=offer.period,
            price_id=config.catalogue.price_ids[index],
            product_id=config.catalogue.product_ids[index // 2],
            currency='usd',
            amount=offer.amount,
            interval=offer.interval,
            interval_count=1,
            tax_behavior='exclusive',
        )
        found.append(
            OfferSnapshot.model_validate(
                {'id': hashlib.sha256(canonical_json(terms)).hexdigest(), **terms},
                strict=True,
            )
        )
    return tuple(found)


class Authority:
    def __init__(
        self,
        store: AccountStore,
        config: BillingConfig,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.config = config
        self.clock = clock or (lambda: datetime.now(UTC))

    @contextmanager
    def write(self) -> Generator[sqlite3.Connection, None, None]:
        with account_connection(self.store.path) as connection:
            connection.execute('BEGIN IMMEDIATE')
            try:
                if check_database_version(connection) != 5:
                    raise BillingHold('unverified')
                if (
                    connection.execute(
                        "SELECT 1 FROM users WHERE plan != 'free' LIMIT 1"
                    ).fetchone()
                    is not None
                ):
                    raise BillingHold('legacy_identity_ambiguous')
                yield connection
            except BaseException:
                connection.execute('ROLLBACK')
                raise
            connection.execute('COMMIT')

    def snapshot(self) -> tuple[tuple[BillingDocument, ...], str, bool]:
        with self.store.read_transaction() as connection:
            records = billing_records_in(connection)
            self.scope(records)
            runtime = connection.execute(
                'SELECT epoch,ready FROM billing_runtime WHERE id=1'
            ).fetchone()
            if runtime is None:
                raise BillingHold('unverified')
            return records, runtime[0], runtime[1] == 1

    def scope(self, records: Sequence[BillingDocument]) -> ScopeRecord:
        scope = next(
            (record for record in records if isinstance(record, ScopeRecord)), None
        )
        if scope is None:
            raise BillingHold('unverified')
        check_scope(self.config, scope)
        return scope

    def _put(
        self,
        connection: sqlite3.Connection,
        records: Sequence[BillingDocument],
        *,
        removed_user: str | None = None,
    ) -> None:
        previous = {record.id: record for record in billing_records_in(connection)}
        changed = {
            record.id: decode_billing(encode_billing(record)) for record in records
        }
        merged = {**previous, **changed}
        users = [user for user in users_in(connection) if user.id != removed_user]
        validate_billing_graph(tuple(merged.values()), users)
        for record in changed.values():
            old = previous.get(record.id)
            if old == record:
                continue
            if old is not None and (
                record.revision != old.revision + 1
                or record.created_at != old.created_at
                or record.updated_at <= old.updated_at
            ):
                raise BillingHold('processing_failed')
            owner_id = (
                record.owner_id
                if isinstance(record, (AccountBillingRecord, EventRecord))
                else None
            )
            connection.execute(
                'INSERT INTO billing_records(id,scope_id,record_type,owner_id,revision,record) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,record=excluded.record,owner_id=excluded.owner_id',
                (
                    record.id,
                    record.scope_id,
                    record.record_type,
                    owner_id,
                    record.revision,
                    encode_billing(record),
                ),
            )
            if isinstance(record, AccountBillingRecord):
                connection.execute(
                    'DELETE FROM billing_resources WHERE owner_id=?', (record.owner_id,)
                )
                connection.executemany(
                    'INSERT INTO billing_resources(scope_id,native_id,native_kind,owner_id) VALUES(?,?,?,?)',
                    [
                        (record.scope_id, native_id, kind, record.owner_id)
                        for native_id, kind in resource_claims(record).items()
                    ],
                )
            elif isinstance(record, EventRecord):
                connection.execute(
                    'INSERT INTO billing_jobs(event_id,record_id) VALUES(?,?) ON CONFLICT(event_id) DO NOTHING',
                    (record.event_id, record.id),
                )
            log_record_change(connection, 'billing', record.id, billing_path(record.id))

    def begin_recovery(self) -> str:
        """Close the global gate durably before the first native HTTP request."""
        with self.write() as connection:
            records = billing_records_in(connection)
            now = timestamp(self.clock())
            if records:
                scope = self.scope(records)
                offers = {offer.id: offer for offer in scope.offers}
                offers.update({offer.id: offer for offer in _offers(self.config)})
                changed = scope.model_copy(
                    update={
                        'revision': scope.revision + 1,
                        'updated_at': _next_time(scope.updated_at, self.clock()),
                        'offers': tuple(offers.values()),
                        'clock_ids': tuple(
                            sorted(set(scope.clock_ids) | set(self.config.clock_ids))
                        ),
                    }
                )
                self._put(connection, (changed,))
            else:
                scope = ScopeRecord(
                    id=self.config.namespace,
                    scope_id=self.config.namespace,
                    revision=0,
                    created_at=now,
                    updated_at=now,
                    account_id=self.config.catalogue.account_id,
                    livemode=False,
                    api_version=self.config.catalogue.api_version,
                    binding_key_id=self.config.binding_key_id,
                    clock_ids=self.config.clock_ids,
                    offers=_offers(self.config),
                    reconciled_started_at=None,
                )
                self._put(connection, (scope,))
            epoch = secrets.token_hex(32)
            connection.execute(
                "INSERT INTO billing_runtime(id,epoch,ready,reason,checked_at) VALUES(1,?,0,'unverified',NULL) ON CONFLICT(id) DO UPDATE SET epoch=excluded.epoch,ready=0,reason='unverified',checked_at=NULL",
                (epoch,),
            )
            connection.execute('DELETE FROM billing_leases')
            return epoch

    def ensure_owner(
        self, owner_id: str, *, clock_id: str | None = None
    ) -> AccountBillingRecord:
        with self.write() as connection:
            records = billing_records_in(connection)
            scope = self.scope(records)
            found = next(
                (
                    record
                    for record in records
                    if isinstance(record, AccountBillingRecord)
                    and record.id == owner_id
                ),
                None,
            )
            if found is not None:
                return found
            user = user_in(connection, 'id', owner_id)
            if user is None or user.plan != 'free':
                raise BillingHold('unknown_owner')
            if clock_id is not None and clock_id not in scope.clock_ids:
                raise BillingHold('clock_unavailable')
            now = timestamp(self.clock())
            owner = AccountBillingRecord(
                id=owner_id,
                owner_id=owner_id,
                scope_id=scope.id,
                revision=0,
                created_at=now,
                updated_at=now,
                customer_id=None,
                test_clock_id=clock_id,
                lifecycle='active',
                binding=None,
                intents=(),
                operations=(),
                coverage=(),
                deletion=None,
            )
            self._put(connection, (owner,))
            return owner

    def claim(
        self, owner_id: str, *, recovery_epoch: str | None = None
    ) -> tuple[Lease, AccountBillingRecord]:
        with self.write() as connection:
            records = billing_records_in(connection)
            self.scope(records)
            runtime = connection.execute(
                'SELECT epoch,ready FROM billing_runtime WHERE id=1'
            ).fetchone()
            if (
                runtime is None
                or (recovery_epoch is None and runtime[1] != 1)
                or (recovery_epoch is not None and runtime[0] != recovery_epoch)
            ):
                raise BillingHold('unverified')
            owner = next(
                (
                    record
                    for record in records
                    if isinstance(record, AccountBillingRecord)
                    and record.id == owner_id
                ),
                None,
            )
            if owner is None:
                raise BillingHold('unknown_owner')
            now = int(self.clock().timestamp())
            existing = connection.execute(
                'SELECT epoch,generation,expires_at FROM billing_leases WHERE record_id=?',
                (owner_id,),
            ).fetchone()
            if existing is not None and existing[0] == runtime[0] and existing[2] > now:
                raise BillingHold('uncertain_operation')
            generation = (existing[1] if existing is not None else 0) + 1
            token = secrets.token_hex(32)
            connection.execute(
                'INSERT INTO billing_leases(record_id,epoch,generation,token,expires_at) VALUES(?,?,?,?,?) ON CONFLICT(record_id) DO UPDATE SET epoch=excluded.epoch,generation=excluded.generation,token=excluded.token,expires_at=excluded.expires_at',
                (
                    owner_id,
                    runtime[0],
                    generation,
                    token,
                    now + self.config.lease_seconds,
                ),
            )
            return Lease(
                owner_id, runtime[0], token, generation, owner.revision, owner.lifecycle
            ), owner

    def _check_lease(
        self, connection: sqlite3.Connection, lease: Lease
    ) -> AccountBillingRecord:
        runtime = connection.execute(
            'SELECT epoch FROM billing_runtime WHERE id=1'
        ).fetchone()
        row = connection.execute(
            'SELECT epoch,generation,token,expires_at FROM billing_leases WHERE record_id=?',
            (lease.owner_id,),
        ).fetchone()
        records = billing_records_in(connection)
        self.scope(records)
        owner = next(
            (
                record
                for record in records
                if isinstance(record, AccountBillingRecord)
                and record.id == lease.owner_id
            ),
            None,
        )
        if (
            runtime is None
            or runtime[0] != lease.epoch
            or row is None
            or tuple(row[:3]) != (lease.epoch, lease.generation, lease.token)
            or row[3] <= int(self.clock().timestamp())
            or owner is None
            or (owner.revision, owner.lifecycle) != (lease.revision, lease.lifecycle)
        ):
            raise BillingHold('uncertain_operation')
        return owner

    def apply(
        self,
        lease: Lease,
        replacement: AccountBillingRecord,
        *,
        applied_events: Sequence[str] = (),
        remove_user: bool = False,
        keep_lease: bool = False,
    ) -> AccountBillingRecord:
        """Receipt/command changes, delivery results and backup logs commit together."""
        with self.write() as connection:
            old = self._check_lease(connection, lease)
            if (replacement.id, replacement.scope_id) != (old.id, old.scope_id):
                raise BillingHold('ownership_conflict')
            now = self.clock()
            replacement = replacement.model_copy(
                update={
                    'revision': old.revision + 1,
                    'updated_at': _next_time(old.updated_at, now),
                }
            )
            changed: list[BillingDocument] = [replacement]
            handled: set[str] = set()
            for record in billing_records_in(connection):
                if (
                    isinstance(record, EventRecord)
                    and record.event_id in applied_events
                ):
                    if record.owner_id != old.id or record.state != 'pending':
                        raise BillingHold('ownership_conflict')
                    changed.append(
                        record.model_copy(
                            update={
                                'state': 'applied',
                                'revision': record.revision + 1,
                                'updated_at': _next_time(record.updated_at, now),
                                'attempts': record.attempts + 1,
                                'next_attempt_at': None,
                                'reason': None,
                            }
                        )
                    )
                    handled.add(record.event_id)
            if handled != set(applied_events) or len(handled) != len(applied_events):
                raise BillingHold('ownership_conflict')
            self._put(connection, changed, removed_user=old.id if remove_user else None)
            if remove_user:
                if replacement.lifecycle != 'deleted':
                    raise BillingHold('deleted_owner')
                user = user_in(connection, 'id', old.id)
                if user is not None:
                    connection.execute('DELETE FROM users WHERE id=?', (old.id,))
                    connection.execute(
                        'DELETE FROM sign_in_codes WHERE email=?', (user.email,)
                    )
                    log_record_change(
                        connection,
                        'user',
                        user.id,
                        f'users/{user.id[:2]}/{user.id}/user.json',
                    )
            if not keep_lease:
                connection.execute(
                    'UPDATE billing_leases SET expires_at=0 WHERE record_id=? AND token=?',
                    (old.id, lease.token),
                )
        return replacement

    def enqueue(self, delivery: Delivery) -> EventRecord:
        with self.write() as connection:
            records = billing_records_in(connection)
            scope = self.scope(records)
            existing = next(
                (
                    record
                    for record in records
                    if isinstance(record, EventRecord)
                    and record.event_id == delivery.event_id
                ),
                None,
            )
            if existing is not None:
                return existing
            owners = {
                row[0]
                for key in (delivery.object_id, delivery.related_id)
                if key is not None
                for row in connection.execute(
                    'SELECT owner_id FROM billing_resources WHERE scope_id=? AND native_id=?',
                    (scope.id, key),
                )
            }
            owner_id = next(iter(owners)) if len(owners) == 1 else None
            reason = (
                'unsupported_event'
                if not delivery.supported
                else (
                    'ownership_conflict'
                    if len(owners) > 1
                    else 'unknown_owner'
                    if owner_id is None
                    else None
                )
            )
            now = timestamp(self.clock())
            event = EventRecord(
                id=new_id(),
                scope_id=scope.id,
                revision=0,
                created_at=now,
                updated_at=now,
                event_id=delivery.event_id,
                event_type=delivery.event_type,
                object_id=delivery.object_id,
                owner_id=owner_id,
                state='pending' if reason is None else 'quarantined',
                attempts=0,
                next_attempt_at=None,
                body_sha256=delivery.body_sha256,
                reason=reason,
            )
            self._put(connection, (event,))
            if event.state == 'pending':
                # A newly delivered wake-up fences any fetch begun before it.
                # Its payload still cannot grant or revoke payment evidence.
                connection.execute(
                    'UPDATE billing_leases SET expires_at=0,generation=generation+1 WHERE record_id=?',
                    (owner_id,),
                )
            return event

    def finish_recovery(self, epoch: str, *, started_at: int) -> None:
        with self.write() as connection:
            records = billing_records_in(connection)
            scope = self.scope(records)
            if any(
                isinstance(record, AccountBillingRecord)
                and (
                    record.lifecycle in ('deleting', 'held')
                    or any(
                        operation.state in ('prepared', 'sent', 'held')
                        for operation in record.operations
                    )
                )
                for record in records
            ):
                raise BillingHold('uncertain_operation')
            current = connection.execute(
                'SELECT epoch FROM billing_runtime WHERE id=1'
            ).fetchone()
            if current is None or current[0] != epoch:
                raise BillingHold('uncertain_operation')
            self._put(
                connection,
                (
                    scope.model_copy(
                        update={
                            'revision': scope.revision + 1,
                            'updated_at': _next_time(scope.updated_at, self.clock()),
                            'reconciled_started_at': started_at,
                        }
                    ),
                ),
            )
            connection.execute(
                "UPDATE billing_runtime SET ready=1,reason='verified',checked_at=? WHERE id=1 AND epoch=?",
                (int(self.clock().timestamp()), epoch),
            )
