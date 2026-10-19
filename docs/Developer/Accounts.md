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
| user | `id` (32 hex digits), `email` (trimmed, lowercase), `language` (`fi`/`en`), `plan` (`free`/`basic`/`pro`/`max`), `created_at`, `updated_at` (UTC, `2026-10-07T12:00:00Z`), `settings` (below, or `null`) | `users/<id[:2]>/<id>/user.json.age` |

A record's file is canonical JSON (UTF-8, keys sorted, two-space indents, a final
newline) with `"schema"` and `"kind"`. A file that decodes to a valid record but is
not exactly those bytes is refused. The app writes schema 3. Schema 1 records, from
before accounts kept settings, have no `settings` field and read as accounts without
any; schema 2 records hold settings with a partner's chart (below). Both still
restore.

An account's settings are part of its record:
- `charts`: the saved charts, in the order saved. New additions currently stop at
  50; reading a retained record has no plan-size limit. Each is an `id` (32
  random hex digits) and a `birth`, which holds `name` (`null` or 1 to 80 printable
  characters), `date`, `time`, `place`, `fold` (`0`, `1` or `null`), `gender`
  (`male`/`female`) and `zi` (`split_midnight`/`whole_zi_23`), checked by the first
  chart's rules. A birth is saved once: two births with the same day, time to the
  second, fold, timezone, coordinates, gender and Zi convention are one chart.
- `my_chart`: the person's own chart, a saved chart's id, or `null`.
- `couples`: each an `id` and `charts`, two different saved charts' ids in the order
  paired; the same two charts at most once, in either order. A chart can be in any
  number of couples: how many a chart may join is its account's plan's (Plans, below),
  a rule for asking for a couple, never for reading a record.
- `pending_partner`: the chart kept from a schema 2 partner, waiting to pair with the
  first chart marked as the person's own, or `null`.
- `place` (where the person is: `name`, `city`, `timezone`, `latitude`, `longitude`,
  or `null`), `schools` (`favourable`, `season`, `transits`: a preset, or `null` to
  follow the default) and `updated_at`.

Coordinates are written as numbers with a decimal point. The database keeps the
settings as the same canonical JSON (migration 4, `settings`, deleted with the
account), and a change to them is logged as the user's, so the backup copies the
account's record again.

Settings written before accounts kept charts hold `partner` (a birth or `null`) in
place of `charts`, `my_chart`, `couples` and `pending_partner`. They are read as they
are, each checked as its own shape's canonical bytes: the partner is a saved chart
under an id derived from its birth (the first 32 hex digits of the SHA-256 of
`partner\n` and its canonical JSON), so every read and every restore of a schema 2
backup gives the same id, and it waits as `pending_partner`. The account's next change
writes the new shape. Rolling the app back after that needs a restore from the
backup.

Every change to a backed-up record is logged in the `changes` table in the same
transaction. Sessions, sign-in codes and the record of codes asked for are kept in the
database too (schema 2) but stay out of the backup: after a restore, people sign in
again. So does the record of first charts asked for (schema 3), kept for an hour for
the limit per client.

### Library allowances: readers before writers

The record, database, export, encrypted backup and restore readers accept retained
libraries larger than the current 50-chart write allowance. Identity, uniqueness,
birth and couple-reference validation still applies to every saved chart. Editing
or removing an existing chart remains possible above the allowance; adding another
does not. A downgrade must never make retained data unreadable.

The browser also understands a future `chart_limit: null` as unlimited in Settings,
the library and birth-saving controls. A positive integer remains a finite write
allowance; an omitted or malformed limit is an error. By default the API returns 50
and the store refuses the 51st addition. No paid tier is selected by this policy.

Deploy these readers everywhere before any writer can store more than 50 charts.
Once such a writer runs, the rollback floor is 0.65.0: older releases reject those
records and can stop backup or restore. Going further back requires restoring a
backup from before the first over-50 library, losing subsequent changes. Neither
the record shape/schema nor the database schema changes in this reader release.

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
   browsers keep one. The session it names ends on the server 30 days after it was
   made or last extended; one used in its second half is extended to 30 days again,
   there. Only signing in sets the cookie, and only signing out or deleting the account
   removes it (by its name, whichever session it holds by then): a renewal or a refusal
   that arrives late changes no cookie.

Codes and session tokens are stored only as HMAC-SHA256 hashes under `EC_SECRET_KEY`,
so the database alone cannot be used to test guesses or take over a session.

### The API

| Request | Does | Answers |
|---|---|---|
| `POST /api/account/code` | sends a code, or word of no account | `202`; `400` malformed, `403` failed person check, `429` over the hourly limit (with `Retry-After`), `502` the email could not be sent, `503` Turnstile not answering |
| `POST /api/account/session` | signs in with a code, creating the account if it was asked for | `200` and the account; `400` wrong or used code |
| `GET /api/account` | the signed-in account | `200` `{email, language, plan, created_at, updated_at, key}`; `401` |
| `PATCH /api/account` | sets `language`; `key` names the account | `200`; `400`, `401`, `409` |
| `DELETE /api/account/session` | signs this browser out | `204` |
| `DELETE /api/account/sessions` | signs the account out everywhere; `{"key": …}` names it | `204`; `400`, `401`, `409` |
| `POST /api/account/export` | everything kept for the account (`{"key": …}` names it), as `bazi-account.json`: its record, its sessions and a pending sign-in code (when made and when they end, without hashes), and the codes asked for in the last hour with the client addresses they came from | `200`; `400`, `401`, `409` |
| `DELETE /api/account` | deletes the account, its sessions and its sign-in code; `{"email": …, "key": …}`: `key` names it, and `email` repeats its address. The codes asked for stay until an hour old, so the hourly limits hold | `204`; `400`, `401`, `409` |
| `GET /api/account/settings` | your saved charts (each with its `id` and its four pillars, or `pillars: null` and the reason in `problem` if the engine no longer charts it), `my_chart`, `couples`, `pending_partner`, `chart_limit` (how many charts the account keeps at most), `couples_per_chart` (how many couples one chart may be in on your plan, `null` for no cap; every settings answer has it), where you are, the schools Today follows and the ones chosen (`null`: the default), `updated_at` (`null` before anything is set) and the account's `key` | `200`; `401` |
| `POST /api/account/charts` | saves a birth: `{key, updated_at, name?, date, time, place: {name, city, timezone, latitude, longitude}, fold?, gender, zi?, mine?, couple_with?}`, checked by the first chart's rules and charted first. `mine` marks it as your own and `couple_with` (a saved chart's id) pairs it, in the same write | `201`, the settings and `saved` (the new id); `400` (a malformed birth, a time the clocks skipped or repeated without `fold`, a full library, a birth saved already, a partner at its plan's cap), `401`, `403`, `404` (no such partner), `409`, `412` |
| `PUT /api/account/charts/{id}` | corrects a saved chart's birth, charted first; it keeps its id, its mark and its couples | `200` and the settings; `400`, `401`, `403`, `404`, `409`, `412` |
| `PUT /api/account/charts/{id}/name` | renames a saved chart (`{key, updated_at, name}`, `null` for none) without charting it again | `200` and the settings; `400`, `401`, `403`, `404`, `409`, `412` |
| `DELETE /api/account/charts/{id}` | removes a saved chart, ends each of its couples, and unmarks it | `200` and the settings; `400`, `401`, `403`, `404`, `409`, `412` |
| `PUT /api/account/my-chart` | marks a saved chart as your own: `{key, updated_at, chart}`; a waiting partner pairs with it unless the chart is at its plan's cap, and waits no longer either way | `200` and the settings; `400`, `401`, `403`, `404`, `409`, `412` |
| `DELETE /api/account/my-chart` | no chart is your own any more | `200` and the settings; `400`, `401`, `403`, `409`, `412` |
| `POST /api/account/couples` | pairs two saved charts: `{key, updated_at, charts: [id, id]}` | `201` and the settings; `400` (one chart twice, the two a couple already, a chart at its plan's cap, named), `401`, `403`, `404`, `409`, `412` |
| `DELETE /api/account/couples/{id}` | ends a couple; both charts stay saved | `200` and the settings; `400`, `401`, `403`, `404`, `409`, `412` |
| `PUT /api/account/place` | where you are: `{key, updated_at, place}` | `200` and the settings; `400`, `401`, `403`, `409`, `412` |
| `DELETE /api/account/place` | forgets where you are; `{"key": …, "updated_at": …}` | `200` and the settings; `400`, `401`, `403`, `409`, `412` |
| `PATCH /api/account/schools` | chooses any of `favourable`, `season`, `transits` (`GET /api/schools`), or `null` to follow the default again; those left out stay. `{key, updated_at, …}` | `200` and the settings; `400` an unknown preset or setting, `401`, `403`, `409`, `412` |

### Plans

An account's plan is its user record's `plan`. `accounts/plans.py` maps each plan to
what it lets the account keep; `AccountStore` takes the table (as it takes its clock),
and refuses one that misses or adds a plan before it opens or builds a database.

- `couples_per_chart`: how many couples one saved chart may be in; `null` for no cap.
  No plan caps couples for now. Once plans are sold, `basic` keeps one and `pro` and
  `max` as many as wanted (the owner, 2026-10-17; #96); the table is the one place
  that changes.
- `charts_per_account`: how many saved charts the account may add up to, a positive
  integer or `None` for unlimited. Every legacy plan defaults to 50. The store checks
  the policy in the same transaction that reads the account and settings; a refusal
  writes no settings or backup change. Every API settings response reports that same
  policy as `chart_limit`, even before the account has settings. A browser cannot
  supply its own allowance. Records, export and encrypted recovery read all retained
  charts above the current allowance; corrections, renames and removals still work.
  The published offer's 1/5/25/unlimited values can be enforced by this path, but are
  not applied to existing legacy plan names or enabled for sale here. Verified
  payment coverage and explicit legacy semantics must select the future sold tier;
  a configured test allowance is not proof of payment or fulfilled paid access.
- A cap is checked when a couple is asked for, in the write that reads the user's plan
  and settings, and never when settings are read, exported, backed up or restored. An
  account moved to a smaller plan keeps and reads every couple, Today keeps reading
  them, a new couple for a chart at or over the cap is refused naming the chart, and
  ending a couple always works.
- The refusals, in order: a malformed id; one chart twice; an unknown chart on either
  side (`404`); the two a couple already ("These two charts are a couple already.");
  a chart at the cap ("{name} is in as many couples as the plan allows ({cap})."). For
  a new chart with `couple_with`: a full library, a birth saved already, an unknown
  partner, the partner at the cap. A refusal changes nothing.
- The waiting partner pairs with the chart marked as yours unless that chart is at the
  cap; it is marked all the same, and the partner stays saved and waits no longer.
- Every settings answer says the cap (`couples_per_chart`); an export carries the plan,
  not the limit.

### Couples: the rollout

A chart in any number of couples came in releases. #98 (0.53.0) taught every reader to
read it: the record, the backup, the restore, the export and the pages. #102 (0.54.0)
lets the store and the API pair a chart that is in a couple already, within its plan's
cap; Settings' Pair follows (#96). The order matters because a release before #98
refuses a row with a chart in two couples, and its backup snapshot reads every changed
account at once: one such row would stop the backup for every account, and that
release could not restore the newest backup. So once any account has a chart in two
couples, roll back to 0.53.0 at most. Going further back needs a restore from a backup
commit made before the first such couple, and loses every account's changes since.

Every request that changes something must carry the site's own `Origin`, or it is
refused with `403`. An id that is not 32 lowercase hex digits answers `400`; the
library's refusals answer `400` too, since the page reads a `409` as another account
signed in. Every `/api/account` answer says `Cache-Control: no-store`.

A change to the settings names the settings it was made from by their `updated_at`, as
`GET /api/account/settings` gave it (`null` for an account that has set nothing). If
the settings have changed since, in another tab or browser, the change is refused with
`412` (`Your settings changed elsewhere since this page read them.`) and nothing is
written: the page reads them again. The check and the write are one transaction, so
one tab never silently undoes another's change.

An action on the account names the account the page shows by its `key`, which every
account answer carries. Tabs share the session cookie, so another tab may have signed
in to another account since, or deleted this one and made it again with its address:
the action is then refused with `409` (`This browser is signed in to another account
now.`) and changes nothing. A malformed `key` is `400`. Deleting the account also needs
its address typed again (`400` if it differs).

## The page

Anyone can open the start page, choose its language, search for a place and type a
birth. Creating the chart asks for an account first.

| Request | Needs an account |
|---|---|
| `POST /api/four_pillars`, `POST /api/chart`, `POST /api/hidden_stems`, `POST /api/evolution_explorer`, `POST /api/today` | yes: without one, `401` before the request is validated |
| `POST /api/first_chart` | no: it is for someone without one, and each client may ask for `EC_CHART_REQUESTS_PER_HOUR_PER_CLIENT` an hour |
| `POST /api/location_suggest`, `POST /api/location_search`, `GET /api/evolution_controls`, `GET /api/schools` | no |

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
- **A session that ended** (signed out elsewhere, the account deleted, or past its
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
  for a sign-in closes, signed in to it. Nothing read for the account before stays on
  the page: Settings forget it (a read or change answered after is not taken, and says
  the account changed), the library and the save dialog close, a birth being added or
  corrected is let go, and Settings, Today, the chart's name and a landing on your
  chart are read again for the account taken. Of one account, the page keeps the language
  and plan of the later change, from any answer (the newest or not, and one for a chart
  or comparison no longer wanted too): every change moves
  the account's `updated_at` past the last (by a second, within one second or with the
  clock gone back), and every answer carries it, since a check sent after a change may
  read the account before it. An account is told apart by its `key`, a hash of its id,
  which no account answer carries: an account made again with an address is another. So a sign-in whose answer sets its cookie
  after a check found another tab's account signs the page in, and one overtaken by a
  newer answer (another tab's account, or the session ended since) closes signed in to
  that account, or asks for a sign-in again.
- **A comparison** checks the session with the server (`GET /api/account`) and asks
  for a sign-in on its own page, before its frames ask for their charts: the frames
  cannot ask themselves. Another account, signed in to in another tab, is taken as a
  sign-in here, with its language, which both charts take; a check asked for before a
  language set in the dialog meanwhile is older, and the language stays. Swapping its
  sides, or changing its language, checks the session first in the same way, one
  change at a time: meanwhile its language and sides take no clicks, and a check that
  fails says so. Its frames take its language as the page takes the account's (below),
  and its address names the language at once, so a swap draws both charts in it. The answer to a check for a
  comparison no longer wanted, or older than what the page has learned since, changes
  nothing, and signing out abandons a comparison on its way.
  **The explorer**, given a birth, links to the start page to sign in.
- **Signed in, the dialog is the account:** its address and plan, its language,
  Download my data (`bazi-account.json`), Sign out, Sign out on every device, and Delete
  account, which needs the address typed again. A chart on screen follows the
  account's language, asked for again in it, and so does a chart on its way, before it
  is drawn. Signing out starts the page again, empty,
  and forgets the chart it showed: going back to its address asks for it, and for a
  sign-in. Tabs share the session cookie, so as the menu opens it asks who the session
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
| `EC_APP_ORIGIN` | `https://bazi.nektari.fi` | `http://127.0.0.1:8000` |
| `EC_DATABASE_PATH` | `/data/accounts.sqlite3` | any path, made with `init` |
| `EC_SECRET_KEY` | 32 bytes or more, random | the same |
| `EC_MAIL_FROM` | `Eight Chord <kirjaudu@nektari.fi>` | any address |
| `EC_MAIL_TRANSPORT` | `smtp` | `directory` |
| `EC_SMTP_HOST`, `EC_SMTP_PORT`, `EC_SMTP_USERNAME`, `EC_SMTP_PASSWORD` | `smtp.resend.com`, `465`, `resend`, the Resend key | — |
| `EC_MAIL_DIRECTORY` | — | a folder; each email becomes a `.eml` file |
| `EC_TURNSTILE_SITE_KEY`, `EC_TURNSTILE_SECRET` | the widget's keys | Cloudflare's test keys |
| `EC_CLIENT_IP_HEADER` | `X-Real-IP` | `peer` (the socket's address) |
| `EC_CODE_REQUESTS_PER_HOUR_PER_ADDRESS` | `5` | as needed |
| `EC_CODE_REQUESTS_PER_HOUR_PER_CLIENT` | `20` | as needed |
| `EC_CHART_REQUESTS_PER_HOUR_PER_CLIENT` | `60` | as needed |
| `EC_PROXY_SECRET` (optional) | 32 bytes or more, random, shared with the one proxy that passes requests on; not set while none does | not set |

SMTP is used with TLS from the first byte (port 465). Cloudflare publishes test keys
for Turnstile: site key `1x00000000000000000000AA` and secret
`1x0000000000000000000000000000000AA` always pass (the secret is still checked with
Cloudflare, so asking for a code needs the network).

### A trusted proxy

The limits per client count the address `EC_CLIENT_IP_HEADER` names. A server that
passes requests on to the app for many visitors, such as another site's Worker, comes
from one address for all of them. So that each visitor still has limits of their own,
that server shows `EC_PROXY_SECRET` in `X-EC-Proxy-Secret` and names the visitor in
`X-EC-Client`, and the app counts the visitor it names.

A request with either header that does not show the secret is refused with `403`, and
one that shows it without naming a client with `400`. A misconfigured proxy so fails at
once, instead of counting all its visitors as one, and nobody else can choose the
client they are counted as. Without `EC_PROXY_SECRET` no proxy is trusted.

### On a laptop

```bash
LOCAL=~/eight-characters-local
mkdir -p "$LOCAL/mail"
python -m eight_characters.accounts init --database "$LOCAL/accounts.sqlite3"
export EC_APP_ORIGIN=http://127.0.0.1:8000
export EC_DATABASE_PATH="$LOCAL/accounts.sqlite3"
export EC_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export EC_MAIL_FROM='Eight Chord <kirjaudu@example.com>'
export EC_MAIL_TRANSPORT=directory
export EC_MAIL_DIRECTORY="$LOCAL/mail"
export EC_TURNSTILE_SITE_KEY=1x00000000000000000000AA
export EC_TURNSTILE_SECRET=1x0000000000000000000000000000000AA
export EC_CLIENT_IP_HEADER=peer
export EC_CODE_REQUESTS_PER_HOUR_PER_ADDRESS=5
export EC_CODE_REQUESTS_PER_HOUR_PER_CLIENT=20
export EC_CHART_REQUESTS_PER_HOUR_PER_CLIENT=60
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

## Sandbox billing catalogue preflight

`python -m eight_characters.accounts billing-preflight` is a read-only prerequisite
for #119. It creates nothing, changes no account or access, and opens no checkout.
No SDK is added: bounded `httpx` GET requests read the credential's own account and
the six configured Prices with their Products expanded. Every response must carry
the exact configured API version. Redirects, unavailable evidence and mismatches
stop the command, without logging credentials or raw provider bodies.

Configure only in the server/operator environment, never browser code or source:

| Variable | Required value |
|---|---|
| `EC_BILLING_MODE` | `sandbox`; absent or `disabled` is explicit disabled status, exit 2. `live` is refused. |
| `EC_STRIPE_API_KEY` | Existing authorized product sandbox secret/restricted key (`sk_test_…` / `rk_test_…`); separate from Adslop accounting. This preflight needs account and Price/Product read access only. |
| `EC_STRIPE_API_VERSION` | Exact dated named version supported by the configured native integration; required, with response-version verification. |
| `EC_STRIPE_ACCOUNT_ID` | Expected sandbox account ID; compared with `GET /v1/account`, never a browser selection. |
| `EC_STRIPE_PRODUCT_BASIC`, `_PLUS`, `_PRO` | Three distinct approved native Product IDs. |
| `EC_STRIPE_PRICE_BASIC_MONTHLY`, `_BASIC_YEARLY`, `_PLUS_MONTHLY`, `_PLUS_YEARLY`, `_PRO_MONTHLY`, `_PRO_YEARLY` | Six distinct approved native Price IDs. |

The offer follows the published pricing contract: Basic 699/5900, Plus 1499/12900,
Pro 2900/24900 USD minor units, monthly/yearly. Each active sandbox Price and
Product must match the configured IDs, per-unit licensed billing, exact integer
and decimal amount, interval/count one, exclusive tax basis, no custom amount,
quantity transform, tiered billing or trial. The report's `required_quantity: 1`
is the future checkout constraint, not evidence of any subscription quantity.

Exit 0 proves only the native catalogue at that read. `checkout_available`,
`payment_verified`, `paid_access_verified` and `tax_calculation_verified` remain
false. Exclusive tax behavior does not itself calculate or collect tax. Exit 1
means invalid configuration or unverified native evidence. Partial Stripe
configuration while mode is disabled is an error. The app does not consume this
configuration yet, and neither a test key nor this CLI is a live launch switch.

Provider contracts: [Price object](https://docs.stripe.com/api/prices/object),
[API keys](https://docs.stripe.com/keys),
[API versioning](https://docs.stripe.com/api/versioning). No native account/product/
price identifier, operator identity or credential is hard-coded.
