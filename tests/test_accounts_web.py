import json
import shutil
import tempfile
import unittest
from datetime import timedelta
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from eight_characters.accounts.mail import MailError
from eight_characters.accounts.person_check import PersonCheckUnavailable
from eight_characters.accounts.store import AccountStore, StoreError
from eight_characters.accounts.web import (
    Accounts,
    ConfigError,
    get_accounts,
    load_config,
)
from eight_characters.main import app
from tests.accounts_support import (
    TEST_ORIGIN,
    Clock,
    FakePersonCheck,
    account_environment,
    code_in,
    mails_to,
)


class TestConfig(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory)

    def test_a_complete_setup(self) -> None:
        config = load_config(account_environment(self.directory))
        self.assertEqual(config.origin, TEST_ORIGIN)
        self.assertTrue(config.secure)
        self.assertEqual(config.cookie_name, '__Host-ec_session')
        self.assertEqual((config.limits.per_address, config.limits.per_client), (5, 20))
        self.assertIsNone(config.client_ip_header)

    def test_smtp(self) -> None:
        env = account_environment(
            self.directory,
            EC_MAIL_TRANSPORT='smtp',
            EC_SMTP_HOST='smtp.resend.com',
            EC_SMTP_PORT='465',
            EC_SMTP_USERNAME='resend',
            EC_SMTP_PASSWORD='key',
        )
        self.assertEqual(load_config(env).smtp, ('smtp.resend.com', 465, 'resend', 'key'))

    def test_local_http(self) -> None:
        for origin in ('http://localhost:8000', 'http://127.0.0.1:8123', 'http://[::1]:8000'):
            with self.subTest(origin):
                config = load_config(account_environment(self.directory, EC_APP_ORIGIN=origin))
                self.assertFalse(config.secure)
                self.assertEqual(config.cookie_name, 'ec_session')

    def test_missing_settings_are_named_together(self) -> None:
        env = account_environment(self.directory)
        del env['EC_SECRET_KEY'], env['EC_TURNSTILE_SECRET']
        with self.assertRaises(ConfigError) as caught:
            load_config(env)
        self.assertIn('EC_SECRET_KEY', str(caught.exception))
        self.assertIn('EC_TURNSTILE_SECRET', str(caught.exception))
        smtp = account_environment(self.directory, EC_MAIL_TRANSPORT='smtp')
        with self.assertRaises(ConfigError) as caught:
            load_config(smtp)
        self.assertIn('EC_SMTP_HOST', str(caught.exception))

    def test_malformed_settings_are_refused(self) -> None:
        for name, value in (
            ('EC_APP_ORIGIN', 'http://bazi.nektari.fi'),
            ('EC_APP_ORIGIN', 'https://bazi.nektari.fi/'),
            ('EC_APP_ORIGIN', 'https://bazi.nektari.fi/app'),
            ('EC_APP_ORIGIN', 'bazi.nektari.fi'),
            ('EC_SECRET_KEY', 'too short'),
            ('EC_MAIL_FROM', 'BaZi'),
            ('EC_MAIL_TRANSPORT', 'pigeon'),
            ('EC_MAIL_DIRECTORY', str(self.directory / 'missing')),
            ('EC_CLIENT_IP_HEADER', 'X Real IP'),
            ('EC_CODE_REQUESTS_PER_HOUR_PER_ADDRESS', '0'),
            ('EC_CODE_REQUESTS_PER_HOUR_PER_CLIENT', 'many'),
        ):
            with self.subTest(name=name, value=value), self.assertRaises(ConfigError):
                load_config(account_environment(self.directory, **{name: value}))

    def test_the_database_must_exist(self) -> None:
        config = load_config(account_environment(self.directory))
        with self.assertRaises(StoreError):
            Accounts.open(config, person_check=FakePersonCheck())


class AccountApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory)
        self.clock = Clock()
        self.person = FakePersonCheck()
        self.open_accounts()
        self.client = self.new_client()

    def open_accounts(self, **env: str) -> None:
        config = load_config(account_environment(self.directory, **env))
        if not config.database.exists():
            AccountStore.create(config.database)
        self.accounts = Accounts.open(config, person_check=self.person, clock=self.clock)
        app.dependency_overrides[get_accounts] = lambda: self.accounts
        self.addCleanup(app.dependency_overrides.pop, get_accounts, None)

    def new_client(self) -> TestClient:
        return TestClient(app, base_url=TEST_ORIGIN, headers={'Origin': TEST_ORIGIN})

    def ask(self, client: TestClient | None = None, **fields: Any) -> Any:
        payload = {
            'email': 'reader@example.com',
            'purpose': 'create',
            'language': 'fi',
            'page_language': 'en',
            'turnstile': 'token',
            **fields,
        }
        return (client or self.client).post('/api/account/code', json=payload)

    def sign_in(self, client: TestClient | None = None, email: str = 'reader@example.com', purpose: str = 'create') -> Any:
        self.assertEqual(self.ask(client, email=email, purpose=purpose).status_code, 202)
        code = code_in(mails_to(self.directory, email)[-1])
        return (client or self.client).post('/api/account/session', json={'email': email, 'code': code})


class TestAskingForACode(AccountApiTestCase):
    def test_the_same_reply_whoever_asks(self) -> None:
        self.accounts.store.create_user('member@example.com', 'en')
        replies = [
            self.ask(email='new@example.com'),
            self.ask(email='member@example.com', purpose='sign_in', language=None),
            self.ask(email='member@example.com'),
            self.ask(email='nobody@example.com', purpose='sign_in', language=None),
        ]
        self.assertEqual({(reply.status_code, reply.text) for reply in replies}, {(202, '{"sent":true}')})
        subjects = {
            address: mails_to(self.directory, address)[-1]['Subject']
            for address in ('new@example.com', 'nobody@example.com')
        }
        self.assertTrue(subjects['new@example.com'].startswith('Koodi tilisi luomiseen: '))
        self.assertEqual(subjects['nobody@example.com'], 'No BaZi account for this address')
        member = [message['Subject'] for message in mails_to(self.directory, 'member@example.com')]
        self.assertTrue(member[0].startswith('Your sign-in code: '))
        self.assertTrue(member[1].startswith('You already have an account. Your sign-in code: '))

    def test_the_person_check_comes_first(self) -> None:
        self.person.answer = False
        reply = self.ask()
        self.assertEqual(reply.status_code, 403)
        self.assertEqual(mails_to(self.directory, 'reader@example.com'), [])
        self.assertEqual(self.person.asked, [('token', 'testclient')])
        self.person.answer = PersonCheckUnavailable('down')
        self.assertEqual(self.ask().status_code, 503)

    def test_only_the_site_itself_may_ask(self) -> None:
        for headers in ({'Origin': 'https://elsewhere.example'}, {'Origin': ''}):
            with self.subTest(headers=headers):
                reply = self.client.post(
                    '/api/account/code',
                    json={'email': 'reader@example.com', 'purpose': 'create', 'language': 'fi', 'page_language': 'en', 'turnstile': 't'},
                    headers=headers,
                )
                self.assertEqual(reply.status_code, 403)
        self.assertEqual(self.person.asked, [])

    def test_malformed_requests(self) -> None:
        for fields in (
            {'email': 'not an address'},
            {'language': None},
            {'language': 'sv'},
            {'purpose': 'reset'},
            {'extra': True},
        ):
            with self.subTest(fields=fields):
                self.assertEqual(self.ask(**fields).status_code, 400)

    def test_the_hourly_limit(self) -> None:
        for _ in range(5):
            self.assertEqual(self.ask().status_code, 202)
        reply = self.ask()
        self.assertEqual(reply.status_code, 429)
        self.assertEqual(reply.headers['Retry-After'], '3600')

    def test_an_email_that_cannot_be_sent_says_so(self) -> None:
        class Broken:
            def send(self, message: object) -> None:
                raise MailError('down')

        self.accounts = Accounts.open(self.accounts.config, mailer=Broken(), person_check=self.person, clock=self.clock)
        self.assertEqual(self.ask().status_code, 502)

    def test_the_client_address_comes_from_the_configured_header(self) -> None:
        self.open_accounts(EC_CLIENT_IP_HEADER='X-Real-IP')
        self.assertEqual(self.client.post('/api/account/code', json={
            'email': 'reader@example.com', 'purpose': 'create', 'language': 'fi', 'page_language': 'en', 'turnstile': 't',
        }, headers={'X-Real-IP': '198.51.100.7'}).status_code, 202)
        self.assertEqual(self.person.asked[-1], ('t', '198.51.100.7'))
        with self.assertRaises(RuntimeError):
            self.ask()


class TestSigningIn(AccountApiTestCase):
    def test_a_code_creates_the_account_and_sets_a_private_cookie(self) -> None:
        reply = self.sign_in()
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(
            reply.json(),
            {'email': 'reader@example.com', 'language': 'fi', 'plan': 'free', 'created_at': '2026-10-07T12:00:00Z'},
        )
        cookie = SimpleCookie(reply.headers['set-cookie'])['__Host-ec_session']
        self.assertEqual(cookie['path'], '/')
        self.assertEqual(cookie['max-age'], str(int(timedelta(days=30).total_seconds())))
        self.assertTrue(cookie['secure'])
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'].lower(), 'lax')
        self.assertEqual(self.client.get('/api/account').json()['email'], 'reader@example.com')

    def test_a_wrong_code_is_refused(self) -> None:
        self.ask()
        code = code_in(mails_to(self.directory, 'reader@example.com')[-1])
        wrong = f'{(int(code) + 1) % 1_000_000:06d}'
        reply = self.client.post('/api/account/session', json={'email': 'reader@example.com', 'code': wrong})
        self.assertEqual((reply.status_code, reply.json()), (400, {'detail': 'That code is wrong or no longer works.'}))
        self.assertNotIn('set-cookie', reply.headers)

    def test_without_a_session(self) -> None:
        reply = self.client.get('/api/account')
        self.assertEqual((reply.status_code, reply.json()), (401, {'detail': 'Sign in to continue.'}))
        self.client.cookies.set('__Host-ec_session', 'forged', domain='testserver')
        self.assertEqual(self.client.get('/api/account').status_code, 401)

    def test_a_session_in_its_second_half_gets_a_fresh_cookie(self) -> None:
        self.sign_in()
        self.clock.advance(timedelta(days=10).total_seconds())
        self.assertNotIn('set-cookie', self.client.get('/api/account').headers)
        self.clock.advance(timedelta(days=6).total_seconds())
        reply = self.client.get('/api/account')
        self.assertEqual(reply.status_code, 200)
        self.assertIn('__Host-ec_session=', reply.headers['set-cookie'])

    def test_plain_http_on_a_laptop(self) -> None:
        self.open_accounts(EC_APP_ORIGIN='http://localhost:8000')
        client = TestClient(app, base_url='http://localhost:8000', headers={'Origin': 'http://localhost:8000'})
        reply = self.sign_in(client)
        self.assertIn('ec_session=', reply.headers['set-cookie'])
        self.assertNotIn('Secure', reply.headers['set-cookie'])
        self.assertEqual(client.get('/api/account').status_code, 200)


class TestTheAccount(AccountApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.assertEqual(self.sign_in().status_code, 200)

    def test_its_language_changes(self) -> None:
        reply = self.client.patch('/api/account', json={'language': 'en'})
        self.assertEqual((reply.status_code, reply.json()['language']), (200, 'en'))
        self.assertEqual(self.client.patch('/api/account', json={'language': 'sv'}).status_code, 400)
        self.assertEqual(
            self.client.patch('/api/account', json={'language': 'fi'}, headers={'Origin': 'https://elsewhere.example'}).status_code,
            403,
        )

    def test_signing_out(self) -> None:
        reply = self.client.delete('/api/account/session')
        self.assertEqual(reply.status_code, 204)
        self.assertIn('Max-Age=0', reply.headers['set-cookie'])
        self.assertEqual(self.client.get('/api/account').status_code, 401)

    def test_signing_out_everywhere(self) -> None:
        other = self.new_client()
        self.assertEqual(self.sign_in(other, purpose='sign_in').status_code, 200)
        self.assertEqual(self.client.delete('/api/account/sessions').status_code, 204)
        self.assertEqual(other.get('/api/account').status_code, 401)
        self.assertEqual(self.client.get('/api/account').status_code, 401)

    def test_its_data_downloads(self) -> None:
        reply = self.client.get('/api/account/export')
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.headers['content-disposition'], 'attachment; filename="bazi-account.json"')
        self.assertEqual(
            json.loads(reply.content),
            {
                'account': {'created_at': '2026-10-07T12:00:00Z', 'email': 'reader@example.com', 'language': 'fi', 'plan': 'free'},
                'exported_at': '2026-10-07T12:00:00Z',
            },
        )

    def test_deleting_needs_the_address_typed_again(self) -> None:
        for typed in ('other@example.com', 'not an address'):
            with self.subTest(typed):
                reply = self.client.request('DELETE', '/api/account', json={'email': typed})
                self.assertEqual(reply.status_code, 400)
        self.assertIsNotNone(self.accounts.store.user_by_email('reader@example.com'))
        reply = self.client.request('DELETE', '/api/account', json={'email': ' Reader@Example.com '})
        self.assertEqual(reply.status_code, 204)
        self.assertIsNone(self.accounts.store.user_by_email('reader@example.com'))
        self.assertEqual(self.client.get('/api/account').status_code, 401)

    def test_the_charts_need_no_account_yet(self) -> None:
        anonymous = TestClient(app)
        reply = anonymous.post('/api/hidden_stems', json={
            'year_pillar': '甲子', 'month_pillar': '乙丑', 'day_pillar': '丙寅', 'hour_pillar': '丁卯',
        })
        self.assertEqual(reply.status_code, 200)


if __name__ == '__main__':
    unittest.main()
