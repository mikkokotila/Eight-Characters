# Accounts: database, backup and restore (Developer)

`eight_characters/accounts/` keeps the app's accounts: one SQLite database, and a
backup of every record as its own age-encrypted file in a private Git repository,
from which the database can be rebuilt with one command, and the API that signs people
in with a code sent by email. The page starts using the API in a later release.

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
  schema newer than the app knows. It runs the numbered migrations an older database
  lacks, each in its own transaction, reading the version under the write lock, so two
  processes opening it at once never run one twice.
- `AccountStore.create(path)` and `AccountStore.restore(path, users, tree=…)` build the
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
transaction. Sessions, sign-in codes and the record of codes asked for are kept in the
database too (schema 2) but stay out of the backup: after a restore, people sign in
again.

## Signing in

There is no password and no separate sign-up form. A code sent to an address proves
it; the first code redeemed for a new address creates its account.

1. The page asks for a code (`POST /api/account/code`) with the address, the purpose
   (`create` or `sign_in`), the account's language when creating (`fi` or `en`), the
   page's language, and a Cloudflare Turnstile token.
2. The server checks the token with Cloudflare, then the hourly limits (per address and
   per client), and sends one of four emails:

   | Asked to | The address has an account | Email | Language |
   |---|---|---|---|
   | create | no | a code that creates it | the chosen one |
   | create | yes | a sign-in code, saying the account exists | the account's |
   | sign in | yes | a sign-in code | the account's |
   | sign in | no | word that there is no account, without a code | the page's |

   The reply is `202 {"sent": true}` in every case, so it never tells who has an account.
3. The page sends the code back (`POST /api/account/session`). A code has 6 digits,
   works once, for 10 minutes, and at most 5 wrong tries; a new code replaces the last.
   Spaces and hyphens in what is typed are ignored.
4. The server sets the session cookie: `__Host-ec_session` over HTTPS (`ec_session` on a
   laptop's plain HTTP), `HttpOnly`, `SameSite=Lax`, `Path=/`, for 30 days. A session
   used in its second half is extended to 30 days again.

Codes and session tokens are stored only as HMAC-SHA256 hashes under `EC_SECRET_KEY`,
so the database alone cannot be used to test guesses or take over a session.

### The API

| Request | Does | Answers |
|---|---|---|
| `POST /api/account/code` | sends a code, or word of no account | `202`; `400` malformed, `403` failed person check, `429` over the hourly limit (with `Retry-After`), `502` the email could not be sent, `503` Turnstile not answering |
| `POST /api/account/session` | signs in with a code, creating the account if it was asked for | `200` and the account; `400` wrong or used code |
| `GET /api/account` | the signed-in account | `200` `{email, language, plan, created_at}`; `401` |
| `PATCH /api/account` | sets `language` | `200`; `401` |
| `DELETE /api/account/session` | signs this browser out | `204` |
| `DELETE /api/account/sessions` | signs the account out everywhere | `204`; `401` |
| `GET /api/account/export` | everything kept for the account, as `bazi-account.json`: its record, its sessions and a pending sign-in code (when made and when they end, without hashes), and the codes asked for in the last hour with the client addresses they came from | `200`; `401` |
| `DELETE /api/account` | deletes the account; `{"email": …}` must repeat its address | `204`; `400`, `401` |

Every request that changes something must carry the site's own `Origin`, or it is
refused with `403`.

## Settings

Everything that differs between a laptop, CI and the server comes from the environment
(AGENTS.md). On the server the values live in `/etc/eight-characters/env`, outside Git.
A missing or malformed value stops the account API with the list of what is wrong.

| Variable | Production | On a laptop |
|---|---|---|
| `EC_APP_ORIGIN` | `https://bazi.nektari.fi` | `http://localhost:8000` |
| `EC_DATABASE_PATH` | `/data/accounts.sqlite3` | any path, made with `init` |
| `EC_SECRET_KEY` | 32 bytes or more, random | the same |
| `EC_MAIL_FROM` | `BaZi <kirjaudu@nektari.fi>` | any address |
| `EC_MAIL_TRANSPORT` | `smtp` | `directory` |
| `EC_SMTP_HOST`, `EC_SMTP_PORT`, `EC_SMTP_USERNAME`, `EC_SMTP_PASSWORD` | `smtp.resend.com`, `465`, `resend`, the Resend key | — |
| `EC_MAIL_DIRECTORY` | — | a folder; each email becomes a `.eml` file |
| `EC_TURNSTILE_SITE_KEY`, `EC_TURNSTILE_SECRET` | the widget's keys | Cloudflare's test keys |
| `EC_CLIENT_IP_HEADER` | `X-Real-IP` | `peer` (the socket's address) |
| `EC_CODE_REQUESTS_PER_HOUR_PER_ADDRESS` | `5` | as needed |
| `EC_CODE_REQUESTS_PER_HOUR_PER_CLIENT` | `20` | as needed |

SMTP is used with TLS from the first byte (port 465). Cloudflare publishes test keys
for Turnstile: site key `1x00000000000000000000AA` and secret
`1x0000000000000000000000000000000AA` always pass.

## The backup

`run_backup(store, checkout, recipient)`, or `python -m eight_characters.accounts
backup`, in this order:

1. Takes the checkout's lock (`.git/eight-characters-backup.lock`); a second run at the
   same time is refused.
2. Stops if the checkout has changes the backup did not make, holds a file or a link
   it never writes, holds records but no manifest, or has a manifest made for another
   key; and if its own files are not as it committed them last. The server cannot read
   a file without the private key, so the database remembers a fingerprint of the
   backup's own files (everything but `.github/`) in its last commit, or in the backup a
   restore read, and any other change, such as a file corrupted or changed by hand,
   stops the run before it adds to it.
3. Reads, in one transaction, every record changed since the last run that reached the
   remote, and encrypts each to the recipient (an age public key, `age1…`). Deleted
   records lose their file and empty folders.
4. Writes `manifest.json` (the recipient and the record count) and checks that the
   files match the database's count.
5. Commits and pushes; only then marks the changes backed up. A failed push leaves
   them for the next run, which pushes everything still on its way. The tree about to
   be committed is recorded first as pending, and as the backup's own once committed,
   so a run stopped between its commit and its record is taken up by the next run
   instead of being taken for a commit the backup did not make.

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
.github/                 the owner's freshness check; the backup never writes it
```

Folders named by the first two characters of an id keep each folder far below
GitHub's recommended 3,000 entries. age authenticates every file, and Git's own
object hashes cover each commit, so the manifest needs no per-file hashes.

### Watching it

The backup is quiet when nothing changes, so the server runs it with `--heartbeat
3600`: a run with nothing new commits an empty `backup: alive` once the last commit is
an hour old. The repository's own scheduled check,
[`backup-freshness.yml`](backup-freshness.yml) in `.github/workflows/`, runs every hour
and fails once the last commit is three hours old; GitHub then emails the person who
last changed its schedule.

That person must be the repository's owner, so the owner commits the check, never the
backup job: the backup leaves `.github/` alone, and its check that the checkout holds
only its own commits fingerprints everything but `.github/`. A change to the check is
committed in the server's checkout, or before the server clones, since the backup never
pulls.

### History

`squash-history` replaces the remote's history with one commit of the current files,
so deleted accounts leave the history. It squashes only the backup the database last
wrote, whole (its layout, a manifest whose count matches the records, and the tree the
database recorded), since the history may be all that holds a record lost since. It
runs only when everything is pushed and the remote has not moved, and its force push
names the commit it replaces.

## Restore

```bash
git clone git@github.com:<owner>/<backup repository>.git backup
python -m eight_characters.accounts restore --checkout backup --identity KEY_FILE --database accounts.sqlite3
```

The restore holds the checkout's lock, so no backup run changes files under it. It
checks the manifest, that the key is the one the backup was encrypted to, the layout,
every file's decryption and form, that each file sits in its own user's folder, that no
address appears twice, and the count. Only then does the database appear, remembering
the Git tree it was restored from, so it backs up into the same repository without
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
