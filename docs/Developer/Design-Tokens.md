# Design Tokens (Standard view)

The Standard view's stylesheet, `eight_characters/static/style.css`, takes every
colour, space, font size and tracking from tokens defined once on `:root`.
Outside those definitions it holds no raw spacing, font size, tracking or ink
value: `tests/test_api_index_route.py`
(`test_stylesheet_takes_spacing_type_and_ink_from_its_tokens`) fails on any.

![Every token, drawn with the app's own stylesheet](design-tokens-specimen.png)

## Colour

| Token | Value | Use |
|---|---|---|
| `--bg` | `#F5F0E8` | the page |
| `--ink-1` | `#2A2520` | text (13.4:1 on the page) |
| `--ink-2` | `#655F58` | labels, notes, secondary text (5.6:1) |
| `--ink-3` | ink at 65% | placeholders (4.6:1) |
| `--ink-found`, `--ink-error` | `#3F6246`, `#8B4E45` | a found place; an error (6.1:1, 5.7:1) |
| `--line-1`, `--line-2` | ink at 12%, 30% | a hairline at rest; hover, focus, a current choice |
| `--surface-1`, `--surface-2`, `--surface-3` | white at 30%, 50%, 80% | at rest; raised or pressed; floating over content |
| `--surface-page-1`, `--surface-page-2` | the page tone at 85%, 92% | an option under the pointer; the active option |
| `--shadow-1`, `--shadow-2`, `--shadow-sheet` | | a focused field; anything raised; the sheet over the foot of the page |
| `--sheen` | | the light across a card's face |
| `--<element>-bg`, `--<element>-text`, `--<element>-tint` | the tint: its element at 20% on the page tone (22% for metal and water), mixed opaque with `color-mix()` | each element's cards, their ink, and its hidden-stem panels |

`--ink-1` and `--ink-2` meet WCAG AA (4.5:1) on the page and on every
element-tinted panel. De-emphasis comes from size, case and tracking, not from a
lighter ink.

## Space

`--space-1` to `--space-8`: 4, 8, 12, 16, 24, 32, 48 and 64px. Margins, padding
and gaps use only these, or `calc()` of them.

## Type

| Token | Size | Use |
|---|---|---|
| `--text-1` | 13px | notes, labels, metadata: the smallest size for content |
| `--text-2` | 15px | controls and running text |
| `--text-3` | 18px | names |
| `--text-4` | 22px | a detail's heading; a pillar's characters |
| `--text-5` | 32px | a page's title |
| `--text-6` | 52px (44px up to 640px wide) | the character on a card |

- Families: `--font-serif` (Cormorant Garamond), `--font-sans` (Manrope), and
  `--font-glyph` (the Noto Serif TC subset of the 22 stems and branches). The
  serif and sans stacks name the Noto face second, so the stems and branches look
  the same wherever they appear.
- Tracking: `--tracking-1` (0.02em) for text, `--tracking-2` (0.18em) for
  capitals, `--tracking-3` (0.3em) for the eyebrow above a title. They are in em,
  so they follow the size.
- Weight 300 is not used below display sizes.

## The pillars and the panel

- One grid holds all four pillars: four columns, two up to 640px wide. Each
  pillar spans eight shared rows (label, name, mark, stem arcs, stem, branch,
  hidden stems, branch arcs) as a subgrid, with its header and its cards as
  nested subgrids. The rows line up across the pillars, and the cards of a row
  share one height, front and back. Opened hidden stems grow their own row, in
  the flow: nothing hangs over what follows. `tests/browser/design-system.test.mjs`
  checks this from 641px to 1440px, in both languages.
- The relationship arcs lie in their own rows, under the pillars. Each row keeps
  one height whatever the arcs in it, so the cards stand in the same place; up
  to 640px there are no arcs and the rows are empty.
  - `--arc-base`, `--arc-step`: the rise of the lowest arc, and of each level
    above it: 6 and 8px.
  - `--arc-band`: the height of each arcs' row, room for four levels: 40px.
  - `--arc-spread`: the distance between the feet of arcs that meet on one card:
    6px.
- `--card-min-height`: a card's least height (160px up to 640px wide).
- `--hidden-stem-row`: the line of a hidden stem in its panel.
- `--chart-width`: the chart column, 960px.
- `--panel-width`: the panel that explains a topic beside the chart, from 1200px
  wide: 420px.
- `--sheet-height`: narrower, the panel is a sheet over the foot of the page, at
  most half the screen tall. The chart keeps as much room below it to scroll
  clear of the sheet.
- A page in the panel reads from the left:
  - its title in `--text-4`;
  - a line in `--ink-2`;
  - its content;
  - one note at its foot in `--text-1`, at most 35em wide: about 60 to 75
    characters to the line.

  Its labels, a pillar's plain name or a group of roles, take the column
  header's capitals. The roles matrix is no wider than `--panel-width`, so on a
  wide sheet each mark stays near its role.
