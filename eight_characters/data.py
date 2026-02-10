# ── Trigram line patterns (top-to-bottom: line3, line2, line1) ──
# L = solid, B = broken

TRIGRAM_LINES = {
    'Zhen': ['B', 'B', 'L'],   # ☳ Thunder
    'Xun':  ['L', 'L', 'B'],   # ☴ Wind
    'Li':   ['L', 'B', 'L'],   # ☲ Fire
    'Gen':  ['L', 'B', 'B'],   # ☶ Mountain
    'Kun':  ['B', 'B', 'B'],   # ☷ Earth
    'Qian': ['L', 'L', 'L'],   # ☰ Heaven
    'Dui':  ['B', 'L', 'L'],   # ☱ Lake
    'Kan':  ['B', 'L', 'B'],   # ☵ Water
}

# ── Hexagram line patterns (twelve sovereign hexagrams, top-to-bottom) ──

HEXAGRAM_LINES = {
    'Fu':        ['B', 'B', 'B', 'B', 'B', 'L'],  # #24 Returning
    'Lin':       ['B', 'B', 'B', 'B', 'L', 'L'],  # #19 Approach
    'Tai':       ['B', 'B', 'B', 'L', 'L', 'L'],  # #11 Peace
    'Dazhuang':  ['B', 'B', 'L', 'L', 'L', 'L'],  # #34 Great Power
    'Guai':      ['B', 'L', 'L', 'L', 'L', 'L'],  # #43 Breakthrough
    'Qian':      ['L', 'L', 'L', 'L', 'L', 'L'],  # #1  Heaven
    'Gou':       ['L', 'L', 'L', 'L', 'L', 'B'],  # #44 Coming to Meet
    'Dun':       ['L', 'L', 'L', 'L', 'B', 'B'],  # #33 Retreat
    'Pi':        ['L', 'L', 'L', 'B', 'B', 'B'],  # #12 Stagnation
    'Guan':      ['L', 'L', 'B', 'B', 'B', 'B'],  # #20 Contemplation
    'Bo':        ['L', 'B', 'B', 'B', 'B', 'B'],  # #23 Stripping Away
    'Kun':       ['B', 'B', 'B', 'B', 'B', 'B'],  # #2  Earth
}


# ── Heavenly Stems (天干) ──

STEMS = {
    '甲': {
        'pinyin': 'Jia', 'element': 'wood', 'polarity': 'Yang',
        'trigram': 'Zhen', 'element_fi': 'Puu',
    },
    '乙': {
        'pinyin': 'Yi', 'element': 'wood', 'polarity': 'Yin',
        'trigram': 'Xun', 'element_fi': 'Puu',
    },
    '丙': {
        'pinyin': 'Bing', 'element': 'fire', 'polarity': 'Yang',
        'trigram': 'Li', 'element_fi': 'Tuli',
    },
    '丁': {
        'pinyin': 'Ding', 'element': 'fire', 'polarity': 'Yin',
        'trigram': 'Li', 'element_fi': 'Tuli',
    },
    '戊': {
        'pinyin': 'Wu', 'element': 'earth', 'polarity': 'Yang',
        'trigram': 'Gen', 'element_fi': 'Maa',
    },
    '己': {
        'pinyin': 'Ji', 'element': 'earth', 'polarity': 'Yin',
        'trigram': 'Kun', 'element_fi': 'Maa',
    },
    '庚': {
        'pinyin': 'Geng', 'element': 'metal', 'polarity': 'Yang',
        'trigram': 'Qian', 'element_fi': 'Metalli',
    },
    '辛': {
        'pinyin': 'Xin', 'element': 'metal', 'polarity': 'Yin',
        'trigram': 'Dui', 'element_fi': 'Metalli',
    },
    '壬': {
        'pinyin': 'Ren', 'element': 'water', 'polarity': 'Yang',
        'trigram': 'Kan', 'element_fi': 'Vesi',
    },
    '癸': {
        'pinyin': 'Gui', 'element': 'water', 'polarity': 'Yin',
        'trigram': 'Kan', 'element_fi': 'Vesi',
    },
}


# ── Earthly Branches (地支) ──

BRANCHES = {
    '子': {
        'pinyin': 'Zi', 'animal': 'Rat', 'element': 'water',
        'polarity': 'Yang', 'hexagram': 'Fu',
        'animal_fi': 'Rotta', 'element_fi': 'Vesi',
    },
    '丑': {
        'pinyin': 'Chou', 'animal': 'Ox', 'element': 'earth',
        'polarity': 'Yin', 'hexagram': 'Lin',
        'animal_fi': 'Härkä', 'element_fi': 'Maa',
    },
    '寅': {
        'pinyin': 'Yin', 'animal': 'Tiger', 'element': 'wood',
        'polarity': 'Yang', 'hexagram': 'Tai',
        'animal_fi': 'Tiikeri', 'element_fi': 'Puu',
    },
    '卯': {
        'pinyin': 'Mao', 'animal': 'Rabbit', 'element': 'wood',
        'polarity': 'Yin', 'hexagram': 'Dazhuang',
        'animal_fi': 'Jänis', 'element_fi': 'Puu',
    },
    '辰': {
        'pinyin': 'Chen', 'animal': 'Dragon', 'element': 'earth',
        'polarity': 'Yang', 'hexagram': 'Guai',
        'animal_fi': 'Lohikäärme', 'element_fi': 'Maa',
    },
    '巳': {
        'pinyin': 'Si', 'animal': 'Snake', 'element': 'fire',
        'polarity': 'Yin', 'hexagram': 'Qian',
        'animal_fi': 'Käärme', 'element_fi': 'Tuli',
    },
    '午': {
        'pinyin': 'Wu', 'animal': 'Horse', 'element': 'fire',
        'polarity': 'Yang', 'hexagram': 'Gou',
        'animal_fi': 'Hevonen', 'element_fi': 'Tuli',
    },
    '未': {
        'pinyin': 'Wei', 'animal': 'Goat', 'element': 'earth',
        'polarity': 'Yin', 'hexagram': 'Dun',
        'animal_fi': 'Vuohi', 'element_fi': 'Maa',
    },
    '申': {
        'pinyin': 'Shen', 'animal': 'Monkey', 'element': 'metal',
        'polarity': 'Yang', 'hexagram': 'Pi',
        'animal_fi': 'Apina', 'element_fi': 'Metalli',
    },
    '酉': {
        'pinyin': 'You', 'animal': 'Rooster', 'element': 'metal',
        'polarity': 'Yin', 'hexagram': 'Guan',
        'animal_fi': 'Kukko', 'element_fi': 'Metalli',
    },
    '戌': {
        'pinyin': 'Xu', 'animal': 'Dog', 'element': 'earth',
        'polarity': 'Yang', 'hexagram': 'Bo',
        'animal_fi': 'Koira', 'element_fi': 'Maa',
    },
    '亥': {
        'pinyin': 'Hai', 'animal': 'Pig', 'element': 'water',
        'polarity': 'Yin', 'hexagram': 'Kun',
        'animal_fi': 'Sika', 'element_fi': 'Vesi',
    },
}


# ── Finnish month names ──

MONTHS_FI = [
    'Tammikuu', 'Helmikuu', 'Maaliskuu', 'Huhtikuu',
    'Toukokuu', 'Kesäkuu', 'Heinäkuu', 'Elokuu',
    'Syyskuu', 'Lokakuu', 'Marraskuu', 'Joulukuu',
]


# ── Pillar labels (Finnish) ──

MONTHS_EN = [
    'January', 'February', 'March', 'April',
    'May', 'June', 'July', 'August',
    'September', 'October', 'November', 'December',
]


PILLAR_LABELS = {
    'fi': {
        'hour': 'Teon portti',
        'day': 'Sisäinen valo',
        'month': 'Sisäinen vuodenaika',
        'year': 'Elämän kenttä',
    },
    'en': {
        'hour': 'Action gate',
        'day': 'Inner light',
        'month': 'Inner season',
        'year': 'Life field',
    },
}


ELEMENT_NAMES = {
    'fi': {
        'wood': 'Puu',
        'fire': 'Tuli',
        'earth': 'Maa',
        'metal': 'Metalli',
        'water': 'Vesi',
    },
    'en': {
        'wood': 'Wood',
        'fire': 'Fire',
        'earth': 'Earth',
        'metal': 'Metal',
        'water': 'Water',
    },
}


def _resolve_lang(lang):
    return lang if lang in ('fi', 'en') else 'fi'


def _header_text(lang, day, month_value, year, time_value):
    if lang == 'en':
        return f'{month_value} {day}, {year} · {time_value}'
    return f'{day}. {month_value.lower()}ta {year} · {time_value}'


def build_stem_data(char, lang='fi'):
    '''Return full stem rendering data for a Chinese character.'''
    active_lang = _resolve_lang(lang)
    stem = STEMS[char]
    element_label = ELEMENT_NAMES[active_lang][stem['element']]
    return {
        'char': char,
        'pinyin': stem['pinyin'],
        'element': stem['element'],
        'polarity': stem['polarity'],
        'label': f'{stem["polarity"]} {element_label}',
        'lines': TRIGRAM_LINES[stem['trigram']],
    }


def build_branch_data(char, lang='fi'):
    '''Return full branch rendering data for a Chinese character.'''
    active_lang = _resolve_lang(lang)
    branch = BRANCHES[char]
    element_label = ELEMENT_NAMES[active_lang][branch['element']]
    animal_name = branch['animal_fi'] if active_lang == 'fi' else branch['animal']
    return {
        'char': char,
        'pinyin': branch['pinyin'],
        'element': branch['element'],
        'polarity': branch['polarity'],
        'animal_name': animal_name,
        'animal_fi': animal_name,
        'element_label': f'{branch["polarity"]} {element_label}',
        'lines': HEXAGRAM_LINES[branch['hexagram']],
    }


def build_chart(date_str, time_str,
                hour_stem, hour_branch,
                day_stem, day_branch,
                month_stem, month_branch,
                year_stem, year_branch,
                lang='fi'):
    '''Build complete chart data for the frontend.'''
    active_lang = _resolve_lang(lang)

    # Parse date for display
    parts = date_str.split('-')
    year = int(parts[0])
    month = int(parts[1])
    day = int(parts[2])
    month_name = MONTHS_FI[month - 1] if active_lang == 'fi' else MONTHS_EN[month - 1]

    return {
        'header': _header_text(active_lang, day, month_name, year, time_str),
        'pillars': [
            {
                'label': PILLAR_LABELS[active_lang]['hour'],
                'value': time_str,
                'stem': build_stem_data(hour_stem, lang=active_lang),
                'branch': build_branch_data(hour_branch, lang=active_lang),
            },
            {
                'label': PILLAR_LABELS[active_lang]['day'],
                'value': str(day),
                'stem': build_stem_data(day_stem, lang=active_lang),
                'branch': build_branch_data(day_branch, lang=active_lang),
            },
            {
                'label': PILLAR_LABELS[active_lang]['month'],
                'value': month_name,
                'stem': build_stem_data(month_stem, lang=active_lang),
                'branch': build_branch_data(month_branch, lang=active_lang),
            },
            {
                'label': PILLAR_LABELS[active_lang]['year'],
                'value': str(year),
                'stem': build_stem_data(year_stem, lang=active_lang),
                'branch': build_branch_data(year_branch, lang=active_lang),
            },
        ],
    }
