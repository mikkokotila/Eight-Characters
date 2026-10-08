# Accounts: database, backup and restore (Developer)

`eight_characters/accounts/` keeps the app's accounts: one SQLite database, and a
backup of every record as its own age-encrypted file in a private Git repository,
from which the database can be rebuilt with one command, and the API that signs people
in with a code sent by email. Charts need an account; the start page does not.

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
   laptop's plain HTTP), `HttpOnly`, `SameSite=Lax`, `Path=/`, for 400 days, the longest
   browsers keep one. The session it names ends on the server after 30 days without
   use; one used in its second half is extended to 30 days again, there. Only signing
   in sets the cookie, and only signing out or deleting the account removes it: an
   answer that arrives late cannot undo a sign-in or a sign-out made meanwhile.

Codes and session tokens are stored only as HMAC-SHA256 hashes under `EC_SECRET_KEY`,
so the database alone cannot be used to test guesses or take over a session.

### The API

| Request | Does | Answers |
|---|---|---|
| `POST /api/account/code` | sends a code, or word of no account | `202`; `400` malformed, `403` failed person check, `429` over the hourly limit (with `Retry-After`), `502` the email could not be sent, `503` Turnstile not answering |
| `POST /api/account/session` | signs in with a code, creating the account if it was asked for | `200` and the account; `400` wrong or used code |
| `GET /api/account` | the signed-in account | `200` `{email, language, plan, created_at, updated_at, key}`; `401` |
| `PATCH /api/account` | sets `language`; `email` names the account | `200`; `400`, `401`, `409` |
| `DELETE /api/account/session` | signs this browser out | `204` |
| `DELETE /api/account/sessions` | signs the account out everywhere; `{"email": …}` names it | `204`; `400`, `401`, `409` |
| `POST /api/account/export` | everything kept for the account (`{"email": …}` names it), as `bazi-account.json`: its record, its sessions and a pending sign-in code (when made and when they end, without hashes), and the codes asked for in the last hour with the client addresses they came from | `200`; `400`, `401`, `409` |
| `DELETE /api/account` | deletes the account, its sessions and its sign-in code; `{"email": …}` must repeat its address. The codes asked for stay until an hour old, so the hourly limits hold | `204`; `400`, `401` |

Every request that changes something must carry the site's own `Origin`, or it is
refused with `403`.

An action on the account names the account the page shows (`email`). Tabs share the
session cookie, so another tab may have signed in to another account since: the
action is then refused with `409` (`This browser is signed in to another account
now.`) and changes nothing. A malformed `email` is `400`. Deleting the account
already names it, typed again.

## The page

Anyone can open the start page, choose its language, search for a place and type a
birth. Creating the chart asks for an account first.

| Request | Needs an account |
|---|---|
| `POST /api/four_pillars`, `POST /api/chart`, `POST /api/hidden_stems`, `POST /api/evolution_explorer` | yes: without one, `401` before the request is read |
| `POST /api/location_suggest`, `POST /api/location_search`, `GET /api/evolution_controls` | no |

`tests/test_accounts_app.py` holds both lists, so a new request fails it until it is
put on one.

- **Who is signed in.** `GET /` writes the account (`{email, language, plan,
  created_at, updated_at, key}`, or `null`) into `<script id="account-state">`, sent with
  `Cache-Control: private, no-cache` so that no shared cache keeps it. The page extends
  a session in its second half too, on the server, and sends no cookie (see step 4).
- **Signing in** (`static/account.js`). Creating a chart while signed out opens the
  account dialog: the address, and for a new account its language, chosen and never
  preset; Cloudflare Turnstile's widget, whose script loads only when the dialog first
  opens; then the code from the email. The dialog switches to signing in an existing
  account, which needs no language.
- **The account's language.** Signing in sets the page to the account's language, and
  the chart is asked for in it. The page's own language switches change only the page,
  as before. The account's language, which its emails use, is set in the account
  dialog, and the page follows it.
- **A session that ended** (signed out elsewhere, the account deleted, or unused for
  30 days) answers a chart with `401`: the dialog asks once more, and the chart is asked
  for again after signing in. Closing the dialog leaves the form, which says that
  charts need an account, with the birth kept. A `401` that arrives for a chart no
  longer wanted asks nothing, so a sign-in made since for a newer one stays.
- **A refusal is checked before the page signs out.** A request refused for want of a
  session (`401`) may have been sent before another tab signed in: the page asks once
  more (`GET /api/account`), takes a session the browser holds after all, and asks for
  the chart again; only a second refusal signs the page out. A chart left meanwhile
  asks for nothing.
- **The newest answer decides who is signed in.** Tabs share the session cookie, and
  answers come in any order. Each answer tells of the cookie at a moment: a request
  that carries it, of the cookie as it was sent; an answer that sets or removes it
  (signing in, signing out, deleting the account), of the cookie from when it comes.
  The page takes who is signed in from the newest of these, and an answer older than
  what it has taken changes nothing, however late it comes. Another account, signed in
  to in another tab, is taken as a sign-in here, with its language, and a dialog asking
  for a sign-in closes, signed in to it. Of one account, the page keeps the language
  and plan of the later change, from any answer (the newest or not, and one for a chart
  or comparison no longer wanted too): every change moves
  the account's `updated_at` past the last (by a second, within one second or with the
  clock gone back), and every answer carries it, since a check sent after a change may
  read the account before it. An account is told apart by its `key`, a hash of its id,
  which the page is never told: an account made again with an address is another. So a sign-in whose answer sets its cookie
  after a check found another tab's account signs the page in, and one overtaken by a
  newer answer (another tab's account, or the session ended since) closes signed in to
  that account, or asks for a sign-in again.
- **A comparison** checks the session with the server (`GET /api/account`) and asks
  for a sign-in on its own page, before its frames ask for their charts: the frames
  cannot ask themselves. Another account, signed in to in another tab, is taken as a
  sign-in here, with its language; a check asked for before a language set in the
  dialog meanwhile is older, and the language stays. The answer to a check for a
  comparison no longer
  wanted, or older than what the page has learned since, changes nothing, and signing
  out abandons a comparison on its way. **The explorer**, given a birth, links to the start page to sign
  in.
- **Signed in, the dialog is the account:** its address and plan, its language,
  Download my data (`bazi-account.json`), Sign out, Sign out on every device, and Delete
  account, which needs the address typed again. Signing out starts the page again,
  empty. Tabs share the session cookie, so as the menu opens it asks who the session
  belongs to (`GET /api/account`; opened again while an action or this question is
  under way, once that one ends), and its actions wait for the answer, which it takes
  whole (a language another tab set shows): an account signed in to in another tab is
  taken as a sign-in here, and a session ended elsewhere asks for a sign-in. Its
  actions name the account (see the API above): one refused with `409` changed
  nothing, and the menu says so and asks again. An action's answer is the newest of
  its moment too: if the page has learned nothing since, it is the session's (a
  language set there signs the page in to its account, even after an older check found
  the session ended), and if the page has learned since, it keeps that, and the action
  does nothing more and says so. A language set is saved, and shown, unless a later
  change of the account (another tab's) stands. A sign-out or
  deletion that went through still signs the page out, since its answer removed the
  cookie.

## Settings

Everything that differs between a laptop, CI and the server comes from the environment
(AGENTS.md). On the server the values live in `/etc/eight-characters/env`, outside Git.
The app reads them, and opens the database, as it starts: a missing or malformed value,
or a database it cannot open, stops it with the reason.

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
`1x0000000000000000000000000000000AA` always pass (the secret is still checked with
Cloudflare, so asking for a code needs the network).

### On a laptop

```bash
LOCAL=~/eight-characters-local
mkdir -p "$LOCAL/mail"
python -m eight_characters.accounts init --database "$LOCAL/accounts.sqlite3"
export EC_APP_ORIGIN=http://127.0.0.1:8000
export EC_DATABASE_PATH="$LOCAL/accounts.sqlite3"
export EC_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export EC_MAIL_FROM='BaZi <kirjaudu@example.com>'
export EC_MAIL_TRANSPORT=directory
export EC_MAIL_DIRECTORY="$LOCAL/mail"
export EC_TURNSTILE_SITE_KEY=1x00000000000000000000AA
export EC_TURNSTILE_SECRET=1x0000000000000000000000000000000AA
export EC_CLIENT_IP_HEADER=peer
export EC_CODE_REQUESTS_PER_HOUR_PER_ADDRESS=5
export EC_CODE_REQUESTS_PER_HOUR_PER_CLIENT=20
uvicorn eight_characters.main:app
```

Open the page at the origin the settings name, `http://127.0.0.1:8000`: requests from
another, such as `localhost`, are refused. Each email arrives as a `.eml` file in
`$LOCAL/mail`, its code in the subject. A new `EC_SECRET_KEY` ends every session.

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
   backup made last, followed by nothing but the owner's commits to `.github/`. The
   server cannot read a file without the private key, so the database remembers the
   backup's last commit (or the one a restore read), and any other commit stops the
   run before it adds to it: a file corrupted or changed by hand, and commits made by
   hand even when undone since, which a push would publish.
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
backup job: the backup leaves `.github/` alone, and takes commits that change nothing
but `.github/` as the owner's, building on them. A change to the check is committed in
the server's checkout, or before the server clones, since the backup never pulls. After
a squash the check's file is part of the backup's one commit; GitHub emails whoever
last changed a schedule, so confirm afterwards that a failure still reaches the owner.

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
