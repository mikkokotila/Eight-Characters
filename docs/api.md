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
- `include_ten_gods` (`false` by default)
- `include_interactions` (`false` by default)
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
- `ten_gods` (when `include_ten_gods=true`)
- `interactions` (when `include_interactions=true`)

`ten_gods` gives, for each pillar, the ten god of its stem and of every
hidden stem of its branch, relative to the Day Master (the day stem). Hidden
stems keep the order and `qi_type` of the `hidden_stems` payload. Values are
`friend`, `rob_wealth`, `eating_god`, `hurting_officer`, `indirect_wealth`,
`direct_wealth`, `seven_killings`, `direct_officer`, `indirect_resource` and
`direct_resource`; the day stem itself is `day_master`. Example for the
`1988-02-04 16:30:00` Chengdu chart (month and day pillars omitted):

```json
{
  "ten_gods": {
    "year": {
      "pillar": "丁卯",
      "stem": { "char": "丁", "element": "fire", "polarity": "Yin", "ten_god": "indirect_resource" },
      "branch": "卯",
      "hidden_stems": [
        { "char": "乙", "element": "wood", "polarity": "Yin", "qi_type": "main", "ten_god": "seven_killings" }
      ]
    },
    "hour": {
      "pillar": "壬申",
      "stem": { "char": "壬", "element": "water", "polarity": "Yang", "ten_god": "direct_wealth" },
      "branch": "申",
      "hidden_stems": [
        { "char": "庚", "element": "metal", "polarity": "Yang", "qi_type": "main", "ten_god": "hurting_officer" },
        { "char": "壬", "element": "water", "polarity": "Yang", "qi_type": "middle", "ten_god": "direct_wealth" },
        { "char": "戊", "element": "earth", "polarity": "Yang", "qi_type": "residual", "ten_god": "rob_wealth" }
      ]
    }
  }
}
```

#### Natal relationships (`include_interactions`)

This independent, opt-in enrichment detects the five stem combinations, six
branch combinations, six branch clashes, and four complete three-harmony frames.
It compares the normalized natal pillars only; hidden stems do not create extra
stem combinations. It does not run Evolution inference or change any natal element.

Every matching occurrence is returned, including repeated and non-adjacent pairs.
A frame requires all three distinct branch members; incomplete sets are not emitted.
An empty array means no matches in this supported scope, not that the chart has no
other relationships. Records are ordered by shared rule index, then by natal
position (year, month, day, hour). Overlapping records are retained independently.

For the canonical `1988-02-04 16:30:00` Chengdu chart:

```json
{
  "interactions": [
    {
      "id": "stem_combination:4:year-hour",
      "kind": "stem_combination",
      "component": "stem",
      "members": [
        { "pillar": "year", "char": "丁", "pinyin": "Ding" },
        { "pillar": "hour", "char": "壬", "pinyin": "Ren" }
      ],
      "adjacent": false,
      "completeness": "pair",
      "potential_element": "wood",
      "transformation": "not_assessed"
    }
  ]
}
```

`kind` is `stem_combination`, `branch_combination`, `branch_clash`, or
`harmony_frame`. Each record identifies its `stem` or `branch` component and
all participating cards. `adjacent` means the participating pillars occupy
consecutive natal positions, independent of responsive screen layout.
`completeness` is `pair` or `complete` (a three-member frame).

`potential_element` is only a reference target for stem combinations and complete
frames. Branch-pair targets are not published because they vary by convention;
clashes have no target. Both use `null`. `transformation` is `not_assessed` for
combinations and frames, and `not_applicable` for clashes. No activation, strength,
transformation, favorable/unfavorable verdict, or life outcome is inferred.

The flag does not implicitly include `chart`, `hidden_stems`, or `ten_gods`;
request those separately. Existing response sections are unchanged.

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
    "include_ten_gods": true,
    "include_interactions": true,
    "lang": "en"
  }'
```
