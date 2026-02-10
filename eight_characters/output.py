import json


def _rounded(value: float, digits: int) -> float:
    return float(f'{value:.{digits}f}')


def normalize_output_numeric_precision(payload: dict) -> dict:
    intermediate = payload['intermediate']
    intermediate['solar_longitude_deg'] = _rounded(intermediate['solar_longitude_deg'], 6)
    intermediate['equation_of_time_minutes'] = _rounded(intermediate['equation_of_time_minutes'], 2)
    intermediate['delta_t_seconds'] = _rounded(intermediate['delta_t_seconds'], 1)
    intermediate['tt_julian_date'] = _rounded(intermediate['tt_julian_date'], 8)

    for pillar_name in ('year', 'month'):
        boundary = payload['pillars'][pillar_name]['boundary']
        boundary['distance_seconds'] = _rounded(boundary['distance_seconds'], 1)

    flags = payload['flags']
    flags['hour_boundary_proximity_seconds'] = _rounded(flags['hour_boundary_proximity_seconds'], 1)
    flags['model_uncertainty_seconds'] = _rounded(flags['model_uncertainty_seconds'], 1)

    return payload


def dumps_deterministic(payload: dict) -> str:
    return json.dumps(
        normalize_output_numeric_precision(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    )
