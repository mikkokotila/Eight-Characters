# Relationships in Standard mode

The strip above the pillars lists detected natal relationships. Select an entry
to outline its participating cards. Select it again, press Escape, or use Clear
to remove the selection. The controls work with a pointer, touch, or keyboard.

Details appear below the chart, leaving the pillars in place. They identify the
stems or branches, their natal elements, and the relevant Ten Gods. Branch details
show every hidden stem's role and qi type. Detail columns follow the chart's display
order; the API retains chronological pillar order.

Solid marks identify combination pairs, dashed marks identify clashes, and double
marks identify complete three-harmony frames. These are line styles, not ratings.
The existing five-element colors, card faces, fonts, and element assignments remain
unchanged. A relationship does not repaint a card as a transformed element.

Show Ten Gods turns all eight cards over together. Hide Ten Gods returns them.
Individual one-second holds still work, and the toggle reflects a mixed state when
only some cards are turned. A quick click or tap on a branch still toggles its
hidden-stem panel; releasing a long press does not also expand it.

## Recognition policy

Standard detects five stem-combination families, six branch-combination families,
six branch-clash families, and four complete three-harmony frames. Every occurrence
is preserved, including non-adjacent and repeated pairs. A frame requires all three
distinct members. Two members, even with repetitions, are not a complete frame.
Overlapping matches are shown independently, without declaring a winner.

Only visible stems participate in stem combinations. Punishments, harms, breaks,
directional combinations, incomplete frames, and temporal/luck pillars are outside
this first release. An empty strip explicitly describes the supported scope.

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

The reference families correspond to the chapters on ten-stem combinations,
six branch combinations, three-harmony combinations, and clashes in
[San Ming Tong Hui, volume 2](https://zh.wikisource.org/w/index.php?title=三命通會/卷二&oldid=2292392).
This is a source for traditional rule identities, not empirical validation of
predictions about people. Presence and transformation are separate in this UI.

See [API Reference](api.md) and [browser regression tests](../tests/browser/README.md).

## Day Master context

The summary above Relationships opens season, root, or role evidence in the
same below-chart detail area. Selecting one clears the other selection and its
highlights; details never accumulate into stacked panels. See
[Day Master context](Standard-Day-Master-Context.md).
