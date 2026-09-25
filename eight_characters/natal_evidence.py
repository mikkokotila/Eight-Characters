"""Shared natal occurrence and root rules; no strength or transformation inference."""

from collections.abc import Mapping, Sequence
from typing import Literal

from typing_extensions import TypedDict

from eight_characters.data import BRANCHES, STEMS, ElementName, PolarityName
from eight_characters.ten_gods import TEN_GOD_NAMES, TenGodName

PILLAR_NAMES = ('year', 'month', 'day', 'hour')
QiType = Literal['main', 'middle', 'residual']
QI_TYPES: tuple[QiType, ...] = ('main', 'middle', 'residual')


class Identity(TypedDict):
    char: str
    pinyin: str
    element: ElementName
    polarity: PolarityName


class StemEvidence(Identity):
    pillar: str
    component: Literal['stem', 'hidden_stem']
    branch: str | None
    qi_type: QiType | None
    ten_god: TenGodName


class RootEvidence(StemEvidence):
    match: Literal['exact_stem', 'opposite_polarity']


def stem_identity(char: str) -> Identity:
    if char not in STEMS:
        raise ValueError(f'Unknown stem: {char}')
    info = STEMS[char]
    return {
        'char': char,
        'pinyin': info['pinyin'],
        'element': info['element'],
        'polarity': info['polarity'],
    }


def natal_occurrences(
    pillars: Mapping[str, tuple[str, str]],
    hidden_stems: Mapping[str, Sequence[str]],
    ten_gods: Mapping[tuple[str, str], TenGodName],
) -> list[StemEvidence]:
    """Every non-Day-Master visible stem and every hidden stem, without merging duplicates."""
    if set(pillars) != set(PILLAR_NAMES):
        raise ValueError('Natal evidence requires exactly four named pillars.')
    for name in PILLAR_NAMES:
        pair = pillars[name]
        if len(pair) != 2 or pair[0] not in STEMS or pair[1] not in BRANCHES:
            raise ValueError(f'Invalid stem/branch pair for {name}: {pair!r}')
        chars = hidden_stems.get(pair[1])
        if (
            chars is None
            or not 1 <= len(chars) <= len(QI_TYPES)
            or len(set(chars)) != len(chars)
            or any(char not in STEMS for char in chars)
        ):
            raise ValueError(f'Invalid hidden-stem mapping for {pair[1]}.')

    day_master = pillars['day'][0]
    result: list[StemEvidence] = []
    for name in PILLAR_NAMES:
        stem, branch = pillars[name]
        occurrences: list[tuple[str, QiType | None]] = (
            [(stem, None)] if name != 'day' else []
        )
        occurrences.extend(zip(hidden_stems[branch], QI_TYPES))
        for char, qi_type in occurrences:
            god = ten_gods.get((day_master, char))
            if god not in TEN_GOD_NAMES:
                raise ValueError(f'Missing or invalid ten god for {day_master}/{char}.')
            result.append(
                {
                    **stem_identity(char),
                    'pillar': name,
                    'component': 'stem' if qi_type is None else 'hidden_stem',
                    'branch': None if qi_type is None else branch,
                    'qi_type': qi_type,
                    'ten_god': god,
                }
            )
    return result


def roots_for_stem(
    char: str, occurrences: Sequence[StemEvidence]
) -> list[RootEvidence]:
    """Same-element hidden occurrences only; Ten Gods stay relative to the natal Day Master."""
    element = stem_identity(char)['element']
    return [
        {
            **record,
            'match': 'exact_stem' if record['char'] == char else 'opposite_polarity',
        }
        for record in occurrences
        if record['component'] == 'hidden_stem' and record['element'] == element
    ]
