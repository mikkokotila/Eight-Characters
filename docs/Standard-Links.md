# Chart links in Standard mode

The address of a chart names the chart on screen, its open topic and its display.
Reloading the page, opening the address in another tab or browser, or sending it
to someone shows the same chart, open at the same place.

## What the address holds

The chart lives in the address's fragment, the part after `#`:

```
/#chart?date=1988-02-04&time=16%3A30&place=Chengdu%2C+Sichuan%2C+China&city=Chengdu&latitude=30.658&longitude=104.066&timezone=Asia%2FShanghai&lang=en
```

- `date`, `time`: the birth as entered, on the place's local clock.
- `place`, `city`: the picked place's full name, shown in the form, and its short
  name, shown in the chart's heading.
- `latitude`, `longitude`, `timezone`: the picked place itself. The chart is
  calculated for these, since place names repeat.
- `lang`: the chart's language, `fi` or `en`.
- `zi`, only when it is not the engine's default: the Zi-hour convention,
  `whole_zi_23`.
- `display`, only when it is not Characters: `ten-gods` or `hidden-stems`.
- `topic`, only when one is open: `season`, `roots`, `roles`, `roles/<role>`,
  `roles/stem/<pillar>`, `roles/<role>/stem/<pillar>` (a stem's roots reached
  from a role's page), `relationships`, `relationships/<id>` (the API's
  relationship id), or `pillar/<pillar>` (a pillar's exact changes).

Browsers never send the fragment to the server, so a birth in a link stays out of
server logs. The chart itself is still calculated by the API, which receives the
birth in the body of its request, as it does when the form is used.

## History

- Creating a chart, opening another topic, Edit and New chart each add a history
  entry, and Back and Forward step through them. Back from a chart returns to the
  form, with the chart's birth in it.
- The language, the Zi-hour convention and the display replace the current entry.
- A chart reached through Back or Forward is calculated again when another chart
  is on screen. Only the chart of the latest step is drawn: one that arrives after
  a later step is dropped.

## Links that open no chart

A link that names no chart, whose part is missing or not valid, or whose topic
this chart does not have, does not open a chart. The form says why, naming the
part, and the address becomes the form's. When the link's birth is valid, it
waits in the form.

## Copy link

Copy link, in the bar above the chart, copies the address. A message over the foot
of the page says that it was copied, or that the browser refused.

See [browser regression tests](../tests/browser/README.md): `links.test.mjs`.
