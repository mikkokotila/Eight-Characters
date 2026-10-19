"""Exact future billing layout shared by the recovery reader and next writer.

This release does not append these statements to MIGRATIONS. Only an explicit
schema-5 restore/fixture construction uses them; normal account creation stays 4.
"""

from typing import Final

BILLING_SCHEMA_VERSION: Final = 5
BILLING_SCHEMA_5: Final[tuple[str, ...]] = (
    "CREATE TABLE billing_records (\n id TEXT PRIMARY KEY,\n scope_id TEXT NOT NULL REFERENCES billing_records(id) DEFERRABLE INITIALLY DEFERRED,\n record_type TEXT NOT NULL CHECK(record_type IN ('scope','account','event')),\n owner_id TEXT,\n revision INTEGER NOT NULL CHECK(revision >= 0),\n record BLOB NOT NULL,\n CHECK((record_type = 'account' AND owner_id = id) OR (record_type = 'scope' AND owner_id IS NULL AND scope_id = id) OR record_type = 'event')\n) STRICT",
    "CREATE UNIQUE INDEX billing_single_scope ON billing_records(record_type) WHERE record_type = 'scope'",
    "CREATE UNIQUE INDEX billing_one_owner ON billing_records(scope_id, owner_id) WHERE record_type = 'account'",
    "CREATE TABLE billing_resources (\n scope_id TEXT NOT NULL REFERENCES billing_records(id),\n native_id TEXT NOT NULL,\n native_kind TEXT NOT NULL CHECK(native_kind IN ('customer','subscription','checkout','invoice','invoice_payment','payment_intent','charge','refund','dispute')),\n owner_id TEXT NOT NULL REFERENCES billing_records(id),\n PRIMARY KEY(scope_id, native_id)\n) STRICT",
    'CREATE TABLE billing_jobs (\n event_id TEXT PRIMARY KEY,\n record_id TEXT NOT NULL UNIQUE REFERENCES billing_records(id)\n) STRICT',
    'CREATE TABLE billing_runtime (\n id INTEGER PRIMARY KEY CHECK(id = 1),\n epoch TEXT NOT NULL,\n ready INTEGER NOT NULL CHECK(ready IN (0,1)),\n reason TEXT NOT NULL,\n checked_at INTEGER\n) STRICT',
    'CREATE TABLE billing_leases (\n record_id TEXT PRIMARY KEY REFERENCES billing_records(id),\n epoch TEXT NOT NULL,\n generation INTEGER NOT NULL CHECK(generation > 0),\n token TEXT NOT NULL,\n expires_at INTEGER NOT NULL CHECK(expires_at >= 0)\n) STRICT',
    'CREATE TEMP TABLE billing_sequence_copy(value INTEGER NOT NULL) STRICT',
    "INSERT INTO billing_sequence_copy SELECT max(\n coalesce((SELECT seq FROM sqlite_sequence WHERE name='changes'),0),\n (SELECT backed_up_seq FROM backup_progress WHERE id=1),\n coalesce((SELECT max(seq) FROM changes),0))",
    "CREATE TABLE changes_next (\n seq INTEGER PRIMARY KEY AUTOINCREMENT,\n kind TEXT NOT NULL CHECK(kind IN ('user','billing')),\n record_id TEXT NOT NULL,\n path TEXT NOT NULL\n) STRICT",
    'INSERT INTO changes_next SELECT seq,kind,record_id,path FROM changes',
    'DROP TABLE changes',
    'ALTER TABLE changes_next RENAME TO changes',
    "DELETE FROM sqlite_sequence WHERE name='changes'",
    "INSERT INTO sqlite_sequence(name,seq) SELECT 'changes',value FROM billing_sequence_copy",
    'DROP TABLE billing_sequence_copy',
)
