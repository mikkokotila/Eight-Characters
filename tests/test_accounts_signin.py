import shutil
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from eight_characters.accounts.records import Language, RecordError, User
from eight_characters.accounts.signin import (
    CODE_LIFETIME,
    SESSION_LIFETIME,
    CodeMessage,
    CodeRefused,
    Limits,
    Purpose,
    SignIn,
    SignInError,
    TooManyRequests,
)
from eight_characters.accounts.store import AccountStore, EmailTaken
from tests.accounts_support import Clock

SECRET = b'a test secret that is long enough!!'


class SignInTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory)
        self.clock = Clock()
        self.store = AccountStore.create(
            self.directory / 'accounts.sqlite3', clock=self.clock
        )
        self.sign_in = SignIn(
            self.store, SECRET, Limits(per_address=5, per_client=20), self.clock
        )

    def ask(
        self,
        email: str = 'reader@example.com',
        purpose: Purpose = 'create',
        language: Language | None = 'fi',
        page_language: Language = 'en',
        client: str = '192.0.2.1',
    ) -> CodeMessage:
        return self.sign_in.request_code(
            email, purpose, language, page_language, client
        )


class TestAskingForCodes(SignInTestCase):
    def test_a_new_address_gets_a_code_that_creates_the_account(self) -> None:
        message = self.ask('  New@Example.COM ', 'create', 'fi')
        self.assertEqual(
            (message.kind, message.email, message.language),
            ('create_code', 'new@example.com', 'fi'),
        )
        assert message.code is not None
        self.assertRegex(message.code, r'^\d{6}$')
        stored = self.store.code('new@example.com')
        assert stored is not None
        self.assertEqual(stored.new_language, 'fi')
        self.assertNotIn(message.code, stored.code_hash)
        self.assertIsNone(self.store.user_by_email('new@example.com'))

    def test_creating_needs_a_language(self) -> None:
        with self.assertRaises(SignInError):
            self.ask(language=None)
        self.assertIsNone(self.store.code('reader@example.com'))

    def test_an_existing_account_gets_a_sign_in_code_in_its_own_language(self) -> None:
        self.store.create_user('reader@example.com', 'en')
        for purpose, kind in (
            ('sign_in', 'sign_in_code'),
            ('create', 'existing_account'),
        ):
            with self.subTest(purpose):
                message = self.ask(purpose=purpose, language='fi', page_language='fi')
                self.assertEqual((message.kind, message.language), (kind, 'en'))
                self.assertIsNotNone(message.code)
                stored = self.store.code('reader@example.com')
                assert stored is not None
                self.assertIsNone(stored.new_language)

    def test_signing_in_without_an_account_sends_word_in_the_page_language(
        self,
    ) -> None:
        message = self.ask('nobody@example.com', 'sign_in', None, 'fi')
        self.assertEqual(
            (message.kind, message.language, message.code), ('no_account', 'fi', None)
        )
        self.assertIsNone(self.store.code('nobody@example.com'))

    def test_refuses_what_cannot_be_an_address(self) -> None:
        with self.assertRaises(RecordError):
            self.ask('not an address')

    def test_codes_are_limited_per_address_and_per_client(self) -> None:
        for _ in range(5):
            self.ask('limited@example.com', client=f'client-{_}')
        with self.assertRaises(TooManyRequests):
            self.ask('limited@example.com', client='another')
        # An hour after the first, the address may ask again.
        self.clock.advance(3601)
        self.ask('limited@example.com')

    def test_codes_are_limited_per_client(self) -> None:
        for n in range(20):
            self.ask(f'u{n}@example.com', client='one')
        with self.assertRaises(TooManyRequests):
            self.ask('another@example.com', client='one')
        self.ask('another@example.com', client='two')


class TestRedeemingCodes(SignInTestCase):
    def code_for(
        self,
        email: str = 'reader@example.com',
        purpose: Purpose = 'create',
        language: Language | None = 'fi',
    ) -> str:
        message = self.ask(email, purpose, language)
        assert message.code is not None
        return message.code

    def test_the_first_code_creates_the_account_in_its_language(self) -> None:
        code = self.code_for('reader@example.com', 'create', 'en')
        signed = self.sign_in.redeem_code(
            'Reader@Example.com', f'{code[:3]} {code[3:]}'
        )
        self.assertTrue(signed.created)
        self.assertEqual(
            (signed.user.email, signed.user.language, signed.user.plan),
            ('reader@example.com', 'en', 'free'),
        )
        self.assertEqual(signed.expires_at, self.clock.now + SESSION_LIFETIME)
        current = self.sign_in.current(signed.token)
        assert current is not None
        self.assertEqual(current.user, signed.user)

    def test_signing_in_does_not_create(self) -> None:
        user = self.store.create_user('reader@example.com', 'fi')
        signed = self.sign_in.redeem_code(
            'reader@example.com', self.code_for('reader@example.com', 'sign_in', None)
        )
        self.assertEqual((signed.user, signed.created), (user, False))

    def test_an_account_deleted_while_signing_in_gets_no_session(self) -> None:
        user = self.store.create_user('reader@example.com', 'fi')
        code = self.code_for('reader@example.com', 'sign_in', None)
        found = self.store.user_by_email

        def deleted_meanwhile(email: str) -> User | None:
            account = found(email)
            self.store.delete_user(user.id)
            return account

        with (
            patch.object(self.store, 'user_by_email', deleted_meanwhile),
            self.assertRaises(CodeRefused),
        ):
            self.sign_in.redeem_code('reader@example.com', code)

    def test_an_account_made_and_deleted_while_creating_it_gets_no_session(
        self,
    ) -> None:
        # Another tab made the account with another code, and it was deleted before
        # this one could sign in to it.
        code = self.code_for('reader@example.com', 'create', 'fi')
        create = self.store.create_user

        def made_and_deleted_meanwhile(email: str, language: Language) -> User:
            self.store.delete_user(create(email, language).id)
            raise EmailTaken('An account with that email address exists already.')

        with (
            patch.object(self.store, 'create_user', made_and_deleted_meanwhile),
            self.assertRaises(CodeRefused),
        ):
            self.sign_in.redeem_code('reader@example.com', code)
        self.assertIsNone(self.store.user_by_email('reader@example.com'))

    def test_a_code_works_once(self) -> None:
        code = self.code_for()
        self.sign_in.redeem_code('reader@example.com', code)
        with self.assertRaises(CodeRefused):
            self.sign_in.redeem_code('reader@example.com', code)

    def test_a_code_expires(self) -> None:
        code = self.code_for()
        self.clock.advance(CODE_LIFETIME.total_seconds())
        with self.assertRaises(CodeRefused):
            self.sign_in.redeem_code('reader@example.com', code)
        self.assertIsNone(self.store.user_by_email('reader@example.com'))

    def test_five_wrong_tries_end_the_code(self) -> None:
        code = self.code_for()
        wrong = f'{(int(code) + 1) % 1_000_000:06d}'
        for _ in range(5):
            with self.assertRaises(CodeRefused):
                self.sign_in.redeem_code('reader@example.com', wrong)
        with self.assertRaises(CodeRefused):
            self.sign_in.redeem_code('reader@example.com', code)

    def test_a_new_code_replaces_the_last(self) -> None:
        first = self.code_for()
        second = self.code_for()
        if first != second:
            with self.assertRaises(CodeRefused):
                self.sign_in.redeem_code('reader@example.com', first)
        self.sign_in.redeem_code('reader@example.com', second)

    def test_refuses_anything_but_six_digits(self) -> None:
        self.code_for()
        for typed in (
            '',
            '12345',
            '1234567',
            'abcdef',
            '\uff11\uff12\uff13\uff14\uff15\uff16',
        ):
            with self.subTest(typed), self.assertRaises(CodeRefused):
                self.sign_in.redeem_code('reader@example.com', typed)

    def test_a_code_belongs_to_its_address(self) -> None:
        code = self.code_for('reader@example.com')
        self.code_for('other@example.com')
        with self.assertRaises(CodeRefused):
            self.sign_in.redeem_code('other@example.com', code)

    def test_another_secret_knows_no_code_or_session(self) -> None:
        code = self.code_for()
        other = SignIn(
            self.store,
            b'another secret, also long enough!!!',
            Limits(5, 20),
            self.clock,
        )
        with self.assertRaises(CodeRefused):
            other.redeem_code('reader@example.com', code)
        signed = self.sign_in.redeem_code('reader@example.com', self.code_for())
        self.assertIsNone(other.current(signed.token))

    def test_a_short_secret_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            SignIn(self.store, b'short', Limits(5, 20), self.clock)


class TestSessions(SignInTestCase):
    def setUp(self) -> None:
        super().setUp()
        message = self.ask('reader@example.com', 'create', 'fi')
        assert message.code is not None
        self.signed = self.sign_in.redeem_code('reader@example.com', message.code)

    def test_unknown_or_malformed_tokens_find_nothing(self) -> None:
        for token in ('', 'unknown', 'x' * 500):
            with self.subTest(token=token[:10]):
                self.assertIsNone(self.sign_in.current(token))

    def test_a_session_in_its_second_half_is_renewed(self) -> None:
        self.clock.advance(timedelta(days=10).total_seconds())
        current = self.sign_in.current(self.signed.token)
        assert current is not None
        self.assertFalse(current.renewed)
        self.clock.advance(timedelta(days=6).total_seconds())
        current = self.sign_in.current(self.signed.token)
        assert current is not None
        self.assertTrue(current.renewed)
        self.assertEqual(current.expires_at, self.clock.now + SESSION_LIFETIME)

    def test_a_session_unused_for_its_lifetime_ends(self) -> None:
        self.clock.advance(SESSION_LIFETIME.total_seconds())
        self.assertIsNone(self.sign_in.current(self.signed.token))

    def test_signing_out(self) -> None:
        self.sign_in.sign_out(self.signed.token)
        self.assertIsNone(self.sign_in.current(self.signed.token))

    def test_signing_out_everywhere(self) -> None:
        message = self.ask('reader@example.com', 'sign_in', None)
        assert message.code is not None
        second = self.sign_in.redeem_code('reader@example.com', message.code)
        self.assertEqual(self.sign_in.sign_out_everywhere(self.signed.user.id), 2)
        self.assertIsNone(self.sign_in.current(second.token))

    def test_a_deleted_account_has_no_session(self) -> None:
        self.store.delete_user(self.signed.user.id)
        self.assertIsNone(self.sign_in.current(self.signed.token))


if __name__ == '__main__':
    unittest.main()
