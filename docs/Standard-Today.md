# The chart's day: Today in Standard mode

Today shows what a day, its month, its year and the luck pillar in force bring to the
chart on screen, and to its partner's when it is in a couple. The API reckons all of it
(`POST /api/today`, by [Today: the rules](Today.md)); the page draws its answer and
computes nothing: no pull, band, tie, call or pairing. The one thing the page reads
itself is the date, and the time, on the clock at where you are.

## Opening it

**Chart · Today**, in a chart's bar, opens the chart's day: today's date where you are.
The chart needs a gender, since the day reads its luck pillars. Today is not offered in
a comparison's frames, and the Evolution explorer, a page of its own, has none.

The day asks for what the account keeps in [Settings](Standard-Settings.md): where you
are, the schools and, when the chart on screen is a saved chart in a couple, the other
chart of the couple. Without a place, Today says so and leads to Settings; without a
gender, back to the chart.

## The page

From the top:

- **The bar:** the date, the chart and where you are; Chart · Today; the day before,
  Today (where you are) and the day after; whose day, when the chart is in a couple;
  With, the partner in view, when it is in several; FI · EN; Copy link; Copy as text;
  Print; Settings. Below 640px the actions show as their icons.
- **The days.** The chosen day in the middle, as the chart's cards: a stem card over
  its branch card, each in its own element's colours, its character with its pinyin,
  its lines (the stem's trigram, the branch's hexagram) and its name (the stem's
  polarity and element, the branch's animal); under them its weekday, date, band (word
  and mark) and score. Two days of the run on either side, one below 640px, smaller:
  they recede by size alone, never by opacity or blur, so their text keeps its contrast.
  They come from the answer's run, so moving asks for nothing more, and a date the
  place's clocks skipped is never drawn. The cards are pictures: they do not turn, hold
  or take keys.
- **The run:** 22 days, 7 back and 14 ahead, as a strip of bars around a zero line, up
  for a positive pull and down for a negative one, their length on the pull's scale.
  Each day is a button named by its date, pillar and pull; the chosen day is marked,
  and today has a dot. Choosing a day shows it.
- **The pull line:** the day's band and score, with the topics beside it: the day's
  page, Marriage (in a couple), Work and Health, each in the panel.
- **The scale:** the day's pull on a scale from −3.5 to +3.5, the same for every day
  and every layer (the rules' largest pull is 3.28, and a test holds every pull inside
  the scale). Zero is in the middle, the band edges ±0.5 and ±1.5 are marked, and the
  marker stands at the API's score. Its ends are named in words, from the chart being
  read: "+ Useful: Wood", "− Unfavourable: Metal". The halves take those elements'
  colours, but colour says nothing the words, numbers and the band's mark do not: the
  scale's outline, ticks and marker are ink, and it reads in greyscale. Under it, the
  five gods, each with its element. An answer with a pull past the scale's ends is
  refused as malformed, never drawn clipped.
- **The four pillars:** the day, the month, the year and the luck pillar, at noon where
  you are (the page says so), each as small cards with the Ten God of its stem, its
  pull and its place on the scale. The luck pillar gives its decade and phase, or says
  there is none on the day; by phase, its stem rests in the branch phase, drawn as the
  chart draws a phase not in force. Each pillar opens its own page.
- **The couple,** when the chart on screen is in one: the day's pillar once (both are
  read on the same day at the same place), each side's pull by mark, word and score,
  both on one neutral scale (each chart's elements are its own), and whether the day
  pulls them apart, as the API says. The chart read comes first, so the sides turn
  around under the partner's day.
- **In your chart:** the relationships the four form with the chart, each with the
  canon's line in English, and the pillars it joins: the day's own for its member of
  this day, month, year or luck pillar, and the chart's own for its members in the
  chart (the partner's under the partner's day), each named, the member outlined on its
  card. A relationship of three members draws all three.
- **The hours:** a dial of the twelve double hours, by branch, Zi at the top and
  clockwise: true solar hours, so the dial has no clock times. Each wedge is in its
  branch's element colours, with the branch and its pinyin and its call's mark. On
  today, the hour the clock is in is outlined and named. Beside it the table, which
  says it all for screen readers and print: each hour on the clock at where you are,
  the Zi hour with its two spans, its ties to the day and its call, Protect, Mixed or
  Avoid, by word and by mark, and the hour now named "now", its row the current time.
  An hour with no tie has no call. The hour now, today's dot in the run and the bar's
  Today follow the clock while the page is open: past an hour's end or midnight, they
  change within half a minute, and at once when the page is seen again.

The day's page gives, for each of the four pillars, the parts of its pull (each
character, its element, its weight, how much it counts and its value) and the canon's
readings, as the decade page reads a luck pillar. A pillar's own page, opened from its
card, gives the same for that pillar alone. Health says it reads the day's elements,
not the body: it is not health advice.

## Moving through the days

Every way of moving goes to the run's next or previous day, in date order, so a date
the place's clocks skipped is passed over (Apia, 30 December 2011): `[` and `]` from
anywhere, the bar's steps, Left and Right while the days have focus (Home and End go to
the run's first and last day), a press on a neighbour, a pick in the run, and a swipe or
drag on the days. A step past the run's end counts the run's days to that end, then
calendar days. With no run drawn (a day the API refused), a step is a calendar day. A
day the API refuses, near the first and last of the engine's years, shows its reason.

A move draws the days at once from the run, and the date in the bar; the rest of the
page is dimmed until the day's own answer is drawn. Keys, presses and picks ask at
once; a drag asks once, when it is let go. Only the answer to the latest request is
drawn. The run drawn leads only its own reading: while another chart, language or
person is on its way, or Today is opened again (its settings may have changed), the
days wait for that answer, and a step until then is a calendar day.

A drag follows the pointer that started it, once it has gone 40px across (more than a
touch hold's 10px), and never from the screen's left edge, which is iOS's Back. Let go,
the day moves by as many days as it went, one at least; let go less than 40px from where
it started, even after going further, it moves nothing. Up and down stays the page's
scrolling. A press that went more than 10px, up and down or off the days and back
included, is no press: the click that ends it opens nothing. A cancel, a lost capture,
the run going while it is dragged (another reading shown, or the day refused), or
another day shown meanwhile (by a key) moves nothing, even when the next reading is
drawn before it is let go. Another pointer pressed with it, of any kind (a touch during
a mouse's drag too), spoils the press: nothing moves, and no click opens a day until a
press starts alone. A mouse let go off the days before its drag began leaves the next
drag as it would be. A step slides the days in 280ms; a pick far away slides one step's
distance, never through the days between. With reduced motion, the days change in place.

## A partner's day

When the chart on screen is a saved chart in a couple, the bar names its partner in
view beside This chart. A chart can be in several couples: then **With** chooses the
partner in view among its partners, in the order the couples were formed, an unnamed
one by its birth and one that no longer charts shown but not chosen. Without a partner
in the address, the first couple's partner is in view, and the page writes it into the
address. Choosing another replaces the address, keeps whose day and the open topic, and
on the partner's side turns to the chosen partner's side.

The partner's day turns the whole page to the partner's chart, counted at where you
are, and the page says so. Opening a partner's chart opens its own Today, which reads
its own first couple unless its address names one. Marriage, the couple, In your chart,
Copy as text and Print read the couple in view: each pull, whether the day pulls you
apart, the day at the spouse palace, and the day's relationships with the other chart.
A chart that is not saved, or not in a couple, has no partner side.

A chart the address names that is not one of this chart's partners in your account (one
unpaired, removed, from another account, or this chart itself) is never swapped for
another partner: this chart's own day is read without a couple, and the page says why,
with With offering its partners; on the partner's side the page says so and offers
This chart, which goes back to this chart's own day with its first partner in view. If
the partner's chart no longer charts, the page says so in the same way. A late answer
for another partner is never drawn, copied or printed: the partner is part of what the
day is read for.

## Its address

`#today?` with the chart's own link parts, as `#chart?` has them (see
[Chart links](Standard-Links.md)), then:
- `day`, the day shown, `YYYY-MM-DD`;
- `who=partner` for the partner's day;
- `partner`, the partner in view: a saved chart's id in your account (see above);
- `topic`: `day`, `marriage`, `work`, `health`, or `pillar/day`, `pillar/month`,
  `pillar/year`, `pillar/luck`.

A link names the chart and the day. The couple and where you are come from the
account that opens it, and a link opened signed out asks for a sign-in first. A link
with an unknown, repeated or invalid part says so, naming the part, as a chart link
does. A day the API cannot read (outside the engine's years, with the run's days) is
shown with the API's reason, and nothing of the day before, nor its open topic, stays on
screen; Try again asks again. While a day is on its way, the day before and its topic
are dimmed.

A day step, Today, the partner switch and the language replace the address; a topic,
and Chart · Today, add to the history. The chart, from Today's bar or its commands,
opens in the language the day is shown in. A link opened signed out asks for a sign-in,
and the day is then shown in the account's language, which its address then names; a
session that ends while the day is open asks for a sign-in when the day is next asked
for. A sign-out leaves nothing of the account's day on the page: neither where you are,
nor a partner's name, nor the days, the scale or the couple. Another account, signed in
to in another tab and taken here, has the day read again with its settings, and nothing
of the day read with the account before stays, shown or hidden. Marriage, open when the
couple ends elsewhere (or the partner's chart no longer charts), closes, and the page
says why.

## Keys and commands

While the page has focus and no field does: `[` and `]` the day before and after, N
today where you are, Escape closes a topic, ? lists the day's keys. The days are one
tab stop: while they have focus, Left and Right step and Home and End go to the run's
ends; elsewhere the arrows keep their own meaning. A held key steps once. A topic, a
day of the run or an action chosen from the keyboard keeps the focus on its button once
the day is drawn again, and the days keep theirs; Today, which is then unavailable,
hands it to the day's heading. Chart · Today hands the focus across: to Today on the day's bar,
or to Chart on the chart's, so each page's keys act at once. Brackets are typed with
Alt or AltGr on many keyboards. The commands (⌘K or Ctrl+K) hold the steps, the
partner's day, the topics, the chart, Copy link, Copy as text and Print (once the day
is drawn) and Settings.

## In Finnish

The canon's readings are in English only: a Finnish day has none, and the day's page
shows the pulls' parts. The owner confirmed the Finnish names on 2026-10-11; the new
Today's words (the five gods, the days' name, "Keskipäivällä", "nyt", "Pari") are
provisional until confirmed. Numbers are written the Finnish way.

## Copy and print

Copy as text gives the date, the chart and where you are, the schools, the day's pull
line, the five gods with their elements, the four pillars with their pulls, in a couple
the other side's pull and whether the day pulls you apart, the run as dates and pulls,
and the hours with their calls. Printing gives the page without its controls: the
chosen day's cards (not its neighbours, nor any motion), the scale with its words, the
four pillars, the couple, In your chart, the hours' table (not the dial), and the run
as a list, each day with its band as a word; the cards and the scale keep their
colours. Until a day's own answer is drawn, Copy as text and Print say they are
unavailable, so neither gives one day's numbers under another's date; printed anyway
(from the browser), the page gives the bar and says the day is still being read. An
answer the page cannot draw is neither copied nor printed: the page says why instead.

See [browser regression tests](../tests/browser/README.md): `today.test.mjs`.
