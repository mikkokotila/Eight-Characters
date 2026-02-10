# Phase 4 Completion - Boundary Solving and Pillar Assignment

This artifact marks completion of Phase 4 (`TKT-012` to `TKT-018`):
- coarse bracketing and Brent solver
- solar-term boundary solve helpers
- year/month/day/hour pillar assignment logic

---

## Implemented Artifacts

- `eight_characters/root_finding.py`
  - angle-difference normalization helper
  - coarse-scan sign-change bracket finder
  - pure Python Brent root solver
- `eight_characters/solar_term_solver.py`
  - longitude-at-JD wrapper
  - solar-term root solve function with time-tolerance conversion
  - Lichun helper for civil year
  - nearest jie boundary distance helper
- `eight_characters/sexagenary.py`
  - Gregorian to JDN conversion
  - day index formula `idx0 = (JDN - 11) % 60`
  - year pillar from Lichun boundary comparison
  - month branch mapping from longitude including 345/15 wrap
  - month stem by Five Tigers rule
  - effective day date algorithm with basis and zi convention handling
  - hour branch mapping and hour stem by Five Rats rule
  - polarity validation checks on all pillar outputs

---

## Validation Coverage

- `tests/test_phase4_boundary_and_pillars.py`
  - bracket-finder behavior
  - Brent convergence behavior
  - nearest boundary distance conversion
  - year boundary before/after behavior
  - month wrap mapping behavior
  - JDN anchor dates and day-index anchor checks
  - effective date divergence and whole-zi adjustment behavior
  - hour branch mapping and basis selection behavior

---

## Ticket Closure

- `TKT-012`: done
- `TKT-013`: done
- `TKT-014`: done
- `TKT-015`: done
- `TKT-016`: done
- `TKT-017`: done
- `TKT-018`: done

Next ready ticket: `TKT-019`.

---

## Test Run Evidence

- Command: `python -m unittest discover -s tests -p 'test_*.py'`
- Result: `Ran 39 tests ... OK`

Phase 4 is complete and validated.
