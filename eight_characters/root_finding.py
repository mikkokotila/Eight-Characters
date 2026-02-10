from typing import Callable


class BracketingError(ValueError):
    pass


def normalize_longitude_difference(diff_degrees: float) -> float:
    while diff_degrees > 180.0:
        diff_degrees -= 360.0
    while diff_degrees < -180.0:
        diff_degrees += 360.0
    return diff_degrees


def find_bracket(
    target_longitude_deg: float,
    seed_jd_tt: float,
    longitude_fn: Callable[[float], float],
    step_days: float = 0.25,
    max_steps: int = 30,
) -> tuple[float, float]:
    def f(jd_tt: float) -> float:
        lam = longitude_fn(jd_tt)
        return normalize_longitude_difference(lam - target_longitude_deg)

    seed_value = f(seed_jd_tt)
    if seed_value == 0.0:
        return (seed_jd_tt - step_days, seed_jd_tt + step_days)

    for i in range(1, max_steps + 1):
        jd_test = seed_jd_tt + i * step_days
        if f(jd_test) * seed_value < 0.0:
            return (seed_jd_tt + (i - 1) * step_days, jd_test)

    for i in range(1, max_steps + 1):
        jd_test = seed_jd_tt - i * step_days
        if f(jd_test) * seed_value < 0.0:
            return (jd_test, seed_jd_tt - (i - 1) * step_days)

    raise BracketingError(
        f'Could not bracket solar longitude {target_longitude_deg} within '
        f'±{max_steps * step_days} days of seed JD {seed_jd_tt}.'
    )


def brentq(
    func: Callable[[float], float],
    xa: float,
    xb: float,
    xtol: float = 1e-12,
    max_iter: int = 100,
) -> float:
    fa = func(xa)
    fb = func(xb)

    if fa == 0.0:
        return xa
    if fb == 0.0:
        return xb
    if fa * fb > 0.0:
        raise ValueError('Root is not bracketed.')

    a = xa
    b = xb
    c = a
    fc = fa
    d = b - a
    e = d

    for _ in range(max_iter):
        if fb * fc > 0.0:
            c = a
            fc = fa
            d = b - a
            e = d

        if abs(fc) < abs(fb):
            a, b, c = b, c, b
            fa, fb, fc = fb, fc, fb

        tol = xtol
        midpoint = 0.5 * (c - b)

        if abs(midpoint) <= tol or fb == 0.0:
            return b

        if abs(e) >= tol and abs(fa) > abs(fb):
            s = fb / fa
            if a == c:
                p = 2.0 * midpoint * s
                q = 1.0 - s
            else:
                q_ratio = fa / fc
                r_ratio = fb / fc
                p = s * (2.0 * midpoint * q_ratio * (q_ratio - r_ratio) - (b - a) * (r_ratio - 1.0))
                q = (q_ratio - 1.0) * (r_ratio - 1.0) * (s - 1.0)

            if p > 0.0:
                q = -q
            p = abs(p)

            min1 = 3.0 * midpoint * q - abs(tol * q)
            min2 = abs(e * q)
            if 2.0 * p < min(min1, min2):
                e = d
                d = p / q
            else:
                d = midpoint
                e = d
        else:
            d = midpoint
            e = d

        a = b
        fa = fb
        if abs(d) > tol:
            b += d
        else:
            b += tol if midpoint > 0.0 else -tol
        fb = func(b)

    raise ValueError('Brent solver did not converge within max_iter.')
