# Settings and the saved charts: what the account keeps

The account keeps its saved charts, which of them is your own, the couples they form,
where you are, and the schools [Today](Standard-Today.md) follows. They are two pages
of one view:
- **Saved charts**, at `#charts`: your chart, the couples and the saved charts, the
  people a visit is about;
- **Settings**, at `#settings`: where you are, the schools and the toolbar, chosen once
  and changed seldom.

Everything both show comes from the API (`GET /api/account/settings`,
`GET /api/schools`), but for the toolbar, which this browser keeps.

## Opening them

**Saved charts**, in the account's window, and **Manage saved charts**, in the library,
open `#charts`. **Settings**, in the account's window and among the commands, opens
`#settings`. Signed out, either asks for a sign-in
first. The page's title names it, and its Close goes back to the page the first of them
was opened from; Account, beside it, opens the account's window. Neither is offered in a
comparison's frames. Each opening reads the settings anew, and only the latest one draws
them or says why it could not.

## Saved charts and the library

A chart link holds a birth, never an id, so a link means the same chart to anyone. The
chart on screen is a saved chart when its birth is one: the same day, time, pass of an
hour the clocks repeat, place on the globe, gender and Zi-hour convention (the API saves
a birth once). The Zi switch, another gender or another pass make another chart.

A chart's heading has a button that names it: its saved name, or that it is unsaved.
It opens **the library**: the saved charts, each with its birth and four pillars (each
character in its element's colours, with its pinyin), Your chart marked in words, and
each chart's partner named. Choosing one opens it; the chart on screen is marked. The
day's heading has the same button, for the chart whose day it shows: a chart chosen
there opens its day, on the date shown, and the day offers no save. The start page and
a comparison's second chart list the saved charts in the same way (see Coming back and
[Compare](Standard-Compare.md)).
**Save the chart on screen** opens a window that looks as every window does (its title,
and Close, which saves nothing), with Save its one action. It asks for a name (optional: one line, at most 80 characters)
and keeps the chart as it is on screen: its date, time and place, its pass, its gender
and its Zi-hour convention. A saved chart needs a gender, since the day reads its luck
pillars: a chart without one is given it in the same window (Female or Male, none chosen
for you; saved without one, the window says so and nothing is saved). The chart saved,
and the chart on screen, take it: the chart's link names it, and the chart is drawn with
its luck pillars. Given a gender, the birth may be a chart saved already: the window says
which, and the API is not asked. **My own chart** saves it as yours, so each visit opens
its day; once chosen it says so, and that a chart marked as yours before stays saved, no
longer yours. An account keeps at most 50 charts
(`chart_limit` in the settings): with as many saved, the library says so, in the page's
language, and asks the API nothing. A second press of Save while the chart is being
saved saves nothing more. Someone else's chart is their data:
save it only with their consent. The library is also among the commands. It is not in
a comparison's frames.

The saved charts' page is one list, as the library's: your chart first, then the
others in the order saved, each opening its chart when chosen. **Add your own birth**,
above it, saves a new birth as yours. With charts saved and none yours, the page asks
which one is. Under each chart are its couples, each on a line of its own in the order
paired ("Couple with A", an unnamed partner by its birth date, however long the name),
with **End the couple**, which ends that couple alone and keeps both charts. Then its
buttons:
- **Mark as yours**, or **Unmark** on yours. Signed in, each visit to the site's bare
  address opens your chart's day (see below).
- **Pair with…** opens, under the chart, the charts it can pair with (never itself or
  one of its partners), and **A new birth**, which saves one and pairs it with this
  chart in one write, even for a chart paired with every other. Cancel, or Pair with…
  again, closes them. A chart can be in any number of couples. With no pair left to
  form, the page says so.
- **Rename**, **Correct the birth** and **Remove**. Rename starts from the name as it
  is, quotes and all. Remove asks once more on its own button, saying what else ends:
  the chart's being yours, each of its couples (naming the other charts), or its wait
  to pair with your chart.

On a plan that caps how many couples a chart may be in (none does for now), a chart at
the cap has no Pair with… and is offered to none, and the page says why. A partner's
chart kept from before accounts kept charts is marked as waiting to pair, and pairs
with your chart once you mark one; marking it, or saving a new birth as yours, then
says with whom it paired, or, with your chart at its plan's cap, that it did not and
waits no longer. A chart the engine no longer charts says why, and can still be renamed
or removed.

**Add your own birth**, **A new birth** (under Pair with…) and **Correct the birth** open
the birth form at `#save?as=mine`, `#save?as=partner&with=<id>` or
`#save?as=correct&chart=<id>`. The form says what it saves, asks for a name, needs a
gender (it leaves "Not given" out and chooses none for you), and checks the birth as it
checks a chart's; a birth saved already is said so,
by the chart's name, and not asked for again. Save keeps it and goes back to the saved
charts' page, and Cancel goes back without saving. **Edit** on a saved chart, in the chart's Actions,
opens the same correction at `#save?as=correct&chart=<id>&back=chart`: Save and Cancel
then go back to the chart, corrected or as it was. A correction keeps the chart's Zi-hour
convention, and its pass while its day, time and zone are unchanged. With the library
full, Add your own birth and A new birth say so instead.

## Coming back

Signed in, a visit to the site's bare address opens your chart's day, today where you
are ([Today](Standard-Today.md)): what each visit is for. The address is replaced, so
Back does not come there again. Signing in from the account button on the empty form
does the same.

With no chart marked as yours, the start page begins with the saved charts, as the
library lists them: each opens its chart, and Back comes to the start page again. Each
has **Mark as yours** under it, which marks it and opens its day, as each visit then
will; pressed again while the mark is on its way, it is asked for once. A mark refused
(the settings changed elsewhere, say) is said, and the list is drawn as the settings
are now. The list is in the page's language, as it changes. The form follows, under
**New chart**. With nothing saved, the start page is the form alone; the list is no
reason to ask for a sign-in.

Every other address keeps its destination: a chart link, Today, a comparison, Settings,
and a chart asked for from the form before signing in. New chart, and Edit on a chart
not saved, open the form alone.

## Where you are

A place search of its own, as the birth form's: choose a place from the list and save
it. The hours of a day are reckoned for it. Today asks for it with the same search while
none is set, and keeps the place chosen there. Remove forgets it. Nothing is guessed from
the browser. A place picked while the one before is being saved stays in the search,
to be saved in turn. Saved or removed from the keyboard, the place leaves the focus in
the search.

## The schools

The three settings, as the API lists them, each a group of presets with its summary and
sources; the default is marked in words. A choice applies at once. Choosing the default
follows it again, so a later change of default applies too.

## The toolbar

Words (the default) or Icons: how the bar above a chart and a day shows its switches
and actions (see [The toolbar](Standard-Toolbar.md)). The choice applies at once, and
this browser keeps it, not the account: another browser keeps its own.

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
