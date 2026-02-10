from dataclasses import dataclass
from datetime import datetime, timedelta
from math import atan2, cos, pi, sin, tan

from eight_characters.nutation import nutation_arcseconds_seed
from eight_characters.obliquity import (
    arcseconds_to_radians,
    mean_obliquity_arcseconds_iau2006,
    true_obliquity_radians,
)
from eight_characters.vsop87d import earth_heliocentric_lbr, normalize_degrees


J2000_JD = 2451545.0
SECONDS_PER_DAY = 86400.0


@dataclass(frozen=True)
class SolarPositionResult:
    jd_tt: float
    lambda_apparent_deg: float
    beta_deg: float
    radius_au: float
    delta_psi_arcseconds: float
    delta_epsilon_arcseconds: float
    epsilon_radians: float
    equation_of_time_minutes: float
    local_mean_solar_time: datetime
    true_solar_time: datetime


def julian_date_from_datetime_utc(utc_datetime: datetime) -> float:
    if utc_datetime.tzinfo is not None:
        dt = utc_datetime.replace(tzinfo=None)
    else:
        dt = utc_datetime
    year_value = dt.year
    month_value = dt.month
    day_fraction = dt.day + (
        dt.hour + (dt.minute + (dt.second + dt.microsecond / 1_000_000.0) / 60.0) / 60.0
    ) / 24.0

    if month_value <= 2:
        year_value -= 1
        month_value += 12

    a = year_value // 100
    b = 2 - a + (a // 4)
    jd = (
        int(365.25 * (year_value + 4716))
        + int(30.6001 * (month_value + 1))
        + day_fraction
        + b
        - 1524.5
    )
    return jd


def compute_apparent_solar_longitude(jd_tt: float) -> tuple[float, float, float, float, float, float]:
    tau = (jd_tt - J2000_JD) / 365250.0
    t_centuries = (jd_tt - J2000_JD) / 36525.0

    earth_l_deg, earth_b_deg, radius_au = earth_heliocentric_lbr(tau)
    theta_deg = normalize_degrees(earth_l_deg + 180.0)
    beta_deg = -earth_b_deg

    delta_psi_arcseconds, delta_epsilon_arcseconds = nutation_arcseconds_seed(t_centuries)
    aberration_deg = (-20.4898 / radius_au) / 3600.0
    lambda_apparent_deg = normalize_degrees(theta_deg + delta_psi_arcseconds / 3600.0 + aberration_deg)

    return (
        lambda_apparent_deg,
        beta_deg,
        radius_au,
        delta_psi_arcseconds,
        delta_epsilon_arcseconds,
        t_centuries,
    )


def _equation_of_time_minutes(
    lambda_apparent_deg: float,
    beta_deg: float,
    radius_au: float,
    delta_psi_arcseconds: float,
    epsilon_radians: float,
    t_centuries: float,
) -> float:
    lambda_rad = lambda_apparent_deg * pi / 180.0
    beta_rad = beta_deg * pi / 180.0

    alpha = atan2(
        sin(lambda_rad) * cos(epsilon_radians) - tan(beta_rad) * sin(epsilon_radians),
        cos(lambda_rad),
    )
    if alpha < 0.0:
        alpha += 2.0 * pi
    alpha_deg = alpha * 180.0 / pi

    l0_deg = normalize_degrees(
        280.46646 + 36000.76983 * t_centuries + 0.0003032 * (t_centuries ** 2)
    )
    eot_deg = (
        l0_deg
        - alpha_deg
        + (delta_psi_arcseconds / 3600.0) * cos(epsilon_radians)
        - (20.4898 / (3600.0 * radius_au))
    )
    while eot_deg > 180.0:
        eot_deg -= 360.0
    while eot_deg < -180.0:
        eot_deg += 360.0
    return eot_deg * 4.0


def compute_solar_position_and_tst(
    utc_datetime: datetime,
    longitude_deg: float,
    tt_minus_utc_seconds: float,
) -> SolarPositionResult:
    jd_utc = julian_date_from_datetime_utc(utc_datetime)
    jd_tt = jd_utc + tt_minus_utc_seconds / SECONDS_PER_DAY

    (
        lambda_apparent_deg,
        beta_deg,
        radius_au,
        delta_psi_arcseconds,
        delta_epsilon_arcseconds,
        t_centuries,
    ) = compute_apparent_solar_longitude(jd_tt)

    epsilon_radians = true_obliquity_radians(t_centuries, delta_epsilon_arcseconds)
    equation_of_time_minutes = _equation_of_time_minutes(
        lambda_apparent_deg=lambda_apparent_deg,
        beta_deg=beta_deg,
        radius_au=radius_au,
        delta_psi_arcseconds=delta_psi_arcseconds,
        epsilon_radians=epsilon_radians,
        t_centuries=t_centuries,
    )

    lmst_dt = utc_datetime.replace(tzinfo=None) + timedelta(hours=longitude_deg / 15.0)
    tst_dt = lmst_dt + timedelta(minutes=equation_of_time_minutes)

    return SolarPositionResult(
        jd_tt=jd_tt,
        lambda_apparent_deg=lambda_apparent_deg,
        beta_deg=beta_deg,
        radius_au=radius_au,
        delta_psi_arcseconds=delta_psi_arcseconds,
        delta_epsilon_arcseconds=delta_epsilon_arcseconds,
        epsilon_radians=epsilon_radians,
        equation_of_time_minutes=equation_of_time_minutes,
        local_mean_solar_time=lmst_dt,
        true_solar_time=tst_dt,
    )


def mean_obliquity_degrees_for_jd_tt(jd_tt: float) -> float:
    t_centuries = (jd_tt - J2000_JD) / 36525.0
    return mean_obliquity_arcseconds_iau2006(t_centuries) / 3600.0


def nutation_degrees_for_jd_tt(jd_tt: float) -> tuple[float, float]:
    t_centuries = (jd_tt - J2000_JD) / 36525.0
    delta_psi_arcseconds, delta_epsilon_arcseconds = nutation_arcseconds_seed(t_centuries)
    return (
        delta_psi_arcseconds / 3600.0,
        delta_epsilon_arcseconds / 3600.0,
    )


def arcseconds_to_degrees(value_arcseconds: float) -> float:
    return value_arcseconds / 3600.0


def radians_from_arcseconds(value_arcseconds: float) -> float:
    return arcseconds_to_radians(value_arcseconds)
