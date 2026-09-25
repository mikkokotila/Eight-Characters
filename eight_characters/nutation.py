"""Nutation in longitude and obliquity: IAU 2000A with the IAU 2006 adjustments.

The series are IERS Conventions 2010 Tables 5.3a and 5.3b (the "IAU 2000_R06"
expression, 1358 and 1056 terms), read unmodified from `resources/astronomy`. Their
checksums, declared term counts and term numbering are verified on load. The
fundamental arguments are those of the IERS Conventions 2003 (Eqs. 5.43 and 5.44),
which the tables' headers name. Amplitudes are in microarcseconds.
"""

import re
from functools import cache
from math import cos, fmod, pi, sin

from eight_characters.vsop87d import astronomy_resource_text

NUTATION_LONGITUDE_FILE = 'tab5.3a.txt'
NUTATION_LONGITUDE_SHA256 = (
    '6da73bfe10873ac815520d00fffd67114d647a34afebc5946cfc275e73693f32'
)
NUTATION_OBLIQUITY_FILE = 'tab5.3b.txt'
NUTATION_OBLIQUITY_SHA256 = (
    'f0dff02c78809b629cc64e2a9fbeffaea5ae20f67e1a62a0ed966f8624807557'
)

ARCSEC_TO_RAD = pi / (180.0 * 3600.0)
ARCSEC_PER_TURN = 1_296_000.0
TWO_PI = 2.0 * pi

# One term: the coefficients of sin(ARG) and cos(ARG), and ARG as (argument, multiplier)
# pairs over the fourteen fundamental arguments.
Term = tuple[float, float, tuple[tuple[int, int], ...]]

_SECTION = re.compile(r'j\s*=\s*(\d)\s+Number\s+of\s+terms\s*=\s*(\d+)')
_ROW = re.compile(r'^\s*(\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)((?:\s+-?\d+){14})\s*$')


def _read_table(file_name: str, sha256: str) -> tuple[tuple[Term, ...], ...]:
    """The j = 0 and j = 1 series of one table, each coefficient pair as (sin, cos)."""
    sections: list[list[Term]] = []
    declared: list[int] = []
    numbers: list[int] = []
    for line in astronomy_resource_text(file_name, sha256).splitlines():
        section = _SECTION.search(line)
        if section:
            if int(section.group(1)) != len(sections):
                raise ValueError(f'{file_name}: series out of order.')
            sections.append([])
            declared.append(int(section.group(2)))
            continue
        row = _ROW.match(line)
        if not row:
            continue
        if not sections:
            raise ValueError(f'{file_name}: term before any series header.')
        # Both tables give the sine coefficient first: Table 5.3a A_i then A"_i (cos),
        # Table 5.3b B"_i then B_i (cos), in both the j = 0 and j = 1 series.
        sine, cosine = float(row.group(2)), float(row.group(3))
        multipliers = tuple(int(value) for value in row.group(4).split())
        arguments = tuple(
            (index, multiplier)
            for index, multiplier in enumerate(multipliers)
            if multiplier
        )
        sections[-1].append((sine, cosine, arguments))
        numbers.append(int(row.group(1)))
    counts = [len(section) for section in sections]
    if len(sections) != 2 or counts != declared:
        raise ValueError(
            f'{file_name}: terms per series {counts}, declared {declared}.'
        )
    if numbers != list(range(1, sum(counts) + 1)):
        raise ValueError(f'{file_name}: terms are not numbered 1 to {sum(counts)}.')
    return tuple(tuple(section) for section in sections)


@cache
def nutation_series() -> tuple[
    tuple[tuple[Term, ...], ...], tuple[tuple[Term, ...], ...]
]:
    """The longitude and obliquity series (j = 0 and j = 1), read and verified once."""
    longitude = _read_table(NUTATION_LONGITUDE_FILE, NUTATION_LONGITUDE_SHA256)
    obliquity = _read_table(NUTATION_OBLIQUITY_FILE, NUTATION_OBLIQUITY_SHA256)
    return longitude, obliquity


def fundamental_arguments(t_centuries: float) -> tuple[float, ...]:
    """l, l', F, D, Omega, the eight planetary longitudes and p_A, in radians.

    IERS Conventions 2003, Eqs. 5.43 (Delaunay arguments, arcseconds) and 5.44.
    """
    t = t_centuries

    def delaunay(constant: float, *rates: float) -> float:
        value = 0.0
        for rate in reversed(rates):
            value = (value + rate) * t
        return fmod(constant + value, ARCSEC_PER_TURN) * ARCSEC_TO_RAD

    return (
        delaunay(485868.249036, 1717915923.2178, 31.8792, 0.051635, -0.00024470),
        delaunay(1287104.793048, 129596581.0481, -0.5532, 0.000136, -0.00001149),
        delaunay(335779.526232, 1739527262.8478, -12.7512, -0.001037, 0.00000417),
        delaunay(1072260.703692, 1602961601.2090, -6.3706, 0.006593, -0.00003169),
        delaunay(450160.398036, -6962890.5431, 7.4722, 0.007702, -0.00005939),
        fmod(4.402608842 + 2608.7903141574 * t, TWO_PI),
        fmod(3.176146697 + 1021.3285546211 * t, TWO_PI),
        fmod(1.753470314 + 628.3075849991 * t, TWO_PI),
        fmod(6.203480913 + 334.0612426700 * t, TWO_PI),
        fmod(0.599546497 + 52.9690962641 * t, TWO_PI),
        fmod(0.874016757 + 21.3299104960 * t, TWO_PI),
        fmod(5.481293872 + 7.4781598567 * t, TWO_PI),
        fmod(5.311886287 + 3.8133035638 * t, TWO_PI),
        (0.02438175 + 0.00000538691 * t) * t,
    )


def _series_sum(terms: tuple[Term, ...], arguments: tuple[float, ...]) -> float:
    total = 0.0
    for sine, cosine, multipliers in terms:
        angle = 0.0
        for index, multiplier in multipliers:
            angle += multiplier * arguments[index]
        total += sine * sin(angle) + cosine * cos(angle)
    return total


def nutation_arcseconds(t_centuries: float) -> tuple[float, float]:
    """Nutation in longitude and in obliquity, in arcseconds, at `t_centuries` of TT from J2000."""
    longitude, obliquity = nutation_series()
    arguments = fundamental_arguments(t_centuries)
    delta_psi = _series_sum(longitude[0], arguments) + t_centuries * _series_sum(
        longitude[1], arguments
    )
    delta_epsilon = _series_sum(obliquity[0], arguments) + t_centuries * _series_sum(
        obliquity[1], arguments
    )
    return delta_psi * 1e-6, delta_epsilon * 1e-6
