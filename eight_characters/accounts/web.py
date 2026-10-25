"""The account API: asking for a code, signing in and out, and the account itself.

Everything that differs between a laptop, CI and the server comes from environment
variables (see `load_config`); a missing or malformed one stops the app with the list
of what is wrong. Requests that change an account must come from the site's own
origin, and the session lives in an HttpOnly cookie the page's scripts cannot read.
"""

import copy
import hashlib
import hmac
import logging
import os
import re
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parseaddr
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Final, Literal, NotRequired, TypeVar
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi import Path as PathPart
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from typing_extensions import TypedDict

from eight_characters.accounts.billing import BillingError
from eight_characters.accounts.billing_access import (
    BillingBusy,
    BillingConfig,
    BillingHold,
    load_runtime_config,
)
from eight_characters.accounts.billing_native import Stripe
from eight_characters.accounts.billing_records import AccountBillingRecord
from eight_characters.accounts.billing_service import BillingService, PurchaseConflict
from eight_characters.accounts.billing_webhook import (
    MAX_BODY,
    InvalidDelivery,
    verify_delivery,
)
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
from eight_characters.accounts.plans import PlanLimits
from eight_characters.accounts.records import (
    DEFAULT_SCHOOLS,
    NO_CHOICE,
    Birth,
    ChosenSchools,
    Language,
    Place,
    RecordError,
    Schools,
    Settings,
    User,
    ZiConvention,
    check_name,
    normalize_email,
    place_value,
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
from eight_characters.accounts.store import (
    SCHEMA_VERSION,
    AccountStore,
    BillingReadOnly,
    ChartLimit,
    CoupleLimit,
    DuplicateChart,
    DuplicateCouple,
    SettingsChanged,
    UnknownChart,
    UnknownCouple,
    UnknownUser,
)
from eight_characters.first_chart import (
    ChartPillar,
    FirstChartInputError,
    PillarName,
)
from eight_characters.school_presets import (
    FavourableSchool,
    SeasonSchool,
    TransitSchool,
)
from eight_characters.time_convert import Gender
from eight_characters.today import TodayInputError, chart_birth

logger = logging.getLogger(__name__)

SIGN_IN_REQUIRED: Final = 'Sign in to continue.'
ACCOUNT_CHANGED: Final = 'This browser is signed in to another account now.'
# A settings write made from settings that changed since (412).
SETTINGS_CHANGED: Final = 'Your settings changed elsewhere since this page read them.'
# How long the browser keeps the session cookie: the longest browsers keep one
# (RFC 6265bis caps Max-Age at 400 days). Only signing in sets it. The session it
# names ends on the server 30 days after it was made or last extended, and is
# extended there when used in its second half.
SESSION_COOKIE_LIFETIME: Final = timedelta(days=400)
# A proxy the app trusts, such as another site's server passing requests on, names
# the visitor in PROXY_CLIENT_HEADER and proves itself with EC_PROXY_SECRET in
# PROXY_SECRET_HEADER. Its own address is the same for every visitor it serves.
PROXY_SECRET_HEADER: Final = 'X-EC-Proxy-Secret'
PROXY_CLIENT_HEADER: Final = 'X-EC-Client'
TOO_MANY_CHARTS: Final = 'Too many charts asked for. Try again within an hour.'
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
    # How many first charts a client may ask for in an hour, without an account.
    chart_requests_per_client: int
    # The secret a trusted proxy shows (see PROXY_SECRET_HEADER); None trusts none.
    proxy_secret: bytes | None
    billing: BillingConfig | None = None

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
            'EC_APP_ORIGIN must be the site origin, like https://my.eightchord.com '
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
        'EC_CHART_REQUESTS_PER_HOUR_PER_CLIENT',
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
            'EC_MAIL_FROM must hold an address, like Eight Chord <kirjaudu@nektari.fi>.'
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
    charts_per_client = _positive(env, 'EC_CHART_REQUESTS_PER_HOUR_PER_CLIENT', errors)
    # Optional: without it, no proxy is trusted, and one that names a client is refused.
    proxy_secret: bytes | None = None
    if 'EC_PROXY_SECRET' in env:
        proxy_secret = env['EC_PROXY_SECRET'].encode()
        if len(proxy_secret) < 32:
            errors.append('EC_PROXY_SECRET must be at least 32 bytes, or not set.')
    if errors:
        raise ConfigError(' '.join(errors))
    try:
        billing = load_runtime_config(env, session_secret=secret_key)
    except BillingError as exc:
        raise ConfigError(str(exc)) from None
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
        chart_requests_per_client=charts_per_client,
        proxy_secret=proxy_secret,
        billing=billing,
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
    billing: BillingService | None = None

    @classmethod
    def open(
        cls,
        config: AccountsConfig,
        *,
        mailer: Mailer | None = None,
        person_check: PersonCheck | None = None,
        clock: Callable[[], datetime] | None = None,
        billing_client: httpx.Client | None = None,
    ) -> 'Accounts':
        now = clock or (lambda: datetime.now(UTC))
        native = (
            None
            if config.billing is None
            else Stripe(
                config.billing,
                billing_client if billing_client is not None else httpx.Client(),
            )
        )
        store = AccountStore.open(
            config.database,
            clock=now,
            billing_config=config.billing,
            billing_clock=None if native is None else native.clock,
        )
        if store.schema_version() > SCHEMA_VERSION or (
            store.financially_managed() and config.billing is None
        ):
            raise ConfigError(
                'This release can recover schema-5 billing records but cannot serve '
                'financially managed accounts. Use the billing writer for account service.'
            )
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
            billing=None
            if native is None or config.billing is None
            else BillingService(
                store, config.billing, config.origin, native, clock=now
            ),
        )


@lru_cache(maxsize=1)
def accounts_from_environment() -> Accounts:
    return Accounts.open(load_config(os.environ))


def get_accounts() -> Accounts:
    """The account services, from the environment. Tests replace this dependency."""
    accounts = accounts_from_environment()
    # Another process may migrate the shared database after this service starts.
    # Even a session that needs no renewal must not serve legacy plan limits.
    if accounts.store.schema_version() > SCHEMA_VERSION or (
        accounts.store.financially_managed() and accounts.billing is None
    ):
        raise BillingReadOnly('This reader cannot serve financially managed accounts.')
    return accounts


AccountsDependency = Annotated[Accounts, Depends(get_accounts)]


def _set_session_cookie(response: Response, accounts: Accounts, token: str) -> None:
    response.set_cookie(
        accounts.config.cookie_name,
        token,
        max_age=int(SESSION_COOKIE_LIFETIME.total_seconds()),
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
    request: Request, accounts: AccountsDependency
) -> CurrentSession | None:
    """The signed-in account, if any; a session in its second half is extended, on
    the server. No answer here sets or removes the cookie: one arriving late could
    not tell whether the browser had signed out, or in again, meanwhile, and a cookie
    is set and removed by its name."""
    token = request.cookies.get(accounts.config.cookie_name)
    if token is None:
        return None
    return accounts.sign_in.current(token)


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


def client_of(request: Request, accounts: Accounts) -> str:
    """Who a request is from, for the limits per visitor.

    A proxy the app trusts names the visitor in PROXY_CLIENT_HEADER and shows the
    secret in PROXY_SECRET_HEADER. A request with either header that does not come
    from one is refused, so a misconfigured proxy fails at once instead of counting
    all its visitors as one, and nobody else can name a client of their choosing.
    Otherwise the address is the configured header's, or the socket's.
    """
    shown = request.headers.get(PROXY_SECRET_HEADER)
    named = request.headers.get(PROXY_CLIENT_HEADER)
    if shown is not None or named is not None:
        secret = accounts.config.proxy_secret
        if (
            shown is None
            or secret is None
            or not hmac.compare_digest(shown.encode(), secret)
        ):
            raise HTTPException(
                status_code=403,
                detail='Only a proxy this app trusts may name the client.',
            )
        if named is None or not named.strip():
            raise HTTPException(
                status_code=400,
                detail=f'A proxy must name the client in {PROXY_CLIENT_HEADER}.',
            )
        return named.strip()
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


def count_chart_request(request: Request, accounts: Accounts) -> None:
    """Counts a request for a first chart against its client's hourly limit, or
    refuses it with 429 when the client has made its limit."""
    client = client_of(request, accounts)
    now = accounts.clock()
    allowed = accounts.store.allow_chart_request(
        client,
        timestamp(now),
        timestamp(now - REQUEST_WINDOW),
        accounts.config.chart_requests_per_client,
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=TOO_MANY_CHARTS,
            headers={'Retry-After': str(int(REQUEST_WINDOW.total_seconds()))},
        )


class AccountView(TypedDict):
    email: str
    language: Language
    plan: str
    created_at: str
    updated_at: str
    key: str


_KEY: Final = re.compile('[0-9a-f]{64}')


def account_key(user: User) -> str:
    """The account's key: the same for its whole life, and another for an account
    made again with its address. A hash of its id, which no account answer carries."""
    return hashlib.sha256(user.id.encode()).hexdigest()


def account_view(user: User) -> AccountView:
    """What the page is told of an account: never its id or a session."""
    return {
        'email': user.email,
        'language': user.language,
        'plan': user.plan,
        'created_at': user.created_at,
        'updated_at': user.updated_at,
        'key': account_key(user),
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
    # The account the page names, by its key (see AccountRequest).
    key: str


class AccountRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    # The account the page names, by its key. Tabs share the session cookie, so another
    # tab may have signed in to another account since the page learned it, or deleted
    # it and made it again with its address; the action is then refused (409) and
    # changes nothing.
    key: str


class CheckoutRequest(AccountRequest):
    plan: Literal['basic', 'plus', 'pro']
    period: Literal['monthly', 'yearly']


class DeleteRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    # The account's address, typed again to confirm.
    email: str
    # The account the page names, by its key (see AccountRequest).
    key: str


class PlaceRequest(BaseModel):
    # A place as /api/location_suggest gives it, with the name the page shows for it.
    model_config = ConfigDict(extra='forbid', strict=True)

    name: str
    # The city alone, as a chart's link names it.
    city: str
    timezone: str
    latitude: float = Field(ge=-90.0, le=90.0, allow_inf_nan=False)
    longitude: float = Field(ge=-180.0, le=180.0, allow_inf_nan=False)


class BirthRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    # The account the page names, by its key (see AccountRequest).
    key: str
    # The settings the page read, by their `updated_at` (null: it read none).
    updated_at: str | None
    name: str | None = None
    date: str
    time: str
    place: PlaceRequest
    # Which pass of a time the clocks repeat: 0 the first, 1 the second.
    fold: int | None = Field(default=None, ge=0, le=1)
    gender: Gender
    # The Zi-hour convention the chart is drawn with, as its link carries it.
    zi: ZiConvention = 'split_midnight'


class BirthBody(BaseModel):
    # A birth sent with a request, as BirthRequest without the account's key.
    model_config = ConfigDict(extra='forbid', strict=True)

    name: str | None = None
    date: str
    time: str
    place: PlaceRequest
    fold: int | None = Field(default=None, ge=0, le=1)
    gender: Gender
    zi: ZiConvention = 'split_midnight'


class HereRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    key: str
    updated_at: str | None
    place: PlaceRequest


class SettingsRequest(BaseModel):
    # Removing a setting: the account named by its key, and the settings read.
    model_config = ConfigDict(extra='forbid', strict=True)

    key: str
    updated_at: str | None


# A saved chart's or a couple's id: 32 lowercase hex digits (records.new_id).
ID_PATTERN: Final = r'^[0-9a-f]{32}$'
ChartId = Annotated[str, PathPart(pattern=ID_PATTERN)]


class NewChartRequest(BirthRequest):
    # Saving a birth may, in the same write, mark it as the person's own, or pair it
    # with one of the saved charts: a failure then leaves neither.
    mine: bool = False
    couple_with: str | None = Field(default=None, pattern=ID_PATTERN)


class NameRequest(BaseModel):
    # A saved chart's new name, or null to leave it unnamed.
    model_config = ConfigDict(extra='forbid', strict=True)

    key: str
    updated_at: str | None
    name: str | None


class MyChartRequest(BaseModel):
    # Which saved chart is the person's own, by its id.
    model_config = ConfigDict(extra='forbid', strict=True)

    key: str
    updated_at: str | None
    chart: str = Field(pattern=ID_PATTERN)


class CoupleRequest(BaseModel):
    # Two saved charts to pair, by their ids.
    model_config = ConfigDict(extra='forbid', strict=True)

    key: str
    updated_at: str | None
    charts: list[Annotated[str, Field(pattern=ID_PATTERN)]] = Field(
        min_length=2, max_length=2
    )


class SchoolsRequest(BaseModel):
    # Each school left out stays as it is; one sent as null follows the default again.
    model_config = ConfigDict(extra='forbid', strict=True)

    key: str
    updated_at: str | None
    favourable: FavourableSchool | None = None
    season: SeasonSchool | None = None
    transits: TransitSchool | None = None


class ChartView(TypedDict):
    name: str | None
    date: str
    time: str
    place: dict[str, Any]
    fold: int | None
    gender: Gender
    zi: ZiConvention
    # The chart's four pillars, as /api/four_pillars gives them; None, with the
    # reason in `problem`, if the engine no longer charts it (a time zone update can
    # make its clock time one the clocks skipped or repeated).
    pillars: dict[PillarName, ChartPillar] | None
    problem: str | None


class SavedChartView(ChartView):
    id: str


class CoupleView(TypedDict):
    id: str
    # The two charts, by their ids, in the order the couple was formed.
    charts: list[str]


class BillingView(TypedDict):
    tier: str
    status: str
    paid_through: int | None
    reason: str | None


class NamedBillingView(BillingView):
    key: str


class SettingsView(TypedDict):
    # The charts the account keeps, in the order they were saved: a new one comes
    # last. Each with its pillars, as a partner's chart had them.
    charts: list[SavedChartView]
    # The person's own chart, by its id; None until one is marked.
    my_chart: str | None
    couples: list[CoupleView]
    # A partner's chart kept from before accounts kept charts: it pairs with the
    # person's own chart when one is first marked.
    pending_partner: str | None
    # The write allowance; null means unlimited. Reads retain over-limit charts.
    chart_limit: int | None
    # How many couples one saved chart may be in on the account's plan; None for no
    # cap (plans.py).
    couples_per_chart: int | None
    place: dict[str, Any] | None
    # The school Today follows for each setting, and the one chosen: None where the
    # account follows the default.
    schools: dict[str, str]
    chosen: dict[str, str | None]
    # When the settings last changed; None for an account that has set nothing.
    updated_at: str | None
    key: str
    billing: NotRequired[BillingView]


class SavedReply(SettingsView):
    # The id the chart was just saved under.
    saved: str


def _not_cached(response: Response) -> None:
    """The account API answers with the account's own data: no cache may keep it."""
    response.headers['Cache-Control'] = 'no-store'


router = APIRouter(prefix='/api/account', dependencies=[Depends(_not_cached)])
provider_router = APIRouter()


def _billing(accounts: Accounts) -> BillingService:
    if accounts.billing is None:
        raise HTTPException(status_code=503, detail='Sandbox billing is not enabled.')
    return accounts.billing


def _capacity_view(
    accounts: Accounts, user: User
) -> tuple[BillingView | None, PlanLimits]:
    try:
        access, limits = accounts.store.capacity(user.id)
    except BillingHold as exc:
        if accounts.billing is None:
            raise
        # Preserve retained-library reads/edits while billing cannot make an
        # addition decision. The store still refuses additions until verified.
        return BillingView(
            tier='free', status='held', paid_through=None, reason=exc.reason
        ), PlanLimits(accounts.store.limits(user.plan).couples_per_chart, 1)
    if access is None:
        return None, limits
    return BillingView(
        tier=access.tier,
        status=access.status,
        paid_through=access.paid_through,
        reason=access.reason,
    ), limits


def _settings_reply(
    accounts: Accounts, user: User, settings: Settings | None
) -> SettingsView:
    billing, limits = _capacity_view(accounts, user)
    reply = settings_view(user, settings, limits)
    if billing is not None:
        reply['billing'] = billing
    return reply


@router.get('/billing')
def read_billing_status(
    current: SessionDependency, accounts: AccountsDependency
) -> NamedBillingView:
    user = _signed_in(current).user
    _billing(accounts)
    billing, _ = _capacity_view(accounts, user)
    if billing is None:
        raise BillingHold('unverified')
    return {**billing, 'key': account_key(user)}


@router.post('/billing/checkout')
def create_billing_checkout(
    payload: CheckoutRequest,
    request: Request,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> dict[str, object]:
    _same_origin(request, accounts)
    user = _signed_in(current).user
    _named(user, payload.key)
    try:
        return _billing(accounts).checkout(user.id, payload.plan, payload.period)
    except PurchaseConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.post('/billing/cancel')
def cancel_billing_renewal(
    payload: AccountRequest,
    request: Request,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> NamedBillingView:
    _same_origin(request, accounts)
    user = _signed_in(current).user
    _named(user, payload.key)
    _billing(accounts).cancel(user.id)
    billing, _ = _capacity_view(accounts, user)
    if billing is None:
        raise BillingHold('unverified')
    return {**billing, 'key': account_key(user)}


@provider_router.get('/account/billing/return')
def billing_return(
    current: SessionDependency, accounts: AccountsDependency
) -> RedirectResponse:
    user = _signed_in(current).user
    service = _billing(accounts)
    headers = {'Cache-Control': 'no-store'}
    try:
        service.reconcile(user.id)
    except BillingBusy:
        # The current owner worker retains the only apply fence. Returning to
        # account status cannot grant the unconfirmed payment in the query.
        headers['Retry-After'] = str(service.config.poll_seconds)
    return RedirectResponse(
        accounts.config.origin + '/',
        status_code=303,
        headers=headers,
    )


@provider_router.post('/api/billing/stripe/webhook', status_code=202)
async def stripe_webhook(
    request: Request, accounts: AccountsDependency
) -> dict[str, str]:
    service = _billing(accounts)
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_BODY:
            raise HTTPException(status_code=413, detail='Invalid Stripe delivery.')
        raw.extend(chunk)
    try:
        delivery = verify_delivery(
            bytes(raw),
            request.headers.get('Stripe-Signature'),
            service.config,
            wall_time=int(accounts.clock().timestamp()),
        )
    except InvalidDelivery as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from None
    try:
        event = await run_in_threadpool(service.authority.enqueue, delivery)
    except (sqlite3.Error, BillingHold):
        raise HTTPException(
            status_code=503, detail='Billing delivery could not be committed.'
        ) from None
    return {'status': event.state}


def _named(user: User, key: str) -> None:
    """An action is for the account the page names, by its key: if the session
    belongs to another one now, or to an account made again with the address,
    nothing is done."""
    if _KEY.fullmatch(key) is None:
        raise HTTPException(status_code=400, detail='The account named is not a key.')
    if key != account_key(user):
        raise HTTPException(status_code=409, detail=ACCOUNT_CHANGED)


@router.post('/code', status_code=202)
def request_code(
    payload: CodeRequest, request: Request, accounts: AccountsDependency
) -> dict[str, bool]:
    """Sends a code, or word that the address has no account. The reply is the same
    either way."""
    _same_origin(request, accounts)
    client = client_of(request, accounts)
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
    _set_session_cookie(response, accounts, signed.token)
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
    _named(user, payload.key)
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
    payload: AccountRequest,
    request: Request,
    response: Response,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> None:
    _same_origin(request, accounts)
    user = _signed_in(current).user
    _named(user, payload.key)
    if accounts.sign_in.sign_out_everywhere(user.id) == 0:
        # Not even this session was left: the account went meanwhile (deleted in
        # another tab), as PATCH, export and delete answer then.
        raise HTTPException(status_code=401, detail=SIGN_IN_REQUIRED)
    _clear_session_cookie(response, accounts)


@router.post('/export')
def export_account(
    payload: AccountRequest,
    request: Request,
    response: Response,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> dict[str, Any]:
    """Everything kept for the account, as a JSON file. What has passed its time is
    dropped first, so the file holds what the account keeps, and no request older
    than the hour. The account is named in the body, not the address, which servers
    log."""
    _same_origin(request, accounts)
    user = _signed_in(current).user
    _named(user, payload.key)
    accounts.sign_in.sweep()
    try:
        data = accounts.store.account_data(user.id)
    except UnknownUser as exc:
        raise HTTPException(status_code=401, detail=SIGN_IN_REQUIRED) from exc
    response.headers['Content-Disposition'] = (
        'attachment; filename="eight-chord-account.json"'
    )
    exported = {**data, 'exported_at': timestamp(accounts.clock())}
    if accounts.billing is not None:
        billing, _ = _capacity_view(accounts, user)
        owner = next(
            (
                record
                for record in accounts.store.billing_records()
                if isinstance(record, AccountBillingRecord)
                and record.id == user.id
                and record.lifecycle != 'deleted'
            ),
            None,
        )
        exported['billing'] = {
            'status': billing,
            'customer_id': None if owner is None else owner.customer_id,
            'invoices': []
            if owner is None
            else [
                {
                    'invoice_id': fact.invoice_id,
                    'charge_id': fact.charge_id,
                    'subscription_id': fact.subscription_id,
                }
                for fact in owner.coverage
            ],
        }
    return exported


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
    _named(user, payload.key)
    try:
        typed = normalize_email(payload.email)
    except RecordError as exc:
        raise HTTPException(
            status_code=400, detail='Type the account’s email address to delete it.'
        ) from exc
    if typed != user.email:
        raise HTTPException(
            status_code=400, detail='Type the account’s email address to delete it.'
        )
    if accounts.billing is not None:
        if accounts.billing.delete(user.id):
            _clear_session_cookie(response, accounts)
        else:
            response.status_code = 202
        return
    try:
        accounts.store.delete_user(user.id)
    except UnknownUser as exc:
        raise HTTPException(status_code=401, detail=SIGN_IN_REQUIRED) from exc
    _clear_session_cookie(response, accounts)


# ── Settings for Today ──


def place_of(request: PlaceRequest) -> Place:
    return Place(
        name=request.name,
        city=request.city,
        timezone=request.timezone,
        # A whole number is a float here: the record writes coordinates as floats.
        latitude=float(request.latitude),
        longitude=float(request.longitude),
    )


def birth_of(request: BirthRequest | BirthBody) -> Birth:
    """The birth a request names, checked by the first chart's rules and charted:
    RecordError, FirstChartInputError or TodayInputError if it cannot be."""
    birth = Birth(
        name=request.name,
        date=request.date,
        time=request.time,
        place=place_of(request.place),
        fold=request.fold,
        gender=request.gender,
        zi=request.zi,
    )
    chart_birth(birth)
    return birth


def charted(birth: Birth) -> dict[PillarName, ChartPillar]:
    """The birth's four pillars, by the engine, with its own Zi-hour convention."""
    return chart_birth(birth).chart()


# How many saved births' charts a process keeps: every answer about the settings
# shows each saved chart's pillars, at about 25 ms of engine time each.
CHARTED_KEPT: Final = 1024


@lru_cache(maxsize=CHARTED_KEPT)
def _charted_or_problem(
    birth: Birth,
) -> tuple[dict[PillarName, ChartPillar] | None, str | None]:
    """A saved birth's four pillars, or why the engine no longer charts it. The engine
    gives a birth the same chart every time under the pinned time zone data, so it is
    charted once per process."""
    try:
        return charted(birth), None
    except TodayInputError as exc:
        # Shown with the chart, so the page can ask for its time again; Today
        # refuses the chart with the same reason.
        return None, str(exc)


def _chart_view(birth: Birth) -> ChartView:
    kept, problem = _charted_or_problem(birth)
    # A copy: what the cache keeps is never handed out to be changed.
    pillars = copy.deepcopy(kept)
    return {
        'name': birth.name,
        'date': birth.date,
        'time': birth.time,
        'place': place_value(birth.place),
        'fold': birth.fold,
        'gender': birth.gender,
        'zi': birth.zi,
        'pillars': pillars,
        'problem': problem,
    }


def _schools_view(schools: Schools) -> dict[str, str]:
    return {
        'favourable': schools.favourable,
        'season': schools.season,
        'transits': schools.transits,
    }


def _chosen_view(chosen: ChosenSchools) -> dict[str, str | None]:
    return {
        'favourable': chosen.favourable,
        'season': chosen.season,
        'transits': chosen.transits,
    }


def settings_view(
    user: User, settings: Settings | None, limits: PlanLimits
) -> SettingsView:
    """What the page is told of the account's settings, each saved chart with its
    pillars, and what the account's plan lets it keep; the defaults when it has set
    nothing."""
    if settings is None:
        return {
            'charts': [],
            'my_chart': None,
            'couples': [],
            'pending_partner': None,
            'chart_limit': limits.charts_per_account,
            'couples_per_chart': limits.couples_per_chart,
            'place': None,
            'schools': _schools_view(DEFAULT_SCHOOLS),
            'chosen': _chosen_view(NO_CHOICE),
            'updated_at': None,
            'key': account_key(user),
        }
    return {
        'charts': [
            {**_chart_view(chart.birth), 'id': chart.id} for chart in settings.charts
        ],
        'my_chart': settings.my_chart,
        'couples': [
            {'id': couple.id, 'charts': list(couple.charts)}
            for couple in settings.couples
        ],
        'pending_partner': settings.pending_partner,
        'chart_limit': limits.charts_per_account,
        'couples_per_chart': limits.couples_per_chart,
        'place': None if settings.place is None else place_value(settings.place),
        'schools': _schools_view(settings.schools.effective()),
        'chosen': _chosen_view(settings.schools),
        'updated_at': settings.updated_at,
        'key': account_key(user),
    }


_Changed = TypeVar('_Changed')


def _store_change(change: Callable[[], _Changed]) -> _Changed:
    """Makes a change to the settings; one the store refuses is the page's answer."""
    try:
        return change()
    except UnknownUser as exc:
        # Deleted since the session was found.
        raise HTTPException(status_code=401, detail=SIGN_IN_REQUIRED) from exc
    except SettingsChanged as exc:
        # Changed in another tab or browser: the page reads them again.
        raise HTTPException(status_code=412, detail=SETTINGS_CHANGED) from exc
    except (UnknownChart, UnknownCouple) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ChartLimit, CoupleLimit, DuplicateChart, DuplicateCouple) as exc:
        # Not 409: the page reads a 409 as another account signed in meanwhile.
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _changed(
    accounts: Accounts, user: User, change: Callable[[], Settings | None]
) -> SettingsView:
    return _settings_reply(accounts, user, _store_change(change))


@router.get('/settings')
def read_settings(
    current: SessionDependency, accounts: AccountsDependency
) -> SettingsView:
    """Your saved charts, your own among them, your couples, where you are, and your
    schools."""
    user = _signed_in(current).user
    return _settings_reply(accounts, user, accounts.store.settings(user.id))


@router.post('/charts', status_code=201)
def save_chart(
    payload: NewChartRequest,
    request: Request,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> SavedReply:
    """Keeps a chart in your library, after the last, and says the id it is kept
    under; in the same write, it can become your own chart, or be paired with one of
    your saved charts. It is checked as a first chart with its time is, and charted
    before it is kept. A birth is saved once."""
    _same_origin(request, accounts)
    user = _signed_in(current).user
    _named(user, payload.key)
    try:
        birth = birth_of(payload)
    except (RecordError, FirstChartInputError, TodayInputError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    settings, chart_id = _store_change(
        lambda: accounts.store.save_chart(
            user.id,
            birth,
            payload.updated_at,
            mine=payload.mine,
            couple_with=payload.couple_with,
        )
    )
    return SavedReply(
        **_settings_reply(accounts, user, settings),
        saved=chart_id,
    )


@router.put('/charts/{chart_id}')
def change_chart(
    chart_id: ChartId,
    payload: BirthRequest,
    request: Request,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> SettingsView:
    """Changes a saved chart's name or birth. It keeps its id, and its place as your
    own chart or in a couple."""
    _same_origin(request, accounts)
    user = _signed_in(current).user
    _named(user, payload.key)
    try:
        birth = birth_of(payload)
    except (RecordError, FirstChartInputError, TodayInputError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _changed(
        accounts,
        user,
        lambda: accounts.store.update_chart(
            user.id, chart_id, birth, payload.updated_at
        ),
    )


@router.put('/charts/{chart_id}/name')
def rename_chart(
    chart_id: ChartId,
    payload: NameRequest,
    request: Request,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> SettingsView:
    """Renames a saved chart, or leaves it unnamed. Its birth is not charted again."""
    _same_origin(request, accounts)
    user = _signed_in(current).user
    _named(user, payload.key)
    try:
        check_name(payload.name)
    except RecordError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _changed(
        accounts,
        user,
        lambda: accounts.store.rename_chart(
            user.id, chart_id, payload.name, payload.updated_at
        ),
    )


@router.delete('/charts/{chart_id}')
def delete_chart(
    chart_id: ChartId,
    payload: SettingsRequest,
    request: Request,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> SettingsView:
    """Removes a chart from your library: it leaves its couple, and stops being your
    own."""
    _same_origin(request, accounts)
    user = _signed_in(current).user
    _named(user, payload.key)
    return _changed(
        accounts,
        user,
        lambda: accounts.store.delete_chart(user.id, chart_id, payload.updated_at),
    )


@router.put('/my-chart')
def mark_my_chart(
    payload: MyChartRequest,
    request: Request,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> SettingsView:
    """Marks one of your saved charts as your own: signing in opens it."""
    _same_origin(request, accounts)
    user = _signed_in(current).user
    _named(user, payload.key)
    return _changed(
        accounts,
        user,
        lambda: accounts.store.set_my_chart(user.id, payload.chart, payload.updated_at),
    )


@router.delete('/my-chart')
def unmark_my_chart(
    payload: SettingsRequest,
    request: Request,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> SettingsView:
    """No saved chart is your own any more; the chart stays in your library."""
    _same_origin(request, accounts)
    user = _signed_in(current).user
    _named(user, payload.key)
    return _changed(
        accounts,
        user,
        lambda: accounts.store.clear_my_chart(user.id, payload.updated_at),
    )


@router.post('/couples', status_code=201)
def pair_charts(
    payload: CoupleRequest,
    request: Request,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> SettingsView:
    """Pairs two of your saved charts as a couple. A chart can be in any number of
    couples, as many as your plan allows; the same two charts are one couple."""
    _same_origin(request, accounts)
    user = _signed_in(current).user
    _named(user, payload.key)
    if payload.charts[0] == payload.charts[1]:
        raise HTTPException(status_code=400, detail='A couple is two different charts.')
    return _changed(
        accounts,
        user,
        lambda: accounts.store.add_couple(
            user.id, (payload.charts[0], payload.charts[1]), payload.updated_at
        ),
    )


@router.delete('/couples/{couple_id}')
def part_couple(
    couple_id: ChartId,
    payload: SettingsRequest,
    request: Request,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> SettingsView:
    """Parts a couple; both charts stay in your library."""
    _same_origin(request, accounts)
    user = _signed_in(current).user
    _named(user, payload.key)
    return _changed(
        accounts,
        user,
        lambda: accounts.store.delete_couple(user.id, couple_id, payload.updated_at),
    )


@router.put('/place')
def save_place(
    payload: HereRequest,
    request: Request,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> SettingsView:
    """Keeps where you are: the place Today's hours are reckoned for."""
    _same_origin(request, accounts)
    user = _signed_in(current).user
    _named(user, payload.key)
    try:
        place = place_of(payload.place)
    except RecordError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _changed(
        accounts,
        user,
        lambda: accounts.store.put_place(user.id, place, payload.updated_at),
    )


@router.delete('/place')
def delete_place(
    payload: SettingsRequest,
    request: Request,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> SettingsView:
    """Forgets where you are, if it is kept."""
    _same_origin(request, accounts)
    user = _signed_in(current).user
    _named(user, payload.key)
    return _changed(
        accounts, user, lambda: accounts.store.delete_place(user.id, payload.updated_at)
    )


@router.patch('/schools')
def choose_schools(
    payload: SchoolsRequest,
    request: Request,
    current: SessionDependency,
    accounts: AccountsDependency,
) -> SettingsView:
    """Chooses the school for any of Today's three settings (GET /api/schools)."""
    _same_origin(request, accounts)
    user = _signed_in(current).user
    _named(user, payload.key)
    chosen: dict[str, str | None] = {
        name: getattr(payload, name)
        for name in ('favourable', 'season', 'transits')
        if name in payload.model_fields_set
    }
    return _changed(
        accounts,
        user,
        lambda: accounts.store.set_schools(user.id, chosen, payload.updated_at),
    )
