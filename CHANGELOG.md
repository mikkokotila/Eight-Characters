# Changelog

## 0.25.0

Stage 5 of the Standard view overhaul (#20), part 1: the chart out of the page, as text and on paper.

### Changed
- **Copy as text**, in the chart's bar and among the commands, copies two lines for notes and messages:
  - the pillars on the chart's cards, in written order, year to hour: `丁卯 癸丑 己丑 壬申`;
  - the birth as entered, its true solar time, and the convention that set the day: `February 4, 1988 · 16:30 · Chengdu · True solar time 15:12:24 · Day changes at midnight`. In the Zi hour it names the convention the chart was read with.

  A message says the text was copied, or that the browser refused. In Finnish the bar's tools now take two rows at desktop widths, as they already did on narrower screens.
- **Print.** The browser's print, or Print among the commands, prints:
  - the chart's name and precision line;
  - the pillars in their element colours, with their arcs and any opened hidden stems;
  - any open topic, below the chart at the page's width.

  The controls and the page's tone are left out. A Zi-hour chart prints its convention as text, and a heading moves to the next page with what it heads.
- On paper, the arcs' rows are laid out as ordinary grid items: paged, Chromium does not place an absolutely placed grid item in its area.
- **Docs.** New `docs/Standard-Copy-and-Print.md`.
- **Tests.** A browser suite for the output (`output.test.mjs`). The copied text is checked against the API and the screen, in both languages and both Zi conventions. The printed layout, the arcs on paper, a refused copy and the commands are checked too. Each of four faults put in fails at least one of its tests:
  - pillars copied hour first;
  - the default convention named for every chart;
  - the panel left as a sheet on paper;
  - the arcs' rows left absolutely placed.
- Version bumped to `0.25.0`; the static assets' cache keys follow it.

## 0.24.0

The Standard view: the panel points at the chart. A follow-up to #19, suggested while reviewing its last part.

### Changed
- **Each line in the panel points at the chart.** A page still highlights all its evidence at once, and now each line in it rings its own part, with a dark ring:
  - a stem, its card;
  - a hidden stem, its branch's card, and its row where hidden stems show;
  - a relationship, its cards and its arc;
  - a role or a group of roles, every place it occurs;
  - a stem's roots control, the roots it leads to.
- **When it rings:**
  - after the pointer rests on a line for half a second; while a ring shows, the next line rings at once, and the ring goes shortly after the pointer leaves every line;
  - for as long as a click or tap keeps it, on a line that leads nowhere else. This serves touch, which has no hover, and a pointer that moves over to the chart to look closer. A second click lets it go. A control keeps its own action;
  - at once, while a control in the panel has keyboard focus.
- Meanwhile the page's other outlines step back and the other arcs fade. The ring is 2px of ink, within half the gap between stacked cards. Nothing moves, opens, turns or changes colour.
- A line may name only what the chart shows; each page checks this as it is built. A page closed or redrawn takes its rings with it.
- **Docs.** `docs/Standard-Day-Master-Context.md` describes the rings; the Roles, Relationships and Keyboard pages and the design tokens add their parts.
- **Tests.** A browser suite for the pointing (`pointing.test.mjs`) checks:
  - the half second, and the quick switch after it;
  - what every kind of line rings, from the API's records;
  - keeping by click, tap and focus;
  - that nothing moves.

  Each of seven faults put into the pointing fails at least one of its tests: no half second, no quick switch, nothing kept, a hidden stem without its row, a ring past half the gap, focus that rings nothing, a ring left behind a closed page.
- Version bumped to `0.24.0`; the static assets' cache keys follow it.

## 0.23.0

Stage 4 of the Standard view overhaul (#19), part 5: what the panel says. This completes #19.

### Changed
- **Roles is a matrix.** Each role stands in its group, with a mark in two columns, the visible stems and the hidden stems: a filled dot where it is visible, a ring where it is hidden, a small dot where it is not. The marks are drawn, not typed.
  - Each group shows its element's colour beside its name, on one line.
  - A role the chart lacks is set in the secondary ink and can still be chosen.
  - Screen readers still hear each role's state in words.
  - The Finnish column headings, "Näkyvissä" and "Piilossa", take the words of the existing presence states.
- **A stem in the panel is a line of text**, with its element's colour, not a box outlined like an input field. The outlines stay on the chart.
- **Nothing is said twice.**
  - A role's page names the role once, in its title, not again under each occurrence.
  - Each occurrence's pillar stands beside it, not over it.
  - The season page no longer stacks "Month branch composition" over "Month".
  - A visible stem no longer says Visible under Visible stems.
- **Every page reads from the left**, as the list of relationships already did. It ends with one note in one style, of about 60 to 75 characters to the line where the panel has room: 66 to 69 on average on a sheet 1024px wide, and never more than 75. When a page has nothing to list, it says so in running text, not in the style of a note.
- **One style for the pillars' names**: the panel writes them in the capitals of their column headers. Page titles keep the detail heading's size in the narrow panel.
- **Docs.** `docs/Standard-Roles.md`, `docs/Standard-Day-Master-Context.md` and `docs/Developer/Design-Tokens.md` describe the panel's pages.
- **Tests.** A browser suite for the panel (`panel.test.mjs`) checks:
  - the matrix and its marks;
  - rows without boxes;
  - no repeated names and no stacked labels;
  - the notes' alignment, style and line length;
  - the pillars' names.

  Every test in it fails on the previous version.
- Version bumped to `0.23.0`; the static assets' cache keys follow it.

## 0.22.0

Stage 4 of the Standard view overhaul (#19), part 4: the chart by keyboard.

### Changed
- **The cards take one tab stop**, the card used last or the hour stem on a new chart. Left and Right move along the pillars, Up and Down between stem and branch; the arrows stop at the edges and do not scroll the page.
- **Enter or Space** opens and closes a branch's hidden stems, as a click does. **T** turns the card with focus to its Ten Gods and back, as a long press does, once even when held.
- **A hint above the card with keyboard focus** says its keys, and a ring inside the card's edge shows the focus.
- **For screen readers**, a branch card is a button with `aria-expanded` and a stem card a group, each named by its pillar and the side it shows; the pillars are a group described by the keys.
- **`?` lists the keys** in a dialog while focus is on the chart (WCAG 2.1.4).
- **⌘K or Ctrl+K opens the commands**: the topics, each relationship, role page and pillar's changes, the display, the other language, the Evolution view, Copy link, Edit, New chart, Close and Keys. Words narrow them; a topic opens in one step of the history.
- **Escape in a dialog** closes the dialog only, and focus returns.
- `docs/Standard-Keyboard.md` describes the keys.
- **Tests.** A browser suite for the keyboard (`keyboard.test.mjs`); in WebKit it steps with Option+Tab, as Safari does without Full Keyboard Access. The suites' `settled()` counts a transition that the next change interrupts as done.
- Version bumped to `0.22.0`; the static assets' cache keys follow it.

## 0.21.0

Stage 4 of the Standard view overhaul (#19), part 3: chart links.

### Changed
- **Each chart has an address of its own.** It names the chart on screen, its open topic and its display, in the address's fragment (`#chart?date=…&time=…&place=…&city=…&latitude=…&longitude=…&timezone=…&lang=…`, then `zi`, `display` and `topic` where they differ from a new chart's), which browsers never send to the server. A topic is named down to its page, such as `roles/direct_wealth/stem/hour` or `relationships/stem_combination:4:year-hour`.
- **Opening a link** — a reload, another tab, or someone else's browser — fills the form with its birth and opens the chart at its topic and display, in the link's language.
- **Back and Forward** step through new charts, topics, Edit and New chart; Back from a chart returns to the form with its birth. The language, the Zi-hour convention and the display replace the current entry. A chart reached through the history is calculated again, and only the latest step's chart is drawn.
- **A link that opens no chart says why**, naming the part that is missing or not valid, and the address becomes the form's; a valid birth waits in the form.
- **Copy link**, in the bar, copies the address. A message over the foot of the page says it was copied, or that the browser refused, and is read out.
- `docs/Standard-Links.md` describes the address.
- **Tests.** A browser suite for chart links (`links.test.mjs`): the address of a new chart, reloads, a new tab in another language, every kind of topic, Back and Forward, Edit and New chart, the entries that settings replace, broken links, a chart that arrives after a later step, and Copy link. `openLink` in `chart-helpers.mjs` opens a link as a new tab would.
- Version bumped to `0.21.0`; the static assets' cache keys follow it.

## 0.20.0

Stage 4 of the Standard view overhaul (#19), part 2: the relationships drawn on the chart.

### Changed
- **Arcs on the chart.** Stem combinations arch above the stems, and branch combinations, clashes and complete frames hang below the branches, each from the middle of its first card to the middle of its last, in the list's lines: solid, dashed for a clash, double for a frame. A frame's middle member has a foot of its own.
  - An arc rises a level for each column it spans, and above every arc it spans or crosses. Four levels hold every combination of four stems or four branches, which a unit test walks through; a chart that needed more would fail visibly.
  - The arcs have rows of their own in the pillar grid, one height each, so the cards stand in the same place whatever the relationships. Real charts have up to seven.
  - The branch arcs' feet reach up to the cards past any opened hidden stems, whose panels cover them. The element tints behind hidden stems are now opaque: the element's colour mixed with the page's tone (`color-mix()`), the same colours as before to within a level.
  - Selecting a relationship darkens its arc and fades the others.
  - With two pillars to a row, on phones, no arcs are drawn; the sheet lists the relationships.
- From 641px wide the pillar headers keep 8px less room below them, since the stem arcs' row keeps its own. Phones are unchanged.
- **Tests.** A browser suite for the arcs (`arcs.test.mjs`) checks each arc's ends, line, feet and level on eight charts at 1440, 1024 and 700px; the chosen arc; the feet behind opened hidden stems; the guard against arcs that would not fit; and, on desktop and mobile, the cards' places with none to seven relationships.
- Version bumped to `0.20.0`; the static assets' cache keys follow it.

## 0.19.0

Stage 4 of the Standard view overhaul (#19), part 1: the chart becomes a workbench. One bar above it, and a panel that explains the chosen topic beside it.

### Changed
- **One bar above the chart** replaces the rows of controls around it. On the left: the chart's date, time, place and true solar time. On the right:
  - a display switch, Characters | Ten Gods | Hidden stems (Merkit | Kymmenen jumalaa | Piilorungot), for every card at once. It replaces Show/Hide Ten Gods;
  - the view, Standard | Evolution. Evolution opens the explorer for this chart's birth, so the landing page no longer asks for a view before there is a chart;
  - FI | EN, which asks for the same chart again in the other language and keeps its display;
  - Edit, which returns to the form with the birth kept and replaces the Back button below the chart, and New chart, which returns to an empty form.
- **The topics in one row above the pillars**: the Day Master, its season, roots and roles, and Relationships (with their number), as buttons rather than the page's faintest text.
- **A panel explains the chosen topic.** From 1200px wide it stands beside the chart, 420px wide, and scrolls on its own. The chart moves over once, when the panel first opens, and keeps its width from 1436px. Narrower, the panel is a sheet over the foot of the page, at most half the screen tall, and the chart keeps room to scroll clear of it. Close, Escape or the topic's own button closes it; the Clear button inside each detail is gone. At 1440×900 every topic's highlighted cards and its explanation are on screen together.
- **Relationships** list in the panel, so their number no longer moves the pillars.
- **Hidden stems join the flow** as a shared row of the pillars' grid: an opened panel moves what follows down instead of hanging over it. The room kept below the pillars and the Back button at the bottom are gone.
- **Pillar names**: each column header pairs the plain name with the poetic one ("HOUR" over "Action gate"). Everywhere else the plain names come in the chart's order (Hour, Day, Month, Year): "Hour–Year · Stem combination", "Year · 丁卯 Ding Mao".
- **A card turns after half a second held**, not one. Under the mouse, a hint above the card says so ("Press and hold: Ten Gods"). A card turned or opened by hand makes the display switch read mixed; pressing its choice again applies it to every card.
- **While the chart is asked for again** (in the other language, or under the other Zi-hour convention), it takes no other clicks.
- On phones the bar's tools read from the left, the display switch spans the width, and the pillars stay two to a row.
- **Tests.**
  - A browser suite for the workbench (`workbench.test.mjs`) checks the acceptance at 1440×900, the one move of the chart, the sheet, the display switch, the half-second hold and its hint, the language switch, Edit and New chart, and the pillar names.
  - The design-system suite checks that opened hidden stems share a row and cover nothing, and that no text on a card or in its hidden stems is clipped or broken inside a word, in any display, from 320 to 1440px, in both languages.
  - The browser suites retry a chart request only when a pooled connection resets before any response.
- Version bumped to `0.19.0`; the static assets' cache keys follow it.

## 0.18.0

Stage 3 of the Standard view overhaul (#18): spacing, type and ink on scales, and one grid for all four pillars.

### Changed
- **Tokens.** Every colour, space, font size and tracking in `style.css` comes from tokens defined once on `:root`. A unit test fails on any raw spacing, font size, tracking or ink value outside them. `docs/Developer/Design-Tokens.md` lists the tokens and their uses, with a specimen.
  - **Space**: one 4px scale, `--space-1` to `--space-8` (4 to 64px). Spacing that was 2, 3, 5, 6, 9, 10, 14, 18, 20, 28, 36, 40, 44 or 56px is rounded onto it. The `-8px` margin patch under the chart header is gone.
  - **Type**: six sizes, `--text-1` to `--text-6` (13, 15, 18, 22, 32 and 52px), where there were fourteen (11 to 52px). Nothing that is read is smaller than 13px, and weight 300 is no longer used below display sizes. Three trackings in em (text, capitals, the eyebrow) replace ten values.
  - **Ink**: `--ink-1` to `--ink-3`, `--line-1` and `--line-2`, `--surface-1` to `--surface-3` and a few more replace ink written out as `rgba()` with eleven alphas. The two near-identical secondary greys are now one, the darker, so every text keeps WCAG AA.
- **One grid for the pillars.** The four pillars share row tracks (label, name, mark, stem, branch) through CSS subgrid, so their rows line up and the cards of a row share one height, front and back.
  - A Finnish label that wraps ("SISÄINEN VUODENAIKA") no longer drops its column's cards.
  - With Ten Gods on, the branch cards are one height instead of 205, 187, 187 and 180px.
- **Room for the hidden stems.** The 110px kept below the pillars is now derived from the tallest hidden-stem panel (three rows) through tokens: 120px.
- **Tests.** A browser suite checks that:
  - the rows line up from 641 to 1440px, in both languages, front and back;
  - the branch chevron clears its card's text;
  - the room below the pillars holds the tallest panel.

  The location list's offset below its field is now read from the spacing token.
- Version bumped to `0.18.0`; the static assets' cache keys follow it.

## 0.17.0

Stage 2 of the Standard view overhaul (#17): the chart shows what the engine knows, and nothing that contradicts it.

### Added
- **Each pillar's own name**: above each pillar, its characters and pinyin (丁卯 Ding Mao) replace the raw Gregorian value, which contradicted the pillar near a boundary. The canonical chart (1988-02-04 16:30, Chengdu) showed "1988" over 丁卯, six hours before Lichun.
- **The characters on the cards**: each card's stem or branch is its main glyph, and the gua lines are secondary. The characters come from a self-hosted subset of Noto Serif TC holding only the 22 stems and branches (SIL OFL 1.1; provenance and licence in `static/fonts/`). Every font stack names it, so they look the same wherever they appear.
- **True solar time**: the header gives the true solar time the day and hour pillars are read from, and its offset from clock time ("True solar time 15:12:24 · 1 h 17 min 36 s behind clock time"), with its date when that differs. The header itself is built on the client from the birth as entered, in the page's language (Finnish writes 16.30); `chart.header` is unchanged in the API.
- **Pillar changes in the engine**: every pillar reports when it last changed before the birth and when it next changes, as `four_pillars.<pillar>.changes.previous` and `.next`. Each gives the elapsed seconds (TT), the pillar on the far side, and the solar term (year, month) or the clock and its reading (day, hour). Day and hour changes follow the clocks the conventions choose, including daylight-saving jumps, and each is confirmed against the engine's own rules. See `conventions-and-output.md`.
- **Marks and exact changes**: a pillar at most 30 minutes from a change is marked beneath its name ("changed 12 min 24 s ago"). Pressing a pillar's name opens its exact changes: the distance to a tenth of a second, the term or the clock, and the pillars on either side.
- **Zi-hour conventions**: where the birth falls in the Zi hour and the two conventions give other pillars, the header offers both, with the chart's own pressed. Choosing the other redraws the whole chart under it (Day Master, Ten Gods, roots, relationships, roles), for that chart only.
- **Notices**: `high_latitude_warning` and `solar_term_ambiguous` are shown when true.

### Changed
- **Precision data is checked before a chart is shown**: an unreadable true solar time, missing or contradictory pillar changes, or flags that contradict the chart stop it, and the form says why.
- **Regression fixture**: gains the four `changes` blocks, each checked against an independent value (`lunar-python` for the terms, a bisection of true solar time for the clocks); otherwise only `engine.version` changes.
- The pillar changes add about 11 ms to a chart.
- New tests: `test_pillar_changes` in the core-engine gate, and an engine-truth browser suite. The browser foundations audits now require the stems and branches to be drawn from the page's own font, and walk the new details, a Zi-hour chart and a high-latitude chart.
- Version bumped to `0.17.0`; the static assets' cache keys follow it.

### Fixed
- The 0.16.1 notes gave the seed kernel's difference from `lunar-python` as a median of 120 s and up to 494 s. Measured again, it is 119 s and 496 s.

## 0.16.1

The engine computes solar terms with the models it reports (#24). The month and year pillars change at the right instants; they were up to 8 minutes off.

### Fixed
- **Solar terms up to 8 minutes off**: the engine evaluated a 6-term seed of VSOP87D and a 4-term nutation series, while reporting `VSOP87D_full_Earth` and `IAU_2000A`. Its jie differed from `lunar-python` by a median of 120 s and up to 494 s (1950-2100), and from the Hong Kong Observatory by −358 s to +328 s. A birth within that margin of a jie could get the wrong month pillar, and at Lichun the wrong year pillar. The engine now evaluates:
  - all 2,425 terms of VSOP87D for the Earth, from IMCCE's published `VSOP87D.ear`;
  - IAU 2000A nutation with the IAU 2006 adjustments: 1,358 and 1,056 terms, IERS Conventions 2010 Tables 5.3a/b. `engine.nutation_model` reads `IAU_2000A_R06`;
  - the FK5 correction of Meeus eq. 32.3.
- **Equinox of date**: VSOP87D carries positions to the date with the IAU 1976 rate of precession (Bretagnon & Francou 1988), but the engine's obliquity and nutation belong to the IAU 2006 precession. Longitudes now refer to the IAU 2006 equinox of date (new decision D-007b; new `engine.precession_model: IAU_2006`). Without this change, the jie drifted by 0.3″ a century against both references: +3 s in the 1950s, −8 s by 2100.
- **Checked against references**:
  - All 240 Hong Kong Observatory terms, 2019-2028, fall within 30.9 s of the published minute; 238 of them round to it.
  - Every jie 1950-2100 is within 2.7 s of `lunar-python` (median 0.6 s).
  - Meeus's Example 25.b is reproduced to 0.0012″. The engine was 3.0″ off.
- The equation of time refers the mean Sun to the same equinox as the true Sun. It had missed the FK5 correction. True solar time moves by 0.006 s.
- **Regression fixture** (1988-02-04, Chengdu): the pillars are unchanged.
  - Lichun 1988 moves from 14:42:08 to 14:42:49.5 UTC. The year and month boundary distances change from 22328.3 s to 22369.5 s. `lunar-python` puts Lichun 0.44 s earlier in TT.
  - The solar longitude changes from 314.738003° to 314.737513°. `lunar-python` gives 314.737519°.
  - `hour_boundary_proximity_seconds` changes from 744.0 to 744.1. The seed series had moved the Sun 1.76″ in the equation of time, 0.12 s of true solar time.

### Changed
- **Model tables checked at startup**: the app reads VSOP87D and both nutation tables when it starts, and checks each one's SHA-256, term counts and term numbering. An altered or truncated table stops it, where before the results would silently change. The tables ship in the package (`resources/astronomy/*`, with a provenance README), and `.gitattributes` keeps them byte for byte on every checkout.
- **Solar term solving**: each jie is solved once per process and reused, and a chart solves only the four nearest its birth. The first chart in a season takes about 90 ms (at most 140 ms); later charts take about 1 ms. The tables load in about 20 ms.
- **Stricter reference tests**:
  - The HKO check converts the engine's TT instants to UTC; it had compared TT with civil time. It now allows 31.5 s against the published minute, down from 420 s.
  - `lunar-python` covers every jie 1950-2100 in TT.
  - New checks: IMCCE's VSOP87D check values; ERFA's `eraP06e` values for the IAU 2006 precession and obliquity; VSOP87D's precession constant as read from its own series.
- **Docs**: `conventions-and-output.md` describes the models step by step. `validation.md` gives the measured accuracy and the one known residual: the engine's instants lie about 0.85 s after the Observatory's. The J2000 equinox tie (FK5, versus the inertial dynamical equinox of the IAU 2006 framework) is about that size. `flags.model_uncertainty_seconds` (0.5 s from 1972) is below that offset.
- Version bumped to `0.16.1`. Besides the numbers above, the regression fixture changes only in `engine.version`, `engine.nutation_model` and the new `engine.precession_model`.

## 0.16.0

Stage 1 of the Standard view overhaul (#16): defects and polish on the landing page and chart, with the layout unchanged.

### Added
- **Birth dates limited to the engine's scope**: the date field's bounds come from the engine policy (1949-2100, decision D-001) through the template, and the page checks the date and time before any request. A missing or out-of-range value is named in the page language beneath its own field, which is marked invalid and focused; editing clears the message. The engine checks the local date's year, so every local date from 1949-01-01 to 2100-12-31 is accepted in any timezone.
- **Progress while a chart is created**: Create chart reads "Creating chart…" / "Luodaan karttaa…", is disabled and the form is `aria-busy` until the chart shows or fails; a second submit meanwhile is ignored.
- **Tab titles**: the landing page's title follows the chosen language, and an open chart names itself by date, time and place ("February 4, 1988 · 16:30 · Chengdu — BaZi").
- **八 tab icon**: two brush strokes in the page's ink on its cream, as SVG with a 16/32/48 px ICO. `GET /favicon.ico` serves it, so no page load gets a 404 any more (the explorer page included).
- **Foundations browser suite** (`tests/browser/foundations.test.mjs`): fonts and (in Chromium) the font that drew every glyph, WCAG contrast composited through every ancestor, element dots and the expand chevron, highlight geometry, third-party and failed requests, form validation and errors, progress, headings, mode labels, and titles, in English and Finnish, desktop and mobile.

### Changed
- **`POST /api/location_suggest` suggests settlements only**: GeoNames populated places (`PPL*`) and administrative areas (`ADM*`). Airports, glaciers, islands, parks, mountains, whole countries, and results without a feature code are left out: "Helsinki" listed a Svalbard glacier, an island and two airports, and the first match for "Luxembourg" was the country's centre, 16 km from the city. The geocoder is asked for 20 candidates, and `limit` counts settlements. Every city-state has its own settlement entry, so Hong Kong (no country) is still suggested. Name resolution in city/country mode is unchanged.
- **Fonts served by the app**: the page used a render-blocking `@import` from Google Fonts; it now uses the variable Manrope and Cormorant Garamond files the explorer already serves, preloaded, one face per family. The page makes no third-party requests.
- **Contrast meets WCAG AA**: the two greys are AA-verified on the page and all five element-tinted panels (`#675F57`, `#655F58`; field labels, pillar labels and Back were 2.7:1, every 11px note and toggle 4.2:1); card subtitles and qi labels use their full ink; the branch expand chevron rises from 1.4:1 to at least 3:1.
- **Hidden-stem dots show their element**: each is filled with its element's colour and ringed in its ink (3:1 on every surface); they were all near-black at half opacity, 1.27:1 apart.
- Location suggestions hang 6px below their field instead of below the status line, list all eight without an inner scrollbar, and form an ARIA combobox/listbox (`aria-expanded`, `aria-activedescendant`, `aria-selected`). A pointer pick leaves focus in the field. An empty answer reads "No matching places."; an answer without a `suggestions` array is reported as a failed search instead of being treated as empty.
- The three birth-data fields share one height (48px; date and time stood 2px taller) and left-aligned text.
- Each view's visible title is its `h1`; the "Four pillars" eyebrow is a paragraph.
- The mode switch is translated (Standardi / Evoluutio) and set in capitals by CSS; the turned-over Ten Gods toggle reads "Hide Ten Gods" / "Piilota kymmenen jumalaa" instead of "Show characters".
- Back arrows are drawn in CSS: the page fonts have no arrow glyph, so "←" came from a system font.
- Version bumped to `0.16.0` with coordinated static-asset cache keys. Only `engine.version` changes in the numerical regression fixture; icons are included in the package data.

### Fixed
- **Chart failures are reported above the button**: every chart error (API failures, and evidence that fails its consistency checks) replaced the picked place's status line. They now appear in the form's alert region; the place status keeps describing the place. The browser suites that corrupt evidence read the error from the new region.
- Form controls inherit the page fonts: the FI/EN and Standard/Evolution switches and every location suggestion rendered in Arial.
- Card highlights stay within the 4px gap between stacked cards; outlines reached 6px (8px for a complete frame) over the neighbouring card.
- Only branch cards, which open on a click, lift under the pointer; stem cards lifted without a click action.

## 0.15.0

### Added
- **Complete Roles view**: Standard's Support control becomes Roles, showing all ten individual Ten Gods under Companion, Output, Wealth, Authority, and Resource. Group and individual states explicitly distinguish visible only, hidden only, both, and not present.
- **Role occurrence inspection**: selects exact visible stems and hidden-stem rows, with precise source and qi position; absent roles remain inspectable with natal scope stated.
- **Roots for every visible stem**: inspect all four positions, including the separately identified Day Master. A dotted outline marks the inspected stem; solid outlines identify same-element hidden-stem root evidence. Exact character matches and opposite-polarity roots remain distinct.
- **Exact hidden-to-visible links**: character-identical matches link to every visible position, including a separately labeled Day Master match. Same-element opposite-polarity roots are never mislabeled as exact matches.
- **Opt-in role profile API**: independent `include_role_profile` flag with `natal_roles_v1` data, stable within-chart occurrence IDs, complete role groups, visible stems, roots, and exact-match references. Existing API sections, including `day_master_context.support`, are unchanged.
- Finnish/English labels, scoped absence states, nested back/focus navigation, exclusive reading selection, and role-profile consistency checks before chart display.
- Independent-reference API tests and a complete Roles browser suite, sharing the browser harness with the existing context and relationship suites.

### Changed
- Root and natal-occurrence collection are shared by Day Master context and Roles to keep their evidence consistent. Ten Gods always remain relative to the natal Day Master, even when inspecting a different stem.
- No new strength weights, favorability ratings, transformations, production dependencies, or Evolution changes.
- Version bumped to `0.15.0` with coordinated static-asset cache keys. Only `engine.version` changes in the numerical regression fixture.

## 0.14.1

### Added
- **Location browser tests** (`tests/browser/location.test.mjs`): same-name places told apart and the picked one charted and opened in the explorer by its coordinates, stale suggestion answers ignored, a picked place editable and kept when returning from the chart, and explorer links with a partial or doubled place rejected. They run in the existing Chromium/WebKit harness, desktop and mobile; the relationship and Day Master context tests' suggestion stubs now have the coordinates the page sends as `location`.

### Changed
- Version bumped to `0.14.1` so HTML, JavaScript, and CSS use coordinated cache keys, and returning visitors load the fixed location code.
- Updated only the regression fixture's `engine.version` metadata; numerical engine results are unchanged.
- **`POST /api/location_suggest` identifies each place**: every suggestion also carries `region` (the geocoder's first-level region, such as a province or state), `latitude` and `longitude`, and `display` names the region: `Chengdu, Sichuan, China` rather than `Chengdu, China`. Empty parts are left out, so a place without a country reads `Hong Kong`, not `Hong Kong, `. Names repeat even within a region (two places called Chengdu in Sichuan, two in Jiangxi), so the coordinates are what identify a suggestion.
- `resolved_location` (city/country mode of `POST /api/four_pillars` and `POST /api/evolution_explorer`, and `POST /api/location_search`) also reports `region`, `latitude` and `longitude`, so a caller can see which place a name was resolved to. A name still resolves to the first geocoder match in the given country; send `location` to compute for a particular place.

### Fixed
- **The chart is computed for the place picked from the suggestions**: the page sent only the picked place's city and country, and the server resolved that name again to the first geocoder match. Picking the second `Chengdu, China` (in Jiangxi, 115.34° E) silently computed the chart for Chengdu, Sichuan (104.07° E), 45 minutes of true solar time away, which can change the hour pillar: 15:40 on 1988-02-04 is a 申 hour in the Jiangxi Chengdu and a 未 hour in the Sichuan one. The page now sends the picked place's coordinates and timezone as `location`.
- The suggestion list and the selected-place status show each place's coordinates, so places that share a name and region can be told apart.
- A place without a country in the geocoder data, such as Hong Kong, can be charted; the page used to send an empty country, which the API rejected.
- **A picked place can be changed without reloading the page**: the field locked after a pick until the chart's Back button, so a wrong pick could only be undone by reloading. The field now stays editable; editing it drops the pick and searches again, and Create chart is disabled until a place is picked.
- **Back from the chart keeps the picked place**: Back cleared the pick and disabled Create chart, so changing only the date or time meant picking the same place again. The pick now stays, with its status line, and Create chart stays enabled.
- **The evolution explorer computes for the picked place too**: its link carried only the city and country, which the explorer resolved by name again. The link now carries the picked place's `latitude`, `longitude` and `timezone`, and the explorer sends them as `location`. Links with `city` and `country` from before still open, resolved by name as they were.
- The explorer no longer shows its bundled sample chart when a link carries only part of the birth, or none of the place: a link from a Hong Kong pick, which had no country, silently opened the sample chart. Such links, and links that name the place both by coordinates and by city, now show an error; `/explorer/` with no birth at all still shows the sample.
- The evolution explorer page is rendered from a template with versioned asset URLs (`?v=<version>`), like the start page. Its script and data were served with no cache instructions, so after an update a browser could keep running the cached old explorer. The page is served at `/explorer/`; `/explorer/index.html` no longer exists.
- **Location suggestions only ever list results for the current input**: responses were applied in the order they arrived, so a slow response for a partial query could replace the list for the full query. Typing `Chengdu` could list `Zhengzhou, China` first (the top result for `Che`, `Chen` and `Cheng`), and picking the top entry gave the wrong birthplace, longitude and true solar time. A lookup is now cancelled as soon as the input changes, and a response for anything other than the current input is discarded.
- The previous list is hidden as soon as the input changes, so Enter or a click can no longer pick a result for an earlier query while the new lookup runs.
- Clearing the input or choosing a city cancels the pending lookup, which could otherwise reopen the list or replace the status. A cancelled lookup is never reported as an error; a failure of the current lookup still is.

## 0.14.0

### Added
- **Day Master context in Standard mode**: a restrained summary beneath the date with Month, Roots, and Support controls. Details show the resolved solar month's traditional group and branch composition, exact same-element hidden-stem roots, and visible/hidden Companion and Resource occurrences.
- **Precise evidence highlights**: participating cards and the matching hidden-stem rows are outlined without changing natal colors, card geometry, flip state, or open panels. Context and relationship details are mutually exclusive.
- **Day Master context API**: independent `include_day_master_context` enrichment with explicit `natal_presence_v1` policy. Root matches distinguish exact stems from opposite polarity; Resource is separate, and the Day Master itself is excluded from Companion occurrences.
- Finnish/English context labels, keyboard controls, focus return, live announcements, reduced-motion support, and explicit absence states.
- Reference-based API tests, real-API desktop/mobile browser coverage, and user/API documentation.

### Fixed
- Escape dismisses the active reading even when pointer activation leaves keyboard focus outside the chart (including WebKit).
- Missing or inconsistent context, hidden-stem composition, or highlight surfaces stop chart creation visibly rather than showing contradictory evidence.

### Changed
- Version bumped to `0.14.0` so HTML, JavaScript, and CSS use coordinated cache keys.
- Updated only the regression fixture's `engine.version` metadata. Numerical engine results, dependencies, and Evolution definitions/inference are unchanged.
- Seasonal groups and month-branch composition are displayed separately. No overall-strength, favorability, transformation, or within-month governing-qi assessment is introduced.

## 0.13.0

### Added
- **Natal relationships API**: `POST /api/four_pillars` accepts `include_interactions`, independently of all other enrichments. It returns every occurrence of the five stem combinations, six branch combinations, six branch clashes, and four complete three-harmony frames, including repeated and non-adjacent matches.
- **Standard-mode relationship strip**: selecting an entry outlines the participating cards without moving the pillars or changing their element colors. Details below the chart show identities, natal elements, Ten Gods, and every hidden-stem role. Solid, dashed, and double line styles distinguish pairs, clashes, and complete frames without good/bad color coding.
- **Chart-wide Ten Gods toggle**: turn all cards together while retaining individual long presses and branch-panel clicks/taps. Mixed card states are exposed accessibly.
- Keyboard selection, Escape/clear focus return, screen-reader announcements, reduced-motion support for new controls, and Finnish/English relationship labels.
- Independent reference tests for relationship recognition and API compatibility; API CI includes the new suite. A Node/Playwright browser harness covers desktop/mobile interaction and layout regressions using explicitly configured existing tooling.
- Relationship policy, API contract, and browser-test documentation.

### Changed
- Version bumped to `0.13.0`, including static-asset cache keys.
- Updated only the regression fixture’s `engine.version` metadata; every other engine output field is unchanged.
- Standard explicitly distinguishes detected presence from transformation: complete frames require all three members; partial frames are not emitted; transformation is never asserted. Potential elements are shown only for stem combinations and complete frames.
- The shared Evolution catalog remains unchanged; Standard does not use its nearest-pair selection or inference.

## 0.12.0

### Added
- **Ten gods API enrichment**: `POST /api/four_pillars` accepts `include_ten_gods` and returns a `ten_gods` section with the ten god of each pillar's stem and of every hidden stem, relative to the Day Master (the day stem itself is `day_master`).
- **Ten gods chart interaction**: holding any chart card for one second flips it to its ten god; branch cards list the ten gods of all hidden stems with their qi type, in the same format as the hidden stems panel. Holding again flips the card back.
- **Ten gods mapping loader** (`eight_characters/ten_gods.py`): `ten-gods.csv` is now the runtime source. It is validated at startup, and every cell must agree with the element-cycle derivation in `evolution.primitives.ten_god_index`.
- **Ten gods test suite** (`tests/test_api_ten_gods.py`): checks the mapping against `evolution.primitives.ten_god_index` and the `lunar-python` reference, pins the canonical 1988-02-04 chart through the API, and compares the ten gods for 300 random `lunar-python` charts with `lunar-python`'s own.
- **Index route test** (`tests/test_api_index_route.py`).
- Ten god names in `localization.js` (Finnish and English).

### Changed
- `tzdata` is pinned to `2026.4` (IANA 2026d) and the regression fixture's `engine.tzdb_version` is updated to match. Compared with the fixture's previous `2025.3`, this changes offsets from late 2026 onward in British Columbia, Alberta, the Northwest Territories, Morocco and Western Sahara; in Moldova since 2022; before 1967 in the legacy `EST5EDT`, `CST6CDT`, `MST7MDT` and `PST8PDT` zones; and for one day each in Bogotá (1992) and Tehran (1979).
- `engine.tzdb_version` no longer falls back to `system`; `tzdata` is a required dependency.
- A quick click on a branch card still toggles its hidden stems panel; the release that ends a long press does not.
- Chart cards are no longer text-selectable, so a long press on touch devices flips the card instead of selecting text.
- Version bumped to `0.12.0`.

### Fixed
- **Reproducible timezone conversion**: zones are now loaded only from the pinned `tzdata` package. Previously Python's `zoneinfo` preferred the host's system tz database, so results could differ between machines and `engine.tzdb_version` could name data that was not used (for example, a birth in Inuvik on 2026-12-01 at 12:00 resolved to 19:00 UTC on a host with IANA 2026c, while the reported `tzdata` 2026.4 gives 18:00 UTC).
- Unknown timezone identifiers are rejected with the same error on every host; case-insensitive filesystems no longer accept keys such as `asia/shanghai`.
- The regression-safety gate no longer fails on fresh installs because of an unpinned `tzdata` version.
- `GET /` returned 500 with Starlette 1.x, which removed the `TemplateResponse(name, context)` signature; the index now uses the request-first signature.

## 0.11.0

### Added
- **Hidden stems API** (`POST /api/hidden_stems`): resolves hidden stems (main, middle, residual qi) for each earthly branch in the four pillars, returning enriched data with element, polarity, and qi type.
- **Hidden stems chart interaction**: clicking any branch card in the chart view reveals its hidden stems in a smooth animated panel that slides out below the card.
- **Hidden stems data** (`eight_characters/resources/mappings/hidden-stems.csv`): canonical mapping of all 12 earthly branches to their hidden stem characters.
- **Ten gods data** (`eight_characters/resources/mappings/ten-gods.csv`): reference mapping for ten gods relationships.
- **Hidden stems test suite** (`tests/test_api_hidden_stems_endpoint.py`).
- Element name and qi-type translations in `localization.js` (Finnish and English).

### Changed
- Branch cards in the chart view are now interactive (click to expand/collapse hidden stems).
- Hidden stems panel uses absolute positioning so expanding a panel never shifts the chart, header, or back button.
- Back button positioned with extra clearance to avoid overlap with expanded panels.
- Date input restricted to 4-digit years (`max="9999-12-31"`).
- Version bumped to `0.11.0`.

### Fixed
- Chart view pinned to top of viewport (`align-self: flex-start`) so expanding hidden stems only pushes content downward, never upward.

## 0.10.4

Previous release — BaZi Four Pillars chart with location autosuggest, i18n (Finnish/English), Docker/Render deployment, and full astrometric engine.
