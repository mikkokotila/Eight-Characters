from typing import Mapping, Sequence

from eight_characters.evolution.primitives import (
    DELTA_CLASH,
    DELTA_PUN,
    EPSILON,
    moisture_contribution,
    polarity_multiplier,
    stage_amplitude,
    temperature_contribution,
    wuxing_interaction,
)
from eight_characters.evolution.state import LatentState, ObservedState


def _clip_unit_interval(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _validate_amplitudes(amplitudes: Sequence[float], expected_count: int) -> None:
    if len(amplitudes) != expected_count:
        raise ValueError(
            f'amplitudes length mismatch: expected {expected_count}, got {len(amplitudes)}'
        )
    for idx, value in enumerate(amplitudes):
        if value < 0.0 or value > 1.0:
            raise ValueError(f'amplitudes[{idx}] must be in [0,1], got {value}')


def _validate_flux_matrix(matrix: Sequence[Sequence[float]], expected_count: int) -> None:
    if len(matrix) != expected_count:
        raise ValueError(
            f'flux matrix row count mismatch: expected {expected_count}, got {len(matrix)}'
        )
    for row in matrix:
        if len(row) != expected_count:
            raise ValueError(
                f'flux matrix column count mismatch: expected {expected_count}, got {len(row)}'
            )


def compute_dynamic_vitality_amplitudes(
    observed_state: ObservedState,
    latent_state: LatentState,
    clash_participation: Mapping[tuple[int, int], float] | None = None,
    punishment_participation: Mapping[tuple[int, int], float] | None = None,
) -> tuple[float, ...]:
    observed_state.validate()
    latent_state.validate()
    entity_count = len(observed_state.base_elements)
    clash_participation = clash_participation or {}
    punishment_participation = punishment_participation or {}

    amplitudes: list[float] = []
    for entity_index in range(entity_count):
        if observed_state.masks[entity_index] == 0:
            amplitudes.append(0.0)
            continue

        base = stage_amplitude(observed_state.vitality_stages[entity_index])
        clash_damage = 0.0
        punishment_damage = 0.0

        for rule_index in range(1, len(latent_state.switches) + 1):
            omega = latent_state.omegas[rule_index - 1]
            switch_value = latent_state.switches[rule_index - 1]
            clash_coeff = clash_participation.get((rule_index, entity_index), 0.0)
            pun_coeff = punishment_participation.get((rule_index, entity_index), 0.0)

            if switch_value == 1 and clash_coeff > 0.0:
                clash_damage += omega * DELTA_CLASH * clash_coeff
            if switch_value > 0 and pun_coeff > 0.0:
                punishment_damage += omega * DELTA_PUN * pun_coeff

        amplitudes.append(_clip_unit_interval(base - clash_damage - punishment_damage))

    return tuple(amplitudes)


def transport_capacity(
    observed_state: ObservedState,
    dynamic_amplitudes: Sequence[float],
    source_index: int,
    target_index: int,
) -> float:
    observed_state.validate()
    _validate_amplitudes(dynamic_amplitudes, len(observed_state.base_elements))
    if source_index < 0 or source_index >= len(observed_state.base_elements):
        raise ValueError(f'source_index out of range: {source_index}')
    if target_index < 0 or target_index >= len(observed_state.base_elements):
        raise ValueError(f'target_index out of range: {target_index}')

    mask_source = observed_state.masks[source_index]
    mask_target = observed_state.masks[target_index]
    amplitude_source = dynamic_amplitudes[source_index]
    amplitude_target = dynamic_amplitudes[target_index]
    hierarchy_source = observed_state.hierarchy_levels[source_index]
    hierarchy_target = observed_state.hierarchy_levels[target_index]
    position_source = observed_state.positions[source_index]
    position_target = observed_state.positions[target_index]

    return (
        mask_source
        * mask_target
        * amplitude_source
        * amplitude_target
        * (hierarchy_source * hierarchy_target)
        * (1.0 / (1.0 + abs(position_source - position_target)))
    )


def realized_flux(
    observed_state: ObservedState,
    effective_elements: Sequence[Sequence[int]],
    dynamic_amplitudes: Sequence[float],
) -> tuple[tuple[float, ...], ...]:
    observed_state.validate()
    _validate_amplitudes(dynamic_amplitudes, len(observed_state.base_elements))
    if len(effective_elements) != len(observed_state.base_elements):
        raise ValueError('effective_elements length must match entity count')

    entity_count = len(observed_state.base_elements)
    matrix: list[list[float]] = []
    for source_index in range(entity_count):
        row: list[float] = []
        for target_index in range(entity_count):
            if source_index == target_index:
                row.append(0.0)
                continue

            source_element = tuple(effective_elements[source_index]).index(1)
            target_element = tuple(effective_elements[target_index]).index(1)
            t_value = transport_capacity(
                observed_state=observed_state,
                dynamic_amplitudes=dynamic_amplitudes,
                source_index=source_index,
                target_index=target_index,
            )
            interaction = wuxing_interaction(source_element, target_element)
            polarity = polarity_multiplier(
                observed_state.polarities[source_index],
                observed_state.polarities[target_index],
            )
            row.append(t_value * interaction * polarity)
        matrix.append(row)
    return tuple(tuple(row) for row in matrix)


def pillar_climate_summaries(
    observed_state: ObservedState,
    effective_elements: Sequence[Sequence[int]],
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float], float, float]:
    observed_state.validate()
    if len(effective_elements) != len(observed_state.base_elements):
        raise ValueError('effective_elements length must match entity count')

    theta_values: list[float] = []
    saturation_values: list[float] = []

    for pillar_position in (1, 2, 3, 4):
        numerator_theta = 0.0
        numerator_saturation = 0.0
        denominator = 0.0
        for entity_index, one_hot in enumerate(effective_elements):
            if observed_state.positions[entity_index] != pillar_position:
                continue
            mask = observed_state.masks[entity_index]
            hierarchy = observed_state.hierarchy_levels[entity_index]
            if mask == 0:
                continue
            element_index = tuple(one_hot).index(1)
            polarity = observed_state.polarities[entity_index]
            weight = mask * hierarchy
            numerator_theta += weight * temperature_contribution(element_index, polarity)
            numerator_saturation += weight * moisture_contribution(element_index, polarity)
            denominator += weight

        theta_values.append(numerator_theta / (denominator + EPSILON))
        saturation_values.append(numerator_saturation / (denominator + EPSILON))

    theta_chart = sum(theta_values) / 4.0
    saturation_chart = sum(saturation_values) / 4.0
    return (
        (theta_values[0], theta_values[1], theta_values[2], theta_values[3]),
        (
            saturation_values[0],
            saturation_values[1],
            saturation_values[2],
            saturation_values[3],
        ),
        theta_chart,
        saturation_chart,
    )


def pillar_retention(
    observed_state: ObservedState,
    flux_matrix: Sequence[Sequence[float]],
) -> tuple[float, float, float, float]:
    observed_state.validate()
    _validate_flux_matrix(flux_matrix, len(observed_state.base_elements))

    retention_values: list[float] = []
    for pillar_position in (1, 2, 3, 4):
        intra_sum = 0.0
        outbound_sum = 0.0
        for source_index in range(len(observed_state.base_elements)):
            if observed_state.positions[source_index] != pillar_position:
                continue
            for target_index in range(len(observed_state.base_elements)):
                if source_index == target_index:
                    continue
                value = abs(flux_matrix[source_index][target_index])
                if observed_state.positions[target_index] == pillar_position:
                    intra_sum += value
                else:
                    outbound_sum += value
        retention_values.append(intra_sum / (outbound_sum + EPSILON))

    return (
        retention_values[0],
        retention_values[1],
        retention_values[2],
        retention_values[3],
    )

