from dataclasses import dataclass
from itertools import combinations, product

from eight_characters.evolution.primitives import (
    BRANCH_CHEN,
    BRANCH_CHOU,
    BRANCH_HAI,
    BRANCH_MAO,
    BRANCH_SHEN,
    BRANCH_SI,
    BRANCH_WEI,
    BRANCH_WU,
    BRANCH_XU,
    BRANCH_YIN,
    BRANCH_YOU,
    BRANCH_ZI,
    ELEMENT_EARTH,
    ELEMENT_FIRE,
    ELEMENT_METAL,
    ELEMENT_WATER,
    ELEMENT_WOOD,
    STEM_BING,
    STEM_DING,
    STEM_GENG,
    STEM_GUI,
    STEM_JI,
    STEM_JIA,
    STEM_REN,
    STEM_WU,
    STEM_XIN,
    STEM_YI,
    one_hot_to_element,
    proximity_weight_by_gap,
    stage_amplitude,
    stem_id_from_element_polarity,
)
from eight_characters.evolution.state import LatentState, ObservedState, RULE_STATE_DOMAINS

FAMILY_STEM_PAIR = 'stem_pair'
FAMILY_BRANCH_PAIR = 'branch_pair'
FAMILY_BRANCH_TRIPLE = 'branch_triple'
FAMILY_SELF_PUNISHMENT = 'self_punishment'


@dataclass(frozen=True)
class FamilySpec:
    rule_index: int
    name: str
    category: str
    state_domain: tuple[int, ...]
    stem_members: tuple[int, ...] = ()
    branch_members: tuple[int, ...] = ()
    target_element_index: int | None = None
    threatened_harmony_rule_index: int | None = None


@dataclass(frozen=True)
class FamilyEvaluation:
    rule_index: int
    applicability: int
    selected_positions: tuple[int, ...]
    proximity_weight: float
    q_entity_indices: tuple[int, ...]
    support: float
    presence_state: int


FAMILY_CATALOG: tuple[FamilySpec, ...] = (
    # Stem combinations r=1..5
    FamilySpec(1, 'Jia+Ji', FAMILY_STEM_PAIR, RULE_STATE_DOMAINS[0], (STEM_JIA, STEM_JI), (), ELEMENT_EARTH),
    FamilySpec(2, 'Yi+Geng', FAMILY_STEM_PAIR, RULE_STATE_DOMAINS[1], (STEM_YI, STEM_GENG), (), ELEMENT_METAL),
    FamilySpec(3, 'Bing+Xin', FAMILY_STEM_PAIR, RULE_STATE_DOMAINS[2], (STEM_BING, STEM_XIN), (), ELEMENT_WATER),
    FamilySpec(4, 'Ding+Ren', FAMILY_STEM_PAIR, RULE_STATE_DOMAINS[3], (STEM_DING, STEM_REN), (), ELEMENT_WOOD),
    FamilySpec(5, 'Wu+Gui', FAMILY_STEM_PAIR, RULE_STATE_DOMAINS[4], (STEM_WU, STEM_GUI), (), ELEMENT_FIRE),
    # Six harmonies r=6..11
    FamilySpec(6, 'Zi+Chou Harmony', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[5], (), (BRANCH_ZI, BRANCH_CHOU), ELEMENT_EARTH),
    FamilySpec(7, 'Yin+Hai Harmony', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[6], (), (BRANCH_YIN, BRANCH_HAI), ELEMENT_WOOD),
    FamilySpec(8, 'Mao+Xu Harmony', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[7], (), (BRANCH_MAO, BRANCH_XU), ELEMENT_FIRE),
    FamilySpec(9, 'Chen+You Harmony', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[8], (), (BRANCH_CHEN, BRANCH_YOU), ELEMENT_METAL),
    FamilySpec(10, 'Si+Shen Harmony', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[9], (), (BRANCH_SI, BRANCH_SHEN), ELEMENT_WATER),
    FamilySpec(11, 'Wu+Wei Harmony', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[10], (), (BRANCH_WU, BRANCH_WEI), ELEMENT_FIRE),
    # Six clashes r=12..17
    FamilySpec(12, 'Zi-Wu Clash', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[11], (), (BRANCH_ZI, BRANCH_WU)),
    FamilySpec(13, 'Chou-Wei Clash', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[12], (), (BRANCH_CHOU, BRANCH_WEI)),
    FamilySpec(14, 'Yin-Shen Clash', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[13], (), (BRANCH_YIN, BRANCH_SHEN)),
    FamilySpec(15, 'Mao-You Clash', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[14], (), (BRANCH_MAO, BRANCH_YOU)),
    FamilySpec(16, 'Chen-Xu Clash', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[15], (), (BRANCH_CHEN, BRANCH_XU)),
    FamilySpec(17, 'Si-Hai Clash', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[16], (), (BRANCH_SI, BRANCH_HAI)),
    # Three harmony frames r=18..21
    FamilySpec(18, 'Shen+Zi+Chen Frame', FAMILY_BRANCH_TRIPLE, RULE_STATE_DOMAINS[17], (), (BRANCH_SHEN, BRANCH_ZI, BRANCH_CHEN), ELEMENT_WATER),
    FamilySpec(19, 'Hai+Mao+Wei Frame', FAMILY_BRANCH_TRIPLE, RULE_STATE_DOMAINS[18], (), (BRANCH_HAI, BRANCH_MAO, BRANCH_WEI), ELEMENT_WOOD),
    FamilySpec(20, 'Yin+Wu+Xu Frame', FAMILY_BRANCH_TRIPLE, RULE_STATE_DOMAINS[19], (), (BRANCH_YIN, BRANCH_WU, BRANCH_XU), ELEMENT_FIRE),
    FamilySpec(21, 'Si+You+Chou Frame', FAMILY_BRANCH_TRIPLE, RULE_STATE_DOMAINS[20], (), (BRANCH_SI, BRANCH_YOU, BRANCH_CHOU), ELEMENT_METAL),
    # Punishments r=22..28
    FamilySpec(22, 'Yin-Si-Shen Punishment', FAMILY_BRANCH_TRIPLE, RULE_STATE_DOMAINS[21], (), (BRANCH_YIN, BRANCH_SI, BRANCH_SHEN)),
    FamilySpec(23, 'Chou-Wei-Xu Punishment', FAMILY_BRANCH_TRIPLE, RULE_STATE_DOMAINS[22], (), (BRANCH_CHOU, BRANCH_WEI, BRANCH_XU)),
    FamilySpec(24, 'Zi-Mao Punishment', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[23], (), (BRANCH_ZI, BRANCH_MAO)),
    FamilySpec(25, 'Zi-Zi Self Punishment', FAMILY_SELF_PUNISHMENT, RULE_STATE_DOMAINS[24], (), (BRANCH_ZI,)),
    FamilySpec(26, 'Wu-Wu Self Punishment', FAMILY_SELF_PUNISHMENT, RULE_STATE_DOMAINS[25], (), (BRANCH_WU,)),
    FamilySpec(27, 'You-You Self Punishment', FAMILY_SELF_PUNISHMENT, RULE_STATE_DOMAINS[26], (), (BRANCH_YOU,)),
    FamilySpec(28, 'Hai-Hai Self Punishment', FAMILY_SELF_PUNISHMENT, RULE_STATE_DOMAINS[27], (), (BRANCH_HAI,)),
    # Harms r=29..34
    FamilySpec(29, 'Zi-Wei Harm', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[28], (), (BRANCH_ZI, BRANCH_WEI), threatened_harmony_rule_index=6),
    FamilySpec(30, 'Chou-Wu Harm', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[29], (), (BRANCH_CHOU, BRANCH_WU), threatened_harmony_rule_index=6),
    FamilySpec(31, 'Yin-Si Harm', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[30], (), (BRANCH_YIN, BRANCH_SI), threatened_harmony_rule_index=7),
    FamilySpec(32, 'Mao-Chen Harm', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[31], (), (BRANCH_MAO, BRANCH_CHEN), threatened_harmony_rule_index=8),
    FamilySpec(33, 'Shen-Hai Harm', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[32], (), (BRANCH_SHEN, BRANCH_HAI), threatened_harmony_rule_index=10),
    FamilySpec(34, 'You-Xu Harm', FAMILY_BRANCH_PAIR, RULE_STATE_DOMAINS[33], (), (BRANCH_YOU, BRANCH_XU), threatened_harmony_rule_index=9),
)


def family_catalog() -> tuple[FamilySpec, ...]:
    return FAMILY_CATALOG


def family_spec(rule_index: int) -> FamilySpec:
    if rule_index < 1 or rule_index > len(FAMILY_CATALOG):
        raise ValueError(f'rule index out of range [1..{len(FAMILY_CATALOG)}]: {rule_index}')
    return FAMILY_CATALOG[rule_index - 1]


def _distance_weight(position_a: int, position_b: int) -> float:
    distance = abs(position_a - position_b)
    if distance < 1 or distance > 3:
        raise ValueError(f'invalid pillar distance {distance} for positions {position_a},{position_b}')
    return proximity_weight_by_gap(distance - 1)


def _pair_distance(pair: tuple[int, int]) -> int:
    return abs(pair[0] - pair[1])


def _select_nearest_pair(
    candidates: list[tuple[int, int]],
    day_position: int | None = None,
) -> tuple[int, int]:
    if not candidates:
        raise ValueError('cannot select nearest pair from empty candidate list')

    min_distance = min(_pair_distance(pair) for pair in candidates)
    filtered = [pair for pair in candidates if _pair_distance(pair) == min_distance]

    if day_position is not None:
        day_matches = [pair for pair in filtered if day_position in pair]
        if len(day_matches) == 1:
            filtered = day_matches

    return min(filtered)


def _pair_positions_for_branches(
    branch_ids: tuple[int, int, int, int],
    branch_a: int,
    branch_b: int,
) -> list[tuple[int, int]]:
    positions_a = [idx for idx, branch in enumerate(branch_ids, start=1) if branch == branch_a]
    positions_b = [idx for idx, branch in enumerate(branch_ids, start=1) if branch == branch_b]
    return [tuple(sorted((a, b))) for a, b in product(positions_a, positions_b) if a != b]


def _mean_pairwise_proximity(positions: tuple[int, ...]) -> float:
    if len(positions) < 2:
        return 0.0
    weights: list[float] = []
    for pos_a, pos_b in combinations(positions, 2):
        weights.append(_distance_weight(pos_a, pos_b))
    return sum(weights) / len(weights)


def _stem_entity_index_by_position(observed_state: ObservedState) -> dict[int, int]:
    result: dict[int, int] = {}
    for entity_index, (mask, hierarchy, position) in enumerate(
        zip(
            observed_state.masks,
            observed_state.hierarchy_levels,
            observed_state.positions,
        )
    ):
        if mask != 1 or hierarchy != 4:
            continue
        if position in result:
            raise ValueError(f'multiple active stem-level entities found in pillar position {position}')
        result[position] = entity_index
    return result


def pillar_stem_ids(observed_state: ObservedState) -> tuple[int, int, int, int]:
    observed_state.validate()
    stem_entity_by_pos = _stem_entity_index_by_position(observed_state)
    pillar_stems: list[int] = []
    for position in (1, 2, 3, 4):
        if position not in stem_entity_by_pos:
            raise ValueError(f'no active stem-level entity found in pillar position {position}')
        entity_index = stem_entity_by_pos[position]
        element_index = one_hot_to_element(observed_state.base_elements[entity_index])
        polarity = observed_state.polarities[entity_index]
        pillar_stems.append(stem_id_from_element_polarity(element_index, polarity))
    return tuple(pillar_stems)  # type: ignore[return-value]


def _q_indices_for_positions(observed_state: ObservedState, positions: tuple[int, ...]) -> tuple[int, ...]:
    position_set = set(positions)
    return tuple(
        entity_index
        for entity_index, (mask, position) in enumerate(
            zip(observed_state.masks, observed_state.positions)
        )
        if mask == 1 and position in position_set
    )


def _q_indices_for_stem_positions(
    observed_state: ObservedState,
    stem_entity_by_pos: dict[int, int],
    positions: tuple[int, int],
) -> tuple[int, ...]:
    q_indices: list[int] = []
    for position in positions:
        if position not in stem_entity_by_pos:
            raise ValueError(f'missing stem-level entity for selected position {position}')
        q_indices.append(stem_entity_by_pos[position])
    return tuple(q_indices)


def _support_from_q(
    applicability: int,
    proximity_weight: float,
    q_entity_indices: tuple[int, ...],
    observed_state: ObservedState,
) -> float:
    if applicability == 0:
        return 0.0
    if not q_entity_indices:
        raise ValueError('Q_r cannot be empty when applicability is active')
    avg_vitality = sum(
        stage_amplitude(observed_state.vitality_stages[entity_index])
        for entity_index in q_entity_indices
    ) / len(q_entity_indices)
    return float(applicability) * proximity_weight * avg_vitality


def evaluate_family(rule_index: int, observed_state: ObservedState) -> FamilyEvaluation:
    observed_state.validate()
    spec = family_spec(rule_index)
    branch_ids = observed_state.branch_ids

    if spec.category == FAMILY_STEM_PAIR:
        stem_entity_by_pos = _stem_entity_index_by_position(observed_state)
        stem_ids = pillar_stem_ids(observed_state)
        stem_a, stem_b = spec.stem_members
        positions_a = [pos for pos, stem in enumerate(stem_ids, start=1) if stem == stem_a]
        positions_b = [pos for pos, stem in enumerate(stem_ids, start=1) if stem == stem_b]
        candidates = [tuple(sorted((a, b))) for a, b in product(positions_a, positions_b) if a != b]
        if not candidates:
            return FamilyEvaluation(rule_index, 0, (), 0.0, (), 0.0, 0)

        selected_pair = _select_nearest_pair(
            candidates=candidates,
            day_position=observed_state.positions[observed_state.day_master_index],
        )
        proximity = _distance_weight(selected_pair[0], selected_pair[1])
        q_indices = _q_indices_for_stem_positions(
            observed_state=observed_state,
            stem_entity_by_pos=stem_entity_by_pos,
            positions=selected_pair,
        )
        support = _support_from_q(1, proximity, q_indices, observed_state)
        return FamilyEvaluation(rule_index, 1, selected_pair, proximity, q_indices, support, 2)

    if spec.category == FAMILY_BRANCH_PAIR:
        branch_a, branch_b = spec.branch_members
        candidates = _pair_positions_for_branches(branch_ids, branch_a, branch_b)
        if not candidates:
            return FamilyEvaluation(rule_index, 0, (), 0.0, (), 0.0, 0)

        selected_pair = _select_nearest_pair(candidates=candidates, day_position=None)
        proximity = _distance_weight(selected_pair[0], selected_pair[1])
        q_indices = _q_indices_for_positions(observed_state, selected_pair)
        support = _support_from_q(1, proximity, q_indices, observed_state)
        return FamilyEvaluation(rule_index, 1, selected_pair, proximity, q_indices, support, 2)

    if spec.category == FAMILY_SELF_PUNISHMENT:
        target_branch = spec.branch_members[0]
        positions = [
            position for position, branch in enumerate(branch_ids, start=1) if branch == target_branch
        ]
        if len(positions) < 2:
            return FamilyEvaluation(rule_index, 0, (), 0.0, (), 0.0, len(positions))

        candidates = [tuple(pair) for pair in combinations(positions, 2)]
        selected_pair = _select_nearest_pair(candidates=candidates, day_position=None)
        proximity = _distance_weight(selected_pair[0], selected_pair[1])
        q_indices = _q_indices_for_positions(observed_state, selected_pair)
        support = _support_from_q(1, proximity, q_indices, observed_state)
        return FamilyEvaluation(rule_index, 1, selected_pair, proximity, q_indices, support, len(positions))

    # Branch triples (frames and triangle punishments)
    member_set = set(spec.branch_members)
    participating_positions = tuple(
        position
        for position, branch in enumerate(branch_ids, start=1)
        if branch in member_set
    )
    unique_members_present = len(
        {branch for branch in branch_ids if branch in member_set}
    )
    applicability = 1 if unique_members_present >= 2 else 0
    proximity = _mean_pairwise_proximity(participating_positions)
    q_indices = _q_indices_for_positions(observed_state, participating_positions)
    support = _support_from_q(applicability, proximity, q_indices, observed_state)
    selected_positions = participating_positions if applicability == 1 else ()
    return FamilyEvaluation(
        rule_index=rule_index,
        applicability=applicability,
        selected_positions=selected_positions,
        proximity_weight=proximity,
        q_entity_indices=q_indices if applicability == 1 else (),
        support=support,
        presence_state=unique_members_present,
    )


def evaluate_all_families(observed_state: ObservedState) -> tuple[FamilyEvaluation, ...]:
    observed_state.validate()
    return tuple(
        evaluate_family(rule_index=rule_index, observed_state=observed_state)
        for rule_index in range(1, len(FAMILY_CATALOG) + 1)
    )


def applicability_mask(observed_state: ObservedState) -> tuple[int, ...]:
    return tuple(
        evaluation.applicability
        for evaluation in evaluate_all_families(observed_state)
    )


def enforce_applicability_lock(
    latent_state: LatentState,
    evaluations: tuple[FamilyEvaluation, ...],
) -> None:
    latent_state.validate()
    if len(evaluations) != len(FAMILY_CATALOG):
        raise ValueError(
            f'evaluations length mismatch: expected {len(FAMILY_CATALOG)}, got {len(evaluations)}'
        )
    for evaluation in evaluations:
        switch_value = latent_state.switches[evaluation.rule_index - 1]
        if evaluation.applicability == 0 and switch_value > 0:
            raise ValueError(
                f'Rule r={evaluation.rule_index} has A_r(Y)=0 so switch must be 0, got {switch_value}'
            )

