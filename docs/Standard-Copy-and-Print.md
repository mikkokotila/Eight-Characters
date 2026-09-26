# Copying and printing a chart in Standard mode

A chart can leave the page three ways: as its link (see [Chart links](Standard-Links.md)),
as text, and on paper. The text and the printout show what the screen shows: the
same pillars, the same true solar time, the same convention.

## Copy as text

Copy as text, in the bar above the chart and among the commands (⌘K or Ctrl+K),
puts two lines on the clipboard, for notes and messages:

```
丁卯 癸丑 己丑 壬申
February 4, 1988 · 16:30 · Chengdu · True solar time 15:12:24 · Day changes at midnight
```

- **The first line** is the chart's pillars, read from its cards, in the written
  order: year, month, day, hour. The chart itself lays them out Hour to Year.
- **The second line** is the birth as it was entered, its true solar time and the
  convention that set the day. When the true solar time falls on another day than
  the clock, it names that day too.

The convention is the Zi-hour one: the day changes at midnight (the engine's
default) or at 23:00. Outside the Zi hour both give the same chart, and the line
names the default. In the Zi hour it names the one the chart was read with, and
switching the convention changes both lines.

The lines follow the chart's language. A message over the foot of the page says
that the text was copied, or that the browser refused.

## Printing

The browser's own print (or Print among the commands) prints the chart:
- the chart's name and its precision line (true solar time and the clock offset);
- the Day Master, and any notices;
- the pillars, in the display on screen, in their element colours, with their arcs
  and any opened hidden stems;
- the open topic, below the chart at the page's width, whatever the screen's width.

The controls are left out: the display, view and language switches, the bar's
actions, the topics' buttons, and Close. The page's tone is left out too, so the
paper stays white. A Zi-hour chart prints the convention it was read with, as text.
A heading moves to the next page with what it heads.

Save as PDF in the print dialog gives the same pages.

See [browser regression tests](../tests/browser/README.md): `output.test.mjs`.
