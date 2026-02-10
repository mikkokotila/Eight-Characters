# Ba Zi Engine Backend Implementation Plan and Workboard

Derived from `astrometrics-spec.md` (v1.2, approved for implementation).  
This document is the execution artifact for engineering delivery, structured as:

- full end-to-end deterministic implementation plan
- ticket-by-ticket workboard with dependencies and validation gates

No step may proceed unless its validation gates pass.

---

## 1) End-to-End Deterministic Implementation Plan

### Phase 1: Governance and Architecture Baseline

#### Step 1: Freeze scope, decisions, and module boundaries
- Objective:
  - codify all binding PRD decisions as enforceable policy
  - define module interfaces before implementation
- Inputs:
  - Part II (D-001 to D-025)
  - Part VI module decomposition
  - Appendix C conventions matrix
- Outputs:
  - immutable engine policy object
  - explicit interface contracts for each module
  - conventions schema and defaults
- Deterministic rules:
  - no behavior outside 1949-2100
  - no non-Gregorian parsing in core
  - no interpretive outputs
  - no forbidden dependencies/models
- Validation gate:
  - policy tests for every decision id
  - interface dependency graph check: no cycles
- Completion criteria:
  - each decision id traceable to one executable rule or contract field

#### Step 2: Build embedded data and version metadata layer
- Objective:
  - ensure all required core data are embedded/versioned
- Inputs:
  - VSOP87D Earth series
  - IAU 2000A nutation coefficients and argument spec
  - IAU 2006 obliquity polynomial
  - Espenak-Meeus delta-T segments
  - IANA leap-second list metadata fields
- Outputs:
  - static data modules
  - metadata accessors for model and dataset versions
- Deterministic rules:
  - Earth series only, never EMB
  - fixed source metadata for leap table: source, last_update, expires
  - geocoding separate from core compute
- Validation gate:
  - dataset integrity tests (term counts/schemas)
  - Earth-vs-EMB guard test
- Completion criteria:
  - core can run offline with embedded astronomical/time data

### Phase 2: Time Normalization Core

#### Step 3: Implement input contract and civil-time resolution
- Objective:
  - map valid input to one UTC instant or reject with explicit error
- Inputs:
  - civil datetime + timezone (+ optional fold) or utc timestamp
  - latitude/longitude
  - conventions
- Outputs:
  - canonical UTC instant
  - normalized input model
  - warnings (for high latitude)
- Deterministic rules:
  - strict validation from section 3.1
  - fold/gap detection via full wall-datetime round-trip
  - utc timestamp mode bypasses local-time conversion
- Validation gate:
  - DST gap rejection tests
  - DST ambiguity tests requiring fold
  - timezone/id/range validation tests
  - utc timestamp mode tests
- Completion criteria:
  - every accepted input maps to exactly one UTC instant

#### Step 4: Implement UTC to TT conversion engine
- Objective:
  - produce TT correctly for both post-1972 and pre-1972 paths
- Inputs:
  - UTC instant
  - leap-second table
  - delta-T polynomial segments
- Outputs:
  - TT instant and TT Julian date
  - conversion method metadata
  - delta_t_seconds value
- Deterministic rules:
  - route at 1972-01-01T00:00:00Z
  - post-1972: UTC -> TAI -> TT
  - pre-1972: UT1 approx UTC, decimal year exact elapsed-fraction formula, then delta-T polynomial
- Validation gate:
  - 1972 boundary routing tests
  - segment polynomial tests, including 1941-1961 reference variable
  - sanity checks for representative epochs
- Completion criteria:
  - TT values stable and traceable to explicit path metadata

### Phase 3: Astronomical Computation Kernel

#### Step 5: Compute apparent geocentric solar longitude
- Objective:
  - produce lambda_apparent deterministically from TT
- Inputs:
  - TT Julian date
  - VSOP87D Earth coefficients
  - IAU 2000A nutation
  - IAU 2006 obliquity
- Outputs:
  - solar_longitude_deg
  - supporting intermediates: R, beta, delta_psi, delta_epsilon, epsilon
- Deterministic rules:
  - full VSOP87D series, no truncation
  - geocentric conversion and normalization to [0, 360)
  - aberration using -20.4898 arcseconds / R
  - apply nutation correction in longitude
- Validation gate:
  - spot checks at known epochs
  - wrap tests near 0/360 boundaries
- Completion criteria:
  - stable lambda_apparent consumable by boundary and month logic

#### Step 6: Compute LMST, EoT, and TST
- Objective:
  - produce true solar time basis for day/hour decisions
- Inputs:
  - UTC instant
  - longitude
  - apparent solar position outputs
- Outputs:
  - local_mean_solar_time
  - equation_of_time_minutes
  - true_solar_time (timezone-naive datetime)
- Deterministic rules:
  - LMST = UTC + longitude/15 hours
  - right ascension from atan2 with normalization
  - EoT uses consistent aberration form
  - TST is full datetime; no UTC labeling
- Validation gate:
  - date rollover tests (civil date differs from TST date)
  - timestamp format tests (no Z for LMST/TST)
- Completion criteria:
  - TST datetime reliable for convention-dependent pillar logic

### Phase 4: Boundary Solving and Pillar Assignment

#### Step 7: Implement solar-term root-finding
- Objective:
  - compute exact boundary crossing times robustly
- Inputs:
  - target longitudes
  - seed TT Julian date
  - lambda_apparent function
- Outputs:
  - exact boundary TT JD
  - nearest boundary distance in seconds
- Deterministic rules:
  - guaranteed bracket via coarse scan
  - Brent refinement with xtol = tolerance_seconds / 86400
  - angle difference normalization to [-180, 180]
- Validation gate:
  - all target longitudes converge
  - bad-seed resilience tests
  - tolerance behavior tests
- Completion criteria:
  - solver either converges from guaranteed bracket or returns explicit bracketing error

#### Step 8: Compute Year and Month pillars
- Objective:
  - assign year/month pillars from astronomical boundaries only
- Inputs:
  - birth TT
  - Lichun crossing TT
  - lambda_apparent at birth
  - year stem index
- Outputs:
  - year pillar
  - month pillar
  - boundary distance metadata
- Deterministic rules:
  - year boundary at exact 315 degree crossing
  - month branch via Appendix B half-open ranges (including 345/15 wrap)
  - month stem via Five Tigers mapping
- Validation gate:
  - at/before/after boundary cases
  - all 12 month interval mapping tests
- Completion criteria:
  - year/month assignments independent of lunar calendar conventions

#### Step 9: Compute Day and Hour pillars with convention matrix
- Objective:
  - assign day/hour pillars for all convention combinations
- Inputs:
  - civil datetime
  - TST datetime
  - zi convention
  - day boundary basis
  - hour basis
- Outputs:
  - day pillar
  - hour pillar
  - effective_day_date
  - zi window flag
- Deterministic rules:
  - compute effective date from selected basis datetime
  - whole zi day increment only for 23:xx
  - idx0 = (JDN - 11) % 60
  - Five Rats mapping from computed day stem
- Validation gate:
  - Appendix D anchors
  - 23:00, 00:00, 00:59 behavior tests
  - TST vs civil divergence scenario tests
- Completion criteria:
  - all 8 combinations produce deterministic, explainable differences only where expected

### Phase 5: Integrity, Output Contract, and Verification

#### Step 10: Apply integrity checks and ambiguity handling
- Objective:
  - enforce checksums and make uncertainty explicit
- Inputs:
  - computed pillars
  - boundary distances
  - model uncertainty
  - optional birth-time uncertainty
- Outputs:
  - flags object
  - alternative_pillars when needed
- Deterministic rules:
  - polarity check on all pillars
  - total uncertainty = max(model uncertainty, user uncertainty when supplied)
  - return both pillar options if inside ambiguity window
- Validation gate:
  - polarity checks across all tests
  - near-boundary ambiguity tests
  - zi window alternative output tests
- Completion criteria:
  - no silent canonical single-output when ambiguity threshold is met

#### Step 11: Implement deterministic JSON output contract
- Objective:
  - serialize complete output exactly to schema and formatting rules
- Inputs:
  - normalized input, intermediates, pillars, flags, metadata
- Outputs:
  - final JSON payload
- Deterministic rules:
  - all mandatory fields included
  - precision rules per field
  - sorted keys
  - timestamp labeling rules (Z for UTC only)
- Validation gate:
  - schema conformance tests
  - precision/format tests
  - snapshot byte-identity tests in fixed environment
- Completion criteria:
  - output conforms exactly to Part IV and determinism scope in Part VI

#### Step 12: Full verification, fixture freeze, and compliance
- Objective:
  - prove implementation completeness and release readiness
- Inputs:
  - full engine
  - HKO solar-term dataset
  - HKO cyclical day dataset
  - random test generator
  - reference implementation integration (6tail/lunar-python)
- Outputs:
  - passing verification suite
  - discrepancy report with root-cause tags
  - frozen regression fixtures
  - attribution/license compliance checklist
- Deterministic rules:
  - 744 solar-term checks for 2000-2030
  - day-cycle verification + anchor dates
  - 1000 random cross-verification runs
  - all mandatory edge cases from Part V
- Validation gate:
  - all required suites green
  - fixtures committed and stable
  - compliance checklist complete
- Completion criteria:
  - implementation marked PRD-complete and regression-locked

---

## 2) Ticket-by-Ticket Workboard

Use statuses: `todo`, `in_progress`, `blocked`, `review`, `done`.  
Each ticket has hard dependency gates.  
`DoR` = definition of ready, `DoD` = definition of done.

### TKT-001: Policy and scope codification
- Status: `todo`
- Depends on: none
- DoR:
  - PRD v1.2 locked
- Scope:
  - encode D-001..D-025 as policy constants/rules
  - define explicit out-of-scope behaviors
- Deliverables:
  - policy module
  - policy test suite
  - decision trace matrix
- Validation:
  - each D-id has at least one passing enforcement test
- DoD:
  - zero uncovered decision ids
- References:
  - Part II, Part VII high-level constraints

### TKT-002: Module interface and dependency graph contract
- Status: `todo`
- Depends on: TKT-001
- DoR:
  - policy module merged
- Scope:
  - define interfaces for time_convert, vsop87d, nutation, obliquity, solar_position, root_finding, solar_term_solver, sexagenary, output, engine, conventions
- Deliverables:
  - interface definitions
  - dependency graph document
- Validation:
  - static check: no circular dependencies
- DoD:
  - all downstream tickets consume these interfaces without ambiguity
- References:
  - Part VI section 6.1

### TKT-003: Embedded model/data packaging
- Status: `todo`
- Depends on: TKT-002
- DoR:
  - module boundaries approved
- Scope:
  - package VSOP87D Earth, nutation data schema, obliquity constants, delta-T segments, leap-second metadata layer
- Deliverables:
  - data modules
  - integrity tests
- Validation:
  - Earth-vs-EMB guard test
  - expected term count checks
- DoD:
  - all data loaded from embedded source only
- References:
  - D-006, D-007, D-007a, D-008, D-016, App A/F

### TKT-004: Input schema and validation engine
- Status: `todo`
- Depends on: TKT-001, TKT-002
- DoR:
  - conventions enum finalized
- Scope:
  - required/optional input handling
  - range and timezone validation
  - alternate utc input mode
- Deliverables:
  - input parser/validator
  - explicit error catalog
- Validation:
  - invalid ranges/timezone tests
  - high-lat warning test
- DoD:
  - all validation rules in section 3.1 covered by tests
- References:
  - section 3.1

### TKT-005: DST fold/gap resolver
- Status: `todo`
- Depends on: TKT-004
- DoR:
  - input validator merged
- Scope:
  - implement PEP 495 fold/gap detection via full round-trip wall datetime
- Deliverables:
  - resolver function
  - DST scenario tests
- Validation:
  - fall-back ambiguity requires fold
  - spring-forward nonexistent time rejected
- DoD:
  - no silent acceptance of invalid local times
- References:
  - section 3.2.1, v1.2 fix note

### TKT-006: UTC to TT conversion routing
- Status: `todo`
- Depends on: TKT-003, TKT-005
- DoR:
  - leap and delta-T data layer available
- Scope:
  - route by 1972 threshold
  - post-1972 UTC->TAI->TT
  - pre-1972 UT1 approx UTC + delta-T
- Deliverables:
  - time-scale conversion module
  - conversion path metadata fields
- Validation:
  - threshold edge tests
  - known epoch numeric checks
- DoD:
  - deterministic TT output with path annotation
- References:
  - section 3.3, D-013

### TKT-007: Decimal year exact implementation
- Status: `todo`
- Depends on: TKT-006
- DoR:
  - UTC handling complete
- Scope:
  - elapsed-seconds over total-seconds-of-year formula
- Deliverables:
  - decimal year helper
  - leap-year correctness tests
- Validation:
  - compare against month-based approximation to ensure expected divergence
- DoD:
  - exact formula in use for pre-1972 path
- References:
  - section 3.3.4, v1.2 fix

### TKT-008: VSOP87D Earth evaluator
- Status: `todo`
- Depends on: TKT-003
- DoR:
  - coefficients embedded
- Scope:
  - evaluate full L/B/R series in tau domain
- Deliverables:
  - vsop87d module
  - unit tests for coordinate outputs
- Validation:
  - normalization and regression checks
- DoD:
  - returns deterministic heliocentric Earth coordinates
- References:
  - section 3.4.1-3.4.3, D-006

### TKT-009: Nutation and obliquity engine
- Status: `todo`
- Depends on: TKT-003
- DoR:
  - coefficient schema validated
- Scope:
  - IAU 2000A argument and term accumulation
  - IAU 2006 mean obliquity
- Deliverables:
  - nutation module
  - obliquity module
- Validation:
  - argument normalization tests
  - conversion-unit tests
- DoD:
  - deterministic delta_psi, delta_epsilon, epsilon outputs
- References:
  - section 3.4.5, App F

### TKT-010: Apparent solar longitude assembly
- Status: `todo`
- Depends on: TKT-008, TKT-009
- DoR:
  - vsop and nutation outputs available
- Scope:
  - geocentric conversion + aberration + nutation longitude correction
- Deliverables:
  - solar_position longitude function
- Validation:
  - boundary wrap tests near 0/360
- DoD:
  - lambda_apparent stable across test epochs
- References:
  - section 3.4.4-3.4.6

### TKT-011: EoT and true solar time engine
- Status: `todo`
- Depends on: TKT-010, TKT-006
- DoR:
  - lambda_apparent and TT available
- Scope:
  - RA calculation, EoT formula, LMST and TST datetime pipeline
- Deliverables:
  - EoT/TST module
  - format-safe datetime representations
- Validation:
  - atan2 normalization tests
  - no Z suffix tests for LMST/TST outputs
- DoD:
  - TST available as timezone-naive datetime with correct date rollover
- References:
  - section 3.5, section 4.3

### TKT-012: Coarse-scan bracket finder
- Status: `todo`
- Depends on: TKT-010
- DoR:
  - lambda function exposed
- Scope:
  - outward scanning bracket guarantee
- Deliverables:
  - bracket-finder utility
- Validation:
  - catches sign change in configured scan window
  - explicit bracketing error coverage
- DoD:
  - root finding never starts without valid bracket
- References:
  - section 3.7.1

### TKT-013: Brent solver implementation
- Status: `todo`
- Depends on: TKT-012
- DoR:
  - bracket finder merged
- Scope:
  - pure Python Brent method
  - tolerance conversion in time units
- Deliverables:
  - root-finding module
- Validation:
  - convergence tests on representative functions and solar-term roots
- DoD:
  - solver converges within configured tolerance
- References:
  - D-010, section 3.7.2

### TKT-014: Solar-term solver and nearest-boundary distance
- Status: `todo`
- Depends on: TKT-013, TKT-010
- DoR:
  - solver and lambda available
- Scope:
  - term crossing solver
  - nearest-boundary distance computation (seconds)
- Deliverables:
  - solar_term_solver module
- Validation:
  - known-term crossing tests
- DoD:
  - boundary times consumable by year/month and ambiguity layers
- References:
  - section 3.7

### TKT-015: Year pillar assignment
- Status: `todo`
- Depends on: TKT-014, TKT-006
- DoR:
  - Lichun crossing function available
- Scope:
  - bazi year derivation by 315 crossing instant
- Deliverables:
  - year pillar function
- Validation:
  - before/at/after Lichun tests
- DoD:
  - year stem/branch always parity-valid
- References:
  - section 3.6.2, D-020

### TKT-016: Month pillar assignment
- Status: `todo`
- Depends on: TKT-010, TKT-015
- DoR:
  - year stem from year pillar available
- Scope:
  - branch from longitude intervals
  - stem via Five Tigers mapping
- Deliverables:
  - month pillar function
- Validation:
  - 12 interval tests + 345/15 wrap test
- DoD:
  - month stem/branch deterministic and parity-valid
- References:
  - section 3.6.3, Appendix B, D-021

### TKT-017: Day pillar effective-date algorithm
- Status: `todo`
- Depends on: TKT-011, TKT-004
- DoR:
  - civil and TST datetimes available
- Scope:
  - basis datetime selection
  - whole-zi adjustment on 23 hour
  - JDN and idx0 computation
- Deliverables:
  - day pillar function
  - effective_day_date output field
- Validation:
  - Appendix D anchors
  - TST date divergence scenario
- DoD:
  - day pillar follows basis datetime date exactly
- References:
  - section 3.6.4, D-018, D-019, D-022

### TKT-018: Hour pillar assignment
- Status: `todo`
- Depends on: TKT-017, TKT-011
- DoR:
  - day stem available
- Scope:
  - branch mapping by selected hour basis
  - stem via Five Rats mapping
- Deliverables:
  - hour pillar function
- Validation:
  - all 12 branch intervals
  - split/whole zi expectations through effective day logic
- DoD:
  - hour pillar deterministic with no extra hidden day adjustments
- References:
  - section 3.6.5

### TKT-019: Polarity checksum enforcement
- Status: `todo`
- Depends on: TKT-015, TKT-016, TKT-017, TKT-018
- DoR:
  - four pillar functions complete
- Scope:
  - parity validation across all pillars
- Deliverables:
  - assertion/check module
  - hard-fail behavior for mismatches
- Validation:
  - polarity checks run across all test vectors
- DoD:
  - any mismatch immediately surfaces as defect
- References:
  - section 3.6.6, section 5.5

### TKT-020: Ambiguity and alternative pillar generation
- Status: `todo`
- Depends on: TKT-014, TKT-015, TKT-016, TKT-017, TKT-018
- DoR:
  - boundary distance and all pillar calculators available
- Scope:
  - compute model uncertainty
  - apply optional user uncertainty override logic
  - populate alternative_pillars for zi and term ambiguity cases
- Deliverables:
  - flags + alternative output module
- Validation:
  - near-boundary synthetic tests
  - zi window dual-output tests
- DoD:
  - ambiguity never hidden from output
- References:
  - D-025, section 3.7.3, section 4.2, section 7.1

### TKT-021: Output schema assembly
- Status: `todo`
- Depends on: TKT-006, TKT-011, TKT-015..TKT-020
- DoR:
  - all intermediate and final outputs available
- Scope:
  - build full JSON object from Part IV schema
- Deliverables:
  - output assembler
  - schema validator tests
- Validation:
  - mandatory fields present
  - structural contract checks
- DoD:
  - output exactly matches required schema shape
- References:
  - section 4.1

### TKT-022: Deterministic numeric and timestamp serialization
- Status: `todo`
- Depends on: TKT-021
- DoR:
  - assembled output object available
- Scope:
  - precision rules
  - sorted keys
  - UTC-only Z suffix policy
- Deliverables:
  - serialization utility
  - snapshot tests in fixed environment
- Validation:
  - precision-field assertions
  - LMST/TST formatting checks
- DoD:
  - byte-identical output for fixed environment scope
- References:
  - section 4.3, section 6.3

### TKT-023: HKO solar-term verification suite
- Status: `todo`
- Depends on: TKT-014, TKT-022
- DoR:
  - solver and serialization stable
- Scope:
  - run 744 checks (2000-2030, 24 terms/year), tolerance ±60s against HKO
- Deliverables:
  - solar-term fixture file
  - verification tests and report
- Validation:
  - full suite pass
- DoD:
  - meets PRD acceptance threshold for published term times
- References:
  - section 5.1

### TKT-024: Sexagenary day verification suite
- Status: `todo`
- Depends on: TKT-017, TKT-022
- DoR:
  - day pillar stable
- Scope:
  - one full-year daily verification from HKO almanac data
  - anchor date assertions
- Deliverables:
  - day-cycle fixtures
  - verification tests
- Validation:
  - all daily checks pass
- DoD:
  - day formula confidence proven against external references
- References:
  - section 5.2, Appendix D

### TKT-025: Cross-verification with 6tail/lunar-python
- Status: `todo`
- Depends on: TKT-022
- DoR:
  - engine pipeline stable
- Scope:
  - compare 1000 random dates (1950-2050)
  - classify discrepancies by expected causes
- Deliverables:
  - comparison harness
  - discrepancy analysis report
- Validation:
  - 1000-run completion with categorized outcomes
- DoD:
  - all mismatches explained or logged as defects
- References:
  - section 5.3

### TKT-026: Mandatory edge-case suite
- Status: `todo`
- Depends on: TKT-020, TKT-022
- DoR:
  - ambiguity logic and final output integrated
- Scope:
  - implement all mandatory edge cases listed in Part V
- Deliverables:
  - edge-case tests
- Validation:
  - all listed scenarios pass
- DoD:
  - no uncovered mandatory edge case remains
- References:
  - section 5.4

### TKT-027: Regression fixture freeze
- Status: `todo`
- Depends on: TKT-023, TKT-024, TKT-025, TKT-026
- DoR:
  - verification suites green
- Scope:
  - freeze full JSON outputs including intermediates
- Deliverables:
  - fixture pack
  - fixture replay tests
- Validation:
  - byte-identical replay for fixed environment
- DoD:
  - regression baseline established
- References:
  - section 5.6, section 6.3

### TKT-028: Limitations surfacing and warning semantics
- Status: `todo`
- Depends on: TKT-022
- DoR:
  - final output object stabilized
- Scope:
  - ensure warnings/limitations are surfaced per PRD
- Deliverables:
  - warning policy tests
  - documentation for consumer behavior
- Validation:
  - high-latitude warning coverage
  - unknown-hour handling guidance present
- DoD:
  - all known limitation fields and notes represented
- References:
  - Part VII

### TKT-029: Licensing and attribution compliance
- Status: `todo`
- Depends on: TKT-003, TKT-027
- DoR:
  - data sources finalized
- Scope:
  - compile attribution and license checklist for all embedded/distributed data
- Deliverables:
  - compliance checklist artifact
  - distribution attribution text
- Validation:
  - checklist complete and reviewed
- DoD:
  - release blocked if any attribution requirement missing
- References:
  - Appendix E

### TKT-030: Release readiness review
- Status: `todo`
- Depends on: TKT-001..TKT-029
- DoR:
  - all prior tickets done
- Scope:
  - final traceability audit PRD -> implementation -> tests
  - unresolved risk log closure
- Deliverables:
  - readiness report
  - go/no-go recommendation
- Validation:
  - every requirement mapped to implementation and passing test evidence
- DoD:
  - project marked implementation-ready with no unresolved critical gaps
- References:
  - full PRD, Appendix G

---

## 3) Global Dependency Sequence

`TKT-001 -> TKT-002 -> TKT-003 -> TKT-004 -> TKT-005 -> TKT-006 -> TKT-007 -> TKT-008 -> TKT-009 -> TKT-010 -> TKT-011 -> TKT-012 -> TKT-013 -> TKT-014 -> TKT-015 -> TKT-016 -> TKT-017 -> TKT-018 -> TKT-019 -> TKT-020 -> TKT-021 -> TKT-022 -> TKT-023/TKT-024/TKT-025/TKT-026 -> TKT-027 -> TKT-028/TKT-029 -> TKT-030`

Parallel-safe lane after TKT-022:
- TKT-023, TKT-024, TKT-025, TKT-026 can run in parallel

---

## 4) Hard Gates and Stop Conditions

- Gate A: no ticket starts without dependency closure and DoR check.
- Gate B: no logic ticket closes without explicit tests proving deterministic behavior.
- Gate C: no output ticket closes without schema and serialization snapshot pass.
- Gate D: no release without complete verification suites and fixture freeze.
- Gate E: any polarity violation, DST silent acceptance, or boundary ambiguity suppression is a hard blocker.

---

## 5) Traceability Matrix (Concise)

- Scope and decisions: Part II -> TKT-001, TKT-030
- Input/time pipeline: section 3.1-3.3 -> TKT-004..TKT-007
- Astronomy core: section 3.4-3.5 + App F -> TKT-008..TKT-011
- Root finding and boundaries: section 3.7 -> TKT-012..TKT-014
- Pillars: section 3.6 + App B/D -> TKT-015..TKT-020
- Output contract: Part IV -> TKT-021..TKT-022
- Verification: Part V -> TKT-023..TKT-027
- Limitations and compliance: Part VII + App E -> TKT-028..TKT-029
- Final audit: full document + Appendix G deltas -> TKT-030

---

## 6) Workboard Operating Rules

- All tickets must include:
  - implementation notes
  - test evidence link
  - traceability ids
  - unresolved risks (if any)
- Any ticket with failing validation automatically moves to `blocked`.
- Any spec interpretation uncertainty must be raised before merge and linked to affected section id.
- No silent fallback behavior is permitted for time resolution, boundary decisions, or convention branching.

---

Prepared for deterministic backend implementation execution against `astrometrics-spec.md` v1.2.
