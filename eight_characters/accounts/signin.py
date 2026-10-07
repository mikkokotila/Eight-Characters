"""Signing in with a code sent by email, and the sessions that follow.

There is no password and no separate sign-up: a code sent to an address proves it,
and the first code redeemed for a new address creates its account, in the language
chosen when asking for the code. Whatever the address, asking for a code sends an
email and gets the same reply, so the reply never tells who has an account.
"""

import hashlib
import hmac
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Literal

from eight_characters.accounts.records import (
    Language,
    User,
    normalize_email,
    parse_timestamp,
    timestamp,
)
from eight_characters.accounts.store import (
    AccountStore,
    EmailTaken,
    Session,
    SignInCode,
)

CODE_DIGITS: Final = 6
CODE_LIFETIME: Final = timedelta(minutes=10)
CODE_TRIES: Final = 5
SESSION_LIFETIME: Final = timedelta(days=30)
# A session used with less than this left is extended to a full lifetime again.
SESSION_RENEWAL: Final = timedelta(days=15)
REQUEST_WINDOW: Final = timedelta(hours=1)
SESSION_TOKEN_MAX_LENGTH: Final = 128

Purpose = Literal['sign_in', 'create']
MessageKind = Literal['sign_in_code', 'create_code', 'existing_account', 'no_account']

_TYPED_CODE = re.compile(r'[\s-]')


class SignInError(Exception):
    """Signing in cannot go on; the message says why and can be shown."""


class TooManyRequests(SignInError):
    """The address or the client has asked for its limit of codes this hour."""


class CodeRefused(SignInError):
    """The code is wrong, used, expired or out of tries. One answer for all, so a
    reply never tells which."""


@dataclass(frozen=True)
class Limits:
    """How many codes an address, and a client, may ask for per hour."""

    per_address: int
    per_client: int

    def __post_init__(self) -> None:
        if self.per_address < 1 or self.per_client < 1:
            raise ValueError('Each limit must allow at least one code an hour.')


@dataclass(frozen=True)
class CodeMessage:
    """The email that answers a request: its kind, to whom, in which language, and
    the code in it (None when it carries none)."""

    kind: MessageKind
    email: str
    language: Language
    code: str | None


@dataclass(frozen=True)
class SignedIn:
    user: User
    token: str
    expires_at: datetime
    created: bool


@dataclass(frozen=True)
class CurrentSession:
    user: User
    token_hash: str
    expires_at: datetime
    # Extended now, so the browser's cookie must be set again.
    renewed: bool


class SignIn:
    def __init__(
        self,
        store: AccountStore,
        secret: bytes,
        limits: Limits,
        clock: Callable[[], datetime],
    ) -> None:
        if len(secret) < 32:
            raise ValueError('The secret key must be at least 32 bytes.')
        self._store = store
        self._secret = secret
        self._limits = limits
        self._clock = clock

    def _hash(self, use: str, *parts: str) -> str:
        # Keyed, so a copy of the database alone cannot test guesses.
        message = '\x00'.join((use, *parts)).encode()
        return hmac.new(self._secret, message, hashlib.sha256).hexdigest()

    def request_code(
        self,
        email: str,
        purpose: Purpose,
        language: Language | None,
        page_language: Language,
        client: str,
    ) -> CodeMessage:
        """Makes and keeps a code when one is due, and says which email to send.

        Raises RecordError for an address that cannot be one, TooManyRequests at the
        hourly limits, and SignInError when an account is asked for without a
        language.
        """
        address = normalize_email(email)
        if purpose == 'create' and language is None:
            raise SignInError('Choose a language for the account.')
        now = self._clock()
        self._store.delete_expired(timestamp(now))
        allowed = self._store.allow_code_request(
            address,
            client,
            timestamp(now),
            timestamp(now - REQUEST_WINDOW),
            self._limits.per_address,
            self._limits.per_client,
        )
        if not allowed:
            raise TooManyRequests('Too many codes asked for. Try again within an hour.')
        user = self._store.user_by_email(address)
        if user is None and purpose == 'sign_in':
            return CodeMessage('no_account', address, page_language, None)
        code = f'{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}'
        self._store.put_code(
            SignInCode(
                email=address,
                code_hash=self._hash('code', address, code),
                new_language=None if user is not None else language,
                created_at=timestamp(now),
                expires_at=timestamp(now + CODE_LIFETIME),
                attempts=0,
            )
        )
        if user is None:
            if language is None:
                raise SignInError('Choose a language for the account.')
            return CodeMessage('create_code', address, language, code)
        kind: MessageKind = (
            'existing_account' if purpose == 'create' else 'sign_in_code'
        )
        return CodeMessage(kind, address, user.language, code)

    def redeem_code(self, email: str, code: str) -> SignedIn:
        """Signs in with the address's code, creating the account if the code was
        asked for to create one. Raises CodeRefused otherwise."""
        address = normalize_email(email)
        typed = _TYPED_CODE.sub('', code)
        if len(typed) != CODE_DIGITS or not typed.isascii() or not typed.isdigit():
            raise CodeRefused('That code is wrong or no longer works.')
        now = self._clock()
        taken = self._store.take_code(
            address, self._hash('code', address, typed), timestamp(now), CODE_TRIES
        )
        if taken is None:
            raise CodeRefused('That code is wrong or no longer works.')
        user = self._store.user_by_email(address)
        created = False
        if user is None:
            if taken.new_language is None:
                # Codes for unknown addresses are made only to create an account.
                raise CodeRefused('That code is wrong or no longer works.')
            try:
                user = self._store.create_user(address, taken.new_language)
                created = True
            except EmailTaken as exc:
                # Made meanwhile, from another tab with another code.
                user = self._store.user_by_email(address)
                if user is None:
                    # And deleted since: there is no account to sign in to.
                    raise CodeRefused('That code is wrong or no longer works.') from exc
        token = secrets.token_urlsafe(32)
        expires_at = now + SESSION_LIFETIME
        session = Session(
            token_hash=self._hash('session', token),
            user_id=user.id,
            created_at=timestamp(now),
            expires_at=timestamp(expires_at),
        )
        if not self._store.create_session(session):
            # The account was deleted meanwhile, taking its code's worth with it.
            raise CodeRefused('That code is wrong or no longer works.')
        return SignedIn(user=user, token=token, expires_at=expires_at, created=created)

    def current(self, token: str) -> CurrentSession | None:
        """The account a session token belongs to, or None. A session in its last
        half is extended to a full lifetime."""
        if not token or len(token) > SESSION_TOKEN_MAX_LENGTH:
            return None
        token_hash = self._hash('session', token)
        found = self._store.session_and_user(token_hash)
        if found is None:
            return None
        session, user = found
        now = self._clock()
        expires_at = parse_timestamp(session.expires_at)
        if expires_at <= now:
            # Only while it is still ended: another request may have renewed it.
            self._store.end_expired_session(token_hash, timestamp(now))
            return None
        renewed = expires_at - now < SESSION_RENEWAL
        if renewed:
            expires_at = now + SESSION_LIFETIME
            if not self._store.extend_session(
                token_hash, timestamp(expires_at), timestamp(now)
            ):
                # Signed out, or ended, meanwhile.
                return None
        return CurrentSession(
            user=user, token_hash=token_hash, expires_at=expires_at, renewed=renewed
        )

    def sign_out(self, token: str) -> None:
        if token and len(token) <= SESSION_TOKEN_MAX_LENGTH:
            self._store.delete_session(self._hash('session', token))

    def sign_out_everywhere(self, user_id: str) -> int:
        return self._store.delete_sessions(user_id)
