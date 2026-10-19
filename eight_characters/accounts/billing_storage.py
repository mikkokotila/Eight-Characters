"""Schema-5 preservation helpers, with no purchase or financial mutation API."""

import re
import secrets
import sqlite3
from collections.abc import Sequence
from functools import lru_cache

from eight_characters.accounts.billing_records import (
    AccountBillingRecord,
    BillingDocument,
    EventRecord,
    decode_billing,
    encode_billing,
    resource_claims,
    validate_billing_graph,
)
from eight_characters.accounts.billing_schema import BILLING_SCHEMA_5
from eight_characters.accounts.records import RecordError, User


def _layout(connection: sqlite3.Connection) -> tuple[tuple[str, ...], ...]:
    rows = connection.execute(
        'SELECT type,name,tbl_name,sql FROM sqlite_master '
        "WHERE name NOT GLOB 'sqlite_*' AND sql IS NOT NULL ORDER BY type,name"
    ).fetchall()
    if any(not all(isinstance(v, str) for v in row) for row in rows):
        raise RecordError('The database has an unreadable schema definition.')
    return tuple(
        (
            str(row[0]),
            str(row[1]),
            str(row[2]),
            re.sub(r'\s+', ' ', str(row[3])).strip(),
        )
        for row in rows
    )


@lru_cache(maxsize=1)
def _expected(migrations: tuple[tuple[str, ...], ...]) -> tuple[tuple[str, ...], ...]:
    connection = sqlite3.connect(':memory:')
    try:
        for migration in (*migrations, BILLING_SCHEMA_5):
            for statement in migration:
                connection.execute(statement)
        return _layout(connection)
    finally:
        connection.close()


def require_billing_layout(
    connection: sqlite3.Connection, migrations: tuple[tuple[str, ...], ...]
) -> None:
    if _layout(connection) != _expected(migrations):
        raise RecordError(
            'The schema-5 database differs from the reviewed billing layout.'
        )


def _header(record: BillingDocument) -> tuple[str, str, str | None, int]:
    owner = (
        record.owner_id
        if isinstance(record, (AccountBillingRecord, EventRecord))
        else None
    )
    return record.scope_id, record.record_type, owner, record.revision


def read_billing(
    connection: sqlite3.Connection, users: Sequence[User]
) -> tuple[BillingDocument, ...]:
    records: list[BillingDocument] = []
    for row in connection.execute(
        'SELECT id,scope_id,record_type,owner_id,revision,record FROM billing_records ORDER BY id'
    ):
        if not isinstance(row[5], bytes):
            raise RecordError('A billing row is not a byte record.')
        record = decode_billing(row[5])
        if (row[0], *row[1:5]) != (record.id, *_header(record)):
            raise RecordError('A billing row header differs from its canonical record.')
        records.append(record)
    validate_billing_graph(records, users)
    expected_claims = {
        (r.scope_id, native_id, kind, r.owner_id)
        for r in records
        if isinstance(r, AccountBillingRecord)
        for native_id, kind in resource_claims(r).items()
    }
    actual_claims = set(
        connection.execute(
            'SELECT scope_id,native_id,native_kind,owner_id FROM billing_resources'
        ).fetchall()
    )
    expected_jobs = {(r.event_id, r.id) for r in records if isinstance(r, EventRecord)}
    actual_jobs = set(
        connection.execute('SELECT event_id,record_id FROM billing_jobs').fetchall()
    )
    if actual_claims != expected_claims or actual_jobs != expected_jobs:
        raise RecordError(
            'Financial ownership or delivery projection differs from authority.'
        )
    return tuple(records)


def restore_billing(
    connection: sqlite3.Connection, records: Sequence[BillingDocument]
) -> None:
    """Only for the exclusive partial database, after complete graph validation."""
    for record in records:
        connection.execute(
            'INSERT INTO billing_records (id,scope_id,record_type,owner_id,revision,record) '
            'VALUES (?,?,?,?,?,?)',
            (record.id, *_header(record), encode_billing(record)),
        )
    for record in records:
        if isinstance(record, AccountBillingRecord):
            for native_id, kind in resource_claims(record).items():
                connection.execute(
                    'INSERT INTO billing_resources (scope_id,native_id,native_kind,owner_id) '
                    'VALUES (?,?,?,?)',
                    (record.scope_id, native_id, kind, record.owner_id),
                )
        elif isinstance(record, EventRecord):
            connection.execute(
                'INSERT INTO billing_jobs (event_id,record_id) VALUES (?,?)',
                (record.event_id, record.id),
            )
    connection.execute(
        'INSERT INTO billing_runtime (id,epoch,ready,reason,checked_at) '
        "VALUES (1,?,0,'unverified',NULL)",
        (secrets.token_hex(16),),
    )
