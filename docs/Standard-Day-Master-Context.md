# Day Master context in Standard mode

The row of topics above the pillars starts with the Day Master and its three
controls: the resolved solar month, Roots, and Roles. Select a control to inspect
its evidence in the panel beside the chart (from 1200px wide; narrower, a sheet
over the foot of the page). Select it again, press Escape, or use Close to
dismiss it. Keyboard activation and focus return work the same way as
Relationships.

Only one relationship or context detail is open at a time. Switching topics
clears the previous highlights without moving the pillars, changing their natal
elements, flipping cards, or opening hidden-stem panels. From 1200px wide the chart
moves over once, when the panel first opens. The five-element palette, card faces,
and the long-press, quick-click, and chart-wide display gestures are unchanged by
a topic.

## What the controls mean

**Month / seasonal context** identifies the month branch calculated by the solar
engine, not the Gregorian month in the input. It shows the declared traditional
season group separately from the branch's natal element and hidden-stem composition.
The month branch and its exact hidden-stem rows are highlighted.

The policy groups Yin/Mao/Chen with spring/Wood, Si/Wu/Wei with summer/Fire,
Shen/You/Xu with autumn/Metal, and Hai/Zi/Chou with winter/Water. These are named
traditional groups, not weather or hemisphere-adjusted local seasons. No
within-month governing-qi allocation, seasonal weighting, or overall-strength
assessment is performed. In particular, Chen, Wei, Xu, and Chou retain their
Earth branch identity and their actual hidden stems.

**Roots** records every same-element hidden stem under the explicit
`natal_presence_v1` policy. An exact Day Master stem is distinguished from a
same-element, opposite-polarity match. Each record retains its pillar, branch,
stem, main/middle/residual qi position, and Ten God. Repeated branches remain
separate occurrences. The summary counts branches containing a match, not points
of strength. Visible stems and Resource stems are not counted as roots.

An outline around a branch identifies where the evidence lives; the branch is
not treated as a single-element root. The specific matching hidden-stem row is
outlined both on the Ten Gods card back and in the existing hidden-stem panel,
when the reader chooses to reveal either surface. The detail always names the
actual matching stem, so opening or flipping a card is not necessary to inspect it.

**Roles** expands the former Support view to all ten roles in five groups.
Companion and Resource remain available alongside Output, Wealth, and Authority.
Each role has its own visible/hidden/absent state and occurrence details. Roots
can now also be inspected for any visible stem. The Day Master itself is still
excluded from additional Companion occurrences. See [Roles](Standard-Roles.md)
for exact hidden-to-visible matching, root inspection, and navigation.

The original `day_master_context.support` API fields are preserved unchanged.
Root and Companion views can describe the same occurrence and are not additive.

For the canonical 1988-02-04 16:30 Chengdu chart, Ji Earth has exact main-qi Ji
matches in Month Chou and Day Chou, plus residual-qi Wu Earth in Hour Shen with
the opposite polarity. Year Ding is visible Indirect Resource. The Chou seasonal
group is winter/Water; Chou itself remains Earth. These facts describe the stored
chart and the declared matching rules, not a prediction about a person.

## API and verification

`include_day_master_context: true` adds `day_master_context` independently to
`POST /api/four_pillars`. The default API response and all other enrichment
sections are unchanged. Standard requests this section automatically. A missing
or inconsistent context is shown as a chart-creation error, not empty evidence.
The context, Ten Gods, and hidden-stem panels must agree on branch, stem, element,
polarity, and qi position before the chart is shown.

The backend uses the existing validated hidden-stem and Ten Gods mappings.
Evolution inference, strengths, transformations, and numerical astronomical
outputs are not used or modified. See `tests/test_api_day_master_context.py`
for independent-reference coverage of all ten Day Masters, twelve branches,
four positions, support roles, and existing API flag combinations.

Browser coverage in `tests/browser/day-master-context.test.mjs` exercises the
real chart API with fixed geocoding coordinates: precise row highlights,
exclusive selection, card gestures, seasonal boundaries, absence states,
Finnish/English, responsive layouts, keyboard focus, reduced motion, chart reset,
and visible errors for corrupted evidence. See `tests/browser/README.md` for setup.
