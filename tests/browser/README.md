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

The chart links suite checks the chart's address (#19). A new chart's address names
it, and a reload shows the same chart, with its birth in the form for Edit. The open
topic and the display come back in a new tab with nothing stored, in the link's
language. Every kind of topic (season, roots, roles and their pages, relationships
and a chosen one, a pillar's changes) comes back from its link. Back and Forward walk
through the topics, the chart and the form; Edit and New chart are steps of their
own, and an earlier chart is asked for again. The display, the Zi-hour convention
and the language replace the current entry. Links that open no chart say why, keep
a valid birth in the form and leave the form's address. A chart that arrives after
a later step is not drawn. Copy link puts the address on the clipboard and says so,
and says so when the browser refuses. `openLink` in `chart-helpers.mjs` opens a
link as a new tab would, with every chart calculated by the real API.

The keyboard suite checks the chart by keyboard (#19). The eight cards take one tab
stop, the arrows move between them and stop at the edges without scrolling the page,
and Tab comes back to the card used last. Enter and Space open and close a branch's
hidden stems and keep `aria-expanded` in step; on a stem they do nothing. T turns the
card with focus once, even held down, and is only a letter elsewhere; the cards are
named by their pillar and the side they show. A hint above the card with keyboard
focus says its keys; a click shows the pointer's hint instead. Escape closes the open
topic. `?` lists the keys while the chart has focus, and Escape closes only the dialog
and gives focus back. ⌘K or Ctrl+K finds a command and runs it as its control would, a
topic in one step of the history. Every control of the chart is reached by Tab, the
cards at one stop. In WebKit the suite steps with Option+Tab, as Safari does without
Full Keyboard Access.

The panel suite checks what the panel says (#19).
- **Roles is a matrix.** Each role has a drawn mark under the visible and the hidden
  stems (filled, ring or small dot), centred under its column's heading.
  - Each group's heading shows its element's swatch on one line with its name.
  - A role the chart lacks is in the secondary ink.
  - Each role gives its state in words to assistive technology.
- **A stem is a line of text** on every page, with its element's swatch, never a
  box. The chart's highlight stays on the chart.
- **Nothing is said twice.** A role's page names the role once, an occurrence's
  pillar stands beside it, and no label in capitals stands directly over another.
- **Every page reads from the left** and ends with one note in one style.
  - The notes never hold more than 75 characters to the line.
  - Where the page has room (a sheet 1024px wide), they average 60 to 75.
- **Pillar names** in the panel are written as their column headers write them.

The pointing suite checks that the panel points at the chart (#19).
- **Timing.** A line rings on the chart what it names after half a second at rest,
  never sooner, measured in the page. While a ring shows, the next line rings at
  once. None stays once the pointer has left, and after a pause the half second
  applies again.
- **Targets.** Every kind of line rings exactly what the API's records say it names:
  - the season's branch and hidden stems;
  - each role and group, and each visible stem and its roots;
  - each occurrence on a role's page, and each visible stem it leads to;
  - each relationship's cards and arc, and each member of a chosen one.

  An absent role names nothing.
- **Keeping and letting go.** A click or tap keeps a line's ring, even while the pointer
  is on the chart, and a second lets it go. A role's click opens its page and nothing
  rings until the pointer moves. Keyboard focus rings at once.
- **Nothing else changes.** Pointing moves, opens, turns and recolours nothing, keeps
  within half the gap between cards, and leaves no ring behind a closed page.

The output suite checks the chart out of the page (#20).
- **Copy as text.** The copied pillars match the API's record and the cards, year to
  hour. The second line matches the screen's name, true solar time and convention,
  in English and Finnish. In the Zi hour, switching the convention changes both
  lines. A refusal says so. The commands offer Copy as text and Print.
- **Print.** With print media, the chart keeps its eight cards, colours and precision
  line; the controls are gone; the open topic follows below at the page's width;
  and with no topic, nothing follows.
- **Arcs on paper.** Each arc stands on its cards as on screen, and the arcs' rows
  are laid out for paged output: Chromium places absolutely placed grid items
  wrongly there, and emulated print is not paged. A Zi-hour chart prints its
  convention as text.

`settled` in `chart-helpers.mjs` waits until nothing moves: a transition that the next
change interrupts counts as done, and one that starts meanwhile is waited for too.
