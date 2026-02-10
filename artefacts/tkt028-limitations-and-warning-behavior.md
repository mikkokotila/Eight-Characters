# TKT-028 - Known Limitations and Warning Semantics

This document defines and verifies how the engine surfaces known limitations.

## Implemented Warning Semantics

- `high_latitude_warning`
  - set to `true` when latitude is above `66` or below `-66`
  - verified in:
    - `tests/test_phase2_time_normalization.py`
    - `tests/test_tkt026_mandatory_edge_cases.py`
- `zi_hour_window`
  - set when basis datetime falls in `23:00` or `00:xx`
  - verified in:
    - `tests/test_api_bazi_endpoint.py`
    - `tests/test_phase5_integrity_output.py`
- `solar_term_ambiguous`
  - set when nearest boundary distance is within configured uncertainty window
  - verified in:
    - `tests/test_phase5_integrity_output.py`

## Caller Guidance for Unknown Birth Time

- The API requires a full time input.
- For unknown birth time use a caller-level policy:
  - run with a best estimate
  - treat hour pillar as low-confidence
  - use year/month/day pillars primarily
- This behavior is intentionally caller-facing and not a hidden engine fallback.

## Residual Limitations

- External HKO archival availability currently provides XML term data for 2019-2028 at the discovered endpoint.
- Full 2000-2030 HKO term fixture expansion can be added when archival source files are available.
- Geocentric model and current kernel implementation are deterministic but not yet tuned to strict ±60s historical criterion across all available terms.
