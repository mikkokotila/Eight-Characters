# Luck pillars in Standard mode

A chart asked for with a gender shows its luck pillars (大運 Da Yun): the ten-year
cycles that follow the birth, each read against the natal chart. How the engine
calculates them, and what it says of each decade, is in
[Ten-year luck pillars](Luck-Pillars.md).

A chart with a gender opens natal, drawn exactly as a chart without one. Showing its
luck pillar brings in the rest. One choice drives them all: a period, either the years
before the first decade or one of a decade's two phases. The ribbon marks it, the
chart shows it as a fifth pillar, and the panel can show its page.

## Asking for them

The form's Gender is optional: Not given (the default), Female or Male. Only the luck
pillars need it, because the traditional rule sets their direction by it and by the
year stem's polarity. A chart without a gender has no luck pillars, and asks the API
for none.

The gender is part of the chart's link (see [Chart links](Standard-Links.md)). Edit
keeps it with the birth; New chart starts without one.

## The ribbon

While the luck pillar shows, the ribbon stands under the chart's topics. It shows:
- **Before**: the years before the first luck pillar, as ages (`0–8`);
- **each decade**: its characters with their names, the age it starts at, and two bars,
  one for each phase.

The decades are grouped by the direction their branch travels, with its season. San
Ming Tong Hui judges a luck cycle by this travel:

| Group | Branches |
| --- | --- |
| East · Spring | 寅 Yin, 卯 Mao, 辰 Chen |
| South · Summer | 巳 Si, 午 Wu, 未 Wei |
| West · Autumn | 申 Shen, 酉 You, 戌 Xu |
| North · Winter | 亥 Hai, 子 Zi, 丑 Chou |

Today's decade wears a dot, and its bar for today's phase is half dark. Today is the
browser's own clock. Dates and years are read on the birth place's clock. A birth still
to come, or a life past its last decade, has no today on the ribbon.

Where the decades do not fit, the ribbon scrolls sideways within itself, never the
page, and keeps the open decade, or today's, in sight. On a phone, the ribbon's name
and Today stand above it.

What the ribbon does:
- **A chip** chooses its decade, shows it in the chart and opens its page: at today's
  phase when today falls in that decade, and at its stem phase otherwise. Pressed again,
  it closes the page; the decade stays in the chart.
- **‹ and ›** step the luck pillar one phase back or forward. They go through the
  years before the decades, then each decade's stem phase and branch phase, and stop at
  either end. An open page follows them; a closed one stays closed.
- **Today** chooses today's phase and opens its page. It is spent while today's phase
  is open, and while today falls outside the ribbon.

## The fifth pillar

A chart with a gender opens natal: its four pillars, with no ribbon and no fifth
column, drawn as the same birth without a gender is, in every display and at every
width. **L**, or the Natal / With luck switch among the chart's controls, shows the
luck pillar: the chosen period, at first today's phase, stands in a fifth column beside
the Year, and the ribbon comes under the topics. L or the switch hides them again, and
the chart is natal once more. Choosing a period with the keys or the commands shows it
too.

While it shows, choosing another period moves nothing on the chart: the column keeps
its room, and before the first decade its cards stay empty.

Shown, the luck pillar reads as the natal pillars do: its name, the decade's place and
years, its characters, and its stem and branch cards. Its mark says the phase and when it
ends, such as "Stem phase until 2028". In the stem phase the stem leads, ringed, and
the branch acts too. In the branch phase the branch leads, ringed, and the stem is set
aside: it turns to its element's tint and says "Set aside". Before the first decade the
column says when the first starts, and its cards stay empty.

Its cards take the chart's display: characters, Ten Gods (read from the natal Day
Master) or hidden stems. A long press turns one, and a click opens the branch's hidden
stems, as on the natal cards. Its name opens the decade's page. Hidden and shown again,
the column is drawn anew, in the chart's display.

The relationships it forms with the natal pillars stand as arcs, drawn as the natal arcs
are: a stem's above the stems, a branch's below the branches, each in its kind's line
(see [Relationships](Standard-Relationships.md)). They ride an outer band beyond the
natal arcs' levels, every one ending on the luck pillar, the narrower lower. A triple's
middle member stands under its arc. On a natal card their feet stand beyond the natal
arcs' feet, so no natal arc's foot moves on its card. In the branch phase a stem's
relationship rests, and its arc recedes. While the luck pillar shows, the natal arcs
recede too, in the secondary line. A relationship chosen in the list, natal or the luck
pillar's, stands in the ink, and every other arc recedes. The outer band is there only
while the luck pillar shows: natal, the arcs' rows are a chart's without a gender.

On a phone the luck pillar stands above the two-by-two chart, its stem beside its
branch.

## The topics with luck

While the luck pillar stands in the chart, the period it shows adds to the chart's
topics, for its phase:
- **Roots** reads "+ luck" when the luck branch roots the Day Master. The Roots page
  then adds the luck branch, with its roots, beside the natal root branches.
- **Roles** reads "+ 2 new" for the roles new to the chart that act in the phase. The
  Roles page adds what the luck pillar brings, each marked when new.
- **Relationships** adds the luck pillar's that act in the phase to its count, as in
  "Relationships (3 + 2)". The list adds them under their own heading. They open as the
  natal ones do, with the luck pillar's card and arc; the canon has no readings for
  them yet.

The topics' icons say the same on their badges: Relationships 3+2, Roots 3+1 (the luck
branch as one more root), Roles +2; the words are in their names, as a screen reader
reads them. Natal, there are none of these: the topics read as a chart's without luck
pillars. A luck relationship chosen that stops acting, as a stem's does in the branch
phase, closes.

## A decade's page

The page shows:
- **The decade.** Its place in the sequence and the sequence's direction (forward or
  backward); its characters and names; its dates and ages; its direction and season.
- **Its two phases**, with their dates:
  - the stem phase, its first five years, when the stem leads and the branch acts too;
  - the branch phase, its last five, when the branch acts alone.

  The phase shown is pressed, and the other opens with a click. Today's phase is marked
  "now".
- **What it brings.** The luck stem, and the hidden stems of the luck branch. Each has
  its Ten God, read from the natal Day Master, and is marked "new to this chart" when no
  natal stem has that Ten God. The stem acts in the stem phase only: in the branch
  phase its line says "not now" and turns to the secondary ink.
- **The Day Master on the luck branch.** Its stage, one of twelve from Birth to Nurture
  (in English as the canon names them), and its roots there.
- **With the natal chart.** Each relationship the luck pillar forms with the natal
  pillars, named as the relationships list names them, with the luck pillar as Luck.
  Each says when it acts: a stem's relationship in the stem phase only, a branch's in
  both. A relationship that completes a natal half into a whole names the half it takes
  in for the decade. Resting the pointer on a line, or clicking it, rings the cards it
  names, the natal ones and the luck pillar's, as the panel's other lines do (see
  [Relationships](Standard-Relationships.md)).
- **Elements.** Each element's count with the luck pillar: the natal chart's eight
  characters, and the luck pillar's that act in the phase, which makes ten in the stem
  phase and nine in the branch phase. Counts are tallies, not strength.

The years before the first decade have a page of their own: their dates and ages, and
that no luck pillar falls there.

Opening a decade replaces any other open topic, and another topic replaces it; the
luck pillar stays in the chart. Nothing weighs strength, applies a transformation or
predicts.

## Keyboard, commands and links

- While the chart has focus, **L** shows and hides the luck pillar, **[** and **]**
  step it a phase, **{** and **}** a decade, and **N** chooses today's phase and opens
  its page. Natal, a step shows the luck pillar a phase or a decade from today's:
  before a birth still to come, from just before the first; past the last decade, from
  just after the last.
- The chips take one tab stop, the chosen period's chip. Left and Right move between
  them, and Home and End go to either end, opening nothing. Enter or Space opens one.
- The luck pillar's cards follow the Year's in the cards' arrows while it shows. Enter or
  Space opens its branch's hidden stems, T turns a card, and R opens the decade's page.
  Hidden, the luck pillar, its ribbon and its page are gone, and focus that was on them
  goes to the chart's cards. See [Keyboard](Standard-Keyboard.md).
- Escape closes the page and gives focus back to its chip, as Close does.
- The commands (⌘K or Ctrl+K) offer the years before the decades, each decade named as
  its chip is, and the switch's other side.
- The address names the period standing in the chart, `luck=before` or
  `luck=<decade>/<stem|branch>` such as `luck=5/stem`, and the open page,
  `topic=luck/before` or `topic=luck/<decade>/<stem|branch>`. A page shows the period
  standing in the chart. A change of language keeps the luck pillar shown.

## Printing and comparing

Print leaves the ribbon out. A luck pillar shown prints in the chart as its fifth
pillar; a natal chart prints its four. An open decade's page prints below the chart, as
any open topic does (see [Copying and printing](Standard-Copy-and-Print.md)). In a
comparison, a chart whose link has a gender has its own luck pillars, natal until they
are shown; the second birth starts without one (see
[Comparing two charts](Standard-Compare.md)).

## A nominal timeline

The luck pillars count their start from the jie (the month's solar term) next to the
birth, with an allowance of 3 seconds for the solar terms' own uncertainty. That is
wider than the natal chart's 0.5 seconds. A birth within that allowance of a jie
has a nominal timeline: on the jie's other side, the decades and the age they start at
are other ones, and at Lichun so is their direction. While the luck pillar shows, the
chart says so in a notice under its name, and each decade's page and the years before
say that their dates are nominal. Natal, the notice goes with the luck pillar, and the
chart's own notices stay. See [Uncertainty](Luck-Pillars.md#uncertainty-and-reference-comparison).

## When the page refuses

The page checks the API's luck pillars, their context and their cards as it reads
them: the decades in sequence and meeting end to end, two phases each that meet, each
relationship naming the luck pillar and acting by the phase rule, counts that add up,
and cards drawn for the decade's own characters. A chart whose luck pillars
do not hold together is not drawn: the form says so.

See [browser regression tests](../tests/browser/README.md): `luck.test.mjs`.
