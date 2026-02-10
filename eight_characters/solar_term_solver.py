from datetime import datetime, timezone

from eight_characters.root_finding import brentq, find_bracket, normalize_longitude_difference
from eight_characters.solar_position import compute_apparent_solar_longitude, julian_date_from_datetime_utc


UTC = timezone.utc

JIE_TARGET_LONGITUDES = (315.0, 345.0, 15.0, 45.0, 75.0, 105.0, 135.0, 165.0, 195.0, 225.0, 255.0, 285.0)


def apparent_longitude_at_jd_tt(jd_tt: float) -> float:
    lambda_apparent_deg, _, _, _, _, _ = compute_apparent_solar_longitude(jd_tt)
    return lambda_apparent_deg


def _term_root_function(target_longitude_deg: float):
    def f(jd_tt: float) -> float:
        lam = apparent_longitude_at_jd_tt(jd_tt)
        return normalize_longitude_difference(lam - target_longitude_deg)

    return f


def find_solar_term(
    target_longitude_deg: float,
    seed_jd_tt: float,
    tolerance_seconds: float = 0.01,
) -> float:
    jd_a, jd_b = find_bracket(
        target_longitude_deg=target_longitude_deg,
        seed_jd_tt=seed_jd_tt,
        longitude_fn=apparent_longitude_at_jd_tt,
    )
    xtol_days = tolerance_seconds / 86400.0
    return brentq(_term_root_function(target_longitude_deg), jd_a, jd_b, xtol=xtol_days)


def lichun_jd_tt_for_civil_year(civil_year: int) -> float:
    seed_utc = datetime(civil_year, 2, 4, 0, 0, 0, tzinfo=UTC)
    seed_jd = julian_date_from_datetime_utc(seed_utc)
    return find_solar_term(315.0, seed_jd)


def nearest_jie_distance_seconds(birth_jd_tt: float, nearby_term_jd: list[float]) -> float:
    if not nearby_term_jd:
        raise ValueError('nearby_term_jd must not be empty.')
    min_distance_days = min(abs(birth_jd_tt - term_jd) for term_jd in nearby_term_jd)
    return min_distance_days * 86400.0
