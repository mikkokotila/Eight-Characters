import fcntl
import shutil
import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pyrage

from eight_characters.accounts import backup as backup_module
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
from eight_characters.accounts.store import AccountStore, StoreError
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

    def status(self) -> str:
        return git(self.checkout, 'status', '--porcelain', '--untracked-files=all')

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
                pyrage.decrypt(ciphertext, [self.identity]), encode_user(user, None)
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
        self.assertEqual(plaintext, encode_user(changed, None))
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
        self.store.create_user('later@example.com', 'fi')
        self.backup()
        # A row lost without its change logged, as only a bug could lose it.
        connection = sqlite3.connect(self.store.path)
        with connection:
            connection.execute('DELETE FROM users WHERE id = ?', (user.id,))
        connection.close()
        self.store.create_user('third@example.com', 'en')
        for _ in range(2):
            with self.assertRaises(BackupError) as caught:
                self.backup()
            # Each run names the same problem: the last run's files are not left
            # behind to be taken for changes the backup did not make.
            message = str(caught.exception)
            self.assertIn('3 user files but the database 2 users', message)
            self.assertEqual(self.status(), '')

    def test_a_link_in_the_checkout_stops_the_run(self) -> None:
        # Neither user's records take the shard of the link (ids are random, and one in
        # 256 began with ff, where the link could not be made).
        with patch(
            'eight_characters.accounts.store.new_id', side_effect=['00' + '1' * 30]
        ):
            self.store.create_user('reader@example.com', 'fi')
        self.backup()
        outside = self.directory / 'outside'
        outside.mkdir()
        (self.checkout / 'users' / 'ff').symlink_to(outside, target_is_directory=True)
        self.commit_by_hand('a link')
        with patch(
            'eight_characters.accounts.store.new_id', side_effect=['01' + '2' * 30]
        ):
            self.store.create_user('later@example.com', 'fi')
        with self.assertRaises(BackupError) as caught:
            self.backup()
        self.assertIn('a link, which it never writes: users/ff', str(caught.exception))
        self.assertEqual(list(outside.iterdir()), [])

    def test_a_record_changed_by_hand_stops_the_run(self) -> None:
        user = self.store.create_user('reader@example.com', 'fi')
        self.backup()
        path = self.file_of(user.id)
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(bytes(data))
        self.commit_by_hand('corrupt a record')
        self.store.create_user('later@example.com', 'fi')
        head = self.remote_head()
        with self.assertRaises(BackupError) as caught:
            self.backup()
        self.assertIn('commits the backup did not make', str(caught.exception))
        self.assertEqual(self.remote_head(), head)

    def test_records_without_a_manifest_stop_the_run(self) -> None:
        self.store.create_user('reader@example.com', 'fi')
        self.backup()
        (self.checkout / MANIFEST).unlink()
        self.commit_by_hand('lose the manifest')
        other = pyrage.x25519.Identity.generate().to_public()
        with self.assertRaises(BackupError) as caught:
            run_backup(self.store, self.checkout, other)
        self.assertIn('records but no manifest', str(caught.exception))

    def test_a_backup_from_elsewhere_stops_the_first_run(self) -> None:
        (self.checkout / 'README.md').write_text('another backup\n')
        self.commit_by_hand('another backup')
        self.store.create_user('reader@example.com', 'fi')
        with self.assertRaises(BackupError) as caught:
            self.backup()
        message = str(caught.exception)
        self.assertIn('not the backup this database last wrote', message)

    def test_a_failed_commit_leaves_the_checkout_as_it_was(self) -> None:
        real = backup_module._git

        def commit_refused(root: Path, *args: str, stdin: bytes | None = None) -> str:
            if 'commit-tree' in args:
                raise BackupError('git commit-tree failed (128): refused')
            return real(root, *args, stdin=stdin)

        refusing = patch.object(backup_module, '_git', commit_refused)
        first = self.store.create_user('first@example.com', 'fi')
        with refusing, self.assertRaises(BackupError):
            self.backup()
        self.assertEqual(self.status(), '')
        self.assertEqual([path.name for path in self.checkout.iterdir()], ['.git'])
        self.backup()
        second = self.store.create_user('second@example.com', 'en')
        with refusing, self.assertRaises(BackupError):
            self.backup()
        self.assertEqual(self.status(), '')
        self.assertTrue(self.file_of(first.id).exists())
        self.assertFalse(self.file_of(second.id).exists())
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual((result.written, result.pushed), (1, True))

    def test_a_run_stopped_between_its_commit_and_its_record_is_taken_up(self) -> None:
        self.store.create_user('reader@example.com', 'fi')
        stopped = StoreError('stopped')
        with (
            patch.object(AccountStore, 'record_backup_head', side_effect=stopped),
            self.assertRaises(StoreError),
        ):
            self.backup()
        # The checkout moved to the commit, which was neither recorded nor pushed.
        self.assertEqual(self.status(), '')
        made = git(self.checkout, 'rev-parse', 'HEAD').strip()
        self.assertEqual(self.store.backup_snapshot().pending_head, made)
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual((result.written, result.pushed), (1, True))
        local = git(self.checkout, 'rev-parse', 'HEAD').strip()
        self.assertEqual(self.remote_head(), local)
        self.assertEqual(git(self.checkout, 'rev-parse', 'HEAD~1').strip(), made)
        snapshot = self.store.backup_snapshot()
        self.assertEqual((snapshot.head, snapshot.pending_head), (local, None))

    def test_a_run_stopped_before_moving_the_checkout_is_redone(self) -> None:
        user = self.store.create_user('reader@example.com', 'fi')
        with (
            patch.object(backup_module, '_branch_ref', side_effect=KeyboardInterrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            self.backup()
        self.assertIsNotNone(self.store.backup_snapshot().pending_head)
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual((result.written, result.pushed), (1, True))
        snapshot = self.store.backup_snapshot()
        progress = (snapshot.head, snapshot.pending_head)
        self.assertEqual(progress, (self.remote_head(), None))
        plaintext = pyrage.decrypt(self.file_of(user.id).read_bytes(), [self.identity])
        self.assertEqual(plaintext, encode_user(user, None))

    def test_a_commit_made_by_hand_and_undone_stops_the_run(self) -> None:
        # Its files are the backup's again, but pushing would publish the commits.
        self.store.create_user('reader@example.com', 'fi')
        self.backup()
        head = self.remote_head()
        secret = 'plaintext that never leaves the server'
        (self.checkout / 'notes.txt').write_text(secret)
        self.commit_by_hand('notes')
        git(self.checkout, 'revert', '--no-edit', 'HEAD')
        self.store.create_user('later@example.com', 'en')
        with self.assertRaises(BackupError) as caught:
            self.backup()
        self.assertIn('commits the backup did not make', str(caught.exception))
        self.assertEqual(self.remote_head(), head)
        self.assertNotIn(secret.encode(), all_object_contents(self.remote))

    def test_a_run_stopped_while_writing_is_taken_up_by_the_next(self) -> None:
        first = self.store.create_user('first@example.com', 'fi')
        self.backup()
        second = self.store.create_user('second@example.com', 'en')
        # What a run killed part way leaves: its marker, a file written and staged,
        # another written, and Git's lock on the index.
        git_dir = self.checkout / '.git'
        (git_dir / 'eight-characters-backup.writing').touch()
        self.file_of(first.id).write_bytes(b'half written')
        git(self.checkout, 'add', '--all')
        target = self.file_of(second.id)
        target.parent.mkdir(parents=True)
        target.write_bytes(b'half written')
        (git_dir / 'index.lock').touch()
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertTrue(result.recovered)
        self.assertEqual((result.written, result.pushed), (1, True))
        self.assertEqual(self.status(), '')
        self.assertFalse((git_dir / 'eight-characters-backup.writing').exists())
        for user in (first, second):
            ciphertext = self.file_of(user.id).read_bytes()
            plaintext = pyrage.decrypt(ciphertext, [self.identity])
            self.assertEqual(plaintext, encode_user(user, None))
        later = run_backup(self.store, self.checkout, self.recipient)
        self.assertFalse(later.recovered)

    def test_a_file_it_writes_found_as_a_folder_stops_the_run(self) -> None:
        self.store.create_user('reader@example.com', 'fi')
        self.backup()
        (self.checkout / 'README.md').unlink()
        (self.checkout / 'README.md').mkdir()
        (self.checkout / 'README.md' / 'inside').write_text('hand-made\n')
        self.commit_by_hand('a folder for a file')
        with self.assertRaises(BackupError) as caught:
            self.backup()
        message = str(caught.exception)
        self.assertIn('README.md as something other than the file', message)

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
        self.assertEqual(plaintext, encode_user(user, None))

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


class TestHeartbeat(BackupTestCase):
    def test_a_quiet_run_says_it_is_alive_once_the_last_commit_is_old(self) -> None:
        self.store.create_user('reader@example.com', 'fi')
        self.backup()
        tree = git(self.remote, 'rev-parse', 'HEAD^{tree}').strip()
        hour = timedelta(hours=1)
        recent = run_backup(self.store, self.checkout, self.recipient, hour)
        self.assertEqual((recent.commit, recent.heartbeat), (None, False))
        beat = run_backup(self.store, self.checkout, self.recipient, timedelta(0))
        self.assertEqual((beat.heartbeat, beat.pushed), (True, True))
        self.assertEqual(self.remote_head(), beat.commit)
        subject = git(self.remote, 'log', '-1', '--format=%s').strip()
        self.assertEqual(subject, 'backup: alive')
        self.assertEqual(git(self.remote, 'rev-parse', 'HEAD^{tree}').strip(), tree)
        # The backup still knows the checkout as its own.
        self.store.create_user('later@example.com', 'fi')
        later = run_backup(self.store, self.checkout, self.recipient, timedelta(0))
        self.assertEqual((later.written, later.heartbeat), (1, False))

    def test_a_run_with_something_new_needs_no_heartbeat(self) -> None:
        self.store.create_user('reader@example.com', 'fi')
        result = run_backup(self.store, self.checkout, self.recipient, timedelta(0))
        self.assertEqual((result.written, result.heartbeat), (1, False))


class TestOwnerFolder(BackupTestCase):
    def owner_commit(self, text: str) -> None:
        workflows = self.checkout / '.github' / 'workflows'
        workflows.mkdir(parents=True, exist_ok=True)
        (workflows / 'backup-freshness.yml').write_text(text)
        self.commit_by_hand("the owner's freshness check")

    def test_the_owner_folder_is_not_the_backups_to_judge(self) -> None:
        # Seeded by the repository's owner before the first run.
        self.owner_commit('on: schedule\n')
        self.store.create_user('reader@example.com', 'fi')
        self.assertEqual(self.store.backup_snapshot().head, None)
        self.backup()
        self.owner_commit('on: workflow_dispatch\n')
        self.store.create_user('later@example.com', 'en')
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual((result.written, result.pushed), (1, True))
        restored = self.directory / 'restored.sqlite3'
        restore_backup(self.fresh_clone(), self.identity, restored)
        self.assertEqual(AccountStore.open(restored).users(), self.store.users())

    def test_an_owners_commit_beyond_the_owner_folder_stops_the_run(self) -> None:
        self.store.create_user('reader@example.com', 'fi')
        self.backup()
        head = self.remote_head()
        (self.checkout / 'README.md').write_text('changed by hand\n')
        self.owner_commit('on: schedule\n')
        self.store.create_user('later@example.com', 'en')
        with self.assertRaises(BackupError) as caught:
            self.backup()
        self.assertIn('commits the backup did not make', str(caught.exception))
        self.assertEqual(self.remote_head(), head)

    def test_the_owner_folder_cannot_be_a_link(self) -> None:
        (self.checkout / '.github').symlink_to(self.directory, target_is_directory=True)
        self.commit_by_hand('a link')
        with self.assertRaises(BackupError) as caught:
            self.backup()
        self.assertIn('a link, which it never writes: .github', str(caught.exception))


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
        squashed = squash_history(self.store, self.checkout)
        self.assertEqual(self.remote_head(), squashed)
        self.assertEqual(git(self.remote, 'rev-list', '--count', 'HEAD').strip(), '1')
        self.assertEqual(git(self.remote, 'rev-parse', 'HEAD^{tree}').strip(), tree)
        self.assertEqual(git(self.checkout, 'rev-parse', 'HEAD').strip(), squashed)
        # The next run builds on the squashed history.
        self.store.create_user('later@example.com', 'fi')
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual(self.remote_head(), result.commit)
        self.assertEqual(git(self.remote, 'rev-list', '--count', 'HEAD').strip(), '2')

    def test_squash_keeps_the_history_of_a_backup_it_cannot_vouch_for(self) -> None:
        first = self.store.create_user('first@example.com', 'fi')
        self.store.create_user('second@example.com', 'en')
        self.backup()
        self.file_of(first.id).unlink()
        self.commit_by_hand('lose a record')
        git(self.checkout, 'push', '--quiet', 'origin', 'HEAD')
        with self.assertRaises(BackupError) as caught:
            squash_history(self.store, self.checkout)
        self.assertIn('manifest counts 2', str(caught.exception))
        git(self.checkout, 'revert', '--no-edit', 'HEAD')
        (self.checkout / 'README.md').write_text('changed by hand\n')
        self.commit_by_hand('change the readme')
        git(self.checkout, 'push', '--quiet', 'origin', 'HEAD')
        with self.assertRaises(BackupError) as caught:
            squash_history(self.store, self.checkout)
        self.assertIn('not the backup this database last wrote', str(caught.exception))
        self.assertEqual(git(self.remote, 'rev-list', '--count', 'HEAD').strip(), '4')

    def test_squash_leaves_any_other_repository_alone(self) -> None:
        for case, name in enumerate(('README.md', 'main.py')):
            with self.subTest(name):
                base = self.directory / f'other-{case}'
                remote, checkout = make_remote_and_checkout(base)
                (checkout / name).write_text('its own file\n')
                git(checkout, 'add', '--all')
                git(checkout, 'commit', '--quiet', '--message', 'its own history')
                git(checkout, 'push', '--quiet', 'origin', 'HEAD')
                head = git(remote, 'rev-parse', 'HEAD').strip()
                with self.assertRaises(BackupError):
                    squash_history(self.store, checkout)
                self.assertEqual(git(remote, 'rev-parse', 'HEAD').strip(), head)

    def test_a_squash_stopped_after_its_push_is_finished_when_run_again(self) -> None:
        for n in range(2):
            self.store.create_user(f'u{n}@example.com', 'fi')
            self.backup()
        before = git(self.checkout, 'rev-parse', 'HEAD').strip()
        real = backup_module._git

        def stopped_before_moving_the_checkout(
            root: Path, *args: str, stdin: bytes | None = None
        ) -> str:
            if args[:1] == ('update-ref',):
                raise BackupError('stopped')
            return real(root, *args, stdin=stdin)

        with (
            patch.object(backup_module, '_git', stopped_before_moving_the_checkout),
            self.assertRaises(BackupError),
        ):
            squash_history(self.store, self.checkout)
        # The remote holds the squash; the checkout still holds the old history.
        self.assertEqual(git(self.remote, 'rev-list', '--count', 'HEAD').strip(), '1')
        self.assertEqual(git(self.checkout, 'rev-parse', 'HEAD').strip(), before)
        self.store.create_user('later@example.com', 'fi')
        with self.assertRaises(BackupError) as caught:
            self.backup()
        self.assertIn('run squash-history again', str(caught.exception))
        squashed = squash_history(self.store, self.checkout)
        self.assertEqual(self.remote_head(), squashed)
        self.assertEqual(git(self.checkout, 'rev-parse', 'HEAD').strip(), squashed)
        result = run_backup(self.store, self.checkout, self.recipient)
        self.assertEqual((result.written, result.pushed), (1, True))
        self.assertEqual(git(self.remote, 'rev-list', '--count', 'HEAD').strip(), '2')

    def test_a_squash_killed_while_moving_the_checkout_is_finished_when_run_again(
        self,
    ) -> None:
        # Killed while Git held the branch's lock: the lock stays behind.
        self.store.create_user('reader@example.com', 'fi')
        self.backup()
        real = backup_module._git
        branch = git(self.checkout, 'symbolic-ref', 'HEAD').strip()
        branch_lock = self.checkout / '.git' / f'{branch}.lock'

        def killed_holding_the_lock(
            root: Path, *args: str, stdin: bytes | None = None
        ) -> str:
            if args[:1] == ('update-ref',):
                branch_lock.write_text('')
                raise KeyboardInterrupt
            return real(root, *args, stdin=stdin)

        with (
            patch.object(backup_module, '_git', killed_holding_the_lock),
            self.assertRaises(KeyboardInterrupt),
        ):
            squash_history(self.store, self.checkout)
        self.assertTrue(branch_lock.exists())
        squashed = squash_history(self.store, self.checkout)
        self.assertFalse(branch_lock.exists())
        self.assertEqual(self.remote_head(), squashed)
        self.assertEqual(git(self.checkout, 'rev-parse', 'HEAD').strip(), squashed)
        self.store.create_user('later@example.com', 'en')
        result = run_backup(self.store, self.checkout, self.recipient)
        outcome = (result.written, result.pushed, result.recovered)
        self.assertEqual(outcome, (1, True, False))

    def test_a_squash_stopped_before_its_push_is_finished_when_run_again(self) -> None:
        self.store.create_user('reader@example.com', 'fi')
        self.backup()
        head = self.remote_head()
        real = AccountStore.record_pending_squash

        def killed_after_recording(store: AccountStore, commit: str, base: str) -> None:
            real(store, commit, base)
            raise KeyboardInterrupt

        with (
            patch.object(AccountStore, 'record_pending_squash', killed_after_recording),
            self.assertRaises(KeyboardInterrupt),
        ):
            squash_history(self.store, self.checkout)
        self.assertEqual(self.remote_head(), head)
        with self.assertRaises(BackupError):
            self.backup()
        squashed = squash_history(self.store, self.checkout)
        self.assertNotEqual(squashed, head)
        self.assertEqual(self.remote_head(), squashed)
        self.assertEqual(git(self.checkout, 'rev-parse', 'HEAD').strip(), squashed)
        self.assertEqual(self.store.backup_snapshot().head, squashed)

    def test_a_refused_squash_leaves_the_history_and_the_backup_goes_on(self) -> None:
        self.store.create_user('reader@example.com', 'fi')
        self.backup()
        head = self.remote_head()
        hook = self.remote / 'hooks' / 'pre-receive'
        hook.write_text('#!/bin/sh\necho "no rewriting here" >&2\nexit 1\n')
        hook.chmod(0o755)
        with self.assertRaises(BackupError) as caught:
            squash_history(self.store, self.checkout)
        self.assertIn('the history stays as it was', str(caught.exception))
        self.assertEqual(self.remote_head(), head)
        snapshot = self.store.backup_snapshot()
        progress = (snapshot.head, snapshot.pending_head, snapshot.squash_of)
        self.assertEqual(progress, (head, None, None))
        hook.unlink()
        self.store.create_user('later@example.com', 'en')
        self.assertTrue(run_backup(self.store, self.checkout, self.recipient).pushed)

    def test_squash_refuses_unpushed_or_moved_history(self) -> None:
        with self.assertRaises(BackupError):
            squash_history(self.store, self.checkout)
        self.store.create_user('reader@example.com', 'fi')
        self.backup()
        other = self.fresh_clone()
        (other / 'README.md').write_text('moved\n')
        git(other, 'commit', '--quiet', '--all', '--message', 'elsewhere')
        git(other, 'push', '--quiet', 'origin', 'HEAD')
        moved = self.remote_head()
        with self.assertRaises(BackupError):
            squash_history(self.store, self.checkout)
        self.assertEqual(self.remote_head(), moved)


class TestRestore(BackupTestCase):
    def setUp(self) -> None:
        super().setUp()
        # Keep the formerly colliding shard occupied in every restore regression.
        with patch(
            'eight_characters.accounts.store.new_id',
            side_effect=['ff' + '0' * 30, '00' + '1' * 30],
        ):
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

    def test_refuses_while_a_backup_run_holds_the_checkout(self) -> None:
        lock_path = self.clone / '.git' / 'eight-characters-backup.lock'
        with open(lock_path, 'w') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BackupBusy):
                restore_backup(self.clone, self.identity, self.target)
        self.assertFalse(self.target.exists())

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
        elif change == 'add a link':
            users = self.clone / 'users'
            unused = next(
                users / f'{shard:02x}'
                for shard in range(256)
                if not (users / f'{shard:02x}').exists()
            )
            unused.symlink_to(self.directory, target_is_directory=True)
        git(self.clone, 'add', '--all')
        git(self.clone, 'commit', '--quiet', '--message', change)

    def test_refuses_a_tampered_backup_and_writes_nothing(self) -> None:
        for change in (
            'flip a byte',
            'swap two records',
            'drop a record',
            'add a stray file',
            'add a link',
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

    def test_refuses_a_file_it_writes_found_as_a_folder(self) -> None:
        for name in ('README.md', '.gitattributes', MANIFEST):
            with self.subTest(name):
                clone = self.fresh_clone(f'folder{name}')
                (clone / name).unlink()
                (clone / name).mkdir()
                (clone / name / 'inside').write_text('x\n')
                git(clone, 'add', '--all')
                git(clone, 'commit', '--quiet', '--message', f'{name} as a folder')
                with self.assertRaises(BackupError) as caught:
                    restore_backup(clone, self.identity, self.target)
                self.assertIn(name, str(caught.exception))
                self.assertFalse(self.target.exists())

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
            pyrage.encrypt(encode_user(twin, None), [self.recipient])
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
        not_text = self.directory / 'not-text.txt'
        not_text.write_bytes(b'\xff\xfe\x00AGE')
        with self.assertRaises(RestoreError):
            read_identity(not_text)


if __name__ == '__main__':
    unittest.main()
