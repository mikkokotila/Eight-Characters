"""The emails sign-in sends, in Finnish and English, and the ways to send them.

Plain text only: a code, what it is for, how long it works, and what to do if it was
not asked for. The site's address comes from the configured origin, never from the
code.
"""

import os
import secrets
import smtplib
import ssl
import tempfile
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from pathlib import Path
from typing import Final, Protocol

from eight_characters.accounts.records import Language
from eight_characters.accounts.signin import CODE_LIFETIME, CodeMessage, MessageKind

SMTP_TIMEOUT_SECONDS: Final = 20.0
_MINUTES: Final = int(CODE_LIFETIME.total_seconds() // 60)

# (subject, body) for each kind and language. {code} and {origin} are filled in.
TEXTS: Final[dict[tuple[MessageKind, Language], tuple[str, str]]] = {
    ('sign_in_code', 'en'): (
        'Your sign-in code: {code}',
        'Your sign-in code for BaZi is\n\n'
        '    {code}\n\n'
        f"It works once, for {_MINUTES} minutes. If you didn't ask for it, you can "
        'ignore this email: no one can sign in without the code.\n\n'
        '{origin}\n',
    ),
    ('sign_in_code', 'fi'): (
        'Kirjautumiskoodisi: {code}',
        'Kirjautumiskoodisi BaZiin on\n\n'
        '    {code}\n\n'
        f'Koodi toimii kerran ja {_MINUTES} minuutin ajan. Jos et pyytänyt sitä, '
        'voit jättää tämän viestin huomiotta: ilman koodia kukaan ei pääse '
        'kirjautumaan.\n\n'
        '{origin}\n',
    ),
    ('create_code', 'en'): (
        'Your code to create your account: {code}',
        'Enter this code on BaZi to create your account:\n\n'
        '    {code}\n\n'
        f"It works once, for {_MINUTES} minutes. If you didn't ask for an account, "
        'you can ignore this email: nothing is created without the code.\n\n'
        '{origin}\n',
    ),
    ('create_code', 'fi'): (
        'Koodi tilisi luomiseen: {code}',
        'Luo tilisi BaZiin syöttämällä tämä koodi:\n\n'
        '    {code}\n\n'
        f'Koodi toimii kerran ja {_MINUTES} minuutin ajan. Jos et pyytänyt tiliä, '
        'voit jättää tämän viestin huomiotta: ilman koodia tiliä ei luoda.\n\n'
        '{origin}\n',
    ),
    ('existing_account', 'en'): (
        'You already have an account. Your sign-in code: {code}',
        'Someone asked to create a BaZi account with this address, but it already '
        'has one. To sign in, enter this code:\n\n'
        '    {code}\n\n'
        f"It works once, for {_MINUTES} minutes. If you didn't ask for it, you can "
        'ignore this email.\n\n'
        '{origin}\n',
    ),
    ('existing_account', 'fi'): (
        'Sinulla on jo tili. Kirjautumiskoodisi: {code}',
        'Tällä osoitteella pyydettiin uutta BaZi-tiliä, mutta osoitteella on jo '
        'tili. Kirjaudu syöttämällä tämä koodi:\n\n'
        '    {code}\n\n'
        f'Koodi toimii kerran ja {_MINUTES} minuutin ajan. Jos et pyytänyt sitä, '
        'voit jättää tämän viestin huomiotta.\n\n'
        '{origin}\n',
    ),
    ('no_account', 'en'): (
        'No BaZi account for this address',
        'Someone asked to sign in to BaZi with this address, but there is no '
        'account for it. To create one, go to {origin} and choose Create account.\n\n'
        "If you didn't ask, you can ignore this email.\n",
    ),
    ('no_account', 'fi'): (
        'Tällä osoitteella ei ole BaZi-tiliä',
        'Tällä osoitteella yritettiin kirjautua BaZiin, mutta osoitteella ei ole '
        'tiliä. Luo tili osoitteessa {origin} valitsemalla Luo tili.\n\n'
        'Jos et yrittänyt kirjautua, voit jättää tämän viestin huomiotta.\n',
    ),
}


class MailError(Exception):
    """The email could not be handed on for delivery."""


class Mailer(Protocol):
    def send(self, message: EmailMessage) -> None: ...


def readable_code(code: str) -> str:
    """Six digits as two groups of three, easier to read and type."""
    return f'{code[:3]} {code[3:]}'


def render(message: CodeMessage, sender: str, origin: str) -> EmailMessage:
    subject, body = TEXTS[(message.kind, message.language)]
    shown = '' if message.code is None else readable_code(message.code)
    email = EmailMessage()
    email['From'] = sender
    email['To'] = message.email
    email['Subject'] = subject.format(code=shown)
    email['Date'] = formatdate(usegmt=True)
    domain = parseaddr(sender)[1].rpartition('@')[2]
    email['Message-ID'] = make_msgid(domain=domain or None)
    # An automated message: out-of-office replies should not answer it.
    email['Auto-Submitted'] = 'auto-generated'
    email.set_content(body.format(code=shown, origin=origin))
    return email


class SmtpTransport:
    """Sends over SMTP with TLS from the first byte (port 465), as Resend offers."""

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password

    def send(self, message: EmailMessage) -> None:
        try:
            with smtplib.SMTP_SSL(
                self._host,
                self._port,
                timeout=SMTP_TIMEOUT_SECONDS,
                context=ssl.create_default_context(),
            ) as smtp:
                smtp.login(self._username, self._password)
                smtp.send_message(message)
        except (smtplib.SMTPException, OSError) as exc:
            raise MailError(
                f'The email server refused or failed ({type(exc).__name__}).'
            ) from exc


class DirectoryTransport:
    """Writes each message as a .eml file into a folder: for running the app on a
    computer of one's own, and for its tests. Nothing is delivered."""

    def __init__(self, directory: Path) -> None:
        if not directory.is_dir():
            raise MailError(f'The mail folder {directory} does not exist.')
        self._directory = directory

    def send(self, message: EmailMessage) -> None:
        # Named by when it was sent, so the folder lists messages in order.
        final = self._directory / f'{time.time_ns():020d}-{secrets.token_hex(4)}.eml'
        try:
            descriptor, name = tempfile.mkstemp(
                dir=self._directory, prefix='.', suffix='.tmp'
            )
        except OSError as exc:
            # A full or unwritable folder is a message not sent, like a refused one.
            raise MailError(f'Writing to {self._directory} failed: {exc}') from exc
        try:
            with os.fdopen(descriptor, 'wb') as handle:
                handle.write(bytes(message))
            os.replace(name, final)
        except OSError as exc:
            Path(name).unlink(missing_ok=True)
            raise MailError(f'Writing to {self._directory} failed: {exc}') from exc
        except BaseException:
            Path(name).unlink(missing_ok=True)
            raise
