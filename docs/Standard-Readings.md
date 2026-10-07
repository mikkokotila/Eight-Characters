# Readings in Standard mode

In an English chart, the pages the chart already has read what the canon,
`canon/Taxonomy.md`, says of this chart. The engine chooses the passages that
apply, from the Day Master, each pillar's stem and branch, the life stages and
the relationships it finds. The words are the canon's: nothing rewrites,
shortens or rephrases them, and nothing in them assesses strength or predicts.

The cards stay as they are. Nothing about a reading starts on a card.

## A reading

Each reading is one line:
- its key, which names it, such as "Who stands here · Rob Wealth";
- the passage's own first sentence;
- the chevron the branches use for their hidden stems.

A click, Enter or Space opens the rest of the passage beneath, and closes it
again. A kind of reading that is open stays open on the next page that has it,
so moving from pillar to pillar keeps the same lines open. A line in the panel
points at the cards it reads, as the panel's other lines do.

## Where readings are

- **A pillar's page**, from the pillar's name:
  - the Day Master's lens on the pillar;
  - who stands on its stem: the stem's role, or on the Day, the Day Master;
  - that stem's own stage on its branch;
  - the ground, the branch in this pillar, and the branch itself;
  - the Day Master on this ground (on the Day, its seat) and its stage here;
  - the relationships that touch the pillar, each with its first sentence;
  - what these readings are.
- **The Day Master's page**, from the Day Master line, which opens it:
  - what the Day Master is, and how it meets any ground;
  - its lens on each pillar;
  - where it is in its cycle, as one sentence (each clause opens its pillar at
    its stage) and as a ring of the twelve stages with this chart's branches on
    it;
  - the twelve stages;
  - the pattern of reconception.
- **Relationships:**
  - in the list, each relationship's first sentence under its name, and below
    the list what each kind of relationship is;
  - on a relationship's page:
    - its pillar pairing;
    - for a stem combination, what it is with the Day Master, or between two
      other stems, its dynamic and its mechanics;
    - the entry itself.

  Where the chart settles a condition the entry states, it says so before the
  entry: "In this chart: born in the Wu month, in summer. The entry reads …".
  Today that is the Zi–Wu clash's season.
- **Roles:** what the roles are, above the overview; on a role's page, what the
  role is, and what it means on each stem where it stands.
- **The season:** the month's branch, in the Month and in itself.
- **Roots:** the Day Master on each root's branch.

A reading's links open the page they name at the line they name, open, in one
step of the history, as the commands do.

## Keys

R on a focused card opens its pillar's page with the card's own line open: a
stem's who-stands-here, or a branch's ground. While a pillar's page is open, the
arrow keys turn it: the focused card's pillar opens at its line, and what is open
stays open. See [the chart by keyboard](Standard-Keyboard.md).

## Language

The canon speaks English, so readings are English only. A Finnish chart asks the
API for no reading, and every page is as it was before readings. The language
switch asks for the chart again, with or without its reading.

The app writes pinyin without diacritics, and so does the canon: a test refuses
any. The canon's arrow, in the stem combinations' titles, is drawn, as the app's
other arrows are.

## On paper

A reading prints as it is open: its line, and its passage when that is open.
The chevrons and links are left out.

## What the canon holds that no chart shows yet

Every one of the canon's paragraphs reaches some chart's reading. A half-frame
reads its frame's opening, the points of its two branches and the paragraph on
half-frames; a punishment reads the paragraphs for the form the chart holds, whole
or half; a self-punishment reads its own branch. Some sentences in the passages
that are read depend on what the app does not compute: Luck Pillars, strength,
transformation. They are listed, with why, in
[issue #39](https://github.com/mikkokotila/Eight-Characters/issues/39).

## For developers

- **The canon is packaged.** The API reads the canon from the package:
  `eight_characters/resources/canon/Taxonomy.md` is a byte-for-byte copy of
  `canon/Taxonomy.md`. After any change to the canon, copy it again. A test
  fails while the two differ.
- **The parser.** `eight_characters/canon.py` reads the canon into keyed
  passages. It refuses a canon whose sections, entries or placements are
  missing or repeated, or whose passages hold Markdown other than emphasis and
  strong.
- **The reading.** `eight_characters/reading.py` chooses the passages for a
  chart, under the policy `canon_taxonomy_v1`. Where it relies on the canon's
  exact words, it checks them when the app starts, and refuses to start if they
  changed. These are the six sentences that hold only for a Day Pillar, the
  Zi–Wu season sentences, the stem combinations' labels, the punishments' and
  self-punishments' labels, the frames' points and half-frame paragraphs, and the
  stage table.
- **The page.** `static/readings.js` builds the lines.

See [the API](api.md#canon-readings-include_reading) and the
[browser regression tests](../tests/browser/README.md): `reading.test.mjs`.
