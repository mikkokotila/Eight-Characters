import fcntl
import shutil
import tempfile
import unittest
from pathlib import Path

import pyrage

from eight_characters.accounts.backup import (
    MANIFEST,
    BackupBusy,
    BackupError,
    Manifest,
    manifest_bytes,
    read_manifest,
    run_backup,
    squash_history,
)
from eight_characters.accounts.records import User, encode_user
from eight_characters.accounts.restore import (
    RestoreError,
    read_identity,
    restore_backup,
)
from eight_characters.accounts.store import AccountStore
from tests.accounts_support import (
    Clock,
    all_object_contents,
    git,
    make_remote_and_checkout,
)


class BackupTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory)
        self.remote, self.checkout = make_remote_and_checkout(self.directory)
        self.identity = pyrage.x25519.Identity.generate()
        self.recipient = self.identity.to_public()
        self.clock = Clock()
        self.store = AccountStore.create(
            self.directory / 'accounts.sqlite3', clock=self.clock
        )

    def backup(self) -> None:
        run_backup(self.store, self.checkout, self.recipient)

    def file_of(self, user_id: str) -> Path:
        return self.checkout / 'users' / user_id[:2] / user_id / 'user.json.age'

    def remote_head(self) -> str:
        return git(self.remote, 'rev-parse', 'HEAD').strip()

    def commit_by_hand(self, message: str) -> None:
        git(self.checkout, 'add', '--all')
        git(self.checkout, 'commit', '--quiet', '--message', message)

    def fresh_clone(self, name: str = 'clone') -> Path:
        target = self.directory / name
        git(self.directory, 'clone', '--quiet', str(self.remote), str(target))
        return target


class TestRunBackup(BackupTestCase):
    def test_the_first_run_writes_every_record_encrypted_and_pushes(self) -> None:
        first = self.store.create_user('first@example.com', 'fi')
        second = self.store.create_user('second@example.com', 'en')
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual((result.written, result.removed, result.pushed), (2, 0, True))
        self.assertEqual(result.commit, self.remote_head())
        self.assertEqual(result.backed_up_seq, 2)
        for user in (first, second):
            ciphertext = self.file_of(user.id).read_bytes()
            self.assertTrue(ciphertext.startswith(b'age-encryption.org/v1\n'))
            self.assertEqual(
                pyrage.decrypt(ciphertext, [self.identity]), encode_user(user)
            )
        self.assertEqual(
            read_manifest(self.checkout),
            Manifest(recipient=str(self.recipient), user_count=2),
        )
        self.assertEqual(
            sorted(git(self.remote, 'ls-tree', '-r', '--name-only', 'HEAD').split()),
            sorted(
                [
                    '.gitattributes',
                    'README.md',
                    MANIFEST,
                    f'users/{first.id[:2]}/{first.id}/user.json.age',
                    f'users/{second.id[:2]}/{second.id}/user.json.age',
                ]
            ),
        )
        self.assertEqual(self.store.backup_snapshot().changes, ())

    def test_nothing_readable_reaches_the_repository(self) -> None:
        self.store.create_user('distinctive.reader@example.com', 'fi')
        self.backup()
        for repository in (self.checkout, self.remote):
            contents = all_object_contents(repository)
            self.assertNotIn(b'distinctive.reader', contents)
            self.assertNotIn(b'"language"', contents)
        self.assertNotIn(
            b'distinctive.reader',
            b''.join(
                path.read_bytes() for path in self.checkout.rglob('*') if path.is_file()
            ),
        )

    def test_a_run_with_nothing_new_commits_nothing(self) -> None:
        self.store.create_user('reader@example.com', 'fi')
        self.backup()
        head = self.remote_head()
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual(
            (result.written, result.commit, result.pushed), (0, None, False)
        )
        self.assertEqual(self.remote_head(), head)

    def test_a_changed_record_is_written_again(self) -> None:
        user = self.store.create_user('reader@example.com', 'fi')
        self.backup()
        self.clock.advance(60)
        changed = self.store.set_language(user.id, 'en')
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual((result.written, result.removed), (1, 0))
        plaintext = pyrage.decrypt(self.file_of(user.id).read_bytes(), [self.identity])
        self.assertEqual(plaintext, encode_user(changed))
        self.assertEqual(self.remote_head(), result.commit)

    def test_a_deleted_record_leaves_the_backup_with_its_folders(self) -> None:
        user = self.store.create_user('reader@example.com', 'fi')
        self.backup()
        self.store.delete_user(user.id)
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual((result.written, result.removed), (0, 1))
        self.assertFalse((self.checkout / 'users').exists())
        self.assertEqual(read_manifest(self.checkout), Manifest(str(self.recipient), 0))
        self.assertNotIn(
            'users/', git(self.remote, 'ls-tree', '-r', '--name-only', 'HEAD')
        )

    def test_a_record_made_and_deleted_between_runs_never_appears(self) -> None:
        self.backup()
        user = self.store.create_user('brief@example.com', 'fi')
        self.store.delete_user(user.id)
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual((result.written, result.removed), (0, 0))
        self.assertFalse(self.file_of(user.id).exists())

    def test_changes_of_its_own_stop_the_run(self) -> None:
        self.store.create_user('reader@example.com', 'fi')
        (self.checkout / 'note.txt').write_text('hand-made\n')
        with self.assertRaises(BackupError) as caught:
            self.backup()
        self.assertIn('note.txt', str(caught.exception))
        self.assertNotEqual(self.store.backup_snapshot().changes, ())

    def test_a_committed_file_it_never_writes_stops_the_run(self) -> None:
        (self.checkout / 'LICENSE').write_text('hand-made\n')
        self.commit_by_hand('a license')
        with self.assertRaises(BackupError) as caught:
            self.backup()
        self.assertIn('LICENSE', str(caught.exception))

    def test_another_key_stops_the_run(self) -> None:
        self.store.create_user('reader@example.com', 'fi')
        self.backup()
        self.store.create_user('later@example.com', 'fi')
        other = pyrage.x25519.Identity.generate().to_public()
        with self.assertRaises(BackupError):
            run_backup(self.store, self.checkout, other)

    def test_a_file_count_that_differs_from_the_database_stops_the_run(self) -> None:
        user = self.store.create_user('reader@example.com', 'fi')
        self.backup()
        self.file_of(user.id).unlink()
        self.commit_by_hand('lose a record')
        self.store.create_user('later@example.com', 'fi')
        with self.assertRaises(BackupError) as caught:
            self.backup()
        self.assertIn('1 user files but the database 2 users', str(caught.exception))

    def test_a_failed_push_keeps_the_changes_for_the_next_run(self) -> None:
        user = self.store.create_user('reader@example.com', 'fi')
        git(
            self.checkout,
            'remote',
            'set-url',
            'origin',
            str(self.directory / 'gone.git'),
        )
        with self.assertRaises(BackupError):
            self.backup()
        self.assertEqual(self.store.backup_snapshot().through_seq, 1)
        self.assertEqual(self.store.backup_snapshot().after_seq, 0)
        git(self.checkout, 'remote', 'set-url', 'origin', str(self.remote))
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertTrue(result.pushed)
        self.assertEqual(result.backed_up_seq, 1)
        self.assertEqual(
            self.remote_head(), git(self.checkout, 'rev-parse', 'HEAD').strip()
        )
        plaintext = pyrage.decrypt(self.file_of(user.id).read_bytes(), [self.identity])
        self.assertEqual(plaintext, encode_user(user))

    def test_a_second_run_at_the_same_time_is_refused(self) -> None:
        lock_path = self.checkout / '.git' / 'eight-characters-backup.lock'
        with open(lock_path, 'w') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BackupBusy):
                self.backup()

    def test_the_checkout_must_be_the_root_of_its_own_repository(self) -> None:
        inside = self.checkout / 'users'
        inside.mkdir()
        with self.assertRaises(BackupError):
            run_backup(self.store, inside, self.recipient)
        plain = self.directory / 'plain'
        plain.mkdir()
        with self.assertRaises(BackupError):
            run_backup(self.store, plain, self.recipient)
        with self.assertRaises(BackupError):
            run_backup(self.store, self.directory / 'missing', self.recipient)


class TestManifest(BackupTestCase):
    def test_a_malformed_manifest_stops_the_run(self) -> None:
        canonical = manifest_bytes(Manifest(str(self.recipient), 0))
        for name, data in {
            'empty': b'',
            'not JSON': b'{',
            'other fields': canonical.replace(b'"schema"', b'"version"'),
            'another schema': canonical.replace(b'"schema": 1', b'"schema": 2'),
            'a negative count': canonical.replace(b'"user": 0', b'"user": -1'),
            'not canonical': canonical.rstrip(b'\n'),
        }.items():
            with self.subTest(name):
                (self.checkout / MANIFEST).write_bytes(data)
                with self.assertRaises(BackupError):
                    read_manifest(self.checkout)


class TestSquashHistory(BackupTestCase):
    def test_squash_keeps_the_files_and_drops_the_history(self) -> None:
        for n in range(3):
            self.store.create_user(f'u{n}@example.com', 'fi')
            self.backup()
        tree = git(self.checkout, 'rev-parse', 'HEAD^{tree}').strip()
        squashed = squash_history(self.checkout)
        self.assertEqual(self.remote_head(), squashed)
        self.assertEqual(git(self.remote, 'rev-list', '--count', 'HEAD').strip(), '1')
        self.assertEqual(git(self.remote, 'rev-parse', 'HEAD^{tree}').strip(), tree)
        self.assertEqual(git(self.checkout, 'rev-parse', 'HEAD').strip(), squashed)
        # The next run builds on the squashed history.
        self.store.create_user('later@example.com', 'fi')
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual(self.remote_head(), result.commit)
        self.assertEqual(git(self.remote, 'rev-list', '--count', 'HEAD').strip(), '2')

    def test_squash_refuses_unpushed_or_moved_history(self) -> None:
        with self.assertRaises(BackupError):
            squash_history(self.checkout)
        self.store.create_user('reader@example.com', 'fi')
        self.backup()
        other = self.fresh_clone()
        (other / 'README.md').write_text('moved\n')
        git(other, 'commit', '--quiet', '--all', '--message', 'elsewhere')
        git(other, 'push', '--quiet', 'origin', 'HEAD')
        moved = self.remote_head()
        with self.assertRaises(BackupError):
            squash_history(self.checkout)
        self.assertEqual(self.remote_head(), moved)


class TestRestore(BackupTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.users = [
            self.store.create_user('first@example.com', 'fi'),
            self.store.create_user('Second@Example.org', 'en'),
        ]
        self.store.set_plan(self.users[0].id, 'pro')
        self.backup()
        self.clone = self.fresh_clone()
        self.target = self.directory / 'restored.sqlite3'

    def test_a_restore_rebuilds_the_database_exactly(self) -> None:
        result = restore_backup(self.clone, self.identity, self.target)
        self.assertEqual(result.users, 2)
        self.assertEqual(AccountStore.open(self.target).users(), self.store.users())

    def test_a_restored_database_backs_up_into_the_same_repository(self) -> None:
        restore_backup(self.clone, self.identity, self.target)
        restored = AccountStore.open(self.target)
        restored.create_user('after@example.com', 'en')
        result = run_backup(restored, self.clone, self.recipient)
        self.assertEqual((result.written, result.removed), (1, 0))
        self.assertEqual(read_manifest(self.clone), Manifest(str(self.recipient), 3))

    def test_refuses_an_existing_database(self) -> None:
        self.target.write_bytes(b'')
        with self.assertRaises(RestoreError):
            restore_backup(self.clone, self.identity, self.target)

    def test_refuses_another_key(self) -> None:
        with self.assertRaises(RestoreError):
            restore_backup(self.clone, pyrage.x25519.Identity.generate(), self.target)
        self.assertFalse(self.target.exists())

    def _tamper(self, change: str) -> None:
        user = self.users[0]
        path = self.clone / 'users' / user.id[:2] / user.id / 'user.json.age'
        if change == 'flip a byte':
            data = bytearray(path.read_bytes())
            data[-1] ^= 1
            path.write_bytes(bytes(data))
        elif change == 'swap two records':
            other = self.users[1]
            other_path = (
                self.clone / 'users' / other.id[:2] / other.id / 'user.json.age'
            )
            first, second = path.read_bytes(), other_path.read_bytes()
            path.write_bytes(second)
            other_path.write_bytes(first)
        elif change == 'drop a record':
            path.unlink()
        elif change == 'add a stray file':
            (self.clone / 'users' / user.id[:2] / user.id / 'notes.txt').write_text('x')
        git(self.clone, 'add', '--all')
        git(self.clone, 'commit', '--quiet', '--message', change)

    def test_refuses_a_tampered_backup_and_writes_nothing(self) -> None:
        for change in (
            'flip a byte',
            'swap two records',
            'drop a record',
            'add a stray file',
        ):
            with self.subTest(change):
                self.clone = self.fresh_clone(change.replace(' ', '-'))
                self._tamper(change)
                with self.assertRaises(BackupError):
                    restore_backup(self.clone, self.identity, self.target)
                self.assertFalse(self.target.exists())

    def test_refuses_a_checkout_with_changes_or_no_manifest(self) -> None:
        (self.clone / 'README.md').write_text('edited\n')
        with self.assertRaises(BackupError):
            restore_backup(self.clone, self.identity, self.target)
        empty = self.directory / 'empty'
        empty.mkdir()
        git(empty, 'init', '--quiet')
        with self.assertRaises(RestoreError):
            restore_backup(empty, self.identity, self.target)

    def test_refuses_two_records_with_one_address(self) -> None:
        clone = self.fresh_clone('twins')
        twin_id = 'f' * 32
        twin = User(
            id=twin_id,
            email=self.users[0].email,
            language='en',
            plan='free',
            created_at=self.users[0].created_at,
            updated_at=self.users[0].updated_at,
        )
        folder = clone / 'users' / 'ff' / twin_id
        folder.mkdir(parents=True)
        (folder / 'user.json.age').write_bytes(
            pyrage.encrypt(encode_user(twin), [self.recipient])
        )
        (clone / MANIFEST).write_bytes(manifest_bytes(Manifest(str(self.recipient), 3)))
        git(clone, 'add', '--all')
        git(clone, 'commit', '--quiet', '--message', 'twin')
        with self.assertRaises(RestoreError) as caught:
            restore_backup(clone, self.identity, self.target)
        self.assertNotIn('first@example.com', str(caught.exception))


class TestIdentityFiles(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory)

    def test_reads_an_age_keygen_file(self) -> None:
        identity = pyrage.x25519.Identity.generate()
        path = self.directory / 'key.txt'
        path.write_text(
            f'# created: 2026-10-07T12:00:00Z\n# public key: {identity.to_public()}\n{identity}\n'
        )
        self.assertEqual(
            str(read_identity(path).to_public()), str(identity.to_public())
        )

    def test_refuses_anything_else(self) -> None:
        one = pyrage.x25519.Identity.generate()
        two = pyrage.x25519.Identity.generate()
        for name, text in {
            'empty': '',
            'two keys': f'{one}\n{two}\n',
            'not a key': 'AGE-SECRET-KEY-1NOTAKEY\n',
            'a public key': f'{one.to_public()}\n',
        }.items():
            with self.subTest(name):
                path = self.directory / f'{name}.txt'
                path.write_text(text)
                with self.assertRaises(RestoreError):
                    read_identity(path)
        with self.assertRaises(RestoreError):
            read_identity(self.directory / 'missing.txt')


if __name__ == '__main__':
    unittest.main()
