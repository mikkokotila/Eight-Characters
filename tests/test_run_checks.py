"""The browser runner's choices (tests/run_checks.py): which suites the essential run
takes, how a suite's two profiles run apart, and what it reads from a run's TAP."""

import re
import unittest
from pathlib import Path

from tests import run_checks

SUITES = Path(run_checks.SUITES)


class EssentialSuites(unittest.TestCase):
    available = ('account', 'compare', 'engine-truth', 'links', 'settings', 'today')

    @staticmethod
    def imported(suite: str) -> set[str]:
        return (
            {'chart-helpers.mjs', 'account-page.mjs'} if suite == 'settings' else set()
        )

    def choose(self, changed: list[str]) -> dict[str, str]:
        return run_checks.essential_suites(
            changed,
            self.available,
            ['engine-truth', 'account'],
            self.imported,
            areas=((r'eight_characters/static/compare\.js', ('compare',)),),
        )

    def test_nothing_changed_runs_the_core_journeys(self) -> None:
        self.assertEqual(
            self.choose([]), {'engine-truth': 'core journey', 'account': 'core journey'}
        )

    def test_a_changed_suite_runs(self) -> None:
        chosen = self.choose(['tests/browser/links.test.mjs', 'README.md'])
        self.assertEqual(list(chosen), ['engine-truth', 'account', 'links'])
        self.assertEqual(chosen['links'], 'changed: tests/browser/links.test.mjs')

    def test_a_deleted_suite_is_not_asked_for(self) -> None:
        self.assertEqual(
            list(self.choose(['tests/browser/gone.test.mjs'])),
            ['engine-truth', 'account'],
        )

    def test_a_changed_helper_runs_the_suites_that_import_it(self) -> None:
        chosen = self.choose(['tests/browser/account-page.mjs'])
        self.assertEqual(chosen['settings'], 'imports tests/browser/account-page.mjs')
        self.assertNotIn('today', chosen)

    def test_a_changed_area_runs_its_suites(self) -> None:
        chosen = self.choose(['eight_characters/static/compare.js'])
        self.assertEqual(
            chosen['compare'], 'area of eight_characters/static/compare.js'
        )

    def test_a_path_outside_the_areas_adds_nothing(self) -> None:
        self.assertEqual(
            list(self.choose(['eight_characters/static/app.js'])),
            ['engine-truth', 'account'],
        )

    def test_a_changed_list_of_core_journeys_runs_every_suite(self) -> None:
        chosen = self.choose(['tests/browser/essential.txt'])
        self.assertEqual(list(chosen), list(self.available))
        self.assertEqual(set(chosen.values()), {'changed: tests/browser/essential.txt'})

    def test_an_area_naming_no_suite_stops_the_run(self) -> None:
        with self.assertRaises(SystemExit):
            run_checks.essential_suites(
                [], self.available, [], self.imported, areas=(('x', ('gone',)),)
            )


class Jobs(unittest.TestCase):
    def test_a_profile_over_the_part_length_runs_in_parts(self) -> None:
        seconds = run_checks.PART_SECONDS * 2 + 1
        planned = run_checks.jobs_of('today', 'desktop', seconds)
        self.assertEqual(
            [job.label for job, _ in planned],
            ['today · desktop · 1/3', 'today · desktop · 2/3', 'today · desktop · 3/3'],
        )
        self.assertEqual({expected for _, expected in planned}, {seconds / 3})
        [(job, expected)] = run_checks.jobs_of('theme', 'mobile', 7)
        self.assertEqual((job.label, job.parts, expected), ('theme · mobile', 1, 7))

    def test_a_suite_not_yet_measured_runs_as_one_job_first(self) -> None:
        planned = [
            *run_checks.jobs_of('b', 'desktop', 300),
            *run_checks.jobs_of('new', 'desktop', None),
        ]
        self.assertEqual(run_checks.order(planned)[0].label, 'new · desktop')

    def test_the_longest_run_starts_first(self) -> None:
        planned = [
            *run_checks.jobs_of('a', 'desktop', 10),
            *run_checks.jobs_of('b', 'desktop', 300),
            *run_checks.jobs_of('c', 'mobile', 90),
        ]
        self.assertEqual(
            [job.label for job in run_checks.order(planned)],
            [
                'b · desktop · 1/3',
                'b · desktop · 2/3',
                'b · desktop · 3/3',
                'c · mobile',
                'a · desktop',
            ],
        )


class TheRepository(unittest.TestCase):
    def test_every_suite_has_its_seconds(self) -> None:
        available = run_checks.available_suites()
        found = run_checks.durations(available)
        self.assertEqual(sorted(found), available)
        self.assertTrue(
            all(
                seconds > 0
                for profiles in found.values()
                for seconds in profiles.values()
            )
        )

    def test_the_core_journeys_and_areas_name_suites_that_exist(self) -> None:
        available = run_checks.available_suites()
        core = run_checks.core_journeys()
        self.assertLessEqual(set(core), set(available))
        chosen = run_checks.essential_suites([], available, core)
        self.assertEqual(list(chosen), core)

    def test_every_suite_takes_its_profiles_and_tests_from_profiles_mjs(self) -> None:
        # The runner runs each profile, or a part of it, in a process of its own
        # (EC_PROFILE, EC_PART): a suite with profiles of its own, tests outside its
        # profiles that are not describeOnce, or tests registered with node:test's own
        # `it`, would run them twice, or in the wrong profile.
        for path in sorted(SUITES.glob('*.mjs')):
            text = path.read_text(encoding='utf-8')
            with self.subTest(path.name):
                if path.name != 'profiles.mjs':
                    self.assertNotIn('viewport: { width: 390, height: 844 }', text)
                self.assertNotIn('profiles[', text)
                if path.name.endswith('.test.mjs'):
                    self.assertEqual(
                        re.findall(r'^(?:describe|it|test)\(', text, re.M), []
                    )
                    own = r"import \{[^}]*\b(?:it|test)\b[^}]*\} from 'node:test'"
                    self.assertIsNone(re.search(own, text))


TAP = """TAP version 13
# Subtest: chromium / desktop / probe
    # Subtest: passes
    ok 1 - passes
      ---
      duration_ms: 1.5
      type: 'test'
      ...
    # Subtest: fails on purpose
    not ok 2 - fails on purpose
      ---
      duration_ms: 0.4
      type: 'test'
      failureType: 'testCodeFailure'
      error: |-
        deliberate

        2 !== 3
      code: 'ERR_ASSERTION'
      ...
    1..2
not ok 1 - chromium / desktop / probe
  ---
  duration_ms: 3.0
  type: 'suite'
  failureType: 'subtestsFailed'
  error: '1 subtest failed'
  ...
1..1
# tests 2
# suites 1
# pass 1
# fail 1
# cancelled 0
# skipped 0
# todo 0
# duration_ms 120.5
"""


class Tap(unittest.TestCase):
    def test_counts(self) -> None:
        self.assertEqual(
            run_checks.tap_counts(TAP),
            {
                'tests': 2,
                'suites': 1,
                'pass': 1,
                'fail': 1,
                'cancelled': 0,
                'skipped': 0,
                'todo': 0,
            },
        )

    def test_a_suite_without_a_matching_name_counts_no_test(self) -> None:
        tap = (
            'TAP version 13\n1..0\n# Subtest: tests/browser/settings.test.mjs\n'
            'ok 1 - tests/browser/settings.test.mjs\n  ---\n  duration_ms: 677.9\n'
            "  type: 'test'\n  ...\n1..1\n# tests 1\n# suites 0\n# pass 1\n# fail 0\n"
            '# cancelled 0\n# skipped 0\n# todo 0\n# duration_ms 682.7\n'
        )
        counts = run_checks.tap_counts(tap)
        self.assertEqual((counts['tests'], counts['pass']), (0, 0))

    def test_failures_are_the_failed_tests_with_their_diagnostics(self) -> None:
        [failure] = run_checks.tap_failures(TAP)
        self.assertTrue(failure.startswith('not ok 2 - fails on purpose\n  ---\n'))
        self.assertIn('2 !== 3', failure)
        self.assertTrue(failure.endswith('  ...'))

    def test_a_run_passes_only_if_a_test_ran_and_none_failed(self) -> None:
        job = run_checks.Job('probe', 'desktop')
        counts = {'tests': 1, 'fail': 0, 'cancelled': 0}
        self.assertTrue(run_checks.Result(job, 1.0, 0, '', counts).passed(False))
        self.assertFalse(run_checks.Result(job, 1.0, 1, '', counts).passed(False))
        self.assertFalse(
            run_checks.Result(job, 1.0, 0, '', {**counts, 'cancelled': 1}).passed(False)
        )
        empty = run_checks.Result(job, 1.0, 0, '', {**counts, 'tests': 0})
        self.assertFalse(empty.passed(False))
        # A name pattern can leave a suite with no test of that name.
        self.assertTrue(empty.passed(True))
        # A run that ended before its counts (a crash) did not pass.
        self.assertFalse(run_checks.Result(job, 1.0, 0, 'Error', {}).passed(True))


if __name__ == '__main__':
    unittest.main()
