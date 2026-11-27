# The first chart

The first chart is what a birth settles on its own: its pillars and its Day Master,
without an account, or without the birth time. It comes from `POST /api/first_chart`
(see [the API](api.md)). Every pillar, change and Day Master on it is the engine's own,
as on the whole chart. eightchord.com shows the same first chart to its visitors.

## Without the birth time

The form's **Time unknown**, under the time field, a choice that stays pressed, sets the
time field aside. Create chart then opens the first chart of the date and the place:
- the day, month and year pillars, each a stem card over its branch card, in the
  chart's order, with their characters and pinyin;
- the hour pillar left open: "Your birth time opens it";
- the luck pillars and the days, which need the time, are not there, and the page says
  so.

The engine reads a date without its time at noon, local time. A pillar that changes
during that day is marked "Changes during the day", and a line under the pillars says
when, on the place's clock and its offset from UTC, with both of its sides and the one
the cards show. February 4, 1988 in Chengdu has three: the day pillar at 01:17:31, and
the year and month at Lichun, 22:42:49, after the noon the cards are read at:

```
The Day pillar changes at 01:17:31 (UTC+08:00). Born before then: 戊子 Wu Zi; from then
on: 己丑 Ji Chou. The cards show 己丑 Ji Chou.
The Year pillar changes at 22:42:49 (UTC+08:00). Born before then: 丁卯 Ding Mao; from
then on: 戊辰 Wu Chen. The cards show 丁卯 Ding Mao.
The Month pillar changes at 22:42:49 (UTC+08:00). Born before then: 癸丑 Gui Chou; from
then on: 甲寅 Jia Yin. The cards show 癸丑 Gui Chou.
```

The day pillar changes at true solar midnight, so wherever the clock runs ahead of the
sun or behind it, it changes during the date. The month changes at a solar term, and
the year at Lichun. A link that names the whole Zi hour (`zi=whole_zi_23`) is read so,
as the whole chart reads it: the day changes at 23:00 true solar time, an hour earlier.

**The Day Master** is the day pillar's stem, named as the chart names it ("Day Master
· Ren — Yang Water"), and the canon's core passage for it reads in full. When the day
pillar changes during the date, a line says from when the Day Master shown holds, and
names the other side's.

Its address is the chart's own link with `time=unknown` (see
[Chart links](Standard-Links.md)). A link without the time names no display, luck
pillar, life grid, topic or pass of a repeated time: the first chart has none. It opens
no day and no comparison, and it saves no birth. Those links say that the day, or the
chart compared, needs the birth time, and the form keeps the birth. On the forms that
save a birth or ask for a comparison's second chart, the choice is not offered.

Edit finds the birth in the form, its time still unknown, and New chart an empty form.

## Without an account

Charts need an account. A visitor without one, who opens a chart's link or creates a
chart, sees its first chart instead:
- all four pillars, at the birth's own moment;
- the Day Master and its core passage, in full;
- the offer: "The whole chart opens with a free account: its relationships, roles,
  luck pillars and days.", and **Create my free account**.

The offer opens the account window, on making an account. Signed in, the address opens
the whole chart, with what the link names (its display, its topic), and the save window
([Settings](Standard-Settings.md#saved-charts-and-the-library)) offers to keep it as the
account's own, with **My own chart** chosen and the gender asked for when the link gave
none: kept, each visit opens its day. An account with a chart of its own, or for which
the chart is saved already, is offered nothing. Cancel keeps nothing. Closed without
signing in, the account window leaves the first chart as it was.

A visitor's link without the time (`time=unknown`, as eightchord.com links a visitor who
gave no birth time) opens the first chart of its date and place. Its offer says that the
whole chart opens with a free account and the birth time; signed in, the chart stays the
first chart until the time is added.

No whole chart is asked for without an account.

See [browser regression tests](../tests/browser/README.md): `first.test.mjs`.
