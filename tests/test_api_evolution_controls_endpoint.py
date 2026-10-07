import json
import re
import threading
import unittest
from dataclasses import fields
from typing import Any
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from eight_characters.evolution import (
    DEFAULT_MODEL_PARAMETERS,
    InferenceConfig,
    ModelParameters,
    PostprocessConfig,
    run_natal_mvp,
)
from eight_characters.evolution.parameters import TABLE_SHAPES, parameter_id
from eight_characters.explorer.build_data_js_from_evolution import (
    build_multi_basin_graph_data,
)
from eight_characters.explorer_controls import (
    DEFAULT_EXPLORER_RUN,
    LIFE_STAGE_LABELS,
    describe_model,
)
from eight_characters.main import BASE_DIR, app

BIRTH: dict[str, Any] = {
    'date': '1988-02-04',
    'time': '16:30',
    'location': {
        'timezone': 'Asia/Shanghai',
        'latitude': 30.658,
        'longitude': 104.066,
    },
}
# The smallest run the explorer accepts, to keep these tests quick.
SMALL_RUN = {'particles': 8, 'temperature_steps': 1, 'sweeps_per_step': 1}


def _entries(value: Any) -> list[float]:
    if isinstance(value, list):
        return [entry for item in value for entry in _entries(item)]
    return [value]


class TestApiEvolutionControlsEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def catalogue(self) -> dict[str, list[dict[str, Any]]]:
        response = self.client.get('/api/evolution_controls')
        self.assertEqual(response.status_code, 200)
        return response.json()

    def explore(self, **extra: Any) -> Any:
        return self.client.post('/api/evolution_explorer', json={**BIRTH, **extra})

    def test_every_model_parameter_has_one_control(self) -> None:
        ids = [control['id'] for control in self.catalogue()['model']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(
            set(ids), {parameter_id(field.name) for field in fields(ModelParameters)}
        )

    def test_each_default_is_the_models_own_and_within_its_range(self) -> None:
        catalogue = self.catalogue()
        defaults = describe_model(DEFAULT_MODEL_PARAMETERS)
        for control in catalogue['model']:
            with self.subTest(control=control['id']):
                self.assertEqual(control['default'], defaults[control['id']])
                for entry in _entries(control['default']):
                    self.assertLessEqual(control['min'], entry)
                    self.assertLessEqual(entry, control['max'])
                shape = TABLE_SHAPES.get(control['id'].lower())
                if shape is None:
                    self.assertEqual(control['kind'], 'number')
                elif len(shape) == 1:
                    self.assertEqual(control['kind'], 'vector')
                    self.assertEqual(len(control['columns']), shape[0])
                else:
                    self.assertEqual(control['kind'], 'matrix')
                    self.assertEqual(
                        (len(control['rows']), len(control['columns'])), shape
                    )
        for control in catalogue['run']:
            with self.subTest(control=control['id']):
                self.assertEqual(
                    control['default'], getattr(DEFAULT_EXPLORER_RUN, control['id'])
                )
                self.assertLessEqual(control['min'], control['default'])
                self.assertLessEqual(control['default'], control['max'])
        for control in catalogue['conventions']:
            with self.subTest(control=control['id']):
                self.assertIn(
                    control['default'],
                    [option['value'] for option in control['options']],
                )

    def test_the_explorer_runs_as_before_by_default(self) -> None:
        self.assertEqual(
            DEFAULT_EXPLORER_RUN.inference_config(),
            InferenceConfig(
                particles=24, temperature_steps=2, sweeps_per_step=1, seed=42
            ),
        )
        self.assertEqual(
            DEFAULT_EXPLORER_RUN.postprocess_config(),
            PostprocessConfig(
                discrete_relax_max_passes=1,
                continuous_passes=1,
                dbscan_eps=0.08,
                dbscan_min_samples=1,
            ),
        )

    def test_the_stage_labels_are_the_explorers_own(self) -> None:
        script = (BASE_DIR / 'explorer' / 'app.js').read_text(encoding='utf-8')
        block = re.search(r'const LIFE_STAGE_INFO = \{(.*?)\};', script, re.S)
        assert block is not None
        self.assertEqual(
            tuple(re.findall(r"\d+: '([^']+)'", block.group(1))), LIFE_STAGE_LABELS
        )

    def test_run_settings_and_model_parameters_reach_the_run_and_the_graph(
        self,
    ) -> None:
        wuxing = [
            [2.0 * entry for entry in row]
            for row in DEFAULT_MODEL_PARAMETERS.wuxing_matrix
        ]
        with (
            patch('eight_characters.main.run_natal_mvp', wraps=run_natal_mvp) as run,
            patch(
                'eight_characters.main.build_multi_basin_graph_data',
                wraps=build_multi_basin_graph_data,
            ) as graph,
        ):
            response = self.explore(
                run={
                    **SMALL_RUN,
                    'seed': 7,
                    'dbscan_eps': 0.2,
                    'dbscan_min_samples': 2,
                },
                model={'LAMBDA_MODE': 6.5, 'WUXING_MATRIX': wuxing},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            run.call_args.kwargs['inference_config'],
            InferenceConfig(
                particles=8, temperature_steps=1, sweeps_per_step=1, seed=7
            ),
        )
        self.assertEqual(
            run.call_args.kwargs['postprocess_config'],
            PostprocessConfig(
                discrete_relax_max_passes=1,
                continuous_passes=1,
                dbscan_eps=0.2,
                dbscan_min_samples=2,
            ),
        )
        parameters = run.call_args.kwargs['parameters']
        self.assertEqual(parameters.lambda_mode, 6.5)
        self.assertEqual(parameters.wuxing_matrix, tuple(tuple(row) for row in wuxing))
        self.assertIs(graph.call_args.kwargs['parameters'], parameters)
        echoed = response.json()['graph_data']['parameters']
        self.assertEqual(
            echoed['run'],
            {
                'particles': 8,
                'temperature_steps': 1,
                'sweeps_per_step': 1,
                'seed': 7,
                'dbscan_eps': 0.2,
                'dbscan_min_samples': 2,
            },
        )
        self.assertEqual(echoed['model']['LAMBDA_MODE'], 6.5)
        self.assertEqual(echoed['model']['WUXING_MATRIX'], wuxing)
        self.assertEqual(
            echoed['model']['LAMBDA_INTER'], DEFAULT_MODEL_PARAMETERS.lambda_inter
        )

    def test_the_documented_request_with_overrides_is_accepted(self) -> None:
        docs = (BASE_DIR.parent / 'docs' / 'api.md').read_text(encoding='utf-8')
        example = re.search(
            r'Request with overrides:\n\n```json\n(.*?)\n```', docs, re.S
        )
        assert example is not None
        with patch(
            'eight_characters.main._build_evolution_explorer_graph_data',
            return_value={},
        ) as build:
            response = self.client.post(
                '/api/evolution_explorer', json=json.loads(example.group(1))
            )
        self.assertEqual(response.status_code, 200, response.text)
        run, parameters = build.call_args.args[3:5]
        self.assertEqual((run.particles, run.seed), (48, 7))
        self.assertEqual(parameters.lambda_mode, 6.5)
        self.assertEqual(parameters.proximity_weight_by_gap, (1.0, 0.6, 0.3))

    def test_an_override_out_of_range_or_unknown_is_refused_before_any_work(
        self,
    ) -> None:
        refusals: list[tuple[dict[str, Any], str]] = [
            (
                {'model': {'LAMBDA_MOOD': 6.5}},
                'model.LAMBDA_MOOD is not a model parameter',
            ),
            (
                {'model': {'LAMBDA_MODE': 25}},
                'model.LAMBDA_MODE must be from 0.1 to 20.0, not 25',
            ),
            (
                {'model': {'LAMBDA_MODE': True}},
                'model.LAMBDA_MODE must be a number, not True',
            ),
            (
                {'model': {'LAMBDA_MODE': '6.5'}},
                "model.LAMBDA_MODE must be a number, not '6.5'",
            ),
            (
                {'model': {'OMEGA_MIN_R': 1.5}},
                'model.OMEGA_MIN_R must be from 0.1 to 1.0',
            ),
            (
                {'model': {'WUXING_MATRIX': [[0.5] * 5] * 4}},
                'model.WUXING_MATRIX must be 5 rows of 5 numbers',
            ),
            (
                {'model': {'WUXING_MATRIX': [[0.5] * 5] * 4 + [[0.5] * 4]}},
                'model.WUXING_MATRIX row 4 must be 5 numbers',
            ),
            (
                {'model': {'STAGE_AMPLITUDE_BY_STAGE': [0.5] * 11}},
                'model.STAGE_AMPLITUDE_BY_STAGE must be 12 numbers',
            ),
            (
                {'model': {'STAGE_AMPLITUDE_BY_STAGE': [0.5] * 11 + [1.6]}},
                'model.STAGE_AMPLITUDE_BY_STAGE must be from 0.0 to 1.5, not 1.6',
            ),
            ({'model': {'CLUSTER_ALPHA': 0.5}}, 'must add up to 1'),
            (
                {'run': {'particles': 100}},
                'run.particles must be from 8 to 64, not 100',
            ),
            ({'run': {'particles': 24.5}}, 'run.particles'),
            ({'run': {'particles': True}}, 'run.particles'),
            (
                {'run': {'temperature_steps': 5}},
                'run.temperature_steps must be from 1 to 4',
            ),
            (
                {'run': {'sweeps_per_step': 3}},
                'run.sweeps_per_step must be from 1 to 2',
            ),
            ({'run': {'seed': -1}}, 'run.seed must be from 0 to 2147483647'),
            (
                {'run': {'particles': 24, 'dbscan_min_samples': 30}},
                'run.dbscan_min_samples (30) must not exceed run.particles (24)',
            ),
            ({'run': {'colour': 1}}, 'run.colour'),
            ({'controls': {'LAMBDA_MODE': 6.5}}, 'controls'),
        ]
        for extra, detail in refusals:
            with (
                self.subTest(request=extra),
                patch(
                    'eight_characters.main._resolve_four_pillars_location',
                    new=AsyncMock(),
                ) as resolve,
            ):
                response = self.explore(**extra)
                self.assertEqual(response.status_code, 400)
                self.assertIn(detail, response.json()['detail'])
                resolve.assert_not_awaited()

    def test_a_run_that_forms_no_basin_says_so_instead_of_inventing_one(self) -> None:
        with (
            patch('eight_characters.main.run_natal_mvp', return_value=object()),
            patch('eight_characters.main.asdict', return_value={'basins': []}),
            patch('eight_characters.main.build_multi_basin_graph_data') as graph,
        ):
            response = self.explore(
                run={**SMALL_RUN, 'dbscan_eps': 0.01, 'dbscan_min_samples': 8}
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()['detail'],
            'No basin formed: no particle had run.dbscan_min_samples (8) particles '
            'within run.dbscan_eps (0.01). Widen the radius or lower the minimum.',
        )
        graph.assert_not_called()

    def test_concurrent_requests_each_get_their_own_parameters(self) -> None:
        requests = {
            'defaults': {'run': SMALL_RUN},
            'changed': {
                'run': SMALL_RUN,
                'model': {'LAMBDA_MODE': 6.5, 'SAME_POLARITY_MULTIPLIER': 1.5},
            },
        }
        alone = {name: self.explore(**extra).json() for name, extra in requests.items()}
        self.assertNotEqual(
            alone['defaults']['graph_data'], alone['changed']['graph_data']
        )

        answers: dict[str, Any] = {}

        def ask(key: str, extra: dict[str, Any]) -> None:
            answers[key] = self.explore(**extra).json()

        threads = [
            threading.Thread(target=ask, args=(f'{name}-{index}', extra))
            for index in range(2)
            for name, extra in requests.items()
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(answers), 4)
        for key, answer in answers.items():
            self.assertEqual(answer, alone[key.rsplit('-', 1)[0]], key)


if __name__ == '__main__':
    unittest.main()
