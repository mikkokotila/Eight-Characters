# Your account

Charts need an account. It is free, and needs no password: a code sent to your email
signs you in. The start page needs none: anyone can open it, choose its language and
type a birth.

## Creating an account

Create chart, while signed out, opens the account window to create a free account.
(Sign in, at the top of the start page, opens it to sign in; "No account yet? Create a
free one" turns it to creating one.)
- Type your email address and choose the account's language, Finnish or English.
  Nothing is chosen for you.
- Wait for the check that you are a person (Cloudflare Turnstile) to finish, and send
  the code.
- The email comes in the account's language. Its code has six digits and works once,
  for ten minutes. Type it, with or without the space.

The chart you asked for then opens, in the account's language.

Already have an account? Sign in, at the top of the start page, or "Already have an
account? Sign in" in the same window: only the address is needed. The email never says whether an address has an account to anyone but its
owner, so the window says only that a code is on its way if the address has one.

## Your language

Signing in sets the app to the account's language. The FI and EN switches still
change the app's language whenever you like; the account's language, which its emails
use, is set in the account window, and the app follows it.

## The account window

Signed in, Account opens it: at the top of the start page, in the chart's and the day's
Actions, in Settings' bar, and among the commands (⌘K or Ctrl+K):
- the address, and the plan (Free);
- the account's language;
- Settings;
- Download my data: everything kept for the account, as `eight-chord-account.json`;
- Sign out, here, or on every device; the app then starts again, empty;
- Delete account, after typing its address again. It cannot be undone.

## What is kept

The account's email address and language, when it was made and changed, and its
sessions. The IP address a code is asked from is kept with that request, for the
hourly limits on codes; a request is dropped once it is an hour old, when the next
code is asked for or the account's data is downloaded. Deleting the account leaves its
requests until then, so that the limits hold.

Charts are calculated, not stored, except those you save. A saved chart keeps its
date, time and place of birth, gender, Zi-hour convention and an optional name: your
own, if you save it and mark it as yours, and anyone else's you save, with the couples
you pair them in. Settings also keep where you are, a place and its coordinates, and
the schools you chose. Someone else's chart is their data: save it only with their
consent. You can rename, correct or remove a saved chart, end a couple, and forget
where you are at any time; all of it leaves with the account.

Accounts, with these settings, are also kept in an encrypted backup, which only the
site's owner can read. A deleted account, a removed chart or a place you remove leaves it at the
backup's next run; earlier copies stay in the backup's history until the owner clears
it.

A session lasts 30 days from signing in, and using the site in its last 15 days
extends it to 30 days again, for at most 400 days from signing in. After it ends, or
after signing out on every device from another one, the next chart asks you to sign
in again, and then opens.
