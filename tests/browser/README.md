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
natal colors, global and individual Ten Gods flips, long-press release suppression,
quick clicks/taps, cancelled touch holds, repeated combinations, complete frames,
empty results, Finnish, narrow viewports, reduced motion, chart reset, and explicit
errors for absent or malformed relationship data.


The Day Master context suite additionally checks all three controls, exact versus
opposite-polarity root evidence on both hidden-stem surfaces, Companion/Resource
presence, no/one/four-root layouts, explicit support absence, resolved solar-month
boundaries, mutually exclusive relationship/context details, and rejection of
missing or inconsistent context. Screenshots include context overview, season,
roots, support, flipped cards, absence, four roots, and Finnish layouts.

The location suite checks that places sharing a name are told apart by region and
coordinates, that the picked place's coordinates reach the chart and the evolution
explorer, that a slow answer for an earlier query never replaces the list, that a
picked place can be edited and is kept when returning from the chart, and that
explorer links naming the place partly, twice, or only by city and country behave
as documented.
