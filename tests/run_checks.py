"""Run static JavaScript, strict types, or browser checks from the repository.

`browser` runs the essential browser tests, or with --full every suite, each suite's
desktop and mobile profiles in processes of their own, beside each other. Every worker
has an app server of its own, with its own database and mail folder, on a free port.
See tests/browser/README.md."""

import argparse
import math
import os
import re
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUITES = ROOT / 'tests' / 'browser'
ESSENTIAL = SUITES / 'essential.txt'
PROFILES = ('desktop', 'mobile')

# The suites a change to one area of the app brings into the essential run, beside
# the core journeys (essential.txt) and any suite the change edits. A path outside
# these areas adds no suite: the full suite covers it.
AREAS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        r'eight_characters/(static/account(-billing)?\.js|accounts/.+)',
        ('account', 'account-sessions', 'account-billing', 'settings'),
    ),
    (r'eight_characters/static/compare\.js', ('compare',)),
    (r'eight_characters/(static/first\.js|first_chart\.py)', ('first',)),
    (r'eight_characters/static/(controls|toolbar|icons)\.js', ('controls', 'toolbar')),
    (
        r'eight_characters/(static/day-master-context\.js|day_master_context\.py)',
        ('day-master-context',),
    ),
    (r'eight_characters/static/life\.js', ('life',)),
    (r'eight_characters/(static/luck\.js|luck_[a-z_]+\.py)', ('luck', 'life')),
    (r'eight_characters/static/motion\.(js|css)', ('motion',)),
    (r'eight_characters/static/palette\.js', ('keyboard',)),
    (
        r'eight_characters/(static/pillar-changes\.js|pillar_changes\.py)',
        ('engine-truth',),
    ),
    (r'eight_characters/(static/place-search\.js|geocoding\.py)', ('location',)),
    (
        r'eight_characters/(static/readings\.js|reading\.py|canon\.py|resources/canon/.+)',
        ('reading',),
    ),
    (
        r'eight_characters/(static/relationships\.js|interactions\.py)',
        ('relationships', 'arcs'),
    ),
    (r'eight_characters/(static/roles\.js|role_profile\.py)', ('roles',)),
    (r'eight_characters/static/(settings|library)\.js', ('settings',)),
    (r'eight_characters/static/spotlight\.js', ('pointing',)),
    (
        r'eight_characters/(static/today\.js|today\.py|schools?\.py|school_[a-z_]+\.py|structure\.py)',
        ('today',),
    ),
    (
        r'eight_characters/static/(style\.css|fonts/.+)',
        ('design-system', 'tokens', 'components', 'theme'),
    ),
    (
        r'eight_characters/(templates/explorer\.html|explorer/.+|evolution/.+|explorer_controls\.py)',
        ('explorer-parameters',),
    ),
)

# The settings of every app server the runner starts: throwaway ones. Turnstile's test
# keys, which the app still checks with Cloudflare (so a run needs the network), and
# limits that a whole run stays within.
SERVER_SETTINGS = {
    'EC_MAIL_FROM': 'Eightchord <hello@example.com>',
    'EC_MAIL_TRANSPORT': 'directory',
    'EC_TURNSTILE_SITE_KEY': '1x00000000000000000000AA',
    'EC_TURNSTILE_SECRET': '1x0000000000000000000000000000000AA',
    'EC_CLIENT_IP_HEADER': 'peer',
    'EC_CODE_REQUESTS_PER_HOUR_PER_ADDRESS': '1000',
    'EC_CODE_REQUESTS_PER_HOUR_PER_CLIENT': '1000',
    'EC_CHART_REQUESTS_PER_HOUR_PER_CLIENT': '1000',
}
SERVER_START_SECONDS = 60
DURATIONS = SUITES / 'durations.txt'
# A profile that takes longer runs in parts of about this long, beside each other: the
# longest suites would otherwise finish long after the rest.
PART_SECONDS = 120
# A job that a stop interrupts gets this long to close its browser before it is killed.
STOP_GRACE_SECONDS = 10


def available_suites() -> list[str]:
    return sorted(
        path.name.removesuffix('.test.mjs') for path in SUITES.glob('*.test.mjs')
    )


def core_journeys() -> list[str]:
    """The suites essential.txt names, in its order: every essential run runs them."""
    lines = (
        line.strip() for line in ESSENTIAL.read_text(encoding='utf-8').splitlines()
    )
    names = [line for line in lines if line and not line.startswith('#')]
    if not names:
        raise SystemExit(f'No browser suites listed in {ESSENTIAL.relative_to(ROOT)}.')
    missing = [name for name in names if not (SUITES / f'{name}.test.mjs').is_file()]
    if missing:
        raise SystemExit(f'Missing essential browser suites: {", ".join(missing)}.')
    return names


def changed_paths() -> list[str]:
    """What the work changes, compared with origin/main: committed, staged, unstaged and
    untracked files, as paths from the repository's root."""

    def git(*args: str) -> str:
        return subprocess.run(
            ['git', *args], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout

    try:
        base = git('merge-base', 'origin/main', 'HEAD').strip()
    except subprocess.CalledProcessError as error:
        raise SystemExit(
            'The essential browser tests compare the work with origin/main, which git '
            f'cannot find here: {error.stderr.strip()}'
        ) from None
    changed = git('diff', '--name-only', '--no-renames', '-z', base).split('\0')
    untracked = git('ls-files', '--others', '--exclude-standard', '-z').split('\0')
    return sorted({path for path in [*changed, *untracked] if path})


def imports(suite: str) -> set[str]:
    """The helper modules a suite imports directly (one step: not their own imports)."""
    text = (SUITES / f'{suite}.test.mjs').read_text(encoding='utf-8')
    return set(re.findall(r"""from '\./([a-z-]+\.mjs)'""", text))


def essential_suites(
    changed: Sequence[str],
    available: Sequence[str],
    core: Sequence[str],
    imported: Callable[[str], set[str]] = imports,
    areas: Sequence[tuple[str, tuple[str, ...]]] = AREAS,
) -> dict[str, str]:
    """The essential run's suites, each with why: the core journeys, any suite the
    change edits or whose helper it edits, and the suites of a changed area. A change
    to the list of core journeys runs every suite."""
    unknown = sorted({name for _, names in areas for name in names} - set(available))
    if unknown:
        raise SystemExit(
            f'The areas name suites that do not exist: {", ".join(unknown)}.'
        )
    listed = str(ESSENTIAL.relative_to(ROOT))
    if listed in changed:
        return dict.fromkeys(available, f'changed: {listed}')
    chosen = dict.fromkeys(core, 'core journey')
    for path in changed:
        suite = re.fullmatch(r'tests/browser/([a-z-]+)\.test\.mjs', path)
        helper = re.fullmatch(r'tests/browser/([a-z-]+\.mjs)', path)
        if suite and suite[1] in available:
            chosen.setdefault(suite[1], f'changed: {path}')
        elif helper and not suite:
            for name in available:
                if helper[1] in imported(name):
                    chosen.setdefault(name, f'imports {path}')
        for area, names in areas:
            if re.fullmatch(area, path):
                for name in names:
                    chosen.setdefault(name, f'area of {path}')
    return chosen


@dataclass(frozen=True)
class Job:
    suite: str
    profile: str
    part: int = 1
    parts: int = 1

    @property
    def label(self) -> str:
        whole = f'{self.suite} · {self.profile}'
        return whole if self.parts == 1 else f'{whole} · {self.part}/{self.parts}'


def durations(available: Sequence[str]) -> dict[str, dict[str, int]]:
    """Each suite's seconds in each profile, from durations.txt. A line for no suite
    stops the run; a suite without a line (a new one, being measured) has none."""
    found: dict[str, dict[str, int]] = {}
    for line in DURATIONS.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        fields = line.split()
        if len(fields) != 1 + len(PROFILES) or not all(f.isdigit() for f in fields[1:]):
            raise SystemExit(
                f'{DURATIONS.relative_to(ROOT)}: not NAME DESKTOP MOBILE: {line}'
            )
        found[fields[0]] = dict(zip(PROFILES, map(int, fields[1:]), strict=True))
    unknown = sorted(set(found) - set(available))
    if unknown:
        raise SystemExit(
            f'{DURATIONS.relative_to(ROOT)} gives the seconds of no such suite: '
            f'{", ".join(unknown)}.'
        )
    return found


def jobs_of(suite: str, profile: str, seconds: int | None) -> list[tuple[Job, float]]:
    """A suite's profile as one job, or in parts when it takes long (EC_PART), each
    with the seconds it is expected to take. A suite not yet measured runs as one job,
    before the others: it may be long."""
    if seconds is None:
        return [(Job(suite, profile), math.inf)]
    parts = max(1, math.ceil(seconds / PART_SECONDS))
    return [
        (Job(suite, profile, part, parts), seconds / parts)
        for part in range(1, parts + 1)
    ]


@dataclass
class Result:
    job: Job
    seconds: float
    code: int
    tap: str
    counts: dict[str, int] = field(default_factory=dict[str, int])

    def passed(self, filtered: bool) -> bool:
        """Whether the run passed: it ended well, nothing failed or was cancelled, and
        a test ran, unless a name pattern left none in this suite."""
        return (
            self.code == 0
            and self.counts.get('fail', 1) == 0
            and self.counts.get('cancelled', 1) == 0
            and (filtered or self.counts.get('tests', 0) > 0)
        )


COUNTS = re.compile(r'^# (tests|suites|pass|fail|cancelled|skipped|todo) (\d+)$', re.M)


# A suite in which no test matched the name pattern: Node reports the file itself as
# one passed test.
NO_TEST = re.compile(r'^ok \d+ - \S+\.test\.mjs$', re.M)


def tap_counts(tap: str) -> dict[str, int]:
    counts = {name: int(value) for name, value in COUNTS.findall(tap)}
    if counts and NO_TEST.search(tap):
        counts['tests'] -= 1
        counts['pass'] -= 1
    return counts


def tap_failures(tap: str) -> list[str]:
    """Each failed test's TAP lines, with its diagnostics: not the suites that only
    report a failed test inside them."""
    lines = tap.splitlines()
    found: list[str] = []
    for index, line in enumerate(lines):
        failed = re.match(r'^(\s*)not ok \d+ - ', line)
        if not failed:
            continue
        indent = len(failed[1])
        block = [line]
        for following in lines[index + 1 :]:
            if len(following) - len(following.lstrip()) <= indent and following.strip():
                break
            block.append(following)
            if following == ' ' * (indent + 2) + '...':
                break
        if not any("failureType: 'subtestsFailed'" in entry for entry in block):
            found.append('\n'.join(entry[indent:] for entry in block))
    return found


def order(jobs: list[tuple[Job, float]]) -> list[Job]:
    """Longest first, so that no long job starts last."""
    return [job for job, _ in sorted(jobs, key=lambda pair: -pair[1])]


@dataclass
class Server:
    origin: str
    mail: Path
    log: Path
    process: subprocess.Popen[bytes]

    def check(self) -> None:
        if self.process.poll() is not None:
            raise RuntimeError(
                f'The app server at {self.origin} exited ({self.process.returncode}):\n'
                + self.log.read_text(encoding='utf-8', errors='replace')
            )


def start_server(directory: Path) -> Server:
    """An app with a new database and mail folder, on a free port. The socket is bound
    here and handed to the app, which serves on it."""
    mail = directory / 'mail'
    mail.mkdir(parents=True)
    listening = socket.socket()
    listening.bind(('127.0.0.1', 0))
    listening.listen(128)
    origin = f'http://127.0.0.1:{listening.getsockname()[1]}'
    # Only the runner's settings: none the shell holds reaches the app under test.
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith('EC_')
    }
    environment.update(
        SERVER_SETTINGS,
        EC_APP_ORIGIN=origin,
        EC_DATABASE_PATH=str(directory / 'accounts.sqlite3'),
        EC_MAIL_DIRECTORY=str(mail),
        EC_SECRET_KEY=secrets.token_urlsafe(48),
    )
    log = directory / 'server.log'
    with log.open('wb') as output:
        process = subprocess.Popen(
            [sys.executable, '-m', 'tests.browser.app_server', str(listening.fileno())],
            cwd=ROOT,
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
            pass_fds=(listening.fileno(),),
        )
    listening.close()
    return Server(origin, mail, log, process)


def wait_until_serving(server: Server) -> None:
    deadline = time.monotonic() + SERVER_START_SECONDS
    while True:
        server.check()
        try:
            with urllib.request.urlopen(server.origin + '/', timeout=5) as answer:
                if answer.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        if time.monotonic() > deadline:
            raise RuntimeError(
                f'The app server at {server.origin} did not answer within '
                f'{SERVER_START_SECONDS} s:\n'
                + server.log.read_text(encoding='utf-8', errors='replace')
            )
        time.sleep(0.2)


class Run:
    """Jobs shared out to workers, each with its own server, longest first."""

    def __init__(
        self, node: str, jobs: list[Job], name: str | None, tap: Path | None
    ) -> None:
        self.node = node
        self.tap = tap
        self.pending = list(jobs)
        self.total = len(jobs)
        self.name = name
        self.results: list[Result] = []
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.running: dict[int, subprocess.Popen[bytes]] = {}
        self.errors: list[BaseException] = []

    def next_job(self) -> Job | None:
        with self.lock:
            if self.stopping.is_set() or not self.pending:
                return None
            return self.pending.pop(0)

    def work(self, worker: int, server: Server, directory: Path) -> None:
        try:
            while (job := self.next_job()) is not None:
                server.check()
                result = self.run_job(worker, job, server, directory)
                with self.lock:
                    self.results.append(result)
                    done = len(self.results)
                counts = result.counts
                state = 'ok  ' if result.passed(bool(self.name)) else 'FAIL'
                failed = counts.get('fail', 0) + counts.get('cancelled', 0)
                print(
                    f'{state} {job.label}: {plural(counts.get("tests", 0), "test")}'
                    + (f', {failed} failed' if failed else '')
                    + f', {result.seconds:.1f} s  [{done}/{self.total}]',
                    flush=True,
                )
                server.check()
        except BaseException as error:
            with self.lock:
                self.errors.append(error)
            self.stop()

    def run_job(self, worker: int, job: Job, server: Server, directory: Path) -> Result:
        command = [self.node, '--test', '--test-concurrency=1', '--test-reporter=tap']
        if self.name:
            command.extend(['--test-name-pattern', self.name])
        command.append(str(SUITES / f'{job.suite}.test.mjs'))
        environment = dict(
            os.environ,
            EC_BASE_URL=server.origin,
            EC_MAIL_DIRECTORY=str(server.mail),
            EC_PROFILE=job.profile,
            EC_PART=f'{job.part}/{job.parts}',
        )
        name = f'{job.suite}.{job.profile}.{job.part}-of-{job.parts}.tap'
        tap = (self.tap or directory) / name
        started = time.monotonic()
        with tap.open('wb') as output:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            with self.lock:
                self.running[worker] = process
            if self.stopping.is_set():
                # Stopped while it started: stop() did not see it.
                signal_group(process, signal.SIGTERM)
            code = process.wait()
            with self.lock:
                del self.running[worker]
        text = tap.read_text(encoding='utf-8', errors='replace')
        return Result(job, time.monotonic() - started, code, text, tap_counts(text))

    def stop(self) -> None:
        """Stops every job: each gets a moment to close its browser, then is killed."""
        self.stopping.set()
        with self.lock:
            processes = list(self.running.values())
        for process in processes:
            signal_group(process, signal.SIGTERM)
        deadline = time.monotonic() + STOP_GRACE_SECONDS
        for process in processes:
            try:
                process.wait(max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                signal_group(process, signal.SIGKILL)


def signal_group(process: subprocess.Popen[bytes], number: int) -> None:
    try:
        os.killpg(process.pid, number)
    except ProcessLookupError:
        pass


def report(
    results: list[Result], workers: int, seconds: float, name: str | None
) -> bool:
    failed = [result for result in results if not result.passed(bool(name))]
    for result in sorted(
        failed,
        key=lambda result: (result.job.suite, result.job.profile, result.job.part),
    ):
        ran = result.counts.get('tests', 0)
        print(f'\n━━ {result.job.label}: exit {result.code}, {plural(ran, "test")}')
        blocks = tap_failures(result.tap)
        # Without a failed test to show (a crash, or no test at all), the end of its output.
        print('\n'.join(blocks) if blocks else result.tap[-4000:])
    totals = {
        key: sum(result.counts.get(key, 0) for result in results)
        for key in ('tests', 'pass', 'fail', 'cancelled', 'skipped', 'todo')
    }
    minutes, rest = divmod(round(seconds), 60)
    print(
        f'\n{plural(totals["tests"], "test")}: {totals["pass"]} passed, {totals["fail"]} failed, '
        f'{totals["cancelled"]} cancelled, {totals["skipped"]} skipped, '
        f'{totals["todo"]} todo; {plural(len(results), "run")} on {plural(workers, "worker")} in '
        f'{minutes} min {rest} s.'
    )
    slowest = sorted(results, key=lambda result: -result.seconds)[:5]
    print(
        'Slowest: '
        + ', '.join(f'{result.job.label} {result.seconds:.0f} s' for result in slowest)
    )
    return not failed


def plural(count: int, word: str) -> str:
    return f'{count} {word}' if count == 1 else f'{count} {word}s'


def default_workers() -> int:
    """Two CPUs fewer than the machine has, for its own work, and at most eight."""
    return max(1, min(8, (os.cpu_count() or 3) - 2))


def run_browser(args: argparse.Namespace, node: str) -> int:
    if 'EC_BASE_URL' in os.environ or 'EC_MAIL_DIRECTORY' in os.environ:
        raise SystemExit(
            'tests/run_checks.py starts app servers of its own: unset EC_BASE_URL and '
            'EC_MAIL_DIRECTORY, or run node --test against your server '
            '(tests/browser/README.md).'
        )
    if not os.environ.get('EC_PLAYWRIGHT_MODULE'):
        raise SystemExit(
            'Set EC_PLAYWRIGHT_MODULE to playwright or its index.mjs path.'
        )
    available = available_suites()
    named: list[str] = args.suite or []
    excluded: list[str] = args.exclude or []
    unknown = sorted((set(named) | set(excluded)) - set(available))
    if unknown:
        raise SystemExit(
            f'No such browser suite: {", ".join(unknown)}. The suites: '
            + ', '.join(available)
        )
    if named:
        chosen = dict.fromkeys(named, 'named')
        kind = 'named'
    elif args.full:
        chosen = dict.fromkeys(available, 'full')
        kind = 'full'
    else:
        chosen = essential_suites(changed_paths(), available, core_journeys())
        kind = 'essential'
    for name in excluded:
        chosen.pop(name, None)
    if not chosen:
        raise SystemExit('No browser suite is left to run.')
    profiles = [args.profile] if args.profile else list(PROFILES)
    seconds = durations(available)
    unmeasured = [suite for suite in chosen if suite not in seconds]
    if unmeasured:
        print(
            f'No seconds for {", ".join(unmeasured)} in '
            f'{DURATIONS.relative_to(ROOT)}: each profile runs as one job, first. Add '
            'a line for each, from the seconds this run prints.',
            flush=True,
        )
    jobs = order(
        [
            planned
            for suite in chosen
            for profile in profiles
            for planned in jobs_of(suite, profile, seconds.get(suite, {}).get(profile))
        ]
    )
    workers = min(args.workers, len(jobs))
    what = {
        'essential': 'the essential browser tests',
        'full': 'the full browser suite',
        'named': 'the named browser suites',
    }[kind]
    print(
        f'Running {what} in {args.browser}: {plural(len(chosen), "suite")}, '
        f'{plural(len(jobs), "run")} on {plural(workers, "worker")}.',
        flush=True,
    )
    if kind == 'essential':
        for suite, why in chosen.items():
            print(f'  {suite}: {why}', flush=True)
    os.environ['EC_BROWSER'] = args.browser
    tap: Path | None = args.tap_dir
    if tap is not None:
        tap.mkdir(parents=True, exist_ok=True)
    run = Run(node, jobs, args.name, tap)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='ec-browser-') as scratch:
        directory = Path(scratch)
        servers: list[Server] = []
        try:
            for index in range(workers):
                servers.append(start_server(directory / f'server-{index}'))
            for server in servers:
                wait_until_serving(server)
            threads = [
                threading.Thread(
                    target=run.work, args=(index, server, directory), daemon=True
                )
                for index, server in enumerate(servers)
            ]
            for thread in threads:
                thread.start()
            try:
                for thread in threads:
                    while thread.is_alive():
                        thread.join(0.5)
            except KeyboardInterrupt:
                print('\nStopping the browser tests.', flush=True)
                run.stop()
                for thread in threads:
                    thread.join()
                return 130
        finally:
            for server in servers:
                server.process.terminate()
            for server in servers:
                try:
                    server.process.wait(STOP_GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    server.process.kill()
                    server.process.wait()
    passed = report(run.results, workers, time.monotonic() - started, args.name)
    if run.errors:
        # The runner itself failed (a server stopped, say): the jobs left did not run.
        raise run.errors[0]
    return 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('check', choices=['syntax', 'types', 'browser'])
    parser.add_argument('--browser', choices=['chromium', 'webkit'])
    parser.add_argument(
        '--full',
        action='store_true',
        help='Run every browser suite (default: the essential tests)',
    )
    parser.add_argument(
        '--suite',
        action='append',
        metavar='NAME',
        help='Run exactly this browser suite (tests/browser/NAME.test.mjs); repeatable',
    )
    parser.add_argument(
        '--exclude',
        action='append',
        metavar='NAME',
        help='Leave this suite out; repeatable',
    )
    parser.add_argument(
        '--name', help='Run only browser test names matching this pattern'
    )
    parser.add_argument('--profile', choices=PROFILES, help='Run only this profile')
    parser.add_argument(
        '--tap-dir',
        type=Path,
        metavar='DIR',
        help="Keep each run's TAP in DIR, as SUITE.PROFILE.tap (default: none kept)",
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=default_workers(),
        help='How many suites run at once, each against its own app server '
        '(default: %(default)s, two fewer than the CPUs, at most 8)',
    )
    args = parser.parse_args()
    if args.check == 'types':
        return subprocess.call([sys.executable, '-m', 'pyright'], cwd=ROOT)
    node = os.environ['EC_NODE']
    if args.check == 'syntax':
        for source in sorted((ROOT / 'eight_characters' / 'static').glob('*.js')):
            subprocess.run([node, '--check', str(source)], cwd=ROOT, check=True)
        return 0
    if not args.browser:
        parser.error('browser checks require --browser')
    if args.full and args.suite:
        parser.error('--full runs every suite; --suite names the ones to run')
    if args.workers < 1:
        parser.error('--workers must be at least 1')
    try:
        return run_browser(args, node)
    except KeyboardInterrupt:
        # Stopped while the servers started: they are stopped, and no job ran.
        return 130


if __name__ == '__main__':
    sys.exit(main())
