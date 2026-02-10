from pathlib import Path
from datetime import datetime

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from eight_characters.data import (
    STEMS, BRANCHES, build_chart,
)
from eight_characters import __version__
from eight_characters.conventions import ConventionSettings
from eight_characters.engine import compute_engine_payload
from eight_characters.time_convert import AmbiguousTimeError, BirthInput, NonexistentTimeError

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title='Eight Characters')
app.mount('/static', StaticFiles(directory=BASE_DIR / 'static'), name='static')
templates = Jinja2Templates(directory=BASE_DIR / 'templates')


# ── Request / Response models ──

class ChartRequest(BaseModel):
    date: str        # YYYY-MM-DD
    time: str        # HH:MM
    hour_stem: str   # Chinese character
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


class BaziRequest(BaseModel):
    date: str
    time: str
    location: LocationInput
    conventions: ConventionInput = ConventionInput()
    birth_time_uncertainty_seconds: float | None = None


class FourPillarsRequest(BaseModel):
    date: str
    time: str
    city: str
    conventions: ConventionInput = ConventionInput()
    birth_time_uncertainty_seconds: float | None = None


class LocationSearchRequest(BaseModel):
    city: str


class LocationSuggestRequest(BaseModel):
    query: str
    limit: int = 6


class ResolvedCity(BaseModel):
    city: str
    country: str
    timezone: str


def _parse_date_and_time(date_value: str, time_value: str) -> tuple[int, int, int, int, int, int]:
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


async def _resolve_city_location(city: str) -> tuple[LocationInput, ResolvedCity]:
    results = await _search_city_candidates(city, count=1)
    if not results:
        raise ValueError(f'Could not resolve city: {city.strip()}')
    top_match = results[0]
    return _city_models_from_result(top_match, city.strip())


async def _search_city_candidates(query: str, count: int = 6) -> list[dict]:
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

    payload = response.json()
    return payload.get('results') or []


def _city_models_from_result(top_match: dict, city_fallback: str) -> tuple[LocationInput, ResolvedCity]:
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


def _build_bazi_result(
    *,
    date_value: str,
    time_value: str,
    location: LocationInput,
    conventions_input: ConventionInput,
    birth_time_uncertainty_seconds: float | None,
) -> dict:
    year, month, day, hour, minute, second = _parse_date_and_time(date_value, time_value)
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
            'local_mean_solar_time': engine_payload['intermediate']['local_mean_solar_time'],
            'true_solar_time': engine_payload['intermediate']['true_solar_time'],
            'equation_of_time_minutes': engine_payload['intermediate']['equation_of_time_minutes'],
        },
        'four_pillars': engine_payload['pillars'],
        'flags': engine_payload['flags'],
        'engine': engine_payload['engine'],
    }


# ── Routes ──

@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    '''Serve the single-page application.'''
    stem_options = [
        {'char': ch, 'pinyin': s['pinyin'], 'element_fi': s['element_fi'], 'polarity': s['polarity']}
        for ch, s in STEMS.items()
    ]
    branch_options = [
        {'char': ch, 'pinyin': b['pinyin'], 'animal_fi': b['animal_fi'], 'element_fi': b['element_fi'], 'polarity': b['polarity']}
        for ch, b in BRANCHES.items()
    ]
    return templates.TemplateResponse('index.html', {
        'request': request,
        'stem_options': stem_options,
        'branch_options': branch_options,
        'app_version': __version__,
    })


@app.post('/api/chart')
async def create_chart(payload: ChartRequest):
    '''Return structured chart data for rendering.'''
    # Validate characters
    for field in ['hour_stem', 'day_stem', 'month_stem', 'year_stem']:
        if getattr(payload, field) not in STEMS:
            return {'error': f'Invalid stem: {getattr(payload, field)}'}
    for field in ['hour_branch', 'day_branch', 'month_branch', 'year_branch']:
        if getattr(payload, field) not in BRANCHES:
            return {'error': f'Invalid branch: {getattr(payload, field)}'}

    chart = build_chart(
        payload.date, payload.time,
        payload.hour_stem, payload.hour_branch,
        payload.day_stem, payload.day_branch,
        payload.month_stem, payload.month_branch,
        payload.year_stem, payload.year_branch,
        lang=payload.lang,
    )
    return chart


@app.post('/api/bazi')
async def calculate_bazi(payload: BaziRequest):
    '''Calculate true solar time and four pillars from date, time, and location.'''
    try:
        result = _build_bazi_result(
            date_value=payload.date,
            time_value=payload.time,
            location=payload.location,
            conventions_input=payload.conventions,
            birth_time_uncertainty_seconds=payload.birth_time_uncertainty_seconds,
        )
    except (ValueError, AmbiguousTimeError, NonexistentTimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail='Internal engine error.') from exc

    return {
        'solar_time': result['solar_time'],
        'four_pillars': result['four_pillars'],
        'flags': result['flags'],
        'engine': result['engine'],
    }


@app.post('/api/four_pillars')
async def calculate_four_pillars(payload: FourPillarsRequest):
    '''Resolve city and return only four pillars + solar time.'''
    try:
        location, resolved_city = await _resolve_city_location(payload.city)
        result = _build_bazi_result(
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

    return {
        'resolved_location': {
            'city': resolved_city.city,
            'country': resolved_city.country,
            'timezone': resolved_city.timezone,
        },
        'solar_time': result['solar_time'],
        'four_pillars': result['four_pillars'],
    }


@app.post('/api/location_search')
async def location_search(payload: LocationSearchRequest):
    '''Resolve a free-text city query and return canonical city metadata.'''
    try:
        _, resolved_city = await _resolve_city_location(payload.city)
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
async def location_suggest(payload: LocationSuggestRequest):
    '''Return city suggestions for autosuggest input.'''
    query = payload.query.strip()
    if not query:
        return {'suggestions': []}

    try:
        results = await _search_city_candidates(query, count=payload.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail='Internal engine error.') from exc

    suggestions = []
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
