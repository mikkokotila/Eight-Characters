import csv
import json
from dataclasses import asdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict, cast

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from eight_characters import __version__
from eight_characters.conventions import ConventionSettings
from eight_characters.data import (
    BRANCHES,
    STEMS,
    ChartPayload,
    build_chart,
)
from eight_characters.engine import compute_engine_payload
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
    basin_index: int = 0
    flux_threshold: float = 0.0


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

    for pillar_position, pillar_name in enumerate(('year', 'month', 'day', 'hour'), start=1):
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
        location_payload = FourPillarsRequest(
            date=payload.date,
            time=payload.time,
            location=payload.location,
            city=payload.city,
            country=payload.country,
            conventions=payload.conventions,
            birth_time_uncertainty_seconds=payload.birth_time_uncertainty_seconds,
            include_chart=False,
            include_hidden_stems=False,
            lang='fi',
        )
        location, resolved_city = await _resolve_four_pillars_location(location_payload)
        four_pillars_result = _build_four_pillars_result(
            date_value=payload.date,
            time_value=payload.time,
            location=location,
            conventions_input=payload.conventions,
            birth_time_uncertainty_seconds=payload.birth_time_uncertainty_seconds,
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
        # Keep API latency reasonable for interactive explorer navigation.
        evolution_output = run_natal_mvp(
            evolution_input=evolution_input,
            inference_config=InferenceConfig(
                particles=24,
                temperature_steps=2,
                sweeps_per_step=1,
                seed=42,
            ),
            postprocess_config=PostprocessConfig(
                discrete_relax_max_passes=1,
                continuous_passes=1,
                dbscan_eps=0.08,
                dbscan_min_samples=1,
            ),
        )
        evolution_payload = _ensure_evolution_basins(
            cast(dict[str, Any], json.loads(json.dumps(asdict(evolution_output))))
        )
        graph_data = build_multi_basin_graph_data(
            evolution_payload,
            basin_index=max(0, payload.basin_index),
            flux_threshold=max(0.0, payload.flux_threshold),
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

    response: dict[str, Any] = {'graph_data': graph_data}
    if resolved_city is not None:
        response['resolved_location'] = {
            'city': resolved_city.city,
            'country': resolved_city.country,
            'timezone': resolved_city.timezone,
        }
    return response


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
