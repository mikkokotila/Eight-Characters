# Relationships in Standard mode

Relationships, in the row of topics above the pillars, says how many natal
relationships were detected and opens their list in the panel: beside the chart
from 1200px wide, and as a sheet over the foot of the page when narrower. Select
an entry to outline its participating cards. Select it again or press Escape to
remove the selection; a second Escape, Close, or Relationships again closes the
list. The controls work with a pointer, touch, or keyboard.

The chart draws them as well. Stem combinations arch above the stems, and branch
combinations, clashes and frames hang below the branches, each from the middle of
its first card to the middle of its last; a complete frame's middle member has a
foot of its own. An arc rises a level for each column it spans, and above any arc
it spans or crosses, so arcs that share a card never run together. The arcs have
rows of their own in the pillar grid, one height each, so the cards stand in the
same place whatever the relationships. The branch arcs' feet reach up to the
cards behind any opened hidden stems. Selecting an entry darkens its arc and
fades the others. With two pillars to a row, up to 640px wide, nothing is drawn,
and the list in the sheet names them.

Resting the pointer on an entry for half a second rings its cards and darkens its
arc; in the details, each member points at its card, and a branch's hidden stems at
their rows.

The selected relationship's details open below the list, and the pillars stay in
place: from 1200px wide the chart moves over once, when the panel first opens,
and a sheet only lies over the page. The details identify the stems or branches,
their natal elements, and the relevant Ten Gods. Branch details show every hidden
stem's role and qi type. Entries and details name the pillars plainly (Hour, Day,
Month, Year) in the chart's display order, as in "Hour–Year"; the API retains
chronological pillar order.

Solid lines identify combination pairs, dashed lines identify clashes, and double
lines identify complete three-harmony frames, on the arcs, in the list, and around
the selected cards. These are line styles, not ratings.
The existing five-element colors, card faces, fonts, and element assignments remain
unchanged. A relationship does not repaint a card as a transformed element.

The display switch above the chart shows characters, Ten Gods or hidden stems on
all eight cards together. Individual half-second holds still turn one card, and a
quick click or tap on a branch still toggles its hidden-stem panel; releasing a
long press does not also expand it. After such a change the switch's choice reads
mixed, and pressing it again shows it on every card.

## Recognition policy

Standard detects five stem-combination families, six branch-combination families,
six branch-clash families, and four complete three-harmony frames. Every occurrence
is preserved, including non-adjacent and repeated pairs. A frame requires all three
distinct members. Two members, even with repetitions, are not a complete frame.
Overlapping matches are shown independently, without declaring a winner.

Only visible stems participate in stem combinations. Punishments, harms, breaks,
directional combinations, incomplete frames, and temporal/luck pillars are outside
this first release. An empty list explicitly describes the supported scope.

Recognition is not an assertion of activation, transformation, strength, or life
outcomes. Potential elements are shown for stem combinations and complete frames,
with an explicit statement that transformation has not been assessed. Branch-pair
transformation targets are deliberately omitted rather than choosing silently
between conventions.

## Implementation and verification

`eight_characters/interactions.py` uses the first 21 definitions in the shared
Evolution family catalog, but not its nearest-pair selector, vitality weights,
partial-frame applicability, or inference. No Evolution rules are changed.
The function consumes normalized pillars and returns a deterministic list. The API
exposes it through the independent `include_interactions` flag.

The character-level reference in `tests/test_api_interactions.py` is independent
of the runtime catalog. It checks every pair orientation and pillar position,
complete-frame permutations, incomplete sets, duplicates, overlapping matches,
input immutability, and unchanged existing API payloads.

`static/relationships.js` lays out the arcs. Four levels hold every combination of
four stems or four branches; the same test module walks all of them with that
layout, and the page fails visibly if a chart ever needs more.
`tests/browser/arcs.test.mjs` checks where each arc starts and ends, its line, its
level against the arcs it spans or crosses, the feet behind opened hidden stems,
the selected arc, and that the cards keep their places with none to seven
relationships.

The reference families correspond to the chapters on ten-stem combinations,
six branch combinations, three-harmony combinations, and clashes in
[San Ming Tong Hui, volume 2](https://zh.wikisource.org/w/index.php?title=三命通會/卷二&oldid=2292392).
This is a source for traditional rule identities, not empirical validation of
predictions about people. Presence and transformation are separate in this UI.

See [API Reference](api.md) and [browser regression tests](../tests/browser/README.md).

## Day Master context

The Day Master's topics, in the same row as Relationships, open season, root, or
role evidence in the same panel. Selecting one clears the other selection and its
highlights; details never accumulate into stacked panels. See
[Day Master context](Standard-Day-Master-Context.md).
