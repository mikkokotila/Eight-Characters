import csv
import random
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from lunar_python import Solar
from lunar_python.util import LunarUtil

import eight_characters
from eight_characters.data import STEMS
from eight_characters.evolution.primitives import TEN_GOD_LABELS, ten_god_index
from eight_characters.main import (
    ELEMENT_INDEX_BY_NAME,
    MAPPINGS_DIR,
    HiddenStemsRequest,
    _build_ten_gods_result,
    app,
)
from eight_characters.ten_gods import DAY_MASTER, TEN_GOD_NAMES, parse_ten_gods_mapping

TEN_GODS_MAPPING_PATH = MAPPINGS_DIR / 'ten-gods.csv'

TEN_GOD_BY_PRIMITIVE_LABEL = {
    'Companion': 'friend',
    'Rob Wealth': 'rob_wealth',
    'Eating God': 'eating_god',
    'Hurting Officer': 'hurting_officer',
    'Indirect Wealth': 'indirect_wealth',
    'Direct Wealth': 'direct_wealth',
    'Seven Killings': 'seven_killings',
    'Direct Officer': 'direct_officer',
    'Indirect Resource': 'indirect_resource',
    'Direct Resource': 'direct_resource',
}

TEN_GOD_BY_LUNAR_NAME = {
    '比肩': 'friend',
    '劫财': 'rob_wealth',
    '食神': 'eating_god',
    '伤官': 'hurting_officer',
    '偏财': 'indirect_wealth',
    '正财': 'direct_wealth',
    '七杀': 'seven_killings',
    '正官': 'direct_officer',
    '偏印': 'indirect_resource',
    '正印': 'direct_resource',
    '日主': DAY_MASTER,
}

CANONICAL_LOCATION = {
    'timezone': 'Asia/Shanghai',
    'longitude': 104.066,
    'latitude': 30.658,
}


def _polarity_bit(polarity: str) -> int:
    return 1 if polarity == 'Yang' else 0


class TestTenGodsMapping(unittest.TestCase):
    def test_mapping_covers_every_stem_pair(self) -> None:
        lookup = parse_ten_gods_mapping(TEN_GODS_MAPPING_PATH)
        self.assertEqual(
            set(lookup),
            {(day_master, target) for day_master in STEMS for target in STEMS},
        )
        self.assertEqual(set(lookup.values()), set(TEN_GOD_NAMES))

    def test_mapping_matches_evolution_primitives(self) -> None:
        lookup = parse_ten_gods_mapping(TEN_GODS_MAPPING_PATH)
        for day_master_char, day_master in STEMS.items():
            for target_char, target in STEMS.items():
                primitive_index = ten_god_index(
                    entity_element_index=ELEMENT_INDEX_BY_NAME[target['element']],
                    entity_polarity=_polarity_bit(target['polarity']),
                    center_element_index=ELEMENT_INDEX_BY_NAME[day_master['element']],
                    center_polarity=_polarity_bit(day_master['polarity']),
                )
                with self.subTest(day_master=day_master_char, target=target_char):
                    self.assertEqual(
                        lookup[(day_master_char, target_char)],
                        TEN_GOD_BY_PRIMITIVE_LABEL[TEN_GOD_LABELS[primitive_index]],
                    )

    def test_mapping_matches_lunar_python_reference(self) -> None:
        lookup = parse_ten_gods_mapping(TEN_GODS_MAPPING_PATH)
        self.assertEqual(len(LunarUtil.SHI_SHEN), len(lookup))
        for day_master_char in STEMS:
            for target_char in STEMS:
                with self.subTest(day_master=day_master_char, target=target_char):
                    self.assertEqual(
                        lookup[(day_master_char, target_char)],
                        TEN_GOD_BY_LUNAR_NAME[
                            LunarUtil.SHI_SHEN[day_master_char + target_char]
                        ],
                    )

    def test_hidden_stems_match_lunar_python_reference(self) -> None:
        client = TestClient(app)
        for pillar_texts in (
            ('甲子', '乙丑', '丙寅', '丁卯'),
            ('戊辰', '己巳', '庚午', '辛未'),
            ('壬申', '癸酉', '甲戌', '乙亥'),
        ):
            response = client.post(
                '/api/hidden_stems',
                json={
                    'year_pillar': pillar_texts[0],
                    'month_pillar': pillar_texts[1],
                    'day_pillar': pillar_texts[2],
                    'hour_pillar': pillar_texts[3],
                },
            )
            self.assertEqual(response.status_code, 200)
            for pillar_payload in response.json()['hidden_stems'].values():
                branch_char = pillar_payload['branch']
                with self.subTest(branch=branch_char):
                    self.assertEqual(
                        [entry['char'] for entry in pillar_payload['hidden_stems']],
                        LunarUtil.ZHI_HIDE_GAN[branch_char],
                    )


class TestTenGodsTranslations(unittest.TestCase):
    def test_every_ten_god_has_finnish_and_english_labels(self) -> None:
        localization_path = (
            Path(eight_characters.__file__).parent / 'static' / 'localization.js'
        )
        source = localization_path.read_text(encoding='utf-8')
        fi_block, en_block = source.split('\n    en: {\n', 1)
        for name in (*TEN_GOD_NAMES, DAY_MASTER):
            for lang, block in (('fi', fi_block), ('en', en_block)):
                with self.subTest(lang=lang, ten_god=name):
                    self.assertRegex(block, rf"\n\s+ten_god_{name}: '[^']+',\n")


class TestTenGodsMappingValidation(unittest.TestCase):
    def setUp(self) -> None:
        with TEN_GODS_MAPPING_PATH.open('r', encoding='utf-8', newline='') as csv_file:
            self.rows = list(csv.reader(csv_file))
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.csv_path = Path(temp_dir.name) / 'ten-gods.csv'

    def _parse(self, rows: list[list[str]]) -> None:
        with self.csv_path.open('w', encoding='utf-8', newline='') as csv_file:
            csv.writer(csv_file, lineterminator='\n').writerows(rows)
        parse_ten_gods_mapping(self.csv_path)

    def test_canonical_rows_roundtrip(self) -> None:
        self._parse(self.rows)

    def test_rejects_missing_file(self) -> None:
        with self.assertRaisesRegex(RuntimeError, 'not found'):
            parse_ten_gods_mapping(self.csv_path)

    def test_rejects_empty_file(self) -> None:
        with self.assertRaisesRegex(RuntimeError, 'empty'):
            self._parse([])

    def test_rejects_unknown_ten_god_label(self) -> None:
        self.rows[1][1] = 'Frend'
        with self.assertRaisesRegex(RuntimeError, 'Unknown ten god label'):
            self._parse(self.rows)

    def test_rejects_transposed_orientation(self) -> None:
        self.rows[0][0] = 'Target \\ Day Master'
        with self.assertRaisesRegex(RuntimeError, 'oriented'):
            self._parse(self.rows)

    def test_rejects_header_contradicting_stem_data(self) -> None:
        self.rows[0][1] = 'Jia (-Wood)'
        with self.assertRaisesRegex(RuntimeError, 'contradicts'):
            self._parse(self.rows)

    def test_rejects_unknown_stem_header(self) -> None:
        self.rows[2][0] = 'Zi (+Water)'
        with self.assertRaisesRegex(RuntimeError, 'Unknown stem'):
            self._parse(self.rows)

    def test_rejects_missing_column(self) -> None:
        rows = [row[:-1] for row in self.rows]
        with self.assertRaisesRegex(RuntimeError, 'columns must list every stem'):
            self._parse(rows)

    def test_rejects_ragged_row(self) -> None:
        self.rows[3] = self.rows[3][:-1]
        with self.assertRaisesRegex(RuntimeError, 'cells'):
            self._parse(self.rows)

    def test_rejects_duplicate_day_master_row(self) -> None:
        self.rows[2] = list(self.rows[1])
        with self.assertRaisesRegex(RuntimeError, 'rows must list every stem'):
            self._parse(self.rows)

    def test_rejects_row_repeating_a_ten_god(self) -> None:
        self.rows[1][2] = self.rows[1][1]
        with self.assertRaisesRegex(RuntimeError, 'each ten god exactly once'):
            self._parse(self.rows)


class TestFourPillarsTenGods(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def _four_pillars(self, **flags: bool) -> dict[str, Any]:
        response = self.client.post(
            '/api/four_pillars',
            json={
                'date': '1988-02-04',
                'time': '16:30:00',
                'location': CANONICAL_LOCATION,
                **flags,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_ten_gods_are_opt_in(self) -> None:
        payload = self._four_pillars(include_chart=True, include_hidden_stems=True)
        self.assertNotIn('ten_gods', payload)

    def test_canonical_chart_ten_gods(self) -> None:
        payload = self._four_pillars(include_ten_gods=True)
        self.assertNotIn('hidden_stems', payload)
        self.assertEqual(
            payload['ten_gods'],
            {
                'year': {
                    'pillar': '丁卯',
                    'stem': {
                        'char': '丁',
                        'element': 'fire',
                        'polarity': 'Yin',
                        'ten_god': 'indirect_resource',
                    },
                    'branch': '卯',
                    'hidden_stems': [
                        {
                            'char': '乙',
                            'element': 'wood',
                            'polarity': 'Yin',
                            'qi_type': 'main',
                            'ten_god': 'seven_killings',
                        },
                    ],
                },
                'month': {
                    'pillar': '癸丑',
                    'stem': {
                        'char': '癸',
                        'element': 'water',
                        'polarity': 'Yin',
                        'ten_god': 'indirect_wealth',
                    },
                    'branch': '丑',
                    'hidden_stems': [
                        {
                            'char': '己',
                            'element': 'earth',
                            'polarity': 'Yin',
                            'qi_type': 'main',
                            'ten_god': 'friend',
                        },
                        {
                            'char': '癸',
                            'element': 'water',
                            'polarity': 'Yin',
                            'qi_type': 'middle',
                            'ten_god': 'indirect_wealth',
                        },
                        {
                            'char': '辛',
                            'element': 'metal',
                            'polarity': 'Yin',
                            'qi_type': 'residual',
                            'ten_god': 'eating_god',
                        },
                    ],
                },
                'day': {
                    'pillar': '己丑',
                    'stem': {
                        'char': '己',
                        'element': 'earth',
                        'polarity': 'Yin',
                        'ten_god': 'day_master',
                    },
                    'branch': '丑',
                    'hidden_stems': [
                        {
                            'char': '己',
                            'element': 'earth',
                            'polarity': 'Yin',
                            'qi_type': 'main',
                            'ten_god': 'friend',
                        },
                        {
                            'char': '癸',
                            'element': 'water',
                            'polarity': 'Yin',
                            'qi_type': 'middle',
                            'ten_god': 'indirect_wealth',
                        },
                        {
                            'char': '辛',
                            'element': 'metal',
                            'polarity': 'Yin',
                            'qi_type': 'residual',
                            'ten_god': 'eating_god',
                        },
                    ],
                },
                'hour': {
                    'pillar': '壬申',
                    'stem': {
                        'char': '壬',
                        'element': 'water',
                        'polarity': 'Yang',
                        'ten_god': 'direct_wealth',
                    },
                    'branch': '申',
                    'hidden_stems': [
                        {
                            'char': '庚',
                            'element': 'metal',
                            'polarity': 'Yang',
                            'qi_type': 'main',
                            'ten_god': 'hurting_officer',
                        },
                        {
                            'char': '壬',
                            'element': 'water',
                            'polarity': 'Yang',
                            'qi_type': 'middle',
                            'ten_god': 'direct_wealth',
                        },
                        {
                            'char': '戊',
                            'element': 'earth',
                            'polarity': 'Yang',
                            'qi_type': 'residual',
                            'ten_god': 'rob_wealth',
                        },
                    ],
                },
            },
        )

    def test_ten_gods_leave_hidden_stems_payload_unchanged(self) -> None:
        hidden_only = self._four_pillars(include_hidden_stems=True)
        combined = self._four_pillars(include_hidden_stems=True, include_ten_gods=True)
        self.assertEqual(combined['hidden_stems'], hidden_only['hidden_stems'])
        for pillar_payload in combined['hidden_stems'].values():
            for entry in pillar_payload['hidden_stems']:
                self.assertNotIn('ten_god', entry)

    def test_ten_gods_follow_hidden_stems_of_each_pillar(self) -> None:
        payload = self._four_pillars(include_hidden_stems=True, include_ten_gods=True)
        for pillar_name, hidden_payload in payload['hidden_stems'].items():
            ten_god_entries = payload['ten_gods'][pillar_name]['hidden_stems']
            with self.subTest(pillar=pillar_name):
                self.assertEqual(
                    [
                        {key: entry[key] for key in entry if key != 'ten_god'}
                        for entry in ten_god_entries
                    ],
                    hidden_payload['hidden_stems'],
                )

    def test_ten_gods_match_lunar_python_eight_char(self) -> None:
        rng = random.Random(10)
        for _ in range(300):
            eight_char = (
                Solar.fromYmdHms(
                    rng.randint(1900, 2100),
                    rng.randint(1, 12),
                    rng.randint(1, 28),
                    rng.randint(0, 23),
                    rng.randint(0, 59),
                    rng.randint(0, 59),
                )
                .getLunar()
                .getEightChar()
            )
            result = _build_ten_gods_result(
                HiddenStemsRequest(
                    year_pillar=eight_char.getYear(),
                    month_pillar=eight_char.getMonth(),
                    day_pillar=eight_char.getDay(),
                    hour_pillar=eight_char.getTime(),
                )
            )
            expected = {
                'year': (
                    eight_char.getYearShiShenGan(),
                    eight_char.getYearShiShenZhi(),
                ),
                'month': (
                    eight_char.getMonthShiShenGan(),
                    eight_char.getMonthShiShenZhi(),
                ),
                'day': (eight_char.getDayShiShenGan(), eight_char.getDayShiShenZhi()),
                'hour': (
                    eight_char.getTimeShiShenGan(),
                    eight_char.getTimeShiShenZhi(),
                ),
            }
            for pillar_name, (stem_reference, branch_reference) in expected.items():
                with self.subTest(eight_char=str(eight_char), pillar=pillar_name):
                    self.assertEqual(
                        result[pillar_name]['stem']['ten_god'],
                        TEN_GOD_BY_LUNAR_NAME[stem_reference],
                    )
                    self.assertEqual(
                        [
                            entry['ten_god']
                            for entry in result[pillar_name]['hidden_stems']
                        ],
                        [TEN_GOD_BY_LUNAR_NAME[name] for name in branch_reference],
                    )


if __name__ == '__main__':
    unittest.main()
