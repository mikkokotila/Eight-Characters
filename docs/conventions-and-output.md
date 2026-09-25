# Conventions and Output

## Convention Parameters

### `zi_convention`

- `split_midnight` (default)
- `whole_zi_23`

Controls day rollover treatment around `23:00`/midnight.

### `hour_basis`

- `true_solar` (default)
- `civil`

Controls which time system maps hour branches.

### `day_boundary_basis`

- `true_solar` (default)
- `civil`

Controls which datetime determines effective day for day pillar.

## Output Structure

Top-level response sections:

- `solar_time`
- `four_pillars`
- `flags`
- `engine`

### `four_pillars` object

Each pillar includes:
- `stem.index`
- `stem.chinese`
- `branch.index`
- `branch.chinese`
- `changes`: when the pillar last changed before the birth (`previous`) and
  when it next changes (`next`)

Year and month include boundary metadata and distance values.

#### `changes`

A change is an instant at which the engine's own rules, under the request's
conventions, give a different pillar. `previous` and `next` each give:

- `seconds`: the time between the birth and the change, in elapsed seconds of
  Terrestrial Time. It is never negative.
- `pillar`: the pillar on the far side of the change, with `stem` and `branch`
  as above.
- For the year and month, `term`: the solar term at which the pillar changes,
  such as `lichun_315` or `xiaohan_285`.
- For the day and hour, `clock`: the clock the conventions read for that change,
  `true_solar` or `civil`, and `clock_time`: what that clock shows at the change,
  to the second, such as `1988-02-04T15:00:00`.

The civil clock's daylight-saving jumps are changes wherever they give a
different pillar. The hour's stem follows the day's, so the hour pillar also
changes when the day does, even on the other clock.

## Warning and Ambiguity Flags

Typical fields:
- `zi_hour_window`
- `solar_term_ambiguous`
- `hour_boundary_proximity_seconds`
- `model_uncertainty_seconds`
- `high_latitude_warning`
- `alternative_pillars` (nullable)

## Astronomical Models

The year pillar changes at Lichun and the month pillar at the twelve jie: the
instants when the Sun's geocentric apparent ecliptic longitude reaches 315°, 345°,
15° … 285°. The engine computes that longitude with the models its `engine`
section names:

| `engine` field | Value | Model |
|---|---|---|
| `vsop87_series` | `VSOP87D_full_Earth` | The Earth's heliocentric L, B, R from all 2,425 terms of VSOP87 version D (Bretagnon & Francou 1988), as IMCCE publishes them in `VSOP87D.ear` |
| `nutation_model` | `IAU_2000A_R06` | Nutation in longitude and obliquity, 1,358 and 1,056 terms: IAU 2000A with the adjustments for the IAU 2006 precession (IERS Conventions 2010, Tables 5.3a and 5.3b) |
| `mean_obliquity_model` | `IAU_2006` | Mean obliquity of the ecliptic (Capitaine, Wallace & Chapront 2003) |
| `precession_model` | `IAU_2006` | General precession in longitude, for the equinox of date (same source) |
| `delta_t_model` | `Espenak_Meeus` | Before 1972, TT is UTC plus ΔT from the Espenak–Meeus polynomials; from 1972, TT − UTC is TAI − UTC from the leap-second table (`leap_second_table`) plus 32.184 s |

From VSOP87D to the apparent longitude:

1. The Sun's geometric longitude is the Earth's L + 180°, its latitude −B.
2. VSOP87's dynamical equinox of J2000 is tied to FK5: −0.09033″ in longitude,
   and a small latitude term (Meeus, *Astronomical Algorithms*, eq. 32.3).
3. VSOP87D carries positions to the equinox of date with the IAU 1976 rate of
   precession (Laskar 1986, as Bretagnon & Francou 1988 give it in section 4.3).
   The engine adds the IAU 2006 general precession in longitude less that one,
   0.300″ per century, so the longitude refers to the same equinox of date as the
   IAU 2006 obliquity and the R06 nutation.
4. Nutation in longitude and annual aberration (−20.4898″ / R) are added.

The mean Sun of the equation of time is referred to the same equinox, so true
solar time does not depend on how the equinox is carried.

Each Lichun and jie instant is found by Brent's method to 0.01 s of TT. It depends
only on the term and its year, so it is solved once and reused; a chart needs the
four jie nearest its birth.

The model tables are the published files, unmodified, in
`eight_characters/resources/astronomy/`, which lists their sources and SHA-256
checksums. The app reads and checks every table when it starts, and refuses to
start if one has changed. `validation.md` gives the measured accuracy.

## Numeric and Serialization Notes

- deterministic JSON output is used for regression stability
- sorted keys are enforced
- field-specific numeric precision is normalized in serialization
