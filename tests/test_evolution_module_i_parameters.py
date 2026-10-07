import ast
import inspect
import json
import threading
import unittest
from dataclasses import FrozenInstanceError, asdict, fields, replace
from pathlib import Path
from types import ModuleType
from typing import Any

from eight_characters import main
from eight_characters.evolution import (
    energy,
    families,
    inference,
    mechanics,
    pipeline,
    postprocess,
    primitives,
)
from eight_characters.evolution.energy import compute_energy_breakdown
from eight_characters.evolution.families import evaluate_all_families
from eight_characters.evolution.inference import InferenceConfig, build_particle
from eight_characters.evolution.mechanics import compute_dynamic_vitality_amplitudes
from eight_characters.evolution.parameters import (
    DEFAULT_MODEL_PARAMETERS,
    TABLE_SHAPES,
    ModelParameters,
    parameter_id,
)
from eight_characters.evolution.pipeline import EvolutionInput, run_natal_mvp
from eight_characters.evolution.postprocess import (
    PostprocessConfig,
    _distance,
    _omega_bounds,
)
from eight_characters.evolution.primitives import (
    element_to_one_hot,
    season_element_from_month_branch,
    stem_element_polarity,
)
from eight_characters.evolution.state import (
    LatentState,
    ObservedState,
    recompute_effective_ten_gods,
)
from eight_characters.explorer import build_data_js_from_evolution as builder

ENGINE_MODULES: tuple[ModuleType, ...] = (
    energy,
    families,
    inference,
    mechanics,
    pipeline,
    postprocess,
    builder,
    main,
)
CONSTANT_NAMES = {parameter_id(field.name) for field in fields(ModelParameters)}
TABLE_LOOKUPS = {
    'domain_resonance',
    'partial_state_weight',
    'polarity_multiplier',
    'proximity_weight_by_gap',
    'stage_amplitude',
    'wuxing_interaction',
}
# The parameters the engine reads through a lookup, and the lookup it reads them by.
LOOKUP_OF = {
    'same_polarity_multiplier': 'polarity_multiplier',
    'diff_polarity_multiplier': 'polarity_multiplier',
    'wuxing_matrix': 'wuxing_interaction',
    'domain_resonance_matrix': 'domain_resonance',
    'stage_amplitude_by_stage': 'stage_amplitude',
    'partial_state_weight_by_s': 'partial_state_weight',
    'proximity_weight_by_gap': 'proximity_weight',
}

# Two particles suffice: post-processing relaxes each through every switch of every
# rule, which is where most parameters weigh in.
SMALL_RUN = InferenceConfig(
    particles=2, temperature_steps=1, sweeps_per_step=1, seed=42
)
EXPLORER_POSTPROCESS = PostprocessConfig(
    discrete_relax_max_passes=1,
    continuous_passes=1,
    dbscan_eps=0.08,
    dbscan_min_samples=1,
)


def _birth(
    branch_ids: tuple[int, int, int, int],
    elements: tuple[int, ...],
    polarities: tuple[int, ...],
    hierarchy_levels: tuple[int, ...],
    positions: tuple[int, ...],
    vitality_stages: tuple[int, ...],
    day_master_index: int,
) -> EvolutionInput:
    return EvolutionInput(
        branch_ids=branch_ids,
        base_elements=tuple(element_to_one_hot(element) for element in elements),
        polarities=polarities,
        hierarchy_levels=hierarchy_levels,
        positions=positions,
        masks=(1,) * len(elements),
        vitality_stages=vitality_stages,
        day_master_index=day_master_index,
    )


# The engine's input for five births, as the explorer builds it (true solar time). The
# first exercises clashes and punishments; together they exercise every parameter the
# explorer's runs can reach.
BIRTHS = {
    '2010-06-15 12:00 New York': _birth(
        (3, 7, 9, 7),
        (3, 0, 1, 2, 4, 1, 2, 1, 3, 4, 2, 0, 1, 2),
        (1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 0, 0),
        (4, 3, 2, 1, 4, 3, 2, 4, 3, 2, 1, 4, 3, 2),
        (1, 1, 1, 1, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4),
        (10, 4, 1, 1, 11, 4, 4, 7, 4, 1, 7, 8, 4, 4),
        7,
    ),
    '2004-05-20 11:17 Chengdu': _birth(
        (9, 6, 12, 6),
        (0, 3, 4, 2, 2, 1, 3, 2, 2, 4, 0, 2, 1, 3, 2),
        (1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 0, 1, 1, 1),
        (4, 3, 2, 1, 4, 3, 2, 1, 4, 3, 2, 4, 3, 2, 1),
        (1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 4, 4, 4, 4),
        (10, 4, 1, 7, 5, 4, 1, 4, 11, 4, 1, 5, 4, 1, 4),
        8,
    ),
    '2023-02-04 10:42 Beijing': _birth(
        (3, 2, 6, 6),
        (4, 0, 1, 2, 4, 2, 4, 3, 4, 1, 3, 2, 1, 1, 3, 2),
        (1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0, 1, 1, 1),
        (4, 3, 2, 1, 4, 3, 2, 1, 4, 3, 2, 1, 4, 3, 2, 1),
        (1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4),
        (7, 4, 1, 1, 3, 9, 3, 12, 11, 4, 1, 4, 5, 4, 1, 4),
        8,
    ),
    '1999-12-31 00:05 Sydney': _birth(
        (4, 1, 5, 1),
        (2, 0, 1, 4, 1, 2, 0, 4, 2, 4),
        (0, 0, 1, 0, 1, 1, 0, 0, 1, 0),
        (4, 3, 4, 3, 4, 3, 2, 1, 4, 3),
        (1, 1, 2, 2, 3, 3, 3, 3, 4, 4),
        (7, 4, 11, 4, 3, 3, 3, 12, 11, 4),
        4,
    ),
    '1988-02-04 16:30 Chengdu': _birth(
        (4, 2, 2, 9),
        (1, 0, 4, 2, 4, 3, 2, 2, 4, 3, 4, 3, 4, 2),
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1),
        (4, 3, 4, 3, 2, 1, 4, 3, 2, 1, 4, 3, 2, 1),
        (1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4),
        (7, 4, 3, 9, 3, 12, 9, 9, 3, 12, 1, 4, 1, 7),
        6,
    ),
}

# Parameters whose terms only charts with a frame, a harm against a full harmony, a
# partial combination, or particles in more than one place exercise; their own tests
# below build such states directly.
REACHED_BY_CONSTRUCTED_STATES = {
    'lambda_frame',
    'omega_season',
    'lambda_cor',
    'lambda_cross',
    'cluster_alpha',
    'cluster_beta',
    'cluster_gamma',
}


def _changed(name: str) -> ModelParameters:
    """The defaults with one parameter moved well within the model's limits."""
    moved: dict[str, float] = {
        'omega_min_r': 0.9,
        'tau_std': 0.0,
        'tau_follow': 0.6,
        'active_edge_fraction_of_max_flux': 0.6,
        'pulse_balance_ratio_min': 0.9,
        'pulse_balance_ratio_max': 1.1,
        'cascade_gain_min': 1.05,
        'bottleneck_quantile': 0.5,
    }
    if name in moved:
        return replace(DEFAULT_MODEL_PARAMETERS, **{name: moved[name]})
    value: Any = getattr(DEFAULT_MODEL_PARAMETERS, name)
    if name in TABLE_SHAPES and len(TABLE_SHAPES[name]) == 2:
        value = tuple(tuple(entry * 1.5 + 0.1 for entry in row) for row in value)
    elif name in TABLE_SHAPES:
        value = tuple(entry * 1.5 + 0.1 for entry in value)
    else:
        value = value * 1.5 + 0.1
    return replace(DEFAULT_MODEL_PARAMETERS, **{name: value})


def _run(
    evolution_input: EvolutionInput, parameters: ModelParameters | None
) -> tuple[str, str]:
    """A small run's output and the explorer's graph of it, as exact JSON."""
    if parameters is None:
        output = run_natal_mvp(evolution_input, SMALL_RUN, EXPLORER_POSTPROCESS)
    else:
        output = run_natal_mvp(
            evolution_input, SMALL_RUN, EXPLORER_POSTPROCESS, parameters=parameters
        )
    payload = json.loads(json.dumps(asdict(output)))
    if parameters is None:
        graph = builder.build_multi_basin_graph_data(payload)
    else:
        graph = builder.build_multi_basin_graph_data(payload, parameters=parameters)
    return json.dumps(payload, sort_keys=True), json.dumps(graph, sort_keys=True)


def _syntax(module: ModuleType) -> ast.Module:
    assert module.__file__ is not None
    return ast.parse(Path(module.__file__).read_text(encoding='utf-8'))


def _observed(
    stem_ids: tuple[int, int, int, int],
    branch_ids: tuple[int, int, int, int],
) -> ObservedState:
    elements = []
    polarities = []
    for stem_id in stem_ids:
        element_index, polarity = stem_element_polarity(stem_id)
        elements.append(element_to_one_hot(element_index))
        polarities.append(polarity)
    return ObservedState(
        branch_ids=branch_ids,
        base_elements=tuple(elements),
        polarities=tuple(polarities),
        hierarchy_levels=(4, 4, 4, 4),
        positions=(1, 2, 3, 4),
        masks=(1, 1, 1, 1),
        vitality_stages=(5, 5, 5, 5),
        day_master_index=2,
    )


def _latent(switched: dict[int, int], mode: str = 'Standard') -> LatentState:
    switches = [0] * 34
    for rule_index, value in switched.items():
        switches[rule_index - 1] = value
    return LatentState(switches=tuple(switches), omegas=(0.5,) * 34, mode=mode)


def _energy(
    observed: ObservedState, latent: LatentState, parameters: ModelParameters
) -> energy.EnergyBreakdown:
    effective_elements = observed.base_elements
    return compute_energy_breakdown(
        observed_state=observed,
        latent_state=latent,
        effective_elements=effective_elements,
        effective_ten_gods=recompute_effective_ten_gods(
            observed_state=observed,
            effective_elements=effective_elements,
            mode=latent.mode,
        ),
        dynamic_amplitudes=compute_dynamic_vitality_amplitudes(
            observed_state=observed, latent_state=latent, parameters=parameters
        ),
        family_evaluations=evaluate_all_families(observed, parameters=parameters),
        parameters=parameters,
    )


class TestEvolutionModuleIParameterDefaults(unittest.TestCase):
    def test_defaults_are_the_models_own_constants(self) -> None:
        for field in fields(ModelParameters):
            with self.subTest(parameter=parameter_id(field.name)):
                self.assertEqual(
                    getattr(DEFAULT_MODEL_PARAMETERS, field.name),
                    getattr(primitives, parameter_id(field.name)),
                )

    def test_a_run_without_parameters_is_a_run_with_the_defaults(self) -> None:
        birth = BIRTHS['1988-02-04 16:30 Chengdu']
        without = _run(birth, None)
        self.assertEqual(_run(birth, DEFAULT_MODEL_PARAMETERS), without)
        self.assertEqual(_run(birth, ModelParameters()), without)

    def test_parameters_cannot_change_once_made(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            DEFAULT_MODEL_PARAMETERS.lambda_mode = 6.5  # type: ignore[misc]


class TestEvolutionModuleIParameterLimits(unittest.TestCase):
    def assert_refused(self, message: str, **values: Any) -> None:
        with self.assertRaises(ValueError) as caught:
            replace(DEFAULT_MODEL_PARAMETERS, **values)
        self.assertIn(message, str(caught.exception))

    def test_numbers_must_be_finite_floats(self) -> None:
        for value in (float('nan'), float('inf'), 6, True, '6.5', None):
            with self.subTest(value=value):
                self.assert_refused(
                    'LAMBDA_MODE must be a finite number', lambda_mode=value
                )

    def test_tables_must_have_their_shapes(self) -> None:
        matrix = primitives.WUXING_MATRIX
        self.assert_refused(
            'WUXING_MATRIX must have 5 rows of 5 numbers', wuxing_matrix=matrix[:4]
        )
        self.assert_refused(
            'WUXING_MATRIX row 2 must have 5 numbers',
            wuxing_matrix=(*matrix[:2], matrix[2][:4], *matrix[3:]),
        )
        self.assert_refused(
            'WUXING_MATRIX must have 5 rows of 5 numbers',
            wuxing_matrix=[list(row) for row in matrix],
        )
        self.assert_refused(
            'STAGE_AMPLITUDE_BY_STAGE must have 12 numbers',
            stage_amplitude_by_stage=primitives.STAGE_AMPLITUDE_BY_STAGE[:11],
        )
        self.assert_refused(
            'DOMAIN_RESONANCE_MATRIX row 3 must be a finite number',
            domain_resonance_matrix=(
                *primitives.DOMAIN_RESONANCE_MATRIX[:3],
                (0.0, 1.0, float('nan'), -0.25, -1.0),
            ),
        )

    def test_omega_floor_stays_below_every_rules_ceiling(self) -> None:
        # A rule rises to 1 plus its proximity weight, and a rule with no pair of
        # pillars has a proximity weight of 0.
        for value in (0.0, -0.1, 1.000001, 2.0):
            with self.subTest(value=value):
                self.assert_refused(
                    'OMEGA_MIN_R must be above 0 and at most 1', omega_min_r=value
                )
        self.assertEqual(
            replace(DEFAULT_MODEL_PARAMETERS, omega_min_r=1.0).omega_min_r, 1.0
        )

    def test_weights_and_amplitudes_must_not_be_negative(self) -> None:
        self.assert_refused(
            'PROXIMITY_WEIGHT_BY_GAP[1] must not be negative',
            proximity_weight_by_gap=(1.0, -0.5, 0.25),
        )
        stages = list(primitives.STAGE_AMPLITUDE_BY_STAGE)
        stages[3] = -0.1
        self.assert_refused(
            'STAGE_AMPLITUDE_BY_STAGE[3] (life stage 4) must not be negative',
            stage_amplitude_by_stage=tuple(stages),
        )

    def test_clustering_weights_are_shares_of_one(self) -> None:
        self.assert_refused(
            'must not be negative',
            cluster_alpha=1.1,
            cluster_beta=-0.2,
            cluster_gamma=0.1,
        )
        self.assert_refused('must add up to 1', cluster_alpha=0.5)
        # 0.6 + 0.3 + 0.1 is 0.9999999999999999 in floating point.
        self.assertEqual(
            replace(
                DEFAULT_MODEL_PARAMETERS, cluster_alpha=0.7, cluster_beta=0.2
            ).cluster_alpha,
            0.7,
        )

    def test_motif_thresholds_keep_their_order_and_ranges(self) -> None:
        self.assert_refused(
            'PULSE_BALANCE_RATIO_MIN must not exceed PULSE_BALANCE_RATIO_MAX',
            pulse_balance_ratio_min=2.5,
        )
        for value in (0.0, 1.5):
            self.assert_refused(
                'ACTIVE_EDGE_FRACTION_OF_MAX_FLUX must be above 0 and at most 1',
                active_edge_fraction_of_max_flux=value,
            )
        for value in (-0.1, 1.5):
            self.assert_refused(
                'BOTTLENECK_QUANTILE must be from 0 to 1', bottleneck_quantile=value
            )


class TestEvolutionModuleIParameterWiring(unittest.TestCase):
    """Every value the engine weighs with comes from the run's parameters."""

    def test_no_engine_module_reads_a_model_constant_itself(self) -> None:
        for module in ENGINE_MODULES:
            for node in ast.walk(_syntax(module)):
                if isinstance(node, ast.ImportFrom):
                    imported = {alias.name for alias in node.names}
                    self.assertFalse(
                        imported & (CONSTANT_NAMES | TABLE_LOOKUPS),
                        f'{module.__name__} imports {imported & (CONSTANT_NAMES | TABLE_LOOKUPS)}',
                    )
                if isinstance(node, ast.Name):
                    self.assertNotIn(
                        node.id, CONSTANT_NAMES | TABLE_LOOKUPS, module.__name__
                    )
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, CONSTANT_NAMES, module.__name__)

    def test_every_call_hands_the_parameters_on(self) -> None:
        takers = {
            name
            for module in ENGINE_MODULES
            for name, member in vars(module).items()
            if inspect.isfunction(member)
            and member.__module__ == module.__name__
            and 'parameters' in inspect.signature(member).parameters
        }
        self.assertIn('compute_energy_breakdown', takers)
        for module in ENGINE_MODULES:
            for node in ast.walk(_syntax(module)):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr
                    if isinstance(func, ast.Attribute)
                    else None
                )
                if name in takers:
                    self.assertTrue(
                        any(keyword.arg == 'parameters' for keyword in node.keywords),
                        f'{module.__name__}:{node.lineno} calls {name} without parameters',
                    )

    def test_every_parameter_is_read(self) -> None:
        read = {
            node.attr
            for module in ENGINE_MODULES
            for node in ast.walk(_syntax(module))
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == 'parameters'
        }
        for field in fields(ModelParameters):
            with self.subTest(parameter=parameter_id(field.name)):
                self.assertIn(LOOKUP_OF.get(field.name, field.name), read)


class TestEvolutionModuleIParameterReach(unittest.TestCase):
    """A changed parameter changes what the run and its graph come to."""

    def test_each_parameter_reaches_the_run_or_its_graph(self) -> None:
        defaults: dict[str, tuple[str, str]] = {}
        for field in fields(ModelParameters):
            if field.name in REACHED_BY_CONSTRUCTED_STATES:
                continue
            with self.subTest(parameter=parameter_id(field.name)):
                changed = _changed(field.name)
                reached = False
                for name, birth in BIRTHS.items():
                    if name not in defaults:
                        defaults[name] = _run(birth, DEFAULT_MODEL_PARAMETERS)
                    if _run(birth, changed) != defaults[name]:
                        reached = True
                        break
                self.assertTrue(reached, 'no birth changed')

    def test_the_graph_is_drawn_with_the_runs_parameters(self) -> None:
        birth = BIRTHS['2010-06-15 12:00 New York']
        payload = json.loads(
            json.dumps(asdict(run_natal_mvp(birth, SMALL_RUN, EXPLORER_POSTPROCESS)))
        )
        drawn = builder.build_multi_basin_graph_data(
            payload, parameters=DEFAULT_MODEL_PARAMETERS
        )
        for name in (
            'wuxing_matrix',
            'same_polarity_multiplier',
            'stage_amplitude_by_stage',
        ):
            with self.subTest(parameter=parameter_id(name)):
                self.assertNotEqual(
                    builder.build_multi_basin_graph_data(
                        payload, parameters=_changed(name)
                    ),
                    drawn,
                )

    def test_the_graphs_flux_is_computed_with_the_runs_parameters(self) -> None:
        # Flux is transport times interaction times polarity, so doubling every
        # interaction doubles every edge's flux, exactly.
        birth = BIRTHS['2010-06-15 12:00 New York']
        payload = json.loads(
            json.dumps(asdict(run_natal_mvp(birth, SMALL_RUN, EXPLORER_POSTPROCESS)))
        )
        doubled = replace(
            DEFAULT_MODEL_PARAMETERS,
            wuxing_matrix=tuple(
                tuple(2.0 * entry for entry in row) for row in primitives.WUXING_MATRIX
            ),
        )
        views = builder.build_multi_basin_graph_data(
            payload, parameters=DEFAULT_MODEL_PARAMETERS
        )['basin_views']
        doubled_views = builder.build_multi_basin_graph_data(
            payload, parameters=doubled
        )['basin_views']
        self.assertEqual(len(doubled_views), len(views))
        for view, doubled_view in zip(views, doubled_views, strict=True):
            flux = {edge['id']: edge['flux'] for edge in view['edges']}
            self.assertTrue(flux)
            self.assertEqual(
                {edge['id']: edge['flux'] for edge in doubled_view['edges']},
                {edge_id: 2.0 * value for edge_id, value in flux.items()},
            )

    def test_frame_weight_and_seasonal_boost_weigh_a_full_frame(self) -> None:
        # Shen, Zi and Chen make the Water frame (r18); a Zi month makes Water the season.
        observed = _observed((1, 3, 5, 7), (9, 1, 5, 7))
        self.assertEqual(season_element_from_month_branch(1), primitives.ELEMENT_WATER)
        latent = _latent({18: 2})
        base = _energy(observed, latent, DEFAULT_MODEL_PARAMETERS).e_frame
        self.assertGreater(base, 0.0)
        doubled = replace(DEFAULT_MODEL_PARAMETERS, lambda_frame=8.0)
        self.assertEqual(_energy(observed, latent, doubled).e_frame, 2.0 * base)
        boosted = replace(DEFAULT_MODEL_PARAMETERS, omega_season=1.0)
        self.assertAlmostEqual(
            _energy(observed, latent, boosted).e_frame / base, 2.0 / 1.5, places=12
        )

    def test_corruption_weight_weighs_a_harm_against_a_full_harmony(self) -> None:
        # Zi-Wei (r29) harms the Zi-Chou harmony (r6), which is at its full state.
        observed = _observed((1, 2, 3, 4), (1, 2, 8, 4))
        latent = _latent({29: 1, 6: 3})
        changed = replace(DEFAULT_MODEL_PARAMETERS, lambda_cor=6.0)
        self.assertEqual(_energy(observed, latent, changed).e_cor, 6.0 * 0.5 * 0.5)

    def test_cross_weight_and_partial_state_weights_weigh_a_partial_harmony(
        self,
    ) -> None:
        observed = _observed((1, 2, 3, 4), (1, 2, 8, 4))
        latent = _latent({6: 2})
        base = _energy(observed, latent, DEFAULT_MODEL_PARAMETERS).e_cross
        self.assertGreater(base, 0.0)
        doubled = replace(DEFAULT_MODEL_PARAMETERS, lambda_cross=10.0)
        self.assertEqual(_energy(observed, latent, doubled).e_cross, 2.0 * base)
        quartered = replace(
            DEFAULT_MODEL_PARAMETERS, partial_state_weight_by_s=(0.0, 0.5, 0.25, 0.0)
        )
        self.assertEqual(_energy(observed, latent, quartered).e_cross, 0.25 * base)

    def test_clustering_weights_weigh_the_three_distances(self) -> None:
        # Jia and Ji combine into Earth (r1); at its full state Jia becomes Earth.
        observed = _observed((1, 6, 3, 7), (1, 2, 3, 4))
        dormant = _latent({})
        combined = _latent({1: 3}, mode='FollowStrength')
        combined = replace(combined, omegas=(0.8, *combined.omegas[1:]))

        def distance(alpha: float, beta: float, gamma: float) -> float:
            parameters = replace(
                DEFAULT_MODEL_PARAMETERS,
                cluster_alpha=alpha,
                cluster_beta=beta,
                cluster_gamma=gamma,
            )
            evaluations = evaluate_all_families(observed, parameters=parameters)
            season = season_element_from_month_branch(observed.branch_ids[1])
            particles = [
                build_particle(
                    observed, latent, evaluations, season, parameters=parameters
                )
                for latent in (dormant, combined)
            ]
            return _distance(
                particles[0],
                particles[1],
                _omega_bounds(evaluations, parameters=parameters),
                parameters=parameters,
            )

        # One switch and the mode differ; one entity's element; r1's omega moved 0.3
        # of its range from 0.5 to 2.0.
        switches_and_mode = 2 / 35
        elements = 1 / 16.0
        omegas = abs(0.8 - 0.5) / 1.5 / 34.0
        self.assertEqual(distance(1.0, 0.0, 0.0), switches_and_mode)
        self.assertEqual(distance(0.0, 1.0, 0.0), elements)
        self.assertAlmostEqual(distance(0.0, 0.0, 1.0), omegas, places=15)
        self.assertAlmostEqual(
            distance(0.6, 0.3, 0.1),
            0.6 * switches_and_mode + 0.3 * elements + 0.1 * omegas,
            places=15,
        )


class TestEvolutionModuleIParameterIsolation(unittest.TestCase):
    def test_concurrent_runs_with_different_parameters_share_nothing(self) -> None:
        birth = BIRTHS['2010-06-15 12:00 New York']
        sets = {
            'defaults': DEFAULT_MODEL_PARAMETERS,
            'changed': replace(
                _changed('wuxing_matrix'), lambda_mode=8.0, omega_min_r=0.9
            ),
        }
        expected = {name: _run(birth, parameters) for name, parameters in sets.items()}
        self.assertNotEqual(expected['defaults'], expected['changed'])

        results: dict[str, tuple[str, str]] = {}
        errors: list[BaseException] = []

        def run(key: str, parameters: ModelParameters) -> None:
            try:
                results[key] = _run(birth, parameters)
            except BaseException as error:  # surfaced below, in the test's thread
                errors.append(error)
                raise

        threads = [
            threading.Thread(target=run, args=(f'{name}-{index}', parameters))
            for index in range(2)
            for name, parameters in sets.items()
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        for key, result in results.items():
            self.assertEqual(result, expected[key.rsplit('-', 1)[0]], key)
        self.assertEqual(len(results), 4)


if __name__ == '__main__':
    unittest.main()
