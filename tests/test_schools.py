"""The schools Today follows (eight_characters/schools.py), held to docs/Today.md."""

import re
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

from eight_characters.data import STEMS
from eight_characters.engine import jie_before, pillars_at
from eight_characters.mappings import hidden_stems_lookup
from eight_characters.qiong_tong_bao_jian import ENTRIES, TABLE, climate_stems
from eight_characters.school_catalog import school_catalog
from eight_characters.school_presets import (
    FAVOURABLE_SCHOOLS,
    SEASON_SCHOOLS,
    TRANSIT_SCHOOLS,
)
from eight_characters.schools import (
    COMMANDERS,
    ELEMENTS,
    climate_order,
    commander,
    element_of,
    pull,
    season_at,
    standings,
    support_and_restrain,
)
from eight_characters.sexagenary import BRANCHES as BRANCH_CHARS
from eight_characters.solar_position import julian_date_from_datetime_utc
from eight_characters.solar_term_solver import find_solar_term
from eight_characters.time_convert import BirthInput, utc_from_jd_tt

FIXTURE = Path(__file__).parent / 'fixtures' / 'qiong_tong_bao_jian_2294674.txt'
# Each of the five gods' weight, in docs/Today.md's order.
GOD_WEIGHTS = (
    ('useful', 1.2),
    ('favourable', 1.0),
    ('idle', 0.0),
    ('enemy', -1.0),
    ('unfavourable', -1.2),
)
FIRE_SEASON = standings('fire')
EVEN = dict.fromkeys(ELEMENTS, 'supported')


def _gods(*elements: str) -> dict[str, str]:
    # The elements for the useful, favourable, idle, enemy and unfavourable gods.
    return dict(zip((god for god, _ in GOD_WEIGHTS), elements, strict=True))


def _weights(*elements: str) -> dict[str, float]:
    return dict(zip(elements, (weight for _, weight in GOD_WEIGHTS), strict=True))


def _chart(*pairs: str) -> dict[str, tuple[str, str]]:
    return {
        name: (pair[0], pair[1])
        for name, pair in zip(('year', 'month', 'day', 'hour'), pairs, strict=True)
    }


class TestStandings(unittest.TestCase):
    def test_each_ruler_sets_the_five_standings(self) -> None:
        self.assertEqual(
            standings('wood'),
            {
                'wood': 'prosperous',
                'fire': 'supported',
                'earth': 'dead',
                'metal': 'imprisoned',
                'water': 'resting',
            },
        )
        for ruler in ELEMENTS:
            with self.subTest(ruler=ruler):
                found = standings(ruler)
                self.assertEqual(found[ruler], 'prosperous')
                self.assertEqual(sorted(found.values()), sorted(set(found.values())))


class TestEarthSeason(unittest.TestCase):
    def test_eighteen_days_by_the_suns_longitude(self) -> None:
        cases = {
            0.0: 'wood',
            26.999: 'wood',
            27.0: 'earth',
            44.999: 'earth',
            45.0: 'fire',
            116.999: 'fire',
            117.0: 'earth',
            135.0: 'metal',
            207.0: 'earth',
            225.0: 'water',
            296.999: 'water',
            297.0: 'earth',
            314.999: 'earth',
            315.0: 'wood',
            359.999: 'wood',
        }
        for longitude, ruler in cases.items():
            with self.subTest(longitude=longitude):
                # The branch does not decide this school.
                self.assertEqual(
                    season_at('eighteen', longitude, '子', 0.0)['ruler'], ruler
                )

    def test_eighteen_days_change_at_the_solvers_instants(self) -> None:
        for target, before, after in (
            (27.0, 'wood', 'earth'),
            (45.0, 'earth', 'fire'),
            (117.0, 'fire', 'earth'),
            (135.0, 'earth', 'metal'),
            (207.0, 'metal', 'earth'),
            (225.0, 'earth', 'water'),
            (297.0, 'water', 'earth'),
            (315.0, 'earth', 'wood'),
        ):
            with self.subTest(target=target):
                # Seeded within a few days of the longitude in 2026.
                day = 80 + (target - 0.0) * 365.2422 / 360
                seed = julian_date_from_datetime_utc(
                    datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day % 365)
                )
                instant = utc_from_jd_tt(find_solar_term(target, seed))
                for offset, ruler in ((-60, before), (60, after)):
                    moment = instant + timedelta(seconds=offset)
                    at = pillars_at(
                        BirthInput(utc_timestamp=moment.strftime('%Y-%m-%dT%H:%M:%SZ'))
                    )
                    season = season_at(
                        'eighteen',
                        at.solar.lambda_apparent_deg,
                        BRANCH_CHARS[at.month.branch_idx],
                        at.solar.jd_tt - jie_before(at),
                    )
                    self.assertEqual(season['ruler'], ruler)

    def test_earth_months_and_late_summer_by_the_months_branch(self) -> None:
        months = {
            '寅': 'wood',
            '卯': 'wood',
            '辰': 'earth',
            '巳': 'fire',
            '午': 'fire',
            '未': 'earth',
            '申': 'metal',
            '酉': 'metal',
            '戌': 'earth',
            '亥': 'water',
            '子': 'water',
            '丑': 'earth',
        }
        late = {**months, '辰': 'wood', '戌': 'metal', '丑': 'water'}
        for branch in months:
            with self.subTest(branch=branch):
                self.assertEqual(
                    season_at('months', 10.0, branch, 3.0)['ruler'], months[branch]
                )
                self.assertEqual(
                    season_at('late_summer', 10.0, branch, 3.0)['ruler'], late[branch]
                )

    def test_the_commander_by_the_days_since_the_jie(self) -> None:
        cases = (
            ('寅', 0.0, '艮土', 'earth'),
            ('寅', 4.99, '艮土', 'earth'),
            ('寅', 5.0, '丙火', 'fire'),
            ('寅', 9.99, '丙火', 'fire'),
            ('寅', 10.0, '甲木', 'wood'),
            ('寅', 31.5, '甲木', 'wood'),
            ('辰', 11.0, '壬水', 'water'),
            ('丑', 12.0, '己土', 'earth'),
        )
        for branch, days, name, element in cases:
            with self.subTest(branch=branch, days=days):
                found = commander(branch, days)
                self.assertEqual((found['name'], found['element']), (name, element))
                season = season_at('commander', 300.0, branch, days)
                self.assertEqual(season['ruler'], element)
                self.assertEqual(season['commander'], found)
        with self.assertRaises(ValueError):
            commander('寅', -0.1)

    def test_the_commanders_are_san_ming_tong_huis(self) -> None:
        # San Ming Tong Hui, juan 2, 論人元司事, as the Siku Quanshu copy has it.
        text = (
            '如正月建寅寅中有艮土用事五日丙火長生五日甲木二十日二月建卯卯中有甲木用事'
            '七日乙木二十三日三月建辰辰中有乙木用事七日壬水墓庫五日戊土一十八日四月建巳'
            '巳中有戊土七日庚金長生五日丙火一十八日五月建午午中丙火用事七日丁火二十三日'
            '六月建未未中有丁火用事七日甲木墓庫五日巳土一十八日七月建申申中有坤土用事'
            '五日壬水長生五日庚金二十日八月建酉酉中有庚金用事七日辛金二十三日九月建戌'
            '戌中有辛金用事七日丙火墓庫五日戊土一十八日十月建亥亥中有戊土五日甲木長生'
            '五日壬水用事二十日十一月建子子中有壬水用事七日癸水二十三日十二月建丑丑中'
            '有癸水用事七日庚金墓庫五日巳土一十八日'
        )
        days = {'五': 5, '七': 7}
        months = re.findall(r'建(.)\1中有?(.*?)(?=[一二三四五六七八九十]+月建|$)', text)
        self.assertEqual(len(months), 12)
        for branch, body in months:
            spans = re.findall(
                r'(..)(?:用事|長生|墓庫)?(一十八|二十三|二十|五|七)日', body
            )
            with self.subTest(branch=branch):
                table = COMMANDERS[branch]
                self.assertEqual(len(spans), len(table))
                for (name, count), span in zip(spans, table, strict=True):
                    # The text writes 己 as 巳 in 未 and 丑.
                    self.assertEqual(name.replace('巳土', '己土'), span.name)
                    if span.days is not None:
                        self.assertEqual(days[count], span.days)


class TestSupportAndRestrain(unittest.TestCase):
    def test_the_canons_worked_example(self) -> None:
        # canon/Background.md's chart, born in a Fire season: weak, Wealth the disease.
        # The Companion is useful and the Resource favourable; the Output idle, the
        # Officer the enemy, and the Wealth unfavourable.
        found = support_and_restrain(
            _chart('丙辰', '甲午', '壬子', '癸卯'), FIRE_SEASON
        )
        self.assertEqual(found['strength'], 'weak')
        self.assertEqual(found['disease'], 'fire')
        self.assertEqual(
            found['weights'], _weights('water', 'metal', 'wood', 'earth', 'fire')
        )
        assert found['tally'] is not None
        self.assertEqual(found['tally']['supported_share'], 0.2)

    def test_each_case_of_the_rule(self) -> None:
        # Day Master 甲 Wood: Companion wood, Output fire, Wealth earth, Officer metal,
        # Resource water. Equal standing, so the tally is the plain count. The gods in
        # docs/Today.md's order: useful, favourable, idle, enemy, unfavourable.
        cases = {
            'weak, Output strongest': (
                ('丙午', '丙午', '甲午', '癸巳'),
                'weak',
                'fire',
                ('water', 'wood', 'metal', 'earth', 'fire'),
            ),
            'weak, Wealth strongest': (
                ('戊戌', '己未', '甲戌', '戊辰'),
                'weak',
                'earth',
                ('wood', 'water', 'fire', 'metal', 'earth'),
            ),
            'weak, Officer strongest': (
                ('庚申', '辛酉', '甲申', '庚申'),
                'weak',
                'metal',
                ('water', 'wood', 'fire', 'metal', 'earth'),
            ),
            'strong, Companion stronger': (
                ('甲寅', '乙卯', '甲寅', '乙卯'),
                'strong',
                'wood',
                ('fire', 'earth', 'metal', 'wood', 'water'),
            ),
            'strong, Resource stronger': (
                ('壬子', '癸亥', '甲子', '壬子'),
                'strong',
                'water',
                ('earth', 'fire', 'metal', 'wood', 'water'),
            ),
        }
        for name, (pillars, strength, disease, gods) in cases.items():
            with self.subTest(name):
                found = support_and_restrain(_chart(*pillars), EVEN)
                self.assertEqual(found['strength'], strength)
                self.assertEqual(found['disease'], disease)
                self.assertEqual(found['gods'], _gods(*gods))
                self.assertEqual(found['weights'], _weights(*gods))

    def test_a_chart_with_no_support_but_its_day_master_follows(self) -> None:
        # 甲 on 午, with no Wood or Water anywhere else, visible or hidden.
        # The Resource, Water, is unfavourable, and the Companion, Wood, the enemy.
        cases = {
            'Wealth strongest': (('戊戌', '己巳', '甲戌', '戊午'), 'earth', 'fire', 'metal'),
            'Output strongest': (('丙午', '丁巳', '甲午', '丙午'), 'fire', 'earth', 'metal'),
            'Officer strongest': (('庚戌', '辛酉', '甲戌', '辛巳'), 'metal', 'earth', 'fire'),
        }
        for name, (pillars, useful, favourable, idle) in cases.items():
            with self.subTest(name):
                found = support_and_restrain(_chart(*pillars), EVEN)
                self.assertEqual(found['strength'], 'following')
                self.assertIsNone(found['disease'])
                self.assertEqual(
                    found['gods'], _gods(useful, favourable, idle, 'wood', 'water')
                )

    def test_a_review_fixture_follows(self) -> None:
        # 1987-08-01 14:00 UTC at 0, 0: 丁卯 丁未 壬午 丁未. No Water or Metal but the
        # Day Master's own stem, so it follows its strongest force, Fire.
        found = support_and_restrain(
            _chart('丁卯', '丁未', '壬午', '丁未'), standings('earth')
        )
        self.assertEqual(found['strength'], 'following')
        self.assertEqual(
            found['gods'], _gods('fire', 'wood', 'earth', 'water', 'metal')
        )

    def test_exactly_half_is_strong(self) -> None:
        # Wood 2.4 and Water 2.2 make 4.6 of 9.2: half, so strong; Wood, the larger,
        # is the disease.
        found = support_and_restrain(_chart('甲子', '丙辰', '甲子', '丙戌'), EVEN)
        assert found['tally'] is not None
        self.assertEqual(found['tally']['supported_share'], 0.5)
        self.assertEqual(found['strength'], 'strong')
        self.assertEqual(found['disease'], 'wood')

    def test_a_tie_goes_to_the_first_named(self) -> None:
        # Companion and Resource count 4.0 each: Companion is named first.
        found = support_and_restrain(_chart('甲子', '甲子', '甲子', '甲子'), EVEN)
        assert found['tally'] is not None
        self.assertEqual(found['tally']['elements']['wood'], 4.0)
        self.assertEqual(found['tally']['elements']['water'], 4.0)
        self.assertEqual(found['disease'], 'wood')

    def test_the_weights_are_a_permutation(self) -> None:
        for day_master in STEMS:
            for branch in BRANCH_CHARS:
                pillars = _chart('甲子', '丙寅', day_master + branch, '庚申')
                for ruler in ELEMENTS:
                    found = support_and_restrain(pillars, standings(ruler))
                    self.assertEqual(
                        sorted(found['weights'].values()),
                        sorted(weight for _, weight in GOD_WEIGHTS),
                    )


class TestClimate(unittest.TestCase):
    def test_every_cell_has_an_entry_from_the_text(self) -> None:
        # The revision's own words, without its bold marks and line breaks.
        source = re.sub(r'\s+', '', FIXTURE.read_text(encoding='utf-8'))
        source = source.replace("'''", '')
        self.assertEqual(len(ENTRIES), 120)
        for entry in TABLE:
            with self.subTest(heading=entry.heading, months=entry.months):
                self.assertIn(entry.heading, source)
                self.assertIn(re.sub(r'\s+', '', entry.sentence), source)
                if entry.later is not None:
                    self.assertIn(re.sub(r'\s+', '', entry.later.sentence), source)

    def test_entries_as_the_text_gives_them(self) -> None:
        # 正月甲木's statement of the month alone comes before 总之正二月甲木's, which
        # speaks of both months; 卯, with nothing said of it alone, takes the latter.
        self.assertEqual(climate_stems('甲', '寅', False), ['丙', '癸'])
        self.assertEqual(climate_stems('甲', '卯', False), ['庚', '戊'])
        self.assertEqual(climate_stems('甲', '辰', True), ['庚', '壬'])
        # 乙 Yi in the 酉 You month: 癸 before 秋分, 丙 then 癸 after it.
        self.assertEqual(climate_stems('乙', '酉', False), ['癸'])
        self.assertEqual(climate_stems('乙', '酉', True), ['丙', '癸'])
        self.assertEqual(climate_stems('丁', '子', False), ['甲', '庚', '癸', '戊'])
        self.assertEqual(climate_stems('壬', '丑', True), ['丙', '甲'])
        # The month's closing summary ranks three stems: 十月壬水、专用戊丙，次取庚金.
        self.assertEqual(climate_stems('壬', '亥', False), ['戊', '丙', '庚'])
        # Of two orders as full, the later: 六月壬水，先辛后甲，次取癸水.
        self.assertEqual(climate_stems('壬', '未', False), ['辛', '甲', '癸'])
        # A ranked statement wins over a listing: 丁先庚后 over 耑取庚丁.
        self.assertEqual(climate_stems('甲', '子', False), ['丁', '庚', '丙'])

    def test_the_order_from_the_stems(self) -> None:
        # 丙 Fire useful, 癸 Water favourable. What controls Fire is Water, taken; so
        # the unfavourable is what controls Water, Earth; then the enemy, what
        # generates Earth, Fire, is taken, so the first free from Fire in the
        # generating order, Metal; last and idle, Wood.
        self.assertEqual(
            climate_order(['丙', '癸']), ['fire', 'water', 'earth', 'metal', 'wood']
        )
        # An element named after the first two is never against the chart while one
        # the text leaves unnamed is free: 丙 in 亥, 甲戊庚, leaves Metal idle.
        self.assertEqual(
            climate_order(['甲', '戊', '庚']), ['wood', 'earth', 'fire', 'water', 'metal']
        )
        # 己 in 戌 names four elements: of the two after the first two, the later,
        # 甲 Wood, takes the place against the chart.
        self.assertEqual(
            climate_order(['癸', '丙', '辛', '甲']),
            ['water', 'fire', 'earth', 'wood', 'metal'],
        )
        # One element named: the favourable is what generates it.
        self.assertEqual(climate_order(['庚', '辛'])[:2], ['metal', 'earth'])
        self.assertEqual(climate_order(['壬'])[:3], ['water', 'metal', 'earth'])
        for entry in TABLE:
            for stems in (
                entry.stems,
                *(() if entry.later is None else (entry.later.stems,)),
            ):
                order = climate_order(stems)
                self.assertEqual(sorted(order), sorted(ELEMENTS))
                named = {element_of(stem) for stem in stems}
                if order[4] not in named:
                    self.assertFalse(named & set(order[2:4]), stems)


class TestPull(unittest.TestCase):
    # Weights for the pull's arithmetic, not a school's.
    WEIGHTS: ClassVar[dict[str, float]] = {
        'water': 1.2,
        'metal': 1.0,
        'fire': -1.0,
        'wood': -0.8,
        'earth': -0.6,
    }

    def test_the_day_counts_by_the_season(self) -> None:
        # 戊午 while Metal rules: 戊 Earth -0.6 × 0.6; 丁 Fire -1.0 × 0.4;
        # 己 Earth -0.6 × 0.4 × 0.6.
        found = pull(
            '戊', '午', self.WEIGHTS, standings('metal'), layer='day', transits='phases'
        )
        self.assertEqual(found['score'], -0.9)
        self.assertEqual(found['band'], 'draining')
        self.assertEqual(
            [(part['char'], part['role'], part['value']) for part in found['parts']],
            [('戊', 'stem', -0.36), ('丁', 'main', -0.4), ('己', 'middle', -0.14)],
        )

    def test_the_year_and_the_luck_pillar_by_school(self) -> None:
        metal = standings('metal')
        year = pull('丙', '午', self.WEIGHTS, metal, layer='year', transits='phases')
        self.assertEqual(year['score'], -1.62)
        self.assertEqual(year['band'], 'strongly_draining')
        branch_phase = pull(
            '己',
            '亥',
            self.WEIGHTS,
            metal,
            layer='luck',
            transits='phases',
            phase='branch',
        )
        self.assertEqual(branch_phase['score'], 0.88)
        self.assertNotIn('stem', [part['role'] for part in branch_phase['parts']])
        stem_phase = pull(
            '己',
            '亥',
            self.WEIGHTS,
            metal,
            layer='luck',
            transits='phases',
            phase='stem',
        )
        self.assertEqual(stem_phase['score'], 0.28)
        whole = pull(
            '己',
            '亥',
            self.WEIGHTS,
            metal,
            layer='luck',
            transits='whole',
            phase='branch',
        )
        self.assertEqual(whole['score'], 0.58)
        seasoned = pull(
            '己',
            '亥',
            self.WEIGHTS,
            metal,
            layer='luck',
            transits='seasoned',
            phase='branch',
        )
        # 己 -0.6 × 0.6; 壬 1.2 × 1.0; 甲 -0.8 × 0.4 × 0.2.
        self.assertEqual(seasoned['score'], 0.78)
        with self.assertRaises(ValueError):
            pull('己', '亥', self.WEIGHTS, metal, layer='luck', transits='phases')

    def test_bands_and_rounding(self) -> None:
        # Exact thousandths, half away from zero: 1.495 is 1.50, strongly supportive.
        weights = dict.fromkeys(ELEMENTS, 1.0)
        found = pull('甲', '子', weights, EVEN, layer='day', transits='phases')
        self.assertEqual(found['score'], 2.0)
        self.assertEqual(found['band'], 'strongly_supportive')

    def test_the_counts_follow_the_hidden_stem_table(self) -> None:
        for branch, hidden in hidden_stems_lookup().items():
            with self.subTest(branch=branch):
                found = pull(
                    '甲',
                    branch,
                    dict.fromkeys(ELEMENTS, 1.0),
                    EVEN,
                    layer='day',
                    transits='phases',
                )
                self.assertEqual([part['char'] for part in found['parts'][1:]], hidden)
                self.assertEqual(
                    [part['factor'] for part in found['parts'][1:]],
                    [1.0, 0.4, 0.2][: len(hidden)],
                )


class TestCatalog(unittest.TestCase):
    def test_every_preset_with_both_languages_its_sources_and_one_default(self) -> None:
        catalog = school_catalog()
        self.assertTrue(catalog['finnish_provisional'])
        listed = {
            setting['id']: [preset['id'] for preset in setting['presets']]
            for setting in catalog['settings']
        }
        self.assertEqual(
            listed,
            {
                'favourable': list(FAVOURABLE_SCHOOLS),
                'season': list(SEASON_SCHOOLS),
                'transits': list(TRANSIT_SCHOOLS),
            },
        )
        self.assertNotIn('structure', listed['favourable'])
        for setting in catalog['settings']:
            defaults = [preset for preset in setting['presets'] if preset['default']]
            self.assertEqual(len(defaults), 1)
            for preset in setting['presets']:
                with self.subTest(preset=preset['id']):
                    for text in (preset['name'], preset['summary']):
                        self.assertTrue(text['fi'] and text['en'])
                    self.assertTrue(preset['sources'])
                    han = preset['han']
                    if han is not None:
                        # Characters never stand alone, and pinyin has no tone marks.
                        self.assertTrue(han['chinese'] and han['pinyin'])
                        self.assertTrue(han['pinyin'].isascii())


if __name__ == '__main__':
    unittest.main()
