# Roles in Standard mode

Roles replaces the former Support control beneath the Day Master summary. It
shows the whole natal chart: Companion, Output, Wealth, Authority, and Resource,
with both individual Ten Gods retained under each group. The season and Day
Master Roots controls continue to work as before.

## Reading the overview

Each group shows its element relative to the natal Day Master. Both the group
and each individual role report one of four states: Visible only, Hidden only,
Visible and hidden, or Not present. These are occurrence states, not power,
strength, percentages, favorability, or personality judgments. A group's presence
does not imply that both of its roles are present.

The Day Master itself is not an additional visible Companion. Other visible
stems with the identical character do remain separate Companion occurrences.
The Visible stems section includes all four positions, with the Day Master
explicitly identified as the reference, and provides root inspection for each.

Select any individual role, including an absent one, to inspect it. Visible and
hidden occurrences are listed separately. Hidden entries name their branch,
actual stem, and qi position. Selecting a role highlights only its occurrences:
visible cards and precise rows on both hidden-stem surfaces. It does not open
panels, flip cards, recolor elements, or move the pillars.

Absence means that the role does not appear in the natal visible or hidden stems
under this policy, excluding the Day Master itself. It does not establish an
absence of a quality or outcome in a person's life.

## Roots and exact hidden-to-visible matches

A visible stem's Roots control inspects all same-element hidden stems across
all four natal branches. The inspected visible stem has a dotted outline; root
branches and their exact hidden-stem rows have solid outlines. The detail names
each matching stem, distinguishing `exact_stem` from `opposite_polarity` and
retaining main, middle, or residual qi position.

An exact hidden-to-visible match requires the same stem character. An
opposite-polarity same-element root is not an exact match. Hidden occurrence
details link to every exactly matching visible position, preserving repetitions.
An exact match to the Day Master is labeled separately and does not change a
hidden-only Companion role into a visible role.

Ten Gods never recenter on the inspected stem: they remain relative to the natal
Day Master. Resource occurrences are not roots of the element they generate.
No roots detected is an evidence state, not a conclusion that the visible stem
is ineffective or has no other support.

Records have stable occurrence IDs within a chart. Root evidence and exact-match
links refer to the same underlying occurrences; they are not additive support
or extra quantities. A clash or combination does not delete or transform natal
evidence in this view.

## Navigation and design

Roles uses the existing below-chart detail surface, fonts, palette, and card
interactions. Role and root detail pages replace one another. Their back control
returns keyboard focus to the originating entry. Clear or Escape dismisses the
whole selection and returns focus to Roles. Selecting Month, Day Master Roots,
or a relationship clears Roles and its highlights. No panels are stacked.

Finnish and English labels, narrow layouts, reduced motion, and screen-reader
announcements are included. The UI validates the profile against the chart and
Ten Gods before display; missing, duplicated, or contradictory evidence is a
visible chart-creation error, not an invented empty state.

## API compatibility and verification

`include_role_profile: true` adds a separate `role_profile` section to
`POST /api/four_pillars`. Standard requests it automatically. The previous
`day_master_context` payload, including `support`, remains unchanged for API
clients. No other enrichment is implicitly enabled.

The policy is `natal_roles_v1`. It reuses the same root definition as
`natal_presence_v1`; the two views share the pure `natal_evidence.py` collector
and root matcher. Evolution inference is not involved.

See `tests/test_api_role_profile.py` for independent-reference coverage and
`tests/browser/roles.test.mjs` for the real-API browser suite. The role, context, and relationship suites share
`tests/browser/chart-helpers.mjs`. Suggestion fixtures carry coordinates and the
app sends them unchanged; chart requests are not rewritten. The location suite
also covers picking a place and opening the explorer. See
[API reference](api.md) and [browser setup](../tests/browser/README.md).
