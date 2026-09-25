# Standard-mode browser regression tests

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

The tests calculate charts through the real `/api/four_pillars` endpoint. They stub
only location suggestions and substitute fixed test coordinates for geocoding.
Malformed-response tests intentionally modify the real response to verify visible
errors. No real birth records or saved user data are used.

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

The Roles suite covers all ten individual roles, five-group presence states,
exact hidden-to-visible matching (including the separately labeled Day Master),
all visible-stem roots, unchanged natal role reference, stable occurrence IDs,
absent roles, unrooted visible stems, repeated visible identities, nested back/focus
navigation, exclusive selection, card gestures, Finnish layouts, and corrupted
profile rejection. `chart-helpers.mjs` is shared by all three suites.
