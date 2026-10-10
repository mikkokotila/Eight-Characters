# Today: the rules

Today shows what a day, its month, its year and the luck pillar in force bring to a
chart, and to a partner's. The API computes all of it (`GET /api/today`,
`POST /api/today`); the page shows what it is given. This page is the rule book: every
number Today shows follows from it, and the tests hold the code to it.

Today adds something the rest of the app does not do. The chart's readings quote the
canon and weigh nothing. Today weighs: each element gets a weight from the chart's
favourable elements, and each pillar a pull. Those weights are the school's judgement,
computed by the rules below, and Today keeps them apart from the canon's words, which
it quotes as the decade page does. Nothing here predicts.

## The schools

Three settings choose the rules. Each is a school, named for the classics it comes
from, with one default; a person picks a preset and never a number. `GET /api/schools`
lists them in Finnish and English, with their sources.

| Setting | Presets (default first) |
| --- | --- |
| Favourable elements | Support and restrain (扶抑 Fu Yi); Climate (调候 Tiao Hou) |
| Earth's season | Earth's 18 days (土王 Tu Wang); Earth months; Late summer only; The month's commander (人元司令 Ren Yuan Si Ling) |
| The year and the luck pillar | By phase; Ten years as one; As the day |

Structure (格局 Ge Ju), from Zi Ping Zhen Quan, is not offered: it is not listed, and
asking for it is refused, until it can be computed in full.

An account keeps the schools it chose. One it never chose follows the default, and
follows a later change of the default too.

The classics give the principles. The numbers below are this app's own conventions,
and are marked so: the classics fix none.

## Counting a chart

Each stem counts 1.0. A branch counts through its hidden stems only, in the order
`eight_characters/resources/mappings/hidden-stems.csv` lists them: the first, its main
qi, 1.0; the second 0.4; the third 0.2. 子 Zi holds 癸 Gui alone, at 1.0; 午 Wu holds
丁 Ding at 1.0 and 己 Ji at 0.4. *(The app's convention.)*

## Each element's standing in the season

At any moment one element rules the season, and every element stands in it as the
five standings (旺相休囚死) say: the ruler prospers, what it generates is supported,
what generates it rests, what controls it is imprisoned, and what it controls is dead.
Each standing scales how much an element counts. *(The multipliers are the app's
convention.)*

| Standing | | Counts |
| --- | --- | --- |
| Prosperous | 旺 Wang | 1.2 |
| Supported | 相 Xiang | 1.0 |
| Resting | 休 Xiu | 0.6 |
| Imprisoned | 囚 Qiu | 0.4 |
| Dead | 死 Si | 0.2 |

### Earth's season: which element rules

The sun's longitude is the engine's apparent geocentric longitude. The month is the
solar month, from one jie to the next, as the month pillar's.

- **Earth's 18 days** (the default). Earth rules the 18 degrees of the sun's path
  before each season starts: while the longitude, modulo 90°, is in [27°, 45°).
  Otherwise the season's own element rules: Wood from 315° to 27°, Fire from 45° to
  117°, Metal from 135° to 207°, Water from 225° to 297°. Each element rules 72°.
  Sources: Bai Hu Tong (土王四季，各十八日); Su Wen, chapter 29; Xie Ji Bian Fang
  Shu; San Ming Tong Hui, juan 2. The canon's own Background gives Earth "the last
  eighteen days of each season".
- **Earth months.** Earth rules the 辰 Chen, 未 Wei, 戌 Xu and 丑 Chou months, whole;
  the other months their season's element. Source: Huainanzi, Tian Wen Xun
  (戊己四季，土也).
- **Late summer only.** Earth rules the 未 Wei month; 辰 Chen is Wood's, 戌 Xu
  Metal's and 丑 Chou Water's. Sources: Huainanzi, Shi Ze Xun, which sets Earth at
  the centre of late summer; Wu Xing Da Yi (六月則土王).
- **The month's commander.** What commands the month rules, by the days since the
  month's jie, each day 86,400 seconds from the jie's instant. The last commander holds
  to the next jie, however long the month. The table is San Ming Tong Hui's, juan 2,
  論人元司事: "如正月建寅，寅中有艮土用事五日，丙火長生五日，甲木二十日…"

  | Month | Commanders, in order, with their days |
  | --- | --- |
  | 寅 Yin | 艮土 Gen Earth 5, 丙火 Bing Fire 5, 甲木 Jia Wood to the end |
  | 卯 Mao | 甲木 Jia Wood 7, 乙木 Yi Wood to the end |
  | 辰 Chen | 乙木 Yi Wood 7, 壬水 Ren Water 5, 戊土 Wu Earth to the end |
  | 巳 Si | 戊土 Wu Earth 7, 庚金 Geng Metal 5, 丙火 Bing Fire to the end |
  | 午 Wu | 丙火 Bing Fire 7, 丁火 Ding Fire to the end |
  | 未 Wei | 丁火 Ding Fire 7, 甲木 Jia Wood 5, 己土 Ji Earth to the end |
  | 申 Shen | 坤土 Kun Earth 5, 壬水 Ren Water 5, 庚金 Geng Metal to the end |
  | 酉 You | 庚金 Geng Metal 7, 辛金 Xin Metal to the end |
  | 戌 Xu | 辛金 Xin Metal 7, 丙火 Bing Fire 5, 戊土 Wu Earth to the end |
  | 亥 Hai | 戊土 Wu Earth 5, 甲木 Jia Wood 5, 壬水 Ren Water to the end |
  | 子 Zi | 壬水 Ren Water 7, 癸水 Gui Water to the end |
  | 丑 Chou | 癸水 Gui Water 7, 庚金 Geng Metal 5, 己土 Ji Earth to the end |

  The text writes 己 Ji as 巳 in the 未 Wei and 丑 Chou months, a slip its own
  hidden-stem lists correct. The commander's element rules the season. Yuan Hai Zi
  Ping, which #66 named, was not used: its copy gives the commanders only in a verse
  keyed to the half-month terms, and the familiar table credited to it is not in it.

## Favourable elements: each element's weight

A school puts the five elements in order. Down the order they weigh +1.2, +1.0, −1.0,
−0.8 and −0.6: the useful element, the favourable one, the disease, the next and the
last. *(The weights are the app's convention, after the daily briefing this page
replaces. They sum to −0.2, so an average day leans slightly to draining; the bands
below are not shifted to hide it.)*

### Support and restrain (扶抑 Fu Yi), the default

Di Tian Sui: 要在扶之抑之得其宜, "support or restrain, each where it fits"; and Zhang
Nan's Shen Feng Tong Kao on disease and medicine (病藥). They give the principle; the
steps below are the app's.

1. **The tally.** Count the natal chart as above, every count times its element's
   standing at the birth, by the chosen Earth's season school. The Day Master's own
   stem counts.
2. **Support** is the tally of the Day Master's element (its Companions) and of its
   Resource. Under half the tally, the chart is **weak**; at half or more, **strong**.
3. **Following.** A chart with no Companion and no Resource anywhere but the Day
   Master's own stem, visible or hidden, follows its strongest force.

The order, by case. Elements are named by their role to the Day Master: Companion,
Output, Wealth, Officer, Resource.

| Case | Disease | Useful (+1.2) | Favourable (+1.0) | Disease (−1.0) | −0.8 | −0.6 |
| --- | --- | --- | --- | --- | --- | --- |
| Weak | Output strongest | Resource | Companion | Output | Wealth | Officer |
| Weak | Wealth strongest | Companion | Resource | Wealth | Output | Officer |
| Weak | Officer strongest | Resource | Companion | Officer | Wealth | Output |
| Strong | Companion stronger | Officer | Wealth | Companion | Resource | Output |
| Strong | Resource stronger | Wealth | Output | Resource | Officer | Companion |
| Following | — | the strongest of Output, Wealth, Officer | what generates it (Wealth when it is Output) | Resource | Companion | the one left |

The rule behind the table: weak, the disease is the strongest of Output, Wealth and
Officer, and the useful element is the one that controls it, except that Officer is
met by the Resource, which it feeds and which feeds the Day Master; the favourable
element is the other of the two that support. Strong, the disease is the stronger of
Companion and Resource, the useful element controls it, and the favourable one
generates the useful. Next comes what generates the disease, or, where that is
already placed, what controls the useful element; last, the one left. A tie goes to
the first named: Output before Wealth before Officer, Companion before Resource.

The daily briefing's two hand-set weight tables are the weak-with-Wealth and the
strong-with-Resource cases, and the rule gives both exactly. The other cases have no
outside reference: their tests hold the code to this table.

### Climate (调候 Tiao Hou)

Qiong Tong Bao Jian names, for each Day Master born in each month, the stems that
month's climate calls for. Its copy is prose, Wikisource's 穷通宝鉴 at revision
2294674 (14 June 2023), and the table the app keeps from it is data
(`eight_characters/qiong_tong_bao_jian.py`): one entry per Day Master and month, with
the stems in the text's order of use, the heading they stand under and the passage
they are taken from, word for word. `tests/fixtures/qiong_tong_bao_jian_2294674.txt`
holds the revision, and the tests find every sentence in it. The reduction:

- What the text says to use for the month, unconditionally, in the order it ranks
  them: 先…后…, …为尊/为用/为主/为要…, …次之/佐之/为佐/为助/为辅. A season's
  passage (三春…, 总之…) counts for a month it names.
- Where the month's use is stated more than once, a statement that ranks its stems
  wins over one that only lists them (专用 X Y, 并用, 兼用, 齐用), then the fullest,
  and of two as full, the later, usually the month's own summary. A statement that
  disclaims its order (四月庚金: 非拘执先后) does not rank.
- A stem the text names only under a condition (或…, 若…, 如无…, 凡…者) or as a
  fallback is left out, and so is a role named without a stem (比劫, 财).
- Where the text treats months together (正二月, 五六月, 三冬), each takes the shared
  entry.
- Where the text divides a month at its middle term (乙 Yi in 午 Wu and 酉 You, 壬 Ren
  in 丑 Chou, 癸 Gui in 辰 Chen), a birth after the middle term takes the second
  half's stems.

The weights then follow:

- The first stem's element is useful, and the next stem's of another element
  favourable; if every stem named shares one element, the element that generates it.
- The disease is the element that controls the useful one; then what generates the
  disease; then the one left. A place whose element is taken goes to the first free
  element in the generating order from the useful one.

## The pull

A pillar's pull is what it brings the chart: for its stem and each hidden stem of its
branch, the element's weight times how much the character counts, summed. Nothing else
enters it: no relationship, no Ten God, no hour.

| Pillar | The stem counts | Each hidden stem counts |
| --- | --- | --- |
| The day | 1.0 × its standing now | its qi × its standing now |
| The month | 1.0 × its standing now | its qi × its standing now |
| The year | 1.0 | its qi × 0.5 |
| The luck pillar, by phase | 1.0 in its stem phase; nothing in its branch phase | its qi |
| The luck pillar, ten years as one | 0.5 | its qi |
| The year and the luck pillar, as the day | as the day | as the day |

*Now* is the day's moment (below), by the chosen Earth's season. The year and the
luck pillar are not scaled by the season unless the school says so: the classics read
a chart's years and decades against the chart, and the season of a single day only
when choosing days (Xie Ji Bian Fang Shu, juan 34: 日之衰旺全看月令). Their pulls share
the bands below.

- **By phase**: San Ming Tong Hui, juan 2, on luck: 在干兼用地支之神，在支則棄天干之物;
  the luck column already sets the stem aside in the branch phase. The year's branch
  at half is the app's convention, after Di Tian Sui's original note that the year
  weighs its stem (太歲……故重天干).
- **Ten years as one**: Di Tian Sui's original note reads a luck pillar as the land
  one passes through, weighing its branch without dropping its stem
  (大運譬如所歷之地，故重地支，未嘗無天干), for the whole decade. The half is the app's
  convention. The luck column still shows its phases; Today names the school it used.

Each part is exact in thousandths and shown rounded to two decimals, half away from
zero; the pull is the exact sum, rounded the same way.

| Band | Pull |
| --- | --- |
| Strongly supportive | 1.50 and above |
| Supportive | 0.50 to 1.49 |
| Mixed | −0.49 to 0.49 |
| Draining | −1.49 to −0.50 |
| Strongly draining | −1.50 and below |

The band is the rounded pull's. Two people **pull apart** on a day when one's pull of
the day is supportive or better and the other's draining or worse.

## The day

`date` is a calendar date at where you are. The day's moment is noon on that date at
that place, as for a first chart with a date and a place: the day's, the month's and
the year's pillars are the engine's at that moment, with the engine's default
conventions (true solar time, the day changing at true solar midnight), and any of
them that changes during that local day is listed with the clock time it changes at.
The standing, the luck pillar and its phase are those of the same moment. A partner's
day is read at the same place.

The run is the seven days before and the fourteen after, each read the same way. A
date whose run would leave the engine's years (1949 to 2100) is refused.

## Relationships

Each of the four pillars of the day (the day's, the month's, the year's and the luck
pillar) is read against the natal chart as the decade page reads a luck pillar: as a
fifth position beside the four, adjacent to each, under the canon's catalogue of
relationships (`eight_characters/interactions.py`), with the natal halves a whole
absorbs. The positions are named `daily`, `monthly`, `annual` and `luck`.

Each relationship carries the canon's line for it. The season the canon's sentence on
the 子 Zi–午 Wu clash speaks of is the birth season, the natal month's, as on the
decade page. The canon's sentences that wait for "a Luck Pillar or annual pillar" are
settled by the luck pillar and the year, never by a day or a month.

## The hours

The twelve double hours of the day, on the clock at where you are, by true solar time:
a double hour starts at every odd hour of true solar time. The day runs from true
solar midnight to midnight, so 子 Zi, which straddles midnight, appears twice: its
first hour opens the day and its second closes it. Each hour gives its spans as clock
times with their UTC offsets, so an hour the clocks skip or repeat shows as it falls.

An hour's **ties** are the relationships, in the canon's catalogue, between its branch
and the day's branch: allied are a combination (六合) and a half-frame; hostile are a
clash, a harm, a punishment and a self-punishment. An hour with the day's own branch is
allied, unless the two punish themselves. The **call** weighs the ties against the
hour's element, its branch's own:

- **Protect**: allied ties only, and the hour's element favourable (weight above zero);
- **Avoid**: hostile ties only, and the hour's element unfavourable;
- **Mixed**: the rest that have a tie;
- an hour with no tie to the day has no call: it says nothing about the day.

The engine does not say what a combination yields, so no tie is read as bringing an
element. The hour stems are not weighed.

## Marriage, Work, Health

- **Marriage.** Both pulls of the day, yours and your partner's, each by its own
  weights, and whether you pull apart; the day's relationships with your Day Branch,
  the spouse palace; the day's relationships with your partner's chart; and your
  partner's luck pillar in force, with its phase.
- **Work.** The career house is your Month Branch: the canon's Background reads a
  strike on it as upheaval in "career, the formative environment, the parents'
  palace". The day's and the month's relationships with it, and the Ten Gods the day
  brings (its stem, and the hidden stems of its branch), each with the canon's sentence
  on what it is.
- **Health.** The elements the day brings, each counted as in the pull but without
  its weight; how much of each your chart holds, as its share of the birth tally; and
  each element's organs in the canon's own words (Background): Wood the liver, Fire the
  heart, Earth the spleen and stomach, Metal the lungs, Water the kidneys. This is not
  medical advice, and the page says so.

## The canon's readings

For each of the four pillars, the canon's passages as the decade page reads a luck
pillar (`eight_characters/reading.py`, `build_luck_reading`): its stem's Ten God, its
branch, the Day Master on that branch (without the sentences that hold only for a Day
Pillar) and the Day Master's stage there, and each relationship as its entry reads,
without a pairing paragraph. The canon is English; a Finnish answer carries no
readings and no lines, as a Finnish chart asks for none.

## What the answer carries

The schools used, the rules' version (`today_v1`) and the engine's. No symbolic stars
and no void: the answer has no such fields, and a test checks it.
