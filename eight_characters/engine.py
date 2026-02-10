from dataclasses import asdict
from datetime import datetime

from eight_characters import __version__
from eight_characters.conventions import (
    DAY_BOUNDARY_BASIS_TRUE_SOLAR,
    HOUR_BASIS_TRUE_SOLAR,
    ConventionSettings,
)
from eight_characters.embedded_data import ENGINE_MODEL_IDS, get_tzdb_version
from eight_characters.integrity import (
    build_alternative_zi_convention,
    hour_boundary_distance_seconds,
    is_zi_hour_window,
    model_uncertainty_seconds_for_year,
    validate_pillar_set,
)
from eight_characters.output import dumps_deterministic
from eight_characters.sexagenary import (
    BRANCHES as SEXAGENARY_BRANCHES,
    STEMS as SEXAGENARY_STEMS,
    day_pillar,
    hour_pillar,
    month_pillar,
    year_pillar,
)
from eight_characters.solar_position import (
    compute_solar_position_and_tst,
    julian_date_from_datetime_utc,
)
from eight_characters.solar_term_solver import (
    find_solar_term,
    lichun_jd_tt_for_civil_year,
    nearest_jie_distance_seconds,
)
from eight_characters.time_convert import BirthInput, convert_utc_to_tt, normalize_birth_input


TERM_LABEL_BY_TARGET = {
    315.0: 'lichun_315',
    345.0: 'jingzhe_345',
    15.0: 'qingming_15',
    45.0: 'lixia_45',
    75.0: 'mangzhong_75',
    105.0: 'xiaoshu_105',
    135.0: 'liqiu_135',
    165.0: 'bailu_165',
    195.0: 'hanlu_195',
    225.0: 'lidong_225',
    255.0: 'daxue_255',
    285.0: 'xiaohan_285',
}

MONTH_BOUNDARIES = (315.0, 345.0, 15.0, 45.0, 75.0, 105.0, 135.0, 165.0, 195.0, 225.0, 255.0, 285.0)

TERM_SEED_MONTH_DAY = {
    285.0: (1, 5),
    315.0: (2, 4),
    345.0: (3, 6),
    15.0: (4, 5),
    45.0: (5, 6),
    75.0: (6, 6),
    105.0: (7, 7),
    135.0: (8, 7),
    165.0: (9, 7),
    195.0: (10, 8),
    225.0: (11, 7),
    255.0: (12, 7),
}


def _seed_jd_for_target(year_value: int, target_longitude: float) -> float:
    month_value, day_value = TERM_SEED_MONTH_DAY[target_longitude]
    seed_dt = datetime(year_value, month_value, day_value, 0, 0, 0)
    return julian_date_from_datetime_utc(seed_dt)


def _nearby_month_term_jds(civil_year: int) -> list[float]:
    values: list[float] = []
    for year_value in (civil_year - 1, civil_year, civil_year + 1):
        for target in MONTH_BOUNDARIES:
            seed_jd = _seed_jd_for_target(year_value, target)
            values.append(find_solar_term(target, seed_jd))
    return values


def _boundary_note(distance_seconds: float, label: str) -> str:
    if distance_seconds < 0.0:
        return f'Birth is before boundary {label}.'
    return f'Birth is after boundary {label}.'


def _pillar_dict(pillar_obj) -> dict:
    return {
        'stem': {
            'index': pillar_obj.stem_idx,
            'chinese': SEXAGENARY_STEMS[pillar_obj.stem_idx],
        },
        'branch': {
            'index': pillar_obj.branch_idx,
            'chinese': SEXAGENARY_BRANCHES[pillar_obj.branch_idx],
        },
    }


def compute_engine_payload(value: BirthInput) -> dict:
    normalized = normalize_birth_input(value)
    tt_result = convert_utc_to_tt(normalized.utc_datetime)

    solar = compute_solar_position_and_tst(
        utc_datetime=normalized.utc_datetime,
        longitude_deg=normalized.longitude,
        tt_minus_utc_seconds=tt_result.tt_minus_utc_seconds,
    )

    lichun_jd = lichun_jd_tt_for_civil_year(normalized.utc_datetime.year)
    year_result, bazi_year = year_pillar(
        civil_year=normalized.utc_datetime.year,
        birth_jd_tt=solar.jd_tt,
        lichun_jd_tt=lichun_jd,
    )
    month_result = month_pillar(
        lambda_apparent_deg=solar.lambda_apparent_deg,
        year_stem_idx=year_result.stem_idx,
    )

    if normalized.civil_datetime_local is None:
        civil_local_naive = normalized.utc_datetime.replace(tzinfo=None)
    else:
        civil_local_naive = normalized.civil_datetime_local

    day_result = day_pillar(
        civil_dt_local=civil_local_naive,
        tst_dt=solar.true_solar_time,
        conventions=value.conventions,
    )
    hour_result = hour_pillar(
        day_stem_idx=day_result.pillar.stem_idx,
        civil_dt_local=civil_local_naive,
        tst_dt=solar.true_solar_time,
        conventions=value.conventions,
    )

    pillars = {
        'year': year_result,
        'month': month_result,
        'day': day_result.pillar,
        'hour': hour_result,
    }
    validate_pillar_set(pillars)

    term_jds = _nearby_month_term_jds(normalized.utc_datetime.year)
    nearest_term_seconds = nearest_jie_distance_seconds(solar.jd_tt, term_jds)
    model_uncertainty_seconds = model_uncertainty_seconds_for_year(normalized.utc_datetime.year)
    user_uncertainty = value.birth_time_uncertainty_seconds or 0.0
    total_uncertainty_seconds = max(model_uncertainty_seconds, user_uncertainty)
    solar_term_ambiguous = nearest_term_seconds < total_uncertainty_seconds

    if value.conventions.hour_basis == HOUR_BASIS_TRUE_SOLAR:
        hour_basis_dt = solar.true_solar_time
    else:
        hour_basis_dt = civil_local_naive
    hour_boundary_seconds = hour_boundary_distance_seconds(hour_basis_dt)

    if value.conventions.day_boundary_basis == DAY_BOUNDARY_BASIS_TRUE_SOLAR:
        zi_basis_dt = solar.true_solar_time
    else:
        zi_basis_dt = civil_local_naive
    zi_window = is_zi_hour_window(zi_basis_dt)

    alternative_pillars = None
    if zi_window:
        alternative_conventions = build_alternative_zi_convention(value.conventions)
        alt_day = day_pillar(
            civil_dt_local=civil_local_naive,
            tst_dt=solar.true_solar_time,
            conventions=alternative_conventions,
        )
        alt_hour = hour_pillar(
            day_stem_idx=alt_day.pillar.stem_idx,
            civil_dt_local=civil_local_naive,
            tst_dt=solar.true_solar_time,
            conventions=alternative_conventions,
        )
        alternative_pillars = {
            'day': _pillar_dict(alt_day.pillar),
            'hour': _pillar_dict(alt_hour),
            'conventions': asdict(alternative_conventions),
        }

    lichun_distance_seconds = (solar.jd_tt - lichun_jd) * 86400.0

    payload = {
        'engine': {
            'version': __version__,
            'vsop87_series': ENGINE_MODEL_IDS['vsop87_series'],
            'nutation_model': ENGINE_MODEL_IDS['nutation_model'],
            'mean_obliquity_model': ENGINE_MODEL_IDS['mean_obliquity_model'],
            'delta_t_model': ENGINE_MODEL_IDS['delta_t_model'],
            'tzdb_version': get_tzdb_version(),
            'leap_second_table': tt_result.leap_second_metadata,
        },
        'input': {
            'date': civil_local_naive.strftime('%Y-%m-%d'),
            'time': civil_local_naive.strftime('%H:%M:%S'),
            'timezone': normalized.timezone_name,
            'fold': normalized.fold,
            'longitude': normalized.longitude,
            'latitude': normalized.latitude,
            'birth_time_uncertainty_seconds': value.birth_time_uncertainty_seconds,
            'conventions': asdict(value.conventions),
        },
        'intermediate': {
            'utc_time': normalized.utc_datetime.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'delta_t_seconds': tt_result.delta_t_seconds,
            'tt_conversion_method': tt_result.conversion_method,
            'tt_julian_date': solar.jd_tt,
            'solar_longitude_deg': solar.lambda_apparent_deg,
            'equation_of_time_minutes': solar.equation_of_time_minutes,
            'local_mean_solar_time': solar.local_mean_solar_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'true_solar_time': solar.true_solar_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'effective_day_date': day_result.effective_date.isoformat(),
            'julian_day_number': day_result.jdn,
            'sexagenary_day_index': day_result.idx0,
        },
        'pillars': {
            'year': {
                **_pillar_dict(year_result),
                'boundary': {
                    'type': TERM_LABEL_BY_TARGET[315.0],
                    'distance_seconds': lichun_distance_seconds,
                    'note': _boundary_note(lichun_distance_seconds, TERM_LABEL_BY_TARGET[315.0]),
                },
            },
            'month': {
                **_pillar_dict(month_result),
                'boundary': {
                    'type': 'nearest_jie_boundary',
                    'distance_seconds': nearest_term_seconds,
                    'note': 'Distance to nearest month boundary term.',
                },
            },
            'day': _pillar_dict(day_result.pillar),
            'hour': _pillar_dict(hour_result),
        },
        'flags': {
            'zi_hour_window': zi_window,
            'solar_term_ambiguous': solar_term_ambiguous,
            'hour_boundary_proximity_seconds': hour_boundary_seconds,
            'model_uncertainty_seconds': model_uncertainty_seconds,
            'high_latitude_warning': normalized.high_latitude_warning,
            'alternative_pillars': alternative_pillars,
        },
        'meta': {
            'bazi_year': bazi_year,
        },
    }
    return payload


def compute_engine_json(value: BirthInput) -> str:
    payload = compute_engine_payload(value)
    return dumps_deterministic(payload)
