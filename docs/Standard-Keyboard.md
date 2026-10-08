# The chart by keyboard in Standard mode

Everything on a chart can be done from the keyboard. The bar's controls, the topics
and the pillars' names are buttons, reached with Tab and pressed with Enter or Space.
The eight cards take a single tab stop between them, and keys of their own.

## The cards

- Tab reaches the cards at one stop: the card used last, or the hour stem on a new
  chart. Tab again leaves them, and coming back finds the same card.
- Left and Right arrows move along the pillars, Hour to Year; Up and Down move between
  a pillar's stem and branch. The arrows stop at the edges, and do not scroll the page.
- Enter or Space opens and closes a branch's hidden stems, as a click does. On a stem
  they do nothing.
- T turns the card with focus to its Ten Gods and back, as a long press does. Held
  down, it turns the card once.
- R, in an English chart, reads the card with focus. It opens the card's pillar with
  the card's own reading open: who stands on a stem, or the ground of a branch. While
  a pillar's page is open, the arrow keys turn it too. The focused card's pillar opens
  at its line, and the readings that are open stay open. See
  [Readings](Standard-Readings.md). A Finnish chart has no readings, and no R.
- A hint above the card with keyboard focus says its keys. In an English chart that
  is "R: read · T: Ten Gods", and on a branch "Enter: hidden stems · R: read · T: Ten
  Gods". In Finnish it is "T: kymmenen jumalaa", and on a branch "Enter: piilorungot ·
  T: kymmenen jumalaa".
- Escape closes the open topic, as it does anywhere on the chart.

A branch card is a button that opens its hidden stems (`aria-expanded`); a stem card
is a group. Each is named by its pillar and the side it shows, such as "Year 丁 Yin
Fire", or "Year Indirect Resource" once turned. The pillars are a group named Pillars,
described by the keys above.

## The luck pillars

In a chart with a gender, while the chart has focus:
- L shows and hides the luck pillar, the chart's fifth;
- [ and ] step it a phase back or forward, { and } a decade;
- N chooses today's phase and opens its page.

The ribbon's chips take a single tab stop: the chosen decade's chip while the luck
pillar shows, else today's. Left and Right arrows move between them, and Home and End
go to the first and the last; moving opens nothing. Enter or Space opens the decade,
and Escape closes it, giving focus back to its chip. The steps and Today are buttons
of their own.

While the luck pillar shows, its cards follow the Year's in the cards' arrows, and Enter,
Space and T work on them as on the natal cards. R on them opens the decade's page.
Hidden, they take no focus. See [Luck pillars](Standard-Luck-Pillars.md).

## ? and the commands

- ? lists the keys, in a dialog, while focus is on the chart. A character key acts only
  while its part of the page has focus (WCAG 2.1.4), so elsewhere ? is only a
  character.
- ⌘K or Ctrl+K opens the commands wherever focus is, while a chart is shown. Typing
  narrows them, every word counting; arrows choose, Enter or a click runs the chosen
  one. The commands are:
  - the topics, each relationship, each role's page and each pillar's changes, and in
    a chart with a gender the years before the luck pillars and each decade, which
    open as a link opens them, in one step of the history;
  - the display, the other language and the Evolution view;
  - Copy link, Copy as text, Edit, New chart, Compare, Print, Close (when a topic is
    open) and Keys.

  In a comparison, each chart's commands are its own: its topics, its display, Copy
  as text and Print; the comparison's bar holds the rest.
- Escape in a dialog closes the dialog only; an open topic stays open. Focus returns to
  where it was.

## The panel

A control in the panel with keyboard focus rings on the chart what it names, at once:
a role where it occurs, a stem's roots, a relationship's cards and arc. The ring goes
when focus moves on.

In Safari, Tab moves between text fields and the cards only unless Full Keyboard Access
is on; Option+Tab reaches every control.

See [browser regression tests](../tests/browser/README.md): `keyboard.test.mjs`.
