"""The model's tunable constants, carried with each run.

Every constant the energy, the mechanics, the rule families and the post-processing
weigh with lives on one immutable ModelParameters. A run takes it as an argument and
hands it on, so runs with different values never share state. Its defaults are the
model's own values, defined in primitives.py; a run given no parameters uses them.

A field's public name, as the API and its messages give it, is the constant's name:
the field name in capitals, such as LAMBDA_MODE for lambda_mode.
"""

import math
from dataclasses import dataclass, fields
from typing import cast

from eight_characters.evolution.primitives import (
    ACTIVE_EDGE_FRACTION_OF_MAX_FLUX,
    BOTTLENECK_QUANTILE,
    CASCADE_GAIN_MIN,
    CLUSTER_ALPHA,
    CLUSTER_BETA,
    CLUSTER_GAMMA,
    DELTA_CLASH,
    DELTA_PUN,
    DELTA_V_R,
    DIFF_POLARITY_MULTIPLIER,
    DOMAIN_RESONANCE_MATRIX,
    LAMBDA_ACT,
    LAMBDA_CLASH,
    LAMBDA_CLIM,
    LAMBDA_COR,
    LAMBDA_CROSS,
    LAMBDA_DOM,
    LAMBDA_FRAME,
    LAMBDA_INTER,
    LAMBDA_INTRA,
    LAMBDA_MODE,
    LAMBDA_PUN,
    LAMBDA_SCATTER,
    LAMBDA_V,
    OMEGA_MIN_R,
    OMEGA_SEASON,
    PARTIAL_STATE_WEIGHT_BY_S,
    PROXIMITY_WEIGHT_BY_GAP,
    PULSE_BALANCE_RATIO_MAX,
    PULSE_BALANCE_RATIO_MIN,
    SAME_POLARITY_MULTIPLIER,
    STAGE_AMPLITUDE_BY_STAGE,
    TAU_FOLLOW,
    TAU_R,
    TAU_STD,
    WUXING_MATRIX,
    domain_resonance_in,
    partial_state_weight_in,
    polarity_multiplier_in,
    proximity_weight_by_gap_in,
    stage_amplitude_in,
    wuxing_interaction_in,
)

Matrix = tuple[tuple[float, ...], ...]
Vector = tuple[float, ...]

# The tables' shapes: (rows, columns) for a matrix, (entries,) for a vector.
TABLE_SHAPES: dict[str, tuple[int, ...]] = {
    'wuxing_matrix': (5, 5),
    'domain_resonance_matrix': (4, 5),
    'stage_amplitude_by_stage': (12,),
    'partial_state_weight_by_s': (4,),
    'proximity_weight_by_gap': (3,),
}

# The three clustering weights share one unit: post-processing's distance is their
# weighted sum, and DBSCAN's radius is measured in it.
CLUSTER_WEIGHT_SUM_TOLERANCE = 1.0e-9


def parameter_id(field_name: str) -> str:
    return field_name.upper()


@dataclass(frozen=True)
class ModelParameters:
    same_polarity_multiplier: float = SAME_POLARITY_MULTIPLIER
    diff_polarity_multiplier: float = DIFF_POLARITY_MULTIPLIER
    omega_min_r: float = OMEGA_MIN_R
    tau_r: float = TAU_R
    tau_std: float = TAU_STD
    tau_follow: float = TAU_FOLLOW
    delta_clash: float = DELTA_CLASH
    delta_pun: float = DELTA_PUN
    delta_v_r: float = DELTA_V_R
    omega_season: float = OMEGA_SEASON
    lambda_intra: float = LAMBDA_INTRA
    lambda_inter: float = LAMBDA_INTER
    lambda_v: float = LAMBDA_V
    lambda_clim: float = LAMBDA_CLIM
    lambda_dom: float = LAMBDA_DOM
    lambda_mode: float = LAMBDA_MODE
    lambda_act: float = LAMBDA_ACT
    lambda_clash: float = LAMBDA_CLASH
    lambda_scatter: float = LAMBDA_SCATTER
    lambda_frame: float = LAMBDA_FRAME
    lambda_pun: float = LAMBDA_PUN
    lambda_cor: float = LAMBDA_COR
    lambda_cross: float = LAMBDA_CROSS
    active_edge_fraction_of_max_flux: float = ACTIVE_EDGE_FRACTION_OF_MAX_FLUX
    pulse_balance_ratio_min: float = PULSE_BALANCE_RATIO_MIN
    pulse_balance_ratio_max: float = PULSE_BALANCE_RATIO_MAX
    cascade_gain_min: float = CASCADE_GAIN_MIN
    bottleneck_quantile: float = BOTTLENECK_QUANTILE
    wuxing_matrix: Matrix = WUXING_MATRIX
    domain_resonance_matrix: Matrix = DOMAIN_RESONANCE_MATRIX
    stage_amplitude_by_stage: Vector = STAGE_AMPLITUDE_BY_STAGE
    partial_state_weight_by_s: Vector = PARTIAL_STATE_WEIGHT_BY_S
    proximity_weight_by_gap: Vector = PROXIMITY_WEIGHT_BY_GAP
    cluster_alpha: float = CLUSTER_ALPHA
    cluster_beta: float = CLUSTER_BETA
    cluster_gamma: float = CLUSTER_GAMMA

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Raise ValueError unless the engine can run with these values.

        These are the model's own limits. The explorer's API accepts narrower ranges,
        which explorer_controls.py lists.
        """
        for field in fields(self):
            name = parameter_id(field.name)
            value: object = getattr(self, field.name)
            shape = TABLE_SHAPES.get(field.name)
            if shape is None:
                _require_number(name, value)
            else:
                _require_table(name, value, shape)

        if not 0.0 < self.omega_min_r <= 1.0:
            raise ValueError(
                'OMEGA_MIN_R must be above 0 and at most 1: a rule with no pillar '
                'proximity can rise no higher than 1.'
            )
        for gap, weight in enumerate(self.proximity_weight_by_gap):
            if weight < 0.0:
                raise ValueError(
                    f'PROXIMITY_WEIGHT_BY_GAP[{gap}] must not be negative: '
                    'a rule can rise to 1 plus its proximity weight.'
                )
        for stage, amplitude in enumerate(self.stage_amplitude_by_stage, start=1):
            if amplitude < 0.0:
                raise ValueError(
                    f'STAGE_AMPLITUDE_BY_STAGE[{stage - 1}] (life stage {stage}) '
                    'must not be negative.'
                )
        cluster_weights = (self.cluster_alpha, self.cluster_beta, self.cluster_gamma)
        if any(weight < 0.0 for weight in cluster_weights):
            raise ValueError(
                'CLUSTER_ALPHA, CLUSTER_BETA and CLUSTER_GAMMA must not be negative.'
            )
        if abs(sum(cluster_weights) - 1.0) > CLUSTER_WEIGHT_SUM_TOLERANCE:
            raise ValueError(
                'CLUSTER_ALPHA, CLUSTER_BETA and CLUSTER_GAMMA must add up to 1, '
                f'not {sum(cluster_weights)!r}: the clustering radius is measured in '
                'their weighted distance.'
            )
        if self.pulse_balance_ratio_min > self.pulse_balance_ratio_max:
            raise ValueError(
                'PULSE_BALANCE_RATIO_MIN must not exceed PULSE_BALANCE_RATIO_MAX.'
            )
        if not 0.0 < self.active_edge_fraction_of_max_flux <= 1.0:
            raise ValueError(
                'ACTIVE_EDGE_FRACTION_OF_MAX_FLUX must be above 0 and at most 1.'
            )
        if not 0.0 <= self.bottleneck_quantile <= 1.0:
            raise ValueError('BOTTLENECK_QUANTILE must be from 0 to 1.')

    def polarity_multiplier(self, source_polarity: int, target_polarity: int) -> float:
        return polarity_multiplier_in(
            self.same_polarity_multiplier,
            self.diff_polarity_multiplier,
            source_polarity,
            target_polarity,
        )

    def wuxing_interaction(
        self, source_element_index: int, target_element_index: int
    ) -> float:
        return wuxing_interaction_in(
            self.wuxing_matrix, source_element_index, target_element_index
        )

    def domain_resonance(
        self, position_1_based: int, ten_god_group_index: int
    ) -> float:
        return domain_resonance_in(
            self.domain_resonance_matrix, position_1_based, ten_god_group_index
        )

    def stage_amplitude(self, vitality_stage_1_based: int) -> float:
        return stage_amplitude_in(self.stage_amplitude_by_stage, vitality_stage_1_based)

    def partial_state_weight(self, state_value: int) -> float:
        return partial_state_weight_in(self.partial_state_weight_by_s, state_value)

    def proximity_weight(self, gap: int) -> float:
        return proximity_weight_by_gap_in(self.proximity_weight_by_gap, gap)


def _require_number(name: str, value: object) -> None:
    # Only a float: callers convert numbers first, so an int or a bool here is a mistake.
    if not isinstance(value, float) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number, not {value!r}.')


def _tuple_of(value: object, length: int) -> tuple[object, ...] | None:
    if not isinstance(value, tuple):
        return None
    items = cast(tuple[object, ...], value)
    return items if len(items) == length else None


def _require_table(name: str, value: object, shape: tuple[int, ...]) -> None:
    if len(shape) == 1:
        rows: tuple[object, ...] = (value,)
    else:
        table = _tuple_of(value, shape[0])
        if table is None:
            raise ValueError(f'{name} must have {shape[0]} rows of {shape[1]} numbers.')
        rows = table
    for index, row in enumerate(rows):
        where = name if len(shape) == 1 else f'{name} row {index}'
        entries = _tuple_of(row, shape[-1])
        if entries is None:
            raise ValueError(f'{where} must have {shape[-1]} numbers.')
        for entry in entries:
            _require_number(where, entry)


DEFAULT_MODEL_PARAMETERS = ModelParameters()
