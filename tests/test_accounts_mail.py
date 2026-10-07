import email
import json
import shutil
import smtplib
import ssl
import tempfile
import unittest
from email.message import EmailMessage
from email.policy import default
from pathlib import Path
from typing import get_args
from unittest.mock import MagicMock, patch

import httpx

from eight_characters.accounts.mail import (
    TEXTS,
    DirectoryTransport,
    MailError,
    SmtpTransport,
    readable_code,
    render,
)
from eight_characters.accounts.person_check import (
    SITEVERIFY_URL,
    PersonCheckUnavailable,
    Turnstile,
)
from eight_characters.accounts.records import LANGUAGES
from eight_characters.accounts.signin import CodeMessage, MessageKind

SENDER = 'BaZi <kirjaudu@nektari.fi>'
ORIGIN = 'https://bazi.nektari.fi'


class TestMessages(unittest.TestCase):
    def test_every_kind_has_both_languages(self) -> None:
        expected = {
            (kind, language) for kind in get_args(MessageKind) for language in LANGUAGES
        }
        self.assertEqual(set(TEXTS), expected)

    def test_messages_carry_the_code_the_site_and_their_headers(self) -> None:
        for kind, language in TEXTS:
            code = None if kind == 'no_account' else '482913'
            with self.subTest(kind=kind, language=language):
                message = render(
                    CodeMessage(kind, 'reader@example.com', language, code),
                    SENDER,
                    ORIGIN,
                )
                body = message.get_content()
                self.assertEqual(message['From'], SENDER)
                self.assertEqual(message['To'], 'reader@example.com')
                self.assertEqual(message['Auto-Submitted'], 'auto-generated')
                self.assertTrue(message['Message-ID'].endswith('@nektari.fi>'))
                self.assertIn(ORIGIN, body)
                self.assertNotIn('{', body + message['Subject'])
                if code is None:
                    self.assertNotRegex(body, r'\d{3} \d{3}')
                else:
                    self.assertIn('482 913', message['Subject'])
                    self.assertIn('    482 913\n', body)
                    self.assertIn('10', body)

    def test_finnish_letters_survive_the_trip(self) -> None:
        message = render(
            CodeMessage('no_account', 'reader@example.com', 'fi', None), SENDER, ORIGIN
        )
        parsed = email.message_from_bytes(bytes(message), policy=default)
        self.assertEqual(parsed['Subject'], 'Tällä osoitteella ei ole BaZi-tiliä')
        body = parsed.get_body()
        assert body is not None
        self.assertIn('yritettiin kirjautua', body.get_content())

    def test_readable_codes(self) -> None:
        self.assertEqual(readable_code('012345'), '012 345')


class TestTransports(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory)
        self.message = render(
            CodeMessage('sign_in_code', 'reader@example.com', 'en', '123456'),
            SENDER,
            ORIGIN,
        )

    def test_a_folder_keeps_each_message_in_order(self) -> None:
        transport = DirectoryTransport(self.directory)
        transport.send(self.message)
        second = EmailMessage()
        second['Subject'] = 'second'
        transport.send(second)
        files = sorted(self.directory.iterdir())
        self.assertEqual([path.suffix for path in files], ['.eml', '.eml'])
        first = email.message_from_bytes(files[0].read_bytes(), policy=default)
        self.assertEqual(first['Subject'], 'Your sign-in code: 123 456')
        self.assertEqual(
            email.message_from_bytes(files[1].read_bytes(), policy=default)['Subject'],
            'second',
        )

    def test_a_missing_folder_is_refused(self) -> None:
        with self.assertRaises(MailError):
            DirectoryTransport(self.directory / 'missing')

    def test_smtp_signs_in_over_tls_and_sends(self) -> None:
        with patch.object(smtplib, 'SMTP_SSL') as smtp_ssl:
            server = MagicMock()
            smtp_ssl.return_value.__enter__.return_value = server
            SmtpTransport('smtp.resend.com', 465, 'resend', 'secret').send(self.message)
        args, kwargs = smtp_ssl.call_args
        self.assertEqual(args, ('smtp.resend.com', 465))
        self.assertIsInstance(kwargs['context'], ssl.SSLContext)
        server.login.assert_called_once_with('resend', 'secret')
        server.send_message.assert_called_once_with(self.message)

    def test_smtp_failures_become_mail_errors(self) -> None:
        for failure in (
            smtplib.SMTPAuthenticationError(535, b'no'),
            smtplib.SMTPRecipientsRefused({}),
            TimeoutError(),
            ConnectionRefusedError(),
        ):
            with (
                self.subTest(type(failure).__name__),
                patch.object(smtplib, 'SMTP_SSL') as smtp_ssl,
            ):
                smtp_ssl.return_value.__enter__.return_value.send_message.side_effect = failure
                with self.assertRaises(MailError) as caught:
                    SmtpTransport('smtp.resend.com', 465, 'resend', 'secret').send(
                        self.message
                    )
                self.assertNotIn('secret', str(caught.exception))


class TestTurnstile(unittest.TestCase):
    def check(self, handler: httpx.MockTransport) -> Turnstile:
        return Turnstile('the-secret', httpx.Client(transport=handler))

    def test_asks_cloudflare_with_the_secret_the_token_and_the_client(self) -> None:
        seen: list[httpx.Request] = []

        def answer(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json={'success': True})

        self.assertTrue(
            self.check(httpx.MockTransport(answer)).verify('token', '192.0.2.1')
        )
        self.assertEqual(str(seen[0].url), SITEVERIFY_URL)
        form = dict(httpx.QueryParams(seen[0].content.decode()))
        self.assertEqual(
            form, {'secret': 'the-secret', 'response': 'token', 'remoteip': '192.0.2.1'}
        )

    def test_a_failed_check_is_false(self) -> None:
        check = self.check(
            httpx.MockTransport(lambda _: httpx.Response(200, json={'success': False}))
        )
        self.assertFalse(check.verify('token', None))

    def test_empty_or_oversized_tokens_fail_without_asking(self) -> None:
        def never(_: httpx.Request) -> httpx.Response:
            raise AssertionError('Cloudflare was asked.')

        check = self.check(httpx.MockTransport(never))
        self.assertFalse(check.verify('', None))
        self.assertFalse(check.verify('x' * 3000, None))

    def test_no_verdict_is_unavailable_not_a_pass(self) -> None:
        def unreachable(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError('down', request=request)

        for handler in (
            unreachable,
            lambda _: httpx.Response(500),
            lambda _: httpx.Response(200, content=b'not json'),
            lambda _: httpx.Response(200, json=['success']),
            lambda _: httpx.Response(200, json={'error-codes': []}),
        ):
            with (
                self.subTest(handler=handler),
                self.assertRaises(PersonCheckUnavailable),
            ):
                self.check(httpx.MockTransport(handler)).verify('token', None)

    def test_a_verdict_must_be_true_itself(self) -> None:
        for verdict in ('true', 1, None):
            with self.subTest(verdict=verdict):
                body = json.dumps({'success': verdict}).encode()
                check = self.check(
                    httpx.MockTransport(
                        lambda _, body=body: httpx.Response(200, content=body)
                    )
                )
                self.assertFalse(check.verify('token', None))


if __name__ == '__main__':
    unittest.main()
