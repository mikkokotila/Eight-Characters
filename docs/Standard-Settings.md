# Settings: what the account keeps

Settings keep the account's saved charts, which of them is your own, the couples they
form, where you are, and the schools [Today](Standard-Today.md) follows. Everything
Settings show comes from the API (`GET /api/account/settings`, `GET /api/schools`).

## Opening them

**Settings**, in the account menu, in Today's bar and among the commands, opens
`#settings`. Signed out, it asks for a sign-in first. Close goes back to the page they
were opened from. Settings are not offered in a comparison's frames. Each opening reads
the settings anew, and only the latest one draws them or says why it could not.

## Saved charts and the library

A chart link holds a birth, never an id, so a link means the same chart to anyone. The
chart on screen is a saved chart when its birth is one: the same day, time, pass of an
hour the clocks repeat, place on the globe, gender and Zi-hour convention (the API saves
a birth once). The Zi switch, another gender or another pass make another chart.

A chart's heading has a button that names it: its saved name, or that it is unsaved.
It opens **the library**: the saved charts, each with its birth and four pillars (each
character in its element's colours, with its pinyin), Your chart marked in words, and
each chart's partner named. Choosing one opens it; the chart on screen is marked.
**Save the chart on screen** asks for a name (optional: one line, at most 80 characters)
and keeps the chart as it is on screen: its date, time and place, its pass, its gender
and its Zi-hour convention. A chart needs a gender to be saved, since the day reads its
luck pillars; without one, the library says so. An account keeps at most 50 charts
(`chart_limit` in the settings): with as many saved, the library says so, in the page's
language, and asks the API nothing. A second press of Save while the chart is being
saved saves nothing more. Someone else's chart is their data:
save it only with their consent. The library is also among the commands. It is not in
a comparison's frames.

Settings have three parts for them:
- **Your chart**: the chart marked as yours, with Open and Unmark; a choice from the
  saved charts to mark; and **Add a new birth**, saved as yours. Signed in, the site's
  bare address opens your chart (see below).
- **Couples**: each couple, with both charts' pillars, and End the couple, which ends
  that couple alone and keeps both charts. A chart can be in several couples, each with
  its own card, in the order paired; pairing a chart that is in a couple already comes
  with #96, so for now two saved charts not in a couple can be paired, and **Add the
  partner as a new birth** saves one and pairs it with the chosen chart in one write.
  A partner's chart kept from before accounts kept charts is listed as waiting, and
  pairs with your chart once you mark one; marking it, or saving a new birth as yours,
  then says with whom it paired.
- **Saved charts**: each with Open, Rename, Correct the birth and Remove. Rename starts
  from the name as it is, quotes and all. Remove asks once more on its own button,
  saying what else ends: the chart's being yours, each of its couples (naming the other
  charts), or its wait to pair with your chart. Each saved chart names its partners in
  the order paired, an unnamed one by its birth date, and past three says how many
  more ("Couple with A, B, C, and 2 more"). A chart the engine no longer charts says
  why, and can still be renamed or removed.

**Add a new birth**, **Add the partner as a new birth** and **Correct the birth** open
the birth form at `#save?as=mine`, `#save?as=partner&with=<id>` or
`#save?as=correct&chart=<id>`. The form says what it saves, asks for a name, needs a
gender, and checks the birth as it checks a chart's; a birth saved already is said so,
by the chart's name, and not asked for again. Save keeps it and goes back to Settings,
and Cancel goes back without saving. A correction keeps the chart's Zi-hour
convention, and its pass while its day, time and zone are unchanged. With the library
full, Add a new birth and Add the partner as a new birth say so instead.

## Signing in to your chart

Signed in, a visit to the site's bare address opens your chart, replacing the address,
so Back does not come there again; with none marked, the form. Signing in from the
account button on the empty form does the same. Every other address keeps its
destination: a chart link, Today, a comparison, Settings, and a chart asked for from
the form before signing in. New chart and Edit still open the form.

## Where you are

A place search of its own, as the birth form's: choose a place from the list and save
it. The hours of a day are reckoned for it. Remove forgets it. Nothing is guessed from
the browser. A place picked while the one before is being saved stays in the search,
to be saved in turn. Saved or removed from the keyboard, the place leaves the focus in
the search.

## The schools

The three settings, as the API lists them, each a group of presets with its summary and
sources; the default is marked in words. A choice applies at once. Choosing the default
follows it again, so a later change of default applies too.

## Changes

Every change carries the account's key and the settings it was made from. Changes are
made one at a time, in the order they were made, each from the settings the one before
it left, so presets passed one after another (arrowing through a school's) are all
kept, the last deciding. A change made from settings another tab or browser has changed
since is refused, and so are the changes made after it from the same settings: the page
shows the settings as they are now, to be chosen again. A session that ended asks for a
sign-in, and the change is not repeated. A change pressed again while it is on its way
(Pair, End the couple, Remove, marking or unmarking your chart) is asked for once.
Another account signed in in this browser, and a change the API refuses, are each said
on the page. Another account, signed in to in another tab and taken here, leaves
nothing of the one before: the library and the save dialog close, a birth being added
or corrected is let go (the form follows its address again, for the account taken),
and Settings, Today and the chart's name are read and drawn again for it. Focus stays on the preset, choice or
action that had it, or, once that is gone, on the first control of its part. A sign-out leaves
nothing of the account on the page, and until the settings are read again nothing can be
changed.

See [browser regression tests](../tests/browser/README.md): `settings.test.mjs`.
