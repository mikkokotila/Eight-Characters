# API Reference

## Base

- Framework: FastAPI
- Local default: `http://127.0.0.1:8000`
- Content type: `application/json`

## Accounts

Charts need a signed-in account: `POST /api/four_pillars`, `POST /api/chart`,
`POST /api/hidden_stems`, `POST /api/evolution_explorer`, `GET /api/today` and
`POST /api/today` answer `401` (`{"detail": "Sign in to continue."}`) without one,
before the request is validated. The first chart, `POST /api/first_chart`, is for
someone without one, a limited number an hour per client. The place search,
`GET /api/evolution_controls` and `GET /api/schools` need none.

A session is the cookie the page gets when signing in (`__Host-ec_session` over HTTPS,
`ec_session` on a laptop's plain HTTP). Signing in, and the account itself, are
`/api/account`, described in [Accounts](Developer/Accounts.md#the-api).

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

- `gender` (`male` or `female`; required when requesting luck pillars)
- `include_luck_pillars` (`false` by default)
- `luck_pillar_count` (strict integer 1-12, default 10)
- `include_luck_context` (`false` by default; requires `include_luck_pillars`)
- `conventions`
- `birth_time_uncertainty_seconds`
- `include_chart` (`false` by default)
- `include_hidden_stems` (`false` by default)
- `include_ten_gods` (`false` by default)
- `include_interactions` (`false` by default)
- `include_day_master_context` (`false` by default)
- `include_role_profile` (`false` by default)
- `include_reading` (`false` by default)
- `lang` (`fi` by default, used when `include_chart=true`)

Response always includes:

- `solar_time`
- `four_pillars`
- `flags`
- `engine`

Response conditionally includes:

- `luck_pillars` (when `include_luck_pillars=true`): direction, Jie reference,
  onset age/date, uncertainty and ten-year periods, each a stem phase and a branch
  phase. See [Luck pillars](Luck-Pillars.md) for the explicit time-scale, calendar and
  age conventions.
- `luck_context` (when `include_luck_context=true`): for each luck pillar, its stems'
  Ten Gods, the Day Master's stage and roots on its branch, the relationships it
  forms with the natal pillars, and element and Ten God counts, phase by phase. See
  [Luck context](Luck-Pillars.md#luck-context).
- `resolved_location` (when city resolution mode is used): the place the name
  was resolved to, with the same `city`, `region`, `country`, `timezone`,
  `latitude` and `longitude` fields as a `POST /api/location_search` result
- `chart` (when `include_chart=true`)
- `luck_chart` (when `include_chart=true` and `include_luck_pillars=true`): each
  luck pillar's cards, drawn as `chart` draws the natal pillars' (each stem and branch
  with its element, labels and lines, in `lang`), under the pillar's `sequence`
- `hidden_stems` (when `include_hidden_stems=true`)
- `ten_gods` (when `include_ten_gods=true`)
- `interactions` (when `include_interactions=true`)
- `day_master_context` (when `include_day_master_context=true`)
- `role_profile` (when `include_role_profile=true`)
- `reading` (when `include_reading=true`)
- `luck_reading` (when `include_reading=true` and `include_luck_context=true`)

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

This independent, opt-in enrichment detects every relationship family the canon
(`canon/Taxonomy.md`) defines: the five stem combinations, six branch combinations,
six branch clashes, four three-harmony frames and their half-frames, four
directional combinations, three punishments with their halves, four
self-punishments, and six harms. It compares the normalized natal pillars only;
hidden stems do not create extra stem combinations. It does not run Evolution
inference or change any natal element.

Rules 1-21 are the shared family catalog's. Rules 22-44 follow the canon where
Evolution's catalog differs from it:

| Rules | `kind` | Members |
| --- | --- | --- |
| 22-25 | `half_frame` | two of a frame's three branches, one of them its Peak Branch (子 Zi, 卯 Mao, 午 Wu or 酉 You) |
| 26-29 | `directional_combination` | 亥子丑 Hai-Zi-Chou, 寅卯辰 Yin-Mao-Chen, 巳午未 Si-Wu-Wei or 申酉戌 Shen-You-Xu, all three |
| 30-31 | `punishment` | 寅巳申 Yin-Si-Shen or 丑未戌 Chou-Wei-Xu, all three |
| 32-33 | `half_punishment` | two of 寅巳申 Yin-Si-Shen or of 丑未戌 Chou-Wei-Xu |
| 34 | `punishment` | 子卯 Zi-Mao |
| 35-38 | `self_punishment` | 辰 Chen, 午 Wu, 酉 You or 亥 Hai in two pillars |
| 39-44 | `harm` | 子未 Zi-Wei, 丑午 Chou-Wu, 寅巳 Yin-Si, 卯辰 Mao-Chen, 申亥 Shen-Hai or 酉戌 You-Xu |

Every matching occurrence is returned, including repeated and non-adjacent pairs.
A frame, directional combination or punishment triangle requires all three distinct
branch members. A complete frame or triangle absorbs the halves of its own kind
among its members, so a half is listed only where its whole is not. Birth and
Storage without the Peak are not a half-frame. An empty array means the chart
holds none of these relationships. Records are ordered by rule index, then by natal
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

`kind` is `stem_combination`, `branch_combination`, `branch_clash`,
`harmony_frame`, `half_frame`, `directional_combination`, `punishment`,
`half_punishment`, `self_punishment`, or `harm`. Each record identifies its `stem`
or `branch` component and all participating cards. `adjacent` means the
participating pillars occupy consecutive natal positions, independent of responsive
screen layout. `completeness` is `pair` (two members), `complete` (all three of a
triple), or `half` (two of a triple's three).

`potential_element` is only a reference target for stem combinations, frames,
half-frames and directional combinations. Branch-pair targets are not published
because they vary by convention; clashes, punishments and harms have no target.
They use `null`. `transformation` is `not_assessed` for combinations, frames,
half-frames and directional combinations, and `not_applicable` for clashes,
punishments and harms. No activation, strength, transformation,
favorable/unfavorable verdict, or life outcome is inferred.

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

#### Role profile

Set `include_role_profile: true` to receive the independent `role_profile` section.
The policy is `natal_roles_v1`. It contains:

- `day_master`: natal identity (`char`, `pinyin`, `element`, `polarity`).
- `groups`: Companion, Output, Wealth, Authority, Resource in that order, each
  with `group`, `element`, `presence`, and two individual `roles`.
- Each role has `ten_god`, `presence`, `visible`, and `hidden` occurrence arrays.
- `visible_stems`: all four stems in year/month/day/hour order, including the
  separately labeled Day Master. Each has identity, `id`, `pillar`, `ten_god`,
  `roots`, and `exact_hidden_matches` (a list of occurrence IDs).

`presence` is `visible_only`, `hidden_only`, `visible_and_hidden`, or `absent`.
Every role is returned even when absent. An absent role has empty occurrence
arrays; a group can be present while one of its roles is absent.

Occurrence records retain the Day Master context evidence fields and add `id`:
`visible:<pillar>` or `hidden:<pillar>:<stem-character>`. IDs are stable within a
chart, not identifiers across different charts. Each non-Day-Master visible and
each hidden occurrence belongs to exactly one role. The Day Master itself is not
counted as another visible Companion.

Each visible stem's `roots` lists same-element hidden occurrences, with the same
IDs and `match: exact_stem` or `opposite_polarity`. `exact_hidden_matches` includes
only character-identical hidden records. Opposite-polarity roots never qualify
as exact matches. `ten_god` remains relative to the natal Day Master even when
another visible stem is being inspected. These links do not add new occurrences.

For the canonical chart, the visible Hour Ren stem has three Water root records
but only `hidden:hour:壬` as an exact match. The Month Gui stem's exact matches
are `hidden:month:癸` and `hidden:day:癸`. Year Ding has empty roots and exact
matches; it still appears as visible-only Indirect Resource.

No strength, favorability, or transformation is inferred. This flag does not
implicitly include any other enrichment. The existing `day_master_context`
response, including `support`, remains unchanged. See [Roles](Standard-Roles.md).

#### Canon readings (`include_reading`)

Set `include_reading: true` to receive `reading`: the passages of the canon,
`canon/Taxonomy.md`, that this chart selects. The policy is `canon_taxonomy_v1`.
The `language` is `en` whatever `lang` is, because the canon is English.
- **A paragraph** is `{ "label": string | null, "text": string }`, in the canon's
  own words.
- **A label** is the canon's own, such as `Month–Day`.
- **`text`** keeps the canon's two inline marks, `*emphasis*` and `**strong**`.

- **`day_master`:**
  - `stem` and the canon's `title` for it;
  - `introduction`, the Day Master section's own;
  - `core`;
  - `grounds_introduction`, on how any stem meets any branch;
  - `grounds`, on how this stem meets any ground;
  - `cycle`:
    - `stages`: the Day Master's life stage, 1 to 12, on each pillar's branch;
    - `ring`: the twelve stages in order, each with its `stage`, `branch`, the
      branch's `pinyin`, and the stage's `name` and `chinese`;
    - `introduction`, `mapping_introduction`, the stem's `narrative`, and
      `reconception`.
- **`pillars`,** for `year`, `month`, `day` and `hour`:
  - `stem` and `branch`;
  - `lens`: the Day Master in this pillar;
  - `stem_reading`:
    - `kind`: `day_master` on the Day, otherwise `ten_god`;
    - `ten_god`;
    - `paragraphs`: the Day Master's core, or the Ten God on this stem;
  - `own_stage`: the life stage of the pillar's own stem on its branch, with the
    stage's core passage; `null` on the Day;
  - `ground`, the branch in this pillar, and `ground_about`, the branch itself;
  - `meets`: the Day Master on this branch. Six of these passages end with a
    sentence that holds only for a Day Pillar; in the other pillars that
    sentence is left out;
  - `stage`: the Day Master's life stage on this branch, with the stage's
    passage for this pillar.
- **`roles_introduction`.**
- **`roles`,** for each Ten God:
  - the canon's `name` and `relation`;
  - `core`;
  - `stems`: its passage on each stem where it can stand, `year`, `month` and
    `hour`.
- **`branches_introduction`.**
- **`relationships`,** keyed by the same ids as `interactions`:
  - `kind`;
  - `line`: the one sentence the list shows, the canon's sentence about this form
    of the relationship (see [Readings](Standard-Readings.md));
  - the kind's `introduction`;
  - the pillar `pairing`, which is `null` for a frame;
  - the `entry`: `title` and `paragraphs`;
  - for a stem combination: `with_day_master` or `neither_day_master`,
    `dynamic` and `mechanics`;
  - `condition`, where the chart settles a condition the entry states. It holds
    the `season` and the entry's own `sentence`. Today that is the Zi–Wu clash.

Nothing is assessed: no strength, transformation, favorable or unfavorable
verdict, or prediction.
- **Other sections.** The flag adds no other section. The relationships are
  read from the same detection as `interactions`, but `interactions` itself
  must be requested.
- **Checks at start.** The API checks the canon's exact words it relies on when
  it starts, and does not start if they changed.
- **The canon's own example.** It is Helsinki, 1976-06-29 at 07:02. Its
  `cycle.stages` are Tomb (9), Embryo (11), Emperor's Peak (5) and Death (8),
  from the year to the hour.

**`luck_reading`**, with `include_luck_context` too, reads each luck pillar, under the
same policy and language. The canon has no passages for the luck position, so a luck
pillar reads as the canon's passages for its stem and its branch from the Day Master's
seat. Its `decades` follow the luck pillars, each with:
- `sequence`;
- `stem`: the luck stem's `ten_god`, and the canon's `name`, `relation` and `core` for
  it;
- `branch`:
  - `about`, the branch itself;
  - `meets`, the Day Master on it, its Day-Pillar sentence left out;
  - `stage`, the Day Master's life stage on it, with the stage's core passage;
- `relationships`, keyed by the luck context's ids. Each reads as a natal
  relationship does, with `pairing` always `null`: the canon's pairings are the natal
  positions';
- `settles`: the canon's sentences that wait for a luck pillar, where this one brings
  what they wait for. Each has its `source`, the natal relationship it settles
  (`natal`, or `null` for a Birth and Storage, which the chart holds as no
  relationship), the luck pillar's relationships that settle it (`by`), and the
  canon's `sentence`. The sources are:
  - `year_hour_stems`: the luck stem is one of a natal Year–Hour stem combination's
    stems, and combines with the other;
  - `year_hour_branches`: the luck branch is one end of a natal Year–Hour branch
    relationship, and forms it with the other end;
  - `half_frame`: the luck branch is a natal half-frame's missing branch, and its
    whole takes the half in;
  - `cradle`: the luck branch is the Peak of a frame whose Birth and Storage the natal
    chart holds without it.

See [Readings](Standard-Readings.md).

### `POST /api/first_chart`

The first chart, for someone without an account: what a birth settles. It needs no
session. Each client may ask for `EC_CHART_REQUESTS_PER_HOUR_PER_CLIENT` an hour
([Accounts](Developer/Accounts.md#settings)); past that the answer is `429`
(`{"detail": "Too many charts asked for. Try again within an hour."}`) with
`Retry-After: 3600`. A server that passes requests on for many visitors names each one
as [a trusted proxy](Developer/Accounts.md#a-trusted-proxy).

Request: a `date`, alone, with its `location`, or with its `location` and `time`.

```json
{
  "date": "1990-03-14",
  "time": "07:40",
  "location": {
    "timezone": "America/Chicago",
    "latitude": 41.8781,
    "longitude": -87.6298
  }
}
```

- `date`: `YYYY-MM-DD`, a date that exists, from 1949 to 2100.
- `time` (optional; needs `location`): `HH:MM` or `HH:MM:SS` on the place's clock.
- `location` (optional): a place as `POST /api/location_suggest` gives it, its
  `timezone`, `latitude` and `longitude`, and `fold` (`0` or `1`) for a time the clocks
  repeat. A time the clocks skipped, or repeated when no `fold` is given, is refused
  with `400`, saying which.

Nothing else is taken: an unknown field, a string where a number belongs, a coordinate
that is not finite or is out of range, or a `fold` other than `0` or `1` is refused with
`400`.

What each birth settles:

| Sent | `pillars` | `changes` | `day_master` | `flags` |
|---|---|---|---|---|
| `date` | `year` and `month`, when they are the same wherever on Earth the birth was that date | a change of either at some moment of that date in some time zone (UTC−12 to UTC+14), with its instant, `at_utc`; that pillar is left out of `pillars` | — | — |
| `date`, `location` | `year`, `month` and `day` at noon that date, local time | each of them that changes during that local date, with the clock time and its UTC offset, `at`, to the second rounded down | from `day` | — |
| `date`, `location`, `time` | all four | `[]` | from `day` | the engine's, as `POST /api/four_pillars` gives them |

A change names the `pillar`, when it changes, and the pillar `before` and `after`, so
that a front end can say for whom a pillar holds rather than show one that may be
wrong. Changes come in the order they happen. The offset places a change in an hour
the clocks repeat on its pass: in Detroit on 1 November 2026 the day changes at
`01:15:45-04:00`, on the first pass, so a birth at 01:10 on the second (`fold` 1) has
the new day. Under the default conventions the day pillar changes at true solar midnight,
which on most dates falls within the clock's day: in Chicago on 14 March 1990 at
23:59:34, and in Detroit on 1 July 1990, under summer time, at 01:35:54. The month
changes at a jie (in New York on 7 November 2026 at 04:52:04, Lidong), and the year at
Lichun.

Success response (Chicago, 14 March 1990, without a time; the month and day pillars
and the rest of the passage cut):

```json
{
  "pillars": {
    "year": {
      "name": "Life field",
      "stem": {"chinese": "庚", "pinyin": "Geng", "element": "metal", "polarity": "Yang"},
      "branch": {"chinese": "午", "pinyin": "Wu", "sign": "Horse", "element": "fire", "polarity": "Yang"}
    }
  },
  "changes": [
    {"pillar": "day", "at": "23:59:34-06:00", "before": {"name": "Inner light", "…": "戊寅"}, "after": {"name": "Inner light", "…": "己卯"}}
  ],
  "day_master": {
    "stem": "戊",
    "pinyin": "Wu",
    "polarity": "Yang",
    "element": "earth",
    "title": "戊 Wu — Yang Earth",
    "passage": ["The mountain, the plateau, the great wall. …"],
    "parts": [
      {"part": "core", "first": "The mountain, the plateau, the great wall.", "rest": ["Massive, stable, immovable, …"]},
      {"part": "grounds", "first": "The mountain."},
      {"part": "day", "first": "The mountain's core."},
      {"part": "month", "first": "The mountain in the world's view."},
      {"part": "year", "first": "The mountain's bedrock."},
      {"part": "cycle", "first": "Emperor's Peak · Bathing · Birth"}
    ]
  },
  "engine": {"version": "0.47.0", "…": "…"}
}
```

Each pillar carries its English name (`PILLAR_LABELS`), and each branch its sign
(`animal` in `eight_characters/data.py`). `day_master.passage` is the canon's passage for
the Day Master, word for word, as the reading gives it.

`day_master.parts` are the parts of the Day Master's reading in the order of the app's
Day Master page, each with `first`, the line the app shows for it: `core`, what the
element is; `grounds`, how it meets any ground; `hour`, `day`, `month` and `year`, the
Day Master in each pillar the chart has, from the hour to the year; and `cycle`, where
it is in its cycle, whose `first` is the names of its stages on the chart's branches,
from the year to the hour, joined by ` · `. A part's `first` is its passage's first
sentence, split as the reading splits one (`sentences` in
`eight_characters/reading.py`, and `static/readings.js`). The core also has `rest`, the
rest of its passage word for word, so that it reads in full; the rest of the other parts
is the reading's, for an account.

### `POST /api/evolution_explorer`

Builds the evolution explorer's graph data for a birth. The place is given
the same two ways as for `POST /api/four_pillars`: `location` (mode A) or
`city` + `country` (mode B, resolved to the first geocoder match).

Request (mode A):

```json
{
  "date": "1988-02-04",
  "time": "15:40",
  "location": {
    "timezone": "Asia/Shanghai",
    "longitude": 115.34289,
    "latitude": 26.36828
  }
}
```

Optional request fields:

- `conventions`, `birth_time_uncertainty_seconds`, `basin_index` (`0` by
  default) and `flux_threshold` (`0.0` by default).
- `run`: the run's size, seed and clustering. Any of:
  - `particles`, 8 to 64 (default 24);
  - `temperature_steps`, 1 to 4 (default 2);
  - `sweeps_per_step`, 1 to 2 (default 1);
  - `seed`, 0 to 2147483647 (default 42);
  - `dbscan_eps`, 0.01 to 1.0 (default 0.08);
  - `dbscan_min_samples`, 1 to 64 and at most `particles` (default 1).

  Whole numbers must be JSON integers. The largest run takes about four and a
  half times as long as the default one.
- `model`: overrides of the model's parameters, by name. Each must lie in the
  range `GET /api/evolution_controls` gives it; a table is a list of numbers,
  or a list of rows. The three clustering weights must add up to 1.

Request with overrides:

```json
{
  "date": "1988-02-04",
  "time": "15:40",
  "location": {
    "timezone": "Asia/Shanghai",
    "longitude": 115.34289,
    "latitude": 26.36828
  },
  "run": {"particles": 48, "seed": 7},
  "model": {"LAMBDA_MODE": 6.5, "PROXIMITY_WEIGHT_BY_GAP": [1.0, 0.6, 0.3]}
}
```

Each request computes with its own parameters, so concurrent requests never
affect each other. A request is rejected with `400`, and nothing is computed,
when it has:

- a field the endpoint doesn't know;
- a parameter the model doesn't have;
- a value outside its range, or of the wrong kind;
- a table of the wrong shape.

A run whose clustering leaves every particle outside any basin is also rejected
with `400`, naming the two clustering settings. The `detail` names the field
in each case.

Response always includes `graph_data`; in mode B it also includes
`resolved_location`, as described for `POST /api/four_pillars`.
`graph_data.parameters` reports what the run used: its `run` settings, its
`conventions`, and every model parameter in `model`.

The explorer page reads the birth from its URL and calls this endpoint. The
start page links to it with the picked place's coordinates:
`/explorer/?date=1988-02-04&time=15:40&latitude=26.36828&longitude=115.34289&timezone=Asia%2FShanghai`.
Links with `city` and `country` instead of the coordinates, made before the
coordinates were passed, still work in mode B. A link with only part of the
date, time or place, or with both coordinates and a city, shows an error;
`/explorer/` with no birth in the URL shows a bundled sample chart.

### `GET /api/schools`

Every school Today can follow (see [Today: the rules](Today.md)): three settings,
`favourable`, `season` and `transits`, each with its `name` and `question`, and its
presets. A preset has an `id`, its `name` and `summary` in Finnish and English (`fi`,
`en`), its characters with their pinyin (`han`: `{chinese, pinyin}`, or `null`), its
`sources`, and whether it is the `default`. `finnish_provisional` is `true` while the
Finnish wording awaits confirmation.

### `GET /api/today`

Everything Today shows for a date, from the signed-in account's charts, place and
schools (`GET /api/account/settings`). Query: `date` (`YYYY-MM-DD`, a date at where
you are), `lang` (`fi` or `en`), `chart` (`self`, the default, or `partner`: the
partner's chart is read, with yours as the partner's). Sent with `Cache-Control:
private, no-cache`.

- `404` when no chart of yours is saved, `chart=partner` and no partner's is, or where
  you are is not set.
- `400` for a malformed date, or one whose run (7 days back, 14 ahead) leaves the
  engine's years.

The answer, by [Today: the rules](Today.md):

- `policy` (`today_v1`), `date`, `chart`, `language`, `place`, `schools` (the presets
  used), `engine` (as the first chart's);
- `changes`: any of the day's, month's and year's pillars that changes during the day,
  as the first chart lists them;
- `season`: the school, the ruling element, each element's standing, and for the
  month's commander, the one in command;
- `favourable`: the school, each element's weight, and the element each of the five
  gods is (`gods`: `useful`, `favourable`, `idle`, `enemy`, `unfavourable`); for
  support and restrain the `disease` (`null` when the chart follows its strongest
  force), the strength and the tally behind it; for climate the stems the text names;
- `layers`: `day`, `month`, `year` and `luck` (`null` before the first luck pillar),
  each with its pillar, the Ten Gods of its stem and hidden stems, its `pull` (`score`,
  `band`, `parts`), its relationships with the natal chart (each with the canon's
  `line`, `null` in Finnish) and the halves they absorb; the luck pillar with its
  decade and phase;
- `run`: 22 days, each with its pillar, pull and relationships;
- `hours`: the twelve double hours, each with its clock spans, its `ties` to the day and
  its `call` (`protect`, `mixed`, `avoid`, or `null` without a tie);
- `marriage` (`null` without a partner's chart): the partner's pull and luck pillar,
  whether you pull apart, the day at your spouse palace, and the day's relationships
  with the partner's chart;
- `work`: your career house, the day's and the month's relationships with it, and the
  Ten Gods the day brings with the canon's sentence on each;
- `health`: each element the day brings, its share of your birth tally, and its organs
  in the canon's words;
- `readings`: the canon's passages for each pillar, as the decade page's; `null` in
  Finnish.

### `POST /api/today`

The same answer for what the body sends: `date`, `lang`, `place` (`{name, city,
timezone, latitude, longitude}`), `charts` (`self`, and optionally `partner`, each a birth as
`PUT /api/account/charts/self` takes one, without `key`), `chart` (`self` or
`partner`) and `schools` (any of the three presets; the others follow their
defaults). An unknown field, an unknown preset or a birth that cannot be charted is
`400`.

### `GET /api/evolution_controls`

Lists what `POST /api/evolution_explorer` lets a caller change, in three lists:
`run`, `conventions` and `model`. Each control has:

- an `id`, the field's or parameter's name;
- a `kind`: `integer`, `number`, `vector`, `matrix` or `choice`;
- a `group`, a `label`, a `description` and its `default`.

Numbers and tables also give their `min`, `max` and `step`. A vector names its
entries in `columns`, and a matrix names its `rows` and `columns`. A choice
lists its `options`, each with a `value` and a `label`.

```json
{
  "id": "LAMBDA_MODE",
  "kind": "number",
  "group": "Structure Mode",
  "label": "Structure-Mode Fidelity Weight",
  "description": "Weight of the chart's fit to its structure mode.",
  "default": 4.0,
  "min": 0.1,
  "max": 20.0,
  "step": 0.01
}
```

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

Each suggestion is one geocoded settlement:

- Only settlements are suggested: GeoNames populated places (feature codes
  `PPL…`) and administrative areas (`ADM…`). Airports, glaciers, islands, parks,
  mountains and whole countries are left out, because a chart computed for their
  coordinates is for the wrong place; the first geocoder match for `Luxembourg`,
  for example, is the country's centre, 16 km from the city. Every city-state,
  such as Hong Kong, has its own settlement entry. `limit` (1–20, default 6)
  counts settlements.
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
- `401` no signed-in account, for the requests that need one
- `403` a request naming its client that does not come from a proxy the app trusts
- `429` past the hourly limit, for codes and first charts, with `Retry-After`
- `500` unexpected internal errors

## Example curl

With the session cookie of a browser signed in to the page (here a laptop's, over
plain HTTP):

```bash
curl -X POST 'http://127.0.0.1:8000/api/four_pillars' \
  -b "ec_session=$SESSION" \
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
    "include_role_profile": true,
    "lang": "en"
  }'
```
