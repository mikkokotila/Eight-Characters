"""The schools Today follows, and their rules.

Today weighs what a day, a month, a year and a luck pillar bring to a chart: each
element has a weight, from the chart's favourable elements, and the season sets
how much each element counts. Three settings choose the rules, each a school named
for the classics it comes from (school_presets.py):

- **Favourable elements**, which give each element its weight: support and
  restrain (扶抑 Fu Yi), the default, or climate (调候 Tiao Hou).
- **Earth's season**, which decides which element rules at a moment, and through it
  every element's standing (旺相休囚死): Earth's 18 days, the default; the Earth
  months; late summer only; or the month's commander.
- **The year and the luck pillar**: by phase, the default; ten years as one; or as
  the day.

The classics fix no numbers. The app's own are integers, so every result is exact
and the same on every machine: weights and factors in tenths, so a part is in
thousandths. They are shown rounded to two decimals, half away from zero.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal

from typing_extensions import TypedDict

from eight_characters.data import STEMS, ElementName
from eight_characters.mappings import hidden_stems_lookup
from eight_characters.school_presets import (
    FavourableSchool,
    SeasonSchool,
    TransitSchool,
)

# The five elements in the order each generates the next.
ELEMENTS: Final[tuple[ElementName, ...]] = ('wood', 'fire', 'earth', 'metal', 'water')
PILLAR_NAMES: Final = ('year', 'month', 'day', 'hour')
# A branch's hidden stems are counted in the order the mapping lists them: main qi,
# middle, residual.
QiName = Literal['main', 'middle', 'residual']
QI_NAMES: Final[tuple[QiName, ...]] = ('main', 'middle', 'residual')
# A visible stem counts in full; a hidden stem by its qi: 1.0, 0.4 or 0.2, in tenths.
STEM_TENTHS: Final = 10
QI_TENTHS: Final[dict[QiName, int]] = {'main': 10, 'middle': 4, 'residual': 2}


def element_of(stem: str) -> ElementName:
    return STEMS[stem]['element']


def generates(element: ElementName) -> ElementName:
    return ELEMENTS[(ELEMENTS.index(element) + 1) % 5]


def generator_of(element: ElementName) -> ElementName:
    return ELEMENTS[(ELEMENTS.index(element) - 1) % 5]


def controls(element: ElementName) -> ElementName:
    return ELEMENTS[(ELEMENTS.index(element) + 2) % 5]


def controller_of(element: ElementName) -> ElementName:
    return ELEMENTS[(ELEMENTS.index(element) - 2) % 5]


def rounded(thousandths: int) -> float:
    """An exact number of thousandths, rounded to two decimals, half away from zero."""
    return share(thousandths, 1000)


def share(part: int, whole: int, places: int = 2) -> float:
    """part / whole, exactly, rounded to `places` decimals, half away from zero."""
    if whole <= 0:
        raise ValueError('A share needs a positive whole.')
    step = Decimal(1).scaleb(-places)
    return float((Decimal(part) / Decimal(whole)).quantize(step, ROUND_HALF_UP))


# ── Standing in the season (旺相休囚死) ──

Standing = Literal['prosperous', 'supported', 'resting', 'imprisoned', 'dead']
STANDINGS: Final[tuple[Standing, ...]] = (
    'prosperous',
    'supported',
    'resting',
    'imprisoned',
    'dead',
)
# By the element's distance from the ruling one along the generating order: the
# ruler prospers (旺), what it generates is supported (相), what it controls is dead
# (死), what controls it is imprisoned (囚), and what generates it rests (休).
_STANDING_BY_DISTANCE: Final[tuple[Standing, ...]] = (
    'prosperous',
    'supported',
    'dead',
    'imprisoned',
    'resting',
)
# How much an element counts in each standing, in tenths: 1.2, 1.0, 0.6, 0.4, 0.2.
STANDING_TENTHS: Final[dict[Standing, int]] = {
    'prosperous': 12,
    'supported': 10,
    'resting': 6,
    'imprisoned': 4,
    'dead': 2,
}


def standings(ruler: ElementName) -> dict[ElementName, Standing]:
    """Each element's standing while `ruler` rules the season."""
    start = ELEMENTS.index(ruler)
    return {
        element: _STANDING_BY_DISTANCE[(ELEMENTS.index(element) - start) % 5]
        for element in ELEMENTS
    }


# ── Earth's season ──

# The element each month's season gives it, Earth months aside.
SEASON_OF_MONTH: Final[dict[str, ElementName]] = {
    **dict.fromkeys('寅卯辰', 'wood'),
    **dict.fromkeys('巳午未', 'fire'),
    **dict.fromkeys('申酉戌', 'metal'),
    **dict.fromkeys('亥子丑', 'water'),
}
EARTH_MONTHS: Final = '辰未戌丑'
LATE_SUMMER: Final = '未'
# Earth's 18 days: the 18 degrees of the sun's longitude before each season starts
# (立春 315°, 立夏 45°, 立秋 135°, 立冬 225°).
EARTH_DAYS_START: Final = 27.0
EARTH_DAYS_END: Final = 45.0


@dataclass(frozen=True)
class CommanderSpan:
    """A stretch of a month and what commands it, as San Ming Tong Hui names it."""

    # The text's two characters (a stem or a trigram, and its element).
    name: str
    pinyin: str
    english: str
    element: ElementName
    # Days from the month's jie; None for the last, which holds to the next jie.
    days: int | None


def _span(name: str, element: ElementName, days: int | None) -> CommanderSpan:
    pinyin = {
        '甲木': ('Jia Mu', 'Jia Wood'),
        '乙木': ('Yi Mu', 'Yi Wood'),
        '丙火': ('Bing Huo', 'Bing Fire'),
        '丁火': ('Ding Huo', 'Ding Fire'),
        '戊土': ('Wu Tu', 'Wu Earth'),
        '己土': ('Ji Tu', 'Ji Earth'),
        '庚金': ('Geng Jin', 'Geng Metal'),
        '辛金': ('Xin Jin', 'Xin Metal'),
        '壬水': ('Ren Shui', 'Ren Water'),
        '癸水': ('Gui Shui', 'Gui Water'),
        '艮土': ('Gen Tu', 'Gen Earth'),
        '坤土': ('Kun Tu', 'Kun Earth'),
    }[name]
    return CommanderSpan(name, pinyin[0], pinyin[1], element, days)


# San Ming Tong Hui, juan 2, 論人元司事: what commands each month, in order, with its
# days from the month's jie. The last holds to the next jie, however long the month
# is. The text writes 己 as 巳 in 未 and 丑, a slip of the brush its own hidden-stem
# lists correct.
COMMANDERS: Final[dict[str, tuple[CommanderSpan, ...]]] = {
    '寅': (
        _span('艮土', 'earth', 5),
        _span('丙火', 'fire', 5),
        _span('甲木', 'wood', None),
    ),
    '卯': (_span('甲木', 'wood', 7), _span('乙木', 'wood', None)),
    '辰': (
        _span('乙木', 'wood', 7),
        _span('壬水', 'water', 5),
        _span('戊土', 'earth', None),
    ),
    '巳': (
        _span('戊土', 'earth', 7),
        _span('庚金', 'metal', 5),
        _span('丙火', 'fire', None),
    ),
    '午': (_span('丙火', 'fire', 7), _span('丁火', 'fire', None)),
    '未': (
        _span('丁火', 'fire', 7),
        _span('甲木', 'wood', 5),
        _span('己土', 'earth', None),
    ),
    '申': (
        _span('坤土', 'earth', 5),
        _span('壬水', 'water', 5),
        _span('庚金', 'metal', None),
    ),
    '酉': (_span('庚金', 'metal', 7), _span('辛金', 'metal', None)),
    '戌': (
        _span('辛金', 'metal', 7),
        _span('丙火', 'fire', 5),
        _span('戊土', 'earth', None),
    ),
    '亥': (
        _span('戊土', 'earth', 5),
        _span('甲木', 'wood', 5),
        _span('壬水', 'water', None),
    ),
    '子': (_span('壬水', 'water', 7), _span('癸水', 'water', None)),
    '丑': (
        _span('癸水', 'water', 7),
        _span('庚金', 'metal', 5),
        _span('己土', 'earth', None),
    ),
}


class CommanderView(TypedDict):
    name: str
    pinyin: str
    english: str
    element: ElementName
    # The span's first day and the day after its last, from the month's jie (counted
    # from 0); `until` is None for the last span, which holds to the next jie.
    since: int
    until: int | None


class Season(TypedDict):
    school: SeasonSchool
    # The element that rules at the moment, and every element's standing in it.
    ruler: ElementName
    standings: dict[ElementName, Standing]
    # The span in command, for the month's commander; None for the other schools.
    commander: CommanderView | None


def commander(month_branch: str, days_since_jie: float) -> CommanderView:
    """What commands the month this many days (of 24 hours) after its jie."""
    if days_since_jie < 0:
        raise ValueError('A moment before its month began has no commander.')
    since = 0
    for span in COMMANDERS[month_branch]:
        if span.days is None or days_since_jie < since + span.days:
            return {
                'name': span.name,
                'pinyin': span.pinyin,
                'english': span.english,
                'element': span.element,
                'since': since,
                'until': None if span.days is None else since + span.days,
            }
        since += span.days
    raise AssertionError(f'The {month_branch} month has no last commander.')


def season_at(
    school: SeasonSchool,
    longitude_deg: float,
    month_branch: str,
    days_since_jie: float,
) -> Season:
    """The season at a moment, by the school: the sun's apparent longitude, the
    month's branch, and the days since the month's jie."""
    if not 0.0 <= longitude_deg < 360.0:
        raise ValueError("The sun's longitude must be in [0, 360).")
    if month_branch not in SEASON_OF_MONTH:
        raise ValueError(f'Not a branch: {month_branch!r}.')
    held: CommanderView | None = None
    if school == 'eighteen':
        if EARTH_DAYS_START <= longitude_deg % 90.0 < EARTH_DAYS_END:
            ruler: ElementName = 'earth'
        else:
            # Each season starts 45° after the start of its quarter of the circle,
            # counted from 立春 at 315°.
            ruler = ('wood', 'fire', 'metal', 'water')[
                int(((longitude_deg - 315.0) % 360.0) // 90.0)
            ]
    elif school == 'months':
        ruler = (
            'earth' if month_branch in EARTH_MONTHS else SEASON_OF_MONTH[month_branch]
        )
    elif school == 'late_summer':
        ruler = (
            'earth' if month_branch == LATE_SUMMER else SEASON_OF_MONTH[month_branch]
        )
    else:
        held = commander(month_branch, days_since_jie)
        ruler = held['element']
    return {
        'school': school,
        'ruler': ruler,
        'standings': standings(ruler),
        'commander': held,
    }


# ── Favourable elements ──

Strength = Literal['weak', 'strong', 'following']
# An element's weight in each place of the order, in tenths: the useful element,
# the favourable one, the disease, the next, the last.
WEIGHT_TENTHS: Final = (12, 10, -10, -8, -6)


class Tally(TypedDict):
    # Each element's count in the chart: its stems and hidden stems by their qi,
    # each scaled by its standing in the birth season. In hundredths.
    elements: dict[ElementName, float]
    # The Day Master's element and its Resource over the whole.
    supported_share: float


class Favourable(TypedDict):
    school: FavourableSchool
    weights: dict[ElementName, float]
    useful: ElementName
    favourable: ElementName
    disease: ElementName
    # Support and restrain: how strong the Day Master is, and the tally that says so.
    strength: Strength | None
    tally: Tally | None
    # Climate: the stems Qiong Tong Bao Jian names, in its order.
    named: list[str] | None


def _weights(order: Sequence[ElementName]) -> dict[ElementName, float]:
    if sorted(order) != sorted(ELEMENTS):
        raise AssertionError(f'Weights need each element once, not {order}.')
    return {
        element: tenths / 10
        for element, tenths in zip(order, WEIGHT_TENTHS, strict=True)
    }


def _first_free(
    candidates: Sequence[ElementName], taken: Sequence[ElementName]
) -> ElementName:
    return next(element for element in candidates if element not in taken)


def _support_order(
    useful: ElementName, favourable: ElementName, disease: ElementName
) -> list[ElementName]:
    """The rest of support and restrain's order: the disease's generator, or where
    that is taken, the controller of the useful element; then the one left."""
    taken: list[ElementName] = [useful, favourable, disease]
    second = _first_free([generator_of(disease), controller_of(useful)], taken)
    taken.append(second)
    return [*taken, _first_free(ELEMENTS, taken)]


def chart_tally(
    pillars: Mapping[str, tuple[str, str]],
    birth_standings: Mapping[ElementName, Standing],
) -> dict[ElementName, int]:
    """Each element's count in hundredths: every stem in full and every hidden stem
    by its qi, each times its element's standing in the birth season."""
    tally = dict.fromkeys(ELEMENTS, 0)
    for name in PILLAR_NAMES:
        stem, branch = pillars[name]
        element = element_of(stem)
        tally[element] += STEM_TENTHS * STANDING_TENTHS[birth_standings[element]]
        for hidden, qi in zip(hidden_stems_lookup()[branch], QI_NAMES, strict=False):
            element = element_of(hidden)
            tally[element] += QI_TENTHS[qi] * STANDING_TENTHS[birth_standings[element]]
    return tally


def _largest(
    tally: Mapping[ElementName, int], among: Sequence[ElementName]
) -> ElementName:
    """The element counted most among these; a tie goes to the first listed."""
    return max(among, key=lambda element: (tally[element], -among.index(element)))


def support_and_restrain(
    pillars: Mapping[str, tuple[str, str]],
    birth_standings: Mapping[ElementName, Standing],
) -> Favourable:
    """Support and restrain (扶抑 Fu Yi), after Di Tian Sui and Shen Feng Tong Kao.

    The chart is counted (_chart_tally). Its Day Master's element and Resource are
    its support; under half the count, the Day Master is weak.
    - Weak: the disease is the strongest of Output, Wealth and Officer. The useful
      element is the one that controls the disease, or the Resource when the disease
      is Officer, and the favourable element is the other of the two that support
      the Day Master.
    - Strong: the disease is the stronger of Companion and Resource, the useful
      element is the one that controls it, and the favourable element the one that
      generates the useful one.
    - Following: with no Companion or Resource anywhere but the Day Master itself,
      the chart follows its strongest force, the strongest of Output, Wealth and
      Officer: it is useful, and the element that generates it favourable (Wealth,
      when the force is Output, whose generator is the Day Master's own). The
      Resource, which would revive the Day Master, is the disease, then the
      Companion.
    Ties go to the first named.
    """
    day_master = pillars['day'][0]
    companion = element_of(day_master)
    output = generates(companion)
    wealth = generates(output)
    officer = generates(wealth)
    resource = generates(officer)
    tally = chart_tally(pillars, birth_standings)
    total = sum(tally.values())
    supported = tally[companion] + tally[resource]
    # Support beyond the Day Master's own stem.
    beyond = supported - STEM_TENTHS * STANDING_TENTHS[birth_standings[companion]]
    if beyond == 0:
        strength: Strength = 'following'
        useful = _largest(tally, (output, wealth, officer))
        favourable = wealth if useful == output else generator_of(useful)
        order: list[ElementName] = [useful, favourable, resource, companion]
        order.append(_first_free(ELEMENTS, order))
    elif supported * 2 < total:
        strength = 'weak'
        disease = _largest(tally, (output, wealth, officer))
        useful = resource if disease == officer else controller_of(disease)
        favourable = companion if useful == resource else resource
        order = _support_order(useful, favourable, disease)
    else:
        strength = 'strong'
        disease = _largest(tally, (companion, resource))
        useful = controller_of(disease)
        favourable = generator_of(useful)
        order = _support_order(useful, favourable, disease)
    return {
        'school': 'support',
        'weights': _weights(order),
        'useful': order[0],
        'favourable': order[1],
        'disease': order[2],
        'strength': strength,
        'tally': {
            'elements': {element: tally[element] / 100 for element in ELEMENTS},
            'supported_share': share(supported, total),
        },
        'named': None,
    }


def climate_favourable(named: Sequence[str]) -> Favourable:
    """Climate (调候 Tiao Hou): the weights from the stems Qiong Tong Bao Jian names
    for the chart's Day Master in its birth month (climate_order)."""
    order = climate_order(named)
    return {
        'school': 'climate',
        'weights': _weights(order),
        'useful': order[0],
        'favourable': order[1],
        'disease': order[2],
        'strength': None,
        'tally': None,
        'named': list(named),
    }


def climate_order(named: Sequence[str]) -> list[ElementName]:
    """Climate's order from the stems Qiong Tong Bao Jian names, in its order.

    The first stem's element is useful, and the next of another element favourable;
    when every named stem shares one element, the element that generates it. The
    others follow the usual order of the five gods: the disease is what controls the
    useful element, then what generates the disease, then the one left. A place
    whose element is taken goes to the next free element, in the generating order
    from the useful one.
    """
    if not named or any(stem not in STEMS for stem in named):
        raise ValueError(f'Climate needs the stems the table names, not {named!r}.')
    useful = element_of(named[0])
    others: list[ElementName] = [
        element_of(stem) for stem in named[1:] if element_of(stem) != useful
    ]
    favourable = others[0] if others else generator_of(useful)
    start = ELEMENTS.index(useful)
    cycle: list[ElementName] = [ELEMENTS[(start + step) % 5] for step in range(5)]
    taken: list[ElementName] = [useful, favourable]
    disease = _first_free(
        [controller_of(useful), controller_of(favourable), *cycle], taken
    )
    taken.append(disease)
    taken.append(_first_free([generator_of(disease), *cycle], taken))
    taken.append(_first_free(cycle, taken))
    return taken


# ── The pull ──

LayerName = Literal['day', 'month', 'year', 'luck']
PhaseName = Literal['stem', 'branch']
Band = Literal[
    'strongly_supportive', 'supportive', 'mixed', 'draining', 'strongly_draining'
]
PartRole = Literal['stem', 'main', 'middle', 'residual']


class PullPart(TypedDict):
    char: str
    pinyin: str
    element: ElementName
    role: PartRole
    # The element's weight, how much this character counts, and their product.
    weight: float
    factor: float
    value: float


class Pull(TypedDict):
    score: float
    band: Band
    parts: list[PullPart]


def band(score: float) -> Band:
    if score >= 1.5:
        return 'strongly_supportive'
    if score >= 0.5:
        return 'supportive'
    if score > -0.5:
        return 'mixed'
    if score > -1.5:
        return 'draining'
    return 'strongly_draining'


def _scales(
    layer: LayerName, transits: TransitSchool, phase: PhaseName | None
) -> tuple[int | None, int, bool]:
    """How a layer counts: the stem's scale and the hidden stems' scale in tenths
    (None: by the standing), and whether the stem counts at all."""
    if layer in ('day', 'month') or transits == 'seasoned':
        return None, 0, True
    if layer == 'year':
        # The year leans on its stem: its branch counts half.
        return 10, 5, True
    if transits == 'whole':
        # Ten years as one, leaning on the branch: the stem counts half.
        return 5, 10, True
    # By phase: the stem counts in the stem phase only; the branch in both.
    return 10, 10, phase == 'stem'


def pull(
    stem: str,
    branch: str,
    weights: Mapping[ElementName, float],
    season: Mapping[ElementName, Standing],
    *,
    layer: LayerName,
    transits: TransitSchool,
    phase: PhaseName | None = None,
) -> Pull:
    """What a pillar brings the chart: each character's weight times how much it
    counts, summed. The day and the month count by the season's standing; the year
    and the luck pillar by the school (_scales)."""
    if layer == 'luck' and phase is None:
        raise ValueError('A luck pillar is counted in its phase.')
    stem_scale, hidden_scale, stem_counts = _scales(layer, transits, phase)
    characters: list[tuple[str, PartRole, int]] = []
    if stem_counts:
        characters.append((stem, 'stem', STEM_TENTHS))
    characters.extend(
        (hidden, qi, QI_TENTHS[qi])
        for hidden, qi in zip(hidden_stems_lookup()[branch], QI_NAMES, strict=False)
    )
    parts: list[PullPart] = []
    total = 0
    for char, role, qi_tenths in characters:
        element = element_of(char)
        weight = round(weights[element] * 10)
        if stem_scale is None:
            scale = STANDING_TENTHS[season[element]]
        else:
            scale = stem_scale if role == 'stem' else hidden_scale
        value = weight * qi_tenths * scale
        total += value
        parts.append(
            {
                'char': char,
                'pinyin': STEMS[char]['pinyin'],
                'element': element,
                'role': role,
                'weight': weight / 10,
                'factor': qi_tenths * scale / 100,
                'value': rounded(value),
            }
        )
    score = rounded(total)
    return {'score': score, 'band': band(score), 'parts': parts}
