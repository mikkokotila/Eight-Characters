# Browser regression tests

The harness uses Node's built-in test runner and an existing Playwright installation
with matching browser binaries. It does not install dependencies, add a frontend
build step, or alter the running app. The server address, module, and browser are
explicit environment settings; a missing setting or browser fails the run.

Start the app as usual, then run from the repository root:

```bash
EC_PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
EC_BASE_URL=http://127.0.0.1:8000 \
EC_BROWSER=chromium \
node --test --test-concurrency=1 tests/browser/*.test.mjs
```

`EC_PLAYWRIGHT_MODULE=playwright` also works when that module is resolvable from the
repository. Run again with `EC_BROWSER=webkit` and an installation that has its
matching WebKit binary. Each run covers desktop and touch-enabled mobile contexts.
No missing browser is skipped or substituted.

Set `EC_SCREENSHOT_DIR` to an output directory to save overview, selection, clash,
frame, and Finnish-language screenshots. Nothing is written into the repository
by default. Review the screenshots alongside the behavioral assertions when
changing typography, spacing, or responsive layout.

The tests calculate charts and explorer graphs through the real API. They stub
only location suggestions, whose fixed test coordinates the page sends as the
chart's `location`, so no test depends on the geocoder. Malformed-response tests
intentionally modify the real response to verify visible errors. No real birth
records or saved user data are used.

Coverage includes selection and keyboard focus, unchanged pillar geometry and
natal colors, the display switch and individual flips (and the switch's mixed state),
long-press release suppression,
quick clicks/taps, cancelled touch holds, repeated combinations, complete frames,
empty results, Finnish, narrow viewports, reduced motion, chart reset, and explicit
errors for absent or malformed relationship data.


The Day Master context suite additionally checks all three controls, exact versus
opposite-polarity root evidence on both hidden-stem surfaces, Companion/Resource
presence, no/one/four-root layouts, explicit support absence, resolved solar-month
boundaries, mutually exclusive relationship/context details, and rejection of
missing or inconsistent context. Screenshots include context overview, season,
roots, support, flipped cards, absence, four roots, and Finnish layouts.

The Roles suite covers all ten individual roles, five-group presence states,
exact hidden-to-visible matching (including the separately labeled Day Master),
all visible-stem roots, unchanged natal role reference, stable occurrence IDs,
absent roles, unrooted visible stems, repeated visible identities, nested back/focus
navigation, exclusive selection, card gestures, Finnish layouts, and corrupted
profile rejection. `chart-helpers.mjs` is shared by the role, context, and relationship suites.

The location suite checks that places sharing a name are told apart by region and
coordinates, that the picked place's coordinates reach the chart and the evolution
explorer, that a slow answer for an earlier query never replaces the list, that a
picked place can be edited and is kept when returning from the chart, and that
explorer links naming the place partly, twice, or only by city and country behave
as documented.

The foundations suite checks the page as a whole, on the landing page, the chart
with hidden stems and Ten Gods, the long-press hint, the relationships list, and
every detail page, in English and Finnish:
every visible text is set in the self-hosted page fonts (and, in Chromium, the
DevTools protocol confirms which font drew every glyph; the stems and branches
must come from the page's own CJK font, and only other CJK characters may come
from a system font), text meets WCAG AA contrast with backgrounds and
opacity composited through every ancestor, the expand chevron and element dots
meet 3:1, card highlights stay within the gap between cards, the page loads
nothing from another origin and nothing fails to load, and the form's date
range, field messages, error region, progress state, headings, display and view
switch labels, and tab titles behave as documented.

The engine-truth suite checks what the chart shows of the engine's own results:
each pillar's identity and characters, the header built from the birth as entered
(in Finnish, times such as 16.30), and the true solar time with its offset from
clock time, dated when it falls on another day. It checks that only a pillar
within 30 minutes of a change is marked, before or after the birth; that every
pillar's exact changes open on demand, naming the solar term or the clock and its
date; that Escape returns focus; and that one detail is open at a time. A chart
whose true solar time cannot be read, or whose pillar changes are missing or
contradict the chart, is not shown. On the Helsinki 00:50 chart (true solar
23:29) the Zi-hour switch appears, sends the other convention, and the Day Master,
pillars, marks, Ten Gods, roots, relationships and roles all follow it and return
with it; charts whose conventions agree show no switch, and a switched chart that
cannot be read sends the form back with the reason. The high-latitude and
solar-term notices appear, and flags that contradict the chart stop it. The
foundations audits also walk the pillar change details, a Zi-hour chart and a
high-latitude chart.

The design-system suite checks the one grid of the pillars: the stem and branch
rows and the pillar names share top edges and heights across the four pillars,
front and back, in English and Finnish, at widths from 641px to 1440px (and in
pairs on mobile); a wrapped pillar label keeps the names level; the branch
chevron clears its card's text; opened hidden stems share a row in the flow and
cover nothing; and no text on a card or in its hidden stems is clipped or broken
inside a word, in any display, from 320px to 1440px, in both languages.

The workbench suite checks the chart's layout (#19): at 1440×900 every topic keeps
its highlighted cards and its explanation on screen together without scrolling;
the chart moves over once when the panel first opens, not again while topics
change, and back when it closes; below 1200px the panel is a sheet over the foot
of the page, and the chart scrolls clear of it; the display switch shows
characters, Ten Gods or hidden stems on every card; a card turns after half a
second held, and the mouse finds a hint saying so, right above the card; the
chart's language switch asks for the chart again and keeps its display; Edit
keeps the birth and New chart empties the form; and the column headers pair each
plain pillar name with its poetic one, while the panel uses the plain names in
the chart's order.

The arcs suite checks the relationships drawn on the chart (#19). On eight charts
the API calculates, from none to seven relationships and with four levels of stem
or branch arcs, at 1440, 1024 and 700px: every relationship has one arc, from the
middle of its first card to the middle of its last, in its line (solid, dashed or
double), standing on the stems or hanging from the branches within its own row;
a frame's middle member has its foot; the feet on one card stand 6px apart around
its middle; and arcs that span or cross each other stand at different heights,
the wider above. It also checks that a chosen relationship darkens its arc and
fades the others until cleared; that opened hidden stems cover the feet passing
behind them (compared pixel for pixel with the arcs hidden) while the arcs keep
their shape; that arcs needing more than the rows hold fail visibly; and, on
desktop and mobile, that the cards stand in the same place with none to all seven
of one chart's relationships. Phones draw no arcs.
