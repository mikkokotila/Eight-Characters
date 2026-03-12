# API Reference

## Base

- Framework: FastAPI
- Local default: `http://127.0.0.1:8000`
- Content type: `application/json`

## Endpoints

### `POST /api/four_pillars`

Computes solar time and Four Pillars from date/time and location.

Request mode A (`location` provided):

```json
{
  "date": "1988-02-04",
  "time": "16:30:00",
  "location": {
    "timezone": "Asia/Shanghai",
    "longitude": 104.066,
    "latitude": 30.658,
    "fold": null
  }
}
```

Request mode B (`city` + `country` provided):

```json
{
  "date": "1988-02-04",
  "time": "16:30:00",
  "city": "Chengdu",
  "country": "China"
}
```

Optional request fields:

- `conventions`
- `birth_time_uncertainty_seconds`
- `include_chart` (`false` by default)
- `include_hidden_stems` (`false` by default)
- `lang` (`fi` by default, used when `include_chart=true`)

Response always includes:

- `solar_time`
- `four_pillars`
- `flags`
- `engine`

Response conditionally includes:

- `resolved_location` (when city resolution mode is used)
- `chart` (when `include_chart=true`)
- `hidden_stems` (when `include_hidden_stems=true`)

### `POST /api/chart`

Builds UI-ready chart payload from already computed pillar characters.

Request:

```json
{
  "date": "1988-02-04",
  "time": "16:30:00",
  "hour_stem": "壬",
  "hour_branch": "申",
  "day_stem": "己",
  "day_branch": "丑",
  "month_stem": "癸",
  "month_branch": "丑",
  "year_stem": "丁",
  "year_branch": "卯",
  "lang": "en"
}
```

Success response includes:

- `header`
- `pillars`

### `POST /api/hidden_stems`

Returns hidden stems for the provided four pillar pairs.

Request:

```json
{
  "year_pillar": "丁卯",
  "month_pillar": "癸丑",
  "day_pillar": "己丑",
  "hour_pillar": "壬申"
}
```

Success response:

```json
{
  "hidden_stems": {
    "year": {
      "pillar": "丁卯",
      "branch": "卯",
      "hidden_stems": [
        { "char": "乙", "element": "wood", "polarity": "Yin", "qi_type": "main" }
      ]
    },
    "month": {
      "pillar": "癸丑",
      "branch": "丑",
      "hidden_stems": [
        { "char": "己", "element": "earth", "polarity": "Yin", "qi_type": "main" },
        { "char": "癸", "element": "water", "polarity": "Yin", "qi_type": "middle" },
        { "char": "辛", "element": "metal", "polarity": "Yin", "qi_type": "residual" }
      ]
    }
  }
}
```

### `POST /api/location_suggest`

Returns autosuggest choices for city input.

Request:

```json
{
  "query": "Hels",
  "limit": 5
}
```

Success response:

```json
{
  "suggestions": [
    {
      "city": "Helsinki",
      "country": "Finland",
      "timezone": "Europe/Helsinki"
    }
  ]
}
```

### `POST /api/location_search`

Resolves a city string into canonical location metadata.

Request:

```json
{
  "city": "Helsinki",
  "country": "Finland"
}
```

`country` is optional but recommended for disambiguation.

Success response:

```json
{
  "resolved_location": {
    "city": "Helsinki",
    "country": "Finland",
    "timezone": "Europe/Helsinki"
  }
}
```

### `POST /api/evolution_explorer`

Builds evolution explorer graph data from birth input and returns control metadata.

Request (example):

```json
{
  "date": "1988-02-04",
  "time": "16:30",
  "city": "Helsinki",
  "country": "Finland",
  "particles": 24,
  "temperature_steps": 2,
  "sweeps_per_step": 1,
  "dbscan_eps": 0.08,
  "dbscan_min_samples": 1,
  "seed_mode": "fixed_42",
  "basin_index": 0,
  "flux_threshold": 0.0,
  "controls": {
    "main_view_controls": {
      "particles": { "value": 64 }
    },
    "evolution_reading_controls": {
      "scalar_constants": {
        "LAMBDA_MODE": { "value": 6.5 }
      }
    }
  }
}
```

Success response includes:

- `graph_data`
- `controls` (includes `ui_label` for each control)
- `resolved_seed`
- `resolved_location` (when city resolution mode is used)

### `GET /api/evolution_controls`

Returns evolution controls and defaults without running chart computation.

Success response includes:

- `controls.main_view_controls`
- `controls.evolution_reading_controls`
- `controls.input_convention_controls`

All controls returned by this endpoint are tunable through `POST /api/evolution_explorer`.

## Error Contract

All non-2xx API responses use this shape:

```json
{
  "detail": "Human-readable error message"
}
```

Common status codes:

- `400` invalid input, request schema validation errors, invalid stem/branch characters, unresolved city, DST ambiguity without `fold`, nonexistent local time, or convention validation errors
- `500` unexpected internal errors

## Example curl

```bash
curl -X POST 'http://127.0.0.1:8000/api/four_pillars' \
  -H 'Content-Type: application/json' \
  -d '{
    "date": "1988-02-04",
    "time": "16:30:00",
    "city": "Chengdu",
    "country": "China",
    "include_chart": true,
    "include_hidden_stems": true,
    "lang": "en"
  }'
```
