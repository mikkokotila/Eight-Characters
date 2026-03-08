ELEMENT_COUNT = 5
TEN_GOD_COUNT = 10

ELEMENT_WOOD = 0
ELEMENT_FIRE = 1
ELEMENT_EARTH = 2
ELEMENT_METAL = 3
ELEMENT_WATER = 4

STEM_JIA = 1
STEM_YI = 2
STEM_BING = 3
STEM_DING = 4
STEM_WU = 5
STEM_JI = 6
STEM_GENG = 7
STEM_XIN = 8
STEM_REN = 9
STEM_GUI = 10

BRANCH_ZI = 1
BRANCH_CHOU = 2
BRANCH_YIN = 3
BRANCH_MAO = 4
BRANCH_CHEN = 5
BRANCH_SI = 6
BRANCH_WU = 7
BRANCH_WEI = 8
BRANCH_SHEN = 9
BRANCH_YOU = 10
BRANCH_XU = 11
BRANCH_HAI = 12

ELEMENT_LABELS = (
    'Wood',
    'Fire',
    'Earth',
    'Metal',
    'Water',
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

TEN_GOD_GROUP_LABELS = (
    'Self',
    'Output',
    'Wealth',
    'Authority',
    'Resource',
)

# Math.md Section 3.1.
WUXING_MATRIX: tuple[tuple[float, ...], ...] = (
    (0.5, 1.0, -1.0, -0.8, -0.5),
    (-0.5, 0.5, 1.0, -1.0, -0.8),
    (-0.8, -0.5, 0.5, 1.0, -1.0),
    (-1.0, -0.8, -0.5, 0.5, 1.0),
    (1.0, -1.0, -0.8, -0.5, 0.5),
)

SAME_POLARITY_MULTIPLIER = 1.2
DIFF_POLARITY_MULTIPLIER = 1.0

_OUTPUT_BY_ELEMENT = (
    ELEMENT_FIRE,
    ELEMENT_EARTH,
    ELEMENT_METAL,
    ELEMENT_WATER,
    ELEMENT_WOOD,
)
_RESOURCE_BY_ELEMENT = (
    ELEMENT_WATER,
    ELEMENT_WOOD,
    ELEMENT_FIRE,
    ELEMENT_EARTH,
    ELEMENT_METAL,
)
_WEALTH_BY_ELEMENT = (
    ELEMENT_EARTH,
    ELEMENT_METAL,
    ELEMENT_WATER,
    ELEMENT_WOOD,
    ELEMENT_FIRE,
)
_AUTHORITY_BY_ELEMENT = (
    ELEMENT_METAL,
    ELEMENT_WATER,
    ELEMENT_WOOD,
    ELEMENT_FIRE,
    ELEMENT_EARTH,
)

_STEM_FROM_ELEMENT_POLARITY = {
    (ELEMENT_WOOD, 1): STEM_JIA,
    (ELEMENT_WOOD, 0): STEM_YI,
    (ELEMENT_FIRE, 1): STEM_BING,
    (ELEMENT_FIRE, 0): STEM_DING,
    (ELEMENT_EARTH, 1): STEM_WU,
    (ELEMENT_EARTH, 0): STEM_JI,
    (ELEMENT_METAL, 1): STEM_GENG,
    (ELEMENT_METAL, 0): STEM_XIN,
    (ELEMENT_WATER, 1): STEM_REN,
    (ELEMENT_WATER, 0): STEM_GUI,
}

_ELEMENT_POLARITY_FROM_STEM = {
    stem_id: key for key, stem_id in _STEM_FROM_ELEMENT_POLARITY.items()
}

# Math.md Section 3.3 sigma(ẽ, p).
_SIGMA_ROW_BY_ELEMENT_POLARITY = {
    (ELEMENT_WOOD, 1): 'Jia',
    (ELEMENT_WOOD, 0): 'Yi',
    (ELEMENT_FIRE, 1): 'BingWu',
    (ELEMENT_FIRE, 0): 'DingJi',
    (ELEMENT_EARTH, 1): 'BingWu',
    (ELEMENT_EARTH, 0): 'DingJi',
    (ELEMENT_METAL, 1): 'Geng',
    (ELEMENT_METAL, 0): 'Xin',
    (ELEMENT_WATER, 1): 'Ren',
    (ELEMENT_WATER, 0): 'Gui',
}

# Branch order is [Zi, Chou, Yin, Mao, Chen, Si, Wu, Wei, Shen, You, Xu, Hai].
_LIFE_STAGE_TABLE = {
    'Jia': (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 1),
    'Yi': (7, 6, 5, 4, 3, 2, 1, 12, 11, 10, 9, 8),
    'BingWu': (11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
    'DingJi': (10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 12, 11),
    'Geng': (8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7),
    'Xin': (1, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2),
    'Ren': (5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4),
    'Gui': (4, 3, 2, 1, 12, 11, 10, 9, 8, 7, 6, 5),
}

# Math.md Section 3.4.
def temperature_contribution(element_index: int, polarity: int) -> float:
    _validate_element_index(element_index)
    _validate_polarity(polarity)
    if element_index == ELEMENT_WOOD:
        return 0.5
    if element_index == ELEMENT_FIRE:
        return 1.0
    if element_index == ELEMENT_EARTH:
        return 0.5 if polarity == 1 else -0.5
    if element_index == ELEMENT_METAL:
        return -0.5
    return -1.0


def moisture_contribution(element_index: int, polarity: int) -> float:
    _validate_element_index(element_index)
    _validate_polarity(polarity)
    if element_index == ELEMENT_WOOD:
        return 0.5
    if element_index == ELEMENT_FIRE:
        return -1.0
    if element_index == ELEMENT_EARTH:
        return -1.0 if polarity == 1 else 0.5
    if element_index == ELEMENT_METAL:
        return -1.0
    return 1.0


# Rows: Year, Month, Day, Hour. Cols: Self, Output, Wealth, Authority, Resource.
DOMAIN_RESONANCE_MATRIX: tuple[tuple[float, ...], ...] = (
    (0.75, -0.25, -0.25, 0.25, 1.0),
    (-0.25, 0.50, 0.75, 1.0, -0.50),
    (1.0, -0.25, 0.75, 0.50, 0.0),
    (0.0, 1.0, 0.50, -0.25, -1.0),
)

# Math.md Section 3.6.
STAGE_AMPLITUDE_BY_STAGE = (
    0.8,
    0.6,
    0.7,
    0.9,
    1.0,
    0.8,
    0.4,
    0.1,
    0.2,
    0.05,
    0.3,
    0.5,
)
PARTIAL_STATE_WEIGHT_BY_S = (
    0.0,
    0.5,
    1.0,
    0.0,
)
TAU_R = 0.4
OMEGA_MIN_R = 0.5
PROXIMITY_WEIGHT_BY_GAP = (
    1.0,   # adjacent
    0.5,   # gap 1
    0.25,  # gap 2
)

# Math.md Sections 4.4 and 8.
DELTA_CLASH = 0.3
DELTA_PUN = 0.1
DELTA_V_R = 0.2
EPSILON = 1.0e-5

# Math.md Section 8 energy weights.
LAMBDA_INTRA = 1.0
LAMBDA_INTER = 1.0
LAMBDA_V = 5.0
LAMBDA_CLIM = 1.0
LAMBDA_DOM = 2.0
LAMBDA_MODE = 4.0
LAMBDA_ACT = 2.0
LAMBDA_CLASH = 4.0
LAMBDA_SCATTER = 2.0
LAMBDA_FRAME = 4.0
LAMBDA_PUN = 3.0
LAMBDA_COR = 3.0
LAMBDA_CROSS = 5.0
OMEGA_SEASON = 0.5
TAU_STD = 0.25
TAU_FOLLOW = 0.25

# Math.md Section 7.2 clustering constants.
CLUSTER_ALPHA = 0.6
CLUSTER_BETA = 0.3
CLUSTER_GAMMA = 0.1
DBSCAN_EPS = 0.15
DBSCAN_MIN_SAMPLES = 15


def _validate_element_index(element_index: int) -> None:
    if element_index < 0 or element_index >= ELEMENT_COUNT:
        raise ValueError(f'element index out of range: {element_index}')


def _validate_polarity(polarity: int) -> None:
    if polarity not in (0, 1):
        raise ValueError(f'polarity must be 0 or 1, got {polarity}')


def _validate_ten_god_index(ten_god_index: int) -> None:
    if ten_god_index < 0 or ten_god_index >= TEN_GOD_COUNT:
        raise ValueError(f'Ten God index out of range: {ten_god_index}')


def _validate_stem_id(stem_id: int) -> None:
    if stem_id < 1 or stem_id > 10:
        raise ValueError(f'stem id out of range [1..10]: {stem_id}')


def _validate_branch_id(branch_id: int) -> None:
    if branch_id < 1 or branch_id > 12:
        raise ValueError(f'branch id out of range [1..12]: {branch_id}')


def element_to_one_hot(element_index: int) -> tuple[int, int, int, int, int]:
    _validate_element_index(element_index)
    return tuple(1 if idx == element_index else 0 for idx in range(ELEMENT_COUNT))


def one_hot_to_element(one_hot: tuple[int, int, int, int, int]) -> int:
    if len(one_hot) != ELEMENT_COUNT:
        raise ValueError(f'element one-hot must have length {ELEMENT_COUNT}')
    if any(value not in (0, 1) for value in one_hot):
        raise ValueError('element one-hot must contain only 0/1 values')
    if sum(one_hot) != 1:
        raise ValueError('element one-hot must have exactly one active entry')
    return one_hot.index(1)


def ten_god_to_one_hot(ten_god_index: int) -> tuple[int, ...]:
    _validate_ten_god_index(ten_god_index)
    return tuple(1 if idx == ten_god_index else 0 for idx in range(TEN_GOD_COUNT))


def stem_id_from_element_polarity(element_index: int, polarity: int) -> int:
    _validate_element_index(element_index)
    _validate_polarity(polarity)
    return _STEM_FROM_ELEMENT_POLARITY[(element_index, polarity)]


def stem_element_polarity(stem_id: int) -> tuple[int, int]:
    _validate_stem_id(stem_id)
    return _ELEMENT_POLARITY_FROM_STEM[stem_id]


def output_element(element_index: int) -> int:
    _validate_element_index(element_index)
    return _OUTPUT_BY_ELEMENT[element_index]


def resource_element(element_index: int) -> int:
    _validate_element_index(element_index)
    return _RESOURCE_BY_ELEMENT[element_index]


def wealth_element(element_index: int) -> int:
    _validate_element_index(element_index)
    return _WEALTH_BY_ELEMENT[element_index]


def authority_element(element_index: int) -> int:
    _validate_element_index(element_index)
    return _AUTHORITY_BY_ELEMENT[element_index]


def wuxing_interaction(source_element_index: int, target_element_index: int) -> float:
    _validate_element_index(source_element_index)
    _validate_element_index(target_element_index)
    return WUXING_MATRIX[source_element_index][target_element_index]


def polarity_multiplier(source_polarity: int, target_polarity: int) -> float:
    _validate_polarity(source_polarity)
    _validate_polarity(target_polarity)
    if source_polarity == target_polarity:
        return SAME_POLARITY_MULTIPLIER
    return DIFF_POLARITY_MULTIPLIER


def _relationship_to_center(
    entity_element_index: int,
    center_element_index: int,
) -> str:
    _validate_element_index(entity_element_index)
    _validate_element_index(center_element_index)
    if entity_element_index == center_element_index:
        return 'same'
    if entity_element_index == output_element(center_element_index):
        return 'output'
    if entity_element_index == wealth_element(center_element_index):
        return 'wealth'
    if entity_element_index == authority_element(center_element_index):
        return 'authority'
    if entity_element_index == resource_element(center_element_index):
        return 'resource'
    raise ValueError('Unexpected elemental relationship state')


def ten_god_index(
    entity_element_index: int,
    entity_polarity: int,
    center_element_index: int,
    center_polarity: int,
) -> int:
    _validate_polarity(entity_polarity)
    _validate_polarity(center_polarity)
    relationship = _relationship_to_center(entity_element_index, center_element_index)
    same_polarity = entity_polarity == center_polarity

    if relationship == 'same':
        return 0 if same_polarity else 1
    if relationship == 'output':
        return 2 if same_polarity else 3
    if relationship == 'wealth':
        return 4 if same_polarity else 5
    if relationship == 'authority':
        return 6 if same_polarity else 7
    return 8 if same_polarity else 9


def ten_god_one_hot(
    entity_element_index: int,
    entity_polarity: int,
    center_element_index: int,
    center_polarity: int,
) -> tuple[int, ...]:
    return ten_god_to_one_hot(
        ten_god_index(
            entity_element_index=entity_element_index,
            entity_polarity=entity_polarity,
            center_element_index=center_element_index,
            center_polarity=center_polarity,
        )
    )


def ten_god_distance(one_hot_a: tuple[int, ...], one_hot_b: tuple[int, ...]) -> int:
    if len(one_hot_a) != TEN_GOD_COUNT or len(one_hot_b) != TEN_GOD_COUNT:
        raise ValueError('Ten-God one-hot vectors must have length 10')
    if sum(one_hot_a) != 1 or sum(one_hot_b) != 1:
        raise ValueError('Ten-God vectors must be one-hot')
    dot = sum(a * b for a, b in zip(one_hot_a, one_hot_b))
    return 1 - dot


def ten_god_group(ten_god_index: int) -> int:
    _validate_ten_god_index(ten_god_index)
    if ten_god_index in (0, 1):
        return 0
    if ten_god_index in (2, 3):
        return 1
    if ten_god_index in (4, 5):
        return 2
    if ten_god_index in (6, 7):
        return 3
    return 4


def sigma_stem_row(element_index: int, polarity: int) -> str:
    _validate_element_index(element_index)
    _validate_polarity(polarity)
    return _SIGMA_ROW_BY_ELEMENT_POLARITY[(element_index, polarity)]


def life_stage_anchor(element_index: int, polarity: int, branch_index_1_based: int) -> int:
    if branch_index_1_based < 1 or branch_index_1_based > 12:
        raise ValueError('branch index must be in [1..12]')
    row_name = sigma_stem_row(element_index, polarity)
    return _LIFE_STAGE_TABLE[row_name][branch_index_1_based - 1]


def domain_resonance(position_1_based: int, ten_god_group_index: int) -> float:
    if position_1_based < 1 or position_1_based > 4:
        raise ValueError('position must be in [1..4]')
    if ten_god_group_index < 0 or ten_god_group_index > 4:
        raise ValueError('Ten-God group index must be in [0..4]')
    return DOMAIN_RESONANCE_MATRIX[position_1_based - 1][ten_god_group_index]


def stage_amplitude(vitality_stage_1_based: int) -> float:
    if vitality_stage_1_based < 1 or vitality_stage_1_based > 12:
        raise ValueError('vitality stage must be in [1..12]')
    return STAGE_AMPLITUDE_BY_STAGE[vitality_stage_1_based - 1]


def partial_state_weight(state_value: int) -> float:
    if state_value < 0 or state_value > 3:
        raise ValueError('state value must be in [0..3]')
    return PARTIAL_STATE_WEIGHT_BY_S[state_value]


def proximity_weight_by_gap(gap: int) -> float:
    if gap < 0 or gap > 2:
        raise ValueError('gap must be one of {0,1,2}')
    return PROXIMITY_WEIGHT_BY_GAP[gap]


def omega_max_for_proximity(proximity_weight: float) -> float:
    return 1.0 + proximity_weight


def season_score(element_index: int, season_element_index: int) -> int:
    _validate_element_index(element_index)
    _validate_element_index(season_element_index)
    if element_index == season_element_index:
        return 2  # Prosperous
    if element_index == output_element(season_element_index):
        return 1  # Strong
    if element_index == resource_element(season_element_index):
        return 0  # Resting
    if element_index == authority_element(season_element_index):
        return -1  # Imprisoned
    return -2  # Dead


def season_element_from_month_branch(branch_id: int) -> int:
    _validate_branch_id(branch_id)
    # Frozen by directional season groups in the taxonomy:
    # [Yin, Mao, Chen] -> Wood; [Si, Wu, Wei] -> Fire;
    # [Shen, You, Xu] -> Metal; [Hai, Zi, Chou] -> Water.
    if branch_id in (BRANCH_YIN, BRANCH_MAO, BRANCH_CHEN):
        return ELEMENT_WOOD
    if branch_id in (BRANCH_SI, BRANCH_WU, BRANCH_WEI):
        return ELEMENT_FIRE
    if branch_id in (BRANCH_SHEN, BRANCH_YOU, BRANCH_XU):
        return ELEMENT_METAL
    return ELEMENT_WATER

