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

    def test_an_area_naming_no_suite_stops_the_run(self) -> None:
        with self.assertRaises(SystemExit):
            run_checks.essential_suites(
                [], self.available, [], self.imported, areas=(('x', ('gone',)),)
            )


class TheRepository(unittest.TestCase):
    def test_the_core_journeys_and_areas_name_suites_that_exist(self) -> None:
        available = run_checks.available_suites()
        core = run_checks.core_journeys()
        self.assertLessEqual(set(core), set(available))
        chosen = run_checks.essential_suites([], available, core)
        self.assertEqual(list(chosen), core)

    def test_every_suite_takes_its_profiles_from_profiles_mjs(self) -> None:
        # The runner runs each profile in a process of its own (EC_PROFILE): a suite with
        # profiles of its own, or tests outside its profiles that are not describeOnce,
        # would run them twice, or in the wrong profile.
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
