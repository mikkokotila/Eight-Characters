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
- A hint above the card with keyboard focus says its keys: "T: Ten Gods", and on a
  branch "Enter: hidden stems · T: Ten Gods".
- Escape closes the open topic, as it does anywhere on the chart.

A branch card is a button that opens its hidden stems (`aria-expanded`); a stem card
is a group. Each is named by its pillar and the side it shows, such as "Year 丁 Yin
Fire", or "Year Indirect Resource" once turned. The pillars are a group named Pillars,
described by the keys above.

## ? and the commands

- ? lists the keys, in a dialog, while focus is on the chart. A character key acts only
  while its part of the page has focus (WCAG 2.1.4), so elsewhere ? is only a
  character.
- ⌘K or Ctrl+K opens the commands wherever focus is, while a chart is shown. Typing
  narrows them, every word counting; arrows choose, Enter or a click runs the chosen
  one. The commands are:
  - the topics, each relationship, each role's page and each pillar's changes, which
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
