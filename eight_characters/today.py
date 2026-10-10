"""Today: what a day, its month, its year and the luck pillar in force bring to a
chart, and to a partner's.

docs/Today.md is the rule book, and this module follows it. The schools' rules are in
eight_characters/schools.py; the pillars are the engine's, the relationships the
canon's catalogue (interactions.py), and the readings the decade page's
(reading.build_luck_reading), each pillar of the day read as the decade page reads a
luck pillar.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Final, Literal, cast

from typing_extensions import TypedDict

from eight_characters import first_chart
from eight_characters.accounts.records import Birth, Language, Place, Role, Schools
from eight_characters.canon import load_canon
from eight_characters.conventions import ConventionSettings
from eight_characters.data import BRANCHES, STEMS, ElementName
from eight_characters.engine import (
    PillarsAt,
    compute_engine_payload,
    jie_before,
    pillars_at,
)
from eight_characters.interactions import (
    LUCK,
    PILLAR_NAMES,
    AbsorbedInteraction,
    Interaction,
    InteractionKind,
    branch_ties,
    detect_interactions,
    detect_luck_interactions,
)
from eight_characters.luck_context import build_luck_context
from eight_characters.luck_pillars import MAX_LUCK_PILLAR_COUNT, LuckPillar
from eight_characters.mappings import hidden_stems_lookup, ten_gods_lookup
from eight_characters.pillar_changes import true_solar_instants
from eight_characters.policy import MAX_SUPPORTED_YEAR, MIN_SUPPORTED_YEAR
from eight_characters.qiong_tong_bao_jian import climate_stems
from eight_characters.reading import LuckDecadeReading, build_luck_reading
from eight_characters.schools import (
    ELEMENTS,
    QI_NAMES,
    QI_TENTHS,
    STANDING_TENTHS,
    STEM_TENTHS,
    Favourable,
    LayerName,
    PhaseName,
    Pull,
    QiName,
    Season,
    chart_tally,
    climate_favourable,
    element_of,
    pull,
    rounded,
    season_at,
    share,
    support_and_restrain,
)
from eight_characters.sexagenary import BRANCHES as BRANCH_CHARS
from eight_characters.sexagenary import STEMS as STEM_CHARS
from eight_characters.ten_gods import TenGodName
from eight_characters.time_convert import (
    AmbiguousTimeError,
    BirthInput,
    NonexistentTimeError,
    load_timezone,
)

POLICY: Final = 'today_v1'
RUN_BEFORE: Final = 7
RUN_AFTER: Final = 14
SECONDS_PER_DAY: Final = 86400.0
LAYERS: Final[tuple[LayerName, ...]] = ('day', 'month', 'year', 'luck')
# Each pillar of the day takes the fifth place beside the natal four under its own
# name, as the luck pillar does on the decade page.
POSITIONS: Final[dict[LayerName, str]] = {
    'day': 'daily',
    'month': 'monthly',
    'year': 'annual',
    'luck': LUCK,
}
# The canon's sentences that wait for "a Luck Pillar or annual pillar".
SETTLING: Final[frozenset[LayerName]] = frozenset({'year', 'luck'})
# The hours' ties: what joins an hour to the day, and what sets them against each
# other (docs/Today.md, The hours).
ALLIED: Final[frozenset[InteractionKind]] = frozenset(
    {'branch_combination', 'half_frame'}
)
HOSTILE: Final[frozenset[InteractionKind]] = frozenset(
    {'branch_clash', 'harm', 'punishment', 'half_punishment', 'self_punishment'}
)
# The canon's Background: "Wood is east, green, the liver …".
ORGANS: Final[dict[ElementName, str]] = {
    'wood': 'the liver',
    'fire': 'the heart',
    'earth': 'the spleen and stomach',
    'metal': 'the lungs',
    'water': 'the kidneys',
}

Tie = InteractionKind | Literal['repeat']
Call = Literal['protect', 'mixed', 'avoid']


class TodayInputError(ValueError):
    """The day cannot be read as asked; the message says why and can be shown."""


# ── Charts ──


@dataclass(frozen=True)
class Natal:
    """A birth, charted by the engine with its luck pillars."""

    birth: Birth
    payload: dict[str, Any]

    @property
    def pillars(self) -> dict[str, tuple[str, str]]:
        found = self.payload['pillars']
        return {
            name: (found[name]['stem']['chinese'], found[name]['branch']['chinese'])
            for name in PILLAR_NAMES
        }

    @property
    def day_master(self) -> str:
        return self.pillars['day'][0]

    @property
    def luck_pillars(self) -> list[LuckPillar]:
        return cast(list[LuckPillar], self.payload['luck_pillars']['pillars'])

    def chart(self) -> dict[first_chart.PillarName, first_chart.ChartPillar]:
        """Its four pillars as /api/four_pillars and the first chart show them."""
        return {
            name: first_chart.engine_pillar(name, self.payload)
            for name in first_chart.PILLAR_NAMES
        }


def chart_birth(birth: Birth) -> Natal:
    """The birth's chart, with its Zi-hour convention, and its luck pillars.
    TodayInputError if its clock time did not happen at its place, or happened twice
    there and no fold says which."""
    first = birth.first_birth()
    clock = first.clock
    if clock is None:
        raise TodayInputError('A chart needs its birth time.')
    try:
        payload = compute_engine_payload(
            BirthInput(
                year=first.day.year,
                month=first.day.month,
                day=first.day.day,
                hour=clock.hour,
                minute=clock.minute,
                second=clock.second,
                timezone_name=birth.place.timezone,
                longitude=birth.place.longitude,
                latitude=birth.place.latitude,
                fold=birth.fold,
                conventions=ConventionSettings(zi_convention=birth.zi),
                gender=birth.gender,
            ),
            include_luck_pillars=True,
            luck_pillar_count=MAX_LUCK_PILLAR_COUNT,
        )
    except NonexistentTimeError as exc:
        raise TodayInputError(
            f'{birth.time} did not happen on {birth.date} in {birth.place.timezone}: '
            'the clocks skipped it.'
        ) from exc
    except AmbiguousTimeError as exc:
        raise TodayInputError(
            f'{birth.time} happened twice on {birth.date} in {birth.place.timezone}: '
            'give fold 0 for its first pass, or 1 for its second.'
        ) from exc
    return Natal(birth=birth, payload=payload)


def _birth_season(natal: Natal, schools: Schools) -> Season:
    pillars = natal.payload['pillars']
    return season_at(
        schools.season,
        float(natal.payload['intermediate']['solar_longitude_deg']),
        pillars['month']['branch']['chinese'],
        float(pillars['month']['changes']['previous']['seconds']) / SECONDS_PER_DAY,
    )


def favourable_for(natal: Natal, schools: Schools) -> Favourable:
    """The chart's favourable elements by the chosen school."""
    if schools.favourable == 'support':
        return support_and_restrain(
            natal.pillars, _birth_season(natal, schools)['standings']
        )
    longitude = float(natal.payload['intermediate']['solar_longitude_deg'])
    # A solar month runs 30 degrees from its jie; its middle term is 15 in.
    second_half = (longitude - 315.0) % 30.0 >= 15.0
    return climate_favourable(
        climate_stems(natal.day_master, natal.pillars['month'][1], second_half)
    )


# ── The day ──


def _check_range(day: date) -> None:
    # The years first: a date far outside them has no run to compute.
    inside = MIN_SUPPORTED_YEAR <= day.year <= MAX_SUPPORTED_YEAR
    if (
        not inside
        or (day - timedelta(days=RUN_BEFORE)).year < MIN_SUPPORTED_YEAR
        or (day + timedelta(days=RUN_AFTER)).year > MAX_SUPPORTED_YEAR
    ):
        raise TodayInputError(
            f'Today reads {RUN_BEFORE} days back and {RUN_AFTER} ahead; dates from '
            f'{date(MIN_SUPPORTED_YEAR, 1, 1) + timedelta(days=RUN_BEFORE)} to '
            f'{date(MAX_SUPPORTED_YEAR, 12, 31) - timedelta(days=RUN_AFTER)} can be read.'
        )


def _noon(day: date, place: Place) -> PillarsAt:
    """The day's moment: noon on that date at the place (its first pass, should the
    clocks ever repeat it). TodayInputError if the clocks skipped it, as Samoa's
    skipped all of 30 December 2011."""
    try:
        return pillars_at(
            BirthInput(
                year=day.year,
                month=day.month,
                day=day.day,
                hour=12,
                minute=0,
                second=0,
                timezone_name=place.timezone,
                longitude=place.longitude,
                latitude=place.latitude,
                fold=0,
            )
        )
    except NonexistentTimeError as exc:
        raise TodayInputError(
            f'Noon on {day} did not happen in {place.timezone}: the clocks skipped it.'
        ) from exc


def _season_now(at: PillarsAt, schools: Schools) -> Season:
    return season_at(
        schools.season,
        at.solar.lambda_apparent_deg,
        BRANCH_CHARS[at.month.branch_idx],
        at.solar.jd_tt - jie_before(at),
    )


def _pair(stem_idx: int, branch_idx: int) -> tuple[str, str]:
    return STEM_CHARS[stem_idx], BRANCH_CHARS[branch_idx]


def _instant(text: str) -> datetime:
    return datetime.fromisoformat(text).astimezone(UTC)


class LuckSpan(TypedDict):
    sequence: int
    phase: PhaseName
    start_utc: str
    end_utc: str
    phase_start_utc: str
    phase_end_utc: str


def _luck_at(natal: Natal, moment: datetime) -> tuple[tuple[str, str], LuckSpan] | None:
    """The luck pillar in force at a moment, and its phase; None before the first."""
    for pillar in natal.luck_pillars:
        if _instant(pillar['start_utc']) <= moment < _instant(pillar['end_utc']):
            for phase in pillar['phases']:
                if _instant(phase['start_utc']) <= moment < _instant(phase['end_utc']):
                    return (pillar['stem']['chinese'], pillar['branch']['chinese']), {
                        'sequence': pillar['sequence'],
                        'phase': phase['phase'],
                        'start_utc': pillar['start_utc'],
                        'end_utc': pillar['end_utc'],
                        'phase_start_utc': phase['start_utc'],
                        'phase_end_utc': phase['end_utc'],
                    }
            raise RuntimeError(f'Luck pillar {pillar["sequence"]} has no phase then.')
    return None


# ── What the answer shows ──


class TenGodAt(TypedDict):
    char: str
    pinyin: str
    element: ElementName
    # Where the stem stands: the pillar's stem, or a hidden stem by its qi.
    role: Literal['stem', 'main', 'middle', 'residual']
    ten_god: TenGodName


def _ten_gods(day_master: str, stem: str, branch: str) -> list[TenGodAt]:
    gods = ten_gods_lookup()
    roles: list[tuple[str, Literal['stem', 'main', 'middle', 'residual']]] = [
        (stem, 'stem')
    ]
    roles.extend(zip(hidden_stems_lookup()[branch], QI_NAMES, strict=False))
    return [
        {
            'char': char,
            'pinyin': STEMS[char]['pinyin'],
            'element': element_of(char),
            'role': role,
            'ten_god': gods[(day_master, char)],
        }
        for char, role in roles
    ]


class Relationship(Interaction):
    # The canon's line for it; None in a Finnish answer.
    line: str | None


class Layer(TypedDict):
    layer: LayerName
    position: str
    pillar: first_chart.ChartPillar
    ten_gods: list[TenGodAt]
    pull: Pull
    relationships: list[Relationship]
    absorbed: list[AbsorbedInteraction]
    # The luck pillar's decade and phase; None for the others.
    luck: LuckSpan | None


def _label(layer: LayerName) -> str:
    return {'day': 'Day', 'month': 'Month', 'year': 'Year', 'luck': 'Luck'}[layer]


@dataclass(frozen=True)
class _Read:
    """A layer's relationships and, in English, its readings."""

    relationships: list[Relationship]
    absorbed: list[AbsorbedInteraction]
    reading: LuckDecadeReading | None


def _read(
    natal: Natal,
    layer: LayerName,
    pair: tuple[str, str],
    english: bool,
    active: PhaseName | None = None,
) -> _Read:
    """The pillar read against the natal chart as the decade page reads a luck
    pillar, in its own fifth position. With `active`, a luck pillar's phase, only what
    acts in it: in the branch phase its stem, and the relationships its stem forms,
    are set aside, as on the decade page."""
    position = POSITIONS[layer]
    pillar = {
        'sequence': 1,
        'stem': {'index': STEM_CHARS.index(pair[0]), 'chinese': pair[0]},
        'branch': {'index': BRANCH_CHARS.index(pair[1]), 'chinese': pair[1]},
    }
    luck_pillars = [cast(LuckPillar, pillar)]
    context = build_luck_context(
        natal.pillars,
        luck_pillars,
        hidden_stems_lookup(),
        ten_gods_lookup(),
        position=position,
    )
    decade = context['decades'][0]
    reading: LuckDecadeReading | None = None
    if english:
        reading = build_luck_reading(
            load_canon(),
            natal.pillars,
            ten_gods_lookup(),
            detect_interactions(natal.pillars),
            luck_pillars,
            context['decades'],
        )['decades'][0]
        if layer not in SETTLING:
            reading = {**reading, 'settles': []}
    kept = {
        found['id']
        for found in decade['interactions']
        if active is None or active in found['phases']
    }
    if reading is not None and active is not None:
        reading = {
            **reading,
            'relationships': {
                key: value
                for key, value in reading['relationships'].items()
                if key in kept
            },
            'settles': [
                {**settled, 'by': [by for by in settled['by'] if by in kept]}
                for settled in reading['settles']
                if any(by in kept for by in settled['by'])
            ],
        }
    relationships: list[Relationship] = []
    for found in decade['interactions']:
        if found['id'] not in kept:
            continue
        interaction = cast(
            Interaction, {k: v for k, v in found.items() if k != 'phases'}
        )
        line = (
            None
            if reading is None
            else reading['relationships'][interaction['id']]['line']
        )
        relationships.append({**interaction, 'line': line})
    absorbed = [
        cast(AbsorbedInteraction, {k: v for k, v in half.items() if k != 'phases'})
        for half in decade['absorbed']
        if active is None or active in half['phases']
    ]
    return _Read(relationships=relationships, absorbed=absorbed, reading=reading)


class RunDay(TypedDict):
    date: str
    # Days from the date asked for.
    offset: int
    pillar: first_chart.ChartPillar
    score: float
    band: str
    relationships: list[Interaction]


class HourSpan(TypedDict):
    # On the clock at the place, with the UTC offset, to the second.
    start: str
    end: str


class Hour(TypedDict):
    branch: str
    pinyin: str
    sign: str
    element: ElementName
    spans: list[HourSpan]
    ties: list[Tie]
    call: Call | None


class Palace(TypedDict):
    branch: str
    pinyin: str
    relationships: list[Relationship]


class PartnerDay(TypedDict):
    pull: Pull
    luck: Layer | None


class Marriage(TypedDict):
    partner: PartnerDay
    pull_apart: bool
    spouse_palace: Palace
    # The day's relationships with the partner's chart.
    partner_chart: list[Relationship]


class GodInPlay(TenGodAt):
    # The canon's heading for the Ten God and what it is to the Day Master.
    name: str | None
    relation: str | None


class Work(TypedDict):
    career_house: Palace
    ten_gods: list[GodInPlay]


class ElementToday(TypedDict):
    element: ElementName
    # The day's count of the element: as in its pull, without the weight.
    today: float
    # The element's share of the birth tally, in percent.
    chart_share: float
    organs: str


class Health(TypedDict):
    elements: list[ElementToday]


class TodayAnswer(TypedDict):
    policy: Literal['today_v1']
    date: str
    chart: Role
    language: Language
    place: dict[str, Any]
    schools: dict[str, str]
    engine: dict[str, Any]
    changes: list[first_chart.PillarChange]
    season: Season
    favourable: Favourable
    layers: dict[LayerName, Layer | None]
    run: list[RunDay]
    hours: list[Hour]
    marriage: Marriage | None
    work: Work
    health: Health
    readings: dict[LayerName, LuckDecadeReading] | None


def _layer(
    natal: Natal,
    layer: LayerName,
    pair: tuple[str, str],
    weights: Mapping[ElementName, float],
    season: Season,
    schools: Schools,
    english: bool,
    luck: LuckSpan | None = None,
) -> tuple[Layer, LuckDecadeReading | None]:
    # By phase, a luck pillar counts and acts as its phase lets it; the other schools
    # count its stem through all ten years.
    active = (
        luck['phase'] if luck is not None and schools.transits == 'phases' else None
    )
    read = _read(natal, layer, pair, english, active)
    view: Layer = {
        'layer': layer,
        'position': POSITIONS[layer],
        'pillar': first_chart.pillar_view(_label(layer), pair[0], pair[1]),
        'ten_gods': _ten_gods(natal.day_master, pair[0], pair[1]),
        'pull': pull(
            pair[0],
            pair[1],
            weights,
            season['standings'],
            layer=layer,
            transits=schools.transits,
            phase=None if luck is None else luck['phase'],
        ),
        'relationships': read.relationships,
        'absorbed': read.absorbed,
        'luck': luck,
    }
    return view, read.reading


def _touching(relationships: Sequence[Relationship], pillar: str) -> list[Relationship]:
    """The relationships that take in a natal pillar's branch."""
    return [
        relationship
        for relationship in relationships
        if relationship['component'] == 'branch'
        and any(member['pillar'] == pillar for member in relationship['members'])
    ]


def _run(
    natal: Natal,
    day: date,
    place: Place,
    weights: Mapping[ElementName, float],
    schools: Schools,
) -> list[RunDay]:
    days: list[RunDay] = []
    for offset in range(-RUN_BEFORE, RUN_AFTER + 1):
        other = day + timedelta(days=offset)
        try:
            at = _noon(other, place)
        except TodayInputError:
            # A date the place's clocks skipped has no noon to read: the run leaves
            # it out (docs/Today.md, The day).
            continue
        pair = _pair(at.day.pillar.stem_idx, at.day.pillar.branch_idx)
        found = pull(
            pair[0],
            pair[1],
            weights,
            _season_now(at, schools)['standings'],
            layer='day',
            transits=schools.transits,
        )
        days.append(
            {
                'date': other.isoformat(),
                'offset': offset,
                'pillar': first_chart.pillar_view('Day', pair[0], pair[1]),
                'score': found['score'],
                'band': found['band'],
                'relationships': detect_luck_interactions(
                    natal.pillars, pair, position=POSITIONS['day']
                )['interactions'],
            }
        )
    return days


def _clock(instant: datetime, place: Place) -> str:
    return instant.astimezone(load_timezone(place.timezone)).isoformat(
        timespec='seconds'
    )


def _hours(
    day: date,
    place: Place,
    noon: PillarsAt,
    day_branch: str,
    weights: Mapping[ElementName, float],
) -> list[Hour]:
    """The twelve double hours of the day at the place, by true solar time
    (docs/Today.md, The hours)."""
    midnight = datetime.combine(day, time(0))
    readings = [midnight + timedelta(hours=hour) for hour in (0, *range(1, 24, 2), 24)]
    instants = true_solar_instants(
        readings,
        place.timezone,
        place.longitude,
        noon.normalized.utc_datetime.replace(tzinfo=UTC),
    )
    at = dict(zip((0, *range(1, 24, 2), 24), instants, strict=True))
    hours: list[Hour] = []
    for index, branch in enumerate(BRANCH_CHARS):
        if index == 0:
            bounds = [(0, 1), (23, 24)]
        else:
            bounds = [(2 * index - 1, 2 * index + 1)]
        ties: list[Tie] = list(branch_ties(branch, day_branch))
        if branch == day_branch and 'self_punishment' not in ties:
            ties.append('repeat')
        allied = any(tie == 'repeat' or tie in ALLIED for tie in ties)
        hostile = any(tie != 'repeat' and tie in HOSTILE for tie in ties)
        weight = weights[BRANCHES[branch]['element']]
        call: Call | None = None
        if ties:
            if allied and not hostile and weight > 0:
                call = 'protect'
            elif hostile and not allied and weight < 0:
                call = 'avoid'
            else:
                call = 'mixed'
        hours.append(
            {
                'branch': branch,
                'pinyin': BRANCHES[branch]['pinyin'],
                'sign': BRANCHES[branch]['animal'],
                'element': BRANCHES[branch]['element'],
                'spans': [
                    {'start': _clock(at[start], place), 'end': _clock(at[end], place)}
                    for start, end in bounds
                ],
                'ties': ties,
                'call': call,
            }
        )
    return hours


def _work(natal: Natal, layers: Mapping[LayerName, Layer | None]) -> Work:
    canon = load_canon()
    month_branch = natal.pillars['month'][1]
    day_layer = layers['day']
    month_layer = layers['month']
    if day_layer is None or month_layer is None:
        raise AssertionError('Every day has its day and month pillars.')
    gods: list[GodInPlay] = []
    for found in day_layer['ten_gods']:
        entry = canon['ten_gods'][found['ten_god']]
        gods.append({**found, 'name': entry['name'], 'relation': entry['relation']})
    return {
        'career_house': {
            'branch': month_branch,
            'pinyin': BRANCHES[month_branch]['pinyin'],
            'relationships': [
                *_touching(day_layer['relationships'], 'month'),
                *_touching(month_layer['relationships'], 'month'),
            ],
        },
        'ten_gods': gods,
    }


def _health(
    natal: Natal, schools: Schools, day_pair: tuple[str, str], season: Season
) -> Health:
    tally = chart_tally(natal.pillars, _birth_season(natal, schools)['standings'])
    total = sum(tally.values())
    brought = dict.fromkeys(ELEMENTS, 0)
    characters: list[tuple[str, int]] = [(day_pair[0], STEM_TENTHS)]
    qis: list[QiName] = list(QI_NAMES)
    characters.extend(
        (hidden, QI_TENTHS[qi])
        for hidden, qi in zip(hidden_stems_lookup()[day_pair[1]], qis, strict=False)
    )
    for char, count in characters:
        element = element_of(char)
        brought[element] += count * STANDING_TENTHS[season['standings'][element]] * 10
    return {
        'elements': [
            {
                'element': element,
                'today': rounded(brought[element]),
                'chart_share': share(tally[element] * 100, total, 1),
                'organs': ORGANS[element],
            }
            for element in ELEMENTS
        ]
    }


def build_today(
    day: date,
    place: Place,
    subject: Birth,
    other: Birth | None,
    schools: Schools,
    language: Language,
    chart: Role = 'self',
) -> TodayAnswer:
    """Everything Today shows for a date at a place: for `subject`'s chart, with
    `other`'s as the partner's (docs/Today.md)."""
    _check_range(day)
    natal = chart_birth(subject)
    english = language == 'en'
    favourable = favourable_for(natal, schools)
    weights = favourable['weights']
    noon = _noon(day, place)
    season = _season_now(noon, schools)
    first = first_chart.build_first_chart(
        first_chart.FirstBirth(
            day=day,
            clock=None,
            place=first_chart.Place(
                timezone=place.timezone,
                latitude=place.latitude,
                longitude=place.longitude,
            ),
        )
    )
    moment = noon.normalized.utc_datetime.replace(tzinfo=UTC)
    pairs: dict[LayerName, tuple[str, str]] = {
        'day': _pair(noon.day.pillar.stem_idx, noon.day.pillar.branch_idx),
        'month': _pair(noon.month.stem_idx, noon.month.branch_idx),
        'year': _pair(noon.year.stem_idx, noon.year.branch_idx),
    }
    layers: dict[LayerName, Layer | None] = {}
    readings: dict[LayerName, LuckDecadeReading] = {}
    for layer in ('day', 'month', 'year'):
        view, reading = _layer(
            natal, layer, pairs[layer], weights, season, schools, english
        )
        layers[layer] = view
        if reading is not None:
            readings[layer] = reading
    in_force = _luck_at(natal, moment)
    layers['luck'] = None
    if in_force is not None:
        view, reading = _layer(
            natal,
            'luck',
            in_force[0],
            weights,
            season,
            schools,
            english,
            luck=in_force[1],
        )
        layers['luck'] = view
        if reading is not None:
            readings['luck'] = reading
    day_layer = layers['day']
    if day_layer is None:
        raise AssertionError('Every day has its day pillar.')
    marriage: Marriage | None = None
    if other is not None:
        partner = chart_birth(other)
        partner_weights = favourable_for(partner, schools)['weights']
        partner_pull = pull(
            pairs['day'][0],
            pairs['day'][1],
            partner_weights,
            season['standings'],
            layer='day',
            transits=schools.transits,
        )
        partner_luck: Layer | None = None
        partner_in_force = _luck_at(partner, moment)
        if partner_in_force is not None:
            partner_luck = _layer(
                partner,
                'luck',
                partner_in_force[0],
                partner_weights,
                season,
                schools,
                english,
                luck=partner_in_force[1],
            )[0]
        own_score = day_layer['pull']['score']
        their_score = partner_pull['score']
        spouse_branch = natal.pillars['day'][1]
        marriage = {
            'partner': {'pull': partner_pull, 'luck': partner_luck},
            'pull_apart': (own_score >= 0.5 and their_score <= -0.5)
            or (their_score >= 0.5 and own_score <= -0.5),
            'spouse_palace': {
                'branch': spouse_branch,
                'pinyin': BRANCHES[spouse_branch]['pinyin'],
                'relationships': _touching(day_layer['relationships'], 'day'),
            },
            'partner_chart': _read(partner, 'day', pairs['day'], english).relationships,
        }
    return {
        'policy': POLICY,
        'date': day.isoformat(),
        'chart': chart,
        'language': language,
        'place': {
            'name': place.name,
            'city': place.city,
            'timezone': place.timezone,
            'latitude': place.latitude,
            'longitude': place.longitude,
        },
        'schools': {
            'favourable': schools.favourable,
            'season': schools.season,
            'transits': schools.transits,
        },
        'engine': first['engine'],
        'changes': first['changes'],
        'season': season,
        'favourable': favourable,
        'layers': layers,
        'run': _run(natal, day, place, weights, schools),
        'hours': _hours(day, place, noon, pairs['day'][1], weights),
        'marriage': marriage,
        'work': _work(natal, layers),
        'health': _health(natal, schools, pairs['day'], season),
        'readings': readings if english else None,
    }
