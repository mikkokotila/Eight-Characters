# Ten-year luck pillars (Da Yun)

The backend computes luck pillars, and what each brings to the natal chart, as
optional enrichments of `POST /api/four_pillars`. The natal chart and its
enrichments retain their existing contracts. Standard mode asks for both when the
form has a gender: see [Luck pillars in Standard mode](Standard-Luck-Pillars.md).

## Request

```json
{
  "date": "1988-02-04",
  "time": "16:30:00",
  "location": {
    "timezone": "Asia/Shanghai",
    "longitude": 104.066,
    "latitude": 30.658
  },
  "gender": "male",
  "include_luck_pillars": true,
  "luck_pillar_count": 10
}
```

`gender` accepts exactly `male` or `female`, the two categories used by the
traditional direction rule. It is required when `include_luck_pillars` is true,
and optional for natal-only requests. An unknown value is rejected, not inferred.
`luck_pillar_count` is a strict integer from 1 through 12, default 10. It counts
actual ten-year pillars, excluding the period before the first pillar.
Missing gender, invalid count and invalid time inputs return `400` with `detail`.
Unexpected calculation failures return `500` with `detail`.

The same `location` or `city`/`country` modes, explicit DST `fold`, and natal
conventions remain available. No gender is inferred from the place or date.

## Calculation convention

The direction and three-days-per-year rule are grounded in
[San Ming Tong Hui, volume 2, On Major Cycles](https://zh.wikisource.org/w/index.php?title=三命通會/卷二&oldid=2292392#论大运).
The continuous conversion and UTC calendar mapping below are explicit implementation
conventions; they are not claims that every traditional school uses one algorithm.

1. Resolve the natal year and month with the existing astronomical engine.
   The year changes at Lichun, not January 1 or lunar New Year.
2. Yang-year male and Yin-year female progress forward. Yin-year male and
   Yang-year female progress backward. Polarity belongs to the resolved **year**
   stem, not the Day Master.
3. Forward selects the next Jie strictly after birth. Backward selects the
   previous Jie at or before birth. Only the twelve month-boundary Jie participate;
   the intervening Zhongqi do not. This matches the natal month boundary's
   inclusive-start rule. A birth exactly at a Jie has zero backward onset age
   and a forward interval to the following Jie.
4. Advance both natal month stem and branch by one step per cycle, in the selected
   direction, wrapping their ten- and twelve-member cycles. The natal month itself
   is not cycle 1. Validate stem/branch polarity for every generated pillar.
5. Measure the birth-to-Jie interval in uniform Terrestrial Time (TT), using the
   same solver and TT birth instant as the natal engine. DST, longitude, true solar
   hour and Zi-day conventions cannot independently change this interval.
6. Three elapsed birth days produce one symbolic age year: twelve 30-day months,
   or 360 days. One birth day gives four age months; one two-hour block gives ten
   age days; one birth second gives two age minutes. Retain seconds and round the
   final scaled duration once to the nearest age second before decomposing it.
7. Add the total age years/months to the Gregorian **UTC** birth year/month,
   preserving the day unless it exceeds that target month's length, when it is
   clamped to the last day. Add the remaining days, hours, minutes and seconds.
   This defines the first start instant. Every later boundary is a ten-year
   calendar anniversary of that first instant, calculated from the original
   onset, so a February 29 onset returns to February 29 in later leap years.

Using UTC for calendar arithmetic makes the timeline identical for the same
instant expressed in different timezones. Dates are UTC ISO 8601 strings;
clients can display them in their chosen zone. The age fields are symbolic
offsets, not calendar-year counting ages or completed birthdays. Calendar mapping
is not a multiplication by 365 or 365.25 days. It can change discontinuously when
an age month/year component carries; the uncertainty estimate below applies to
the symbolic duration, not a promised timestamp confidence interval.

The natal birth range remains 1949-2100. Arithmetic cycle dates may extend past
2100; no ephemeris evaluation or extrapolated annual/monthly pillars are performed
at those future dates.

## Response

`luck_pillars` adds these fields without changing the natal response:

| Field | Meaning |
| --- | --- |
| `rule_version` | `dayun_elapsed_time_v1` |
| `phase_rule` | `stem_then_branch_v1`: see [Phases](#phases) |
| `gender`, `direction`, `year_stem_polarity` | Input and resolved direction evidence |
| `onset_method` | `three_days_per_year_continuous` |
| `interval_basis` | `terrestrial_time` |
| `calendar_basis` | `gregorian_utc` |
| `reference_jie` | Term label, longitude, TT Julian date, UTC instant and elapsed seconds |
| `start_age`, `start_utc` | First onset offset and mapped date |
| `pre_luck_period` | Birth-to-first-onset interval, with no invented luck pillar |
| `pillars` | Actual cycles in chronological sequence, starting at 1 |
| `uncertainty` | Birth uncertainty, solar-term allowance, amplified age uncertainty and boundary flag |

Each pillar contains `sequence`, `stem` and `branch` (each with `index` and
`chinese`), `start_age`, `end_age`, `start_utc`, `end_utc` and `phases`.
Each age contains `years`, `months`, `days`, `hours`, `minutes` and `seconds`.
Intervals include their start and exclude their end. Adjacent intervals meet
exactly; there are no gaps or overlapping endpoints. `pre_luck_period` can be empty.
No current-time-dependent active-pillar selection is performed.

With `include_chart`, `luck_chart.pillars` draws each luck pillar's cards as `chart`
draws the natal pillars', in the request's `lang`: the stem's and the branch's
element, labels and lines, under the pillar's `sequence`.

## Phases

San Ming Tong Hui's same passage on major cycles: "凡行運，在干兼用地支之神，在支則棄天干之物"
(Fan xing yun, zai gan jian yong di zhi zhi shen, zai zhi ze qi tian gan zhi wu):
in every luck period, while it is on the stem the branch is used as well; while it is
on the branch the stem is set aside. Its next clause gives the reason: the luck cycle
weighs the branch more. The passage names no number of years; practice reads "on the
stem" as a cycle's first five years and "on the branch" as its last five.

Each pillar's `phases` holds exactly two intervals, in order:

| `phase` | Interval | What acts |
| --- | --- | --- |
| `stem` | `start_utc` to the fifth anniversary | the stem, and the branch as well |
| `branch` | the fifth anniversary to `end_utc` | the branch alone |

Each phase has `start_age`, `end_age`, `start_utc` and `end_utc`. The stem phase
starts with its pillar, the branch phase ends with it, and the two meet at the
boundary between them. That boundary is a five-year calendar anniversary
of the first onset, counted like the cycles' own boundaries: a 29 February onset
clamps to 28 February in a common year, and the clamp never carries into a later
boundary. Its age is the cycle's `start_age` with five more years.

## Luck context

`include_luck_context` (`false` by default) adds `luck_context`: what each luck
pillar brings to the natal chart, phase by phase. It requires `include_luck_pillars`,
and so `gender`; asked for alone, it is refused with `400`.

The luck pillar stands as a fifth position after the natal four, under the natal
relationship rules ([Natal relationships](api.md#natal-relationships-include_interactions)), and it counts as adjacent to
every natal pillar. The phase rule decides what acts when:

- in the stem phase only: the luck stem, and each relationship it forms;
- in both phases: the luck branch, its hidden stems, the Day Master's stage on it, and
  each relationship it forms.

| Field | Meaning |
| --- | --- |
| `policy` | `luck_context_v1` |
| `natal_counts` | The natal chart's own counts (see Counts) |
| `decades` | One entry for each luck pillar, in the same order |

Each decade:

| Field | Meaning |
| --- | --- |
| `sequence` | The luck pillar's `sequence` |
| `occurrences` | The luck stem, then the hidden stems of the luck branch in main, middle, residual order, recorded as the role profile records stems (`char`, `pinyin`, `element`, `polarity`, `pillar` `luck`, `component` `stem` or `hidden_stem`, `branch`, `qi_type`, `ten_god` relative to the natal Day Master), with `new_to_chart` and `phases` |
| `day_master_stage` | The Day Master's stage on the luck branch: 1 (Birth) to 12 (Nurture) |
| `roots` | The luck branch's hidden stems of the Day Master's element, each with `match` (`exact_stem` or `opposite_polarity`) and `phases` |
| `interactions` | Each relationship the luck pillar takes part in, in the shape and order of `interactions` (rule, then position), with `phases` |
| `absorbed` | Each natal half that a complete whole with the luck pillar absorbs for the decade: its `id`, the absorbing wholes' ids in `by`, and `phases` |
| `counts` | `stem` and `branch`: the counts with the luck pillar, phase by phase |

`new_to_chart` is true when no natal stem occurrence has that Ten God.
In `interactions`, the luck member's `pillar` is `luck`, and its ids name it last, as
in `stem_combination:1:month-luck`. A relationship with the luck pillar is `adjacent`
when its natal members are: always for a pair, and for a triple when its two natal
pillars stand side by side. The natal halves of a frame or punishment triangle that a
whole with the luck pillar completes are `absorbed` for the decade. A half that a
natal whole already absorbs is not a natal relationship, so it is never listed there.

Counts are tallies, not weights or strengths. Each holds every element and every Ten
God, with zero where there is none:

- `elements`: each visible character, stem or branch, by its own element. That is
  eight natal characters; ten in the stem phase, nine in the branch phase.
- `ten_gods`: each stem occurrence by its Ten God, that is, every visible stem but the
  Day Master and every hidden stem. Natal ones, plus the luck pillar's that act in the
  phase.

Nothing in the context weighs strength, applies a transformation or predicts.

## Uncertainty and reference comparison

Luck calculations use a declared 3-second solar-term allowance, added to the
user's nonnegative, finite `birth_time_uncertainty_seconds` (zero when omitted).
This allowance exceeds the existing independent comparison's maximum 2.7-second
Jie discrepancy and the documented HKO residual, but is not a proof of absolute
accuracy. See [astronomical validation and known residual](validation.md).

`scaled_age_seconds` is 120 times that combined interval allowance. Scaling that
would overflow rejects the input explicitly instead of emitting a non-finite
JSON number. If the birth's allowance overlaps any Jie, `boundary_ambiguous` is
true. The returned
timeline is then nominal: the month anchor, reference term, onset, and at Lichun
even direction can change. Do not treat it as a resolved timeline. The flag
also considers the nearest Jie on the opposite side of the birth.

`lunar-python` is a verification reference, not a production calculation path.
Its `getYun(gender, 2)` uses minute-quantized civil intervals, Beijing-time terms
and calendar-year-based age labels. Its default `sect=1` instead counts days
and two-hour blocks. This implementation explicitly uses continuous TT intervals,
own-engine instants and symbolic age offsets, so unqualified equality of start
dates against either package method is not an acceptance criterion.
Reference comparisons account for that quantization and the time-scale conversion.

## Python use and verification

```python
from eight_characters.engine import compute_engine_payload
from eight_characters.time_convert import BirthInput

result = compute_engine_payload(
    BirthInput(utc_timestamp='1988-02-04T08:30:00Z', gender='male'),
    include_luck_pillars=True,
    luck_pillar_count=10,
)
```

`compute_engine_json` accepts the same options and retains deterministic
serialization. With no opt-in and no gender, the engine's existing payload and
regression fixture remain unchanged.

`tests/test_luck_pillars.py` covers all year-stem/gender directions, conversion
ratios, wraparound, exact Jie inclusion, Lichun crossing, same-instant timezone
equivalence, leap dates, phases and their leap-day anniversaries, uncertainty,
supported birth endpoints, independent package sequences and ephemeris instants,
and deterministic JSON.
`tests/test_api_luck_pillars.py` covers input validation, city resolution, DST
folds/gaps, explicit internal errors, OpenAPI and unchanged natal enrichments.
`tests/test_api_interactions.py` compares the relationships a luck pillar forms, and
the natal halves it absorbs, with independent readings of the canon on every
combination of four natal branches and a luck branch, and of four natal stems and a
luck stem. `tests/test_api_luck_context.py` checks the context of the design's sample
chart (14 August 1975, 07:45, Helsinki, female) by hand, decade by decade, and
through the API.
