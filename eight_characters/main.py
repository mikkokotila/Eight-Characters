import csv
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict, cast

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from eight_characters import __version__
from eight_characters.conventions import ConventionSettings
from eight_characters.data import (
    BRANCHES,
    STEMS,
    ChartPayload,
    build_chart,
)
from eight_characters.engine import compute_engine_payload
from eight_characters.time_convert import (
    AmbiguousTimeError,
    BirthInput,
    NonexistentTimeError,
)

BASE_DIR = Path(__file__).resolve().parent
MAPPINGS_DIR = BASE_DIR / 'resources' / 'mappings'

app = FastAPI(title='Eight Characters')
app.mount('/static', StaticFiles(directory=BASE_DIR / 'static'), name='static')
templates = Jinja2Templates(directory=BASE_DIR / 'templates')


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
    conventions: ConventionInput = ConventionInput()
    birth_time_uncertainty_seconds: float | None = None
    include_chart: bool = False
    include_hidden_stems: bool = False
    lang: str = 'fi'


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
    except Exception as exc:
        raise ValueError('Failed to resolve city. Please try again.') from exc

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
            response['chart'] = build_chart(
                payload.date,
                payload.time,
                _pillar_component_from_four_pillars(
                    four_pillars,
                    pillar_name='hour',
                    component_name='stem',
                ),
                _pillar_component_from_four_pillars(
                    four_pillars,
                    pillar_name='hour',
                    component_name='branch',
                ),
                _pillar_component_from_four_pillars(
                    four_pillars,
                    pillar_name='day',
                    component_name='stem',
                ),
                _pillar_component_from_four_pillars(
                    four_pillars,
                    pillar_name='day',
                    component_name='branch',
                ),
                _pillar_component_from_four_pillars(
                    four_pillars,
                    pillar_name='month',
                    component_name='stem',
                ),
                _pillar_component_from_four_pillars(
                    four_pillars,
                    pillar_name='month',
                    component_name='branch',
                ),
                _pillar_component_from_four_pillars(
                    four_pillars,
                    pillar_name='year',
                    component_name='stem',
                ),
                _pillar_component_from_four_pillars(
                    four_pillars,
                    pillar_name='year',
                    component_name='branch',
                ),
                lang=payload.lang,
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


@app.post('/api/location_search')
async def location_search(payload: LocationSearchRequest) -> dict[str, dict[str, str]]:
    """Resolve a free-text city query and return canonical city metadata."""
    try:
        _, resolved_city = await _resolve_city_location(payload.city, payload.country)
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
