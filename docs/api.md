# API Reference

## Base

- Framework: FastAPI
- Local default: `http://127.0.0.1:8000`

## Endpoints

### `POST /api/four_pillars`

Computes solar time and Four Pillars from date/time using either explicit coordinates or city resolution.

#### Request body

Option A: explicit resolved location

```json
{
  "date": "1988-02-04",
  "time": "16:30:00",
  "location": {
    "timezone": "Asia/Shanghai",
    "longitude": 104.066,
    "latitude": 30.658,
    "fold": null
  },
  "conventions": {
    "zi_convention": "split_midnight",
    "hour_basis": "true_solar",
    "day_boundary_basis": "true_solar"
  },
  "birth_time_uncertainty_seconds": null
}
```

Option B: city and country

```json
{
  "date": "1988-02-04",
  "time": "16:30:00",
  "city": "Chengdu",
  "country": "China",
  "conventions": {
    "zi_convention": "split_midnight",
    "hour_basis": "true_solar",
    "day_boundary_basis": "true_solar"
  },
  "birth_time_uncertainty_seconds": null
}
```

#### Required fields

- `date` in `YYYY-MM-DD`
- `time` in `HH:MM` or `HH:MM:SS`
- either:
  - `location.timezone` (IANA), `location.longitude`, `location.latitude`
  - or `city` + `country`

#### Optional fields

- `location.fold` for DST fall-back ambiguity (`0` or `1`)
- `conventions` (defaults are applied when omitted)
- `birth_time_uncertainty_seconds`

#### Success response

- `solar_time`
  - `utc_time`
  - `local_mean_solar_time`
  - `true_solar_time`
  - `equation_of_time_minutes`
- `four_pillars`
  - `year`, `month`, `day`, `hour`
- `flags`
  - ambiguity and warning fields
- `engine`
  - engine and model metadata
- `resolved_location` (present when `city` + `country` mode is used)
  - `city`, `country`, `timezone`

### `POST /api/chart`

Legacy frontend chart endpoint for existing UI rendering payloads.

### `POST /api/hidden_stems`

Returns hidden stems for the four supplied pillar pairs.

#### Request body

```json
{
  "year_pillar": "丁卯",
  "month_pillar": "癸丑",
  "day_pillar": "己丑",
  "hour_pillar": "壬申"
}
```

Each pillar must be exactly two Chinese characters:
- first character: heavenly stem
- second character: earthly branch

#### Success response

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

## Errors

- `400` for invalid input, DST ambiguity without fold, DST nonexistent time, and convention validation errors
- `500` for unexpected internal errors

## Example `curl`

```bash
curl -X POST 'http://127.0.0.1:8000/api/four_pillars' \
  -H 'Content-Type: application/json' \
  -d '{
    "date": "1988-02-04",
    "time": "16:30:00",
    "location": {
      "timezone": "Asia/Shanghai",
      "longitude": 104.066,
      "latitude": 30.658
    }
  }'
```
