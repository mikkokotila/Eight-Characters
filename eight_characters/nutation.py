from math import cos, radians, sin


def _longitude_of_ascending_node_deg(t_centuries: float) -> float:
    return 125.04452 - 1934.136261 * t_centuries + 0.0020708 * (t_centuries ** 2)


def _mean_longitude_sun_deg(t_centuries: float) -> float:
    return 280.4665 + 36000.7698 * t_centuries


def _mean_longitude_moon_deg(t_centuries: float) -> float:
    return 218.3165 + 481267.8813 * t_centuries


def nutation_arcseconds_seed(t_centuries: float) -> tuple[float, float]:
    # Compact deterministic seed model in IAU-style quantities.
    omega = radians(_longitude_of_ascending_node_deg(t_centuries))
    l_sun = radians(_mean_longitude_sun_deg(t_centuries))
    l_moon = radians(_mean_longitude_moon_deg(t_centuries))

    delta_psi_arcseconds = (
        -17.20 * sin(omega)
        - 1.32 * sin(2.0 * l_sun)
        - 0.23 * sin(2.0 * l_moon)
        + 0.21 * sin(2.0 * omega)
    )
    delta_epsilon_arcseconds = (
        9.20 * cos(omega)
        + 0.57 * cos(2.0 * l_sun)
        + 0.10 * cos(2.0 * l_moon)
        - 0.09 * cos(2.0 * omega)
    )
    return delta_psi_arcseconds, delta_epsilon_arcseconds
