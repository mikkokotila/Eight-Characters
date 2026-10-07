# Accounts: database, backup and restore (Developer)

`eight_characters/accounts/` keeps the app's accounts: one SQLite database, and a
backup of every record as its own age-encrypted file in a private Git repository,
from which the database can be rebuilt with one command. The web app does not use
it yet; sign-in arrives in a later release.

## Goals

- One file holds the live data; every change is durable when the call returns.
- Every record the backup keeps is backed up within one run of its change, and the
  backup holds nothing readable without the private key, which never comes near the
  server.
- Anything unexpected stops the database, the backup or the restore with the reason.
  Nothing is skipped, guessed or repaired silently.

## The database

- One SQLite file, created owner-only (`0600`), in write-ahead-log mode with
  `synchronous = FULL`: a committed change survives a crash, a power cut or a deploy.
- `AccountStore.open(path)` refuses a missing file (and never creates one), a file that
  is no account database (account databases carry SQLite's `application_id`), and a
  schema newer than the app knows. It runs the numbered
  migrations an older database lacks, each in its own transaction.
- `AccountStore.create(path)` and `AccountStore.restore(path, users, head=…)` build the
  database beside its final path (`<name>.partial`, created exclusively, so a second
  build at the same time fails at once) and move it into place only when complete;
  neither builds over an existing file.
- Each call opens its own connection; writes take the write lock first
  (`BEGIN IMMEDIATE`), so two sign-ups with one address make one account.

### Records

| Record | Fields | Backup path |
|---|---|---|
| user | `id` (32 hex digits), `email` (trimmed, lowercase), `language` (`fi`/`en`), `plan` (`free`/`basic`/`pro`/`max`), `created_at`, `updated_at` (UTC, `2026-10-07T12:00:00Z`) | `users/<id[:2]>/<id>/user.json.age` |

A record's file is canonical JSON (UTF-8, keys sorted, two-space indents, a final
newline) with `"schema": 1` and `"kind"`. A file that decodes to a valid record but is
not exactly those bytes is refused.

Every change to a backed-up record is logged in the `changes` table in the same
transaction. Sign-in codes and sessions, when they arrive, stay out of the backup.

## The backup

`run_backup(store, checkout, recipient)`, or `python -m eight_characters.accounts
backup`, in this order:

1. Takes the checkout's lock (`.git/eight-characters-backup.lock`); a second run at the
   same time is refused. A run that was stopped while writing (killed, or the server
   restarting) left its marker, `.git/eight-characters-backup.writing`: its changes,
   and the locks its Git commands left, are put back, and the database still holds
   what it was writing.
2. Stops if the checkout has changes the backup did not make, holds a file or a link
   it never writes (or a folder where it writes a file), holds records but no manifest,
   or has a manifest made for another key; and if its last commit is not the one the
   backup made last. The server cannot read a file without the private key, so the
   database remembers the backup's last commit (or the one a restore read), and any
   other commit stops the run before it adds to it: a file corrupted or changed by
   hand, and commits made by hand even when undone since, which a push would
   publish.
3. Reads, in one transaction, every record changed since the last run that reached the
   remote, and encrypts each to the recipient (an age public key, `age1…`). Deleted
   records lose their file and empty folders.
4. Writes `manifest.json` (the recipient and the record count) and checks that the
   files match the database's count.
5. Commits and pushes; only then marks the changes backed up. A failed push leaves
   them for the next run, which pushes everything still on its way. The commit is made
   first and recorded as pending, then the branch moves to it and it is recorded as
   the backup's own, so a run stopped in between is taken up by the next run instead
   of being taken for a commit the backup did not make.

A run that fails before its commit (a count that differs, Git refusing to commit or
taking too long) puts the work tree and the index back to the last commit before it
reports the reason, so the next run meets the same problem and names it, instead of
stopping at files the failed run wrote.

Git runs with a 120-second limit per command and never waits for a password
(`GIT_TERMINAL_PROMPT=0`); SSH settings come from the environment
(`GIT_SSH_COMMAND`). Commits carry the identity `Eight Characters backup`.

The checkout is a clone of the backup repository, which starts empty: a repository
created with a README or licence holds files the backup never writes, and stops it.

### Layout

```
manifest.json            the recipient and the record count
README.md                how to restore
.gitattributes           *.age binary
users/<id[:2]>/<id>/user.json.age
```

Folders named by the first two characters of an id keep each folder far below
GitHub's recommended 3,000 entries. age authenticates every file, and Git's own
object hashes cover each commit, so the manifest needs no per-file hashes.

### History

`squash-history` replaces the remote's history with one commit of the current files,
so deleted accounts leave the history. It squashes only the backup the database last
wrote, whole (its layout, a manifest whose count matches the records, and the commit the
database recorded), since the history may be all that holds a record lost since. It
runs only when everything is pushed and the remote has not moved, and its force push
names the commit it replaces.

The squash is recorded before anything moves, and the remote moves before the
checkout. Stopped part way, it stops the backup ("run squash-history again") until it
is run again, which finishes it from wherever it stopped. While it moves anything it
keeps the writing marker, so one killed part way leaves no Git lock behind for the
next. A push that fails while the remote has not moved leaves the history as it was,
and the backup goes on.

## Restore

```bash
git clone git@github.com:<owner>/<backup repository>.git backup
python -m eight_characters.accounts restore --checkout backup --identity KEY_FILE --database accounts.sqlite3
```

The restore holds the checkout's lock, so no backup run changes files under it. It
checks the manifest, that the key is the one the backup was encrypted to, the layout,
every file's decryption and form, that each file sits in its own user's folder, that no
address appears twice, and the count. Only then does the database appear, remembering
the commit it was restored from, so it backs up into the same repository without
rewriting it.

## Keys

```bash
python -m eight_characters.accounts keygen --identity backup-key.txt
```

writes a new private key in `age-keygen`'s format to a new owner-only file and prints
the public key. The public key goes to the server's settings; the private key stays
offline. `age --decrypt --identity backup-key.txt FILE` reads any one record.

## Commands

| Command | Does |
|---|---|
| `init --database PATH` | creates an empty database |
| `keygen --identity PATH` | makes the backup key pair |
| `backup --database PATH --checkout DIR --recipient AGE1…` | one backup run |
| `restore --checkout DIR --identity PATH --database PATH` | rebuilds a database |
| `squash-history --database PATH --checkout DIR` | one commit of the current files |

Each prints one line and exits `0`, or prints `error: …` and exits `1`.
