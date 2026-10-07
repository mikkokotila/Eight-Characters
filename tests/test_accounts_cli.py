import contextlib
import io
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eight_characters.accounts.__main__ import main
from eight_characters.accounts.restore import read_identity
from eight_characters.accounts.store import AccountStore
from tests.accounts_support import make_remote_and_checkout


def run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class TestCommands(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory)

    def test_keygen_writes_a_private_key_only_its_owner_reads(self) -> None:
        key = self.directory / 'key.txt'
        code, out, _ = run('keygen', '--identity', str(key))
        self.assertEqual(code, 0)
        self.assertEqual(stat.S_IMODE(key.stat().st_mode), 0o600)
        self.assertEqual(out.strip(), str(read_identity(key).to_public()))
        self.assertTrue(out.startswith('age1'))
        self.assertNotIn('AGE-SECRET-KEY', out)

    def test_keygen_never_overwrites_a_key(self) -> None:
        key = self.directory / 'key.txt'
        key.write_text('precious\n')
        code, _, err = run('keygen', '--identity', str(key))
        self.assertEqual(code, 1)
        self.assertIn('exists already', err)
        self.assertEqual(key.read_text(), 'precious\n')

    def test_init_makes_a_database_once(self) -> None:
        database = self.directory / 'accounts.sqlite3'
        self.assertEqual(run('init', '--database', str(database))[0], 0)
        self.assertEqual(AccountStore.open(database).users(), [])
        code, _, err = run('init', '--database', str(database))
        self.assertEqual(code, 1)
        self.assertIn('exists already', err)

    def test_backup_refuses_a_recipient_that_is_no_public_key(self) -> None:
        database = self.directory / 'accounts.sqlite3'
        AccountStore.create(database)
        _, checkout = make_remote_and_checkout(self.directory)
        code, _, err = run(
            'backup',
            '--database',
            str(database),
            '--checkout',
            str(checkout),
            '--recipient',
            'AGE-SECRET-KEY-1NOTAPUBLICKEY',
        )
        self.assertEqual(code, 1)
        self.assertIn('not an age public key', err)

    def test_backup_and_restore_from_the_command_line(self) -> None:
        key = self.directory / 'key.txt'
        recipient = run('keygen', '--identity', str(key))[1].strip()
        database = self.directory / 'accounts.sqlite3'
        store = AccountStore.create(database)
        store.create_user('reader@example.com', 'fi')
        remote, checkout = make_remote_and_checkout(self.directory)
        code, out, _ = run(
            'backup',
            '--database',
            str(database),
            '--checkout',
            str(checkout),
            '--recipient',
            recipient,
        )
        self.assertEqual(code, 0, out)
        self.assertIn('1 written, 0 removed, pushed', out)
        clone = self.directory / 'clone'
        subprocess.run(('git', 'clone', '--quiet', str(remote), str(clone)), check=True)
        restored = self.directory / 'restored.sqlite3'
        code, out, err = run(
            'restore',
            '--checkout',
            str(clone),
            '--identity',
            str(key),
            '--database',
            str(restored),
        )
        self.assertEqual(code, 0, err)
        self.assertIn('Restored 1 users', out)
        self.assertEqual(AccountStore.open(restored).users(), store.users())

    def test_the_heartbeat_must_be_positive(self) -> None:
        database = self.directory / 'accounts.sqlite3'
        AccountStore.create(database)
        _, checkout = make_remote_and_checkout(self.directory)
        recipient = run('keygen', '--identity', str(self.directory / 'key.txt'))[1]
        code, _, err = run(
            'backup',
            '--database',
            str(database),
            '--checkout',
            str(checkout),
            '--recipient',
            recipient.strip(),
            '--heartbeat',
            '0',
        )
        self.assertEqual(code, 1)
        self.assertIn('--heartbeat must be at least one second', err)

    def test_a_failure_is_one_line_on_stderr(self) -> None:
        code, out, err = run(
            'backup',
            '--database',
            str(self.directory / 'none.sqlite3'),
            '--checkout',
            str(self.directory),
            '--recipient',
            'age1x',
        )
        self.assertEqual((code, out), (1, ''))
        self.assertTrue(err.startswith('error: No account database at'))

    def test_the_module_runs(self) -> None:
        completed = subprocess.run(
            (sys.executable, '-m', 'eight_characters.accounts', '--help'),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        for command in ('init', 'keygen', 'backup', 'restore', 'squash-history'):
            self.assertIn(command, completed.stdout)


if __name__ == '__main__':
    unittest.main()
