# Changelog

## 0.41.2

Fixes to accounts (0.41.0), from a read of the whole change: the page's language reaches every chart, signing out forgets the chart, and a comparison asks for the sign-in its frames cannot.

### Fixed
- **A chart on screen kept its language when the account's was set in its menu.** The page's words changed, and so did the chart's language switch, which then could not ask for the language it showed; the chart's own words stayed in the other. The chart is now asked for again in the language.
- **A chart on its way kept the language it was asked for** when the page's changed meanwhile (in the account's menu, or on the start page), and was drawn in it, under the page's words in the other. It is now asked for again in the page's language before it is drawn, as often as the language changes meanwhile.
- **Going back to a chart's address after signing out showed the chart again**, from the page's memory, with no session. Signing out now forgets the chart: going back asks for it, and for a sign-in.
- **The page's title** named no chart once the page's language changed with a chart on screen; it names the chart again.
- **A comparison whose session ended elsewhere** asked for no sign-in when its sides were swapped or its language changed: its frames, which cannot ask, each said that charts need an account. The page now makes sure of the session first, as when a comparison opens, and asks for the sign-in itself; a check that fails says so. Meanwhile the comparison's language and sides take no clicks, so one change is made at a time.
- **A comparison's language** reached a frame still asking for its first chart, or showing none, as a script error, whose message the frame showed instead of its chart; and a frame asking for its chart again lost a newer language, so the comparison named a language its chart was not in. A frame now takes the comparison's language as the page takes the account's: a chart on screen is asked for again in it, and one on its way before it is drawn. The comparison's address names its language at once, and a swap draws both charts in it, though a frame has not yet told its new link (one that shows no chart never does).
- **A comparison's toasts did not show**: Copy link's (Comparison link copied) was part of the chart's view, which a comparison hides. The toast is now the page's, over any view.
- **A deletion begun in the account's menu**, its address typed, stayed open when the page took another account (signed in to in another tab); it is now closed, and the address cleared.
- **Signing out on every device after the account was deleted in another tab** answered `204` and removed the session cookie, as if it had signed out. It now answers `401`, as the account's other actions do then.
- **[Your account](docs/Account.md)** says that accounts are also kept in an encrypted backup, which only the site's owner can read, and how long a deleted account stays in it.

### Changed
- Version bumped to `0.41.2`; the static assets' cache keys follow it. The regression fixture changes only in `engine.version`.

## 0.41.0

Charts need an account; the start page does not. Creating a chart while signed out asks for an account first, made or signed in with a code sent by email, free and without a password.

### Added
- **The account dialog**, on the start page (Sign in) and when a chart needs it.
  - A new account needs its language, Finnish or English, chosen and never preset. Its emails come in it, and signing in sets the page to it; the chart asked for is then drawn in it.
  - An existing account signs in from the same dialog, without a language. Every answer reads the same whether the address has an account or not.
  - Cloudflare Turnstile checks for a person; its script loads only when the dialog first opens, so the start page loads nothing from another site. A script that does not load is said, and tried again.
  - Closing the dialog leaves the form, saying that charts need an account, with the birth kept.
- **The account**, signed in, in the same dialog (and among the chart's commands): its address and plan, its language (the page follows it), Download my data (`bazi-account.json`), Sign out, Sign out on every device, and Delete account, which needs the address typed again. Signing out starts the page again, empty. As it opens (or, opened again while an action or this question is under way, once that one ends), it asks who the session belongs to, and its actions wait for the answer, so it never acts for an account another tab has left, and shows a language another tab set. An action's answer counts as the newest of its moment: if the page has learned nothing since, it is the session's, and a language set there signs the page in to its account, even after an older check found the session ended; if the page has learned since, it keeps that, and the action does nothing more, and says so. A language set is saved, and shown, unless a later change of the account (another tab's) stands.
- **The newest answer decides who is signed in.** Tabs share the session cookie, and answers come in any order. Each tells of the cookie at a moment: a request that carries it, as it was sent; an answer that sets or removes it (signing in or out, deleting the account), from when it comes. The page takes the newest, and an older answer changes nothing, however late it comes; of one account, it keeps the language and plan of the later change. A sign-in whose answer sets its cookie after a check took another tab's account signs the page in; one overtaken by a newer answer closes signed in to that answer's account, or, if the session ended since, asks for a sign-in again. A code answered after the page took another tab's session changes nothing, and the account's menu stays.
- **A session that ended** (signed out elsewhere, deleted, or past its 30 days) asks for a sign-in once more, and the chart is asked for again. A refusal is checked once more first: if the browser holds a session after all (another tab signed in), the page takes it and asks for the chart again; a chart left meanwhile asks for nothing. A refusal that arrives for a chart no longer wanted asks nothing, so a sign-in made since for a newer chart stays.
- **A comparison** opened signed out, or after the session ended elsewhere, asks on its own page (which checks the session with the server first), before its frames ask for their charts. One signed in to in another tab is taken as a sign-in here, and both charts take its language, as when signing in here; a check asked for before a language set in the dialog meanwhile is older, so the language stays. The answer to a check for a comparison no longer wanted, or older than what the page has learned since, changes nothing, and signing out abandons a comparison on its way. **The explorer**, given a birth, links a visitor to the start page to sign in.
- **[Your account](docs/Account.md)**, a guide for readers.

### Changed
- **The account's actions name the account they are for**: setting its language (`PATCH /api/account`), signing out everywhere (`DELETE /api/account/sessions`) and Download my data, which is now `POST /api/account/export`, carry `{"key": …}`, the account's key from its answers, and Delete account carries it beside the address typed again. Tabs share the session cookie, so another tab may have signed in to another account since, or deleted this one and made it again with its address: the server then answers `409` and changes nothing, and the menu says so and asks who the session is.
- **Charts need an account.** `POST /api/four_pillars`, `/api/chart`, `/api/hidden_stems` and `/api/evolution_explorer` answer `401` without one, before the request is validated. The place search and `GET /api/evolution_controls` stay open. A test holds both lists, so a new request must join one.
- **An account's answers say when it last changed** (`updated_at`), and each change moves that on, by a second within one second or with the clock gone back: of two answers about the account (the newest or not, and one for a chart or comparison no longer wanted too), the page keeps the later change's, of any account it has seen, so a change saved while it held another account is kept when that account comes back. They name the account by a `key`, a hash of its id (which no account answer carries), so that an account made again with an address is told apart.
- **The start page names the signed-in account** (or `null`) for its script, and is sent `Cache-Control: private, no-cache`. It extends a session in its second half, on the server.
- **The app reads its account settings, and opens its database, as it starts**: a missing or malformed setting stops it with the reason. Running it on a laptop needs the settings in [Accounts, on a laptop](docs/Developer/Accounts.md#on-a-laptop).

### Fixed
- **Signing in when another tab made the account and it was deleted meanwhile** refused nothing and answered 500; it now refuses the code, as when an account goes before its session is made.
- **A late answer that renewed a session set its cookie again**: after a sign-out and a new sign-in, it put back the session signed out, and the browser lost the new one. Only signing in now sets the cookie, for 400 days, the longest browsers keep one; the server alone extends a session used in its second half, and ends one 30 days after it was made or last extended.
- **An answer for a session that ended removed the session cookie**, though by then it could be a newer session's: the browser may have signed in meanwhile, and a cookie is removed by its name. The cookie of a session that ended is now left to expire; signing out and deleting the account still remove it.
- **A session renewed by one request while another found it ended** was deleted by the second, or turned away by it, and its answer removed the browser's fresh cookie. A session is now deleted only while it is still ended, and renewed only while it is still live; a request that found it ended after another renewed it takes it as renewed.
- **The account export listed requests for codes older than the hour**, kept until the next code was asked for. Exporting now drops what has passed its time first: ended sessions and codes, and requests older than the hourly window.
- **A full or unwritable mail folder** (on a laptop) answered 500; it is now a mail error, answered 502 like any message that could not be sent.

### Tests
- `tests/test_accounts_app.py`: which requests need an account, the `401`s (also for a session that ended), the start page's account state (escaped, without the session or the account's id), extending the session there without a cookie (also when another request renews it as the page's crosses its old end), leaving the cookie of a session that ended, and starting the app with missing settings, a missing database, and complete ones.
- The API tests sign in as the page does.
- The browser suites sign in to accounts of their own through the API, reading codes from the app's mail folder (`EC_MAIL_DIRECTORY`). The new account suite and the foundations audit of the dialog run in both engines, on desktop and mobile; Cloudflare's widget is stubbed.
- Version bumped to `0.41.0`; the static assets' cache keys follow it. The regression fixture changes only in `engine.version`.

## 0.40.0

The luck pillar stands in the chart. This is the fourth slice of the luck pillar design, in its first part: the fifth pillar, its keys and its link. The luck pillar's arcs, and the topics with luck, come next.

### Added
- **The fifth pillar.** A chart with a gender keeps a fifth column beside the Year. It opens natal: the column is kept, empty but for its note. L, or the Natal / With luck switch among the chart's controls, shows the chosen period there and hides it again. Choosing a period, on the ribbon or with the keys, shows it.
  - Showing it moves nothing. Hidden, its cards keep their room unseen, in every display and at every width.
  - It reads as the natal pillars do: its name, the decade's place and years, its characters, and its stem and branch cards. Its mark says the phase and when it ends.
  - In the stem phase the stem leads, ringed, and the branch acts too. In the branch phase the branch leads, and the stem is set aside in its element's tint.
  - Before the first decade, the column says when the first starts.
  - Its cards take the chart's display. A long press turns one, and a click opens the branch's hidden stems. Its name opens the decade's page.
  - On a phone it stands above the two-by-two chart, its stem beside its branch.
- **One choice.** The ribbon, the fifth pillar, the decade's page and the keys show and move the same period.
- **Keys**, while the chart has focus:
  - L shows and hides the luck pillar;
  - [ and ] step a phase, and { and } a decade;
  - N chooses today's phase and opens its page.

  The luck pillar's cards follow the Year's in the cards' arrows. Enter, Space and T work on them, and R opens the decade's page. ? lists the keys.
- **Its link.** `luck=before` or `luck=<decade>/<stem|branch>` names the period standing in the chart. A change of language keeps it.
- **API: `luck_chart`.** With `include_chart` and `include_luck_pillars`, each luck pillar's cards come drawn as `chart` draws the natal pillars', in the request's language.
- **Finnish, provisional until confirmed:** Onnenpilari, Syntymäkartta, Onnen kanssa (the switch); Rungon vaihe vuoteen {year}, Haaran vaihe vuoteen {year}, Ei onnenpilaria ennen ikää {age}, L näyttää onnenpilarin, Sivussa (the fifth pillar); Näyttää ja piilottaa onnenpilarin, Vaihe taakse tai eteen, Vuosikymmen taakse tai eteen, Onnenpilari nyt (the keys).

### Changed
- ‹ and › no longer open the decade's page. They move the luck pillar; an open page follows them, and a closed one stays closed.
- A chip pressed again closes its page and leaves the decade in the chart.
- A relationship on the decade's page rings the luck pillar's card as well as the natal ones.

### Fixed
- Opened hidden stems keep their content's height at any width. Opening them set a fixed height that a later change of width left in place, so the panel clipped its rows or left a gap. The listener meant to free the height took the opacity's end for the height's.

### Tests
- `tests/browser/luck.test.mjs`:
  - the fifth pillar's invariance: every card, panel and arc stays in place as L shows and hides it, in all three displays, at 1440, 1024, 900 and 700px and on phones;
  - its phases and states, the keys and the focus they need, and the cards' keys;
  - the luck part of links, and bad ones;
  - a phone's layout, and a change of language.

  The earlier tests follow the steps and chips as they now behave.
- `tests/test_api_luck_pillars.py`: `luck_chart` in both languages, checked against the natal chart's own drawing of a character the two share; absent without the chart or the luck pillars.
- Version bumped to `0.40.0`; the static assets' cache keys follow it. The regression fixture changes only in `engine.version`. (0.38.0 was skipped: it was held for PR #48, released as 0.41.0.)

## 0.39.0

Luck pillars on the chart. This is the third slice of the luck pillar design: the form takes an optional gender, the chart shows its decades on a ribbon, and a decade opens a page of its own.

### Added
- **The gender, optional.** The form asks for it: Not given, Female or Male. Only luck pillars need it. A chart with one asks the API for its luck pillars and their context, and its link names it (`gender`). Edit keeps it; New chart starts without one.
- **The ribbon**, under the chart's topics: the years before the first decade, then each decade by its characters, names and starting age. The decades are grouped by the direction their branch travels: East · Spring, South · Summer, West · Autumn, North · Winter. Today's decade and phase are marked.
  - A chip opens its decade at today's phase, or else at its stem phase. Pressed again, it closes.
  - ‹ and › step one phase at a time, from the years before the decades to the last decade's branch phase.
  - Today opens today's phase.
  - The chips take one tab stop; the arrows, Home and End move between them.
  - The commands offer the years before the decades and each decade.
  - Where the decades do not fit, the ribbon scrolls within itself and keeps the open decade, or today's, in sight. On a phone its name and Today stand above it.
- **A decade's page**, in the panel:
  - its two phases with their dates: the stem phase, when the stem leads and the branch acts too, and the branch phase, when the branch acts alone;
  - what it brings: the luck stem and the branch's hidden stems, with their Ten Gods, each marked when new to the chart. In the branch phase the stem says "not now";
  - the Day Master's stage on the luck branch, named as the canon names it, and its roots there;
  - its relationships with the natal chart and when each acts; a whole names the natal half it takes in, and each points at its natal cards;
  - the elements counted with the luck pillar: ten characters in the stem phase, nine in the branch phase.
- **The years before the first decade**, with a page of their own.
- **Today, where there is one.** A birth still to come, or a life past its last decade, has no today on the ribbon; ‹ and › then start from just beyond that end.
- **A nominal timeline says so.** The luck pillars' allowance around a jie is 3 s, wider than the natal chart's 0.5 s. A birth within it gets a notice under the chart's name, and each decade's page says that its dates are nominal: on the jie's other side the decades and their starting age change, and at Lichun so does their direction.
- **Links** to a phase: `topic=luck/before` and `topic=luck/<decade>/<stem|branch>`.
- **Strict reading.** The page checks the luck pillars as it reads them: decades in sequence and meeting end to end, two phases each that meet, relationships that name the luck pillar, counts that add up. Otherwise no chart is drawn, and the form says why.
- **Finnish, provisional until confirmed:** Sukupuoli (valinnainen), Ei annettu, Nainen, Mies; Onnenpilarit, Onnenpilari; Ennen, Tänään, Edellinen vaihe, Seuraava vaihe; Itä, Etelä, Länsi, Pohjoinen; eteenpäin, taaksepäin; Rungon vaihe, Haaran vaihe; Mitä se tuo, uusi tälle kartalle; Päivän mestarin juuret, Syntymäkartan kanssa. The twelve stages: Syntymä, Kylpy, Kruunaus, Virkaan astuminen, Keisarin huippu, Heikkeneminen, Sairaus, Kuolema, Hauta, Sammuminen, Alkio, Hoiva.

### Tests
- `tests/browser/luck.test.mjs`, desktop and mobile, on the design's sample with the clock at 7 October 2026:
  - the optional gender, the ribbon, Today and both phases, word for word;
  - steps, chips, focus, the tab stop and arrows;
  - the years before the decades, and a child's chart, an old one and a birth to come;
  - births seconds from Jingzhe and from Lichun, with their notices;
  - links, an absorbed natal half, refused data, Finnish, the language switch and the commands.
- The foundations audits (fonts, glyphs, contrast and element dots) visit a chart with luck pillars.
- `luck.js`'s pinyin and direction tables match the engine's, and the English stage names match the canon's twelve.
- Version bumped to `0.39.0`; the static assets' cache keys follow it. The regression fixture changes only in `engine.version`. (0.38.0 was skipped: it was held for PR #48, released as 0.41.0.)

## 0.37.0

The engine says what each luck pillar brings to a chart, phase by phase. This is the second slice of the luck pillar design; the API comes first, and the screens follow.

### Added
- **Phases.** Each luck pillar is a stem phase, its first five years, and a branch phase, its last five. San Ming Tong Hui's passage on major cycles: while a cycle is on its stem, the branch is used as well; while it is on its branch, the stem is set aside. Each pillar's `phases` gives both intervals with their ages and UTC instants. The boundary between them is the fifth anniversary of the cycle's start, counted from the first onset like the cycles' own boundaries. `luck_pillars.phase_rule` is `stem_then_branch_v1`.
- **The luck context**, with `include_luck_context` (which needs `include_luck_pillars`). For each decade:
  - the luck stem and the hidden stems of the luck branch, each with its Ten God, whether the chart has that Ten God at all, and the phases it acts in;
  - the Day Master's stage on the luck branch, and its roots there;
  - each relationship the luck pillar forms with the natal pillars, under the natal rules, with the phases it acts in: a stem's in the stem phase, a branch's in both. The luck pillar counts as adjacent to every natal pillar;
  - the natal halves that a frame or triangle completed by the luck pillar absorbs for the decade;
  - element and Ten God counts, natal and with the luck pillar in each phase: eight characters natal, ten in the stem phase, nine in the branch phase.

  Counts are tallies, not weights; nothing weighs strength, transforms or predicts.

### Changed
- `luck_pillars`: each pillar gains `phases`, and the payload `phase_rule`. Everything else in it is unchanged, the decades' boundaries included.
- Relationship detection gathers each combination's characters once for all the rules, about three times faster, with the same findings, ids and order.

### Fixed
- The 0.35.0 entry gave the Finnish relationship names as provisional; the maintainer has confirmed them.

### Tests
- The relationships a luck pillar forms, and the natal halves it absorbs, against independent readings of the canon on every combination of four natal branches and a luck branch (248,832), and of four natal stems and a luck stem (100,000).
- The design's sample chart (14 August 1975, 07:45, Helsinki, female), decade by decade by hand, and through the API.
- Phases, and their leap-day anniversaries.
- `tests.test_api_luck_context` runs in the API integration gate.
- Version bumped to `0.37.0`; the static assets' cache keys follow it. The regression fixture changes only in `engine.version`. (0.36.0 was skipped: it was held for PR #48, released as 0.41.0.)

## 0.35.0

Standard reads every relationship family the canon defines. Luck pillars will form these families with a chart most of all, so they come first.

### Added
- **Five more relationship families**, rules 22–44. They follow `canon/Taxonomy.md` where Evolution's catalog differs from it:
  - half-frames: two of a frame's three branches, one of them its Peak Branch (子 Zi, 卯 Mao, 午 Wu or 酉 You). Birth and Storage without the Peak only cradle it and are not listed;
  - the four directional combinations, 亥子丑 Hai-Zi-Chou, 寅卯辰 Yin-Mao-Chen, 巳午未 Si-Wu-Wei and 申酉戌 Shen-You-Xu, all three present;
  - the punishments: the triangles of Ingratitude, 寅巳申 Yin-Si-Shen, and of Bullying by Strength, 丑未戌 Chou-Wei-Xu, two of three as a half-punishment, and 子卯 Zi-Mao;
  - the four self-punishments: 辰 Chen, 午 Wu, 酉 You or 亥 Hai in two pillars;
  - the six harms.

  A complete frame or triangle absorbs the halves among its own members.
- **Their readings, in English.** Each finding reads the canon's paragraphs for its own form:
  - a half-frame: its frame's opening, the points of its two branches and the paragraph on half-frames;
  - a whole punishment: what applies to the whole, and a half-punishment what applies to two of three;
  - a self-punishment: its own branch.

  Every paragraph of the canon now reaches some chart's reading. The labels the reading relies on are checked when the app starts.
- **A line of its own for each form.** Under its name in the list, and on a pillar's page, a relationship reads the canon's sentence about its own form:
  - a half-frame or a half-punishment: the sentence on its own two branches; a half-frame's names the branch it lacks;
  - a whole punishment: its character;
  - a harm: what it does in practice, which runs both ways;
  - a self-punishment: its own branch's first sentence;
  - with a pillar pairing, the pairing's first sentence, and anything else its entry's first sentence, as before.

  The reading gives the line as `line`, and the sentences it chooses are checked when the app starts.
- **On the chart.** A combination, clash or frame keeps an arc of its own, as before. A half-frame, directional combination, punishment or harm joins an arc that already spans the same columns, as a strand 3px inside the one before. Where none does, it gets an arc of its own.
  - Without the strands, 730 of the 20,736 combinations of four branches would need more than the four levels the arcs' rows hold. With them, every one fits in four levels and at most three strands.
  - Charts with only the earlier families are laid out exactly as before.
- **A line for each kind**, on the arcs, in the list and around the selected cards:
  - a directional combination: 2px solid;
  - a punishment, half-punishment or self-punishment: 2px dashed;
  - a harm: 2px dotted;
  - a half-frame: double, like its frame.
- **Names.** English: Half-frame, Directional combination, Punishment, Half-punishment, Self-punishment, Branch harm. Finnish: Puolikas kolmen haaran harmonia, Suuntayhdistelmä, Rangaistus, Puolikas rangaistus, Itserangaistus, Haarojen vahinko.

### Changed
- `include_interactions`: `kind` takes six more values, and `completeness` takes `half` (two of a triple's three). Rules 1–21, their ids and their order are unchanged.
- An empty list says "No relationships between these pillars."
- The canon's "About" lines under the list go by family, so a frame and a half-frame share one.

### Fixed
- A sentence that ends inside quotes ends there, in the reading and on the page: 'hence "uncivilized."' closes the Zi-Mao punishment's character.

### Tests
- New tests:
  - a brute-force reading of the canon's own tables, compared with the detector on every combination of four branches;
  - the shared families' findings, ids and order, compared with the detection before these families came, on every combination of four branches and of four stems;
  - each form's paragraphs, and its line in the list, word for word; every relationship's line is one whole sentence of its own reading, and a canon without a form's sentence is refused;
  - the arcs' levels and strands on every combination;
  - real charts for each new family, an arc of three strands and six feet on one card.
- Browser expectations that named a chart's relationships now include what the canon finds besides. The chart with none is 1990-01-15 12:00 in Chengdu; 1990-01-01 holds a harm and a half-punishment, twice.
- Version bumped to `0.35.0`; the static assets' cache keys follow it. The regression fixture changes only in `engine.version`. (0.34.0 was skipped: it was held for PR #48, released as 0.41.0.)

## 0.33.1

CI and the linters test the Python that production runs, 3.11. Nothing the app computes or serves changes.

### Fixed
- **CI tested other Pythons than the one production runs.** The production image is `python:3.11-slim`, but the seven test gates, the accounts gate among them, ran Python 3.13 and the style and type gates 3.12; ruff targeted 3.12 and pyright checked for 3.12. Code that needs 3.12 passed every gate, then failed on the server, which deploys a merge to `main` within about five minutes: an f-string that reuses its quotes, a `type` statement or a type parameter list is a syntax error on 3.11, so its module cannot be imported, and `itertools.batched`, `typing.override` or `Path.walk` raises where it runs.
  - Every gate now runs 3.11; ruff targets `py311`, and pyright checks for 3.11.
  - At 3.11, ruff refuses the three syntax forms and pyright all six; at 3.12, neither refused any.
- **The test gates check the numbers production computes.** From Python 3.12, built-in `sum()` adds floats with compensation, and the explorer's model sums with it. On one machine, the same 30 explorer runs give 3,220 values that differ between 3.11 and 3.13, by at most 5.6e-14 of their size: a basin's mass is 0.9999999999999996 on 3.11 and 1.0 on 3.13. Nothing else differs: every jie from 1950 to 2100, 7,858 apparent solar longitudes and 400 charts with every section are identical byte for byte.

### Changed
- The developer guide names Python 3.11 and creates its venv with `python3.11`.

### Tests
- **`test_production_python`**, in the regression-safety gate, fails when `requires-python`'s floor, ruff's target, pyright's version or any workflow's `python-version` names another Python than the Dockerfile's. Each job must set up its own Python with `actions/setup-python`, one version per step: a job without it runs the runner's Python, whatever the other jobs set up. On 0.33.0 it fails 11 times: the nine workflows' jobs, ruff and pyright.
- Version bumped to `0.33.1`; the static assets' cache keys follow it. The regression fixture changes only in `engine.version`.

## 0.33.0

The backup gets ready to run on the server: it says when it is alive, its repository can watch it, and the image carries the tools it runs. Nothing on the page changes.

### Added
- **`backup --heartbeat SECONDS`.** With nothing new, a run commits an empty `backup: alive` once the last commit is that old. The server uses an hour, so a quiet backup can be told from a stopped one.
- **The backup repository's freshness check** ([`docs/Developer/backup-freshness.yml`](docs/Developer/backup-freshness.yml)). It runs hourly in the repository and fails once the last commit is three hours old; GitHub then emails whoever last changed its schedule. The repository's owner commits it, so that is the owner.
- **Git and OpenSSH in the image**, which the backup job runs.

### Changed
- **The backup leaves `.github/` to the repository's owner.** It never writes there, and takes commits that change nothing but `.github/` as the owner's, building on them, so the owner's check does not stop it. Any other commit it did not make still stops it.

### Tests
- The heartbeat (quiet runs, a recent commit, a run with something new), the owner's folder (seeded before the first run, changed later, refused as a link, kept through a restore) and `--heartbeat` refusing zero.
- Version bumped to `0.33.0`; the static assets' cache keys follow it. The regression fixture changes only in `engine.version`.

## 0.32.0

The account API: people can sign in with a code sent by email. The page starts using it in the next release; until then nothing on it changes, and charts need no account.

### Added
- **Signing in with a code**, without passwords or a separate sign-up.
  - Asking for a code to create an account takes its language, Finnish or English, which then sets the language of its emails.
  - The first code redeemed for a new address creates the account. Codes have six digits, work once, for ten minutes, with at most five wrong tries.
  - Every request gets the same answer, `202`, so the answer never tells who has an account. The email says what happened instead: a code to create the account, a code to sign in, word that the account exists already, or word that there is none.
  - Codes and session tokens are kept only as keyed hashes.
- **Sessions** in an HttpOnly, SameSite=Lax cookie (`__Host-` over HTTPS) for 30 days, extended when used in their second half. Signing out ends this browser's session or every session of the account.
- **The account API** (`/api/account`): ask for a code, sign in, read the account, change its language, sign out, download everything kept for the account as JSON (its record, sessions, a pending code, and the codes asked for with the client addresses they came from), and delete it after typing its address again. Every request that changes something must come from the site's own origin. See [Accounts](docs/Developer/Accounts.md).
- **Emails** in Finnish and English, plain text, sent over SMTP with TLS from the first byte (Resend, from nektari.fi), or written to a folder when running on a laptop.
- **Cloudflare Turnstile** checks for a person before any email is sent. Without an answer from Cloudflare, nothing is sent.
- **Limits:** codes per address and per client per hour, both set by the environment. Refused requests do not count, so asking again never lengthens a wait.
- **Settings** come from environment variables and are checked together: a missing or malformed one is named.

### Changed
- The account database is at schema 2: sessions, sign-in codes and the record of codes asked for. None of them is backed up. Deleting an account deletes its sessions and sign-in code; the record of codes asked for stays until it is an hour old, so that deleting and creating an account again does not reset the hourly limits.
- Migrations read the database's version under the write lock, so two processes opening an older database at once never run one twice.

### Tests
- The `accounts-gate` adds the sign-in logic, the emails and Turnstile, the settings and every account endpoint, among them the same answer for every address, the cookie's attributes, the Origin check and the hourly limits.
- Version bumped to `0.32.0`; the static assets' cache keys follow it. The regression fixture changes only in `engine.version`.

## 0.31.0

Accounts get a home: one database, and a backup of every account as its own encrypted file in a private Git repository, from which the database can be rebuilt with one command. Nothing on the page changes; signing in comes in a later release.

### Added
- **The account database** (`eight_characters/accounts/`), one SQLite file.
  - A user has an id, an email address (trimmed and lowercased; one account per address), a language (`fi` or `en`), a plan (`free`, `basic`, `pro` or `max`) and when it was made and last changed.
  - The file is owner-only, writes ahead to a log and syncs every commit, so a finished change survives a crash or a deploy.
  - It opens only an existing account database, never creating an empty one, and refuses a schema newer than the app knows. Migrations are numbered and run in their own transactions.
  - New and restored databases are built aside, in a file created exclusively, and moved into place when complete.
  - Account databases carry SQLite's application id, so another application's file is never taken for one.
  - Every change to a backed-up record is logged in the same transaction as the change.
- **The backup.** Each run copies the accounts changed since the last run that reached the remote into a Git checkout, one file per account, encrypted with age to a public key, so the server and GitHub hold nothing readable. It writes a manifest (the key and the count), commits, pushes, and only then counts the changes as backed up: a failed push leaves them for the next run.
  - A checkout with changes of its own, a file or a link the backup never writes, records without a manifest, another key, or a file count that differs from the database stops the run with the reason.
  - The database remembers the backup's last commit. The server cannot read the files, but any commit it did not make, such as a file corrupted by hand, stops the run before anything is added to it, even one undone since: a push would publish it.
  - A run that fails before its commit puts the checkout back as it found it, so the next run names the same problem instead of its predecessor's files. A run stopped outright while writing (killed, or the server restarting) leaves a marker, and the next run puts its changes back and writes them again.
  - Git never waits for a password and each command has two minutes.
  - `squash-history` replaces the backup's history with one commit of its files, so deleted accounts leave it. It squashes only the backup the database last wrote, whole: its layout, a manifest that counts its records, and the commit the database recorded. It is recorded before anything moves: stopped part way, it stops the backup until run again, which finishes it; a refused push leaves the history as it was.
  - A commit is recorded as pending before the branch moves to it, so a run stopped between the two is taken up by the next run.
- **The restore** rebuilds a database from a clone of the backup and the private key. It holds the checkout's lock and checks the manifest, the key, the layout, every file's decryption and form, and the count before the new database appears.
- **Commands:** `python -m eight_characters.accounts init`, `keygen`, `backup`, `restore` and `squash-history`. See [Accounts](docs/Developer/Accounts.md).

### Changed
- `requires-python` is `>=3.11`: the engine has needed 3.11 (`datetime.UTC`, `typing.NotRequired`) all along.
- New dependency: `pyrage==1.4.0`, for age. It ships no type stubs, so `typings/` carries the ones the app uses.

### Tests
- A new `accounts-gate` runs 76 tests: records, the database (including eight sign-ups with one address at once), backup runs against a real Git remote (including that no address reaches any Git object), squashing, restores of tampered backups, identity files and the commands.
- Version bumped to `0.31.0`; the static assets' cache keys follow it. The regression fixture changes only in `engine.version`.

## 0.30.0

The Evolution explorer: a parameter pane, and runs that carry their own parameters. This rebuilds PR #7 from today's `main`.

### Added
- **A parameter pane in the explorer.** The Parameters button opens it beside the graph.
  - It holds the run (particles, temperature steps, sweeps, seed), the clustering, the conventions and every constant of the model, in groups, each with its default and range.
  - Recompute asks for the chart again with every value that differs from its default, so earlier changes stay applied. A change made while a recompute runs waits for the next.
  - Discard Changes returns to what the chart was computed with; Reset to Defaults sets every value back to its default. Either one drops a recompute on its way, even one that changes nothing but the seed.
  - A refused recompute says why, and the chart stays as it was.

  On a phone the pane is a sheet over the foot of the page.
- **`GET /api/evolution_controls`** lists every run setting, convention and model parameter, with its default, range, step and labels.
- **`POST /api/evolution_explorer` takes `run` and `model`**: the run's size, seed and clustering, and overrides of the model's parameters by name. Each is checked against its range before any work, and the largest run takes about 4.5 times as long as the default one. `graph_data.parameters` reports what the run used.

### Changed
- **Each run carries its own parameters.** The energy, mechanics, rule families, inference, post-processing and the explorer's graph builder read every constant from the immutable `ModelParameters` the run is given, never from module state.
  - Given none, a run uses the model's own values.
  - The explorer's output equals 0.29.2's byte for byte for ten births.
- Post-processing's five motif thresholds, which were written into the code, are model parameters now, with the same values.
- `POST /api/evolution_explorer` refuses fields it doesn't know.
- **The explorer measures its graph again whenever the canvas changes size**, not only when the window does: when the pane opens or closes, and when the web fonts arrive after the first drawing. Until now, at 1440 or 1100 px wide, the graph stayed drawn for a canvas 17 px taller than the one it ended up in.

### Removed
- The fallback that invented a basin (Standard mode, every ten god a Companion) when clustering formed none. Such a run is refused with 400, naming the two clustering settings; the explorer's default settings always form one.

### Tests
- New tests cover:
  - the parameters' defaults, limits, wiring and isolation;
  - the API's catalogue, overrides, refusals and concurrency;
  - the pane in the browser, desktop and mobile.

  Twenty-four planted faults, among them each of the reviews' findings on PR #7, fail them.
- Version bumped to `0.30.0`; the static assets' cache keys follow it. The regression fixture changes only in `engine.version`.

## 0.29.2

Unused strings leave the page's translations. Nothing on the page changes.

### Removed
- **The old Support page's strings**, in Finnish and English: `context_support`, `context_companions`, `context_resources`, `context_support_meta`, `context_support_note`, `context_hidden` and `context_both`. Roles replaced that page, and nothing has read them since:
  - no script, template, test or doc names them;
  - no key the page builds at runtime can be one of them. The one `context_` key built from data takes a season's name, checked first to be one of the four seasons.

### Changed
- Version bumped to `0.29.2`; the static assets' cache keys follow it. The regression fixture changes only in `engine.version`.

## 0.29.1

The installed package serves every file the app uses. Nothing changes where the app runs from its source tree, as on Render.

### Fixed
- **The explorer's files and the start page's fonts were missing from the package.** `package-data` had never listed anything under `eight_characters/explorer/`, so the wheel and the sdist carried only the explorer's Python module.
  - Installed from its wheel and run from another directory, the app answered 404 for the explorer's stylesheet, d3, data and script, and for the two fonts the start page loads from `/explorer/vendor/fonts/`, Manrope and Cormorant Garamond.
  - The Docker image served them only because uvicorn puts its working directory, `/app`, first on `sys.path`, so the copied source tree shadows the installed package.

  `package-data` now lists the explorer's stylesheets, scripts, sample payloads, d3 and fonts.
- **A test keeps it so** (`test_served_files_ship_in_the_package`): every file in a directory the app serves from (`/static`, `/explorer`) or renders templates from must match a `package-data` pattern, expanded the way setuptools expands it. On 0.29.0 it fails, naming the explorer's 16 files.

### Changed
- Version bumped to `0.29.1`; the static assets' cache keys follow it. The regression fixture changes only in `engine.version`.

## 0.29.0

### Added
- Backend ten-year luck pillars, opt-in through `include_luck_pillars` on
  `POST /api/four_pillars`, with explicit `male`/`female` gender input and
  1-12 actual cycles (default 10).
- Direction from the Lichun-resolved year stem, progression from the natal
  month pillar, and onset from the engine's own Jie instants in TT.
- A documented continuous three-days-per-year convention, UTC calendar
  boundaries, symbolic onset ages, pre-luck period and visible uncertainty.
- Engine/API regression tests and independent package comparisons, included
  in the core and API CI gates. No frontend integration.

### Changed
- Reject negative or non-finite birth-time uncertainty instead of calculating
  with invalid uncertainty; reject finite values that overflow luck-age scaling.
  Existing natal-only response sections are unchanged.

## 0.28.0

Readings: the canon's taxonomy, `canon/Taxonomy.md`, in the pages the chart already has.

### Changed
- **Readings.** In an English chart, each page reads what the canon says of this chart. The engine chooses the passages that apply:
  - the Day Master;
  - each pillar's stem and branch;
  - the life stages;
  - the relationships it finds.

  The words are the canon's, and nothing assesses strength or predicts. The cards stay as they are.
- **A reading is one line:** a key, the passage's own first sentence, and the hidden stems' chevron. The rest opens beneath, and what is open stays open from page to page. A line points at its cards, as the panel's other lines do.
- **A pillar's page** reads:
  - the Day Master's lens on the pillar;
  - who stands on its stem, and that stem's own stage on its branch;
  - its ground;
  - the Day Master on this ground, and its stage here;
  - the relationships that touch the pillar.
- **The Day Master line** opens the Day Master's own page, `topic=day-master`. The page reads:
  - what the Day Master is, and how it meets any ground;
  - its lens on each pillar;
  - its cycle, as a sentence and as a ring of the twelve stages with this chart's branches on it;
  - the twelve stages;
  - the pattern of reconception.
- **Relationships** read their first sentence in the list, what each kind is, and on each page:
  - the canon's pairing;
  - for a stem combination, the Day Master's part in it, its dynamic and its mechanics;
  - the entry.

  A condition the chart settles, the Zi–Wu clash's season, is said before the entry.
- **Roles, the season and the roots** read their own lines beside their evidence.
- **Links in a reading** open their page at the line they name, in one step of the history.
- **R on a focused card** opens its pillar at the card's own line. While a pillar's page is open, the arrow keys turn it.
- **English only.** The canon is English. A Finnish chart asks for no reading, and every Finnish page is as it was, pixel for pixel.
- **The API.** `POST /api/four_pillars` takes `include_reading` and returns `reading` under the policy `canon_taxonomy_v1`:
  - the canon is packaged with the app and parsed into keyed passages;
  - a malformed canon is refused;
  - the exact words the reading relies on are checked when the app starts.

  A new `life_stages` module gives the life stage of any stem on any branch. It matches the canon's table and lunar_python on all 120 cells.
- **The canon writes pinyin without diacritics,** as the app does: its 148 marked letters are plain. A test refuses any diacritic. The canon's arrow is drawn, as the app's other arrows are, since the page fonts have none.
- **A full panel keeps the page's margins.** Beside the chart, from 1200px, a panel at its full height made the page 48px taller than the window. Where scroll bars take room, the bar then moved the chart a second time, as the Roles page already did. The panel now keeps the page's margin above and below, as the `--page-block` token.
- **What is not in yet** is listed in #39, found by building the reading for every path the engine can select. 523 of the canon's 579 paragraphs reach some chart's reading. The rest are the punishments, harms and directional combinations Standard does not detect yet. A test keeps that list exact.
- **Docs.**
  - New: `docs/Standard-Readings.md`.
  - `docs/api.md` documents `include_reading`.
  - The keyboard and links pages name R and `topic=day-master`.
- **Tests.**
  - Python: the canon parser, including every paragraph read once and five malformed canons refused.
  - Python: the life stages against the canon and lunar_python.
  - Python: the reading, for every Day Master in every pillar on every branch, and every relationship.
  - Python: what no reading can show.
  - A browser suite for readings, `reading.test.mjs`.
  - The foundations suite's font, glyph and contrast audits also visit the readings, open.
- Version bumped to `0.28.0`; the static assets' cache keys and the regression fixture's `engine.version` follow it.

## 0.27.0

Stage 5 of the Standard view overhaul (#20), part 3: two charts side by side.

### Changed
- **Compare**, in a chart's bar and among the commands, asks for the second birth. The form names the chart it will be compared with; Cancel goes back to it.
- **The two charts stand side by side.** Each is the chart view itself, in a frame of its own. It keeps its display, Copy as text, topics, panel (a sheet over the foot of its frame) and the pointing from its panel. Nothing is drawn between the charts.
- **The comparison's bar** holds:
  - the language, which asks both charts again in it;
  - Swap sides, where each chart keeps what is open in it;
  - Copy link, for the pair;
  - Close, which goes to the first chart.

  Narrower than 900px, one chart shows at a time, with a switch between them.
- **The pair's address**, `#compare?a=…&b=…`, holds both charts' links. It follows what is open in either, so the link reopens both as they were. With `a` alone, the form asks for the second chart. Back steps from the pair to its form, then to the first chart; what is done within a chart adds nothing to the history. A comparison link that names no pair says why.
- **Embedded chart view** (`?embed=1`). The chart view can be embedded in a comparison's frame: its bar keeps the chart's own controls, its steps replace its history entry, and it tells the page each address.
- **Docs.** New `docs/Standard-Compare.md`; the links and keyboard pages point to it.
- **Tests.** A browser suite for comparing (`compare.test.mjs`), with the charts' pillars checked against the API. Each of four faults put in fails at least one of its tests:
  - a compared chart adding history entries;
  - Swap moving the frames, which reloads them without their open topics;
  - the language not passed on;
  - the pair's address not following its charts.
- Version bumped to `0.27.0`; the static assets' cache keys follow it.

## 0.26.0

Stage 5 of the Standard view overhaul (#20), part 2: a dark theme.

### Changed
- **A dark theme**, on screen when the system's setting is dark. The colour tokens take the embers palette, chosen from three drawn on the real chart:
  - a dark warm page with light ink;
  - deep element colours with light type (metal `#5C5851`, fire `#7C3E34`, wood `#3D5C38`, earth `#6B5E2E`, water `#384E5F`);
  - the element tints, mixed on the dark page as by day.

  It changes on an open page as the setting changes. The page declares its colour scheme, so the browser's own controls, such as the date and time pickers, follow it. Paper keeps the day's colours.
- **Contrast.** Every ink meets WCAG AA on the page, on each tinted panel and on its card, and each element's ring is 3:1 or more. The foundations suite's contrast audit, which visits every state in both languages, now runs in both themes.
- **Docs.** `docs/Developer/Design-Tokens.md` gives the dark values and their contrast.
- **Tests.** A browser suite for the theme (`theme.test.mjs`):
  - the setting chooses the palette, live;
  - every card takes its element's dark colours;
  - print keeps the day's colours when the screen is dark.
- Version bumped to `0.26.0`; the static assets' cache keys follow it.

## 0.25.0

Stage 5 of the Standard view overhaul (#20), part 1: the chart out of the page, as text and on paper.

### Changed
- **Copy as text**, in the chart's bar and among the commands, copies two lines for notes and messages:
  - the pillars on the chart's cards, in written order, year to hour: `丁卯 癸丑 己丑 壬申`;
  - the birth as entered, its true solar time, and the convention that set the day: `February 4, 1988 · 16:30 · Chengdu · True solar time 15:12:24 · Day changes at midnight`. In the Zi hour it names the convention the chart was read with.

  A message says the text was copied, or that the browser refused. In Finnish the bar's tools now take two rows at desktop widths, as they already did on narrower screens.
- **Print.** The browser's print, or Print among the commands, prints:
  - the chart's name and precision line;
  - the pillars in their element colours, with their arcs and any opened hidden stems;
  - any open topic, below the chart at the page's width.

  The controls and the page's tone are left out. A Zi-hour chart prints its convention as text, and a heading moves to the next page with what it heads.
- On paper, the arcs' rows are laid out as ordinary grid items: paged, Chromium does not place an absolutely placed grid item in its area.
- **Docs.** New `docs/Standard-Copy-and-Print.md`.
- **Tests.** A browser suite for the output (`output.test.mjs`). The copied text is checked against the API and the screen, in both languages and both Zi conventions. The printed layout, the arcs on paper, a refused copy and the commands are checked too. Each of four faults put in fails at least one of its tests:
  - pillars copied hour first;
  - the default convention named for every chart;
  - the panel left as a sheet on paper;
  - the arcs' rows left absolutely placed.
- Version bumped to `0.25.0`; the static assets' cache keys follow it.

## 0.24.0

The Standard view: the panel points at the chart. A follow-up to #19, suggested while reviewing its last part.

### Changed
- **Each line in the panel points at the chart.** A page still highlights all its evidence at once, and now each line in it rings its own part, with a dark ring:
  - a stem, its card;
  - a hidden stem, its branch's card, and its row where hidden stems show;
  - a relationship, its cards and its arc;
  - a role or a group of roles, every place it occurs;
  - a stem's roots control, the roots it leads to.
- **When it rings:**
  - after the pointer rests on a line for half a second; while a ring shows, the next line rings at once, and the ring goes shortly after the pointer leaves every line;
  - for as long as a click or tap keeps it, on a line that leads nowhere else. This serves touch, which has no hover, and a pointer that moves over to the chart to look closer. A second click lets it go. A control keeps its own action;
  - at once, while a control in the panel has keyboard focus.
- Meanwhile the page's other outlines step back and the other arcs fade. The ring is 2px of ink, within half the gap between stacked cards. Nothing moves, opens, turns or changes colour.
- A line may name only what the chart shows; each page checks this as it is built. A page closed or redrawn takes its rings with it.
- **Docs.** `docs/Standard-Day-Master-Context.md` describes the rings; the Roles, Relationships and Keyboard pages and the design tokens add their parts.
- **Tests.** A browser suite for the pointing (`pointing.test.mjs`) checks:
  - the half second, and the quick switch after it;
  - what every kind of line rings, from the API's records;
  - keeping by click, tap and focus;
  - that nothing moves.

  Each of seven faults put into the pointing fails at least one of its tests: no half second, no quick switch, nothing kept, a hidden stem without its row, a ring past half the gap, focus that rings nothing, a ring left behind a closed page.
- Version bumped to `0.24.0`; the static assets' cache keys follow it.

## 0.23.0

Stage 4 of the Standard view overhaul (#19), part 5: what the panel says. This completes #19.

### Changed
- **Roles is a matrix.** Each role stands in its group, with a mark in two columns, the visible stems and the hidden stems: a filled dot where it is visible, a ring where it is hidden, a small dot where it is not. The marks are drawn, not typed.
  - Each group shows its element's colour beside its name, on one line.
  - A role the chart lacks is set in the secondary ink and can still be chosen.
  - Screen readers still hear each role's state in words.
  - The Finnish column headings, "Näkyvissä" and "Piilossa", take the words of the existing presence states.
- **A stem in the panel is a line of text**, with its element's colour, not a box outlined like an input field. The outlines stay on the chart.
- **Nothing is said twice.**
  - A role's page names the role once, in its title, not again under each occurrence.
  - Each occurrence's pillar stands beside it, not over it.
  - The season page no longer stacks "Month branch composition" over "Month".
  - A visible stem no longer says Visible under Visible stems.
- **Every page reads from the left**, as the list of relationships already did. It ends with one note in one style, of about 60 to 75 characters to the line where the panel has room: 66 to 69 on average on a sheet 1024px wide, and never more than 75. When a page has nothing to list, it says so in running text, not in the style of a note.
- **One style for the pillars' names**: the panel writes them in the capitals of their column headers. Page titles keep the detail heading's size in the narrow panel.
- **Docs.** `docs/Standard-Roles.md`, `docs/Standard-Day-Master-Context.md` and `docs/Developer/Design-Tokens.md` describe the panel's pages.
- **Tests.** A browser suite for the panel (`panel.test.mjs`) checks:
  - the matrix and its marks;
  - rows without boxes;
  - no repeated names and no stacked labels;
  - the notes' alignment, style and line length;
  - the pillars' names.

  Every test in it fails on the previous version.
- Version bumped to `0.23.0`; the static assets' cache keys follow it.

## 0.22.0

Stage 4 of the Standard view overhaul (#19), part 4: the chart by keyboard.

### Changed
- **The cards take one tab stop**, the card used last or the hour stem on a new chart. Left and Right move along the pillars, Up and Down between stem and branch; the arrows stop at the edges and do not scroll the page.
- **Enter or Space** opens and closes a branch's hidden stems, as a click does. **T** turns the card with focus to its Ten Gods and back, as a long press does, once even when held.
- **A hint above the card with keyboard focus** says its keys, and a ring inside the card's edge shows the focus.
- **For screen readers**, a branch card is a button with `aria-expanded` and a stem card a group, each named by its pillar and the side it shows; the pillars are a group described by the keys.
- **`?` lists the keys** in a dialog while focus is on the chart (WCAG 2.1.4).
- **⌘K or Ctrl+K opens the commands**: the topics, each relationship, role page and pillar's changes, the display, the other language, the Evolution view, Copy link, Edit, New chart, Close and Keys. Words narrow them; a topic opens in one step of the history.
- **Escape in a dialog** closes the dialog only, and focus returns.
- `docs/Standard-Keyboard.md` describes the keys.
- **Tests.** A browser suite for the keyboard (`keyboard.test.mjs`); in WebKit it steps with Option+Tab, as Safari does without Full Keyboard Access. The suites' `settled()` counts a transition that the next change interrupts as done.
- Version bumped to `0.22.0`; the static assets' cache keys follow it.

## 0.21.0

Stage 4 of the Standard view overhaul (#19), part 3: chart links.

### Changed
- **Each chart has an address of its own.** It names the chart on screen, its open topic and its display, in the address's fragment (`#chart?date=…&time=…&place=…&city=…&latitude=…&longitude=…&timezone=…&lang=…`, then `zi`, `display` and `topic` where they differ from a new chart's), which browsers never send to the server. A topic is named down to its page, such as `roles/direct_wealth/stem/hour` or `relationships/stem_combination:4:year-hour`.
- **Opening a link** — a reload, another tab, or someone else's browser — fills the form with its birth and opens the chart at its topic and display, in the link's language.
- **Back and Forward** step through new charts, topics, Edit and New chart; Back from a chart returns to the form with its birth. The language, the Zi-hour convention and the display replace the current entry. A chart reached through the history is calculated again, and only the latest step's chart is drawn.
- **A link that opens no chart says why**, naming the part that is missing or not valid, and the address becomes the form's; a valid birth waits in the form.
- **Copy link**, in the bar, copies the address. A message over the foot of the page says it was copied, or that the browser refused, and is read out.
- `docs/Standard-Links.md` describes the address.
- **Tests.** A browser suite for chart links (`links.test.mjs`): the address of a new chart, reloads, a new tab in another language, every kind of topic, Back and Forward, Edit and New chart, the entries that settings replace, broken links, a chart that arrives after a later step, and Copy link. `openLink` in `chart-helpers.mjs` opens a link as a new tab would.
- Version bumped to `0.21.0`; the static assets' cache keys follow it.

## 0.20.0

Stage 4 of the Standard view overhaul (#19), part 2: the relationships drawn on the chart.

### Changed
- **Arcs on the chart.** Stem combinations arch above the stems, and branch combinations, clashes and complete frames hang below the branches, each from the middle of its first card to the middle of its last, in the list's lines: solid, dashed for a clash, double for a frame. A frame's middle member has a foot of its own.
  - An arc rises a level for each column it spans, and above every arc it spans or crosses. Four levels hold every combination of four stems or four branches, which a unit test walks through; a chart that needed more would fail visibly.
  - The arcs have rows of their own in the pillar grid, one height each, so the cards stand in the same place whatever the relationships. Real charts have up to seven.
  - The branch arcs' feet reach up to the cards past any opened hidden stems, whose panels cover them. The element tints behind hidden stems are now opaque: the element's colour mixed with the page's tone (`color-mix()`), the same colours as before to within a level.
  - Selecting a relationship darkens its arc and fades the others.
  - With two pillars to a row, on phones, no arcs are drawn; the sheet lists the relationships.
- From 641px wide the pillar headers keep 8px less room below them, since the stem arcs' row keeps its own. Phones are unchanged.
- **Tests.** A browser suite for the arcs (`arcs.test.mjs`) checks each arc's ends, line, feet and level on eight charts at 1440, 1024 and 700px; the chosen arc; the feet behind opened hidden stems; the guard against arcs that would not fit; and, on desktop and mobile, the cards' places with none to seven relationships.
- Version bumped to `0.20.0`; the static assets' cache keys follow it.

## 0.19.0

Stage 4 of the Standard view overhaul (#19), part 1: the chart becomes a workbench. One bar above it, and a panel that explains the chosen topic beside it.

### Changed
- **One bar above the chart** replaces the rows of controls around it. On the left: the chart's date, time, place and true solar time. On the right:
  - a display switch, Characters | Ten Gods | Hidden stems (Merkit | Kymmenen jumalaa | Piilorungot), for every card at once. It replaces Show/Hide Ten Gods;
  - the view, Standard | Evolution. Evolution opens the explorer for this chart's birth, so the landing page no longer asks for a view before there is a chart;
  - FI | EN, which asks for the same chart again in the other language and keeps its display;
  - Edit, which returns to the form with the birth kept and replaces the Back button below the chart, and New chart, which returns to an empty form.
- **The topics in one row above the pillars**: the Day Master, its season, roots and roles, and Relationships (with their number), as buttons rather than the page's faintest text.
- **A panel explains the chosen topic.** From 1200px wide it stands beside the chart, 420px wide, and scrolls on its own. The chart moves over once, when the panel first opens, and keeps its width from 1436px. Narrower, the panel is a sheet over the foot of the page, at most half the screen tall, and the chart keeps room to scroll clear of it. Close, Escape or the topic's own button closes it; the Clear button inside each detail is gone. At 1440×900 every topic's highlighted cards and its explanation are on screen together.
- **Relationships** list in the panel, so their number no longer moves the pillars.
- **Hidden stems join the flow** as a shared row of the pillars' grid: an opened panel moves what follows down instead of hanging over it. The room kept below the pillars and the Back button at the bottom are gone.
- **Pillar names**: each column header pairs the plain name with the poetic one ("HOUR" over "Action gate"). Everywhere else the plain names come in the chart's order (Hour, Day, Month, Year): "Hour–Year · Stem combination", "Year · 丁卯 Ding Mao".
- **A card turns after half a second held**, not one. Under the mouse, a hint above the card says so ("Press and hold: Ten Gods"). A card turned or opened by hand makes the display switch read mixed; pressing its choice again applies it to every card.
- **While the chart is asked for again** (in the other language, or under the other Zi-hour convention), it takes no other clicks.
- On phones the bar's tools read from the left, the display switch spans the width, and the pillars stay two to a row.
- **Tests.**
  - A browser suite for the workbench (`workbench.test.mjs`) checks the acceptance at 1440×900, the one move of the chart, the sheet, the display switch, the half-second hold and its hint, the language switch, Edit and New chart, and the pillar names.
  - The design-system suite checks that opened hidden stems share a row and cover nothing, and that no text on a card or in its hidden stems is clipped or broken inside a word, in any display, from 320 to 1440px, in both languages.
  - The browser suites retry a chart request only when a pooled connection resets before any response.
- Version bumped to `0.19.0`; the static assets' cache keys follow it.

## 0.18.0

Stage 3 of the Standard view overhaul (#18): spacing, type and ink on scales, and one grid for all four pillars.

### Changed
- **Tokens.** Every colour, space, font size and tracking in `style.css` comes from tokens defined once on `:root`. A unit test fails on any raw spacing, font size, tracking or ink value outside them. `docs/Developer/Design-Tokens.md` lists the tokens and their uses, with a specimen.
  - **Space**: one 4px scale, `--space-1` to `--space-8` (4 to 64px). Spacing that was 2, 3, 5, 6, 9, 10, 14, 18, 20, 28, 36, 40, 44 or 56px is rounded onto it. The `-8px` margin patch under the chart header is gone.
  - **Type**: six sizes, `--text-1` to `--text-6` (13, 15, 18, 22, 32 and 52px), where there were fourteen (11 to 52px). Nothing that is read is smaller than 13px, and weight 300 is no longer used below display sizes. Three trackings in em (text, capitals, the eyebrow) replace ten values.
  - **Ink**: `--ink-1` to `--ink-3`, `--line-1` and `--line-2`, `--surface-1` to `--surface-3` and a few more replace ink written out as `rgba()` with eleven alphas. The two near-identical secondary greys are now one, the darker, so every text keeps WCAG AA.
- **One grid for the pillars.** The four pillars share row tracks (label, name, mark, stem, branch) through CSS subgrid, so their rows line up and the cards of a row share one height, front and back.
  - A Finnish label that wraps ("SISÄINEN VUODENAIKA") no longer drops its column's cards.
  - With Ten Gods on, the branch cards are one height instead of 205, 187, 187 and 180px.
- **Room for the hidden stems.** The 110px kept below the pillars is now derived from the tallest hidden-stem panel (three rows) through tokens: 120px.
- **Tests.** A browser suite checks that:
  - the rows line up from 641 to 1440px, in both languages, front and back;
  - the branch chevron clears its card's text;
  - the room below the pillars holds the tallest panel.

  The location list's offset below its field is now read from the spacing token.
- Version bumped to `0.18.0`; the static assets' cache keys follow it.

## 0.17.0

Stage 2 of the Standard view overhaul (#17): the chart shows what the engine knows, and nothing that contradicts it.

### Added
- **Each pillar's own name**: above each pillar, its characters and pinyin (丁卯 Ding Mao) replace the raw Gregorian value, which contradicted the pillar near a boundary. The canonical chart (1988-02-04 16:30, Chengdu) showed "1988" over 丁卯, six hours before Lichun.
- **The characters on the cards**: each card's stem or branch is its main glyph, and the gua lines are secondary. The characters come from a self-hosted subset of Noto Serif TC holding only the 22 stems and branches (SIL OFL 1.1; provenance and licence in `static/fonts/`). Every font stack names it, so they look the same wherever they appear.
- **True solar time**: the header gives the true solar time the day and hour pillars are read from, and its offset from clock time ("True solar time 15:12:24 · 1 h 17 min 36 s behind clock time"), with its date when that differs. The header itself is built on the client from the birth as entered, in the page's language (Finnish writes 16.30); `chart.header` is unchanged in the API.
- **Pillar changes in the engine**: every pillar reports when it last changed before the birth and when it next changes, as `four_pillars.<pillar>.changes.previous` and `.next`. Each gives the elapsed seconds (TT), the pillar on the far side, and the solar term (year, month) or the clock and its reading (day, hour). Day and hour changes follow the clocks the conventions choose, including daylight-saving jumps, and each is confirmed against the engine's own rules. See `conventions-and-output.md`.
- **Marks and exact changes**: a pillar at most 30 minutes from a change is marked beneath its name ("changed 12 min 24 s ago"). Pressing a pillar's name opens its exact changes: the distance to a tenth of a second, the term or the clock, and the pillars on either side.
- **Zi-hour conventions**: where the birth falls in the Zi hour and the two conventions give other pillars, the header offers both, with the chart's own pressed. Choosing the other redraws the whole chart under it (Day Master, Ten Gods, roots, relationships, roles), for that chart only.
- **Notices**: `high_latitude_warning` and `solar_term_ambiguous` are shown when true.

### Changed
- **Precision data is checked before a chart is shown**: an unreadable true solar time, missing or contradictory pillar changes, or flags that contradict the chart stop it, and the form says why.
- **Regression fixture**: gains the four `changes` blocks, each checked against an independent value (`lunar-python` for the terms, a bisection of true solar time for the clocks); otherwise only `engine.version` changes.
- The pillar changes add about 11 ms to a chart.
- New tests: `test_pillar_changes` in the core-engine gate, and an engine-truth browser suite. The browser foundations audits now require the stems and branches to be drawn from the page's own font, and walk the new details, a Zi-hour chart and a high-latitude chart.
- Version bumped to `0.17.0`; the static assets' cache keys follow it.

### Fixed
- The 0.16.1 notes gave the seed kernel's difference from `lunar-python` as a median of 120 s and up to 494 s. Measured again, it is 119 s and 496 s.

## 0.16.1

The engine computes solar terms with the models it reports (#24). The month and year pillars change at the right instants; they were up to 8 minutes off.

### Fixed
- **Solar terms up to 8 minutes off**: the engine evaluated a 6-term seed of VSOP87D and a 4-term nutation series, while reporting `VSOP87D_full_Earth` and `IAU_2000A`. Its jie differed from `lunar-python` by a median of 120 s and up to 494 s (1950-2100), and from the Hong Kong Observatory by −358 s to +328 s. A birth within that margin of a jie could get the wrong month pillar, and at Lichun the wrong year pillar. The engine now evaluates:
  - all 2,425 terms of VSOP87D for the Earth, from IMCCE's published `VSOP87D.ear`;
  - IAU 2000A nutation with the IAU 2006 adjustments: 1,358 and 1,056 terms, IERS Conventions 2010 Tables 5.3a/b. `engine.nutation_model` reads `IAU_2000A_R06`;
  - the FK5 correction of Meeus eq. 32.3.
- **Equinox of date**: VSOP87D carries positions to the date with the IAU 1976 rate of precession (Bretagnon & Francou 1988), but the engine's obliquity and nutation belong to the IAU 2006 precession. Longitudes now refer to the IAU 2006 equinox of date (new decision D-007b; new `engine.precession_model: IAU_2006`). Without this change, the jie drifted by 0.3″ a century against both references: +3 s in the 1950s, −8 s by 2100.
- **Checked against references**:
  - All 240 Hong Kong Observatory terms, 2019-2028, fall within 30.9 s of the published minute; 238 of them round to it.
  - Every jie 1950-2100 is within 2.7 s of `lunar-python` (median 0.6 s).
  - Meeus's Example 25.b is reproduced to 0.0012″. The engine was 3.0″ off.
- The equation of time refers the mean Sun to the same equinox as the true Sun. It had missed the FK5 correction. True solar time moves by 0.006 s.
- **Regression fixture** (1988-02-04, Chengdu): the pillars are unchanged.
  - Lichun 1988 moves from 14:42:08 to 14:42:49.5 UTC. The year and month boundary distances change from 22328.3 s to 22369.5 s. `lunar-python` puts Lichun 0.44 s earlier in TT.
  - The solar longitude changes from 314.738003° to 314.737513°. `lunar-python` gives 314.737519°.
  - `hour_boundary_proximity_seconds` changes from 744.0 to 744.1. The seed series had moved the Sun 1.76″ in the equation of time, 0.12 s of true solar time.

### Changed
- **Model tables checked at startup**: the app reads VSOP87D and both nutation tables when it starts, and checks each one's SHA-256, term counts and term numbering. An altered or truncated table stops it, where before the results would silently change. The tables ship in the package (`resources/astronomy/*`, with a provenance README), and `.gitattributes` keeps them byte for byte on every checkout.
- **Solar term solving**: each jie is solved once per process and reused, and a chart solves only the four nearest its birth. The first chart in a season takes about 90 ms (at most 140 ms); later charts take about 1 ms. The tables load in about 20 ms.
- **Stricter reference tests**:
  - The HKO check converts the engine's TT instants to UTC; it had compared TT with civil time. It now allows 31.5 s against the published minute, down from 420 s.
  - `lunar-python` covers every jie 1950-2100 in TT.
  - New checks: IMCCE's VSOP87D check values; ERFA's `eraP06e` values for the IAU 2006 precession and obliquity; VSOP87D's precession constant as read from its own series.
- **Docs**: `conventions-and-output.md` describes the models step by step. `validation.md` gives the measured accuracy and the one known residual: the engine's instants lie about 0.85 s after the Observatory's. The J2000 equinox tie (FK5, versus the inertial dynamical equinox of the IAU 2006 framework) is about that size. `flags.model_uncertainty_seconds` (0.5 s from 1972) is below that offset.
- Version bumped to `0.16.1`. Besides the numbers above, the regression fixture changes only in `engine.version`, `engine.nutation_model` and the new `engine.precession_model`.

## 0.16.0

Stage 1 of the Standard view overhaul (#16): defects and polish on the landing page and chart, with the layout unchanged.

### Added
- **Birth dates limited to the engine's scope**: the date field's bounds come from the engine policy (1949-2100, decision D-001) through the template, and the page checks the date and time before any request. A missing or out-of-range value is named in the page language beneath its own field, which is marked invalid and focused; editing clears the message. The engine checks the local date's year, so every local date from 1949-01-01 to 2100-12-31 is accepted in any timezone.
- **Progress while a chart is created**: Create chart reads "Creating chart…" / "Luodaan karttaa…", is disabled and the form is `aria-busy` until the chart shows or fails; a second submit meanwhile is ignored.
- **Tab titles**: the landing page's title follows the chosen language, and an open chart names itself by date, time and place ("February 4, 1988 · 16:30 · Chengdu — BaZi").
- **八 tab icon**: two brush strokes in the page's ink on its cream, as SVG with a 16/32/48 px ICO. `GET /favicon.ico` serves it, so no page load gets a 404 any more (the explorer page included).
- **Foundations browser suite** (`tests/browser/foundations.test.mjs`): fonts and (in Chromium) the font that drew every glyph, WCAG contrast composited through every ancestor, element dots and the expand chevron, highlight geometry, third-party and failed requests, form validation and errors, progress, headings, mode labels, and titles, in English and Finnish, desktop and mobile.

### Changed
- **`POST /api/location_suggest` suggests settlements only**: GeoNames populated places (`PPL*`) and administrative areas (`ADM*`). Airports, glaciers, islands, parks, mountains, whole countries, and results without a feature code are left out: "Helsinki" listed a Svalbard glacier, an island and two airports, and the first match for "Luxembourg" was the country's centre, 16 km from the city. The geocoder is asked for 20 candidates, and `limit` counts settlements. Every city-state has its own settlement entry, so Hong Kong (no country) is still suggested. Name resolution in city/country mode is unchanged.
- **Fonts served by the app**: the page used a render-blocking `@import` from Google Fonts; it now uses the variable Manrope and Cormorant Garamond files the explorer already serves, preloaded, one face per family. The page makes no third-party requests.
- **Contrast meets WCAG AA**: the two greys are AA-verified on the page and all five element-tinted panels (`#675F57`, `#655F58`; field labels, pillar labels and Back were 2.7:1, every 11px note and toggle 4.2:1); card subtitles and qi labels use their full ink; the branch expand chevron rises from 1.4:1 to at least 3:1.
- **Hidden-stem dots show their element**: each is filled with its element's colour and ringed in its ink (3:1 on every surface); they were all near-black at half opacity, 1.27:1 apart.
- Location suggestions hang 6px below their field instead of below the status line, list all eight without an inner scrollbar, and form an ARIA combobox/listbox (`aria-expanded`, `aria-activedescendant`, `aria-selected`). A pointer pick leaves focus in the field. An empty answer reads "No matching places."; an answer without a `suggestions` array is reported as a failed search instead of being treated as empty.
- The three birth-data fields share one height (48px; date and time stood 2px taller) and left-aligned text.
- Each view's visible title is its `h1`; the "Four pillars" eyebrow is a paragraph.
- The mode switch is translated (Standardi / Evoluutio) and set in capitals by CSS; the turned-over Ten Gods toggle reads "Hide Ten Gods" / "Piilota kymmenen jumalaa" instead of "Show characters".
- Back arrows are drawn in CSS: the page fonts have no arrow glyph, so "←" came from a system font.
- Version bumped to `0.16.0` with coordinated static-asset cache keys. Only `engine.version` changes in the numerical regression fixture; icons are included in the package data.

### Fixed
- **Chart failures are reported above the button**: every chart error (API failures, and evidence that fails its consistency checks) replaced the picked place's status line. They now appear in the form's alert region; the place status keeps describing the place. The browser suites that corrupt evidence read the error from the new region.
- Form controls inherit the page fonts: the FI/EN and Standard/Evolution switches and every location suggestion rendered in Arial.
- Card highlights stay within the 4px gap between stacked cards; outlines reached 6px (8px for a complete frame) over the neighbouring card.
- Only branch cards, which open on a click, lift under the pointer; stem cards lifted without a click action.

## 0.15.0

### Added
- **Complete Roles view**: Standard's Support control becomes Roles, showing all ten individual Ten Gods under Companion, Output, Wealth, Authority, and Resource. Group and individual states explicitly distinguish visible only, hidden only, both, and not present.
- **Role occurrence inspection**: selects exact visible stems and hidden-stem rows, with precise source and qi position; absent roles remain inspectable with natal scope stated.
- **Roots for every visible stem**: inspect all four positions, including the separately identified Day Master. A dotted outline marks the inspected stem; solid outlines identify same-element hidden-stem root evidence. Exact character matches and opposite-polarity roots remain distinct.
- **Exact hidden-to-visible links**: character-identical matches link to every visible position, including a separately labeled Day Master match. Same-element opposite-polarity roots are never mislabeled as exact matches.
- **Opt-in role profile API**: independent `include_role_profile` flag with `natal_roles_v1` data, stable within-chart occurrence IDs, complete role groups, visible stems, roots, and exact-match references. Existing API sections, including `day_master_context.support`, are unchanged.
- Finnish/English labels, scoped absence states, nested back/focus navigation, exclusive reading selection, and role-profile consistency checks before chart display.
- Independent-reference API tests and a complete Roles browser suite, sharing the browser harness with the existing context and relationship suites.

### Changed
- Root and natal-occurrence collection are shared by Day Master context and Roles to keep their evidence consistent. Ten Gods always remain relative to the natal Day Master, even when inspecting a different stem.
- No new strength weights, favorability ratings, transformations, production dependencies, or Evolution changes.
- Version bumped to `0.15.0` with coordinated static-asset cache keys. Only `engine.version` changes in the numerical regression fixture.

## 0.14.1

### Added
- **Location browser tests** (`tests/browser/location.test.mjs`): same-name places told apart and the picked one charted and opened in the explorer by its coordinates, stale suggestion answers ignored, a picked place editable and kept when returning from the chart, and explorer links with a partial or doubled place rejected. They run in the existing Chromium/WebKit harness, desktop and mobile; the relationship and Day Master context tests' suggestion stubs now have the coordinates the page sends as `location`.

### Changed
- Version bumped to `0.14.1` so HTML, JavaScript, and CSS use coordinated cache keys, and returning visitors load the fixed location code.
- Updated only the regression fixture's `engine.version` metadata; numerical engine results are unchanged.
- **`POST /api/location_suggest` identifies each place**: every suggestion also carries `region` (the geocoder's first-level region, such as a province or state), `latitude` and `longitude`, and `display` names the region: `Chengdu, Sichuan, China` rather than `Chengdu, China`. Empty parts are left out, so a place without a country reads `Hong Kong`, not `Hong Kong, `. Names repeat even within a region (two places called Chengdu in Sichuan, two in Jiangxi), so the coordinates are what identify a suggestion.
- `resolved_location` (city/country mode of `POST /api/four_pillars` and `POST /api/evolution_explorer`, and `POST /api/location_search`) also reports `region`, `latitude` and `longitude`, so a caller can see which place a name was resolved to. A name still resolves to the first geocoder match in the given country; send `location` to compute for a particular place.

### Fixed
- **The chart is computed for the place picked from the suggestions**: the page sent only the picked place's city and country, and the server resolved that name again to the first geocoder match. Picking the second `Chengdu, China` (in Jiangxi, 115.34° E) silently computed the chart for Chengdu, Sichuan (104.07° E), 45 minutes of true solar time away, which can change the hour pillar: 15:40 on 1988-02-04 is a 申 hour in the Jiangxi Chengdu and a 未 hour in the Sichuan one. The page now sends the picked place's coordinates and timezone as `location`.
- The suggestion list and the selected-place status show each place's coordinates, so places that share a name and region can be told apart.
- A place without a country in the geocoder data, such as Hong Kong, can be charted; the page used to send an empty country, which the API rejected.
- **A picked place can be changed without reloading the page**: the field locked after a pick until the chart's Back button, so a wrong pick could only be undone by reloading. The field now stays editable; editing it drops the pick and searches again, and Create chart is disabled until a place is picked.
- **Back from the chart keeps the picked place**: Back cleared the pick and disabled Create chart, so changing only the date or time meant picking the same place again. The pick now stays, with its status line, and Create chart stays enabled.
- **The evolution explorer computes for the picked place too**: its link carried only the city and country, which the explorer resolved by name again. The link now carries the picked place's `latitude`, `longitude` and `timezone`, and the explorer sends them as `location`. Links with `city` and `country` from before still open, resolved by name as they were.
- The explorer no longer shows its bundled sample chart when a link carries only part of the birth, or none of the place: a link from a Hong Kong pick, which had no country, silently opened the sample chart. Such links, and links that name the place both by coordinates and by city, now show an error; `/explorer/` with no birth at all still shows the sample.
- The evolution explorer page is rendered from a template with versioned asset URLs (`?v=<version>`), like the start page. Its script and data were served with no cache instructions, so after an update a browser could keep running the cached old explorer. The page is served at `/explorer/`; `/explorer/index.html` no longer exists.
- **Location suggestions only ever list results for the current input**: responses were applied in the order they arrived, so a slow response for a partial query could replace the list for the full query. Typing `Chengdu` could list `Zhengzhou, China` first (the top result for `Che`, `Chen` and `Cheng`), and picking the top entry gave the wrong birthplace, longitude and true solar time. A lookup is now cancelled as soon as the input changes, and a response for anything other than the current input is discarded.
- The previous list is hidden as soon as the input changes, so Enter or a click can no longer pick a result for an earlier query while the new lookup runs.
- Clearing the input or choosing a city cancels the pending lookup, which could otherwise reopen the list or replace the status. A cancelled lookup is never reported as an error; a failure of the current lookup still is.

## 0.14.0

### Added
- **Day Master context in Standard mode**: a restrained summary beneath the date with Month, Roots, and Support controls. Details show the resolved solar month's traditional group and branch composition, exact same-element hidden-stem roots, and visible/hidden Companion and Resource occurrences.
- **Precise evidence highlights**: participating cards and the matching hidden-stem rows are outlined without changing natal colors, card geometry, flip state, or open panels. Context and relationship details are mutually exclusive.
- **Day Master context API**: independent `include_day_master_context` enrichment with explicit `natal_presence_v1` policy. Root matches distinguish exact stems from opposite polarity; Resource is separate, and the Day Master itself is excluded from Companion occurrences.
- Finnish/English context labels, keyboard controls, focus return, live announcements, reduced-motion support, and explicit absence states.
- Reference-based API tests, real-API desktop/mobile browser coverage, and user/API documentation.

### Fixed
- Escape dismisses the active reading even when pointer activation leaves keyboard focus outside the chart (including WebKit).
- Missing or inconsistent context, hidden-stem composition, or highlight surfaces stop chart creation visibly rather than showing contradictory evidence.

### Changed
- Version bumped to `0.14.0` so HTML, JavaScript, and CSS use coordinated cache keys.
- Updated only the regression fixture's `engine.version` metadata. Numerical engine results, dependencies, and Evolution definitions/inference are unchanged.
- Seasonal groups and month-branch composition are displayed separately. No overall-strength, favorability, transformation, or within-month governing-qi assessment is introduced.

## 0.13.0

### Added
- **Natal relationships API**: `POST /api/four_pillars` accepts `include_interactions`, independently of all other enrichments. It returns every occurrence of the five stem combinations, six branch combinations, six branch clashes, and four complete three-harmony frames, including repeated and non-adjacent matches.
- **Standard-mode relationship strip**: selecting an entry outlines the participating cards without moving the pillars or changing their element colors. Details below the chart show identities, natal elements, Ten Gods, and every hidden-stem role. Solid, dashed, and double line styles distinguish pairs, clashes, and complete frames without good/bad color coding.
- **Chart-wide Ten Gods toggle**: turn all cards together while retaining individual long presses and branch-panel clicks/taps. Mixed card states are exposed accessibly.
- Keyboard selection, Escape/clear focus return, screen-reader announcements, reduced-motion support for new controls, and Finnish/English relationship labels.
- Independent reference tests for relationship recognition and API compatibility; API CI includes the new suite. A Node/Playwright browser harness covers desktop/mobile interaction and layout regressions using explicitly configured existing tooling.
- Relationship policy, API contract, and browser-test documentation.

### Changed
- Version bumped to `0.13.0`, including static-asset cache keys.
- Updated only the regression fixture’s `engine.version` metadata; every other engine output field is unchanged.
- Standard explicitly distinguishes detected presence from transformation: complete frames require all three members; partial frames are not emitted; transformation is never asserted. Potential elements are shown only for stem combinations and complete frames.
- The shared Evolution catalog remains unchanged; Standard does not use its nearest-pair selection or inference.

## 0.12.0

### Added
- **Ten gods API enrichment**: `POST /api/four_pillars` accepts `include_ten_gods` and returns a `ten_gods` section with the ten god of each pillar's stem and of every hidden stem, relative to the Day Master (the day stem itself is `day_master`).
- **Ten gods chart interaction**: holding any chart card for one second flips it to its ten god; branch cards list the ten gods of all hidden stems with their qi type, in the same format as the hidden stems panel. Holding again flips the card back.
- **Ten gods mapping loader** (`eight_characters/ten_gods.py`): `ten-gods.csv` is now the runtime source. It is validated at startup, and every cell must agree with the element-cycle derivation in `evolution.primitives.ten_god_index`.
- **Ten gods test suite** (`tests/test_api_ten_gods.py`): checks the mapping against `evolution.primitives.ten_god_index` and the `lunar-python` reference, pins the canonical 1988-02-04 chart through the API, and compares the ten gods for 300 random `lunar-python` charts with `lunar-python`'s own.
- **Index route test** (`tests/test_api_index_route.py`).
- Ten god names in `localization.js` (Finnish and English).

### Changed
- `tzdata` is pinned to `2026.4` (IANA 2026d) and the regression fixture's `engine.tzdb_version` is updated to match. Compared with the fixture's previous `2025.3`, this changes offsets from late 2026 onward in British Columbia, Alberta, the Northwest Territories, Morocco and Western Sahara; in Moldova since 2022; before 1967 in the legacy `EST5EDT`, `CST6CDT`, `MST7MDT` and `PST8PDT` zones; and for one day each in Bogotá (1992) and Tehran (1979).
- `engine.tzdb_version` no longer falls back to `system`; `tzdata` is a required dependency.
- A quick click on a branch card still toggles its hidden stems panel; the release that ends a long press does not.
- Chart cards are no longer text-selectable, so a long press on touch devices flips the card instead of selecting text.
- Version bumped to `0.12.0`.

### Fixed
- **Reproducible timezone conversion**: zones are now loaded only from the pinned `tzdata` package. Previously Python's `zoneinfo` preferred the host's system tz database, so results could differ between machines and `engine.tzdb_version` could name data that was not used (for example, a birth in Inuvik on 2026-12-01 at 12:00 resolved to 19:00 UTC on a host with IANA 2026c, while the reported `tzdata` 2026.4 gives 18:00 UTC).
- Unknown timezone identifiers are rejected with the same error on every host; case-insensitive filesystems no longer accept keys such as `asia/shanghai`.
- The regression-safety gate no longer fails on fresh installs because of an unpinned `tzdata` version.
- `GET /` returned 500 with Starlette 1.x, which removed the `TemplateResponse(name, context)` signature; the index now uses the request-first signature.

## 0.11.0

### Added
- **Hidden stems API** (`POST /api/hidden_stems`): resolves hidden stems (main, middle, residual qi) for each earthly branch in the four pillars, returning enriched data with element, polarity, and qi type.
- **Hidden stems chart interaction**: clicking any branch card in the chart view reveals its hidden stems in a smooth animated panel that slides out below the card.
- **Hidden stems data** (`eight_characters/resources/mappings/hidden-stems.csv`): canonical mapping of all 12 earthly branches to their hidden stem characters.
- **Ten gods data** (`eight_characters/resources/mappings/ten-gods.csv`): reference mapping for ten gods relationships.
- **Hidden stems test suite** (`tests/test_api_hidden_stems_endpoint.py`).
- Element name and qi-type translations in `localization.js` (Finnish and English).

### Changed
- Branch cards in the chart view are now interactive (click to expand/collapse hidden stems).
- Hidden stems panel uses absolute positioning so expanding a panel never shifts the chart, header, or back button.
- Back button positioned with extra clearance to avoid overlap with expanded panels.
- Date input restricted to 4-digit years (`max="9999-12-31"`).
- Version bumped to `0.11.0`.

### Fixed
- Chart view pinned to top of viewport (`align-self: flex-start`) so expanding hidden stems only pushes content downward, never upward.

## 0.10.4

Previous release — BaZi Four Pillars chart with location autosuggest, i18n (Finnish/English), Docker/Render deployment, and full astrometric engine.
