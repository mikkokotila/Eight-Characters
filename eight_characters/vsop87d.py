"""Earth's heliocentric position from the full VSOP87D series (Bretagnon & Francou 1988).

The coefficients are read from IMCCE's published file `VSOP87D.ear`, unmodified, in
`resources/astronomy`. Its checksum and every series length are verified on load, so
a truncated or altered file stops the app instead of silently degrading positions.
"""

import hashlib
import re
from functools import cache
from math import cos, pi
from pathlib import Path

DEG_PER_RAD = 180.0 / pi
ASTRONOMY_DIR = Path(__file__).resolve().parent / 'resources' / 'astronomy'

VSOP87D_EARTH_FILE = 'VSOP87D.ear'
VSOP87D_EARTH_SHA256 = (
    '8b160c859136d467f2be7fc29efa8a9652e95516dfbde00e4c739d7ddc90ca91'
)
# Terms per power of time for L (variable 1), B (2) and R (3), as IMCCE publishes them.
VSOP87D_EARTH_TERM_COUNTS = {
    1: (559, 341, 142, 22, 11, 5),
    2: (184, 99, 49, 11, 5),
    3: (526, 292, 139, 27, 10, 3),
}

# One series: for each power of time, the (amplitude, phase, frequency) of its terms.
Series = tuple[tuple[tuple[float, float, float], ...], ...]

_HEADER = re.compile(
    r'VSOP87 VERSION D4\s+EARTH\s+VARIABLE (\d) \(LBR\)\s+\*T\*\*(\d)\s+(\d+) TERMS'
)


def astronomy_resource_text(file_name: str, sha256: str) -> str:
    """A model table from `resources/astronomy`, after checking it is the published one."""
    data = (ASTRONOMY_DIR / file_name).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        raise ValueError(f'{file_name} is not the published table (SHA-256 {digest}).')
    return data.decode('ascii')


@cache
def earth_series() -> dict[int, Series]:
    """The L, B and R series (variables 1, 2, 3), read and verified once."""
    blocks: dict[int, list[list[tuple[float, float, float]]]] = {1: [], 2: [], 3: []}
    declared: dict[int, list[int]] = {1: [], 2: [], 3: []}
    current: list[tuple[float, float, float]] | None = None
    for line in astronomy_resource_text(
        VSOP87D_EARTH_FILE, VSOP87D_EARTH_SHA256
    ).splitlines():
        header = _HEADER.search(line)
        if header:
            variable, power, count = (int(value) for value in header.groups())
            if power != len(blocks[variable]):
                raise ValueError(f'VSOP87D variable {variable} series out of order.')
            current = []
            blocks[variable].append(current)
            declared[variable].append(count)
        elif line.strip():
            if current is None:
                raise ValueError('VSOP87D term before any series header.')
            # The last three fields are the amplitude A, phase B and frequency C.
            amplitude, phase, frequency = (float(value) for value in line.split()[-3:])
            current.append((amplitude, phase, frequency))
    series: dict[int, Series] = {}
    for variable, expected in VSOP87D_EARTH_TERM_COUNTS.items():
        counts = tuple(len(block) for block in blocks[variable])
        if counts != expected or tuple(declared[variable]) != expected:
            raise ValueError(
                f'VSOP87D variable {variable} has {counts} terms, expected {expected}.'
            )
        series[variable] = tuple(tuple(block) for block in blocks[variable])
    return series


def _evaluate(series: Series, tau: float) -> float:
    total = 0.0
    tau_power = 1.0
    for terms in series:
        partial = 0.0
        for amplitude, phase, frequency in terms:
            partial += amplitude * cos(phase + frequency * tau)
        total += partial * tau_power
        tau_power *= tau
    return total


def normalize_degrees(value: float) -> float:
    return value % 360.0


def earth_heliocentric_longitude_deg(tau: float) -> float:
    """L in degrees, for `tau` Julian millennia of TDB from J2000."""
    return normalize_degrees(_evaluate(earth_series()[1], tau) * DEG_PER_RAD)


def earth_heliocentric_lbr(tau: float) -> tuple[float, float, float]:
    """L and B in degrees and R in astronomical units, for `tau` Julian millennia of TDB from J2000."""
    series = earth_series()
    l_deg = normalize_degrees(_evaluate(series[1], tau) * DEG_PER_RAD)
    b_deg = _evaluate(series[2], tau) * DEG_PER_RAD
    r_au = _evaluate(series[3], tau)
    return l_deg, b_deg, r_au
