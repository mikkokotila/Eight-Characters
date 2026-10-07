"""The app's use of accounts: which requests need one, what the start page is told of
the signed-in account, and the settings checked when the app starts."""

import json
import os
import re
import shutil
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from eight_characters.accounts.records import User, timestamp
from eight_characters.accounts.signin import SESSION_LIFETIME
from eight_characters.accounts.store import AccountStore, Session, StoreError
from eight_characters.accounts.web import (
    SIGN_IN_REQUIRED,
    ConfigError,
    accounts_from_environment,
    require_account,
)
from eight_characters.main import app, templates
from tests.accounts_support import (
    TEST_ORIGIN,
    Clock,
    account_environment,
    install_accounts,
    sign_in,
    site_client,
)

SESSION_COOKIE = '__Host-ec_session'

# Every API request but the account's own: the charts, which need an account, and
# what the start page and the explorer use before anyone signs in.
NEEDS_ACCOUNT = {
    ('POST', '/api/chart'),
    ('POST', '/api/four_pillars'),
    ('POST', '/api/evolution_explorer'),
    ('POST', '/api/hidden_stems'),
}
OPEN = {
    ('POST', '/api/location_search'),
    ('POST', '/api/location_suggest'),
    ('GET', '/api/evolution_controls'),
}

ACCOUNT_STATE = re.compile(
    r'<script id="account-state" type="application/json">(.*?)</script>', re.S
)


class TestWhatNeedsAnAccount(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.accounts = install_accounts(cls)

    def test_every_api_request_is_open_or_needs_an_account(self) -> None:
        # A new request must be put on one list or the other.
        needs: set[tuple[str, str]] = set()
        open_: set[tuple[str, str]] = set()
        for route in app.routes:
            if not isinstance(route, APIRoute) or not route.path.startswith('/api/'):
                continue
            if route.path.startswith('/api/account'):
                continue
            gated = any(
                depends.dependency is require_account for depends in route.dependencies
            )
            for method in route.methods - {'HEAD'}:
                (needs if gated else open_).add((method, route.path))
        self.assertEqual(needs, NEEDS_ACCOUNT)
        self.assertEqual(open_, OPEN)

    def test_charts_answer_401_before_reading_the_request(self) -> None:
        anonymous = site_client()
        for method, path in sorted(NEEDS_ACCOUNT):
            with self.subTest(path):
                response = anonymous.request(method, path, json={})
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json(), {'detail': SIGN_IN_REQUIRED})

    def test_a_session_that_ended_gets_no_chart(self) -> None:
        client = site_client()
        sign_in(client, self.accounts, 'ended@example.com')
        token = client.cookies[SESSION_COOKIE]
        self.assertEqual(client.delete('/api/account/sessions').status_code, 204)
        stale = TestClient(app, base_url=TEST_ORIGIN, cookies={SESSION_COOKIE: token})
        response = stale.post('/api/hidden_stems', json={})
        self.assertEqual(response.status_code, 401)

    def test_open_requests_need_no_account(self) -> None:
        response = site_client().get('/api/evolution_controls')
        self.assertEqual(response.status_code, 200)


class TestTheStartPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.accounts = install_accounts(cls)

    def account_state(self, page: str) -> Any:
        match = ACCOUNT_STATE.search(page)
        if match is None:
            self.fail('The page names no account state.')
        return json.loads(match.group(1))

    def test_anyone_gets_the_start_page(self) -> None:
        response = site_client().get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.account_state(response.text))
        self.assertNotIn('set-cookie', response.headers)
        site_key = self.accounts.config.turnstile_site_key
        self.assertIn(f'data-site-key="{site_key}"', response.text)

    def test_no_shared_cache_keeps_the_page(self) -> None:
        response = site_client().get('/')
        self.assertEqual(response.headers['cache-control'], 'private, no-cache')

    def test_a_signed_in_page_names_its_account_and_nothing_secret(self) -> None:
        client = site_client()
        sign_in(client, self.accounts, 'reader@example.com')
        response = client.get('/')
        user = self.accounts.store.user_by_email('reader@example.com')
        if user is None:
            self.fail('Signing in made no account.')
        self.assertEqual(
            self.account_state(response.text),
            {
                'email': 'reader@example.com',
                'language': 'en',
                'plan': 'free',
                'created_at': user.created_at,
            },
        )
        self.assertNotIn(client.cookies[SESSION_COOKIE], response.text)
        self.assertNotIn(user.id, response.text)

    def test_an_address_cannot_break_out_of_the_page(self) -> None:
        # The state is JSON inside a script element: nothing an address may hold, and
        # an address may hold < and >, ends the element.
        email = '</script><script>alert(1)</script>@example.com'
        page = templates.get_template('index.html').render(
            account={
                'email': email,
                'language': 'en',
                'plan': 'free',
                'created_at': '2026-10-07T12:00:00Z',
            },
            turnstile_site_key='key',
            app_version='0',
            stem_options=[],
            branch_options=[],
        )
        self.assertNotIn('<script>alert(1)', page)
        self.assertEqual(self.account_state(page)['email'], email)

    def test_the_page_renews_a_session_in_its_second_half(self) -> None:
        client = site_client()
        sign_in(client, self.accounts, 'renewed@example.com')
        clock = cast(Clock, self.accounts.clock)
        clock.advance(timedelta(days=16).total_seconds())
        response = client.get('/')
        self.assertIsNotNone(self.account_state(response.text))
        cookie = response.headers['set-cookie']
        self.assertTrue(cookie.startswith(f'{SESSION_COOKIE}='), cookie)
        self.assertIn(f'Max-Age={int(timedelta(days=30).total_seconds())}', cookie)

    def test_a_page_crossing_the_end_of_a_session_renewed_meanwhile_keeps_it(
        self,
    ) -> None:
        # The page's request reads the session just before it ends; another request
        # renews it; the page's clock then passes the old end.
        client = site_client()
        sign_in(client, self.accounts, 'crossing@example.com')
        clock = cast(Clock, self.accounts.clock)
        clock.advance(SESSION_LIFETIME.total_seconds() - 1)
        store = self.accounts.store
        read = store.session_and_user
        renewals: list[str] = []

        def renewed_meanwhile(token_hash: str) -> tuple[Session, User] | None:
            found = read(token_hash)
            if not renewals:
                now = clock.now
                renewal = timestamp(now + SESSION_LIFETIME)
                self.assertTrue(
                    store.extend_session(token_hash, renewal, timestamp(now))
                )
                renewals.append(renewal)
                clock.advance(2)
            return found

        with patch.object(store, 'session_and_user', renewed_meanwhile):
            response = client.get('/')
        state = self.account_state(response.text)
        self.assertIsNotNone(state)
        cookie = response.headers['set-cookie']
        self.assertTrue(cookie.startswith(f'{SESSION_COOKIE}='), cookie)
        renewed_for = int(SESSION_LIFETIME.total_seconds()) - 2
        self.assertIn(f'Max-Age={renewed_for}', cookie)

    def test_a_page_with_an_ended_session_ends_its_cookie(self) -> None:
        client = site_client()
        sign_in(client, self.accounts, 'deleted@example.com')
        user = self.accounts.store.user_by_email('deleted@example.com')
        if user is None:
            self.fail('Signing in made no account.')
        self.accounts.store.delete_user(user.id)
        response = client.get('/')
        self.assertIsNone(self.account_state(response.text))
        cookie = response.headers['set-cookie']
        self.assertTrue(cookie.startswith(f'{SESSION_COOKIE}='), cookie)
        self.assertIn('Max-Age=0', cookie)


class TestStartingTheApp(unittest.TestCase):
    """The app reads its account settings and opens the database as it starts."""

    def setUp(self) -> None:
        accounts_from_environment.cache_clear()
        self.addCleanup(accounts_from_environment.cache_clear)
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory)
        # The rest of the environment stays, so only the account settings differ.
        self.base = {
            name: value
            for name, value in os.environ.items()
            if not name.startswith('EC_')
        }

    def start(self, env: dict[str, str]) -> None:
        with patch.dict(os.environ, env, clear=True):
            with TestClient(app, base_url=TEST_ORIGIN) as client:
                self.assertEqual(client.get('/').status_code, 200)

    def test_missing_settings_stop_the_app_at_start(self) -> None:
        with self.assertRaises(ConfigError) as caught:
            self.start(self.base)
        self.assertIn('EC_APP_ORIGIN', str(caught.exception))

    def test_a_missing_database_stops_the_app_at_start(self) -> None:
        with self.assertRaises(StoreError):
            self.start({**self.base, **account_environment(self.directory)})

    def test_complete_settings_start_the_app(self) -> None:
        env = account_environment(self.directory)
        AccountStore.create(Path(env['EC_DATABASE_PATH']))
        self.start({**self.base, **env})


if __name__ == '__main__':
    unittest.main()
