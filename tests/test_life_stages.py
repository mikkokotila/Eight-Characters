import unittest

from lunar_python import EightChar, Solar

from eight_characters.canon import BRANCH_CHARS, STEM_CHARS, load_canon
from eight_characters.life_stages import life_stage


class TestLifeStages(unittest.TestCase):
    def test_every_stem_on_every_branch_matches_the_canon(self):
        table = load_canon()['cycle']['table']
        for stem in STEM_CHARS:
            for branch in BRANCH_CHARS:
                self.assertEqual(
                    life_stage(stem, branch), table[stem][branch], stem + branch
                )

    def test_every_stem_on_every_branch_matches_an_independent_reference(self):
        # lunar_python's own Day Master stages, over ten days of hours: every Day
        # Master meets every branch in the hour pillar.
        seen = set()
        for day in range(1, 11):
            for hour in range(0, 24, 2):
                chart = (
                    Solar.fromYmdHms(2026, 3, day, hour, 30, 0)
                    .getLunar()
                    .getEightChar()
                )
                stem, branch = chart.getDayGan(), chart.getTimeZhi()
                expected = EightChar.CHANG_SHENG.index(chart.getTimeDiShi()) + 1
                self.assertEqual(life_stage(stem, branch), expected, stem + branch)
                seen.add(stem + branch)
        self.assertEqual(len(seen), 120)

    def test_unknown_characters_are_refused(self):
        with self.assertRaises(ValueError):
            life_stage('子', '子')
        with self.assertRaises(ValueError):
            life_stage('甲', '甲')


if __name__ == '__main__':
    unittest.main()
