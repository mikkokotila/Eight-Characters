"""What the Evolution explorer lets a reader change, and the ranges it accepts.

Three kinds of control:
- run settings: how large a run is, its seed, and how its particles are clustered
  into basins;
- conventions: how the birth becomes pillars, the same conventions as the chart's;
- model parameters: the constants of ModelParameters, one control each, named after
  its constant (LAMBDA_MODE).

The ranges are the API's. A model parameter's range is narrower than the model's own
limits (ModelParameters.validate), to what is worth exploring. The run sizes are
capped so that the largest run takes about four and a half times as long as the
explorer's default one. A run's time grows with its particles, each costing about
0.05 s plus 0.0084 s per temperature step and sweep (measured on this engine): 64
particles, 4 steps and 2 sweeps take about 8 s, where the default 24, 2 and 1 take
1.8 s.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from typing import Any, Literal, cast

from eight_characters.conventions import (
    DAY_BOUNDARY_BASIS_CIVIL,
    DAY_BOUNDARY_BASIS_TRUE_SOLAR,
    HOUR_BASIS_CIVIL,
    HOUR_BASIS_TRUE_SOLAR,
    ZI_CONVENTION_SPLIT_MIDNIGHT,
    ZI_CONVENTION_WHOLE_ZI_23,
)
from eight_characters.evolution import (
    DEFAULT_MODEL_PARAMETERS,
    InferenceConfig,
    ModelParameters,
    PostprocessConfig,
)
from eight_characters.evolution.parameters import TABLE_SHAPES, parameter_id
from eight_characters.evolution.primitives import (
    ELEMENT_LABELS,
    TEN_GOD_GROUP_LABELS,
)

PILLAR_LABELS = ('Year', 'Month', 'Day', 'Hour')
# As the explorer names the twelve stages (app.js, LIFE_STAGE_INFO).
LIFE_STAGE_LABELS = (
    'Chang Sheng (Birth)',
    'Mu Yu (Bath)',
    'Guan Dai (Crowning)',
    'Lin Guan (Office)',
    'Di Wang (Prosperity)',
    'Shuai (Decline)',
    'Bing (Sickness)',
    'Si (Death)',
    'Mu (Tomb)',
    'Jue (Extinction)',
    'Tai (Gestation)',
    'Yang (Nourishment)',
)
SWITCH_STATE_LABELS = ('Off', 'State 1', 'State 2', 'State 3')
PILLAR_GAP_LABELS = ('Adjacent', 'One between', 'Two between')

Kind = Literal['integer', 'number', 'vector', 'matrix', 'choice']


@dataclass(frozen=True)
class Control:
    """One control: its range for a number or a table's entries, or its options."""

    id: str
    kind: Kind
    group: str
    label: str
    description: str
    default: Any
    minimum: float | int | None = None
    maximum: float | int | None = None
    step: float | int | None = None
    rows: tuple[str, ...] | None = None
    columns: tuple[str, ...] | None = None
    options: tuple[tuple[str, str], ...] | None = None

    def describe(self) -> dict[str, Any]:
        described: dict[str, Any] = {
            'id': self.id,
            'kind': self.kind,
            'group': self.group,
            'label': self.label,
            'description': self.description,
            'default': _json(self.default),
        }
        for key, value in (
            ('min', self.minimum),
            ('max', self.maximum),
            ('step', self.step),
            ('rows', self.rows),
            ('columns', self.columns),
        ):
            if value is not None:
                described[key] = _json(value)
        if self.options is not None:
            described['options'] = [
                {'value': value, 'label': label} for value, label in self.options
            ]
        return described


def _json(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_json(item) for item in cast(tuple[Any, ...], value)]
    return value


# ── Run settings ──

RUN_CONTROLS = (
    Control(
        'particles',
        'integer',
        'Run',
        'Particles',
        "How many particles the run follows. More find more of the chart's basins, "
        'and cost more.',
        24,
        8,
        64,
        1,
    ),
    Control(
        'temperature_steps',
        'integer',
        'Run',
        'Temperature Steps',
        'How many steps the run cools through, from temperature 10 to 1.',
        2,
        1,
        4,
        1,
    ),
    Control(
        'sweeps_per_step',
        'integer',
        'Run',
        'Sweeps Per Step',
        'How many times each particle proposes a change at each temperature.',
        1,
        1,
        2,
        1,
    ),
    Control(
        'seed',
        'integer',
        'Run',
        'Seed',
        'The random seed. The same seed and settings give the same run.',
        42,
        0,
        2**31 - 1,
        1,
    ),
    Control(
        'dbscan_eps',
        'number',
        'Clustering',
        'Basin Clustering Radius',
        'How close, in the weighted distance, particles must be to share a basin.',
        0.08,
        0.01,
        1.0,
        0.01,
    ),
    Control(
        'dbscan_min_samples',
        'integer',
        'Clustering',
        'Basin Clustering Min Samples',
        "How many particles within the radius make a basin's core. At most the "
        'number of particles.',
        1,
        1,
        64,
        1,
    ),
)


@dataclass(frozen=True)
class ExplorerRun:
    """A run's size, seed and clustering; the defaults are the explorer's run."""

    particles: int = 24
    temperature_steps: int = 2
    sweeps_per_step: int = 1
    seed: int = 42
    dbscan_eps: float = 0.08
    dbscan_min_samples: int = 1

    def __post_init__(self) -> None:
        for control in RUN_CONTROLS:
            value = getattr(self, control.id)
            assert control.minimum is not None and control.maximum is not None
            if not control.minimum <= value <= control.maximum:
                raise ValueError(
                    f'run.{control.id} must be from {control.minimum} to '
                    f'{control.maximum}, not {value!r}.'
                )
        if self.dbscan_min_samples > self.particles:
            raise ValueError(
                f'run.dbscan_min_samples ({self.dbscan_min_samples}) must not exceed '
                f'run.particles ({self.particles}).'
            )

    def inference_config(self) -> InferenceConfig:
        return InferenceConfig(
            particles=self.particles,
            temperature_steps=self.temperature_steps,
            sweeps_per_step=self.sweeps_per_step,
            seed=self.seed,
        )

    def postprocess_config(self) -> PostprocessConfig:
        # One pass of each relaxation keeps the explorer interactive.
        return PostprocessConfig(
            discrete_relax_max_passes=1,
            continuous_passes=1,
            dbscan_eps=self.dbscan_eps,
            dbscan_min_samples=self.dbscan_min_samples,
        )

    def describe(self) -> dict[str, Any]:
        return {control.id: getattr(self, control.id) for control in RUN_CONTROLS}


DEFAULT_EXPLORER_RUN = ExplorerRun()

# ── Conventions ──

CONVENTION_CONTROLS = (
    Control(
        'zi_convention',
        'choice',
        'Conventions',
        'Zi Hour',
        'Which day an hour from 23:00 to midnight belongs to.',
        ZI_CONVENTION_SPLIT_MIDNIGHT,
        options=(
            (ZI_CONVENTION_SPLIT_MIDNIGHT, 'Split at midnight'),
            (ZI_CONVENTION_WHOLE_ZI_23, 'Whole Zi from 23:00'),
        ),
    ),
    Control(
        'hour_basis',
        'choice',
        'Conventions',
        'Hour Basis',
        'The clock the hour pillar is read from.',
        HOUR_BASIS_TRUE_SOLAR,
        options=(
            (HOUR_BASIS_TRUE_SOLAR, 'True solar time'),
            (HOUR_BASIS_CIVIL, 'Clock time'),
        ),
    ),
    Control(
        'day_boundary_basis',
        'choice',
        'Conventions',
        'Day Boundary Basis',
        'The clock whose midnight starts the day pillar.',
        DAY_BOUNDARY_BASIS_TRUE_SOLAR,
        options=(
            (DAY_BOUNDARY_BASIS_TRUE_SOLAR, 'True solar time'),
            (DAY_BOUNDARY_BASIS_CIVIL, 'Clock time'),
        ),
    ),
)

# ── Model parameters ──


def _number(
    field_name: str,
    group: str,
    label: str,
    description: str,
    minimum: float,
    maximum: float,
) -> Control:
    return Control(
        parameter_id(field_name),
        'number',
        group,
        label,
        description,
        getattr(DEFAULT_MODEL_PARAMETERS, field_name),
        minimum,
        maximum,
        0.01,
    )


def _table(
    field_name: str,
    label: str,
    description: str,
    minimum: float,
    maximum: float,
    rows: tuple[str, ...] | None,
    columns: tuple[str, ...],
) -> Control:
    return Control(
        parameter_id(field_name),
        'matrix' if rows is not None else 'vector',
        'Tables',
        label,
        description,
        getattr(DEFAULT_MODEL_PARAMETERS, field_name),
        minimum,
        maximum,
        0.01,
        rows=rows,
        columns=columns,
    )


MODEL_CONTROLS = (
    _number(
        'same_polarity_multiplier',
        'Polarity',
        'Yin-Yang Same-Polarity Resonance',
        'Scales the flow between two entities of the same polarity.',
        0.8,
        1.6,
    ),
    _number(
        'diff_polarity_multiplier',
        'Polarity',
        'Yin-Yang Cross-Polarity Resonance',
        'Scales the flow between two entities of opposite polarity.',
        0.6,
        1.4,
    ),
    _number(
        'omega_min_r',
        'Rule Activation',
        'Minimum Rule Qi Activation',
        "The lowest a switched-on rule's qi activation goes. Its highest is 1 plus "
        "the rule's proximity weight, never below 1.",
        0.1,
        1.0,
    ),
    _number(
        'tau_r',
        'Rule Activation',
        'Rule Support Gate',
        'A rule switched on with support below this is penalized by the square of '
        'the shortfall.',
        0.1,
        1.0,
    ),
    _number(
        'lambda_act',
        'Rule Activation',
        'Activated Rule Penalty Weight',
        'Weight of that penalty for a rule its support does not carry.',
        0.1,
        12.0,
    ),
    _number(
        'tau_std',
        'Structure Mode',
        'Standard Structure Tolerance',
        'In the Standard mode, the larger of the strength and weakness scores may '
        'reach this before it is penalized.',
        0.0,
        1.0,
    ),
    _number(
        'tau_follow',
        'Structure Mode',
        'Follow-Pattern Tolerance',
        'In a Follow mode, the score the mode follows must reach this, or it is '
        'penalized.',
        0.0,
        1.0,
    ),
    _number(
        'lambda_mode',
        'Structure Mode',
        'Structure-Mode Fidelity Weight',
        "Weight of the chart's fit to its structure mode.",
        0.1,
        20.0,
    ),
    _number(
        'delta_clash',
        'Damage',
        'Clash Damage Intensity',
        "How much an active clash lowers each participant's vitality, per unit of "
        "the rule's qi activation.",
        0.0,
        1.0,
    ),
    _number(
        'delta_pun',
        'Damage',
        'Punishment Damage Intensity',
        "How much an active punishment lowers each participant's vitality, per "
        'unit of qi activation.',
        0.0,
        0.8,
    ),
    _number(
        'delta_v_r',
        'Damage',
        'Clash Vitality Displacement',
        'The vitality an active clash displaces, squared in the clash energy.',
        0.0,
        1.0,
    ),
    _number(
        'lambda_intra',
        'Energy Weights',
        'Intra-Pillar Coherence Weight',
        'Weight of the energy within each pillar: its chemistry and how far its '
        "stem sits from its life stage's vitality.",
        0.1,
        10.0,
    ),
    _number(
        'lambda_inter',
        'Energy Weights',
        'Inter-Pillar Flow Weight',
        'Weight of the flow between pillars, which lowers the energy.',
        0.1,
        10.0,
    ),
    _number(
        'lambda_v',
        'Energy Weights',
        'Life-Stage Anchor Weight',
        "Weight of a stem's distance from its life stage's vitality.",
        0.1,
        20.0,
    ),
    _number(
        'lambda_clim',
        'Energy Weights',
        'Climate Balance Weight',
        'Weight of the climate gap between pillars that exchange flow.',
        0.1,
        10.0,
    ),
    _number(
        'lambda_dom',
        'Energy Weights',
        'Pillar Domain Resonance Weight',
        "Weight of each entity's ten-god resonance with its pillar.",
        0.1,
        12.0,
    ),
    _number(
        'lambda_clash',
        'Energy Weights',
        'Clash Penalty Weight',
        'Weight of the vitality an active clash displaces.',
        0.1,
        20.0,
    ),
    _number(
        'lambda_scatter',
        'Energy Weights',
        'Clash Scatter Penalty Weight',
        'Weight of the chemistry an active clash scatters.',
        0.1,
        12.0,
    ),
    _number(
        'lambda_frame',
        'Energy Weights',
        'Three-Frame Conversion Weight',
        'Weight of the entities that resist an active three-element frame.',
        0.1,
        20.0,
    ),
    _number(
        'omega_season',
        'Energy Weights',
        'Seasonal Qi Boost',
        "How much more a frame weighs when its element is the season's.",
        0.0,
        2.0,
    ),
    _number(
        'lambda_pun',
        'Energy Weights',
        'Punishment Retention Weight',
        'Weight of the flow an active punishment traps within its pillars.',
        0.1,
        16.0,
    ),
    _number(
        'lambda_cor',
        'Energy Weights',
        'Harmony Corruption Weight',
        'Weight of a harm against a harmony at its full state.',
        0.1,
        16.0,
    ),
    _number(
        'lambda_cross',
        'Energy Weights',
        'Ten-God Reassignment Cost',
        'Weight of the ten-god change a combination or harmony brings.',
        0.1,
        24.0,
    ),
    _number(
        'active_edge_fraction_of_max_flux',
        'Motifs',
        'Qi Current Activation Threshold',
        'An edge counts in the motifs from this fraction of the largest flow.',
        0.05,
        0.8,
    ),
    _number(
        'pulse_balance_ratio_min',
        'Motifs',
        'Pulse Balance Lower Bound',
        'A pulse takes in at least this ratio of what it gives out.',
        0.1,
        1.0,
    ),
    _number(
        'pulse_balance_ratio_max',
        'Motifs',
        'Pulse Balance Upper Bound',
        'A pulse takes in at most this ratio of what it gives out.',
        1.0,
        10.0,
    ),
    _number(
        'cascade_gain_min',
        'Motifs',
        'Cascade Amplification Gate',
        "A cascade's last step carries at least this multiple of its first.",
        1.0,
        3.0,
    ),
    _number(
        'bottleneck_quantile',
        'Motifs',
        'Pressure Node Cutoff',
        "A bottleneck's flow per unit of vitality reaches at least this quantile.",
        0.5,
        0.99,
    ),
    _number(
        'cluster_alpha',
        'Clustering',
        'Cluster Distance Weight: Switches',
        'Share of the distance between particles from their rule switches and mode.',
        0.0,
        1.0,
    ),
    _number(
        'cluster_beta',
        'Clustering',
        'Cluster Distance Weight: Elements',
        "Share of the distance from their entities' effective elements.",
        0.0,
        1.0,
    ),
    _number(
        'cluster_gamma',
        'Clustering',
        'Cluster Distance Weight: Activations',
        "Share of the distance from their rules' qi activations. The three shares "
        'add up to 1.',
        0.0,
        1.0,
    ),
    _table(
        'wuxing_matrix',
        'Element Interaction Matrix',
        'The flow from each element (row) to each element (column): an element '
        'produces, controls, drains or is controlled by another.',
        -2.0,
        2.0,
        ELEMENT_LABELS,
        ELEMENT_LABELS,
    ),
    _table(
        'domain_resonance_matrix',
        'Pillar Domain Resonance Matrix',
        'How each ten-god group (column) resonates in each pillar (row).',
        -1.5,
        1.5,
        PILLAR_LABELS,
        TEN_GOD_GROUP_LABELS,
    ),
    _table(
        'stage_amplitude_by_stage',
        'Life-Stage Vitality Profile',
        'The vitality of each of the twelve life stages.',
        0.0,
        1.5,
        None,
        LIFE_STAGE_LABELS,
    ),
    _table(
        'partial_state_weight_by_s',
        'Partial-State Weight Curve',
        'How much of its ten-god change a combination or harmony brings at each '
        'switch state.',
        0.0,
        1.0,
        None,
        SWITCH_STATE_LABELS,
    ),
    _table(
        'proximity_weight_by_gap',
        'Pillar Distance Decay Curve',
        "A rule's proximity weight by how far apart its pillars are.",
        0.0,
        1.5,
        None,
        PILLAR_GAP_LABELS,
    ),
)
MODEL_CONTROLS_BY_ID = {control.id: control for control in MODEL_CONTROLS}
FIELD_BY_ID = {
    parameter_id(field.name): field.name for field in fields(ModelParameters)
}


def catalogue() -> dict[str, Any]:
    """Every control, with its default, range and labels: GET /api/evolution_controls."""
    return {
        'run': [control.describe() for control in RUN_CONTROLS],
        'conventions': [control.describe() for control in CONVENTION_CONTROLS],
        'model': [control.describe() for control in MODEL_CONTROLS],
    }


def resolve_model_parameters(overrides: Mapping[str, object]) -> ModelParameters:
    """The defaults with these overrides, each within its control's range.

    Raises ValueError, naming the parameter, for an unknown name, a value of the wrong
    kind or shape, a value outside its range, or values the model cannot run with
    together (ModelParameters.validate).
    """
    changes: dict[str, Any] = {}
    for control_id, value in overrides.items():
        control = MODEL_CONTROLS_BY_ID.get(control_id)
        if control is None:
            raise ValueError(
                f'model.{control_id} is not a model parameter; '
                'GET /api/evolution_controls lists them.'
            )
        changes[FIELD_BY_ID[control_id]] = _accept(control, value)
    try:
        return replace(DEFAULT_MODEL_PARAMETERS, **changes)
    except ValueError as error:
        raise ValueError(f'model: {error}') from error


def _accept(control: Control, value: object) -> Any:
    name = f'model.{control.id}'
    if control.kind == 'number':
        return _in_range(name, value, control)
    shape = TABLE_SHAPES[FIELD_BY_ID[control.id]]
    if control.kind == 'vector':
        return _entries(name, value, shape[0], control)
    rows = _sequence(value, shape[0])
    if rows is None:
        raise ValueError(f'{name} must be {shape[0]} rows of {shape[1]} numbers.')
    return tuple(
        _entries(f'{name} row {index}', row, shape[1], control)
        for index, row in enumerate(rows)
    )


def _entries(
    name: str, value: object, count: int, control: Control
) -> tuple[float, ...]:
    entries = _sequence(value, count)
    if entries is None:
        raise ValueError(f'{name} must be {count} numbers.')
    return tuple(_in_range(name, entry, control) for entry in entries)


def _sequence(value: object, length: int) -> list[object] | None:
    if not isinstance(value, list):
        return None
    items = cast(list[object], value)
    return items if len(items) == length else None


def _in_range(name: str, value: object, control: Control) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
    ):
        raise ValueError(f'{name} must be a number, not {value!r}.')
    assert control.minimum is not None and control.maximum is not None
    if not control.minimum <= value <= control.maximum:
        raise ValueError(
            f'{name} must be from {control.minimum} to {control.maximum}, '
            f'not {value!r}.'
        )
    return float(value)


def describe_model(parameters: ModelParameters) -> dict[str, Any]:
    return {
        control.id: _json(getattr(parameters, FIELD_BY_ID[control.id]))
        for control in MODEL_CONTROLS
    }
