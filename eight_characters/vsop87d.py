from dataclasses import dataclass
from math import cos, pi


DEG_PER_RAD = 180.0 / pi


@dataclass(frozen=True)
class VsopTerm:
    amplitude: float
    phase: float
    frequency: float


# Seed subset organized in VSOP87D form. The evaluator is full-series capable.
# Coefficient expansion to full published table is a data-pack task.
L_SERIES: tuple[tuple[VsopTerm, ...], ...] = (
    (
        VsopTerm(1.75347045673, 0.0, 0.0),
        VsopTerm(0.03341656456, 4.66925680417, 6283.0758499914),
        VsopTerm(0.00034894275, 4.62610241759, 12566.1516999828),
        VsopTerm(0.00003417571, 2.82886579606, 3.523118349),
        VsopTerm(0.00003497056, 2.74411800971, 5753.3848848968),
        VsopTerm(0.00003135899, 3.62767041756, 77713.7714681205),
    ),
    (
        VsopTerm(6283.31966747491, 0.0, 0.0),
        VsopTerm(0.00206058863, 2.67823455584, 6283.0758499914),
        VsopTerm(0.0000430343, 2.63512650414, 12566.1516999828),
        VsopTerm(0.00000425264, 1.59046980729, 3.523118349),
    ),
    (
        VsopTerm(0.0005291887, 0.0, 0.0),
        VsopTerm(0.00008719837, 1.07209665242, 6283.0758499914),
        VsopTerm(0.00000309125, 0.86728818832, 12566.1516999828),
    ),
    (
        VsopTerm(0.00000289226, 5.84384198723, 6283.0758499914),
        VsopTerm(0.00000034955, 0.0, 0.0),
    ),
    (
        VsopTerm(0.00000114084, 3.14159265359, 0.0),
    ),
    (
        VsopTerm(0.00000000878, 3.14159265359, 0.0),
    ),
)

B_SERIES: tuple[tuple[VsopTerm, ...], ...] = (
    (
        VsopTerm(0.0000027962, 3.19870156017, 84334.6615813083),
        VsopTerm(0.00000101643, 5.42248619256, 5507.5532386674),
        VsopTerm(0.00000080445, 3.88013204458, 5223.6939198022),
    ),
    (
        VsopTerm(0.0000000903, 3.8972906189, 5507.5532386674),
        VsopTerm(0.00000006177, 1.73038850355, 5223.6939198022),
    ),
)

R_SERIES: tuple[tuple[VsopTerm, ...], ...] = (
    (
        VsopTerm(1.00013988799, 0.0, 0.0),
        VsopTerm(0.01670699626, 3.09846350771, 6283.0758499914),
        VsopTerm(0.00013956024, 3.0552460962, 12566.1516999828),
        VsopTerm(0.0000308372, 5.19846674381, 77713.7714681205),
    ),
    (
        VsopTerm(0.00103018608, 1.10748968172, 6283.0758499914),
        VsopTerm(0.00001721238, 1.06442301418, 12566.1516999828),
    ),
    (
        VsopTerm(0.00004359385, 5.78455133738, 6283.0758499914),
    ),
)


def normalize_degrees(value: float) -> float:
    return value % 360.0


def _evaluate_series(series: tuple[tuple[VsopTerm, ...], ...], tau: float) -> float:
    total = 0.0
    for power, terms in enumerate(series):
        partial = 0.0
        for term in terms:
            partial += term.amplitude * cos(term.phase + term.frequency * tau)
        total += partial * (tau ** power)
    return total


def earth_heliocentric_lbr(tau: float) -> tuple[float, float, float]:
    l_rad = _evaluate_series(L_SERIES, tau)
    b_rad = _evaluate_series(B_SERIES, tau)
    r_au = _evaluate_series(R_SERIES, tau)

    l_deg = normalize_degrees(l_rad * DEG_PER_RAD)
    b_deg = b_rad * DEG_PER_RAD
    return l_deg, b_deg, r_au
