from math import pi


def mean_obliquity_arcseconds_iau2006(t_centuries: float) -> float:
    return (
        84381.406
        - 46.836769 * t_centuries
        - 0.0001831 * (t_centuries ** 2)
        + 0.00200340 * (t_centuries ** 3)
        - 0.000000576 * (t_centuries ** 4)
        - 0.0000000434 * (t_centuries ** 5)
    )


def arcseconds_to_radians(value_arcseconds: float) -> float:
    return value_arcseconds * pi / (180.0 * 3600.0)


def true_obliquity_radians(t_centuries: float, delta_epsilon_arcseconds: float) -> float:
    epsilon0_arcseconds = mean_obliquity_arcseconds_iau2006(t_centuries)
    return arcseconds_to_radians(epsilon0_arcseconds + delta_epsilon_arcseconds)
