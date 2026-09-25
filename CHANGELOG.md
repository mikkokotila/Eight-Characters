# Changelog

## Unreleased

### Changed
- **`POST /api/location_suggest` identifies each place**: every suggestion also carries `region` (the geocoder's first-level region, such as a province or state), `latitude` and `longitude`, and `display` names the region: `Chengdu, Sichuan, China` rather than `Chengdu, China`. Empty parts are left out, so a place without a country reads `Hong Kong`, not `Hong Kong, `. Names repeat even within a region (two places called Chengdu in Sichuan, two in Jiangxi), so the coordinates are what identify a suggestion.
- `resolved_location` (city/country mode of `POST /api/four_pillars` and `POST /api/evolution_explorer`, and `POST /api/location_search`) also reports `region`, `latitude` and `longitude`, so a caller can see which place a name was resolved to. A name still resolves to the first geocoder match in the given country; send `location` to compute for a particular place.

### Fixed
- **The chart is computed for the place picked from the suggestions**: the page sent only the picked place's city and country, and the server resolved that name again to the first geocoder match. Picking the second `Chengdu, China` (in Jiangxi, 115.34° E) silently computed the chart for Chengdu, Sichuan (104.07° E), 45 minutes of true solar time away, which can change the hour pillar: 15:40 on 1988-02-04 is a 申 hour in the Jiangxi Chengdu and a 未 hour in the Sichuan one. The page now sends the picked place's coordinates and timezone as `location`.
- The suggestion list and the selected-place status show each place's coordinates, so places that share a name and region can be told apart.
- A place without a country in the geocoder data, such as Hong Kong, can be charted; the page used to send an empty country, which the API rejected.
- **A picked place can be changed without reloading the page**: the field locked after a pick until the chart's Back button, so a wrong pick could only be undone by reloading. The field now stays editable; editing it drops the pick and searches again, and Create chart is disabled until a place is picked.
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
