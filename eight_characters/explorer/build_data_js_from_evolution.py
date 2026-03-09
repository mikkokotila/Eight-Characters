from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from eight_characters.evolution.families import evaluate_all_families, family_spec
from eight_characters.evolution.mechanics import (
    compute_dynamic_vitality_amplitudes,
    realized_flux,
)
from eight_characters.evolution.primitives import (
    ELEMENT_LABELS,
    TEN_GOD_GROUP_LABELS,
    TEN_GOD_LABELS,
    authority_element,
    moisture_contribution,
    output_element,
    polarity_multiplier,
    resource_element,
    temperature_contribution,
    ten_god_group,
    wuxing_interaction,
    wealth_element,
)
from eight_characters.evolution.state import (
    RULE_COUNT,
    RULE_STATE_DOMAINS,
    LatentState,
    ObservedState,
)

PILLAR_NAMES = {1: 'Year', 2: 'Month', 3: 'Day', 4: 'Hour'}
HIERARCHY_NAMES = {4: 'Stem', 3: 'Principal', 2: 'Secondary', 1: 'Residual'}
POLARITY_NAMES = {1: 'Yang', 0: 'Yin'}

ELEMENT_NAMES = tuple(ELEMENT_LABELS)
TEN_GOD_NAMES = tuple(TEN_GOD_LABELS)
TEN_GOD_GROUP_NAMES = tuple(TEN_GOD_GROUP_LABELS)


def _one_hot_index(vector: list[int] | tuple[int, ...]) -> int:
    if not vector:
        return 0
    max_index, _ = max(enumerate(vector), key=lambda pair: pair[1])
    return int(max_index)


def _as_dict(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f'{field} must be an object.')
    return cast(dict[str, Any], value)


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return cast(list[Any], value)
    return []


def _as_int(value: Any, *, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _as_float(value: Any, *, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        return value
    return default


def _as_str(value: Any, *, default: str = '') -> str:
    if isinstance(value, str):
        return value
    return default


def _as_int_list(value: Any) -> list[int]:
    values = _as_list(value)
    return [_as_int(item) for item in values]


def _as_float_list(value: Any) -> list[float]:
    values = _as_list(value)
    return [_as_float(item) for item in values]


def _as_int_matrix(value: Any) -> list[list[int]]:
    rows = _as_list(value)
    return [_as_int_list(row) for row in rows]


def _build_observed_state(input_shape: dict[str, Any]) -> ObservedState:
    branch_ids_raw = _as_int_list(input_shape.get('branch_ids'))
    if len(branch_ids_raw) < 4:
        raise ValueError('input_shape.branch_ids must contain 4 values')
    branch_ids = cast(
        tuple[int, int, int, int],
        (
            branch_ids_raw[0],
            branch_ids_raw[1],
            branch_ids_raw[2],
            branch_ids_raw[3],
        ),
    )

    base_elements_raw = _as_int_matrix(input_shape.get('base_elements'))
    base_elements = tuple(
        cast(
            tuple[int, int, int, int, int],
            (
                row[0] if len(row) > 0 else 0,
                row[1] if len(row) > 1 else 0,
                row[2] if len(row) > 2 else 0,
                row[3] if len(row) > 3 else 0,
                row[4] if len(row) > 4 else 0,
            ),
        )
        for row in base_elements_raw
    )

    observed = ObservedState(
        branch_ids=branch_ids,
        base_elements=base_elements,
        polarities=tuple(_as_int_list(input_shape.get('polarities'))),
        hierarchy_levels=tuple(_as_int_list(input_shape.get('hierarchy_levels'))),
        positions=tuple(_as_int_list(input_shape.get('positions'))),
        masks=tuple(_as_int_list(input_shape.get('masks'))),
        vitality_stages=tuple(_as_int_list(input_shape.get('vitality_stages'))),
        day_master_index=_as_int(input_shape.get('day_master_index'), default=0),
    )
    observed.validate()
    return observed


def _build_latent_state(basin: dict[str, Any]) -> LatentState:
    raw_switches = _as_int_list(basin.get('map_switches'))
    raw_omegas = _as_float_list(basin.get('map_omegas'))

    switches: list[int] = []
    omegas: list[float] = []
    for idx in range(RULE_COUNT):
        domain = RULE_STATE_DOMAINS[idx]
        switch_value = raw_switches[idx] if idx < len(raw_switches) else 0
        if switch_value not in domain:
            switch_value = 0
        omega_value = raw_omegas[idx] if idx < len(raw_omegas) else 0.5
        if omega_value < 0.0:
            omega_value = 0.0
        switches.append(switch_value)
        omegas.append(omega_value)

    mode = _as_str(basin.get('mode'), default='Standard')
    latent = LatentState(
        switches=tuple(switches),
        omegas=tuple(omegas),
        mode=mode,
    )
    latent.validate()
    return latent


def _build_effective_elements(
    observed_state: ObservedState, basin: dict[str, Any]
) -> tuple[tuple[int, int, int, int, int], ...]:
    matrix = _as_int_matrix(basin.get('map_effective_elements'))
    if len(matrix) != len(observed_state.base_elements):
        return observed_state.base_elements
    return tuple(
        cast(
            tuple[int, int, int, int, int],
            (
                row[0] if len(row) > 0 else 0,
                row[1] if len(row) > 1 else 0,
                row[2] if len(row) > 2 else 0,
                row[3] if len(row) > 3 else 0,
                row[4] if len(row) > 4 else 0,
            ),
        )
        for row in matrix
    )


def _build_effective_ten_gods(
    observed_state: ObservedState, basin: dict[str, Any]
) -> tuple[tuple[int, ...], ...]:
    matrix = _as_int_matrix(basin.get('map_effective_ten_gods'))
    if len(matrix) != len(observed_state.base_elements):
        return tuple(
            cast(tuple[int, ...], (1, 0, 0, 0, 0, 0, 0, 0, 0, 0))
            for _ in observed_state.base_elements
        )
    return tuple(
        cast(
            tuple[int, ...],
            tuple((row[idx] if idx < len(row) else 0) for idx in range(10)),
        )
        for row in matrix
    )


def _damage_participation_maps(
    latent_state: LatentState, evaluations: tuple[Any, ...]
) -> tuple[dict[tuple[int, int], float], dict[tuple[int, int], float]]:
    clash_map: dict[tuple[int, int], float] = {}
    punishment_map: dict[tuple[int, int], float] = {}
    for evaluation in evaluations:
        rule_index = int(evaluation.rule_index)
        switch_value = latent_state.switches[rule_index - 1]

        if 12 <= rule_index <= 17 and switch_value == 1:
            for entity_index in evaluation.q_entity_indices:
                clash_map[(rule_index, int(entity_index))] = 1.0

        if 22 <= rule_index <= 28 and switch_value > 0:
            for entity_index in evaluation.q_entity_indices:
                punishment_map[(rule_index, int(entity_index))] = 1.0

    return clash_map, punishment_map


def _relation_class(source_element: int, target_element: int) -> str:
    if target_element == output_element(source_element) or target_element == source_element:
        return 'production'
    if target_element == wealth_element(source_element):
        return 'control'
    if target_element == authority_element(source_element):
        return 'control'
    if target_element == resource_element(source_element):
        return 'drain'
    return 'control'


def _motif_path_to_node_ids(path_value: Any, active_node_ids: set[str]) -> list[str]:
    result: list[str] = []
    for entity_index in _as_int_list(path_value):
        node_id = f'E{entity_index}'
        if node_id in active_node_ids:
            result.append(node_id)
    return result


def _pulse_nodes(pulses_value: Any, active_node_ids: set[str]) -> list[str]:
    pulse_set: set[str] = set()
    for pulse in _as_list(pulses_value):
        if isinstance(pulse, list):
            for entity_index in _as_int_list(pulse):
                node_id = f'E{entity_index}'
                if node_id in active_node_ids:
                    pulse_set.add(node_id)
            continue
        entity_index = _as_int(pulse, default=-1)
        node_id = f'E{entity_index}'
        if node_id in active_node_ids:
            pulse_set.add(node_id)
    return sorted(pulse_set, key=lambda node_id: int(node_id[1:]))


def _modifier_kind(rule_index: int) -> str:
    if 12 <= rule_index <= 17:
        return 'clash'
    if 22 <= rule_index <= 28:
        return 'punishment'
    if 29 <= rule_index <= 34:
        return 'harm'
    if (1 <= rule_index <= 11) or (18 <= rule_index <= 21):
        return 'harmony'
    return 'harmony'


def build_graph_data(
    payload: dict[str, Any], basin_index: int = 0, flux_threshold: float = 0.0
) -> dict[str, Any]:
    input_shape = _as_dict(payload.get('input_shape'), field='payload.input_shape')
    basins = _as_list(payload.get('basins'))
    if not basins:
        raise ValueError('payload.basins must contain at least one basin.')
    if basin_index < 0 or basin_index >= len(basins):
        raise ValueError(f'basin_index {basin_index} out of range.')

    basin = _as_dict(basins[basin_index], field='payload.basins[basin_index]')
    observed_state = _build_observed_state(input_shape)
    latent_state = _build_latent_state(basin)

    evaluations = evaluate_all_families(observed_state)
    clash_map, punishment_map = _damage_participation_maps(latent_state, evaluations)
    dynamic_amplitudes = compute_dynamic_vitality_amplitudes(
        observed_state=observed_state,
        latent_state=latent_state,
        clash_participation=clash_map,
        punishment_participation=punishment_map,
    )

    effective_elements = _build_effective_elements(observed_state, basin)
    effective_ten_gods = _build_effective_ten_gods(observed_state, basin)
    flux_matrix = realized_flux(
        observed_state=observed_state,
        effective_elements=effective_elements,
        dynamic_amplitudes=dynamic_amplitudes,
    )

    active_indices = [
        idx for idx, mask in enumerate(observed_state.masks) if int(mask) == 1
    ]
    active_node_ids = {f'E{idx}' for idx in active_indices}

    nodes: list[dict[str, Any]] = []
    for entity_index in active_indices:
        element_index = _one_hot_index(list(effective_elements[entity_index]))
        ten_god_index_value = _one_hot_index(list(effective_ten_gods[entity_index]))
        ten_god_group_index = ten_god_group(ten_god_index_value)
        position = int(observed_state.positions[entity_index])
        hierarchy = int(observed_state.hierarchy_levels[entity_index])
        polarity = int(observed_state.polarities[entity_index])
        dynamic_vitality = float(dynamic_amplitudes[entity_index])
        climate_temperature = float(temperature_contribution(element_index, polarity))
        climate_moisture = float(moisture_contribution(element_index, polarity))
        climate_weight = float(observed_state.masks[entity_index] * hierarchy)

        nodes.append(
            {
                'id': f'E{entity_index}',
                'entity_index': entity_index,
                'label': (
                    f'{PILLAR_NAMES.get(position, "P?")} '
                    f'{HIERARCHY_NAMES.get(hierarchy, "H?")}'
                ),
                'pillar': PILLAR_NAMES.get(position, 'Unknown'),
                'pillar_index': position,
                'hierarchy': HIERARCHY_NAMES.get(hierarchy, 'Unknown'),
                'hierarchy_index': hierarchy,
                'polarity': POLARITY_NAMES.get(polarity, 'Unknown'),
                'effective_element': ELEMENT_NAMES[element_index],
                'effective_element_index': element_index,
                'ten_god': TEN_GOD_NAMES[ten_god_index_value],
                'ten_god_index': ten_god_index_value,
                'ten_god_group': TEN_GOD_GROUP_NAMES[ten_god_group_index],
                'ten_god_group_index': ten_god_group_index,
                'dynamic_vitality': dynamic_vitality,
                'vitality_stage': int(observed_state.vitality_stages[entity_index]),
                'climate_temperature_component': climate_temperature,
                'climate_moisture_component': climate_moisture,
                'climate_temperature_weighted': climate_temperature * climate_weight,
                'climate_moisture_weighted': climate_moisture * climate_weight,
                'is_day_master': entity_index == observed_state.day_master_index,
                'is_ghost': False,
            }
        )

    edges: list[dict[str, Any]] = []
    for source_index in active_indices:
        source_element = _one_hot_index(list(effective_elements[source_index]))
        source_polarity = int(observed_state.polarities[source_index])
        source_hierarchy = int(observed_state.hierarchy_levels[source_index])
        source_position = int(observed_state.positions[source_index])
        source_vitality = float(dynamic_amplitudes[source_index])
        for target_index in active_indices:
            if source_index == target_index:
                continue
            target_element = _one_hot_index(list(effective_elements[target_index]))
            target_polarity = int(observed_state.polarities[target_index])
            target_hierarchy = int(observed_state.hierarchy_levels[target_index])
            target_position = int(observed_state.positions[target_index])
            target_vitality = float(dynamic_amplitudes[target_index])

            relationship = _relation_class(source_element, target_element)
            polarity_mod = float(polarity_multiplier(source_polarity, target_polarity))
            proximity_weight = float(1.0 / (1.0 + abs(source_position - target_position)))
            vitality_differential = float(source_vitality - target_vitality)
            vitality_product = float(source_vitality * target_vitality)
            hierarchy_coupling = float(source_hierarchy * target_hierarchy)
            elemental_interaction = float(
                wuxing_interaction(source_element, target_element)
            )
            transport_capacity_component = float(
                vitality_product * hierarchy_coupling * proximity_weight
            )
            flux_value = float(flux_matrix[source_index][target_index])
            abs_flux = abs(flux_value)
            if abs_flux < flux_threshold:
                continue
            edges.append(
                {
                    'id': f'F_{source_index}_{target_index}',
                    'source': f'E{source_index}',
                    'target': f'E{target_index}',
                    'flux': flux_value,
                    'abs_flux': abs_flux,
                    'relation': relationship,
                    'elemental_relationship': relationship,
                    'source_element_index': source_element,
                    'target_element_index': target_element,
                    'polarity_modifier': polarity_mod,
                    'vitality_differential': vitality_differential,
                    'proximity_weight': proximity_weight,
                    'elemental_interaction': elemental_interaction,
                    'transport_capacity_component': transport_capacity_component,
                    'hierarchy_coupling': hierarchy_coupling,
                    'vitality_product': vitality_product,
                    'source_position_index': source_position,
                    'target_position_index': target_position,
                    'source_hierarchy_index': source_hierarchy,
                    'target_hierarchy_index': target_hierarchy,
                    'is_ghost': False,
                }
            )

    motifs_raw = _as_dict(basin.get('motifs', {}), field='basin.motifs')
    chains = [
        path
        for path in (
            _motif_path_to_node_ids(path_raw, active_node_ids)
            for path_raw in _as_list(motifs_raw.get('chains'))
        )
        if len(path) >= 2
    ]
    loops = [
        path
        for path in (
            _motif_path_to_node_ids(path_raw, active_node_ids)
            for path_raw in _as_list(motifs_raw.get('loops'))
        )
        if len(path) >= 2
    ]
    cascades = [
        path
        for path in (
            _motif_path_to_node_ids(path_raw, active_node_ids)
            for path_raw in _as_list(motifs_raw.get('cascades'))
        )
        if len(path) >= 2
    ]
    bottlenecks = [
        node_id
        for node_id in (f'E{idx}' for idx in _as_int_list(motifs_raw.get('bottlenecks')))
        if node_id in active_node_ids
    ]
    pulses = _pulse_nodes(motifs_raw.get('pulses'), active_node_ids)
    absences = [
        idx
        for idx in _as_int_list(motifs_raw.get('absences'))
        if 0 <= idx < len(ELEMENT_NAMES)
    ]

    topology_modifiers: list[dict[str, Any]] = []
    for evaluation in evaluations:
        rule_index = int(evaluation.rule_index)
        switch_state = int(latent_state.switches[rule_index - 1])
        if switch_state <= 0:
            continue
        if not evaluation.selected_positions:
            continue
        pillar_indices = sorted({int(value) for value in evaluation.selected_positions})
        if len(pillar_indices) < 2:
            continue
        spec = family_spec(rule_index)
        topology_modifiers.append(
            {
                'id': f'r{rule_index}',
                'rule_index': rule_index,
                'label': spec.name,
                'kind': _modifier_kind(rule_index),
                'pillar_indices': pillar_indices,
                'pillars': [
                    PILLAR_NAMES.get(pillar_index, 'Unknown')
                    for pillar_index in pillar_indices
                ],
                'switch_state': switch_state,
                'omega': float(latent_state.omegas[rule_index - 1]),
            }
        )

    ghost_nodes: list[dict[str, Any]] = []
    ghost_edges: list[dict[str, Any]] = []
    for slot, missing_element_index in enumerate(absences):
        ghost_id = f'GHOST_{missing_element_index}'
        inbound_source_element = resource_element(missing_element_index)
        outbound_target_element = output_element(missing_element_index)

        inbound_sources = [
            f'E{idx}'
            for idx in active_indices
            if _one_hot_index(list(effective_elements[idx])) == inbound_source_element
        ]
        outbound_targets = [
            f'E{idx}'
            for idx in active_indices
            if _one_hot_index(list(effective_elements[idx])) == outbound_target_element
        ]

        ghost_nodes.append(
            {
                'id': ghost_id,
                'entity_index': -1,
                'label': f'Missing {ELEMENT_NAMES[missing_element_index]}',
                'pillar': 'Absent',
                'pillar_index': 0,
                'hierarchy': 'Ghost',
                'hierarchy_index': 0,
                'polarity': 'N/A',
                'effective_element': ELEMENT_NAMES[missing_element_index],
                'effective_element_index': missing_element_index,
                'ten_god': 'N/A',
                'ten_god_index': -1,
                'ten_god_group': 'None',
                'ten_god_group_index': -1,
                'dynamic_vitality': 0.0,
                'vitality_stage': 0,
                'is_day_master': False,
                'is_ghost': True,
                'ghost_slot': slot,
                'connects_from': inbound_sources,
                'connects_to': outbound_targets,
            }
        )

        for source_id in inbound_sources:
            ghost_edges.append(
                {
                    'id': f'GH_IN_{source_id}_{ghost_id}',
                    'source': source_id,
                    'target': ghost_id,
                    'flux': 0.0,
                    'abs_flux': 0.0,
                    'relation': 'production',
                    'source_element_index': inbound_source_element,
                    'target_element_index': missing_element_index,
                    'is_ghost': True,
                }
            )
        for target_id in outbound_targets:
            ghost_edges.append(
                {
                    'id': f'GH_OUT_{ghost_id}_{target_id}',
                    'source': ghost_id,
                    'target': target_id,
                    'flux': 0.0,
                    'abs_flux': 0.0,
                    'relation': 'production',
                    'source_element_index': missing_element_index,
                    'target_element_index': outbound_target_element,
                    'is_ghost': True,
                }
            )

    all_nodes = nodes + ghost_nodes
    max_abs_flux = max((edge['abs_flux'] for edge in edges), default=0.0)
    basin_mass_distribution = [
        {
            'basin_id': _as_int(_as_dict(item, field='basin').get('basin_id'), default=index),
            'mass': _as_float(_as_dict(item, field='basin').get('mass'), default=0.0),
            'mode': _as_str(_as_dict(item, field='basin').get('mode'), default='Unknown'),
        }
        for index, item in enumerate(basins)
    ]

    return {
        'meta': {
            'basin_id': _as_int(basin.get('basin_id'), default=basin_index),
            'basin_mass': _as_float(basin.get('mass'), default=0.0),
            'mode': latent_state.mode,
            'chart_temperature': _as_float(basin.get('chart_temperature')),
            'chart_saturation': _as_float(basin.get('chart_saturation')),
            'day_master_index': observed_state.day_master_index,
            'branch_ids': [int(value) for value in observed_state.branch_ids],
            'max_abs_flux': max_abs_flux,
            'basin_mass_distribution': basin_mass_distribution,
        },
        'layout': {
            'pillars': ['Year', 'Month', 'Day', 'Hour'],
            'hierarchy': ['Stem', 'Principal', 'Secondary', 'Residual'],
        },
        'nodes': sorted(
            all_nodes,
            key=lambda node: (
                1 if bool(node.get('is_ghost')) else 0,
                _as_int(node.get('pillar_index')),
                -_as_int(node.get('hierarchy_index')),
                _as_int(node.get('entity_index')),
            ),
        ),
        'edges': sorted(edges, key=lambda edge: edge['abs_flux'], reverse=True),
        'ghost_edges': ghost_edges,
        'topology_modifiers': topology_modifiers,
        'motifs': {
            'chains': chains,
            'loops': loops,
            'cascades': cascades,
            'bottlenecks': bottlenecks,
            'pulses': pulses,
            'absences': absences,
        },
    }


def build_multi_basin_graph_data(
    payload: dict[str, Any], basin_index: int = 0, flux_threshold: float = 0.0
) -> dict[str, Any]:
    basins = _as_list(payload.get('basins'))
    if not basins:
        raise ValueError('payload.basins must contain at least one basin.')

    clamped_index = max(0, min(int(basin_index), len(basins) - 1))
    basin_views = [
        build_graph_data(payload, basin_index=index, flux_threshold=flux_threshold)
        for index in range(len(basins))
    ]
    active_view = basin_views[clamped_index]
    active_meta = _as_dict(active_view.get('meta'), field='active_view.meta')
    active_meta.update(
        {
            'active_basin_index': clamped_index,
            'basin_count': len(basin_views),
        }
    )

    combined = dict(active_view)
    combined.update(
        {
            'meta': active_meta,
            'active_basin_index': clamped_index,
            'basin_views': basin_views,
        }
    )
    return combined


def write_data_js(graph_data: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    js_payload = json.dumps(graph_data, indent=2, ensure_ascii=False)
    output_path.write_text(f'const GRAPH_DATA = {js_payload};\n', encoding='utf-8')


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description='Build explorer data.js from an evolution payload JSON file.'
    )
    parser.add_argument(
        '--payload',
        type=Path,
        default=script_dir / 'chart3_evolution_payload.json',
        help='Path to evolution payload JSON.',
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=script_dir / 'data.js',
        help='Output path for generated data.js.',
    )
    parser.add_argument(
        '--basin-index',
        type=int,
        default=0,
        help='Basin index to visualize from payload.basins.',
    )
    parser.add_argument(
        '--flux-threshold',
        type=float,
        default=0.0,
        help='Minimum |flux| for emitting direct F(i->j) edges.',
    )
    parser.add_argument(
        '--single-basin',
        action='store_true',
        help='Emit only the selected basin in data.js.',
    )
    args = parser.parse_args()

    payload_data = json.loads(args.payload.read_text(encoding='utf-8'))
    flux_threshold = max(0.0, float(args.flux_threshold))
    if args.single_basin:
        graph_data = build_graph_data(
            payload_data,
            basin_index=args.basin_index,
            flux_threshold=flux_threshold,
        )
    else:
        graph_data = build_multi_basin_graph_data(
            payload_data,
            basin_index=args.basin_index,
            flux_threshold=flux_threshold,
        )
    write_data_js(graph_data, args.output)

    print(
        f'Wrote {args.output} with '
        f'{len(graph_data["nodes"])} nodes, '
        f'{len(graph_data["edges"])} flux edges, '
        f'{len(graph_data["ghost_edges"])} ghost edges, '
        f'{len(_as_list(graph_data.get("basin_views")))} basin view(s).'
    )


if __name__ == '__main__':
    main()
