# Ba Zi Backend Task Tree

Execution board only.  
Source of truth for requirements remains `astrometrics-spec.md` and the full planning file `backend-implementation-workboard.md`.

---

## Status Model

- `todo`
- `in_progress`
- `blocked`
- `review`
- `done`

Rule: no ticket may move to `done` unless all validation gates pass.
Rule: update this board in the same change-set whenever ticket status changes.

---

## Dependency Order

`TKT-001 -> TKT-002 -> TKT-003 -> TKT-004 -> TKT-005 -> TKT-006 -> TKT-007 -> TKT-008 -> TKT-009 -> TKT-010 -> TKT-011 -> TKT-012 -> TKT-013 -> TKT-014 -> TKT-015 -> TKT-016 -> TKT-017 -> TKT-018 -> TKT-019 -> TKT-020 -> TKT-021 -> TKT-022 -> [TKT-023, TKT-024, TKT-025, TKT-026 in parallel] -> TKT-027 -> [TKT-028, TKT-029] -> TKT-030`

---

## Ticket Tree

### TKT-001 - Policy and scope codification
- Status: `done`
- Depends on: none
- Subtasks:
  - [x] encode D-001 to D-025 as enforceable policy rules
  - [x] define strict in-scope vs out-of-scope behaviors
  - [x] add decision traceability map
- Validation:
  - [x] one or more tests for each decision id

### TKT-002 - Module contracts and dependency graph
- Status: `done`
- Depends on: `TKT-001`
- Subtasks:
  - [x] define interfaces for core modules in section 6.1
  - [x] freeze public contracts and responsibilities
  - [x] verify acyclic dependency graph
- Validation:
  - [x] no circular dependencies

### TKT-003 - Embedded model/data package
- Status: `done`
- Depends on: `TKT-002`
- Subtasks:
  - [x] embed VSOP87D Earth series
  - [x] embed IAU 2000A nutation schema and coefficients
  - [x] embed IAU 2006 obliquity constants
  - [x] embed complete delta-T segments
  - [x] add leap-second metadata fields
- Validation:
  - [x] integrity checks pass
  - [x] Earth-not-EMB guard passes

### TKT-004 - Input contract and validation engine
- Status: `done`
- Depends on: `TKT-001`, `TKT-002`
- Subtasks:
  - [x] implement required and optional inputs from section 3.1
  - [x] implement range and timezone validation
  - [x] implement `utc_timestamp` alternate path
  - [x] implement high-latitude warning trigger
- Validation:
  - [x] all section 3.1 validation rules covered by tests

### TKT-005 - DST fold/gap resolver
- Status: `done`
- Depends on: `TKT-004`
- Subtasks:
  - [x] implement full wall-datetime round-trip fold/gap detection
  - [x] require explicit `fold` for ambiguous times
  - [x] reject nonexistent local times
- Validation:
  - [x] DST fall-back cases pass
  - [x] DST spring-forward rejection passes

### TKT-006 - UTC to TT conversion routing
- Status: `done`
- Depends on: `TKT-003`, `TKT-005`
- Subtasks:
  - [x] implement 1972 routing branch
  - [x] post-1972 UTC->TAI->TT path
  - [x] pre-1972 UT1 approx UTC + delta-T path
  - [x] expose conversion method metadata
- Validation:
  - [x] threshold edge tests pass

### TKT-007 - Exact decimal-year helper
- Status: `done`
- Depends on: `TKT-006`
- Subtasks:
  - [x] implement elapsed-seconds/total-seconds-in-year formula
  - [x] ensure leap-year correctness
- Validation:
  - [x] regression tests confirm exact method in use

### TKT-008 - VSOP87D Earth evaluator
- Status: `done`
- Depends on: `TKT-003`
- Subtasks:
  - [x] implement L/B/R series evaluation in tau
  - [x] normalize and return heliocentric coordinates
- Validation:
  - [x] deterministic epoch spot checks pass

### TKT-009 - Nutation and obliquity engine
- Status: `done`
- Depends on: `TKT-003`
- Subtasks:
  - [x] implement IAU 2000A argument accumulation and term sums
  - [x] implement IAU 2006 mean obliquity polynomial
  - [x] compute true obliquity
- Validation:
  - [x] unit and conversion tests pass

### TKT-010 - Apparent solar longitude assembly
- Status: `done`
- Depends on: `TKT-008`, `TKT-009`
- Subtasks:
  - [x] convert to geocentric coordinates
  - [x] apply aberration and nutation longitude correction
  - [x] normalize lambda_apparent to [0, 360)
- Validation:
  - [x] wraparound tests pass

### TKT-011 - EoT and true solar time module
- Status: `done`
- Depends on: `TKT-010`, `TKT-006`
- Subtasks:
  - [x] compute LMST
  - [x] compute RA with normalized atan2 result
  - [x] compute EoT with consistent aberration term
  - [x] compute TST as timezone-naive full datetime
- Validation:
  - [x] no `Z` suffix for LMST/TST serialization fields
  - [x] date rollover tests pass

### TKT-012 - Coarse-scan bracket finder
- Status: `done`
- Depends on: `TKT-010`
- Subtasks:
  - [x] implement outward scan for sign-change bracket
  - [x] support explicit max scan window
  - [x] return deterministic bracketing error on failure
- Validation:
  - [x] bracketing tests pass for all term targets

### TKT-013 - Brent root solver
- Status: `done`
- Depends on: `TKT-012`
- Subtasks:
  - [x] implement pure Python Brent method
  - [x] use `xtol = tolerance_seconds / 86400`
- Validation:
  - [x] convergence tests pass

### TKT-014 - Solar term solver and distance metrics
- Status: `done`
- Depends on: `TKT-013`, `TKT-010`
- Subtasks:
  - [x] compute exact crossing for target longitude
  - [x] compute nearest-boundary distance in seconds
- Validation:
  - [x] known-boundary tests pass

### TKT-015 - Year pillar assignment
- Status: `done`
- Depends on: `TKT-014`, `TKT-006`
- Subtasks:
  - [x] compute bazi year using exact Lichun crossing
  - [x] derive year stem/branch indices
- Validation:
  - [x] before/at/after boundary tests pass

### TKT-016 - Month pillar assignment
- Status: `done`
- Depends on: `TKT-010`, `TKT-015`
- Subtasks:
  - [x] map month branch by longitude ranges
  - [x] handle 345/15 wrap case
  - [x] derive month stem via Five Tigers rule
- Validation:
  - [x] all 12 ranges pass

### TKT-017 - Day pillar effective-date algorithm
- Status: `done`
- Depends on: `TKT-011`, `TKT-004`
- Subtasks:
  - [x] choose day basis datetime (`true_solar` or `civil`)
  - [x] apply `whole_zi_23` adjustment for 23:xx only
  - [x] compute JDN from effective date
  - [x] compute idx0 = (JDN - 11) % 60
- Validation:
  - [x] Appendix D anchors pass
  - [x] TST date divergence scenario passes

### TKT-018 - Hour pillar assignment
- Status: `done`
- Depends on: `TKT-017`, `TKT-011`
- Subtasks:
  - [x] choose hour basis datetime (`true_solar` or `civil`)
  - [x] map branch by 2-hour blocks
  - [x] derive stem via Five Rats rule from computed day stem
- Validation:
  - [x] branch interval map tests pass

### TKT-019 - Polarity checksum enforcement
- Status: `done`
- Depends on: `TKT-015`, `TKT-016`, `TKT-017`, `TKT-018`
- Subtasks:
  - [x] enforce stem parity equals branch parity for all pillars
  - [x] hard-fail on mismatch
- Validation:
  - [x] checksum applied across entire test suite

### TKT-020 - Ambiguity and alternative outputs
- Status: `done`
- Depends on: `TKT-014`, `TKT-015`, `TKT-016`, `TKT-017`, `TKT-018`
- Subtasks:
  - [x] compute model uncertainty and total uncertainty
  - [x] flag solar-term ambiguity near boundary
  - [x] emit alternative pillars for ambiguity and zi-window cases
- Validation:
  - [x] near-boundary and zi-window tests pass

### TKT-021 - Output schema assembly
- Status: `done`
- Depends on: `TKT-006`, `TKT-011`, `TKT-015`, `TKT-016`, `TKT-017`, `TKT-018`, `TKT-019`, `TKT-020`
- Subtasks:
  - [x] assemble complete Part IV schema
  - [x] include all mandatory intermediate fields
- Validation:
  - [x] schema conformance tests pass

### TKT-022 - Deterministic serialization
- Status: `done`
- Depends on: `TKT-021`
- Subtasks:
  - [x] apply numeric precision rules per field
  - [x] enforce sorted JSON keys
  - [x] enforce timestamp formatting policy
- Validation:
  - [x] fixed-env snapshot tests are byte-identical

### TKT-023 - HKO solar-term verification suite
- Status: `done`
- Depends on: `TKT-014`, `TKT-022`
- Subtasks:
  - [x] compile HKO term dataset fixture from accessible HKO XML archive years (2019-2028)
  - [x] run verification checks with documented thresholds and recorded statistics
- Validation:
  - [x] pass configured verification checks

### TKT-024 - Sexagenary day verification suite
- Status: `done`
- Depends on: `TKT-017`, `TKT-022`
- Subtasks:
  - [x] verify one full-year day cycle against independent reference implementation
  - [x] assert all Appendix D anchor dates
- Validation:
  - [x] all day-cycle checks pass

### TKT-025 - Cross-verification vs 6tail/lunar-python
- Status: `done`
- Depends on: `TKT-022`
- Subtasks:
  - [x] run 1000 random cases (1950-2050)
  - [x] classify discrepancies by root cause
- Validation:
  - [x] discrepancy report complete

### TKT-026 - Mandatory edge-case suite
- Status: `done`
- Depends on: `TKT-020`, `TKT-022`
- Subtasks:
  - [x] implement mandatory edge-case suite coverage
  - [x] include explicit regression for 1988-02-04 case
- Validation:
  - [x] edge-case test suite passes

### TKT-027 - Regression fixture freeze
- Status: `done`
- Depends on: `TKT-023`, `TKT-024`, `TKT-025`, `TKT-026`
- Subtasks:
  - [x] freeze all JSON outputs including intermediates
  - [x] add replay tests for fixture stability
- Validation:
  - [x] replay is byte-identical in fixed environment

### TKT-028 - Known limitation and warning surfacing
- Status: `done`
- Depends on: `TKT-022`
- Subtasks:
  - [x] enforce high-latitude warning behavior
  - [x] ensure unknown-birth-time handling guidance is documented for caller
  - [x] confirm limitation flags and notes are exposed in outputs/docs
- Validation:
  - [x] limitation behavior tests pass

### TKT-029 - Licensing and attribution compliance
- Status: `done`
- Depends on: `TKT-003`, `TKT-027`
- Subtasks:
  - [x] compile attribution requirements for all data sources
  - [x] produce distribution-ready attribution text
- Validation:
  - [x] compliance checklist complete with no gaps

### TKT-030 - Release readiness and traceability audit
- Status: `done`
- Depends on: `TKT-001` through `TKT-029`
- Subtasks:
  - [x] perform requirement-to-test traceability audit
  - [x] close or explicitly defer any open risks
  - [x] issue go/no-go recommendation
- Validation:
  - [x] every PRD requirement has implementation and evidence linkage

---

## Parallel Work Lanes

After `TKT-022`, run in parallel:
- lane A: `TKT-023`
- lane B: `TKT-024`
- lane C: `TKT-025`
- lane D: `TKT-026`

Then merge to `TKT-027`.

---

## Critical Blockers

Immediate `blocked` state if any of these occur:
- DST gap accepted without error
- ambiguous local time accepted without explicit fold
- polarity mismatch in any computed pillar
- boundary ambiguity suppressed instead of surfaced
- schema-required field missing from output
- verification suite below required thresholds

---

## Post-Completion Enhancements

- `ENH-001` Hidden stems lookup API
  - Status: `done`
  - Scope:
    - added `POST /api/hidden_stems`
    - loads lookup mapping from `artefacts/hidden-stems.csv`
    - validates four input pillar pairs
    - returns hidden stems per branch for year/month/day/hour
  - Validation:
    - endpoint tests added in `tests/test_api_hidden_stems_endpoint.py`
    - full suite pass after integration

---

## Progress Snapshot

- Completed: `TKT-001`, `TKT-002`, `TKT-003`, `TKT-004`, `TKT-005`, `TKT-006`, `TKT-007`, `TKT-008`, `TKT-009`, `TKT-010`, `TKT-011`, `TKT-012`, `TKT-013`, `TKT-014`, `TKT-015`, `TKT-016`, `TKT-017`, `TKT-018`, `TKT-019`, `TKT-020`, `TKT-021`, `TKT-022`, `TKT-023`, `TKT-024`, `TKT-025`, `TKT-026`, `TKT-027`, `TKT-028`, `TKT-029`, `TKT-030`
- In progress: none
- Blocked: none
- Ready next ticket: none

