# Comparing two charts in Standard mode

Two charts can stand side by side, each as it stands on its own.

## Starting a comparison

Compare, in a chart's bar and among the commands (⌘K or Ctrl+K), asks for the
second birth. The form says which chart it will be compared with, and starts
empty. Compare, at its foot, opens the pair. Cancel goes back to the first chart.

## The two charts

Each chart is the chart view itself, in a frame of its own:
- its name and true solar time;
- the display switch and Copy as text;
- the topics, which open in its own panel, a sheet over the foot of its frame;
- the pillars, their arcs and hidden stems, and the pointing from its panel.

Each scrolls on its own. The two charts have nothing drawn between them: the
relationships are each chart's own.

The comparison's bar holds what belongs to the pair:
- the language: both charts are asked for again in it;
- Swap sides: each chart keeps what is open in it;
- Copy link: the pair's address;
- Close: back to the first chart.

Narrower than 900px, one chart shows at a time, with a switch between them.

## Its address

The pair has an address of its own: `#compare?a=…&b=…`, where each part is a chart
link's parameters (see [Chart links](Standard-Links.md)). With `a` alone, the form
asks for the second chart.
- The address follows what is open in either chart, so the pair's link reopens both
  as they were.
- Back steps from the pair to its form, then to the first chart. What is done within
  a chart adds nothing to the history.
- A comparison link that names no pair says why, naming the part, as a chart link
  does.

See [browser regression tests](../tests/browser/README.md): `compare.test.mjs`.
