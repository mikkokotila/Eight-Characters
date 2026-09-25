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

Mode B resolves the name to the first geocoder match in that country, and
reports the place it used in `resolved_location`. Many places share a name
(the geocoder knows four places called Chengdu in China, two in Sichuan and two
in Jiangxi, up to 13° of longitude apart: about 53 minutes of true solar time),
so to compute for one particular place, send its coordinates in mode A, for
example a suggestion from `POST /api/location_suggest`.

Optional request fields:

- `conventions`
- `birth_time_uncertainty_seconds`
- `include_chart` (`false` by default)
- `include_hidden_stems` (`false` by default)
- `include_ten_gods` (`false` by default)
- `include_interactions` (`false` by default)
- `include_day_master_context` (`false` by default)
- `lang` (`fi` by default, used when `include_chart=true`)

Response always includes:

- `solar_time`
- `four_pillars`
- `flags`
- `engine`

Response conditionally includes:

- `resolved_location` (when city resolution mode is used): the place the name
  was resolved to, with the same `city`, `region`, `country`, `timezone`,
  `latitude` and `longitude` fields as a `POST /api/location_search` result
- `chart` (when `include_chart=true`)
- `hidden_stems` (when `include_hidden_stems=true`)
- `ten_gods` (when `include_ten_gods=true`)
- `interactions` (when `include_interactions=true`)
- `day_master_context` (when `include_day_master_context=true`)

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

#### Day Master context

Set `include_day_master_context: true` to request the context independently of
chart, hidden-stem, Ten Gods, or interaction enrichment. The response adds:

- `policy`: `natal_presence_v1`.
- `day_master`: `char`, `pinyin`, `element`, and `polarity`.
- `season`: `basis: traditional_month_branch_groups`, `name`, `element`,
  `month_branch` identity, and that branch's `hidden_stems` evidence.
- `roots`: every same-element hidden-stem occurrence, including repeated branches.
- `support`: separate `companions` and `resources` evidence arrays.

An evidence record contains `pillar`, `component` (`stem` or `hidden_stem`),
`branch`, `char`, `pinyin`, `element`, `polarity`, `qi_type`, and `ten_god`.
Visible records have `branch: null` and `qi_type: null`. Hidden records identify
their enclosing branch and `main`, `middle`, or `residual` qi position.
Roots additionally include `match: exact_stem` or `opposite_polarity`.
Records follow year/month/day/hour order, visible before hidden within a pillar.

For example, the canonical chart's first root is:

```json
{
  "pillar": "month", "component": "hidden_stem", "branch": "丑",
  "char": "己", "pinyin": "Ji", "element": "earth", "polarity": "Yin",
  "qi_type": "main", "ten_god": "friend", "match": "exact_stem"
}
```

No root means `roots: []`; no support means the corresponding array is empty.
The Day Master itself is excluded from companions. Hidden companions can be
the same occurrences as roots and must not be double-counted. Resource is not
a root. Season describes the resolved solar-month branch's traditional group,
not Gregorian-month weather or a within-month governing-qi estimate. The group
element, branch element, and hidden stems are deliberately distinct.

These are natal occurrence records, not strength weights, favorability ratings,
or applied transformations. See [Day Master context](Standard-Day-Master-Context.md)
for the policy and Standard-mode controls.

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

Success response (query `Chengdu`, first two of three suggestions):

```json
{
  "suggestions": [
    {
      "city": "Chengdu",
      "region": "Sichuan",
      "country": "China",
      "timezone": "Asia/Shanghai",
      "latitude": 30.66667,
      "longitude": 104.06667,
      "display": "Chengdu, Sichuan, China"
    },
    {
      "city": "Chengdu",
      "region": "Jiangxi",
      "country": "China",
      "timezone": "Asia/Shanghai",
      "latitude": 26.36828,
      "longitude": 115.34289,
      "display": "Chengdu, Jiangxi, China"
    }
  ]
}
```

Each suggestion is one geocoded place:

- `region` is the geocoder's first-level administrative region (province,
  state); `region` and `country` are empty strings when the geocoder has none.
- `display` joins `city`, `region` and `country`, leaving out empty parts
  (`Hong Kong` has neither).
- Places can share a name and a region (the third suggestion above is another
  `Chengdu, Jiangxi, China`, at 26.983, 114.207), so show the coordinates as
  well when the difference matters.
- To compute for the chosen place, send its `timezone`, `latitude` and
  `longitude` to `POST /api/four_pillars` or `POST /api/evolution_explorer` as
  `location`. Sending its `city` and `country` instead resolves the name again,
  and the first match may be a different place.

### `POST /api/location_search`

Resolves a city string into canonical location metadata.

Request:

```json
{
  "city": "Helsinki",
  "country": "Finland"
}
```

`country` is optional but recommended for disambiguation. The name resolves to
the first geocoder match (in `country`, when given); the response names the
place that was used.

Success response:

```json
{
  "resolved_location": {
    "city": "Helsinki",
    "region": "Uusimaa",
    "country": "Finland",
    "timezone": "Europe/Helsinki",
    "latitude": 60.16952,
    "longitude": 24.93545
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
    "include_day_master_context": true,
    "lang": "en"
  }'
```
