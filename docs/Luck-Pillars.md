# Ten-year luck pillars (Da Yun)

The backend computes luck pillars as an optional enrichment of
`POST /api/four_pillars`. The natal chart and its enrichments retain their
existing contracts. The frontend does not request or render this enrichment.

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
`chinese`), `start_age`, `end_age`, `start_utc` and `end_utc`.
Each age contains `years`, `months`, `days`, `hours`, `minutes` and `seconds`.
Intervals include their start and exclude their end. Adjacent intervals meet
exactly; there are no gaps or overlapping endpoints. `pre_luck_period` can be empty.
No current-time-dependent active-pillar selection is performed.

## Uncertainty and reference comparison

Luck calculations use a declared 3-second solar-term allowance, added to the
user's nonnegative, finite `birth_time_uncertainty_seconds` (zero when omitted).
This allowance exceeds the existing independent comparison's maximum 2.7-second
Jie discrepancy and the documented HKO residual, but is not a proof of absolute
accuracy. See [astronomical validation and known residual](validation.md).

`scaled_age_seconds` is 120 times that combined interval allowance. If the
birth's allowance overlaps any Jie, `boundary_ambiguous` is true. The returned
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
    BirthInput(utc_timestamp="1988-02-04T08:30:00Z", gender="male"),
    include_luck_pillars=True,
    luck_pillar_count=10,
)
```

`compute_engine_json` accepts the same options and retains deterministic
serialization. With no opt-in and no gender, the engine's existing payload and
regression fixture remain unchanged.

`tests/test_luck_pillars.py` covers all year-stem/gender directions, conversion
ratios, wraparound, exact Jie inclusion, Lichun crossing, same-instant timezone
equivalence, leap dates, uncertainty, supported birth endpoints, independent
package sequences and ephemeris instants, and deterministic JSON.
`tests/test_api_luck_pillars.py` covers input validation, city resolution, DST
folds/gaps, explicit internal errors, OpenAPI and unchanged natal enrichments.
