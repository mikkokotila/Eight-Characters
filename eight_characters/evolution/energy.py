from dataclasses import dataclass
from math import inf, isinf
from typing import Iterable, Sequence

from eight_characters.evolution.families import (
    FAMILY_CATALOG,
    FamilyEvaluation,
    enforce_applicability_lock,
    evaluate_all_families,
    family_spec,
)
from eight_characters.evolution.mechanics import (
    pillar_climate_summaries,
    pillar_retention,
    realized_flux,
    transport_capacity,
)
from eight_characters.evolution.primitives import (
    DELTA_V_R,
    EPSILON,
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
    OMEGA_SEASON,
    TAU_FOLLOW,
    TAU_R,
    TAU_STD,
    authority_element,
    domain_resonance,
    life_stage_anchor,
    one_hot_to_element,
    output_element,
    partial_state_weight,
    resource_element,
    season_element_from_month_branch,
    season_score,
    stage_amplitude,
    ten_god_distance,
    ten_god_group,
    ten_god_one_hot,
    wealth_element,
)
from eight_characters.evolution.state import (
    FullTransformationCapture,
    LatentState,
    ObservedState,
    active_mode_center,
)


@dataclass(frozen=True)
class EnergyBreakdown:
    e_excl: float
    e_act: float
    e_intra: float
    e_inter: float
    e_clim: float
    e_dom: float
    e_mode: float
    e_clash: float
    e_frame: float
    e_pun: float
    e_cor: float
    e_cross: float
    total: float
    e_chem_by_pillar: tuple[float, float, float, float]
    pillar_retention: tuple[float, float, float, float]
    pillar_temperatures: tuple[float, float, float, float]
    pillar_saturations: tuple[float, float, float, float]
    chart_temperature: float
    chart_saturation: float
    mode_score_str: float
    mode_score_weak: float


def exclusivity_energy(
    full_captures: Iterable[FullTransformationCapture] | None,
    entity_count: int,
) -> float:
    if full_captures is None:
        return 0.0
    targets_by_entity: dict[int, set[int]] = {}
    for capture in full_captures:
        capture.validate(entity_count=entity_count)
        targets = targets_by_entity.setdefault(capture.entity_index, set())
        targets.add(capture.target_element_index)
        if len(targets) > 1:
            return inf
    return 0.0


def _stem_entity_index_by_position(observed_state: ObservedState) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for entity_index, (mask, hierarchy, position) in enumerate(
        zip(
            observed_state.masks,
            observed_state.hierarchy_levels,
            observed_state.positions,
        )
    ):
        if mask != 1 or hierarchy != 4:
            continue
        if position in mapping:
            raise ValueError(f'multiple active stem entities found in position {position}')
        mapping[position] = entity_index
    return mapping


def _evaluate_chem_by_pillar(
    observed_state: ObservedState,
    flux_matrix: Sequence[Sequence[float]],
) -> tuple[float, float, float, float]:
    values: list[float] = []
    for pillar_position in (1, 2, 3, 4):
        subtotal = 0.0
        for source_index in range(len(flux_matrix)):
            if observed_state.positions[source_index] != pillar_position:
                continue
            for target_index in range(len(flux_matrix)):
                if source_index == target_index:
                    continue
                if observed_state.positions[target_index] != pillar_position:
                    continue
                subtotal += flux_matrix[source_index][target_index]
        values.append(-subtotal)
    return (values[0], values[1], values[2], values[3])


def _mode_diagnostics(
    observed_state: ObservedState,
    effective_elements: Sequence[Sequence[int]],
    season_element_index: int,
) -> tuple[float, float, float, float, float, float, float, int]:
    day_master_element = one_hot_to_element(
        tuple(effective_elements[observed_state.day_master_index])
    )

    z_denom = 0.0
    element_mass = [0.0] * 5
    for entity_index in range(len(observed_state.base_elements)):
        if observed_state.masks[entity_index] == 0:
            continue
        weight = (
            observed_state.masks[entity_index]
            * observed_state.hierarchy_levels[entity_index]
            * stage_amplitude(observed_state.vitality_stages[entity_index])
        )
        z_denom += weight
        element_index = one_hot_to_element(tuple(effective_elements[entity_index]))
        element_mass[element_index] += weight

    def u(element_index: int) -> float:
        return element_mass[element_index] / (z_denom + EPSILON)

    u_self = u(day_master_element)
    u_res = u(resource_element(day_master_element))
    u_out = u(output_element(day_master_element))
    u_w = u(wealth_element(day_master_element))
    u_auth = u(authority_element(day_master_element))

    root_dm = 0
    for entity_index in range(len(observed_state.base_elements)):
        if observed_state.masks[entity_index] == 0:
            continue
        if observed_state.hierarchy_levels[entity_index] >= 4:
            continue
        if one_hot_to_element(tuple(effective_elements[entity_index])) == day_master_element:
            root_dm = 1
            break

    season_dm = season_score(day_master_element, season_element_index)
    score_str = (
        u_self
        + u_res
        + 0.2 * root_dm
        + 0.1 * max(season_dm, 0)
        - u_out
        - u_w
        - u_auth
    )
    score_weak = (
        u_out
        + u_w
        + u_auth
        + 0.1 * max(-season_dm, 0)
        - u_self
        - u_res
        - 0.2 * root_dm
    )
    return (
        score_str,
        score_weak,
        u_self,
        u_res,
        u_out,
        u_w,
        u_auth,
        day_master_element,
    )


def _mode_energy(
    latent_state: LatentState,
    score_str: float,
    score_weak: float,
    u_self: float,
    u_res: float,
    u_out: float,
    u_w: float,
    u_auth: float,
) -> float:
    mode = latent_state.mode
    if mode == 'Standard':
        return LAMBDA_MODE * max(0.0, max(score_str, score_weak) - TAU_STD) ** 2
    if mode == 'FollowStrength':
        return LAMBDA_MODE * (
            max(0.0, TAU_FOLLOW - score_str) ** 2
            + max(0.0, max(u_w, u_auth, u_out) - (u_self + u_res)) ** 2
        )
    if mode == 'FollowWealth':
        return LAMBDA_MODE * (
            max(0.0, TAU_FOLLOW - score_weak) ** 2
            + max(0.0, max(u_self + u_res, u_auth, u_out) - u_w) ** 2
        )
    if mode == 'FollowAuthority':
        return LAMBDA_MODE * (
            max(0.0, TAU_FOLLOW - score_weak) ** 2
            + max(0.0, max(u_self + u_res, u_w, u_out) - u_auth) ** 2
        )
    # FollowOutput
    return LAMBDA_MODE * (
        max(0.0, TAU_FOLLOW - score_weak) ** 2
        + max(0.0, max(u_self + u_res, u_w, u_auth) - u_out) ** 2
    )


def _rule_sets() -> tuple[set[int], set[int], set[int], set[int], set[int], set[int]]:
    r_comb = set(range(1, 6))
    r_harm = set(range(6, 12))  # Six harmonies
    r_clash = set(range(12, 18))
    r_frame = set(range(18, 22))
    r_pun = set(range(22, 29))
    r_cor = set(range(29, 35))
    return r_comb, r_harm, r_clash, r_frame, r_pun, r_cor


def compute_energy_breakdown(
    observed_state: ObservedState,
    latent_state: LatentState,
    effective_elements: Sequence[Sequence[int]],
    effective_ten_gods: Sequence[Sequence[int]],
    dynamic_amplitudes: Sequence[float],
    family_evaluations: Sequence[FamilyEvaluation] | None = None,
    season_element_index: int | None = None,
    full_captures: Iterable[FullTransformationCapture] | None = None,
) -> EnergyBreakdown:
    observed_state.validate()
    latent_state.validate()
    entity_count = len(observed_state.base_elements)

    if len(effective_elements) != entity_count:
        raise ValueError('effective_elements length must match entity count')
    if len(effective_ten_gods) != entity_count:
        raise ValueError('effective_ten_gods length must match entity count')
    if len(dynamic_amplitudes) != entity_count:
        raise ValueError('dynamic_amplitudes length must match entity count')

    evaluations = tuple(family_evaluations) if family_evaluations is not None else evaluate_all_families(observed_state)
    if len(evaluations) != len(FAMILY_CATALOG):
        raise ValueError(
            f'family evaluations length mismatch: expected {len(FAMILY_CATALOG)}, got {len(evaluations)}'
        )
    enforce_applicability_lock(latent_state=latent_state, evaluations=evaluations)

    if season_element_index is None:
        season_element_index = season_element_from_month_branch(observed_state.branch_ids[1])

    e_excl = exclusivity_energy(full_captures=full_captures, entity_count=entity_count)
    if isinf(e_excl):
        return EnergyBreakdown(
            e_excl=e_excl,
            e_act=0.0,
            e_intra=0.0,
            e_inter=0.0,
            e_clim=0.0,
            e_dom=0.0,
            e_mode=0.0,
            e_clash=0.0,
            e_frame=0.0,
            e_pun=0.0,
            e_cor=0.0,
            e_cross=0.0,
            total=inf,
            e_chem_by_pillar=(0.0, 0.0, 0.0, 0.0),
            pillar_retention=(0.0, 0.0, 0.0, 0.0),
            pillar_temperatures=(0.0, 0.0, 0.0, 0.0),
            pillar_saturations=(0.0, 0.0, 0.0, 0.0),
            chart_temperature=0.0,
            chart_saturation=0.0,
            mode_score_str=0.0,
            mode_score_weak=0.0,
        )

    flux_matrix = realized_flux(
        observed_state=observed_state,
        effective_elements=effective_elements,
        dynamic_amplitudes=dynamic_amplitudes,
    )
    e_chem_by_pillar = _evaluate_chem_by_pillar(observed_state, flux_matrix)
    retention = pillar_retention(observed_state=observed_state, flux_matrix=flux_matrix)
    theta_k, sat_k, theta_chart, sat_chart = pillar_climate_summaries(
        observed_state=observed_state,
        effective_elements=effective_elements,
    )

    # E_act
    e_act = 0.0
    for evaluation in evaluations:
        rule_idx = evaluation.rule_index
        switch = latent_state.switches[rule_idx - 1]
        if switch <= 0:
            continue
        omega = latent_state.omegas[rule_idx - 1]
        gap = max(0.0, TAU_R - evaluation.support)
        e_act += LAMBDA_ACT * omega * omega * gap * gap

    # E_intra
    stem_by_pos = _stem_entity_index_by_position(observed_state)
    e_intra = 0.0
    for pillar_position in (1, 2, 3, 4):
        pillar_chem = e_chem_by_pillar[pillar_position - 1]
        if pillar_position not in stem_by_pos:
            e_intra += pillar_chem
            continue
        stem_entity = stem_by_pos[pillar_position]
        m_stem = observed_state.masks[stem_entity]
        stem_element = one_hot_to_element(tuple(effective_elements[stem_entity]))
        stem_polarity = observed_state.polarities[stem_entity]
        branch_id = observed_state.branch_ids[pillar_position - 1]
        v_star = life_stage_anchor(stem_element, stem_polarity, branch_id)
        anchor_amplitude = stage_amplitude(v_star)
        penalty = LAMBDA_V * m_stem * abs(dynamic_amplitudes[stem_entity] - anchor_amplitude) ** 2
        e_intra += pillar_chem + penalty

    # E_inter
    e_inter = 0.0
    for source_index in range(entity_count):
        for target_index in range(entity_count):
            if observed_state.positions[source_index] == observed_state.positions[target_index]:
                continue
            e_inter -= flux_matrix[source_index][target_index]

    # E_clim
    e_clim = 0.0
    active_count_by_pillar = {
        p: sum(
            observed_state.masks[i]
            for i in range(entity_count)
            if observed_state.positions[i] == p
        )
        for p in (1, 2, 3, 4)
    }
    for left in (1, 2, 3, 4):
        for right in range(left + 1, 5):
            numerator = 0.0
            for source_index in range(entity_count):
                if observed_state.positions[source_index] != left:
                    continue
                for target_index in range(entity_count):
                    if observed_state.positions[target_index] != right:
                        continue
                    numerator += abs(flux_matrix[source_index][target_index])
            denominator = (
                active_count_by_pillar[left] * active_count_by_pillar[right]
                + EPSILON
            )
            q_km = numerator / denominator
            climate_gap = (theta_k[left - 1] - theta_k[right - 1]) ** 2 + (
                sat_k[left - 1] - sat_k[right - 1]
            ) ** 2
            e_clim += q_km * climate_gap
    e_clim *= LAMBDA_CLIM

    # E_dom
    e_dom = 0.0
    for entity_index in range(entity_count):
        if observed_state.masks[entity_index] == 0:
            continue
        ten_god_index = tuple(effective_ten_gods[entity_index]).index(1)
        group_idx = ten_god_group(ten_god_index)
        resonance = domain_resonance(observed_state.positions[entity_index], group_idx)
        e_dom += (
            observed_state.masks[entity_index]
            * observed_state.hierarchy_levels[entity_index]
            * resonance
        )
    e_dom *= -LAMBDA_DOM

    # E_mode
    (
        score_str,
        score_weak,
        u_self,
        u_res,
        u_out,
        u_w,
        u_auth,
        day_master_element,
    ) = _mode_diagnostics(
        observed_state=observed_state,
        effective_elements=effective_elements,
        season_element_index=season_element_index,
    )
    e_mode = _mode_energy(
        latent_state=latent_state,
        score_str=score_str,
        score_weak=score_weak,
        u_self=u_self,
        u_res=u_res,
        u_out=u_out,
        u_w=u_w,
        u_auth=u_auth,
    )

    # Precompute transport matrix for E_frame.
    transport_matrix: list[list[float]] = []
    for source_index in range(entity_count):
        row: list[float] = []
        for target_index in range(entity_count):
            if source_index == target_index:
                row.append(0.0)
                continue
            row.append(
                transport_capacity(
                    observed_state=observed_state,
                    dynamic_amplitudes=dynamic_amplitudes,
                    source_index=source_index,
                    target_index=target_index,
                )
            )
        transport_matrix.append(row)

    r_comb, r_harm, r_clash, r_frame, r_pun, r_cor = _rule_sets()

    # E_clash
    e_clash = 0.0
    for rule_idx in r_clash:
        if latent_state.switches[rule_idx - 1] != 1:
            continue
        omega = latent_state.omegas[rule_idx - 1]
        evaluation = evaluations[rule_idx - 1]
        local_chem = sum(
            e_chem_by_pillar[position - 1]
            for position in evaluation.selected_positions
        )
        e_clash += (
            LAMBDA_CLASH * omega * omega * (DELTA_V_R**2)
            + LAMBDA_SCATTER * omega * abs(min(0.0, local_chem))
        )

    # E_frame
    e_frame = 0.0
    for rule_idx in r_frame:
        if latent_state.switches[rule_idx - 1] != 2:
            continue
        spec = family_spec(rule_idx)
        if spec.target_element_index is None:
            continue
        omega = latent_state.omegas[rule_idx - 1]
        season_dot = 1.0 if spec.target_element_index == season_element_index else 0.0
        lambda_dyn = LAMBDA_FRAME * (1.0 + OMEGA_SEASON * season_dot)
        evaluation = evaluations[rule_idx - 1]
        inner = 0.0
        for entity_index in evaluation.q_entity_indices:
            if observed_state.masks[entity_index] == 0:
                continue
            entity_element = one_hot_to_element(tuple(effective_elements[entity_index]))
            mismatch = 1.0 - float(entity_element == spec.target_element_index)
            outward_capacity = 0.0
            source_position = observed_state.positions[entity_index]
            for target_index in range(entity_count):
                if observed_state.positions[target_index] == source_position:
                    continue
                outward_capacity += transport_matrix[entity_index][target_index]
            inner += observed_state.masks[entity_index] * mismatch * outward_capacity
        e_frame += lambda_dyn * omega * inner

    # E_pun
    e_pun = 0.0
    for rule_idx in r_pun:
        if latent_state.switches[rule_idx - 1] <= 0:
            continue
        omega = latent_state.omegas[rule_idx - 1]
        evaluation = evaluations[rule_idx - 1]
        retention_sum = sum(
            retention[position - 1] ** 2
            for position in evaluation.selected_positions
        )
        e_pun += LAMBDA_PUN * omega * omega * retention_sum

    # E_cor
    e_cor = 0.0
    for rule_idx in r_cor:
        if latent_state.switches[rule_idx - 1] != 1:
            continue
        spec = family_spec(rule_idx)
        threatened = spec.threatened_harmony_rule_index
        if threatened is None:
            continue
        threatened_spec = family_spec(threatened)
        threatened_full_state = max(threatened_spec.state_domain)
        active_indicator = 1.0 if latent_state.switches[threatened - 1] == threatened_full_state else 0.0
        omega = latent_state.omegas[rule_idx - 1]
        e_cor += LAMBDA_COR * omega * omega * active_indicator

    # E_cross
    center = active_mode_center(day_master_element, latent_state.mode)
    p_dm = observed_state.polarities[observed_state.day_master_index]
    cross_sum = 0.0
    for rule_idx in sorted(r_comb | r_harm):
        spec = family_spec(rule_idx)
        if spec.target_element_index is None:
            continue
        weight_c = partial_state_weight(latent_state.switches[rule_idx - 1])
        if weight_c == 0.0:
            continue
        evaluation = evaluations[rule_idx - 1]
        inner = 0.0
        for entity_index in evaluation.q_entity_indices:
            base_element = one_hot_to_element(observed_state.base_elements[entity_index])
            polarity = observed_state.polarities[entity_index]
            tg_base = ten_god_one_hot(base_element, polarity, center, p_dm)
            tg_target = ten_god_one_hot(spec.target_element_index, polarity, center, p_dm)
            inner += ten_god_distance(tg_base, tg_target)
        cross_sum += weight_c * inner
    e_cross = LAMBDA_CROSS * cross_sum

    total = (
        e_act
        + LAMBDA_INTRA * e_intra
        + LAMBDA_INTER * e_inter
        + e_clim
        + e_dom
        + e_mode
        + e_clash
        + e_frame
        + e_pun
        + e_cor
        + e_cross
    )

    return EnergyBreakdown(
        e_excl=e_excl,
        e_act=e_act,
        e_intra=e_intra,
        e_inter=e_inter,
        e_clim=e_clim,
        e_dom=e_dom,
        e_mode=e_mode,
        e_clash=e_clash,
        e_frame=e_frame,
        e_pun=e_pun,
        e_cor=e_cor,
        e_cross=e_cross,
        total=total,
        e_chem_by_pillar=e_chem_by_pillar,
        pillar_retention=retention,
        pillar_temperatures=theta_k,
        pillar_saturations=sat_k,
        chart_temperature=theta_chart,
        chart_saturation=sat_chart,
        mode_score_str=score_str,
        mode_score_weak=score_weak,
    )

