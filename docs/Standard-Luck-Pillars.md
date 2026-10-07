# Luck pillars in Standard mode

A chart asked for with a gender shows its luck pillars (大運 Da Yun): the ten-year
cycles that follow the birth, each read against the natal chart. How the engine
calculates them, and what it says of each decade, is in
[Ten-year luck pillars](Luck-Pillars.md).

## Asking for them

The form's Gender is optional: Not given (the default), Female or Male. Only the luck
pillars need it, because the traditional rule sets their direction by it and by the
year stem's polarity. A chart without a gender has no luck pillars, and asks the API
for none.

The gender is part of the chart's link (see [Chart links](Standard-Links.md)). Edit
keeps it with the birth; New chart starts without one.

## The ribbon

The ribbon stands under the chart's topics. It shows:
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
browser's own clock. Dates and years are read on the birth place's clock.

Where the decades do not fit, the ribbon scrolls sideways within itself, never the
page, and keeps the open decade, or today's, in sight. On a phone, the ribbon's name
and Today stand above it.

What the ribbon does:
- **A chip** opens its decade's page in the panel: at today's phase when today falls in
  that decade, and at its stem phase otherwise. Pressed again, it closes the page.
- **‹ and ›** step one phase back or forward. They go through the years before the
  decades, then each decade's stem phase and branch phase, and stop at either end. With
  nothing open, they start from today's phase.
- **Today** opens today's phase. It is spent while today's phase is open, and after the
  last decade there is no today.

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
  in for the decade. Resting the pointer on a line, or clicking it, rings the natal
  cards it names, as the panel's other lines do (see
  [Relationships](Standard-Relationships.md)). The luck pillar has no card on the
  chart.
- **Elements.** Each element's count with the luck pillar: the natal chart's eight
  characters, and the luck pillar's that act in the phase, which makes ten in the stem
  phase and nine in the branch phase. Counts are tallies, not strength.

The years before the first decade have a page of their own: their dates and ages, and
that no luck pillar falls there.

Opening a decade replaces any other open topic, and another topic replaces it. Nothing
on the chart moves, opens or changes colour. Nothing weighs strength, applies a
transformation or predicts.

## Keyboard, commands and links

- The chips take one tab stop: the open decade's chip, else today's. Left and Right
  move between them, and Home and End go to either end, opening nothing. Enter or Space
  opens one. See [Keyboard](Standard-Keyboard.md).
- Escape closes the page and gives focus back to its chip, as Close does.
- The commands (⌘K or Ctrl+K) offer the years before the decades and each decade,
  named as their chips are.
- The address names the open phase: `topic=luck/before`, or
  `topic=luck/<decade>/<stem|branch>`, such as `luck/5/stem`.

## Printing and comparing

Print leaves the ribbon out; an open decade's page prints below the chart, as any open
topic does (see [Copying and printing](Standard-Copy-and-Print.md)). In a comparison,
a chart whose link has a gender shows its own ribbon; the second birth starts without
one (see [Comparing two charts](Standard-Compare.md)).

## When the page refuses

The page checks the API's luck pillars and their context as it reads them: the
decades in sequence and meeting end to end, two phases each that meet, each
relationship naming the luck pillar, and counts that add up. A chart whose luck pillars
do not hold together is not drawn: the form says so.

See [browser regression tests](../tests/browser/README.md): `luck.test.mjs`.
