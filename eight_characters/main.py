import csv
import json
import secrets
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from typing_extensions import TypedDict

from eight_characters import __version__
from eight_characters.conventions import ConventionSettings
from eight_characters.data import (
    BRANCHES,
    STEMS,
    ChartPayload,
    build_chart,
)
from eight_characters.engine import compute_engine_payload
from eight_characters.evolution import energy as evolution_energy
from eight_characters.evolution import inference as evolution_inference
from eight_characters.evolution import mechanics as evolution_mechanics
from eight_characters.evolution import postprocess as evolution_postprocess
from eight_characters.evolution import primitives as evolution_primitives
from eight_characters.evolution.inference import InferenceConfig
from eight_characters.evolution.pipeline import EvolutionInput, run_natal_mvp
from eight_characters.evolution.postprocess import PostprocessConfig
from eight_characters.evolution.primitives import (
    ELEMENT_EARTH,
    ELEMENT_FIRE,
    ELEMENT_METAL,
    ELEMENT_WATER,
    ELEMENT_WOOD,
    life_stage_anchor,
)
from eight_characters.evolution.state import RULE_COUNT
from eight_characters.explorer.build_data_js_from_evolution import (
    build_multi_basin_graph_data,
)
from eight_characters.time_convert import (
    AmbiguousTimeError,
    BirthInput,
    NonexistentTimeError,
)

BASE_DIR = Path(__file__).resolve().parent
MAPPINGS_DIR = BASE_DIR / 'resources' / 'mappings'
EXPLORER_DIR = BASE_DIR / 'explorer'

BRANCH_ID_BY_CHAR: dict[str, int] = {
    char: index + 1
    for index, char in enumerate(
        ('子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥')
    )
}
ELEMENT_INDEX_BY_NAME: dict[str, int] = {
    'wood': ELEMENT_WOOD,
    'fire': ELEMENT_FIRE,
    'earth': ELEMENT_EARTH,
    'metal': ELEMENT_METAL,
    'water': ELEMENT_WATER,
}
QI_HIERARCHY_BY_TYPE: dict[str, int] = {'main': 3, 'middle': 2, 'residual': 1}

EVOLUTION_DEFAULT_PARTICLES = 24
EVOLUTION_DEFAULT_TEMPERATURE_STEPS = 2
EVOLUTION_DEFAULT_SWEEPS_PER_STEP = 1
EVOLUTION_DEFAULT_DBSCAN_EPS = 0.08
EVOLUTION_DEFAULT_DBSCAN_MIN_SAMPLES = 1
EVOLUTION_DEFAULT_SEED_MODE = 'fixed_42'
EVOLUTION_FIXED_SEED = 42
EVOLUTION_CONSTANT_PATCH_LOCK = threading.Lock()

app = FastAPI(title='Eight Characters')
app.mount('/static', StaticFiles(directory=BASE_DIR / 'static'), name='static')
app.mount('/explorer', StaticFiles(directory=EXPLORER_DIR, html=True), name='explorer')
templates = Jinja2Templates(directory=BASE_DIR / 'templates')


def _validation_error_message(exc: RequestValidationError) -> str:
    details: list[str] = []
    for error in exc.errors():
        raw_location = error.get('loc', ())
        location_parts = [str(part) for part in raw_location if str(part) != 'body']
        location = '.'.join(location_parts)
        message = str(error.get('msg', 'Invalid request payload.'))
        if location:
            details.append(f'{location}: {message}')
        else:
            details.append(message)
    if details:
        return '; '.join(details)
    return 'Invalid request payload.'


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={'detail': _validation_error_message(exc)},
    )


# ── Request / Response models ──


class ChartRequest(BaseModel):
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    hour_stem: str  # Chinese character
    hour_branch: str
    day_stem: str
    day_branch: str
    month_stem: str
    month_branch: str
    year_stem: str
    year_branch: str
    lang: str = 'fi'


class LocationInput(BaseModel):
    timezone: str
    longitude: float
    latitude: float
    fold: int | None = None


class ConventionInput(BaseModel):
    zi_convention: str = 'split_midnight'
    hour_basis: str = 'true_solar'
    day_boundary_basis: str = 'true_solar'


class FourPillarsRequest(BaseModel):
    date: str
    time: str
    location: LocationInput | None = None
    city: str | None = None
    country: str | None = None
    conventions: ConventionInput = Field(default_factory=ConventionInput)
    birth_time_uncertainty_seconds: float | None = None
    include_chart: bool = False
    include_hidden_stems: bool = False
    lang: str = 'fi'


class EvolutionExplorerRequest(BaseModel):
    date: str
    time: str
    location: LocationInput | None = None
    city: str | None = None
    country: str | None = None
    conventions: ConventionInput = Field(default_factory=ConventionInput)
    birth_time_uncertainty_seconds: float | None = None
    particles: int = EVOLUTION_DEFAULT_PARTICLES
    temperature_steps: int = EVOLUTION_DEFAULT_TEMPERATURE_STEPS
    sweeps_per_step: int = EVOLUTION_DEFAULT_SWEEPS_PER_STEP
    dbscan_eps: float = EVOLUTION_DEFAULT_DBSCAN_EPS
    dbscan_min_samples: int = EVOLUTION_DEFAULT_DBSCAN_MIN_SAMPLES
    seed_mode: str = EVOLUTION_DEFAULT_SEED_MODE
    basin_index: int = 0
    flux_threshold: float = 0.0
    controls: dict[str, Any] | None = None


class LocationSearchRequest(BaseModel):
    city: str
    country: str | None = None


class LocationSuggestRequest(BaseModel):
    query: str
    limit: int = 6


class HiddenStemsRequest(BaseModel):
    year_pillar: str
    month_pillar: str
    day_pillar: str
    hour_pillar: str


class ResolvedCity(BaseModel):
    city: str
    country: str
    timezone: str


class GeocodeResult(TypedDict, total=False):
    name: str
    country: str
    timezone: str
    longitude: float
    latitude: float


class CityLookupServiceError(RuntimeError):
    """Raised when upstream geocoding service is unavailable or fails."""


def _parse_date_and_time(
    date_value: str, time_value: str
) -> tuple[int, int, int, int, int, int]:
    try:
        parsed_date = datetime.strptime(date_value, '%Y-%m-%d')
    except ValueError as exc:
        raise ValueError('date must be in YYYY-MM-DD format.') from exc

    time_formats = ('%H:%M:%S', '%H:%M')
    parsed_time = None
    for time_format in time_formats:
        try:
            parsed_time = datetime.strptime(time_value, time_format)
            break
        except ValueError:
            continue
    if parsed_time is None:
        raise ValueError('time must be in HH:MM or HH:MM:SS format.')

    return (
        parsed_date.year,
        parsed_date.month,
        parsed_date.day,
        parsed_time.hour,
        parsed_time.minute,
        parsed_time.second,
    )


async def _resolve_city_location(
    city: str, country: str | None = None
) -> tuple[LocationInput, ResolvedCity]:
    city_name = city.strip()
    country_name = (country or '').strip()
    if not city_name:
        raise ValueError('city must not be empty.')

    query = f'{city_name}, {country_name}' if country_name else city_name
    count = 8 if country_name else 1
    results = await _search_city_candidates(query, count=count)
    if not results:
        if country_name:
            raise ValueError(
                f'Could not resolve city/country combination: {city_name}, {country_name}'
            )
        raise ValueError(f'Could not resolve city: {city_name}')

    if not country_name:
        return _city_models_from_result(results[0], city_name)

    target_country = country_name.casefold()
    for candidate in results:
        candidate_country = str(candidate.get('country') or '').strip().casefold()
        if candidate_country == target_country:
            return _city_models_from_result(candidate, city_name)
    raise ValueError(
        f'Could not resolve city/country combination: {city_name}, {country_name}'
    )


async def _search_city_candidates(query: str, count: int = 6) -> list[GeocodeResult]:
    city_name = query.strip()
    if not city_name:
        return []

    safe_count = max(1, min(count, 20))
    geocode_url = 'https://geocoding-api.open-meteo.com/v1/search'
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                geocode_url,
                params={'name': city_name, 'count': safe_count, 'language': 'en'},
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise CityLookupServiceError('City lookup service returned an error.') from exc
    except httpx.RequestError as exc:
        raise CityLookupServiceError('City lookup service request failed.') from exc

    payload = cast(dict[str, Any], response.json())
    raw_results_obj = payload.get('results')
    if not isinstance(raw_results_obj, list):
        return []
    raw_results = cast(list[object], raw_results_obj)
    results: list[GeocodeResult] = []
    for item in raw_results:
        if isinstance(item, dict):
            results.append(cast(GeocodeResult, item))
    return results


def _city_models_from_result(
    top_match: GeocodeResult,
    city_fallback: str,
) -> tuple[LocationInput, ResolvedCity]:
    timezone_name = top_match.get('timezone')
    longitude = top_match.get('longitude')
    latitude = top_match.get('latitude')
    if timezone_name is None or longitude is None or latitude is None:
        raise ValueError('City resolution returned incomplete location data.')

    resolved_location = LocationInput(
        timezone=str(timezone_name),
        longitude=float(longitude),
        latitude=float(latitude),
    )
    resolved_city = ResolvedCity(
        city=str(top_match.get('name') or city_fallback),
        country=str(top_match.get('country') or ''),
        timezone=str(timezone_name),
    )
    return resolved_location, resolved_city


def _build_four_pillars_result(
    *,
    date_value: str,
    time_value: str,
    location: LocationInput,
    conventions_input: ConventionInput,
    birth_time_uncertainty_seconds: float | None,
) -> dict[str, Any]:
    year, month, day, hour, minute, second = _parse_date_and_time(
        date_value, time_value
    )
    conventions = ConventionSettings(
        zi_convention=conventions_input.zi_convention,
        hour_basis=conventions_input.hour_basis,
        day_boundary_basis=conventions_input.day_boundary_basis,
    )
    birth_input = BirthInput(
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        second=second,
        timezone_name=location.timezone,
        longitude=location.longitude,
        latitude=location.latitude,
        fold=location.fold,
        birth_time_uncertainty_seconds=birth_time_uncertainty_seconds,
        conventions=conventions,
    )
    engine_payload = compute_engine_payload(birth_input)

    return {
        'solar_time': {
            'utc_time': engine_payload['intermediate']['utc_time'],
            'local_mean_solar_time': engine_payload['intermediate'][
                'local_mean_solar_time'
            ],
            'true_solar_time': engine_payload['intermediate']['true_solar_time'],
            'equation_of_time_minutes': engine_payload['intermediate'][
                'equation_of_time_minutes'
            ],
        },
        'four_pillars': engine_payload['pillars'],
        'flags': engine_payload['flags'],
        'engine': engine_payload['engine'],
    }


def _pillar_component_from_four_pillars(
    four_pillars: dict[str, Any],
    pillar_name: str,
    component_name: str,
) -> str:
    pillar_raw = four_pillars.get(pillar_name)
    if not isinstance(pillar_raw, dict):
        raise ValueError(f'four_pillars.{pillar_name} is missing or invalid')
    pillar = cast(dict[str, Any], pillar_raw)

    component_raw = pillar.get(component_name)
    if not isinstance(component_raw, dict):
        raise ValueError(
            f'four_pillars.{pillar_name}.{component_name} is missing or invalid'
        )
    component = cast(dict[str, Any], component_raw)

    chinese_char_raw = component.get('chinese')
    if not isinstance(chinese_char_raw, str) or not chinese_char_raw:
        raise ValueError(
            f'four_pillars.{pillar_name}.{component_name}.chinese is missing or invalid'
        )
    return chinese_char_raw


def _pillar_text_for_hidden_stems(
    four_pillars: dict[str, Any],
    pillar_name: str,
) -> str:
    stem_char = _pillar_component_from_four_pillars(
        four_pillars=four_pillars,
        pillar_name=pillar_name,
        component_name='stem',
    )
    branch_char = _pillar_component_from_four_pillars(
        four_pillars=four_pillars,
        pillar_name=pillar_name,
        component_name='branch',
    )
    return f'{stem_char}{branch_char}'


def _chart_components_from_four_pillars(
    four_pillars: dict[str, Any],
) -> dict[str, tuple[str, str]]:
    components: dict[str, tuple[str, str]] = {}
    for pillar_name in ('year', 'month', 'day', 'hour'):
        components[pillar_name] = (
            _pillar_component_from_four_pillars(
                four_pillars=four_pillars,
                pillar_name=pillar_name,
                component_name='stem',
            ),
            _pillar_component_from_four_pillars(
                four_pillars=four_pillars,
                pillar_name=pillar_name,
                component_name='branch',
            ),
        )
    return components


def _build_chart_from_four_pillars(
    *,
    date_value: str,
    time_value: str,
    lang: str,
    four_pillars: dict[str, Any],
) -> ChartPayload:
    chart_components = _chart_components_from_four_pillars(four_pillars)
    hour_stem, hour_branch = chart_components['hour']
    day_stem, day_branch = chart_components['day']
    month_stem, month_branch = chart_components['month']
    year_stem, year_branch = chart_components['year']

    return build_chart(
        date_value,
        time_value,
        hour_stem,
        hour_branch,
        day_stem,
        day_branch,
        month_stem,
        month_branch,
        year_stem,
        year_branch,
        lang=lang,
    )


async def _resolve_four_pillars_location(
    payload: FourPillarsRequest,
) -> tuple[LocationInput, ResolvedCity | None]:
    city_name = (payload.city or '').strip()
    country_name = (payload.country or '').strip()
    has_city_fields = bool(city_name or country_name)

    if payload.location is not None and has_city_fields:
        raise ValueError('Provide either location or city/country, not both.')
    if payload.location is not None:
        return payload.location, None
    if not has_city_fields:
        raise ValueError('Provide either location or city/country.')
    if not city_name or not country_name:
        raise ValueError(
            'Both city and country are required when using city/country input.'
        )
    return await _resolve_city_location(city_name, country_name)


def _extract_hidden_stem_char(entry: str) -> str:
    token = entry.strip()
    if not token:
        raise ValueError('Hidden stem entry cannot be empty.')
    parts = token.split()
    return parts[-1]


@lru_cache(maxsize=1)
def _load_hidden_stems_lookup() -> dict[str, list[str]]:
    csv_path = MAPPINGS_DIR / 'hidden-stems.csv'
    if not csv_path.exists():
        raise RuntimeError(f'Hidden stems lookup not found: {csv_path}')

    lookup: dict[str, list[str]] = {}
    with csv_path.open('r', encoding='utf-8', newline='') as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            branch_col = (row.get('Earthly Branch') or '').strip()
            hidden_col = (
                row.get('Hidden Stems (Main, Middle, Residual Qi)') or ''
            ).strip()
            if not branch_col or not hidden_col:
                continue
            branch_char = branch_col[-1]
            entries = [item for item in hidden_col.split(',') if item.strip()]
            lookup[branch_char] = [_extract_hidden_stem_char(item) for item in entries]

    if not lookup:
        raise RuntimeError('Hidden stems lookup is empty.')
    return lookup


def _validate_pillar_text(pillar_text: str, field_name: str) -> tuple[str, str]:
    value = pillar_text.strip()
    if len(value) != 2:
        raise ValueError(f'{field_name} must be exactly 2 Chinese characters.')
    stem_char, branch_char = value[0], value[1]
    if stem_char not in STEMS:
        raise ValueError(f'Invalid stem in {field_name}: {stem_char}')
    if branch_char not in BRANCHES:
        raise ValueError(f'Invalid branch in {field_name}: {branch_char}')
    return stem_char, branch_char


def _build_hidden_stems_result(
    payload: HiddenStemsRequest,
) -> dict[str, dict[str, Any]]:
    lookup = _load_hidden_stems_lookup()
    pillar_inputs = {
        'year': payload.year_pillar,
        'month': payload.month_pillar,
        'day': payload.day_pillar,
        'hour': payload.hour_pillar,
    }
    qi_types = ['main', 'middle', 'residual']
    result: dict[str, dict[str, Any]] = {}
    for pillar_name, pillar_text in pillar_inputs.items():
        stem_char, branch_char = _validate_pillar_text(
            pillar_text,
            field_name=f'{pillar_name}_pillar',
        )
        hidden_chars = lookup.get(branch_char)
        if hidden_chars is None:
            raise ValueError(f'No hidden stem mapping found for branch: {branch_char}')
        enriched: list[dict[str, Any]] = []
        for i, h_char in enumerate(hidden_chars):
            stem_info = STEMS.get(h_char)
            if stem_info is None:
                raise ValueError(f'Unknown stem character in hidden stems: {h_char}')
            enriched.append(
                {
                    'char': h_char,
                    'element': stem_info['element'],
                    'polarity': stem_info['polarity'],
                    'qi_type': qi_types[i] if i < len(qi_types) else 'residual',
                }
            )
        result[pillar_name] = {
            'pillar': f'{stem_char}{branch_char}',
            'branch': branch_char,
            'hidden_stems': enriched,
        }
    return result


def _stem_profile(stem_char: str) -> tuple[tuple[int, int, int, int, int], int, int]:
    stem_info = STEMS.get(stem_char)
    if stem_info is None:
        raise ValueError(f'Unknown stem in evolution input: {stem_char}')

    element_name_raw = stem_info.get('element')
    element_name = element_name_raw.strip().lower()
    element_index = ELEMENT_INDEX_BY_NAME.get(element_name)
    if element_index is None:
        raise ValueError(f'Unknown element for stem {stem_char}: {element_name_raw}')

    polarity_raw = stem_info.get('polarity')
    polarity_name = polarity_raw.strip().lower()
    if polarity_name == 'yang':
        polarity = 1
    elif polarity_name == 'yin':
        polarity = 0
    else:
        raise ValueError(f'Unknown polarity for stem {stem_char}: {polarity_raw}')

    one_hot = [0, 0, 0, 0, 0]
    one_hot[element_index] = 1
    one_hot_tuple = cast(tuple[int, int, int, int, int], tuple(one_hot))
    return one_hot_tuple, element_index, polarity


def _build_evolution_input_from_four_pillars(
    *,
    four_pillars: dict[str, Any],
    hidden_stems: dict[str, dict[str, Any]],
) -> EvolutionInput:
    branch_ids: list[int] = []
    base_elements: list[tuple[int, int, int, int, int]] = []
    polarities: list[int] = []
    hierarchy_levels: list[int] = []
    positions: list[int] = []
    masks: list[int] = []
    vitality_stages: list[int] = []
    day_master_index = -1
    entity_index = 0

    for pillar_position, pillar_name in enumerate(
        ('year', 'month', 'day', 'hour'), start=1
    ):
        stem_char = _pillar_component_from_four_pillars(
            four_pillars=four_pillars,
            pillar_name=pillar_name,
            component_name='stem',
        )
        branch_char = _pillar_component_from_four_pillars(
            four_pillars=four_pillars,
            pillar_name=pillar_name,
            component_name='branch',
        )
        branch_id = BRANCH_ID_BY_CHAR.get(branch_char)
        if branch_id is None:
            raise ValueError(f'Unknown branch in evolution input: {branch_char}')
        branch_ids.append(branch_id)

        stem_one_hot, stem_element_index, stem_polarity = _stem_profile(stem_char)
        base_elements.append(stem_one_hot)
        polarities.append(stem_polarity)
        hierarchy_levels.append(4)
        positions.append(pillar_position)
        masks.append(1)
        vitality_stages.append(
            life_stage_anchor(stem_element_index, stem_polarity, branch_id)
        )

        if pillar_name == 'day':
            day_master_index = entity_index
        entity_index += 1

        pillar_hidden_raw = hidden_stems.get(pillar_name)
        if not isinstance(pillar_hidden_raw, dict):
            continue
        pillar_hidden = pillar_hidden_raw
        hidden_entries_raw = pillar_hidden.get('hidden_stems')
        if not isinstance(hidden_entries_raw, list):
            continue
        hidden_entries = cast(list[object], hidden_entries_raw)
        for hidden_entry_raw in hidden_entries:
            if not isinstance(hidden_entry_raw, dict):
                continue
            hidden_entry = cast(dict[str, Any], hidden_entry_raw)
            hidden_char_raw = hidden_entry.get('char')
            if not isinstance(hidden_char_raw, str) or not hidden_char_raw:
                continue
            qi_type_raw = hidden_entry.get('qi_type')
            qi_type = (
                qi_type_raw.strip().lower()
                if isinstance(qi_type_raw, str)
                else 'residual'
            )
            hierarchy = QI_HIERARCHY_BY_TYPE.get(qi_type, 1)

            hidden_one_hot, hidden_element_index, hidden_polarity = _stem_profile(
                hidden_char_raw
            )
            base_elements.append(hidden_one_hot)
            polarities.append(hidden_polarity)
            hierarchy_levels.append(hierarchy)
            positions.append(pillar_position)
            masks.append(1)
            vitality_stages.append(
                life_stage_anchor(hidden_element_index, hidden_polarity, branch_id)
            )
            entity_index += 1

    if len(branch_ids) != 4:
        raise ValueError('Evolution input requires four branch ids.')
    if day_master_index < 0:
        raise ValueError('Evolution input requires a valid Day Master index.')
    branch_ids_tuple: tuple[int, int, int, int] = (
        branch_ids[0],
        branch_ids[1],
        branch_ids[2],
        branch_ids[3],
    )

    return EvolutionInput(
        branch_ids=branch_ids_tuple,
        base_elements=tuple(base_elements),
        polarities=tuple(polarities),
        hierarchy_levels=tuple(hierarchy_levels),
        positions=tuple(positions),
        masks=tuple(masks),
        vitality_stages=tuple(vitality_stages),
        day_master_index=day_master_index,
    )


def _ensure_evolution_basins(payload: dict[str, Any]) -> dict[str, Any]:
    basins_raw = payload.get('basins')
    if isinstance(basins_raw, list) and basins_raw:
        return payload

    input_shape_raw = payload.get('input_shape')
    if not isinstance(input_shape_raw, dict):
        return payload
    input_shape = cast(dict[str, Any], input_shape_raw)
    base_elements_raw = input_shape.get('base_elements')
    if isinstance(base_elements_raw, list):
        base_elements: list[list[int]] = []
        for row_raw in cast(list[object], base_elements_raw):
            if not isinstance(row_raw, list):
                continue
            row_values = cast(list[object], row_raw)
            normalized_row: list[int] = []
            for value_raw in row_values[:5]:
                if isinstance(value_raw, bool):
                    normalized_row.append(int(value_raw))
                elif isinstance(value_raw, int):
                    normalized_row.append(value_raw)
                elif isinstance(value_raw, float):
                    normalized_row.append(int(value_raw))
                else:
                    normalized_row.append(0)
            while len(normalized_row) < 5:
                normalized_row.append(0)
            base_elements.append(normalized_row)
    else:
        base_elements = []
    entity_count = len(base_elements)

    payload['basins'] = [
        {
            'basin_id': 0,
            'mass': 1.0,
            'mode': 'Standard',
            'chart_temperature': 0.0,
            'chart_saturation': 0.0,
            'motifs': {
                'chains': [],
                'loops': [],
                'pulses': [],
                'cascades': [],
                'absences': [],
                'bottlenecks': [],
            },
            'map_total_energy': 0.0,
            'map_switches': [0 for _ in range(RULE_COUNT)],
            'map_omegas': [0.5 for _ in range(RULE_COUNT)],
            'map_effective_elements': base_elements,
            'map_effective_ten_gods': [
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 0] for _ in range(entity_count)
            ],
        }
    ]
    payload['noise_probability'] = 0.0
    return payload


def _resolve_evolution_seed(seed_mode: str) -> int:
    normalized_mode = seed_mode.strip().lower()
    if normalized_mode == 'fixed_42':
        return EVOLUTION_FIXED_SEED
    if normalized_mode == 'random':
        return secrets.randbelow(2_147_483_648)
    raise ValueError("seed_mode must be 'fixed_42' or 'random'.")


def _json_compatible(value: Any) -> Any:
    if isinstance(value, tuple):
        tuple_values = cast(tuple[Any, ...], value)
        return [_json_compatible(item) for item in tuple_values]
    if isinstance(value, list):
        list_values = cast(list[Any], value)
        return [_json_compatible(item) for item in list_values]
    if isinstance(value, dict):
        value_dict = cast(dict[object, Any], value)
        normalized: dict[str, Any] = {}
        for raw_key, item in value_dict.items():
            normalized[str(raw_key)] = _json_compatible(item)
        return normalized
    return value


@dataclass(frozen=True)
class ResolvedEvolutionControls:
    flux_threshold: float
    particles: int
    temperature_steps: int
    sweeps_per_step: int
    dbscan_eps: float
    dbscan_min_samples: int
    seed_mode: str
    conventions: ConventionInput
    birth_time_uncertainty_seconds: float | None
    scalar_constants: dict[str, float]
    vector_matrix_constants: dict[str, Any]


def _control_payload(
    *,
    value: Any,
    ui_label: str,
    ui_type: str,
    min_value: float | int | None = None,
    max_value: float | int | None = None,
    distribution: str | None = None,
    options: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'value': _json_compatible(value),
        'ui_label': ui_label,
        'ui_type': ui_type,
    }
    if min_value is not None:
        payload['min'] = min_value
    if max_value is not None:
        payload['max'] = max_value
    if distribution is not None:
        payload['distribution'] = distribution
    if options is not None:
        payload['options'] = options
    return payload


def _default_evolution_scalar_constants() -> dict[str, float]:
    return {
        'SAME_POLARITY_MULTIPLIER': float(
            evolution_primitives.SAME_POLARITY_MULTIPLIER
        ),
        'DIFF_POLARITY_MULTIPLIER': float(
            evolution_primitives.DIFF_POLARITY_MULTIPLIER
        ),
        'OMEGA_MIN_R': float(evolution_primitives.OMEGA_MIN_R),
        'TAU_R': float(evolution_primitives.TAU_R),
        'TAU_STD': float(evolution_primitives.TAU_STD),
        'TAU_FOLLOW': float(evolution_primitives.TAU_FOLLOW),
        'DELTA_CLASH': float(evolution_primitives.DELTA_CLASH),
        'DELTA_PUN': float(evolution_primitives.DELTA_PUN),
        'DELTA_V_R': float(evolution_primitives.DELTA_V_R),
        'OMEGA_SEASON': float(evolution_primitives.OMEGA_SEASON),
        'LAMBDA_INTRA': float(evolution_primitives.LAMBDA_INTRA),
        'LAMBDA_INTER': float(evolution_primitives.LAMBDA_INTER),
        'LAMBDA_V': float(evolution_primitives.LAMBDA_V),
        'LAMBDA_CLIM': float(evolution_primitives.LAMBDA_CLIM),
        'LAMBDA_DOM': float(evolution_primitives.LAMBDA_DOM),
        'LAMBDA_MODE': float(evolution_primitives.LAMBDA_MODE),
        'LAMBDA_ACT': float(evolution_primitives.LAMBDA_ACT),
        'LAMBDA_CLASH': float(evolution_primitives.LAMBDA_CLASH),
        'LAMBDA_SCATTER': float(evolution_primitives.LAMBDA_SCATTER),
        'LAMBDA_FRAME': float(evolution_primitives.LAMBDA_FRAME),
        'LAMBDA_PUN': float(evolution_primitives.LAMBDA_PUN),
        'LAMBDA_COR': float(evolution_primitives.LAMBDA_COR),
        'LAMBDA_CROSS': float(evolution_primitives.LAMBDA_CROSS),
        'active_edge_fraction_of_max_flux': float(
            evolution_postprocess.ACTIVE_EDGE_FRACTION_OF_MAX_FLUX
        ),
        'pulse_balance_ratio_min': float(evolution_postprocess.PULSE_BALANCE_RATIO_MIN),
        'pulse_balance_ratio_max': float(evolution_postprocess.PULSE_BALANCE_RATIO_MAX),
        'cascade_gain_min': float(evolution_postprocess.CASCADE_GAIN_MIN),
        'bottleneck_quantile': float(evolution_postprocess.BOTTLENECK_QUANTILE),
    }


def _default_evolution_vector_matrix_constants() -> dict[str, Any]:
    return {
        'WUXING_MATRIX': evolution_primitives.WUXING_MATRIX,
        'DOMAIN_RESONANCE_MATRIX': evolution_primitives.DOMAIN_RESONANCE_MATRIX,
        'STAGE_AMPLITUDE_BY_STAGE': evolution_primitives.STAGE_AMPLITUDE_BY_STAGE,
        'PARTIAL_STATE_WEIGHT_BY_S': evolution_primitives.PARTIAL_STATE_WEIGHT_BY_S,
        'PROXIMITY_WEIGHT_BY_GAP': evolution_primitives.PROXIMITY_WEIGHT_BY_GAP,
        'CLUSTER_ALPHA': float(evolution_primitives.CLUSTER_ALPHA),
        'CLUSTER_BETA': float(evolution_primitives.CLUSTER_BETA),
        'CLUSTER_GAMMA': float(evolution_primitives.CLUSTER_GAMMA),
    }


def _controls_root(controls: dict[str, Any] | None) -> dict[str, Any] | None:
    if controls is None:
        return None
    if 'controls' in controls and isinstance(controls['controls'], dict):
        return cast(dict[str, Any], controls['controls'])
    return controls


def _control_entry_value(entry: Any) -> Any:
    if isinstance(entry, dict):
        mapping = cast(dict[str, Any], entry)
        if 'value' in mapping:
            return mapping['value']
        return mapping
    return entry


def _lookup_control_value(
    controls: dict[str, Any] | None,
    group_path: tuple[str, ...],
    key: str,
) -> Any | None:
    controls_map = _controls_root(controls)
    if controls_map is None:
        return None

    if key in controls_map:
        return _control_entry_value(controls_map[key])

    current: Any = controls_map
    for path_key in group_path:
        if not isinstance(current, dict):
            return None
        current = cast(dict[str, Any], current).get(path_key)
    if not isinstance(current, dict):
        return None

    section = cast(dict[str, Any], current)
    if key not in section:
        return None
    return _control_entry_value(section[key])


def _coerce_float(value: Any, key: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f'{key} must be numeric.')
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError as exc:
            raise ValueError(f'{key} must be numeric.') from exc
    else:
        raise ValueError(f'{key} must be numeric.')
    if number != number or number in (float('inf'), float('-inf')):
        raise ValueError(f'{key} must be finite.')
    return number


def _coerce_int(value: Any, key: str) -> int:
    number = _coerce_float(value, key)
    if not number.is_integer():
        raise ValueError(f'{key} must be an integer.')
    return int(number)


def _coerce_choice(value: Any, key: str, options: tuple[str, ...]) -> str:
    if not isinstance(value, str):
        raise ValueError(f'{key} must be one of: {", ".join(options)}.')
    normalized = value.strip()
    if normalized not in options:
        raise ValueError(f'{key} must be one of: {", ".join(options)}.')
    return normalized


def _coerce_float_vector(value: Any, key: str, expected_length: int) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f'{key} must be a sequence with length {expected_length}.')
    sequence = list(cast(list[Any] | tuple[Any, ...], value))
    if len(sequence) != expected_length:
        raise ValueError(f'{key} must have length {expected_length}.')
    return tuple(_coerce_float(item, key) for item in sequence)


def _coerce_float_matrix(
    value: Any,
    key: str,
    expected_rows: int,
    expected_cols: int,
) -> tuple[tuple[float, ...], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(
            f'{key} must be a matrix with shape {expected_rows}x{expected_cols}.'
        )
    rows = list(cast(list[Any] | tuple[Any, ...], value))
    if len(rows) != expected_rows:
        raise ValueError(
            f'{key} must be a matrix with shape {expected_rows}x{expected_cols}.'
        )
    normalized_rows: list[tuple[float, ...]] = []
    for row in rows:
        if not isinstance(row, (list, tuple)):
            raise ValueError(
                f'{key} must be a matrix with shape {expected_rows}x{expected_cols}.'
            )
        row_items = list(cast(list[Any] | tuple[Any, ...], row))
        if len(row_items) != expected_cols:
            raise ValueError(
                f'{key} must be a matrix with shape {expected_rows}x{expected_cols}.'
            )
        normalized_rows.append(tuple(_coerce_float(item, key) for item in row_items))
    return tuple(normalized_rows)


def _resolve_evolution_controls(
    payload: EvolutionExplorerRequest,
) -> ResolvedEvolutionControls:
    flux_threshold = max(0.0, float(payload.flux_threshold))
    particles = int(payload.particles)
    temperature_steps = int(payload.temperature_steps)
    sweeps_per_step = int(payload.sweeps_per_step)
    dbscan_eps = float(payload.dbscan_eps)
    dbscan_min_samples = int(payload.dbscan_min_samples)
    seed_mode = payload.seed_mode
    zi_convention = payload.conventions.zi_convention
    hour_basis = payload.conventions.hour_basis
    day_boundary_basis = payload.conventions.day_boundary_basis
    birth_time_uncertainty_seconds = payload.birth_time_uncertainty_seconds

    scalar_constants = _default_evolution_scalar_constants()
    vector_matrix_constants = _default_evolution_vector_matrix_constants()

    controls = payload.controls
    flux_threshold_override = _lookup_control_value(
        controls, ('main_view_controls',), 'flux_threshold'
    )
    if flux_threshold_override is not None:
        flux_threshold = max(0.0, _coerce_float(flux_threshold_override, 'flux_threshold'))

    particles_override = _lookup_control_value(
        controls, ('main_view_controls',), 'particles'
    )
    if particles_override is not None:
        particles = _coerce_int(particles_override, 'particles')

    temperature_steps_override = _lookup_control_value(
        controls, ('main_view_controls',), 'temperature_steps'
    )
    if temperature_steps_override is not None:
        temperature_steps = _coerce_int(temperature_steps_override, 'temperature_steps')

    sweeps_override = _lookup_control_value(
        controls, ('main_view_controls',), 'sweeps_per_step'
    )
    if sweeps_override is not None:
        sweeps_per_step = _coerce_int(sweeps_override, 'sweeps_per_step')

    dbscan_eps_override = _lookup_control_value(controls, ('main_view_controls',), 'dbscan_eps')
    if dbscan_eps_override is not None:
        dbscan_eps = _coerce_float(dbscan_eps_override, 'dbscan_eps')

    dbscan_min_samples_override = _lookup_control_value(
        controls, ('main_view_controls',), 'dbscan_min_samples'
    )
    if dbscan_min_samples_override is not None:
        dbscan_min_samples = _coerce_int(
            dbscan_min_samples_override, 'dbscan_min_samples'
        )

    seed_mode_override = _lookup_control_value(controls, ('main_view_controls',), 'seed_mode')
    if seed_mode_override is not None:
        seed_mode = _coerce_choice(
            seed_mode_override, 'seed_mode', ('fixed_42', 'random')
        )

    zi_override = _lookup_control_value(
        controls, ('input_convention_controls',), 'zi_convention'
    )
    if zi_override is not None:
        zi_convention = _coerce_choice(
            zi_override,
            'zi_convention',
            ('split_midnight', 'whole_zi_23'),
        )

    hour_override = _lookup_control_value(
        controls, ('input_convention_controls',), 'hour_basis'
    )
    if hour_override is not None:
        hour_basis = _coerce_choice(hour_override, 'hour_basis', ('true_solar', 'civil'))

    day_boundary_override = _lookup_control_value(
        controls, ('input_convention_controls',), 'day_boundary_basis'
    )
    if day_boundary_override is not None:
        day_boundary_basis = _coerce_choice(
            day_boundary_override, 'day_boundary_basis', ('true_solar', 'civil')
        )

    uncertainty_override = _lookup_control_value(
        controls,
        ('input_convention_controls',),
        'birth_time_uncertainty_seconds',
    )
    if uncertainty_override is not None:
        birth_time_uncertainty_seconds = _coerce_float(
            uncertainty_override, 'birth_time_uncertainty_seconds'
        )

    for key in tuple(scalar_constants.keys()):
        override = _lookup_control_value(
            controls, ('evolution_reading_controls', 'scalar_constants'), key
        )
        if override is not None:
            scalar_constants[key] = _coerce_float(override, key)

    wuxing_override = _lookup_control_value(
        controls, ('evolution_reading_controls', 'vector_matrix_constants'), 'WUXING_MATRIX'
    )
    if wuxing_override is not None:
        vector_matrix_constants['WUXING_MATRIX'] = _coerce_float_matrix(
            wuxing_override, 'WUXING_MATRIX', expected_rows=5, expected_cols=5
        )

    domain_override = _lookup_control_value(
        controls,
        ('evolution_reading_controls', 'vector_matrix_constants'),
        'DOMAIN_RESONANCE_MATRIX',
    )
    if domain_override is not None:
        vector_matrix_constants['DOMAIN_RESONANCE_MATRIX'] = _coerce_float_matrix(
            domain_override,
            'DOMAIN_RESONANCE_MATRIX',
            expected_rows=4,
            expected_cols=5,
        )

    stage_override = _lookup_control_value(
        controls,
        ('evolution_reading_controls', 'vector_matrix_constants'),
        'STAGE_AMPLITUDE_BY_STAGE',
    )
    if stage_override is not None:
        vector_matrix_constants['STAGE_AMPLITUDE_BY_STAGE'] = _coerce_float_vector(
            stage_override, 'STAGE_AMPLITUDE_BY_STAGE', expected_length=12
        )

    partial_override = _lookup_control_value(
        controls,
        ('evolution_reading_controls', 'vector_matrix_constants'),
        'PARTIAL_STATE_WEIGHT_BY_S',
    )
    if partial_override is not None:
        vector_matrix_constants['PARTIAL_STATE_WEIGHT_BY_S'] = _coerce_float_vector(
            partial_override, 'PARTIAL_STATE_WEIGHT_BY_S', expected_length=4
        )

    proximity_override = _lookup_control_value(
        controls,
        ('evolution_reading_controls', 'vector_matrix_constants'),
        'PROXIMITY_WEIGHT_BY_GAP',
    )
    if proximity_override is not None:
        vector_matrix_constants['PROXIMITY_WEIGHT_BY_GAP'] = _coerce_float_vector(
            proximity_override, 'PROXIMITY_WEIGHT_BY_GAP', expected_length=3
        )

    cluster_alpha_override = _lookup_control_value(
        controls,
        ('evolution_reading_controls', 'vector_matrix_constants'),
        'CLUSTER_ALPHA',
    )
    if cluster_alpha_override is not None:
        vector_matrix_constants['CLUSTER_ALPHA'] = _coerce_float(
            cluster_alpha_override, 'CLUSTER_ALPHA'
        )

    cluster_beta_override = _lookup_control_value(
        controls,
        ('evolution_reading_controls', 'vector_matrix_constants'),
        'CLUSTER_BETA',
    )
    if cluster_beta_override is not None:
        vector_matrix_constants['CLUSTER_BETA'] = _coerce_float(
            cluster_beta_override, 'CLUSTER_BETA'
        )

    cluster_gamma_override = _lookup_control_value(
        controls,
        ('evolution_reading_controls', 'vector_matrix_constants'),
        'CLUSTER_GAMMA',
    )
    if cluster_gamma_override is not None:
        vector_matrix_constants['CLUSTER_GAMMA'] = _coerce_float(
            cluster_gamma_override, 'CLUSTER_GAMMA'
        )

    if particles <= 0:
        raise ValueError('particles must be positive.')
    if temperature_steps <= 0:
        raise ValueError('temperature_steps must be positive.')
    if sweeps_per_step <= 0:
        raise ValueError('sweeps_per_step must be positive.')
    if dbscan_eps <= 0.0:
        raise ValueError('dbscan_eps must be positive.')
    if dbscan_min_samples <= 0:
        raise ValueError('dbscan_min_samples must be positive.')
    if birth_time_uncertainty_seconds is not None and birth_time_uncertainty_seconds < 0.0:
        raise ValueError('birth_time_uncertainty_seconds must be non-negative.')
    if scalar_constants['pulse_balance_ratio_max'] < scalar_constants['pulse_balance_ratio_min']:
        raise ValueError(
            'pulse_balance_ratio_max must be greater than or equal to pulse_balance_ratio_min.'
        )
    if not 0.0 <= scalar_constants['bottleneck_quantile'] <= 1.0:
        raise ValueError('bottleneck_quantile must be between 0.0 and 1.0.')

    conventions = ConventionInput(
        zi_convention=zi_convention,
        hour_basis=hour_basis,
        day_boundary_basis=day_boundary_basis,
    )
    return ResolvedEvolutionControls(
        flux_threshold=flux_threshold,
        particles=particles,
        temperature_steps=temperature_steps,
        sweeps_per_step=sweeps_per_step,
        dbscan_eps=dbscan_eps,
        dbscan_min_samples=dbscan_min_samples,
        seed_mode=seed_mode,
        conventions=conventions,
        birth_time_uncertainty_seconds=birth_time_uncertainty_seconds,
        scalar_constants=scalar_constants,
        vector_matrix_constants=vector_matrix_constants,
    )


_EVOLUTION_SCALAR_PATCH_TARGETS: dict[str, tuple[tuple[object, str], ...]] = {
    'SAME_POLARITY_MULTIPLIER': (
        (evolution_primitives, 'SAME_POLARITY_MULTIPLIER'),
    ),
    'DIFF_POLARITY_MULTIPLIER': (
        (evolution_primitives, 'DIFF_POLARITY_MULTIPLIER'),
    ),
    'OMEGA_MIN_R': (
        (evolution_primitives, 'OMEGA_MIN_R'),
        (evolution_inference, 'OMEGA_MIN_R'),
        (evolution_postprocess, 'OMEGA_MIN_R'),
    ),
    'TAU_R': (
        (evolution_primitives, 'TAU_R'),
        (evolution_energy, 'TAU_R'),
    ),
    'TAU_STD': (
        (evolution_primitives, 'TAU_STD'),
        (evolution_energy, 'TAU_STD'),
    ),
    'TAU_FOLLOW': (
        (evolution_primitives, 'TAU_FOLLOW'),
        (evolution_energy, 'TAU_FOLLOW'),
    ),
    'DELTA_CLASH': (
        (evolution_primitives, 'DELTA_CLASH'),
        (evolution_mechanics, 'DELTA_CLASH'),
    ),
    'DELTA_PUN': (
        (evolution_primitives, 'DELTA_PUN'),
        (evolution_mechanics, 'DELTA_PUN'),
    ),
    'DELTA_V_R': (
        (evolution_primitives, 'DELTA_V_R'),
        (evolution_energy, 'DELTA_V_R'),
    ),
    'OMEGA_SEASON': (
        (evolution_primitives, 'OMEGA_SEASON'),
        (evolution_energy, 'OMEGA_SEASON'),
    ),
    'LAMBDA_INTRA': (
        (evolution_primitives, 'LAMBDA_INTRA'),
        (evolution_energy, 'LAMBDA_INTRA'),
    ),
    'LAMBDA_INTER': (
        (evolution_primitives, 'LAMBDA_INTER'),
        (evolution_energy, 'LAMBDA_INTER'),
    ),
    'LAMBDA_V': (
        (evolution_primitives, 'LAMBDA_V'),
        (evolution_energy, 'LAMBDA_V'),
    ),
    'LAMBDA_CLIM': (
        (evolution_primitives, 'LAMBDA_CLIM'),
        (evolution_energy, 'LAMBDA_CLIM'),
    ),
    'LAMBDA_DOM': (
        (evolution_primitives, 'LAMBDA_DOM'),
        (evolution_energy, 'LAMBDA_DOM'),
    ),
    'LAMBDA_MODE': (
        (evolution_primitives, 'LAMBDA_MODE'),
        (evolution_energy, 'LAMBDA_MODE'),
    ),
    'LAMBDA_ACT': (
        (evolution_primitives, 'LAMBDA_ACT'),
        (evolution_energy, 'LAMBDA_ACT'),
    ),
    'LAMBDA_CLASH': (
        (evolution_primitives, 'LAMBDA_CLASH'),
        (evolution_energy, 'LAMBDA_CLASH'),
    ),
    'LAMBDA_SCATTER': (
        (evolution_primitives, 'LAMBDA_SCATTER'),
        (evolution_energy, 'LAMBDA_SCATTER'),
    ),
    'LAMBDA_FRAME': (
        (evolution_primitives, 'LAMBDA_FRAME'),
        (evolution_energy, 'LAMBDA_FRAME'),
    ),
    'LAMBDA_PUN': (
        (evolution_primitives, 'LAMBDA_PUN'),
        (evolution_energy, 'LAMBDA_PUN'),
    ),
    'LAMBDA_COR': (
        (evolution_primitives, 'LAMBDA_COR'),
        (evolution_energy, 'LAMBDA_COR'),
    ),
    'LAMBDA_CROSS': (
        (evolution_primitives, 'LAMBDA_CROSS'),
        (evolution_energy, 'LAMBDA_CROSS'),
    ),
    'active_edge_fraction_of_max_flux': (
        (evolution_postprocess, 'ACTIVE_EDGE_FRACTION_OF_MAX_FLUX'),
    ),
    'pulse_balance_ratio_min': (
        (evolution_postprocess, 'PULSE_BALANCE_RATIO_MIN'),
    ),
    'pulse_balance_ratio_max': (
        (evolution_postprocess, 'PULSE_BALANCE_RATIO_MAX'),
    ),
    'cascade_gain_min': (
        (evolution_postprocess, 'CASCADE_GAIN_MIN'),
    ),
    'bottleneck_quantile': (
        (evolution_postprocess, 'BOTTLENECK_QUANTILE'),
    ),
}

_EVOLUTION_VECTOR_MATRIX_PATCH_TARGETS: dict[str, tuple[tuple[object, str], ...]] = {
    'WUXING_MATRIX': ((evolution_primitives, 'WUXING_MATRIX'),),
    'DOMAIN_RESONANCE_MATRIX': ((evolution_primitives, 'DOMAIN_RESONANCE_MATRIX'),),
    'STAGE_AMPLITUDE_BY_STAGE': ((evolution_primitives, 'STAGE_AMPLITUDE_BY_STAGE'),),
    'PARTIAL_STATE_WEIGHT_BY_S': ((evolution_primitives, 'PARTIAL_STATE_WEIGHT_BY_S'),),
    'PROXIMITY_WEIGHT_BY_GAP': ((evolution_primitives, 'PROXIMITY_WEIGHT_BY_GAP'),),
    'CLUSTER_ALPHA': (
        (evolution_primitives, 'CLUSTER_ALPHA'),
        (evolution_postprocess, 'CLUSTER_ALPHA'),
    ),
    'CLUSTER_BETA': (
        (evolution_primitives, 'CLUSTER_BETA'),
        (evolution_postprocess, 'CLUSTER_BETA'),
    ),
    'CLUSTER_GAMMA': (
        (evolution_primitives, 'CLUSTER_GAMMA'),
        (evolution_postprocess, 'CLUSTER_GAMMA'),
    ),
}


@contextmanager
def _temporary_evolution_control_overrides(
    scalar_constants: dict[str, float],
    vector_matrix_constants: dict[str, Any],
):
    original_values: list[tuple[object, str, Any]] = []
    with EVOLUTION_CONSTANT_PATCH_LOCK:
        try:
            for key, value in scalar_constants.items():
                for target_module, target_name in _EVOLUTION_SCALAR_PATCH_TARGETS.get(
                    key, ()
                ):
                    original_values.append(
                        (target_module, target_name, getattr(target_module, target_name))
                    )
                    setattr(target_module, target_name, value)

            for key, value in vector_matrix_constants.items():
                for target_module, target_name in _EVOLUTION_VECTOR_MATRIX_PATCH_TARGETS.get(
                    key, ()
                ):
                    original_values.append(
                        (target_module, target_name, getattr(target_module, target_name))
                    )
                    setattr(target_module, target_name, value)
            yield
        finally:
            for target_module, target_name, original in reversed(original_values):
                setattr(target_module, target_name, original)

def _build_evolution_controls_payload(
    *,
    flux_threshold: float,
    particles: int,
    temperature_steps: int,
    sweeps_per_step: int,
    dbscan_eps: float,
    dbscan_min_samples: int,
    seed_mode: str,
    conventions: ConventionInput,
    birth_time_uncertainty_seconds: float | None,
    scalar_constants: dict[str, float],
    vector_matrix_constants: dict[str, Any],
) -> dict[str, Any]:
    main_view_controls = {
        'flux_threshold': _control_payload(
            value=flux_threshold,
            ui_label='Min |F(i→j)| Display Threshold',
            ui_type='slider',
            min_value=0.0,
            distribution='linear',
        ),
        'particles': _control_payload(
            value=particles,
            ui_label='Particles',
            ui_type='slider',
            min_value=8,
            max_value=4096,
            distribution='discrete_log_uniform',
        ),
        'temperature_steps': _control_payload(
            value=temperature_steps,
            ui_label='Temperature Steps',
            ui_type='slider',
            min_value=1,
            max_value=200,
            distribution='discrete_log_uniform',
        ),
        'sweeps_per_step': _control_payload(
            value=sweeps_per_step,
            ui_label='Sweeps Per Step',
            ui_type='slider',
            min_value=1,
            max_value=20,
            distribution='discrete_log_uniform',
        ),
        'dbscan_eps': _control_payload(
            value=dbscan_eps,
            ui_label='Basin Clustering Radius',
            ui_type='slider',
            min_value=0.01,
            max_value=1.0,
            distribution='log_uniform',
        ),
        'dbscan_min_samples': _control_payload(
            value=dbscan_min_samples,
            ui_label='Basin Clustering Min Samples',
            ui_type='slider',
            min_value=1,
            max_value=64,
            distribution='discrete_log_uniform',
        ),
        'seed_mode': _control_payload(
            value=seed_mode,
            ui_label='Seed Mode',
            ui_type='toggle',
            options=['fixed_42', 'random'],
        ),
    }

    evolution_scalar_controls = {
        'SAME_POLARITY_MULTIPLIER': _control_payload(
            value=scalar_constants['SAME_POLARITY_MULTIPLIER'],
            ui_label='Yin-Yang Same-Polarity Resonance',
            ui_type='slider',
            min_value=0.8,
            max_value=1.6,
            distribution='log_normal',
        ),
        'DIFF_POLARITY_MULTIPLIER': _control_payload(
            value=scalar_constants['DIFF_POLARITY_MULTIPLIER'],
            ui_label='Yin-Yang Cross-Polarity Resonance',
            ui_type='slider',
            min_value=0.6,
            max_value=1.4,
            distribution='log_normal',
        ),
        'OMEGA_MIN_R': _control_payload(
            value=scalar_constants['OMEGA_MIN_R'],
            ui_label='Minimum Rule Qi Activation',
            ui_type='slider',
            min_value=0.1,
            max_value=2.0,
            distribution='log_uniform',
        ),
        'TAU_R': _control_payload(
            value=scalar_constants['TAU_R'],
            ui_label='Rule Support Gate',
            ui_type='slider',
            min_value=0.1,
            max_value=1.0,
            distribution='beta',
        ),
        'TAU_STD': _control_payload(
            value=scalar_constants['TAU_STD'],
            ui_label='Standard Structure Tolerance',
            ui_type='slider',
            min_value=0.0,
            max_value=1.0,
            distribution='beta',
        ),
        'TAU_FOLLOW': _control_payload(
            value=scalar_constants['TAU_FOLLOW'],
            ui_label='Follow-Pattern Tolerance',
            ui_type='slider',
            min_value=0.0,
            max_value=1.0,
            distribution='beta',
        ),
        'DELTA_CLASH': _control_payload(
            value=scalar_constants['DELTA_CLASH'],
            ui_label='Clash Damage Intensity',
            ui_type='slider',
            min_value=0.0,
            max_value=1.0,
            distribution='log_normal',
        ),
        'DELTA_PUN': _control_payload(
            value=scalar_constants['DELTA_PUN'],
            ui_label='Punishment Damage Intensity',
            ui_type='slider',
            min_value=0.0,
            max_value=0.8,
            distribution='log_normal',
        ),
        'DELTA_V_R': _control_payload(
            value=scalar_constants['DELTA_V_R'],
            ui_label='Clash Vitality Displacement',
            ui_type='slider',
            min_value=0.0,
            max_value=1.0,
            distribution='log_normal',
        ),
        'OMEGA_SEASON': _control_payload(
            value=scalar_constants['OMEGA_SEASON'],
            ui_label='Seasonal Qi Boost',
            ui_type='slider',
            min_value=0.0,
            max_value=2.0,
            distribution='beta',
        ),
        'LAMBDA_INTRA': _control_payload(
            value=scalar_constants['LAMBDA_INTRA'],
            ui_label='Intra-Pillar Coherence Weight',
            ui_type='slider',
            min_value=0.1,
            max_value=10.0,
            distribution='log_uniform',
        ),
        'LAMBDA_INTER': _control_payload(
            value=scalar_constants['LAMBDA_INTER'],
            ui_label='Inter-Pillar Flow Weight',
            ui_type='slider',
            min_value=0.1,
            max_value=10.0,
            distribution='log_uniform',
        ),
        'LAMBDA_V': _control_payload(
            value=scalar_constants['LAMBDA_V'],
            ui_label='Life-Stage Anchor Weight',
            ui_type='slider',
            min_value=0.1,
            max_value=20.0,
            distribution='log_uniform',
        ),
        'LAMBDA_CLIM': _control_payload(
            value=scalar_constants['LAMBDA_CLIM'],
            ui_label='Climate Balance Weight',
            ui_type='slider',
            min_value=0.1,
            max_value=10.0,
            distribution='log_uniform',
        ),
        'LAMBDA_DOM': _control_payload(
            value=scalar_constants['LAMBDA_DOM'],
            ui_label='Pillar Domain Resonance Weight',
            ui_type='slider',
            min_value=0.1,
            max_value=12.0,
            distribution='log_uniform',
        ),
        'LAMBDA_MODE': _control_payload(
            value=scalar_constants['LAMBDA_MODE'],
            ui_label='Structure-Mode Fidelity Weight',
            ui_type='slider',
            min_value=0.1,
            max_value=20.0,
            distribution='log_uniform',
        ),
        'LAMBDA_ACT': _control_payload(
            value=scalar_constants['LAMBDA_ACT'],
            ui_label='Activated Rule Penalty Weight',
            ui_type='slider',
            min_value=0.1,
            max_value=12.0,
            distribution='log_uniform',
        ),
        'LAMBDA_CLASH': _control_payload(
            value=scalar_constants['LAMBDA_CLASH'],
            ui_label='Clash Penalty Weight',
            ui_type='slider',
            min_value=0.1,
            max_value=20.0,
            distribution='log_uniform',
        ),
        'LAMBDA_SCATTER': _control_payload(
            value=scalar_constants['LAMBDA_SCATTER'],
            ui_label='Clash Scatter Penalty Weight',
            ui_type='slider',
            min_value=0.1,
            max_value=12.0,
            distribution='log_uniform',
        ),
        'LAMBDA_FRAME': _control_payload(
            value=scalar_constants['LAMBDA_FRAME'],
            ui_label='Three-Frame Conversion Weight',
            ui_type='slider',
            min_value=0.1,
            max_value=20.0,
            distribution='log_uniform',
        ),
        'LAMBDA_PUN': _control_payload(
            value=scalar_constants['LAMBDA_PUN'],
            ui_label='Punishment Retention Weight',
            ui_type='slider',
            min_value=0.1,
            max_value=16.0,
            distribution='log_uniform',
        ),
        'LAMBDA_COR': _control_payload(
            value=scalar_constants['LAMBDA_COR'],
            ui_label='Harmony Corruption Weight',
            ui_type='slider',
            min_value=0.1,
            max_value=16.0,
            distribution='log_uniform',
        ),
        'LAMBDA_CROSS': _control_payload(
            value=scalar_constants['LAMBDA_CROSS'],
            ui_label='Ten-God Reassignment Cost',
            ui_type='slider',
            min_value=0.1,
            max_value=24.0,
            distribution='log_uniform',
        ),
        'active_edge_fraction_of_max_flux': _control_payload(
            value=scalar_constants['active_edge_fraction_of_max_flux'],
            ui_label='Qi Current Activation Threshold',
            ui_type='slider',
            min_value=0.05,
            max_value=0.8,
            distribution='beta',
        ),
        'pulse_balance_ratio_min': _control_payload(
            value=scalar_constants['pulse_balance_ratio_min'],
            ui_label='Pulse Balance Lower Bound',
            ui_type='slider',
            min_value=0.1,
            max_value=1.0,
            distribution='beta',
        ),
        'pulse_balance_ratio_max': _control_payload(
            value=scalar_constants['pulse_balance_ratio_max'],
            ui_label='Pulse Balance Upper Bound',
            ui_type='slider',
            min_value=1.0,
            max_value=10.0,
            distribution='log_uniform',
        ),
        'cascade_gain_min': _control_payload(
            value=scalar_constants['cascade_gain_min'],
            ui_label='Cascade Amplification Gate',
            ui_type='slider',
            min_value=1.0,
            max_value=3.0,
            distribution='log_uniform',
        ),
        'bottleneck_quantile': _control_payload(
            value=scalar_constants['bottleneck_quantile'],
            ui_label='Pressure Node Cutoff',
            ui_type='slider',
            min_value=0.5,
            max_value=0.99,
            distribution='beta',
        ),
    }

    evolution_vector_matrix_controls = {
        'WUXING_MATRIX': _control_payload(
            value=vector_matrix_constants['WUXING_MATRIX'],
            ui_label='Element Interaction Matrix',
            ui_type='matrix',
            min_value=-2.0,
            max_value=2.0,
            distribution='component_wise_truncated_normal',
        ),
        'DOMAIN_RESONANCE_MATRIX': _control_payload(
            value=vector_matrix_constants['DOMAIN_RESONANCE_MATRIX'],
            ui_label='Pillar Domain Resonance Matrix',
            ui_type='matrix',
            min_value=-1.5,
            max_value=1.5,
            distribution='component_wise_truncated_normal',
        ),
        'STAGE_AMPLITUDE_BY_STAGE': _control_payload(
            value=vector_matrix_constants['STAGE_AMPLITUDE_BY_STAGE'],
            ui_label='Life-Stage Vitality Profile',
            ui_type='vector',
            min_value=0.0,
            max_value=1.5,
            distribution='component_wise_beta',
        ),
        'PARTIAL_STATE_WEIGHT_BY_S': _control_payload(
            value=vector_matrix_constants['PARTIAL_STATE_WEIGHT_BY_S'],
            ui_label='Partial-State Weight Curve',
            ui_type='vector',
            min_value=0.0,
            max_value=1.0,
            distribution='constrained_beta',
        ),
        'PROXIMITY_WEIGHT_BY_GAP': _control_payload(
            value=vector_matrix_constants['PROXIMITY_WEIGHT_BY_GAP'],
            ui_label='Pillar Distance Decay Curve',
            ui_type='vector',
            min_value=0.0,
            max_value=1.5,
            distribution='monotonic_constrained_beta',
        ),
        'CLUSTER_ALPHA': _control_payload(
            value=vector_matrix_constants['CLUSTER_ALPHA'],
            ui_label='Cluster Distance Weight Alpha',
            ui_type='simplex',
            min_value=0.0,
            max_value=1.0,
            distribution='dirichlet',
        ),
        'CLUSTER_BETA': _control_payload(
            value=vector_matrix_constants['CLUSTER_BETA'],
            ui_label='Cluster Distance Weight Beta',
            ui_type='simplex',
            min_value=0.0,
            max_value=1.0,
            distribution='dirichlet',
        ),
        'CLUSTER_GAMMA': _control_payload(
            value=vector_matrix_constants['CLUSTER_GAMMA'],
            ui_label='Cluster Distance Weight Gamma',
            ui_type='simplex',
            min_value=0.0,
            max_value=1.0,
            distribution='dirichlet',
        ),
    }

    optional_input_conventions = {
        'zi_convention': _control_payload(
            value=conventions.zi_convention,
            ui_label='Zi Convention',
            ui_type='segmented',
            options=['split_midnight', 'whole_zi_23'],
        ),
        'hour_basis': _control_payload(
            value=conventions.hour_basis,
            ui_label='Hour Basis',
            ui_type='segmented',
            options=['true_solar', 'civil'],
        ),
        'day_boundary_basis': _control_payload(
            value=conventions.day_boundary_basis,
            ui_label='Day Boundary Basis',
            ui_type='segmented',
            options=['true_solar', 'civil'],
        ),
        'birth_time_uncertainty_seconds': _control_payload(
            value=0.0
            if birth_time_uncertainty_seconds is None
            else float(birth_time_uncertainty_seconds),
            ui_label='Birth Time Uncertainty (Seconds)',
            ui_type='slider',
            min_value=0.0,
            max_value=7200.0,
            distribution='linear',
        ),
    }

    return {
        'main_view_controls': main_view_controls,
        'evolution_reading_controls': {
            'scalar_constants': evolution_scalar_controls,
            'vector_matrix_constants': evolution_vector_matrix_controls,
        },
        'input_convention_controls': optional_input_conventions,
    }


def _build_evolution_explorer_graph_data(
    evolution_input: EvolutionInput,
    basin_index: int,
    flux_threshold: float,
    particles: int,
    temperature_steps: int,
    sweeps_per_step: int,
    seed: int,
    dbscan_eps: float,
    dbscan_min_samples: int,
    scalar_constants: dict[str, float],
    vector_matrix_constants: dict[str, Any],
) -> dict[str, Any]:
    # Keep API latency reasonable for interactive explorer navigation.
    with _temporary_evolution_control_overrides(
        scalar_constants=scalar_constants,
        vector_matrix_constants=vector_matrix_constants,
    ):
        evolution_output = run_natal_mvp(
            evolution_input=evolution_input,
            inference_config=InferenceConfig(
                particles=particles,
                temperature_steps=temperature_steps,
                sweeps_per_step=sweeps_per_step,
                seed=seed,
            ),
            postprocess_config=PostprocessConfig(
                discrete_relax_max_passes=1,
                continuous_passes=1,
                dbscan_eps=dbscan_eps,
                dbscan_min_samples=dbscan_min_samples,
            ),
        )
    evolution_payload = _ensure_evolution_basins(
        cast(dict[str, Any], json.loads(json.dumps(asdict(evolution_output))))
    )
    return build_multi_basin_graph_data(
        evolution_payload,
        basin_index=max(0, basin_index),
        flux_threshold=max(0.0, flux_threshold),
    )


# ── Routes ──


@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    """Serve the single-page application."""
    stem_options = [
        {
            'char': ch,
            'pinyin': s['pinyin'],
            'element_fi': s['element_fi'],
            'polarity': s['polarity'],
        }
        for ch, s in STEMS.items()
    ]
    branch_options = [
        {
            'char': ch,
            'pinyin': b['pinyin'],
            'animal_fi': b['animal_fi'],
            'element_fi': b['element_fi'],
            'polarity': b['polarity'],
        }
        for ch, b in BRANCHES.items()
    ]
    return templates.TemplateResponse(
        'index.html',
        {
            'request': request,
            'stem_options': stem_options,
            'branch_options': branch_options,
            'app_version': __version__,
        },
    )


@app.post('/api/chart')
async def create_chart(payload: ChartRequest) -> ChartPayload:
    """Return structured chart data for rendering."""
    # Validate characters
    for field in ['hour_stem', 'day_stem', 'month_stem', 'year_stem']:
        if getattr(payload, field) not in STEMS:
            raise HTTPException(
                status_code=400,
                detail=f'Invalid stem: {getattr(payload, field)}',
            )
    for field in ['hour_branch', 'day_branch', 'month_branch', 'year_branch']:
        if getattr(payload, field) not in BRANCHES:
            raise HTTPException(
                status_code=400,
                detail=f'Invalid branch: {getattr(payload, field)}',
            )
    try:
        _parse_date_and_time(payload.date, payload.time)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    chart = build_chart(
        payload.date,
        payload.time,
        payload.hour_stem,
        payload.hour_branch,
        payload.day_stem,
        payload.day_branch,
        payload.month_stem,
        payload.month_branch,
        payload.year_stem,
        payload.year_branch,
        lang=payload.lang,
    )
    return chart


@app.post('/api/four_pillars')
async def calculate_four_pillars(payload: FourPillarsRequest) -> dict[str, Any]:
    """Calculate true solar time and four pillars from date/time with either location or city/country."""
    try:
        location, resolved_city = await _resolve_four_pillars_location(payload)
        result = _build_four_pillars_result(
            date_value=payload.date,
            time_value=payload.time,
            location=location,
            conventions_input=payload.conventions,
            birth_time_uncertainty_seconds=payload.birth_time_uncertainty_seconds,
        )
    except (ValueError, AmbiguousTimeError, NonexistentTimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail='Internal engine error.') from exc

    response: dict[str, Any] = {
        'solar_time': result['solar_time'],
        'four_pillars': result['four_pillars'],
        'flags': result['flags'],
        'engine': result['engine'],
    }
    if resolved_city is not None:
        response['resolved_location'] = {
            'city': resolved_city.city,
            'country': resolved_city.country,
            'timezone': resolved_city.timezone,
        }

    four_pillars = cast(dict[str, Any], result['four_pillars'])
    try:
        if payload.include_chart:
            response['chart'] = _build_chart_from_four_pillars(
                date_value=payload.date,
                time_value=payload.time,
                lang=payload.lang,
                four_pillars=four_pillars,
            )
        if payload.include_hidden_stems:
            hidden_stems_request = HiddenStemsRequest(
                year_pillar=_pillar_text_for_hidden_stems(four_pillars, 'year'),
                month_pillar=_pillar_text_for_hidden_stems(four_pillars, 'month'),
                day_pillar=_pillar_text_for_hidden_stems(four_pillars, 'day'),
                hour_pillar=_pillar_text_for_hidden_stems(four_pillars, 'hour'),
            )
            response['hidden_stems'] = _build_hidden_stems_result(hidden_stems_request)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail='Internal engine error.') from exc

    return response


@app.post('/api/evolution_explorer')
async def evolution_explorer(payload: EvolutionExplorerRequest) -> dict[str, Any]:
    """Build explorer graph data from date/time and city/location input."""
    resolved_city: ResolvedCity | None = None
    try:
        resolved_controls = _resolve_evolution_controls(payload)
        resolved_seed = _resolve_evolution_seed(resolved_controls.seed_mode)
        location_payload = FourPillarsRequest(
            date=payload.date,
            time=payload.time,
            location=payload.location,
            city=payload.city,
            country=payload.country,
            conventions=resolved_controls.conventions,
            birth_time_uncertainty_seconds=resolved_controls.birth_time_uncertainty_seconds,
            include_chart=False,
            include_hidden_stems=False,
            lang='fi',
        )
        location, resolved_city = await _resolve_four_pillars_location(location_payload)
        four_pillars_result = _build_four_pillars_result(
            date_value=payload.date,
            time_value=payload.time,
            location=location,
            conventions_input=resolved_controls.conventions,
            birth_time_uncertainty_seconds=resolved_controls.birth_time_uncertainty_seconds,
        )
        four_pillars = cast(dict[str, Any], four_pillars_result['four_pillars'])
        hidden_stems_payload = _build_hidden_stems_result(
            HiddenStemsRequest(
                year_pillar=_pillar_text_for_hidden_stems(four_pillars, 'year'),
                month_pillar=_pillar_text_for_hidden_stems(four_pillars, 'month'),
                day_pillar=_pillar_text_for_hidden_stems(four_pillars, 'day'),
                hour_pillar=_pillar_text_for_hidden_stems(four_pillars, 'hour'),
            )
        )
        evolution_input = _build_evolution_input_from_four_pillars(
            four_pillars=four_pillars,
            hidden_stems=hidden_stems_payload,
        )
        graph_data = await run_in_threadpool(
            _build_evolution_explorer_graph_data,
            evolution_input,
            payload.basin_index,
            resolved_controls.flux_threshold,
            resolved_controls.particles,
            resolved_controls.temperature_steps,
            resolved_controls.sweeps_per_step,
            resolved_seed,
            resolved_controls.dbscan_eps,
            resolved_controls.dbscan_min_samples,
            resolved_controls.scalar_constants,
            resolved_controls.vector_matrix_constants,
        )
    except CityLookupServiceError as exc:
        raise HTTPException(
            status_code=500,
            detail='City lookup service unavailable.',
        ) from exc
    except (ValueError, AmbiguousTimeError, NonexistentTimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail='Internal engine error.') from exc

    response: dict[str, Any] = {
        'graph_data': graph_data,
        'resolved_seed': resolved_seed,
        'controls': _build_evolution_controls_payload(
            flux_threshold=resolved_controls.flux_threshold,
            particles=resolved_controls.particles,
            temperature_steps=resolved_controls.temperature_steps,
            sweeps_per_step=resolved_controls.sweeps_per_step,
            dbscan_eps=resolved_controls.dbscan_eps,
            dbscan_min_samples=resolved_controls.dbscan_min_samples,
            seed_mode=resolved_controls.seed_mode,
            conventions=resolved_controls.conventions,
            birth_time_uncertainty_seconds=resolved_controls.birth_time_uncertainty_seconds,
            scalar_constants=resolved_controls.scalar_constants,
            vector_matrix_constants=resolved_controls.vector_matrix_constants,
        ),
    }
    if resolved_city is not None:
        response['resolved_location'] = {
            'city': resolved_city.city,
            'country': resolved_city.country,
            'timezone': resolved_city.timezone,
        }
    return response


@app.get('/api/evolution_controls')
async def evolution_controls() -> dict[str, Any]:
    """Expose evolution control metadata and default values for UI."""
    default_conventions = ConventionInput()
    default_scalar_constants = _default_evolution_scalar_constants()
    default_vector_matrix_constants = _default_evolution_vector_matrix_constants()
    return {
        'controls': _build_evolution_controls_payload(
            flux_threshold=0.0,
            particles=EVOLUTION_DEFAULT_PARTICLES,
            temperature_steps=EVOLUTION_DEFAULT_TEMPERATURE_STEPS,
            sweeps_per_step=EVOLUTION_DEFAULT_SWEEPS_PER_STEP,
            dbscan_eps=EVOLUTION_DEFAULT_DBSCAN_EPS,
            dbscan_min_samples=EVOLUTION_DEFAULT_DBSCAN_MIN_SAMPLES,
            seed_mode=EVOLUTION_DEFAULT_SEED_MODE,
            conventions=default_conventions,
            birth_time_uncertainty_seconds=None,
            scalar_constants=default_scalar_constants,
            vector_matrix_constants=default_vector_matrix_constants,
        )
    }


@app.post('/api/location_search')
async def location_search(payload: LocationSearchRequest) -> dict[str, dict[str, str]]:
    """Resolve a free-text city query and return canonical city metadata."""
    try:
        _, resolved_city = await _resolve_city_location(payload.city, payload.country)
    except CityLookupServiceError as exc:
        raise HTTPException(
            status_code=500,
            detail='City lookup service unavailable.',
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail='Internal engine error.') from exc

    return {
        'resolved_location': {
            'city': resolved_city.city,
            'country': resolved_city.country,
            'timezone': resolved_city.timezone,
        },
    }


@app.post('/api/location_suggest')
async def location_suggest(
    payload: LocationSuggestRequest,
) -> dict[str, list[dict[str, str]]]:
    """Return city suggestions for autosuggest input."""
    query = payload.query.strip()
    if not query:
        return {'suggestions': []}

    try:
        results = await _search_city_candidates(query, count=payload.limit)
    except CityLookupServiceError as exc:
        raise HTTPException(
            status_code=500,
            detail='City lookup service unavailable.',
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail='Internal engine error.') from exc

    suggestions: list[dict[str, str]] = []
    for result in results:
        try:
            _, resolved_city = _city_models_from_result(result, query)
        except ValueError:
            continue
        suggestions.append(
            {
                'city': resolved_city.city,
                'country': resolved_city.country,
                'timezone': resolved_city.timezone,
                'display': f'{resolved_city.city}, {resolved_city.country}',
            }
        )

    return {'suggestions': suggestions}


@app.post('/api/hidden_stems')
async def hidden_stems(
    payload: HiddenStemsRequest,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Resolve hidden stems for the four supplied pillar pairs."""
    try:
        hidden_stems_payload = _build_hidden_stems_result(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail='Internal hidden stems lookup error.'
        ) from exc

    return {'hidden_stems': hidden_stems_payload}
