import json
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

from eight_characters.accounts.records import (
    EMAIL_MAX_LENGTH,
    RecordError,
    User,
    decode_user,
    encode_user,
    is_id,
    new_id,
    normalize_email,
    timestamp,
    user_path,
)

USER = User(
    id='3f9c2a7d0b8e4c51a6f2d9e0b7c4a1e5',
    email='reader@example.com',
    language='fi',
    plan='free',
    created_at='2026-10-07T12:00:00Z',
    updated_at='2026-10-07T12:30:00Z',
)


class TestIdsAndTimes(unittest.TestCase):
    def test_new_ids_are_random_hex(self) -> None:
        ids = {new_id() for _ in range(1000)}
        self.assertEqual(len(ids), 1000)
        self.assertTrue(all(is_id(value) for value in ids))

    def test_is_id_refuses_anything_else(self) -> None:
        for value in (
            '',
            '3F9C2A7D0B8E4C51A6F2D9E0B7C4A1E5',
            'g' * 32,
            'a' * 31,
            'a' * 33,
        ):
            self.assertFalse(is_id(value), value)

    def test_timestamps_are_utc_to_the_second(self) -> None:
        helsinki = timezone(timedelta(hours=3))
        moment = datetime(2026, 10, 7, 15, 4, 5, 999_999, tzinfo=helsinki)
        self.assertEqual(timestamp(moment), '2026-10-07T12:04:05Z')

    def test_a_timestamp_needs_a_time_zone(self) -> None:
        with self.assertRaises(RecordError):
            timestamp(datetime(2026, 10, 7, 12, 0))


class TestEmail(unittest.TestCase):
    def test_trimmed_and_lowercased(self) -> None:
        self.assertEqual(
            normalize_email('  Reader@Example.COM \n'), 'reader@example.com'
        )

    def test_keeps_letters_beyond_ascii(self) -> None:
        self.assertEqual(normalize_email('Äiti@Esimerkki.fi'), 'äiti@esimerkki.fi')

    def test_refuses_what_cannot_be_an_address(self) -> None:
        for raw in (
            '',
            'reader',
            'reader@example',
            '@example.com',
            'reader@',
            're ader@example.com',
            'reader@@example.com',
            'reader@exam\x00ple.com',
            'reader\u2028@example.com',
            'a' * (EMAIL_MAX_LENGTH - len('@example.com') + 1) + '@example.com',
        ):
            with self.subTest(raw=raw), self.assertRaises(RecordError) as caught:
                normalize_email(raw)
            # The message never repeats the address, so it can be logged.
            self.assertNotIn('reader', str(caught.exception))

    def test_the_longest_address_allowed(self) -> None:
        email = 'a' * (EMAIL_MAX_LENGTH - len('@example.com')) + '@example.com'
        self.assertEqual(normalize_email(email), email)


class TestUser(unittest.TestCase):
    def test_every_field_is_checked(self) -> None:
        for changes in (
            {'id': 'not-an-id'},
            {'email': 'Reader@example.com'},
            {'email': ' reader@example.com'},
            {'email': 'reader'},
            {'language': 'sv'},
            {'plan': 'gold'},
            {'created_at': '2026-10-07 12:00:00'},
            {'created_at': '2026-02-30T12:00:00Z'},
            {'updated_at': '2026-10-07T12:00:00+00:00'},
            {'updated_at': '2026-10-07T11:59:59Z'},
        ):
            with self.subTest(changes=changes), self.assertRaises(RecordError):
                replace(USER, **changes)

    def test_a_valid_user_is_made(self) -> None:
        self.assertEqual(replace(USER, plan='max').plan, 'max')


class TestRecordFiles(unittest.TestCase):
    def test_canonical_bytes(self) -> None:
        self.assertEqual(
            encode_user(USER, None),
            b'{\n'
            b'  "created_at": "2026-10-07T12:00:00Z",\n'
            b'  "email": "reader@example.com",\n'
            b'  "id": "3f9c2a7d0b8e4c51a6f2d9e0b7c4a1e5",\n'
            b'  "kind": "user",\n'
            b'  "language": "fi",\n'
            b'  "plan": "free",\n'
            b'  "schema": 2,\n'
            b'  "settings": null,\n'
            b'  "updated_at": "2026-10-07T12:30:00Z"\n'
            b'}\n',
        )

    def test_round_trip(self) -> None:
        for user in (USER, replace(USER, email='äiti@esimerkki.fi', language='en')):
            with self.subTest(email=user.email):
                self.assertEqual(decode_user(encode_user(user, None)), (user, None))

    def test_letters_are_written_as_themselves(self) -> None:
        data = encode_user(replace(USER, email='äiti@esimerkki.fi'), None)
        self.assertIn('äiti@esimerkki.fi'.encode(), data)

    def _variant(self, **changes: object) -> bytes:
        record = json.loads(encode_user(USER, None))
        record.update(changes)
        return (
            json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
        ).encode()

    def test_refuses_anything_but_a_valid_canonical_record(self) -> None:
        canonical = encode_user(USER, None)
        cases = {
            'not UTF-8': b'\xff\xfe',
            'not JSON': b'{',
            'not an object': b'[]\n',
            'missing a field': canonical.replace(b'  "plan": "free",\n', b''),
            'an extra field': self._variant(admin=True),
            'another schema': self._variant(schema=3),
            'a schema 1 record with settings': self._variant(schema=1),
            'a schema that is not a number': self._variant(schema=True),
            'another kind': self._variant(kind='chart'),
            'a field that is not text': self._variant(language=1),
            'an unknown language': self._variant(language='sv'),
            'an invalid user': self._variant(email='Reader@example.com'),
            'no final newline': canonical.rstrip(b'\n'),
            'other indentation': json.dumps(
                json.loads(canonical), sort_keys=True
            ).encode(),
            'unsorted keys': json.dumps(
                dict(reversed(list(json.loads(canonical).items()))), indent=2
            ).encode()
            + b'\n',
        }
        for name, data in cases.items():
            with self.subTest(name), self.assertRaises(RecordError):
                decode_user(data)

    def test_records_spread_over_folders_named_by_their_ids(self) -> None:
        self.assertEqual(
            user_path(USER.id), 'users/3f/3f9c2a7d0b8e4c51a6f2d9e0b7c4a1e5/user.json'
        )
        with self.assertRaises(RecordError):
            user_path('../../etc')

    def test_now_is_utc(self) -> None:
        self.assertTrue(timestamp(datetime.now(UTC)).endswith('Z'))


if __name__ == '__main__':
    unittest.main()
