"""What GET /api/schools says of each school: the three settings and their presets, in
Finnish and English, with their sources and their defaults (docs/Today.md).

The Finnish names and summaries are provisional until confirmed.
"""

from typing import Final, Literal

from typing_extensions import TypedDict

from eight_characters.school_presets import (
    DEFAULT_FAVOURABLE,
    DEFAULT_SEASON,
    DEFAULT_TRANSITS,
    FAVOURABLE_SCHOOLS,
    SEASON_SCHOOLS,
    TRANSIT_SCHOOLS,
)

SettingName = Literal['favourable', 'season', 'transits']


class Text(TypedDict):
    fi: str
    en: str


class Han(TypedDict):
    # Characters never stand alone: each carries its pinyin.
    chinese: str
    pinyin: str


class Preset(TypedDict):
    id: str
    name: Text
    han: Han | None
    summary: Text
    sources: list[str]
    default: bool


class Setting(TypedDict):
    id: SettingName
    name: Text
    question: Text
    presets: list[Preset]


class Catalog(TypedDict):
    # Finnish wording that still awaits confirmation.
    finnish_provisional: bool
    settings: list[Setting]


def _preset(
    preset_id: str,
    default: str,
    name: Text,
    han: Han | None,
    summary: Text,
    sources: list[str],
) -> Preset:
    return {
        'id': preset_id,
        'name': name,
        'han': han,
        'summary': summary,
        'sources': sources,
        'default': preset_id == default,
    }


_FAVOURABLE: Final = [
    _preset(
        'support',
        DEFAULT_FAVOURABLE,
        {'fi': 'Tue ja hillitse', 'en': 'Support and restrain'},
        {'chinese': '扶抑', 'pinyin': 'Fu Yi'},
        {
            'fi': 'Mittaa Päivän mestarin voiman syntymän vuodenajassa ja etsii '
            'vahvimman sitä vastustavan voiman, taudin. Tautia hillitsevästä '
            'elementistä tulee hyödyllinen elementti. Kartta, jolla ei ole lainkaan '
            'tukea, seuraa vahvinta voimaansa.',
            'en': "Measures the Day Master's strength in the birth season and finds "
            'the strongest force against it, the disease. What controls the disease '
            'becomes the useful element. A chart with no support at all follows its '
            'strongest force.',
        },
        [
            'Di Tian Sui, 體用 Ti Yong (要在扶之抑之得其宜)',
            'Zhang Nan, Shen Feng Tong Kao, 病藥說 Bing Yao Shuo',
        ],
    ),
    _preset(
        'climate',
        DEFAULT_FAVOURABLE,
        {'fi': 'Ilmasto', 'en': 'Climate'},
        {'chinese': '调候', 'pinyin': 'Tiao Hou'},
        {
            'fi': 'Ottaa rungot, jotka Qiong Tong Bao Jian nimeää Päivän mestarille '
            'sen syntymäkuussa: lämpöä talvella syntyneelle, vettä kesällä '
            'syntyneelle.',
            'en': 'Takes the stems Qiong Tong Bao Jian names for the Day Master in its '
            'birth month: warmth for a winter birth, water for a summer one.',
        },
        ['Qiong Tong Bao Jian (Yu Chuntai, Qing)'],
    ),
]
_SEASON: Final = [
    _preset(
        'eighteen',
        DEFAULT_SEASON,
        {'fi': 'Maan 18 päivää', 'en': "Earth's 18 days"},
        {'chinese': '土王', 'pinyin': 'Tu Wang'},
        {
            'fi': 'Maa hallitsee auringon viimeiset 18 astetta ennen kunkin '
            'vuodenajan alkua, noin 18 päivää, joten jokainen elementti hallitsee '
            'viidenneksen vuodesta.',
            'en': "Earth rules the sun's last 18 degrees before each season begins, "
            'about 18 days, so every element rules a fifth of the year.',
        },
        [
            'Bai Hu Tong (土王四季，各十八日)',
            'Su Wen, chapter 29',
            'Xie Ji Bian Fang Shu',
            'San Ming Tong Hui, juan 2',
        ],
    ),
    _preset(
        'months',
        DEFAULT_SEASON,
        {'fi': 'Maan kuukaudet', 'en': 'Earth months'},
        None,
        {
            'fi': 'Lohikäärmeen, vuohen, koiran ja härän kuukaudet kuuluvat '
            'kokonaan maalle.',
            'en': "The Dragon, Goat, Dog and Ox months are Earth's, whole.",
        },
        ['Huainanzi, Tian Wen Xun (戊己四季，土也)'],
    ),
    _preset(
        'late_summer',
        DEFAULT_SEASON,
        {'fi': 'Vain loppukesä', 'en': 'Late summer only'},
        None,
        {
            'fi': 'Maa hallitsee vain vuohen kuukautta.',
            'en': 'Earth rules the Goat month alone.',
        },
        ['Huainanzi, Shi Ze Xun', 'Wu Xing Da Yi (六月則土王)'],
    ),
    _preset(
        'commander',
        DEFAULT_SEASON,
        {'fi': 'Kuukauden komentaja', 'en': "The month's commander"},
        {'chinese': '人元司令', 'pinyin': 'Ren Yuan Si Ling'},
        {
            'fi': 'Kuukautta komentava hallitsee, päivinä kuukauden aurinkotermistä '
            'laskien, San Ming Tong Huin taulukon mukaan.',
            'en': 'What commands the month rules, by the days since its solar term, as '
            "San Ming Tong Hui's table gives them.",
        },
        ['San Ming Tong Hui, juan 2, 論人元司事 Lun Ren Yuan Si Shi'],
    ),
]
_TRANSITS: Final = [
    _preset(
        'phases',
        DEFAULT_TRANSITS,
        {'fi': 'Vaiheittain', 'en': 'By phase'},
        None,
        {
            'fi': 'Onnenpilarin runko lasketaan sen viitenä ensimmäisenä vuonna, haara '
            'kaikkina kymmenenä. Vuoden haara lasketaan puolella painolla.',
            'en': "A luck pillar's stem counts in its first five years, its branch in "
            'all ten. The year counts its branch at half.',
        },
        [
            'San Ming Tong Hui, juan 2, on luck (在干兼用地支之神，在支則棄天干之物)',
            'Di Tian Sui, original notes (太歲……故重天干)',
        ],
    ),
    _preset(
        'whole',
        DEFAULT_TRANSITS,
        {'fi': 'Kymmenen vuotta yhtenä', 'en': 'Ten years as one'},
        None,
        {
            'fi': 'Onnenpilari luetaan yhtenä kymmenen vuoden kokonaisuutena: haara '
            'täysin, runko puolella painolla.',
            'en': 'A luck pillar counts as one ten-year whole: its branch in full, its '
            'stem at half.',
        },
        ['Di Tian Sui, original notes (大運……故重地支，未嘗無天干)'],
    ),
    _preset(
        'seasoned',
        DEFAULT_TRANSITS,
        {'fi': 'Kuin päivä', 'en': 'As the day'},
        None,
        {
            'fi': 'Vuosi ja onnenpilari lasketaan kuten päivä, tämän kuun vuodenajan '
            'mukaan.',
            'en': 'The year and the luck pillar count as the day does, by this '
            "month's season.",
        },
        ['Xie Ji Bian Fang Shu, juan 34 (日之衰旺全看月令)'],
    ),
]


def school_catalog() -> Catalog:
    settings: list[Setting] = [
        {
            'id': 'favourable',
            'name': {'fi': 'Suotuisat elementit', 'en': 'Favourable elements'},
            'question': {
                'fi': 'Mitkä elementit ravitsevat sinua ja mitkä kuluttavat?',
                'en': 'Which elements feed you, and which drain you?',
            },
            'presets': list(_FAVOURABLE),
        },
        {
            'id': 'season',
            'name': {'fi': 'Maan vuodenaika', 'en': "Earth's season"},
            'question': {
                'fi': 'Mikä osa vuodesta kuuluu maalle?',
                'en': 'Which part of the year belongs to Earth?',
            },
            'presets': list(_SEASON),
        },
        {
            'id': 'transits',
            'name': {
                'fi': 'Vuosi ja onnenpilari',
                'en': 'The year and the luck pillar',
            },
            'question': {
                'fi': 'Miten vuosi ja onnenpilari lasketaan?',
                'en': 'How do the year and your luck pillar count?',
            },
            'presets': list(_TRANSITS),
        },
    ]
    listed = {
        'favourable': [preset['id'] for preset in _FAVOURABLE],
        'season': [preset['id'] for preset in _SEASON],
        'transits': [preset['id'] for preset in _TRANSITS],
    }
    if listed != {
        'favourable': list(FAVOURABLE_SCHOOLS),
        'season': list(SEASON_SCHOOLS),
        'transits': list(TRANSIT_SCHOOLS),
    }:
        raise RuntimeError('The catalogue does not list exactly the schools offered.')
    return {'finnish_provisional': True, 'settings': settings}
