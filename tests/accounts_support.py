"""Shared set-up for the account tests: a fixed clock, Git remotes and checkouts."""

import email
import re
import shutil
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.policy import default
from pathlib import Path

from fastapi.testclient import TestClient

from eight_characters.accounts.store import AccountStore
from eight_characters.accounts.web import Accounts, get_accounts, load_config
from eight_characters.main import app

# Commits the tests make by hand carry an identity of their own, so no global Git
# configuration is needed.
COMMITTER = (
    '-c',
    'user.name=Test',
    '-c',
    'user.email=test@example.invalid',
    '-c',
    'commit.gpgsign=false',
)


class Clock:
    """A clock the test moves by hand."""

    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 10, 7, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ('git', '-C', str(root), *COMMITTER, *args),
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f'git {" ".join(args)} failed: {completed.stderr.decode(errors="replace")}'
        )
    return completed.stdout.decode()


def make_remote_and_checkout(base: Path) -> tuple[Path, Path]:
    """An empty bare repository and a clone of it, as a new backup starts."""
    remote = base / 'remote.git'
    checkout = base / 'checkout'
    subprocess.run(('git', 'init', '--quiet', '--bare', str(remote)), check=True)
    subprocess.run(
        ('git', 'clone', '--quiet', str(remote), str(checkout)),
        check=True,
        capture_output=True,
    )
    return remote, checkout


def all_object_contents(repository: Path) -> bytes:
    """Every object in a repository, decompressed, so a search sees what Git stores."""
    return subprocess.run(
        ('git', '-C', str(repository), 'cat-file', '--batch-all-objects', '--batch'),
        capture_output=True,
        check=True,
    ).stdout


# ── The account API ──

TEST_ORIGIN = 'https://testserver'
TEST_SECRET = 'a test secret that is at least 32 bytes long'


class FakePersonCheck:
    """Answers Turnstile's question as told, and remembers what it was asked."""

    def __init__(self, answer: bool | Exception = True) -> None:
        self.answer = answer
        self.asked: list[tuple[str, str | None]] = []

    def verify(self, token: str, client: str | None) -> bool:
        self.asked.append((token, client))
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def account_environment(directory: Path, **changes: str) -> dict[str, str]:
    """A complete account setup in `directory`: its database and a mail folder."""
    mail = directory / 'mail'
    mail.mkdir(exist_ok=True)
    env = {
        'EC_APP_ORIGIN': TEST_ORIGIN,
        'EC_DATABASE_PATH': str(directory / 'accounts.sqlite3'),
        'EC_SECRET_KEY': TEST_SECRET,
        'EC_MAIL_FROM': 'BaZi <kirjaudu@example.com>',
        'EC_MAIL_TRANSPORT': 'directory',
        'EC_MAIL_DIRECTORY': str(mail),
        'EC_TURNSTILE_SITE_KEY': '1x00000000000000000000AA',
        'EC_TURNSTILE_SECRET': '1x0000000000000000000000000000000AA',
        'EC_CLIENT_IP_HEADER': 'peer',
        'EC_CODE_REQUESTS_PER_HOUR_PER_ADDRESS': '5',
        'EC_CODE_REQUESTS_PER_HOUR_PER_CLIENT': '20',
        'EC_CHART_REQUESTS_PER_HOUR_PER_CLIENT': '30',
    }
    env.update(changes)
    return env


def mails_to(directory: Path, address: str) -> list[EmailMessage]:
    """The messages the mail folder holds for an address, oldest first."""
    found: list[EmailMessage] = []
    for path in sorted((directory / 'mail').glob('*.eml')):
        message = email.message_from_bytes(path.read_bytes(), policy=default)
        if isinstance(message, EmailMessage) and message['To'] == address:
            found.append(message)
    return found


def code_in(message: EmailMessage) -> str:
    match = re.search(r'(\d{3}) (\d{3})$', str(message['Subject']))
    if match is None:
        raise AssertionError(f'No code in: {message["Subject"]}')
    return match.group(1) + match.group(2)


def install_accounts(case: type[unittest.TestCase], **changes: str) -> Accounts:
    """A fresh account database and services, in place of the app's own for as long
    as the test class runs; `changes` alter its settings."""
    directory = Path(tempfile.mkdtemp())
    case.addClassCleanup(shutil.rmtree, directory)
    config = load_config(account_environment(directory, **changes))
    AccountStore.create(config.database)
    accounts = Accounts.open(config, person_check=FakePersonCheck(), clock=Clock())
    app.dependency_overrides[get_accounts] = lambda: accounts
    case.addClassCleanup(app.dependency_overrides.pop, get_accounts, None)
    return accounts


def sign_in(client: TestClient, accounts: Accounts, email: str) -> None:
    """Signs `client` in to a new account, the way the page does: a code asked for,
    read from the mail folder and sent back."""
    asked = client.post(
        '/api/account/code',
        json={
            'email': email,
            'purpose': 'create',
            'language': 'en',
            'page_language': 'en',
            'turnstile': 'token',
        },
    )
    if asked.status_code != 202:
        raise AssertionError(f'Asking for a code failed: {asked.text}')
    folder = accounts.config.mail_directory
    if folder is None:
        raise AssertionError('The test accounts send no mail to a folder.')
    code = code_in(mails_to(folder.parent, email)[-1])
    signed = client.post('/api/account/session', json={'email': email, 'code': code})
    if signed.status_code != 200:
        raise AssertionError(f'Signing in failed: {signed.text}')


def site_client() -> TestClient:
    """A browser on the site: its requests carry the site's own origin."""
    return TestClient(app, base_url=TEST_ORIGIN, headers={'Origin': TEST_ORIGIN})


def signed_in_client(
    case: type[unittest.TestCase], email: str = 'tester@example.com'
) -> TestClient:
    """A client signed in to a new account, in account services of its own for as
    long as the test class runs."""
    accounts = install_accounts(case)
    client = site_client()
    sign_in(client, accounts, email)
    return client
