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

Year and month include boundary metadata and distance values.

## Warning and Ambiguity Flags

Typical fields:
- `zi_hour_window`
- `solar_term_ambiguous`
- `hour_boundary_proximity_seconds`
- `model_uncertainty_seconds`
- `high_latitude_warning`
- `alternative_pillars` (nullable)

## Numeric and Serialization Notes

- deterministic JSON output is used for regression stability
- sorted keys are enforced
- field-specific numeric precision is normalized in serialization
