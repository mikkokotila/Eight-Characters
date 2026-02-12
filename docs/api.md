# API Reference

## Base

- Framework: FastAPI
- Local default: `http://127.0.0.1:8000`

## Endpoints

### `POST /api/bazi`

Computes solar time and Four Pillars from date, time, and location.

#### Request body

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

#### Required fields

- `date` in `YYYY-MM-DD`
- `time` in `HH:MM` or `HH:MM:SS`
- `location.timezone` (IANA, for example `Asia/Shanghai`)
- `location.longitude` in `[-180, 180]`
- `location.latitude` in `[-90, 90]`

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
    "year": { "pillar": "丁卯", "branch": "卯", "hidden_stems": ["乙"] },
    "month": { "pillar": "癸丑", "branch": "丑", "hidden_stems": ["己", "癸", "辛"] },
    "day": { "pillar": "己丑", "branch": "丑", "hidden_stems": ["己", "癸", "辛"] },
    "hour": { "pillar": "壬申", "branch": "申", "hidden_stems": ["庚", "壬", "戊"] }
  }
}
```

## Errors

- `400` for invalid input, DST ambiguity without fold, DST nonexistent time, and convention validation errors
- `500` for unexpected internal errors

## Example `curl`

```bash
curl -X POST 'http://127.0.0.1:8000/api/bazi' \
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
