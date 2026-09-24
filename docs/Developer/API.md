# API Endpoints (Developer)

## Goals

- Keep endpoint contracts explicit and stable.
- Ensure one consistent error shape for all API failures.
- Document cross-endpoint dependencies and frontend usage.

## Endpoint Inventory

### `POST /api/four_pillars`

- **Purpose**: canonical compute endpoint for solar time + Four Pillars.
- **Primary callers**: frontend submit flow and external API clients.
- **Input modes**:
  - explicit `location` (`timezone`, `longitude`, `latitude`, optional `fold`)
  - `city` + `country` (resolved through geocoding)
- **Optional enrichments**:
  - `include_chart=true` adds chart payload from `build_chart`
  - `include_hidden_stems=true` adds hidden stems payload from `_build_hidden_stems_result`
  - `include_ten_gods=true` adds ten gods payload from `_build_ten_gods_result`
    (stem and hidden stem ten gods relative to the Day Master)
- **Internal calls**:
  - `_resolve_four_pillars_location`
  - `_build_four_pillars_result`
  - (optional) `build_chart`
  - (optional) `_build_hidden_stems_result`
  - (optional) `_build_ten_gods_result`
- **Error behavior**:
  - `400` for user/input/time-validation errors
  - `500` for unexpected internal errors

### `POST /api/chart`

- **Purpose**: render payload endpoint for explicit pillar-character inputs.
- **Primary callers**: external clients that already have pillar characters.
- **Internal calls**: `build_chart`.
- **Validation**:
  - stem fields are validated against `STEMS`
  - branch fields are validated against `BRANCHES`
- **Error behavior**:
  - `400` with `detail` for invalid stem/branch values

### `POST /api/hidden_stems`

- **Purpose**: hidden stem expansion for four two-character pillars.
- **Primary callers**: external API clients and optional backend composition path.
- **Internal calls**: `_build_hidden_stems_result`.
- **Error behavior**:
  - `400` with `detail` for invalid pillar format/content

### `POST /api/location_suggest`

- **Purpose**: autosuggest while user types location text.
- **Primary callers**: frontend location input.
- **Internal calls**:
  - `_search_city_candidates`
  - `_city_models_from_result`
- **Notes**:
  - empty query returns `{"suggestions": []}` without error
- **Error behavior**:
  - `400` for invalid query params
  - `500` for unexpected failures

### `POST /api/location_search`

- **Purpose**: deterministic city resolution endpoint.
- **Primary callers**: currently external/programmatic clients (not required by current frontend flow).
- **Input**: `city` and optional `country`.
- **Internal calls**: `_resolve_city_location`.
- **Error behavior**:
  - `400` with `detail` when a city cannot be resolved
  - `500` for unexpected failures

## Mapping Data

- Canonical mapping assets live in `eight_characters/resources/mappings/`.
- Current tracked mappings:
  - `hidden-stems.csv`
  - `ten-gods.csv`
  - `stem-map.csv`
  - `branch-mapping.csv`
- Runtime hidden stems lookup in `eight_characters/main.py` reads from this directory first.
- Runtime ten gods lookup in `eight_characters/main.py` reads `ten-gods.csv`
  through `parse_ten_gods_mapping` (`eight_characters/ten_gods.py`). It rejects
  a malformed or incomplete table, and any cell that disagrees with the
  element-cycle derivation in `evolution.primitives.ten_god_index`, instead of
  skipping it. Both mappings load when `main` is imported, so a broken table
  stops the app at startup. `tests/test_api_ten_gods.py` also checks the table
  against the `lunar-python` reference.

## Frontend Flow

Current UI submit flow:

1. `POST /api/four_pillars` with:
   - `city`, `country`, `date`, `time`
   - `include_chart=true`
   - `include_hidden_stems=true`
   - `include_ten_gods=true`
2. Render chart from `response.chart`.
3. Render ten gods on the card backs from `response.ten_gods`.
4. Render hidden stems from `response.hidden_stems`.

Chart card interactions:

- Quick click on a branch card toggles its hidden stems panel.
- Holding any card for at least one second flips it to its ten god; branch
  cards list the ten god of every hidden stem, with their qi type. Holding
  again flips it back.

Location typing flow remains:

1. `POST /api/location_suggest` while user types.
2. User selects a suggestion (`city`, `country`, `timezone`).

## Error Contract (All Endpoints)

Non-2xx responses must be:

```json
{
  "detail": "Human-readable error message"
}
```

FastAPI request validation errors are normalized through a global
`RequestValidationError` handler and returned as `400` with this same payload
shape.
