# Your account

Charts need an account. It is free, and needs no password: a code sent to your email
signs you in. The start page needs none: anyone can open it, choose its language and
type a birth.

## Creating an account

Create chart, while signed out, opens the account window (so does Sign in, at the top
of the start page).
- Type your email address and choose the account's language, Finnish or English.
  Nothing is chosen for you.
- Wait for the check that you are a person (Cloudflare Turnstile) to finish, and send
  the code.
- The email comes in the account's language. Its code has six digits and works once,
  for ten minutes. Type it, with or without the space.

The chart you asked for then opens, in the account's language.

Already have an account? Choose Sign in in the same window: only the address is
needed. The email never says whether an address has an account to anyone but its
owner, so the window says only that a code is on its way if the address has one.

## Your language

Signing in sets the app to the account's language. The FI and EN switches still
change the app's language whenever you like; the account's language, which its emails
use, is set in the account window, and the app follows it.

## The account window

Signed in, Account at the top of the start page (or Account among the commands, ⌘K or
Ctrl+K, on a chart) opens it:
- the address, and the plan (Free);
- the account's language;
- Download my data: everything kept for the account, as `bazi-account.json`;
- Sign out, here, or on every device; the app then starts again, empty;
- Delete account, after typing its address again. It cannot be undone.

## What is kept

The account's email address and language, when it was made and changed, and its
sessions. The IP address a code is asked from is kept with that request, for the
hourly limits on codes; a request is dropped once it is an hour old, when the next
code is asked for. Deleting the account leaves its requests until then, so that the
limits hold. Charts are calculated, not stored.

A session lasts 30 days from its last use. After it ends, or after signing out on
another device, the next chart asks you to sign in again, and then opens.
