# Changelog

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
