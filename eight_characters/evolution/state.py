from dataclasses import dataclass
from typing import Iterable, Sequence

from eight_characters.evolution.primitives import (
    ELEMENT_COUNT,
    TEN_GOD_COUNT,
    authority_element,
    element_to_one_hot,
    one_hot_to_element,
    output_element,
    ten_god_one_hot,
    wealth_element,
)


PILLAR_COUNT = 4
RULE_COUNT = 34

MODE_STANDARD = 'Standard'
MODE_FOLLOW_WEALTH = 'FollowWealth'
MODE_FOLLOW_AUTHORITY = 'FollowAuthority'
MODE_FOLLOW_OUTPUT = 'FollowOutput'
MODE_FOLLOW_STRENGTH = 'FollowStrength'

VALID_MODES = (
    MODE_STANDARD,
    MODE_FOLLOW_WEALTH,
    MODE_FOLLOW_AUTHORITY,
    MODE_FOLLOW_OUTPUT,
    MODE_FOLLOW_STRENGTH,
)

TEN_GOD_LABELS = (
    'Companion',
    'Rob Wealth',
    'Eating God',
    'Hurting Officer',
    'Indirect Wealth',
    'Direct Wealth',
    'Seven Killings',
    'Direct Officer',
    'Indirect Resource',
    'Direct Resource',
)

# Per Math.md Section 2 domains.
RULE_STATE_DOMAINS: tuple[tuple[int, ...], ...] = (
    (0, 1, 2, 3),  # 1
    (0, 1, 2, 3),  # 2
    (0, 1, 2, 3),  # 3
    (0, 1, 2, 3),  # 4
    (0, 1, 2, 3),  # 5
    (0, 1, 2, 3),  # 6
    (0, 1, 2, 3),  # 7
    (0, 1, 2, 3),  # 8
    (0, 1, 2, 3),  # 9
    (0, 1, 2, 3),  # 10
    (0, 1, 2, 3),  # 11
    (0, 1),  # 12
    (0, 1),  # 13
    (0, 1),  # 14
    (0, 1),  # 15
    (0, 1),  # 16
    (0, 1),  # 17
    (0, 1, 2),  # 18
    (0, 1, 2),  # 19
    (0, 1, 2),  # 20
    (0, 1, 2),  # 21
    (0, 1),  # 22
    (0, 1),  # 23
    (0, 1),  # 24
    (0, 1),  # 25
    (0, 1),  # 26
    (0, 1),  # 27
    (0, 1),  # 28
    (0, 1),  # 29
    (0, 1),  # 30
    (0, 1),  # 31
    (0, 1),  # 32
    (0, 1),  # 33
    (0, 1),  # 34
)

def _validate_binary_int(value: int, field_name: str) -> None:
    if value not in (0, 1):
        raise ValueError(f'{field_name} must be 0 or 1, got {value}')


def _validate_one_hot(vector: Sequence[int], length: int, field_name: str) -> None:
    if len(vector) != length:
        raise ValueError(f'{field_name} must have length {length}, got {len(vector)}')
    if any(value not in (0, 1) for value in vector):
        raise ValueError(f'{field_name} must contain only 0/1 values')
    if sum(vector) != 1:
        raise ValueError(f'{field_name} must be one-hot with exactly one active entry')


def _one_hot_index(vector: Sequence[int], field_name: str, length: int) -> int:
    _validate_one_hot(vector, length=length, field_name=field_name)
    return vector.index(1)


@dataclass(frozen=True)
class ObservedState:
    branch_ids: tuple[int, int, int, int]
    base_elements: tuple[tuple[int, int, int, int, int], ...]
    polarities: tuple[int, ...]
    hierarchy_levels: tuple[int, ...]
    positions: tuple[int, ...]
    masks: tuple[int, ...]
    vitality_stages: tuple[int, ...]
    day_master_index: int

    def validate(self) -> None:
        if len(self.branch_ids) != PILLAR_COUNT:
            raise ValueError(
                f'branch_ids must contain exactly {PILLAR_COUNT} pillar entries'
            )
        for index, branch_id in enumerate(self.branch_ids):
            if branch_id < 1 or branch_id > 12:
                raise ValueError(
                    f'branch_ids[{index}] out of range [1..12]: {branch_id}'
                )

        entity_count = len(self.base_elements)
        if entity_count == 0:
            raise ValueError('ObservedState must contain at least one entity')

        if len(self.polarities) != entity_count:
            raise ValueError('polarities length must match base_elements length')
        if len(self.hierarchy_levels) != entity_count:
            raise ValueError('hierarchy_levels length must match base_elements length')
        if len(self.positions) != entity_count:
            raise ValueError('positions length must match base_elements length')
        if len(self.masks) != entity_count:
            raise ValueError('masks length must match base_elements length')
        if len(self.vitality_stages) != entity_count:
            raise ValueError('vitality_stages length must match base_elements length')

        for idx, one_hot in enumerate(self.base_elements):
            _validate_one_hot(one_hot, length=ELEMENT_COUNT, field_name=f'base_elements[{idx}]')
        for idx, polarity in enumerate(self.polarities):
            _validate_binary_int(polarity, f'polarities[{idx}]')
        for idx, hierarchy in enumerate(self.hierarchy_levels):
            if hierarchy < 1 or hierarchy > 4:
                raise ValueError(
                    f'hierarchy_levels[{idx}] out of range [1..4]: {hierarchy}'
                )
        for idx, position in enumerate(self.positions):
            if position < 1 or position > 4:
                raise ValueError(f'positions[{idx}] out of range [1..4]: {position}')
        for idx, mask in enumerate(self.masks):
            _validate_binary_int(mask, f'masks[{idx}]')
        for idx, vitality in enumerate(self.vitality_stages):
            if vitality < 1 or vitality > 12:
                raise ValueError(
                    f'vitality_stages[{idx}] out of range [1..12]: {vitality}'
                )

        if self.day_master_index < 0 or self.day_master_index >= entity_count:
            raise ValueError(
                'day_master_index must point to an entity within base_elements'
            )
        if self.positions[self.day_master_index] != 3:
            raise ValueError('day_master_index must refer to an entity in Day position')
        if self.hierarchy_levels[self.day_master_index] != 4:
            raise ValueError('day_master_index must refer to a stem-level entity')
        if self.masks[self.day_master_index] != 1:
            raise ValueError('day_master_index must refer to an active entity (mask=1)')


@dataclass(frozen=True)
class LatentState:
    switches: tuple[int, ...]
    omegas: tuple[float, ...]
    mode: str

    def validate(self) -> None:
        if len(self.switches) != RULE_COUNT:
            raise ValueError(f'switches must contain {RULE_COUNT} entries')
        if len(self.omegas) != RULE_COUNT:
            raise ValueError(f'omegas must contain {RULE_COUNT} entries')
        if self.mode not in VALID_MODES:
            raise ValueError(f'mode must be one of {VALID_MODES}, got {self.mode}')

        for idx, (value, domain) in enumerate(zip(self.switches, RULE_STATE_DOMAINS), start=1):
            if value not in domain:
                raise ValueError(f'S_{idx} invalid state {value}; allowed states={domain}')
        for idx, omega_value in enumerate(self.omegas, start=1):
            if omega_value < 0.0:
                raise ValueError(f'omega_{idx} must be non-negative')


@dataclass(frozen=True)
class DerivedState:
    effective_elements: tuple[tuple[int, int, int, int, int], ...]
    effective_ten_gods: tuple[tuple[int, ...], ...]
    dynamic_vitality_amplitudes: tuple[float, ...]
    pillar_temperatures: tuple[float, float, float, float]
    pillar_saturations: tuple[float, float, float, float]
    chart_temperature: float
    chart_saturation: float

    def validate(self, expected_entity_count: int) -> None:
        if len(self.effective_elements) != expected_entity_count:
            raise ValueError('effective_elements length must match entity count')
        if len(self.effective_ten_gods) != expected_entity_count:
            raise ValueError('effective_ten_gods length must match entity count')
        if len(self.dynamic_vitality_amplitudes) != expected_entity_count:
            raise ValueError('dynamic_vitality_amplitudes length must match entity count')

        for idx, one_hot in enumerate(self.effective_elements):
            _validate_one_hot(
                one_hot,
                length=ELEMENT_COUNT,
                field_name=f'effective_elements[{idx}]',
            )
        for idx, one_hot in enumerate(self.effective_ten_gods):
            _validate_one_hot(
                one_hot,
                length=TEN_GOD_COUNT,
                field_name=f'effective_ten_gods[{idx}]',
            )
        for idx, amplitude in enumerate(self.dynamic_vitality_amplitudes):
            if amplitude < 0.0 or amplitude > 1.0:
                raise ValueError(
                    f'dynamic_vitality_amplitudes[{idx}] must be in [0,1], got {amplitude}'
                )


@dataclass(frozen=True)
class FullTransformationCapture:
    rule_index: int
    entity_index: int
    target_element_index: int

    def validate(self, entity_count: int) -> None:
        if self.rule_index < 1 or self.rule_index > RULE_COUNT:
            raise ValueError(f'rule_index out of range [1..{RULE_COUNT}]')
        if self.entity_index < 0 or self.entity_index >= entity_count:
            raise ValueError(
                f'entity_index out of range [0..{entity_count - 1}]: {self.entity_index}'
            )
        if self.target_element_index < 0 or self.target_element_index >= ELEMENT_COUNT:
            raise ValueError(
                f'target_element_index out of range [0..{ELEMENT_COUNT - 1}]'
            )


def active_mode_center(day_master_element_index: int, mode: str) -> int:
    if mode not in VALID_MODES:
        raise ValueError(f'Unsupported mode: {mode}')
    if day_master_element_index < 0 or day_master_element_index >= ELEMENT_COUNT:
        raise ValueError(
            f'day_master_element_index out of range: {day_master_element_index}'
        )

    if mode in (MODE_STANDARD, MODE_FOLLOW_STRENGTH):
        return day_master_element_index
    if mode == MODE_FOLLOW_WEALTH:
        return wealth_element(day_master_element_index)
    if mode == MODE_FOLLOW_AUTHORITY:
        return authority_element(day_master_element_index)
    return output_element(day_master_element_index)


def resolve_effective_elements(
    observed_state: ObservedState,
    full_captures: Iterable[FullTransformationCapture],
) -> tuple[tuple[int, int, int, int, int], ...]:
    observed_state.validate()
    captures_by_entity: dict[int, set[int]] = {}
    entity_count = len(observed_state.base_elements)

    for capture in full_captures:
        capture.validate(entity_count=entity_count)
        capture_set = captures_by_entity.setdefault(capture.entity_index, set())
        capture_set.add(capture.target_element_index)
        if len(capture_set) > 1:
            raise ValueError(
                'Absolute exclusivity violation: one entity captured by full rules '
                'with different target elements'
            )

    result = list(observed_state.base_elements)
    for entity_index, targets in captures_by_entity.items():
        target_element = next(iter(targets))
        result[entity_index] = element_to_one_hot(target_element)
    return tuple(result)


def recompute_effective_ten_gods(
    observed_state: ObservedState,
    effective_elements: Sequence[Sequence[int]],
    mode: str,
) -> tuple[tuple[int, ...], ...]:
    observed_state.validate()
    if len(effective_elements) != len(observed_state.base_elements):
        raise ValueError(
            'effective_elements length must match observed entity count for TG recomputation'
        )

    day_master_element = one_hot_to_element(
        tuple(effective_elements[observed_state.day_master_index])
    )
    day_master_polarity = observed_state.polarities[observed_state.day_master_index]
    center = active_mode_center(day_master_element_index=day_master_element, mode=mode)

    result: list[tuple[int, ...]] = []
    for idx, one_hot in enumerate(effective_elements):
        entity_element = one_hot_to_element(tuple(one_hot))
        entity_polarity = observed_state.polarities[idx]
        result.append(
            ten_god_one_hot(
                entity_element_index=entity_element,
                entity_polarity=entity_polarity,
                center_element_index=center,
                center_polarity=day_master_polarity,
            )
        )
    return tuple(result)

