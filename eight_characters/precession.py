"""General precession in longitude: from VSOP87D's equinox of date to the IAU 2006 one.

VSOP87D refers the Earth to the mean ecliptic and equinox of date through the
precession of Laskar (1986) with the IAU 1976 constants (Bretagnon & Francou 1988,
A&A 202, 309, section 4.3). The engine's mean obliquity and its nutation, IAU 2000A
as revised for use with the IAU 2006 precession, belong to the IAU 2006 precession
(Capitaine, Wallace & Chapront 2003, A&A 412, 567), whose equinox of date moves
0.300" per century more slowly. Adding the difference of the two general precessions
in longitude refers a longitude of date from VSOP87D to the IAU 2006 equinox of date.
"""


def general_precession_vsop87_arcsec(t_centuries: float) -> float:
    """p_A of VSOP87C and VSOP87D, in arcseconds (Bretagnon & Francou 1988, sec. 4.3).

    The paper counts time in thousands of Julian years; `t_centuries` is Julian
    centuries of TT from J2000.
    """
    t = t_centuries / 10.0
    return (
        50290.966
        + (
            111.1971
            + (0.07732 + (-0.235316 + (-1805.5e-6 + 174.51e-6 * t) * t) * t) * t
        )
        * t
    ) * t


def general_precession_iau2006_arcsec(t_centuries: float) -> float:
    """p_A of the IAU 2006 precession, in arcseconds (Capitaine et al. 2003, as SOFA)."""
    t = t_centuries
    return (
        5028.796195
        + (1.1054348 + (0.00007964 + (-0.000023857 - 0.0000000383 * t) * t) * t) * t
    ) * t


def vsop87_to_iau2006_equinox_arcsec(t_centuries: float) -> float:
    """Add to a VSOP87D longitude of date to refer it to the IAU 2006 equinox of date."""
    return general_precession_iau2006_arcsec(
        t_centuries
    ) - general_precession_vsop87_arcsec(t_centuries)
