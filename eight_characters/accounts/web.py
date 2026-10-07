"""The account API: asking for a code, signing in and out, and the account itself.

Everything that differs between a laptop, CI and the server comes from environment
variables (see `load_config`); a missing or malformed one stops the app with the list
of what is wrong. Requests that change an account must come from the site's own
origin, and the session lives in an HttpOnly cookie the page's scripts cannot read.
"""

import logging
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parseaddr
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Final, Literal
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict
from typing_extensions import TypedDict

from eight_characters.accounts.mail import (
    DirectoryTransport,
    Mailer,
    MailError,
    SmtpTransport,
    render,
)
from eight_characters.accounts.person_check import (
    PersonCheck,
    PersonCheckUnavailable,
    Turnstile,
)
from eight_characters.accounts.records import (
    Language,
    RecordError,
    User,
    normalize_email,
    timestamp,
)
from eight_characters.accounts.signin import (
    REQUEST_WINDOW,
    CodeRefused,
    CurrentSession,
    Limits,
    Purpose,
    SignIn,
    SignInError,
    TooManyRequests,
)
from eight_characters.accounts.store import AccountStore, UnknownUser

logger = logging.getLogger(__name__)

SIGN_IN_REQUIRED: Final = 'Sign in to continue.'
_HEADER_NAME = re.compile(r'[A-Za-z0-9-]+')
_LOCAL_HOSTS: Final = frozenset({'localhost', '127.0.0.1', '::1'})


class ConfigError(Exception):
    """The environment does not describe a working account setup."""


@dataclass(frozen=True)
class AccountsConfig:
    origin: str
    database: Path
    secret_key: bytes
    mail_from: str
    mail: Literal['smtp', 'directory']
    smtp: tuple[str, int, str, str] | None
    mail_directory: Path | None
    turnstile_site_key: str
    turnstile_secret: str
    # The request header that carries the visitor's address; None for the socket's.
    client_ip_header: str | None
    limits: Limits

    @property
    def secure(self) -> bool:
        return self.origin.startswith('https://')

    @property
    def cookie_name(self) -> str:
        # The __Host- prefix makes browsers refuse the cookie from anywhere but this
        # exact host, over HTTPS; on a laptop's plain HTTP it cannot be used.
        return '__Host-ec_session' if self.secure else 'ec_session'


def _origin(value: str) -> str:
    parts = urlsplit(value)
    host = parts.hostname or ''
    secure = parts.scheme == 'https' and bool(host)
    local = parts.scheme == 'http' and host in _LOCAL_HOSTS
    if (
        not (secure or local)
        or parts.path
        or parts.query
        or parts.fragment
        or parts.username
        or parts.password
    ):
        raise ConfigError(
            'EC_APP_ORIGIN must be the site origin, like https://bazi.nektari.fi '
            '(plain http only for localhost), without a path or a trailing slash.'
        )
    return value


def _positive(env: Mapping[str, str], name: str, errors: list[str]) -> int:
    text = env.get(name, '')
    if not text.isdigit() or int(text) < 1:
        errors.append(f'{name} must be a whole number of at least 1.')
        return 1
    return int(text)


def load_config(env: Mapping[str, str]) -> AccountsConfig:
    """The account settings in `env`, or ConfigError naming everything wrong."""
    required = (
        'EC_APP_ORIGIN',
        'EC_DATABASE_PATH',
        'EC_SECRET_KEY',
        'EC_MAIL_FROM',
        'EC_MAIL_TRANSPORT',
        'EC_TURNSTILE_SITE_KEY',
        'EC_TURNSTILE_SECRET',
        'EC_CLIENT_IP_HEADER',
        'EC_CODE_REQUESTS_PER_HOUR_PER_ADDRESS',
        'EC_CODE_REQUESTS_PER_HOUR_PER_CLIENT',
    )
    transport = env.get('EC_MAIL_TRANSPORT', '')
    if transport == 'smtp':
        required += (
            'EC_SMTP_HOST',
            'EC_SMTP_PORT',
            'EC_SMTP_USERNAME',
            'EC_SMTP_PASSWORD',
        )
    elif transport == 'directory':
        required += ('EC_MAIL_DIRECTORY',)
    missing = [name for name in required if not env.get(name, '').strip()]
    if missing:
        raise ConfigError(f'Missing settings: {", ".join(missing)}.')
    errors: list[str] = []
    origin = ''
    try:
        origin = _origin(env['EC_APP_ORIGIN'])
    except ConfigError as exc:
        errors.append(str(exc))
    secret_key = env['EC_SECRET_KEY'].encode()
    if len(secret_key) < 32:
        errors.append('EC_SECRET_KEY must be at least 32 bytes.')
    mail_from = env['EC_MAIL_FROM']
    if '@' not in parseaddr(mail_from)[1]:
        errors.append(
            'EC_MAIL_FROM must hold an address, like BaZi <kirjaudu@nektari.fi>.'
        )
    if transport not in ('smtp', 'directory'):
        errors.append('EC_MAIL_TRANSPORT must be smtp or directory.')
    smtp: tuple[str, int, str, str] | None = None
    mail_directory: Path | None = None
    if transport == 'smtp':
        port = env['EC_SMTP_PORT']
        if not port.isdigit() or not 0 < int(port) < 65536:
            errors.append('EC_SMTP_PORT must be a port number.')
        else:
            smtp = (
                env['EC_SMTP_HOST'],
                int(port),
                env['EC_SMTP_USERNAME'],
                env['EC_SMTP_PASSWORD'],
            )
    elif transport == 'directory':
        mail_directory = Path(env['EC_MAIL_DIRECTORY'])
        if not mail_directory.is_dir():
            errors.append('EC_MAIL_DIRECTORY must be an existing folder.')
    header = env['EC_CLIENT_IP_HEADER']
    if header != 'peer' and _HEADER_NAME.fullmatch(header) is None:
        errors.append('EC_CLIENT_IP_HEADER must be a header name, or peer.')
    per_address = _positive(env, 'EC_CODE_REQUESTS_PER_HOUR_PER_ADDRESS', errors)
    per_client = _positive(env, 'EC_CODE_REQUESTS_PER_HOUR_PER_CLIENT', errors)
    if errors:
        raise ConfigError(' '.join(errors))
    return AccountsConfig(
        origin=origin,
        database=Path(env['EC_DATABASE_PATH']),
        secret_key=secret_key,
        mail_from=mail_from,
        mail='smtp' if transport == 'smtp' else 'directory',
        smtp=smtp,
        mail_directory=mail_directory,
        turnstile_site_key=env['EC_TURNSTILE_SITE_KEY'],
        turnstile_secret=env['EC_TURNSTILE_SECRET'],
        client_ip_header=None if header == 'peer' else header,
        limits=Limits(per_address=per_address, per_client=per_client),
    )


@dataclass(frozen=True)
class Accounts:
    """Everything the account API works with, made once from the settings."""

    config: AccountsConfig
    store: AccountStore
    sign_in: SignIn
    mailer: Mailer
    person_check: PersonCheck
    clock: Callable[[], datetime]

    @classmethod
    def open(
        cls,
        config: AccountsConfig,
        *,
        mailer: Mailer | None = None,
        person_check: PersonCheck | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> 'Accounts':
        now = clock or (lambda: datetime.now(UTC))
        store = AccountStore.open(config.database, clock=now)
        if mailer is None:
            if config.smtp is not None:
                mailer = SmtpTransport(*config.smtp)
            elif config.mail_directory is not None:
                mailer = DirectoryTransport(config.mail_directory)
            else:
                raise ConfigError('No way to send email is configured.')
        return cls(
            config=config,
            store=store,
            sign_in=SignIn(store, config.secret_key, config.limits, now),
            mailer=mailer,
            person_check=person_check
            or Turnstile(config.turnstile_secret, httpx.Client()),
            clock=now,
        )


@lru_cache(maxsize=1)
def accounts_from_environment() -> Accounts:
    return Accounts.open(load_config(os.environ))


def get_accounts() -> Accounts:
    """The account services, from the environment. Tests replace this dependency."""
    return accounts_from_environment()


AccountsDependency = Annotated[Accounts, Depends(get_accounts)]


def _set_session_cookie(
    response: Response, accounts: Accounts, token: str, expires_at: datetime
) -> None:
    response.set_cookie(
        accounts.config.cookie_name,
        token,
        max_age=max(0, int((expires_at - accounts.clock()).total_seconds())),
        path='/',
        secure=accounts.config.secure,
        httponly=True,
        samesite='lax',
    )


def _clear_session_cookie(response: Response, accounts: Accounts) -> None:
    response.delete_cookie(
        accounts.config.cookie_name,
        path='/',
        secure=accounts.config.secure,
        httponly=True,
        samesite='lax',
    )


def current_session(
    request: Request, response: Response, accounts: AccountsDependency
) -> CurrentSession | None:
    """The signed-in account, if any; a session in its second half is renewed."""
    token = request.cookies.get(accounts.config.cookie_name)
    if token is None:
        return None
    current = accounts.sign_in.current(token)
    if current is None:
        _clear_session_cookie(response, accounts)
    elif current.renewed:
        _set_session_cookie(response, accounts, token, current.expires_at)
    return current


SessionDependency = Annotated[CurrentSession | None, Depends(current_session)]


def _signed_in(current: CurrentSession | None) -> CurrentSession:
    if current is None:
        raise HTTPException(status_code=401, detail=SIGN_IN_REQUIRED)
    return current


def require_account(current: SessionDependency) -> User:
    """For what needs an account: the signed-in user, or 401."""
    return _signed_in(current).user


def _same_origin(request: Request, accounts: Accounts) -> None:
    # Browsers send Origin with every request that can change something; another
    # site's page cannot forge it.
    if request.headers.get('origin') != accounts.config.origin:
        raise HTTPException(
            status_code=403,
            detail='A request that changes an account must come from the site itself.',
        )


def _client(request: Request, accounts: Accounts) -> str:
    header = accounts.config.client_ip_header
    if header is None:
        if request.client is None:
            raise RuntimeError('The request has no client address.')
        return request.client.host
    value = request.headers.get(header, '').strip()
    if not value:
        # The proxy in front of the app sets it on every request; without it, the
        # limits per visitor would not hold.
        raise RuntimeError(f'The {header} header is missing.')
    return value


class AccountView(TypedDict):
    email: str
    language: Language
    plan: str
    created_at: str


def account_view(user: User) -> AccountView:
    """What the page is told of an account: never its id or a session."""
    return {
        'email': user.email,
        'language': user.language,
        'plan': user.plan,
        'created_at': user.created_at,
    }


class CodeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    email: str
    purpose: Purpose
    # The account's language; required when creating one.
    language: Literal['fi', 'en'] | None = None
    # The page's language, for an email to an address that has no account.
    page_language: Literal['fi', 'en']
    turnstile: str


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    email: str
    code: str


class LanguageRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    language: Literal['fi', 'en']


class DeleteRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    # The account's address, typed again to confirm.
    email: str


router = APIRouter(prefix='/api/account')


@router.post('/code', status_code=202)
def request_code(
    payload: CodeRequest, request: Request, accounts: AccountsDependency
) -> dict[str, bool]:
    """Sends a code, or word that the address has no account. The reply is the same
    either way."""
    _same_origin(request, accounts)
    client = _client(request, accounts)
    try:
        person = accounts.person_check.verify(payload.turnstile, client)
    except PersonCheckUnavailable as exc:
        logger.error('Turnstile could not be asked: %s', exc)
        raise HTTPException(
            status_code=503,
            detail='The check that you are a person is not answering. Try again in a minute.',
        ) from exc
    if not person:
        raise HTTPException(
            status_code=403,
            detail='The check that you are a person did not pass. Try again.',
        )
    try:
        message = accounts.sign_in.request_code(
            payload.email,
            payload.purpose,
            payload.language,
            payload.page_language,
            client,
        )
    except RecordError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TooManyRequests as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={'Retry-After': str(int(REQUEST_WINDOW.total_seconds()))},
        ) from exc
    except SignInError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        accounts.mailer.send(
            render(message, accounts.config.mail_from, accounts.config.origin)
        )
    except MailError as exc:
        logger.error('A sign-in email could not be sent: %s', exc)
        raise HTTPException(
            status_code=502,
            detail='The email could not be sent. Try again in a minute.',
        ) from exc
    return {'sent': True}


@router.post('/session')
def sign_in(
    payload: SessionRequest,
    request: Request,
    response: Response,
    accounts: AccountsDependency,
) -> AccountView:
    """Signs in with a code, creating the account if the code was asked for to
    create one, and sets the session cookie."""
    _same_origin(request, accounts)
    try:
        signed = accounts.sign_in.redeem_code(payload.email, payload.code)
    except (RecordError, CodeRefused) as exc:
        raise HTTPException(
            status_code=400, detail='That code is wrong or no longer works.'
        ) from exc
    _set_session_cookie(response, accounts, signed.token, signed.expires_at)
    return account_view(signed.user)


@router.get('')
def read_account(current: SessionDependency) -> AccountView:
    return account_view(_signed_in(current).user)


@router.patch('')
def update_account(
    payload: LanguageRequest,
    request: Request,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> AccountView:
    """Sets the account's language: the page's language after signing in, and the
    language of its emails."""
    _same_origin(request, accounts)
    user = _signed_in(current).user
    try:
        return account_view(accounts.store.set_language(user.id, payload.language))
    except UnknownUser as exc:
        # Deleted since the session was found.
        raise HTTPException(status_code=401, detail=SIGN_IN_REQUIRED) from exc


@router.delete('/session', status_code=204)
def sign_out(
    request: Request, response: Response, accounts: AccountsDependency
) -> None:
    _same_origin(request, accounts)
    token = request.cookies.get(accounts.config.cookie_name)
    if token is not None:
        accounts.sign_in.sign_out(token)
    _clear_session_cookie(response, accounts)


@router.delete('/sessions', status_code=204)
def sign_out_everywhere(
    request: Request,
    response: Response,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> None:
    _same_origin(request, accounts)
    accounts.sign_in.sign_out_everywhere(_signed_in(current).user.id)
    _clear_session_cookie(response, accounts)


@router.get('/export')
def export_account(
    response: Response, current: SessionDependency, accounts: AccountsDependency
) -> dict[str, Any]:
    """Everything kept for the account, as a JSON file. Returned as data, so a renewed
    session cookie goes out with it."""
    user = _signed_in(current).user
    try:
        data = accounts.store.account_data(user.id)
    except UnknownUser as exc:
        raise HTTPException(status_code=401, detail=SIGN_IN_REQUIRED) from exc
    response.headers['Content-Disposition'] = 'attachment; filename="bazi-account.json"'
    return {**data, 'exported_at': timestamp(accounts.clock())}


@router.delete('', status_code=204)
def delete_account(
    payload: DeleteRequest,
    request: Request,
    response: Response,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> None:
    """Deletes the account and its sessions; its file leaves the backup at the next
    run."""
    _same_origin(request, accounts)
    user = _signed_in(current).user
    try:
        typed = normalize_email(payload.email)
    except RecordError as exc:
        raise HTTPException(
            status_code=400, detail="Type the account's email address to delete it."
        ) from exc
    if typed != user.email:
        raise HTTPException(
            status_code=400, detail="Type the account's email address to delete it."
        )
    try:
        accounts.store.delete_user(user.id)
    except UnknownUser as exc:
        raise HTTPException(status_code=401, detail=SIGN_IN_REQUIRED) from exc
    _clear_session_cookie(response, accounts)
