// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Today: the day of the chart on screen (docs/Standard-Today.md). Every number the page
// shows is the API's (POST /api/today), asked for with the place and the schools the
// account keeps and, when the chart on screen is saved in a couple, the partner in view.
// The address names the chart, the day, whose day, the partner in view and the topic; a
// step replaces it and a topic adds to it; late answers are dropped.
import {
  assert, describe, it, engineName, profiles, openLink, settled, withPage, playwright, HELSINKI,
} from './chart-helpers.mjs';
import { newAccount, asAccount, signInPage, stubTurnstile } from './account-helpers.mjs';
import { dialogOpens, signInThroughDialog } from './account-page.mjs';

// A made-up birth, of nobody: the luck suites' sample, 14 August 1975, 07:45, Helsinki.
const CHART = { date: '1975-08-14', time: '07:45', gender: 'female' };
const chartParams = (parts = {}) => new URLSearchParams({
  date: CHART.date, time: CHART.time, place: HELSINKI.display, city: HELSINKI.city,
  latitude: String(HELSINKI.latitude), longitude: String(HELSINKI.longitude), timezone: HELSINKI.timezone,
  lang: 'en', gender: CHART.gender, ...parts,
});
const todayLink = (parts = {}, chart = {}) => `/#today?${chartParams(chart)}&${new URLSearchParams({ day: DAY, ...parts })}`;
// Noon in Helsinki on the day the suite reads.
const DAY = '2026-10-11';
const NOW = new Date('2026-10-11T09:00:00Z');
const PLACE = {
  name: HELSINKI.display, city: HELSINKI.city, timezone: HELSINKI.timezone,
  latitude: HELSINKI.latitude, longitude: HELSINKI.longitude,
};
// Another made-up birth, named as no one is, so that a name is shown as text.
const PARTNER = {
  name: 'Partner <img src=x onerror=window.__named=1>', date: '1988-11-02', time: '21:05:30',
  place: PLACE, gender: 'male', zi: 'split_midnight',
};
const BANDS = {
  strongly_supportive: 'Strongly supportive', supportive: 'Supportive', mixed: 'Mixed',
  draining: 'Draining', strongly_draining: 'Strongly draining',
};
const score = (value) => new Intl.NumberFormat('en', {
  minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: 'exceptZero',
}).format(value);
const pull = (value) => `${BANDS[value.band]} (${score(value.score)})`;
const ELEMENT_NAMES = { wood: 'Wood', fire: 'Fire', earth: 'Earth', metal: 'Metal', water: 'Water' };
const GOD_NAMES = { useful: 'Useful', favourable: 'Favourable', idle: 'Idle', enemy: 'Enemy', unfavourable: 'Unfavourable' };
const godLine = (gods, god) => `${GOD_NAMES[god]}: ${ELEMENT_NAMES[gods[god]]}`;
// Where the pull's scale puts a score: -3.5 at the left end, +3.5 at the right.
const scaleAt = (value) => `${(50 + (value / 3.5) * 50).toFixed(2)}%`;
// A place whose clocks skipped a day: Apia, on 30 December 2011.
const APIA = { name: 'Apia, Samoa', city: 'Apia', timezone: 'Pacific/Apia', latitude: -13.833, longitude: -171.767 };
// A card's lines as the answer writes them: L a whole line, B a broken one.
const linesOf = (card) => card.locator('.gua > *').evaluateAll((lines) => lines.map((line) => line.className));

// The chart on screen as the library keeps it.
const SELF = { date: CHART.date, time: CHART.time, place: PLACE, gender: CHART.gender, zi: 'split_midnight' };
// The account's settings, changed from the page as Settings changes them: where you are
// and, with a partner, the chart on screen and the partner saved as a couple. Every
// chart saved before is removed first.
async function setSettings(page, { place = PLACE, partner = null } = {}) {
  const statuses = await page.evaluate(async ({ place, partner, self }) => {
    const write = async (method, path, body) => {
      const read = await (await fetch('/api/account/settings')).json();
      const response = await fetch(path, {
        method, headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...body, key: read.key, updated_at: read.updated_at }),
      });
      return { status: response.status, value: await response.json() };
    };
    const results = [];
    for (const chart of (await (await fetch('/api/account/settings')).json()).charts) {
      results.push((await write('DELETE', `/api/account/charts/${chart.id}`, {})).status);
    }
    results.push((place === null ? await write('DELETE', '/api/account/place', {}) : await write('PUT', '/api/account/place', { place })).status);
    if (partner !== null) {
      const mine = await write('POST', '/api/account/charts', self);
      results.push(mine.status);
      results.push((await write('POST', '/api/account/charts', { ...partner, couple_with: mine.value.saved })).status);
    }
    return results;
  }, { place, partner, self: SELF });
  assert.ok(statuses.every((status) => status === 200 || status === 201), statuses.join());
}
// A second partner of the chart on screen, saved, and its couple as #96's release keeps
// it: this release reads a chart in several couples and cannot pair one yet, so every
// settings answer of this account gets the couple added. With `problem`, the second
// partner's chart no longer charts. The ids: the chart's own, its first partner's and the
// second's.
const SECOND = { ...PARTNER, name: 'Second partner', date: '1979-03-21', time: '06:10' };
async function keepSecondCouple(page, { problem = null } = {}) {
  const ids = await page.evaluate(async (second) => {
    const read = await (await fetch('/api/account/settings')).json();
    const reply = await fetch('/api/account/charts', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...second, key: read.key, updated_at: read.updated_at }),
    });
    const [mine, first] = read.couples[0].charts;
    return { mine, first, second: (await reply.json()).saved };
  }, SECOND);
  await page.route('**/api/account/settings', async (route) => {
    if (route.request().method() !== 'GET') return route.fallback();
    const response = await route.fetch();
    const value = await response.json();
    // Another account's settings are left as they are.
    if (!value.charts.some((chart) => chart.id === ids.second)) return route.fulfill({ response, json: value });
    const charts = problem === null ? value.charts
      : value.charts.map((chart) => (chart.id === ids.second ? { ...chart, pillars: null, problem } : chart));
    return route.fulfill({ response, json: { ...value, charts, couples: [...value.couples, { id: 'd'.repeat(32), charts: [ids.mine, ids.second] }] } });
  });
  return ids;
}
// Waits until `ready()` holds, for what reaches the server rather than what the page draws.
async function until(page, ready) {
  for (let tries = 0; tries < 200 && !ready(); tries += 1) await page.waitForTimeout(25);
  assert.ok(ready(), 'still not so after 5 s');
}
// Every answer to POST /api/today, the day's own (requests for days are recordDays'),
// with what the page asked; `hold` keeps back the next answer for a day, and with
// `match`, the next one whose request it matches; `pause` keeps back every answer until
// its release.
async function recordToday(page) {
  const answers = [];
  const held = [];
  let paused = null;
  await page.route('**/api/today', async (route) => {
    const response = await route.fetch();
    const entry = { request: route.request().postDataJSON(), payload: await response.json() };
    answers.push(entry);
    if (held.length && held[0].day === entry.request.date && held[0].match(entry.request)) {
      const wait = held.shift();
      await wait.released;
    }
    if (paused !== null) await paused;
    await route.fulfill({ response });
  });
  const hold = (day, match = () => true) => {
    let release;
    const released = new Promise((resolve) => { release = resolve; });
    held.push({ day, match, released });
    return release;
  };
  const pause = () => {
    let release;
    paused = new Promise((resolve) => { release = resolve; });
    return () => {
      paused = null;
      release();
    };
  };
  return { answers, hold, pause };
}
// Every request for days (POST /api/today/days), with what the page asked and, once
// answered, what it was answered; `hold` keeps back the next answer (with `match`, the
// next one whose request it matches), `fail` answers the next request with a status of
// its own, and `tamper` changes the next answer.
async function recordDays(page) {
  const asked = [];
  const holds = [];
  let failing = null;
  let tampering = null;
  await page.route('**/api/today/days', async (route) => {
    const entry = { request: route.request().postDataJSON() };
    asked.push(entry);
    if (failing !== null) {
      const status = failing;
      failing = null;
      entry.payload = null;
      return route.fulfill({ status, json: { detail: 'Stopped by the test.' } });
    }
    const response = await route.fetch();
    let json = await response.json();
    if (tampering !== null) {
      json = tampering(json);
      tampering = null;
    }
    const gate = holds.findIndex((held) => held.match(entry.request));
    if (gate >= 0) await holds.splice(gate, 1)[0].released;
    entry.payload = json;
    return route.fulfill({ response, json });
  });
  return {
    asked,
    hold: (match = () => true) => {
      let release;
      const released = new Promise((resolve) => { release = resolve; });
      holds.push({ match, released });
      return release;
    },
    fail: (status) => { failing = status; },
    tamper: (change) => { tampering = change; },
  };
}
// Every toast the page shows from now on, in turn, as `window.__toasts`.
const recordToasts = (page) => page.evaluate(() => {
  window.__toasts = [];
  new MutationObserver(() => {
    const said = document.querySelector('.toast')?.textContent ?? '';
    if (said !== '' && window.__toasts.at(-1) !== said) window.__toasts.push(said);
  }).observe(document.body, { subtree: true, childList: true, characterData: true });
});
const toastsSaid = (page) => page.evaluate(() => window.__toasts);
// The day the address names, and the carousel's centre.
const dayIs = (page, day) => page.waitForFunction((day) => new URLSearchParams(location.hash.split('?')[1]).get('day') === day, day);
const centreOf = (page) => page.locator('.today-day.is-centre');
// Steps the days `count` times one way by the arrow keys, the days having focus.
async function stepDays(page, count, key = 'ArrowRight') {
  await page.locator('#today-days').focus();
  for (let step = 0; step < count; step += 1) await page.keyboard.press(key);
}
async function shown(page) {
  await page.locator('#today-view').waitFor({ state: 'visible' });
  await page.waitForFunction(() => !document.getElementById('today-view').hasAttribute('aria-busy'));
  await settled(page);
}
const part = (page, name) => page.evaluate((name) => new URLSearchParams(location.hash.split('?')[1] ?? '').get(name), name);

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / today`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 120000 }, () => withPage(profile, run));

    check('Chart · Today opens the day of the chart on screen, every number the API’s', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      await openLink(page, `/#chart?${chartParams()}`, { place: HELSINKI });
      await setSettings(page);
      await page.locator('#page-switch [data-page="today"]').click();
      await shown(page);
      assert.equal(await part(page, 'day'), DAY);
      assert.equal(await part(page, 'date'), CHART.date);
      const { request, payload } = answers.at(-1);
      assert.equal(request.date, DAY);
      assert.equal(request.lang, 'en');
      assert.deepEqual(request.place, PLACE);
      assert.equal(request.chart, 'self');
      assert.equal(request.charts.self.date, CHART.date);
      assert.equal(request.charts.self.gender, CHART.gender);
      assert.equal(request.charts.partner, undefined);
      assert.equal(await page.locator('#today-pull-line').textContent(), `The day: ${pull(payload.layers.day.pull)}`);
      // The run: each day's date, pillar, score and band, as the answer gives them.
      const chips = await page.locator('.today-run-day').evaluateAll((nodes) => nodes.map((node) => ({
        day: node.dataset.todayDay,
        chars: node.querySelector('.today-run-chars').textContent,
        score: node.querySelector('.today-run-score').textContent,
        label: node.getAttribute('aria-label'),
        selected: node.getAttribute('aria-current'),
      })));
      assert.deepEqual(chips.map((chip) => chip.day), payload.run.map((day) => day.date));
      payload.run.forEach((day, index) => {
        assert.equal(chips[index].chars, day.pillar.stem.chinese + day.pillar.branch.chinese);
        assert.equal(chips[index].score, score(day.score));
        assert.ok(chips[index].label.endsWith(`: ${pull(day)}`), chips[index].label);
        assert.equal(chips[index].selected, day.date === DAY ? 'date' : null);
      });
      // The four pillars of the day, each as the chart's cards: each character with its
      // pinyin, in its own element's colours; and its pull.
      for (const layer of ['day', 'month', 'year', 'luck']) {
        const card = page.locator(`.today-pillar[data-layer="${layer}"]`);
        const data = payload.layers[layer];
        assert.ok(data !== null, `the sample has a ${layer} pillar`);
        assert.deepEqual(await card.locator('.today-card-glyph').allTextContents(), [data.pillar.stem.chinese, data.pillar.branch.chinese]);
        assert.deepEqual(await card.locator('.today-card-pinyin').allTextContents(), [data.pillar.stem.pinyin, data.pillar.branch.pinyin]);
        assert.deepEqual(await card.locator('.today-card').evaluateAll((cards) => cards.map((node) => node.classList[2])),
          [data.pillar.stem.element, data.pillar.branch.element]);
        assert.equal((await card.locator('.today-pillar-pull').textContent()).trim(), pull(data.pull));
      }
      assert.equal(await page.locator('#today-pillars-label').textContent(), 'At noon in Helsinki');
      // The relationships with the chart, one item each.
      const all = ['day', 'month', 'year', 'luck'].flatMap((layer) => payload.layers[layer].relationships);
      assert.deepEqual(await page.locator('#today-in-chart .today-relationship').evaluateAll(
        (nodes) => nodes.map((node) => node.dataset.relationship)), all.map((r) => r.id));
      // The hours: twelve rows, each with its branch and call, the Zi hour with its two spans.
      const rows = await page.locator('.today-hours tbody tr').evaluateAll((nodes) => nodes.map((node) => ({
        branch: node.querySelector('th [lang]').textContent,
        times: node.querySelectorAll('td')[0].innerHTML.split('<br>').length,
        call: node.querySelectorAll('td')[2].textContent.trim(),
      })));
      assert.deepEqual(rows.map((row) => row.branch), payload.hours.map((hour) => hour.branch));
      payload.hours.forEach((hour, index) => {
        assert.equal(rows[index].times, hour.spans.length);
        assert.equal(rows[index].call, hour.call === null ? '—' : { protect: 'Protect', mixed: 'Mixed', avoid: 'Avoid' }[hour.call]);
      });
      // No marriage without a partner's chart, and no partner switch.
      assert.equal(await page.locator('[data-today-topic="marriage"]').count(), 0);
      assert.equal(await page.locator('#today-who').isHidden(), true);
      // Chart · Today back on the chart page.
      await page.locator('#today-page-switch [data-page="chart"]').click();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      assert.match(await page.evaluate(() => location.hash), /^#chart\?/);
    });

    check('the date on the clock is read from its parts, even where en-CA writes dates as M/D/YYYY', async (page) => {
      // As a runtime without en-CA's own pattern writes them (#100): like en-US.
      await page.addInitScript(() => {
        const Native = Intl.DateTimeFormat;
        const Wrapped = function DateTimeFormat(locales, options) {
          return new Native(String(locales).toLowerCase() === 'en-ca' ? 'en-US' : locales, options);
        };
        Wrapped.prototype = Native.prototype;
        Wrapped.supportedLocalesOf = Native.supportedLocalesOf.bind(Native);
        Intl.DateTimeFormat = Wrapped;
      });
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      await openLink(page, `/#chart?${chartParams()}`, { place: HELSINKI });
      assert.equal(await page.evaluate(() => new Intl.DateTimeFormat('en-CA', { timeZone: 'UTC' }).format(new Date(Date.UTC(2026, 9, 11)))), '10/11/2026');
      await setSettings(page);
      // Chart · Today opens on the date where you are, and the day knows it is today.
      await page.locator('#page-switch [data-page="today"]').click();
      await shown(page);
      assert.equal(await part(page, 'day'), DAY);
      assert.equal(answers.at(-1).request.date, DAY);
      assert.equal(await page.locator('.today-run-day.is-today').getAttribute('data-today-day'), DAY);
      assert.equal(await page.locator('[data-today-now]').isDisabled(), true);
      // A day on, Today goes back to it.
      await page.locator('.today-step[data-today-step="1"]').click();
      await shown(page);
      assert.equal(await part(page, 'day'), '2026-10-12');
      await page.locator('[data-today-now]').click();
      await shown(page);
      assert.equal(await part(page, 'day'), DAY);
    });

    check('a day step replaces the address, a topic adds to it, and Back and reload keep the place', async (page) => {
      await page.clock.setFixedTime(NOW);
      await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      const entries = await page.evaluate(() => history.length);
      await page.locator('.today-step[data-today-step="1"]').click();
      await shown(page);
      assert.equal(await part(page, 'day'), '2026-10-12');
      assert.equal(await page.evaluate(() => history.length), entries, 'a step replaces the entry');
      assert.equal(await page.locator('[data-today-now]').isDisabled(), false);
      await page.locator('#today-topics [data-today-topic="work"]').click();
      await shown(page);
      assert.equal(await part(page, 'topic'), 'work');
      assert.equal(await page.evaluate(() => history.length), entries + 1, 'a topic adds an entry');
      assert.equal(await page.locator('#today-panel').isVisible(), true);
      await page.reload();
      await shown(page);
      assert.equal(await part(page, 'topic'), 'work');
      assert.equal(await page.locator('#today-detail-title').textContent(), 'Work');
      await page.goBack();
      await shown(page);
      assert.equal(await part(page, 'topic'), null);
      assert.equal(await page.locator('#today-panel').isHidden(), true);
      // Today goes back to the day on the clock where you are.
      await page.locator('[data-today-now]').click();
      await shown(page);
      assert.equal(await part(page, 'day'), DAY);
      assert.equal(await page.locator('[data-today-now]').isDisabled(), true);
    });

    check('only the answer to the latest step is drawn', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { hold } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      const release = hold('2026-10-12');
      await page.locator('.today-step[data-today-step="1"]').click();
      await page.locator('.today-step[data-today-step="1"]').click();
      await page.waitForFunction(() => new URLSearchParams(location.hash.split('?')[1]).get('day') === '2026-10-13');
      await page.waitForFunction(() => document.querySelector('.today-run-day.is-selected')?.dataset.todayDay === '2026-10-13');
      release();
      await page.waitForTimeout(500);
      assert.equal(await page.locator('.today-run-day.is-selected').getAttribute('data-today-day'), '2026-10-13');
      assert.match(await page.locator('#today-date').textContent(), /October 13, 2026/);
    });

    check('the keys step the day, go to today and close a topic, only while the page has focus', async (page) => {
      await page.clock.setFixedTime(NOW);
      await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      await page.locator('.today-run-day.is-selected').focus();
      await page.keyboard.press(']');
      await shown(page);
      assert.equal(await part(page, 'day'), '2026-10-12');
      await page.locator('.today-run-day.is-selected').focus();
      // AltGr, as Finnish keyboards type brackets.
      await page.keyboard.press('Control+Alt+[');
      await shown(page);
      assert.equal(await part(page, 'day'), DAY);
      await page.locator('[data-today-topic="health"]').click();
      await shown(page);
      await page.locator('[data-today-topic="health"]').focus();
      await page.keyboard.press('Escape');
      await shown(page);
      assert.equal(await part(page, 'topic'), null);
      await page.locator('.today-run-day.is-selected').focus();
      await page.keyboard.press('?');
      assert.equal(await page.locator('#keys-dialog').isVisible(), true);
      // The day's keys, not the chart's.
      assert.deepEqual(await page.locator('#keys-dialog .key-row').filter({ visible: true }).locator('dd').allTextContents(),
        ['The day before or after', 'Today, where you are', 'On the days: a day back or ahead, the run’s first or last', 'Closes what is open', 'Commands', 'These keys']);
      assert.equal(await page.locator('#keys-dialog .key-note').textContent(),
        'Letter keys work while the page has focus and no field does.');
      await page.keyboard.press('Escape');
      // The commands, too, show over the day: neither dialog lives in the hidden chart.
      await page.keyboard.press('ControlOrMeta+k');
      assert.equal(await page.locator('#command-palette').isVisible(), true);
      assert.ok((await page.locator('#palette-list').textContent()).includes('The day after'));
      // Dialogs fade out (motion.css), so the palette is still drawn for a moment after
      // Escape: it closes, rather than being gone at once.
      await page.keyboard.press('Escape');
      await page.locator('#command-palette').waitFor({ state: 'hidden' });
      // A field's own keys are its own.
      await page.locator('#today-copy-link').focus();
      await page.evaluate(() => document.activeElement.blur());
      await page.keyboard.press(']');
      assert.equal(await part(page, 'day'), DAY, 'nothing on the page has focus');
    });

    check('a topic opened from the keyboard keeps focus on its button, and the keys go on working', async (page) => {
      await page.clock.setFixedTime(NOW);
      await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      await page.locator('#today-topics [data-today-topic="work"]').focus();
      await page.keyboard.press('Enter');
      await shown(page);
      assert.equal(await part(page, 'topic'), 'work');
      assert.equal(await page.evaluate(() => document.activeElement?.dataset.todayTopic), 'work');
      await page.keyboard.press('Escape');
      await shown(page);
      assert.equal(await part(page, 'topic'), null);
      assert.equal(await page.evaluate(() => document.activeElement?.dataset.todayTopic), 'work');
      await page.keyboard.press(']');
      await shown(page);
      assert.equal(await part(page, 'day'), '2026-10-12');
      // A day of the run, chosen from the keyboard, keeps it too.
      await page.locator('.today-run-day[data-today-day="2026-10-14"]').focus();
      await page.keyboard.press('Enter');
      await shown(page);
      assert.equal(await part(page, 'day'), '2026-10-14');
      assert.equal(await page.evaluate(() => document.activeElement?.dataset.todayDay), '2026-10-14');
      // Today, pressed from the keyboard, is then disabled: the day's heading takes focus.
      await page.locator('[data-today-now]').focus();
      await page.keyboard.press('Enter');
      await shown(page);
      assert.equal(await part(page, 'day'), DAY);
      assert.equal(await page.locator('[data-today-now]').isDisabled(), true);
      assert.equal(await page.evaluate(() => document.activeElement?.id), 'today-date');
      await page.keyboard.press(']');
      await shown(page);
      assert.equal(await part(page, 'day'), '2026-10-12');
    });

    check('Chart · Today hands the focus across, so each page’s keys act at once', async (page) => {
      await page.clock.setFixedTime(NOW);
      await recordToday(page);
      await openLink(page, `/#chart?${chartParams()}`, { place: HELSINKI });
      await setSettings(page);
      await page.locator('#page-switch [data-page="today"]').focus();
      await page.keyboard.press('Enter');
      await shown(page);
      await page.waitForFunction(() => document.activeElement?.matches('#today-page-switch [data-page="today"]'));
      await page.keyboard.press(']');
      await shown(page);
      assert.equal(await part(page, 'day'), '2026-10-12');
      await page.locator('#today-page-switch [data-page="chart"]').focus();
      await page.keyboard.press('Enter');
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await page.waitForFunction(() => document.activeElement?.matches('#page-switch [data-page="chart"]'));
      await page.keyboard.press('?');
      assert.equal(await page.locator('#keys-dialog').isVisible(), true);
      assert.equal(await page.locator('#keys-dialog .key-row-chart').first().isVisible(), true);
    });

    check('the day in another language opens the chart in it', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      await page.locator('#today-language [data-today-lang="fi"]').click();
      await shown(page);
      assert.equal(await part(page, 'lang'), 'fi');
      assert.equal(answers.at(-1).request.lang, 'fi');
      await page.locator('#today-page-switch [data-page="chart"]').click();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await page.waitForFunction(() => !document.getElementById('chart-view').hasAttribute('aria-busy'));
      assert.equal(await part(page, 'lang'), 'fi');
      assert.equal(await page.evaluate(() => document.documentElement.lang), 'fi');
    });

    check('until its answer is drawn, a day is neither copied as text nor printed, and then its own text is', async (page) => {
      await page.clock.setFixedTime(NOW);
      await page.addInitScript(() => {
        window.__copied = [];
        Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async (text) => { window.__copied.push(text); } } });
      });
      const { answers, hold } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      assert.equal(await page.locator('#today-copy-text').getAttribute('aria-disabled'), 'false');
      const release = hold('2026-10-12');
      await page.locator('.today-step[data-today-step="1"]').click();
      await page.waitForFunction(() => new URLSearchParams(location.hash.split('?')[1]).get('day') === '2026-10-12');
      assert.equal(await page.locator('#today-copy-text').getAttribute('aria-disabled'), 'true');
      assert.equal(await page.locator('#today-print').getAttribute('aria-disabled'), 'true');
      // Pressed anyway: the button says it is unavailable, and copies nothing.
      await page.locator('#today-copy-text').click({ force: true });
      assert.deepEqual(await page.evaluate(() => window.__copied), [], 'nothing is copied while the day is on its way');
      release();
      await shown(page);
      assert.equal(await page.locator('#today-copy-text').getAttribute('aria-disabled'), 'false');
      await page.locator('#today-copy-text').click();
      await page.waitForFunction(() => window.__copied.length === 1);
      const copied = await page.evaluate(() => window.__copied[0]);
      const { payload } = answers.at(-1);
      assert.equal(payload.date, '2026-10-12');
      assert.ok(copied.startsWith('Monday, October 12, 2026'), copied);
      const day = payload.layers.day;
      assert.ok(copied.includes(`${day.pillar.stem.chinese}${day.pillar.branch.chinese} ${day.pillar.stem.pinyin} ${day.pillar.branch.pinyin} · ${pull(day.pull)}`), copied);
      // After the pull line, the five gods with their elements.
      const lines = copied.split('\n');
      const gods = ['useful', 'favourable', 'idle', 'enemy', 'unfavourable'].map((god) => godLine(payload.favourable.gods, god)).join(' · ');
      assert.equal(lines[lines.indexOf(`The day: ${pull(day.pull)}`) + 1], gods);
    });

    check('an answer the page cannot draw is neither copied as text nor printed', async (page) => {
      await page.clock.setFixedTime(NOW);
      await page.addInitScript(() => {
        window.__copied = [];
        window.__printed = 0;
        Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async (text) => { window.__copied.push(text); } } });
        window.print = () => { window.__printed += 1; };
      });
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      // A relationship with a member in the luck pillar on a day with none: the answer
      // passes its check, and In your chart cannot draw it.
      await page.route('**/api/today', async (route) => {
        const response = await route.fetch();
        const value = await response.json();
        value.layers.luck = null;
        value.layers.day.relationships.push({
          id: 'drawn-nowhere', kind: 'branch_clash', line: null,
          members: [{ char: '子', pinyin: 'zi', pillar: 'luck' }, { char: '午', pinyin: 'wu', pillar: 'daily' }],
        });
        await route.fulfill({ response, json: value });
      });
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      assert.match(await page.locator('#today-notice').textContent(), /could not be shown/);
      assert.equal(await page.locator('#today-body').isHidden(), true);
      assert.equal(await page.locator('#today-copy-text').getAttribute('aria-disabled'), 'true');
      await page.locator('#today-copy-text').click({ force: true });
      await page.locator('#today-print').click({ force: true });
      await page.waitForTimeout(100);
      assert.deepEqual(await page.evaluate(() => [window.__copied, window.__printed]), [[], 0]);
    });

    check('a day that cannot be shown leaves nothing of the day before, its topic neither, and Retry asks again', async (page) => {
      await page.clock.setFixedTime(NOW);
      await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink({ topic: 'work' }), process.env.EC_BASE_URL).href);
      await shown(page);
      assert.equal(await page.locator('#today-panel').isVisible(), true);
      const refuse = (route) => route.fulfill({ status: 500, json: { detail: 'Stopped by the test.' } });
      await page.route('**/api/today', refuse);
      await page.locator('.today-step[data-today-step="1"]').click();
      await shown(page);
      assert.equal(await page.locator('#today-notice').textContent(), 'Stopped by the test.Try again');
      assert.equal(await page.locator('#today-body').isHidden(), true);
      assert.equal(await page.locator('#today-panel').isHidden(), true);
      assert.equal(await page.locator('#today-detail').innerHTML(), '');
      await page.unroute('**/api/today', refuse);
      await page.locator('[data-today-action="retry"]').click();
      await shown(page);
      assert.equal(await part(page, 'day'), '2026-10-12');
      assert.equal(await page.locator('#today-body').isVisible(), true);
      assert.equal(await page.locator('#today-detail-title').textContent(), 'Work');
    });

    check('Marriage, open when the partner’s chart is removed elsewhere, closes and the day says why', async (page) => {
      await page.clock.setFixedTime(NOW);
      await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page, { partner: PARTNER });
      await page.goto(new URL(todayLink({ topic: 'marriage' }), process.env.EC_BASE_URL).href);
      await shown(page);
      assert.equal(await page.locator('#today-detail-title').textContent(), 'Marriage');
      await setSettings(page);
      await page.reload();
      await shown(page);
      assert.equal(await part(page, 'topic'), null);
      assert.equal(await page.locator('#today-body').isVisible(), true);
      assert.equal(await page.locator('#today-panel').isHidden(), true);
      assert.equal(await page.locator('[data-today-topic="marriage"]').count(), 0);
      assert.match(await page.locator('#today-notice').textContent(), /not in a couple/);
    });

    check('a chart in several couples, as #96 will keep them: With chooses the partner in view, the address names it, and a chart that is not a partner is never swapped', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers, hold } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page, { partner: PARTNER });
      const ids = await keepSecondCouple(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      // The first couple's partner is in view, and the address says so; With names both,
      // as text, in the order paired.
      assert.equal(await part(page, 'partner'), ids.first);
      assert.equal(await page.locator('#today-partner-choice').isVisible(), true);
      assert.deepEqual(await page.locator('#today-partner option').allTextContents(), [PARTNER.name, SECOND.name]);
      assert.equal(await page.evaluate(() => window.__named), undefined, 'a name is text');
      assert.equal(await page.locator('.today-who-name').textContent(), PARTNER.name);
      assert.equal(answers.at(-1).request.charts.partner.name, PARTNER.name);
      // The second chosen: the address names it, and its couple is the one read.
      await page.locator('#today-partner').selectOption(ids.second);
      await shown(page);
      assert.equal(await part(page, 'partner'), ids.second);
      assert.equal(answers.at(-1).request.charts.partner.name, SECOND.name);
      assert.deepEqual(await page.locator('#today-couple .today-couple-name').allTextContents(), ['This chart', SECOND.name]);
      // An answer for the first partner, still on its way when the second is chosen
      // again, is never drawn.
      const before = answers.length;
      const release = hold(DAY, (request) => request.charts.partner?.name === PARTNER.name);
      await page.locator('#today-partner').selectOption(ids.first);
      await until(page, () => answers.slice(before).some((entry) => entry.request.charts.partner?.name === PARTNER.name));
      await page.locator('#today-partner').selectOption(ids.second);
      await shown(page);
      release();
      await page.waitForTimeout(200);
      assert.deepEqual(await page.locator('#today-couple .today-couple-name').allTextContents(), ['This chart', SECOND.name]);
      assert.equal(await page.locator('.today-who-name').textContent(), SECOND.name);
      // Its day, from its side, keeps it in view.
      await page.locator('#today-who [data-who="partner"]').click();
      await shown(page);
      assert.deepEqual([await part(page, 'who'), await part(page, 'partner')], ['partner', ids.second]);
      assert.deepEqual([answers.at(-1).request.chart, answers.at(-1).request.charts.partner.name], ['partner', SECOND.name]);
      // A link naming a chart that is not one of this chart's partners: never swapped.
      // On this chart's own day the day is read without a couple, and the page says why.
      const stranger = 'f'.repeat(32);
      await page.goto(new URL(todayLink({ partner: stranger }), process.env.EC_BASE_URL).href);
      await shown(page);
      assert.equal(await part(page, 'partner'), stranger);
      assert.equal(answers.at(-1).request.charts.partner, undefined);
      assert.equal(await page.locator('#today-notice').textContent(), 'That chart is not one of this chart’s partners in your account.');
      assert.equal(await page.locator('#today-couple').isHidden(), true);
      assert.equal(await page.locator('#today-partner-choice').isVisible(), true);
      // On the partner's side there is no day to read: This chart goes back to the
      // chart's own day, with its first partner in view.
      await page.goto(new URL(todayLink({ who: 'partner', partner: stranger }), process.env.EC_BASE_URL).href);
      // Its notice, not the one before: only the partner's side offers This chart.
      await page.locator('[data-today-action="self"]').waitFor({ state: 'visible' });
      assert.match(await page.locator('#today-notice').textContent(), /^That chart is not one of this chart’s partners in your account\./);
      assert.equal(await page.locator('#today-body').isHidden(), true);
      await page.locator('[data-today-action="self"]').click();
      await shown(page);
      assert.deepEqual([await part(page, 'who'), await part(page, 'partner')], [null, ids.first]);
      assert.equal(answers.at(-1).request.charts.partner.name, PARTNER.name);
    });

    check('the partner’s day of a chart in no couple, with no partner named, says why and asks for nothing', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink({ who: 'partner' }), process.env.EC_BASE_URL).href);
      await page.locator('[data-today-action="self"]').waitFor({ state: 'visible' });
      assert.match(await page.locator('#today-notice').textContent(), /^This chart is not in a couple: pair it in Settings\./);
      assert.equal(await page.locator('#today-body').isHidden(), true);
      assert.equal(answers.length, 0, 'no day is asked for');
      await page.locator('[data-today-action="self"]').click();
      await shown(page);
      assert.deepEqual([await part(page, 'who'), await part(page, 'partner')], [null, null]);
      assert.deepEqual([answers.at(-1).request.chart, answers.at(-1).request.charts.partner], ['self', undefined]);
    });

    check('the partner in view stays through a choice, the commands, steps, the language, reload and history, and out of the chart’s own link', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page, { partner: PARTNER });
      const ids = await keepSecondCouple(page);
      const read = () => [answers.at(-1).request.chart, answers.at(-1).request.charts.partner?.name];
      // The partner's day with no partner named: the first couple's partner's side, and
      // the address says so.
      await page.goto(new URL(todayLink({ who: 'partner', topic: 'work' }), process.env.EC_BASE_URL).href);
      await shown(page);
      assert.deepEqual([await part(page, 'who'), await part(page, 'partner'), await part(page, 'topic')], ['partner', ids.first, 'work']);
      assert.deepEqual(read(), ['partner', PARTNER.name]);
      // Another partner chosen on the partner's side: that partner's side, the topic
      // left open.
      await page.locator('#today-partner').selectOption(ids.second);
      await shown(page);
      assert.deepEqual([await part(page, 'who'), await part(page, 'partner'), await part(page, 'topic')], ['partner', ids.second, 'work']);
      assert.deepEqual(read(), ['partner', SECOND.name]);
      assert.equal(await page.locator('#today-detail-title').textContent(), 'Work');
      // This chart's own day keeps the partner in view, and the commands offer one
      // partner's day: its own.
      await page.locator('#today-who [data-who="self"]').click();
      await shown(page);
      assert.deepEqual([await part(page, 'who'), await part(page, 'partner')], [null, ids.second]);
      assert.deepEqual(read(), ['self', SECOND.name]);
      await page.keyboard.press('ControlOrMeta+k');
      await page.locator('#command-palette').waitFor({ state: 'visible' });
      const labels = (await page.locator('#palette-list .palette-label').allTextContents()).map((label) => label.trim());
      assert.deepEqual(labels.filter((label) => label === SECOND.name || label === PARTNER.name), [SECOND.name]);
      await page.keyboard.press('Escape');
      // A step, the language, a reload, Back and Forward keep it.
      await page.locator('.today-step[data-today-step="1"]').click();
      await shown(page);
      assert.deepEqual([await part(page, 'day'), await part(page, 'partner')], ['2026-10-12', ids.second]);
      await page.locator('#today-language [data-today-lang="fi"]').click();
      await shown(page);
      assert.deepEqual([await part(page, 'lang'), await part(page, 'partner')], ['fi', ids.second]);
      assert.deepEqual(read(), ['self', SECOND.name]);
      await page.reload();
      await shown(page);
      assert.equal(await part(page, 'partner'), ids.second);
      assert.deepEqual(read(), ['self', SECOND.name]);
      // The chart's own link leaves it out.
      await page.locator('#today-page-switch [data-page="chart"]').click();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      assert.equal(await page.evaluate(() => new URLSearchParams(location.hash.split('?')[1]).has('partner')), false);
      await page.goBack();
      await shown(page);
      assert.equal(await part(page, 'partner'), ids.second);
      assert.deepEqual(read(), ['self', SECOND.name]);
      await page.goForward();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await page.goBack();
      await shown(page);
      assert.equal(await part(page, 'partner'), ids.second);
      assert.deepEqual(read(), ['self', SECOND.name]);
    });

    check('a partner whose chart no longer charts is shown in With but never chosen, and never swapped', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page, { partner: PARTNER });
      const ids = await keepSecondCouple(page, { problem: 'Stopped by the test.' });
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      assert.equal(await part(page, 'partner'), ids.first);
      const options = page.locator('#today-partner option');
      assert.deepEqual(await options.allTextContents(), [PARTNER.name, `${SECOND.name} (cannot be charted)`]);
      assert.deepEqual(await options.evaluateAll((items) => items.map((item) => item.disabled)), [false, true]);
      // Named in the address on this chart's own day: the day without a couple, and why.
      await page.goto(new URL(todayLink({ partner: ids.second }), process.env.EC_BASE_URL).href);
      await shown(page);
      assert.equal(await part(page, 'partner'), ids.second);
      assert.equal(answers.at(-1).request.charts.partner, undefined);
      assert.equal(await page.locator('#today-notice').textContent(), 'The other chart of the couple can no longer be charted: see Settings.');
      assert.equal(await page.locator('#today-couple').isHidden(), true);
      assert.equal(await page.locator('#today-partner-choice').isVisible(), true);
      // On its side there is no day to read, and This chart goes back to the chart's own
      // day with its first partner in view.
      const asked = answers.length;
      await page.goto(new URL(todayLink({ who: 'partner', partner: ids.second }), process.env.EC_BASE_URL).href);
      await page.locator('[data-today-action="self"]').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#today-body').isHidden(), true);
      assert.match(await page.locator('#today-notice').textContent(), /^The other chart of the couple can no longer be charted: see Settings\./);
      assert.equal(answers.length, asked, 'no day is asked for');
      await page.locator('[data-today-action="self"]').click();
      await shown(page);
      assert.deepEqual([await part(page, 'who'), await part(page, 'partner')], [null, ids.first]);
      assert.equal(answers.at(-1).request.charts.partner.name, PARTNER.name);
    });

    check('the partner’s day: the switch carries the name as text, and Marriage reads both charts', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page, { partner: PARTNER });
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      assert.equal(await page.locator('#today-who').isVisible(), true);
      assert.equal(await page.locator('.today-who-name').textContent(), PARTNER.name);
      assert.equal(await page.evaluate(() => window.__named), undefined, 'a name is text');
      assert.equal(answers.at(-1).request.charts.partner.name, PARTNER.name);
      // The partner's birth alone: no library id, no drawn pillars.
      assert.equal(answers.at(-1).request.charts.partner.id, undefined);
      assert.equal(answers.at(-1).request.charts.partner.pillars, undefined);
      // The couple: both pulls of the day, and whether it pulls them apart, as the API says.
      const before = answers.at(-1).payload;
      const sides = await page.locator('#today-couple .today-couple-side').evaluateAll((items) => items.map((item) => [
        item.querySelector('.today-couple-name').textContent, item.querySelector('.today-pillar-pull').textContent.trim(),
      ]));
      assert.deepEqual(sides, [['This chart', pull(before.layers.day.pull)], [PARTNER.name, pull(before.marriage.partner.pull)]]);
      assert.equal(await page.locator('.today-couple-apart').textContent(),
        before.marriage.pull_apart ? 'The day pulls you apart.' : 'The day does not pull you apart.');
      assert.deepEqual(await page.locator('#today-couple .today-scale-marker').evaluateAll((markers) => markers.map((m) => m.style.getPropertyValue('--at'))),
        [scaleAt(before.layers.day.pull.score), scaleAt(before.marriage.partner.pull.score)]);
      await page.locator('[data-today-topic="marriage"]').click();
      await shown(page);
      const marriage = answers.at(-1).payload.marriage;
      assert.match(await page.locator('#today-detail').textContent(), new RegExp(pull(marriage.partner.pull).replace(/[()+]/g, '\\$&')));
      await page.locator('#today-who [data-who="partner"]').click();
      await shown(page);
      assert.equal(await part(page, 'who'), 'partner');
      assert.equal(answers.at(-1).request.chart, 'partner');
      // From the partner's side the couple turns around: the same two pulls, the same flag.
      const turned = answers.at(-1).payload;
      assert.deepEqual(await page.locator('#today-couple .today-couple-side').evaluateAll((items) => items.map((item) => [
        item.querySelector('.today-couple-name').textContent, item.querySelector('.today-pillar-pull').textContent.trim(),
      ])), [[PARTNER.name, pull(turned.layers.day.pull)], ['This chart', pull(turned.marriage.partner.pull)]]);
      assert.deepEqual([turned.layers.day.pull, turned.marriage.partner.pull], [marriage.partner.pull, before.layers.day.pull]);
      assert.equal(turned.marriage.pull_apart, before.marriage.pull_apart);
      assert.match(await page.locator('#today-notice').textContent(), /your partner’s day/);
      // Removed elsewhere: the page says so, and offers the chart's own day.
      await setSettings(page);
      await page.reload();
      await page.locator('#today-notice').waitFor({ state: 'visible' });
      assert.match(await page.locator('#today-notice').textContent(), /not in a couple/);
      await page.locator('[data-today-action="self"]').click();
      await shown(page);
      assert.equal(await part(page, 'who'), null);
      // Without a couple there is none to draw.
      assert.equal(await page.locator('#today-couple').isHidden(), true);
    });

    check('without a place the day says so and leads to Settings; without a gender, to the chart', async (page) => {
      await page.clock.setFixedTime(NOW);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page, { place: null });
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await page.locator('#today-notice').waitFor({ state: 'visible' });
      assert.match(await page.locator('#today-notice').textContent(), /needs where you are/);
      assert.equal(await page.locator('#today-body').isHidden(), true);
      await page.locator('[data-today-action="settings"]').click();
      await page.locator('#settings-view').waitFor({ state: 'visible' });
      assert.equal(await page.evaluate(() => location.hash), '#settings');
      await setSettings(page);
      const link = `/#today?${new URLSearchParams([...chartParams()].filter(([key]) => key !== 'gender'))}&day=${DAY}`;
      await page.goto(new URL(link, process.env.EC_BASE_URL).href);
      await page.locator('#today-notice').waitFor({ state: 'visible' });
      assert.match(await page.locator('#today-notice').textContent(), /gender/);
    });

    check('a link with an unknown, repeated or wrong part is refused, naming it', async (page) => {
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      for (const [link, named] of [
        [todayLink({ day: '2026-02-30' }), 'day'],
        [`${todayLink()}&day=2026-10-12`, 'day'],
        [todayLink({ who: 'self' }), 'who'],
        [todayLink({ partner: 'A'.repeat(32) }), 'partner'],
        [todayLink({ partner: 'f'.repeat(31) }), 'partner'],
        [`${todayLink({ partner: 'f'.repeat(32) })}&partner=${'e'.repeat(32)}`, 'partner'],
        [todayLink({ topic: 'stars' }), 'topic'],
        [todayLink({ luck: '5/stem' }), 'luck'],
        [`${todayLink()}&mood=1`, 'mood'],
      ]) {
        await page.goto(new URL(link, process.env.EC_BASE_URL).href);
        await page.locator('#form-error').waitFor({ state: 'visible' });
        assert.match(await page.locator('#form-error').textContent(), new RegExp(named), link);
        assert.equal(await page.locator('#today-view').isHidden(), true);
      }
    });

    check('in Finnish the day has no readings, and its numbers are written the Finnish way', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink({ topic: 'day' }, { lang: 'fi' }), process.env.EC_BASE_URL).href);
      await shown(page);
      const { request, payload } = answers.at(-1);
      assert.equal(request.lang, 'fi');
      assert.equal(payload.readings, null);
      assert.equal(await page.locator('.today-reading').count(), 0);
      const finnish = new Intl.NumberFormat('fi', { minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: 'exceptZero' })
        .format(payload.layers.day.pull.score);
      assert.ok((await page.locator('#today-pull-line').textContent()).includes(finnish));
      assert.equal(await page.evaluate(() => document.documentElement.lang), 'fi');
    });

    check('printed, the day keeps its run with each band as a word, and loses its controls', async (page) => {
      await page.clock.setFixedTime(NOW);
      await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      await page.emulateMedia({ media: 'print' });
      const printed = await page.evaluate(() => ({
        run: getComputedStyle(document.getElementById('today-run')).display,
        band: getComputedStyle(document.querySelector('.today-run-band')).display,
        tools: getComputedStyle(document.querySelector('#today-view .chart-tools')).display,
      }));
      assert.deepEqual(printed, { run: 'flex', band: 'block', tools: 'none' });
      await page.emulateMedia({ media: 'screen' });
    });

    check('every character the day renders stands with its pinyin', async (page) => {
      await page.clock.setFixedTime(NOW);
      await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink({ topic: 'pillar/luck' }), process.env.EC_BASE_URL).href);
      await shown(page);
      // The canon's own passages are quoted as they are; everything else pairs each
      // character with its pinyin, beside it.
      const lonely = await page.evaluate(() => [...document.querySelectorAll('#today-view [lang="zh-Hant"]')]
        .filter((node) => !node.closest('.today-reading'))
        .filter((node) => {
          const around = (node.parentElement?.textContent ?? '').replace(node.textContent, '');
          return !/[A-Z][a-z]+/.test(around);
        })
        .map((node) => node.textContent));
      assert.deepEqual(lonely, []);
      assert.ok(await page.locator('.today-run-pinyin').count() > 0);
      // And no pinyin has a tone mark.
      const marked = await page.evaluate(() => [...document.querySelectorAll('#today-view :is(.today-pinyin, .today-run-pinyin)')]
        .map((node) => node.textContent).filter((text) => /[\u0300-\u036f]/.test(text.normalize('NFD'))));
      assert.deepEqual(marked, []);
    });

    check('the days: the chosen day in the middle as the chart’s cards, the run’s days beside it, moved by a press and the keys', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      const { payload } = answers.at(-1);
      const at = payload.run.findIndex((day) => day.date === DAY);
      // In the middle, the day as the chart's cards: each character in its own element's
      // colours, with its pinyin and the lines the answer gives it.
      const centre = page.locator('.today-day.is-centre');
      assert.equal(await centre.getAttribute('data-today-pick'), DAY);
      const entry = payload.run[at];
      assert.deepEqual(await centre.locator('.today-card-glyph').allTextContents(), [entry.pillar.stem.chinese, entry.pillar.branch.chinese]);
      assert.deepEqual(await centre.locator('.today-card').evaluateAll((cards) => cards.map((node) => node.classList[2])),
        [entry.pillar.stem.element, entry.pillar.branch.element]);
      assert.deepEqual(await linesOf(centre.locator('.today-card.is-stem')), entry.pillar.stem.lines);
      assert.deepEqual(await linesOf(centre.locator('.today-card.is-branch')), entry.pillar.branch.lines);
      assert.equal((await centre.locator('.today-day-pull').textContent()).trim(), pull(entry));
      // Beside it the run's days, two on either side, one on a phone; they are pictures of
      // the run, which stays the list a screen reader reads.
      const width = profile.name === 'mobile' ? 1 : 2;
      const seen = await page.locator('.today-day').evaluateAll((nodes) => nodes
        .filter((node) => node.checkVisibility({ visibilityProperty: true }))
        .map((node) => [node.dataset.todayPick, Number(node.dataset.place)])
        .sort((a, b) => a[1] - b[1]));
      assert.deepEqual(seen, Array.from({ length: 2 * width + 1 }, (_, i) => [payload.run[at - width + i].date, i - width]));
      assert.equal(await page.locator('.today-day:not(.is-centre)[aria-hidden="true"]').count(), await page.locator('.today-day:not(.is-centre)').count());
      // A press on a neighbour picks it.
      await page.locator('.today-day[data-place="1"]').click();
      await shown(page);
      assert.equal(await part(page, 'day'), payload.run[at + 1].date);
      // The keys move the day only while the days have focus; a held key steps once.
      await page.locator('#today-days').focus();
      await page.keyboard.press('ArrowLeft');
      await shown(page);
      assert.equal(await part(page, 'day'), DAY);
      await page.keyboard.down('ArrowRight');
      await page.keyboard.down('ArrowRight');
      await page.keyboard.up('ArrowRight');
      await shown(page);
      assert.equal(await part(page, 'day'), payload.run[at + 1].date);
      await page.keyboard.press('End');
      await shown(page);
      assert.equal(await part(page, 'day'), answers.at(-2).payload.run.at(-1).date);
      await page.keyboard.press('Home');
      await shown(page);
      const fromEnd = answers.at(-2).payload.run;
      assert.equal(await part(page, 'day'), fromEnd[0].date);
      assert.equal(await page.evaluate(() => document.activeElement?.id), 'today-days');
      // Elsewhere the arrows are not the day's.
      const day = await part(page, 'day');
      await page.locator('.today-run-day.is-selected').focus();
      await page.keyboard.press('ArrowRight');
      assert.equal(await part(page, 'day'), day);
    });

    check('the days follow a drag that started on them, ask once when it is let go, and a drag up or cancelled moves nothing', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      const run = answers.at(-1).payload.run;
      const at = run.findIndex((day) => day.date === DAY);
      const box = await page.locator('.today-day.is-centre .today-cards').boundingBox();
      const x = box.x + box.width / 2;
      const y = box.y + box.height / 2;
      // Dragged left by 1.4 days' width: one day later, and one request.
      const asked = answers.length;
      await page.mouse.move(x, y);
      await page.mouse.down();
      for (const step of [20, 60, 120, 1.4 * box.width]) await page.mouse.move(x - step, y + 3);
      await page.mouse.up();
      await shown(page);
      assert.equal(await part(page, 'day'), run[at + 1].date);
      assert.equal(answers.length, asked + 1, 'one request for the drag');
      // Let go over a neighbour, it is not picked: the drag was the step.
      await page.waitForTimeout(100);
      assert.equal(await part(page, 'day'), run[at + 1].date);
      // Up and down: the page's scrolling, not a drag.
      const stay = await part(page, 'day');
      await page.mouse.move(x, y);
      await page.mouse.down();
      for (const step of [20, 60, 120]) await page.mouse.move(x + 5, y + step);
      await page.mouse.up();
      assert.equal(await part(page, 'day'), stay);
      // Cancelled midway: nothing moves.
      await page.mouse.move(x, y);
      await page.mouse.down();
      await page.mouse.move(x - 80, y);
      await page.locator('.today-days-track').dispatchEvent('pointercancel', { pointerId: 1, isPrimary: true });
      await page.mouse.move(x - 200, y);
      await page.mouse.up();
      await page.waitForTimeout(100);
      assert.equal(await part(page, 'day'), stay);
      assert.equal(await page.locator('#today-days').getAttribute('class'), 'today-days');
      // Taken past 40px and brought back to where it started: nothing moves.
      await page.mouse.move(x, y);
      await page.mouse.down();
      for (const step of [20, 60, 120, 60, 5]) await page.mouse.move(x - step, y + 3);
      await page.mouse.up();
      await page.waitForTimeout(100);
      assert.equal(await part(page, 'day'), stay);
      // A touch while the mouse drags: neither moves the days, the touch neither, and its
      // tap's click on a neighbour picks nothing.
      await page.mouse.move(x, y);
      await page.mouse.down();
      await page.mouse.move(x - 80, y);
      const touch = { pointerId: 7, pointerType: 'touch', isPrimary: true, button: 0, buttons: 1, clientX: x, clientY: y };
      await page.locator('.today-days-track').dispatchEvent('pointerdown', touch);
      await page.locator('.today-days-track').dispatchEvent('pointermove', { ...touch, clientX: x - 200 });
      await page.locator('.today-days-track').dispatchEvent('pointerup', { ...touch, clientX: x - 200, buttons: 0 });
      await page.locator('.today-day[data-place="1"]').dispatchEvent('click');
      await page.mouse.move(x - 200, y);
      await page.mouse.up();
      await page.waitForTimeout(100);
      assert.equal(await part(page, 'day'), stay);
      assert.equal(answers.length, asked + 1, 'nothing asked since the first drag');
      // Up and down on a neighbour, and let go on it: a press that went more than 10px is
      // no press, so the neighbour is not picked.
      const side = await page.locator('.today-day[data-place="1"]').boundingBox();
      await page.mouse.move(side.x + side.width / 2, side.y + side.height * 0.35);
      await page.mouse.down();
      for (const share of [0.45, 0.55, 0.65]) await page.mouse.move(side.x + side.width / 2 + 2, side.y + side.height * share);
      await page.mouse.up();
      await page.waitForTimeout(100);
      assert.equal(await part(page, 'day'), stay);
      // Out off the days and back to where it started, let go on the neighbour: the press
      // went more than 10px, so it picks nothing.
      const daysBox = await page.locator('#today-days').boundingBox();
      const outside = daysBox.y + daysBox.height + 40;
      assert.ok(outside < page.viewportSize().height, `below the days, in the window: ${outside}`);
      await page.mouse.move(side.x + side.width / 2, side.y + side.height * 0.5);
      await page.mouse.down();
      await page.mouse.move(side.x + side.width / 2, outside);
      await page.mouse.move(side.x + side.width / 2, side.y + side.height * 0.5);
      await page.mouse.up();
      await page.waitForTimeout(100);
      assert.equal(await part(page, 'day'), stay);
      // Let go off the days before its drag began: the next drag still moves them.
      const area = await page.locator('#today-days').boundingBox();
      await page.mouse.move(x, y);
      await page.mouse.down();
      await page.mouse.move(x - 15, Math.min(area.y + area.height + 40, page.viewportSize().height - 5));
      await page.mouse.up();
      await page.waitForTimeout(100);
      assert.equal(await part(page, 'day'), stay);
      await page.mouse.move(x, y);
      await page.mouse.down();
      for (const step of [20, 60, 120, 1.4 * box.width]) await page.mouse.move(x - step, y + 3);
      await page.mouse.up();
      await shown(page);
      assert.equal(await part(page, 'day'), run[at + 2].date);
      // A press alone after all these picks again: a neighbour pressed is picked.
      await page.locator('.today-day[data-place="1"]').click();
      await shown(page);
      assert.equal(await part(page, 'day'), run[at + 3].date);
      // A drag on a neighbour whose capture is lost, let go on that neighbour: no pick.
      await page.evaluate(() => {
        window.__pointer = null;
        document.addEventListener('pointerdown', (event) => { window.__pointer = event.pointerId; }, { capture: true, once: true });
      });
      const near = await page.locator('.today-day[data-place="1"]').boundingBox();
      const nx = near.x + Math.min(20, near.width / 4);
      const ny = near.y + near.height / 2;
      await page.mouse.move(nx, ny);
      await page.mouse.down();
      // A capture is taken, and a release applied, at the pointer's next event.
      const captured = () => page.evaluate(() => document.querySelector('.today-days-track').hasPointerCapture(window.__pointer));
      for (const step of [15, 30, 45, 46]) await page.mouse.move(nx + step, ny + 2);
      assert.equal(await page.locator('#today-days').getAttribute('class'), 'today-days is-dragging');
      assert.equal(await captured(), true);
      await page.evaluate(() => document.querySelector('.today-days-track').releasePointerCapture(window.__pointer));
      await page.mouse.move(nx + 47, ny + 2);
      assert.equal(await captured(), false);
      assert.equal(await page.locator('#today-days').getAttribute('class'), 'today-days');
      await page.mouse.up();
      await page.waitForTimeout(100);
      assert.equal(await part(page, 'day'), run[at + 3].date);
    });

    check('a drag whose run is discarded while it is under way moves nothing, even once the next reading is drawn', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      const box = await page.locator('.today-day.is-centre .today-cards').boundingBox();
      const x = box.x + box.width / 2;
      const y = box.y + box.height / 2;
      await page.mouse.move(x, y);
      await page.mouse.down();
      for (const step of [20, 60, 120]) await page.mouse.move(x - step, y + 3);
      assert.equal(await page.locator('#today-days').getAttribute('class'), 'today-days is-dragging');
      // Finnish chosen by its button while the mouse is still down, and drawn.
      const asked = answers.length;
      await page.evaluate(() => document.querySelector('#today-language [data-today-lang="fi"]').click());
      await page.waitForFunction(() => new URLSearchParams(location.hash.split('?')[1]).get('lang') === 'fi');
      await page.waitForFunction(() => !document.getElementById('today-view').hasAttribute('aria-busy'));
      assert.equal(answers.length, asked + 1);
      assert.equal(await page.locator('#today-days').getAttribute('class'), 'today-days');
      // Let go a day's width further: the drag's run was English, so it moves nothing.
      await page.mouse.move(x - 1.4 * box.width, y + 3);
      await page.mouse.up();
      await page.waitForTimeout(100);
      assert.equal(await part(page, 'day'), DAY);
      assert.equal(answers.length, asked + 1, 'the drag asked for nothing');
      // A key steps the day while a drag is under way: the drag, begun on the day before,
      // moves nothing more.
      await page.mouse.move(x, y);
      await page.mouse.down();
      for (const step of [20, 60, 120]) await page.mouse.move(x - step, y + 3);
      assert.equal(await page.locator('#today-days').getAttribute('class'), 'today-days is-dragging');
      await page.keyboard.press(']');
      await page.waitForFunction(() => new URLSearchParams(location.hash.split('?')[1]).get('day') === '2026-10-12');
      await page.mouse.move(x - 1.4 * box.width, y + 3);
      await page.mouse.up();
      await page.waitForFunction(() => !document.getElementById('today-view').hasAttribute('aria-busy'));
      await page.waitForTimeout(100);
      assert.equal(await part(page, 'day'), '2026-10-12');
    });

    check('a drag while the day shown is past the strip steps by the days it went', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      const last = answers.at(-1).payload.run.at(-1).date;
      // Every answer asked for from here is held back: the run drawn stays this one.
      let release;
      const released = new Promise((resolve) => { release = resolve; });
      await page.route('**/api/today', async (route) => {
        await released;
        await route.fallback();
      });
      const calendarDay = (day, by) => {
        const next = new Date(`${day}T00:00:00Z`);
        next.setUTCDate(next.getUTCDate() + by);
        return next.toISOString().slice(0, 10);
      };
      await page.locator('#today-days').focus();
      await page.keyboard.press('End');
      await page.keyboard.press(']');
      await page.waitForFunction((day) => new URLSearchParams(location.hash.split('?')[1]).get('day') === day, calendarDay(last, 1));
      await settled(page);
      // Past the strip, dragged one day's width, the day steps once.
      const box = await page.locator('.today-day.is-centre .today-cards').boundingBox();
      const x = box.x + box.width / 2;
      const y = box.y + box.height / 2;
      await page.mouse.move(x, y);
      await page.mouse.down();
      for (const step of [20, 60, 120, 1.4 * box.width]) await page.mouse.move(x - step, y + 3);
      await page.mouse.up();
      await page.waitForFunction((day) => new URLSearchParams(location.hash.split('?')[1]).get('day') !== day, calendarDay(last, 1));
      assert.equal(await part(page, 'day'), calendarDay(last, 2));
      release();
      await shown(page);
      assert.equal(await part(page, 'day'), calendarDay(last, 2));
    });

    check('with reduced motion the days change in place, and still move', async (page) => {
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.clock.setFixedTime(NOW);
      await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      assert.deepEqual(await page.locator('.today-day').evaluateAll((nodes) => [...new Set(nodes.map((node) => getComputedStyle(node).transitionDuration))]), ['0s']);
      await page.locator('#today-days').focus();
      await page.keyboard.press('ArrowRight');
      await shown(page);
      assert.equal(await part(page, 'day'), '2026-10-12');
    });

    check('the days move at once through the run drawn for the reading shown alone: another person’s wait for their own answer', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers, hold } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page, { partner: PARTNER });
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      // The partner's day asked for, and a step taken before it is drawn: the days on
      // screen are the chart's own, so they stay until the partner's are drawn.
      const releaseSwitch = hold(DAY);
      const releaseStep = hold('2026-10-12');
      await page.locator('#today-who [data-who="partner"]').click();
      await page.waitForFunction(() => new URLSearchParams(location.hash.split('?')[1]).get('who') === 'partner');
      // Meanwhile a press moved up and down on a neighbour, and let go on it, is still no
      // press: it picks nothing.
      const side = await page.locator('.today-day[data-place="1"]').boundingBox();
      await page.mouse.move(side.x + side.width / 2, side.y + side.height * 0.35);
      await page.mouse.down();
      for (const share of [0.45, 0.55, 0.65]) await page.mouse.move(side.x + side.width / 2 + 2, side.y + side.height * share);
      await page.mouse.up();
      await page.waitForTimeout(100);
      assert.equal(await part(page, 'day'), DAY);
      await page.keyboard.press(']');
      await page.waitForFunction(() => new URLSearchParams(location.hash.split('?')[1]).get('day') === '2026-10-12');
      assert.equal(await page.locator('.today-day.is-centre').getAttribute('data-today-pick'), DAY);
      releaseSwitch();
      releaseStep();
      await shown(page);
      const { request, payload } = answers.at(-1);
      assert.deepEqual([request.chart, request.date], ['partner', '2026-10-12']);
      assert.equal(await page.locator('.today-day.is-centre').getAttribute('data-today-pick'), '2026-10-12');
      assert.equal(await page.locator('.today-day.is-centre .today-day-pull').textContent(), pull(payload.run.find((day) => day.date === '2026-10-12')));
    });

    check('a step goes through the run’s days: Apia’s skipped 30 December 2011 is passed over', async (page) => {
      await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page, { place: APIA });
      await page.goto(new URL(todayLink({ day: '2011-12-29' }), process.env.EC_BASE_URL).href);
      await shown(page);
      assert.equal(await page.locator('.today-run-day[data-today-day="2011-12-30"]').count(), 0);
      await page.locator('#today-days').focus();
      await page.keyboard.press(']');
      await shown(page);
      assert.equal(await part(page, 'day'), '2011-12-31');
      await page.locator('#today-days').focus();
      await page.keyboard.press('ArrowLeft');
      await shown(page);
      assert.equal(await part(page, 'day'), '2011-12-29');
    });

    check('a drag past the run’s end goes on through the days known: Apia’s skipped day once', async (page) => {
      const { answers } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page, { place: APIA });
      // 5 January 2012: its run starts on 29 December 2011, then 31 December.
      await page.goto(new URL(todayLink({ day: '2012-01-05' }), process.env.EC_BASE_URL).href);
      await shown(page);
      assert.deepEqual(answers.at(-1).payload.run.slice(0, 2).map((day) => day.date), ['2011-12-29', '2011-12-31']);
      // Back through the run to 31 December while every answer asked for since is held
      // back, so the run drawn stays 5 January's.
      let release;
      const released = new Promise((resolve) => { release = resolve; });
      await page.route('**/api/today', async (route) => {
        await released;
        await route.fallback();
      });
      await page.locator('#today-days').focus();
      for (let press = 0; press < 5; press += 1) await page.keyboard.press('ArrowLeft');
      await page.waitForFunction(() => new URLSearchParams(location.hash.split('?')[1]).get('day') === '2011-12-31');
      // Measured once the days have stopped sliding.
      await settled(page);
      assert.equal(await page.locator('.today-day.is-centre').getAttribute('data-today-pick'), '2011-12-31');
      // Two days back by a drag: 29 December, the run's first, then 28 December.
      const centre = await page.locator('.today-day.is-centre').boundingBox();
      const area = await page.locator('#today-days').boundingBox();
      const from = area.x + 30;
      const to = from + 2 * centre.width;
      assert.ok(to < page.viewportSize().width, `a two-day drag fits: ${to}`);
      const y = centre.y + centre.height / 2;
      await page.mouse.move(from, y);
      await page.mouse.down();
      for (const share of [0.1, 0.3, 0.6, 1]) await page.mouse.move(from + share * (to - from), y + 2);
      await page.mouse.up();
      await page.waitForFunction(() => new URLSearchParams(location.hash.split('?')[1]).get('day') !== '2011-12-31');
      assert.equal(await part(page, 'day'), '2011-12-28');
      release();
      await shown(page);
      assert.ok(answers.some((answer) => answer.request.date === '2011-12-28'), 'asked for 28 December');
      assert.equal(await page.locator('.today-day.is-centre').getAttribute('data-today-pick'), '2011-12-28');
    });

    check('past the run, the days go on through days fetched beyond it, while the day’s own answers are held', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers, pause } = await recordToday(page);
      const fetched = await recordDays(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      const run = answers.at(-1).payload.run;
      assert.equal(fetched.asked.length, 0, 'four days known or more each way: nothing fetched');
      const resume = pause();
      // Ten steps ahead leave four days known ahead: nothing is fetched.
      await stepDays(page, 10);
      await dayIs(page, '2026-10-21');
      await page.waitForTimeout(200);
      assert.equal(fetched.asked.length, 0);
      // The eleventh leaves three: the days after the run's last are asked for, once, with
      // the day's own request but its date and language.
      await page.keyboard.press('ArrowRight');
      await until(page, () => fetched.asked.length === 1 && fetched.asked[0].payload !== undefined);
      const { request, payload } = fetched.asked[0];
      assert.equal(request.after, run.at(-1).date);
      assert.deepEqual(Object.keys(request).sort(), ['after', 'chart', 'charts', 'place', 'schools']);
      assert.deepEqual(request.place, answers[0].request.place);
      // Past the run's last day the days go on, drawn from those fetched.
      await stepDays(page, 6);
      await dayIs(page, '2026-10-28');
      await settled(page);
      assert.equal(await centreOf(page).getAttribute('data-today-pick'), '2026-10-28');
      assert.equal(await centreOf(page).locator('.today-day-pull').textContent(), pull(payload.days.find((day) => day.date === '2026-10-28')));
      assert.equal(await page.locator('#today-view').getAttribute('aria-busy'), 'true', 'the day’s own answer is on its way');
      resume();
      await shown(page);
      assert.equal(await part(page, 'day'), '2026-10-28');
    });

    check('a date not known yet is a pending card until its days arrive; one request a way at a time, the two ways apart', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers, pause } = await recordToday(page);
      const fetched = await recordDays(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      const run = answers.at(-1).payload.run;
      const resume = pause();
      const releaseAhead = fetched.hold();
      // A day past the run, its days still on their way: a pending card, said as loading.
      await stepDays(page, 15);
      await dayIs(page, '2026-10-26');
      await settled(page);
      assert.equal(await centreOf(page).evaluate((node) => node.classList.contains('is-pending')), true);
      assert.equal(await centreOf(page).locator('.today-day-pull .sr-only').textContent(), 'Loading');
      assert.equal(fetched.asked.length, 1, 'one request ahead while it is on its way');
      // The other way meanwhile: Home goes to the strip's first day, and the days before
      // it are asked for, apart from those ahead.
      await page.keyboard.press('Home');
      await dayIs(page, run[0].date);
      await until(page, () => fetched.asked.length === 2);
      assert.equal(fetched.asked[1].request.before, run[0].date);
      // The days ahead arrive: the pending day is a day.
      releaseAhead();
      await until(page, () => fetched.asked[0].payload !== undefined);
      await page.keyboard.press('End');
      await stepDays(page, 1);
      await dayIs(page, '2026-10-26');
      await settled(page);
      assert.equal(await centreOf(page).evaluate((node) => node.classList.contains('is-pending')), false);
      resume();
      await shown(page);
    });

    check('Apia: the days fetched pass over the skipped 30 December both ways, and it is never asked for as the day', async (page) => {
      const { answers, pause } = await recordToday(page);
      const fetched = await recordDays(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page, { place: APIA });
      for (const [start, key, near, past, beyond] of [
        ['2011-12-09', 'ArrowRight', 11, 9, '2011-12-29'],
        ['2012-01-20', 'ArrowLeft', 4, 16, '2011-12-31'],
      ]) {
        // Each way from no days known: Today left, then opened on the day.
        await page.goto(new URL('/', process.env.EC_BASE_URL).href);
        await page.goto(new URL(todayLink({ day: start }), process.env.EC_BASE_URL).href);
        await shown(page);
        const asked = fetched.asked.length;
        const resume = pause();
        // Near the run's end the days beyond it are fetched, and the steps wait for them.
        await stepDays(page, near, key);
        await until(page, () => fetched.asked.length > asked && fetched.asked.at(-1).payload !== undefined);
        assert.ok(!fetched.asked.at(-1).payload.days.some((day) => day.date === '2011-12-30'));
        await stepDays(page, past, key);
        await dayIs(page, beyond);
        // One more step passes over 30 December.
        await stepDays(page, 1, key);
        await dayIs(page, beyond === '2011-12-29' ? '2011-12-31' : '2011-12-29');
        resume();
        await shown(page);
      }
      assert.ok(!answers.some((answer) => answer.request.date === '2011-12-30'), '30 December was never the day');
    });

    check('the engine’s ends: the days reach 31 December 2100 and 1 January 1949 and stop there; a date beyond the day’s own reach says why', async (page) => {
      const { pause } = await recordToday(page);
      const fetched = await recordDays(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      for (const [start, key, near, end] of [
        ['2100-11-27', 'ArrowRight', 11, '2100-12-31'],
        ['1949-01-28', 'ArrowLeft', 4, '1949-01-01'],
      ]) {
        await page.goto(new URL(todayLink({ day: start }), process.env.EC_BASE_URL).href);
        await shown(page);
        const asked = fetched.asked.length;
        const resume = pause();
        await stepDays(page, near, key);
        await until(page, () => fetched.asked.length === asked + 1 && fetched.asked.at(-1).payload !== undefined);
        const { payload } = fetched.asked.at(-1);
        assert.deepEqual([payload.through, payload.end], [end, true]);
        // On to the end, and no further: nothing more is asked for that way.
        await stepDays(page, 40, key);
        await dayIs(page, end);
        await page.waitForTimeout(200);
        assert.equal(await part(page, 'day'), end);
        assert.equal(fetched.asked.length, asked + 1);
        // The day's own answer for a date its run cannot reach is refused, with the API's
        // reason.
        resume();
        await page.locator('#today-notice').waitFor({ state: 'visible' });
        assert.match(await page.locator('#today-notice').textContent(), /can be read/);
      }
    });

    check('a past day, then Today: the days between the two runs are fetched, never stepped over; and the other way round', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { pause } = await recordToday(page);
      const fetched = await recordDays(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink({ day: '2026-09-01' }), process.env.EC_BASE_URL).href);
      await shown(page);
      await page.locator('#today-days').focus();
      await page.keyboard.press('n');
      await shown(page);
      assert.equal(await part(page, 'day'), DAY);
      // Today is further than one request beyond the past day's days: nothing chased it.
      assert.deepEqual(fetched.asked, []);
      let resume = pause();
      await stepDays(page, 4, 'ArrowLeft');
      await until(page, () => fetched.asked.some((entry) => entry.request.before === '2026-10-04' && entry.payload !== undefined));
      await stepDays(page, 4, 'ArrowLeft');
      await dayIs(page, '2026-10-03');
      resume();
      await shown(page);
      // From Today to a past day by a link: stepping on from its run's last day goes on to
      // the next date, never to Today's run.
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      await page.goto(new URL(todayLink({ day: '2026-09-01' }), process.env.EC_BASE_URL).href);
      await shown(page);
      resume = pause();
      await stepDays(page, 11);
      await until(page, () => fetched.asked.some((entry) => entry.request.after === '2026-09-15' && entry.payload !== undefined));
      await stepDays(page, 4);
      await dayIs(page, '2026-09-16');
      resume();
      await shown(page);
    });

    check('days on their way for a reading left are never merged into the next', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers, pause } = await recordToday(page);
      const fetched = await recordDays(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      const releaseOld = fetched.hold((request) => request.after === '2026-10-25');
      await stepDays(page, 11);
      await shown(page);
      await until(page, () => fetched.asked.length === 1);
      // Another language read while those days are on their way: they arrive late.
      await page.locator('#today-language [data-today-lang="fi"]').click();
      await shown(page);
      const releaseNew = fetched.hold((request) => request.after !== '2026-10-25');
      releaseOld();
      await until(page, () => fetched.asked[0].payload !== undefined);
      // Past the new reading's run its days are still on their way, as is its own day: a
      // pending card, not the old reading's day.
      const run = answers.at(-1).payload.run;
      const resume = pause();
      await page.locator('#today-days').focus();
      await page.keyboard.press('End');
      await stepDays(page, 1);
      await settled(page);
      assert.equal(await centreOf(page).getAttribute('data-today-pick') > run.at(-1).date, true);
      assert.equal(await centreOf(page).evaluate((node) => node.classList.contains('is-pending')), true);
      releaseNew();
      resume();
      await shown(page);
    });

    check('days fetched before the day’s own answer change only the carousel: Copy and Print wait for the day’s own', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { pause } = await recordToday(page);
      const fetched = await recordDays(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      const strip = await page.locator('.today-run-day').evaluateAll((nodes) => nodes.map((node) => node.dataset.todayDay));
      const resume = pause();
      await page.locator('#today-days').focus();
      await page.keyboard.press('End');
      await until(page, () => fetched.asked.length === 1 && fetched.asked[0].payload !== undefined);
      await stepDays(page, 1);
      await dayIs(page, '2026-10-26');
      await settled(page);
      // The carousel draws the day fetched; the strip, Copy and Print wait for its own.
      assert.equal(await centreOf(page).evaluate((node) => node.classList.contains('is-pending')), false);
      assert.deepEqual(await page.locator('.today-run-day').evaluateAll((nodes) => nodes.map((node) => node.dataset.todayDay)), strip);
      assert.equal(await page.locator('#today-copy-text').getAttribute('aria-disabled'), 'true');
      resume();
      await shown(page);
      assert.equal(await page.locator('#today-copy-text').getAttribute('aria-disabled'), 'false');
    });

    check('a request for days that fails says so, leaves the way open and is asked again on the next move that way', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { pause } = await recordToday(page);
      const fetched = await recordDays(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      const resume = pause();
      fetched.fail(500);
      await recordToasts(page);
      await stepDays(page, 11);
      await until(page, () => fetched.asked.length === 1);
      await page.waitForFunction(() => window.__toasts.length > 0);
      assert.deepEqual(await toastsSaid(page), ['The days after Sunday, October 25, 2026 could not be fetched.']);
      // An answer that extends nothing is a failure too.
      fetched.tamper((value) => ({ ...value, through: value.after, days: [] }));
      await stepDays(page, 1);
      await until(page, () => fetched.asked.length === 2 && fetched.asked[1].payload !== undefined);
      // The next move that way asks again, and the days arrive.
      await stepDays(page, 1);
      await until(page, () => fetched.asked.length === 3 && fetched.asked[2].payload !== undefined);
      assert.equal(fetched.asked[2].request.after, '2026-10-25');
      resume();
      await shown(page);
    });

    check('a day fetched that disagrees with the day’s own answer is said, and the day’s own is drawn', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      const fetched = await recordDays(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      fetched.tamper((value) => ({
        ...value,
        days: value.days.map((day) => (day.date === '2026-11-01' ? { ...day, score: day.score > 0 ? day.score - 1 : day.score + 1 } : day)),
      }));
      await recordToasts(page);
      await stepDays(page, 11);
      await until(page, () => fetched.asked.length === 1 && fetched.asked[0].payload !== undefined);
      // A day drawn whose run covers 1 November reads it as the API does, and the page
      // says the day fetched disagreed.
      await shown(page);
      // Said whichever answer finds it first: a late one (fetching stops) or the one drawn
      // (the day's own is shown).
      await page.waitForFunction(() => window.__toasts.some((said) => [
        'A day fetched disagrees with the one shown: no more are fetched that way.',
        'A day fetched disagreed with the day’s own answer: the day’s own is shown.',
      ].includes(said)));
      await stepDays(page, 10);
      await dayIs(page, '2026-11-01');
      await shown(page);
      const own = answers.at(-1).payload.run.find((day) => day.date === '2026-11-01');
      assert.equal(await centreOf(page).locator('.today-day-pull').textContent(), pull(own));
    });

    check('a drag from a date not known yet into the days known passes over Apia’s skipped day', async (page) => {
      const { answers, pause } = await recordToday(page);
      const fetched = await recordDays(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page, { place: APIA });
      // 5 January 2012: its run starts on 29 December 2011, then 31 December.
      await page.goto(new URL(todayLink({ day: '2012-01-05' }), process.env.EC_BASE_URL).href);
      await shown(page);
      // The days before the run are held on their way: 28 December is not known yet.
      fetched.hold();
      const resume = pause();
      await stepDays(page, 7, 'ArrowLeft');
      await dayIs(page, '2011-12-28');
      await settled(page);
      assert.equal(await centreOf(page).evaluate((node) => node.classList.contains('is-pending')), true);
      // Two days ahead by a drag: 29 December, then 31 December, never the 30th.
      const box = await centreOf(page).boundingBox();
      const x = box.x + box.width / 2;
      const y = box.y + box.height / 3;
      await page.mouse.move(x, y);
      await page.mouse.down();
      for (const step of [20, 60, 120, 2.2 * box.width]) await page.mouse.move(x - step, y + 3);
      await page.mouse.up();
      await dayIs(page, '2011-12-31');
      resume();
      await shown(page);
      assert.ok(!answers.some((answer) => answer.request.date === '2011-12-30'), '30 December was never the day');
    });

    check('Home and End go to the strip’s ends, never against their way, past the strip and while the day’s own answer is held', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers, pause } = await recordToday(page);
      const fetched = await recordDays(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      const run = answers.at(-1).payload.run;
      const resume = pause();
      await stepDays(page, 11);
      await until(page, () => fetched.asked.length === 1 && fetched.asked[0].payload !== undefined);
      await stepDays(page, 5);
      await dayIs(page, '2026-10-27');
      // Past the strip's last day, End does nothing; Home goes to its first, End to its last.
      await page.keyboard.press('End');
      await page.waitForTimeout(150);
      assert.equal(await part(page, 'day'), '2026-10-27');
      await page.keyboard.press('Home');
      await dayIs(page, run[0].date);
      await page.keyboard.press('End');
      await dayIs(page, run.at(-1).date);
      resume();
      await shown(page);
    });

    check('days arriving during a drag wait for it to end, and the drag steps as it would have', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      const fetched = await recordDays(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink({ day: '2026-10-22' }), process.env.EC_BASE_URL).href);
      await shown(page);
      // From the run's first days, four back asks for the days before it: held.
      const releaseBack = fetched.hold();
      await page.locator('#today-days').focus();
      await page.keyboard.press('Home');
      await shown(page);
      await until(page, () => fetched.asked.length === 1);
      const asked = answers.length;
      // A day is as wide as its slot, as the drag counts it (its cards may be wider).
      const box = await centreOf(page).boundingBox();
      const x = box.x + box.width / 2;
      const y = box.y + box.height / 3;
      await page.mouse.move(x, y);
      await page.mouse.down();
      for (const step of [20, 60]) await page.mouse.move(x - step, y + 3);
      // The days before arrive mid-drag: the drag goes on.
      releaseBack();
      await until(page, () => fetched.asked[0].payload !== undefined);
      assert.equal(await page.locator('#today-days').evaluate((node) => node.classList.contains('is-dragging')), true);
      for (const step of [120, 1.4 * box.width]) await page.mouse.move(x - step, y + 3);
      await page.mouse.up();
      await shown(page);
      assert.equal(answers.length, asked + 1, 'one request for the drag');
      assert.equal(answers.at(-1).request.date, '2026-10-16');
    });

    check('the pull on one scale, its ends and the five gods named in words; a pull past the scale is refused', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      const { payload } = answers.at(-1);
      const gods = payload.favourable.gods;
      assert.equal(await page.locator('#today-scale .today-scale-marker').evaluate((m) => m.style.getPropertyValue('--at')), scaleAt(payload.layers.day.pull.score));
      assert.deepEqual(await page.locator('#today-scale .today-scale-tick').evaluateAll((ticks) => ticks.map((tick) => tick.style.getPropertyValue('--at'))),
        [-1.5, -0.5, 0, 0.5, 1.5].map(scaleAt));
      assert.equal(await page.locator('.today-scale-end.is-for').textContent(), `+ ${godLine(gods, 'useful')}`);
      assert.equal(await page.locator('.today-scale-end.is-against').textContent(), `− ${godLine(gods, 'unfavourable')}`);
      assert.deepEqual(await page.locator('.today-five-gods .today-god').allTextContents(),
        ['useful', 'favourable', 'idle', 'enemy', 'unfavourable'].map((god) => godLine(gods, god)));
      // Each of the four pillars on the same scale.
      for (const layer of ['day', 'month', 'year', 'luck']) {
        assert.equal(await page.locator(`.today-pillar[data-layer="${layer}"] .today-scale-marker`).evaluate((m) => m.style.getPropertyValue('--at')),
          scaleAt(payload.layers[layer].pull.score));
      }
      // An answer whose pull passes the scale's end is not drawn clipped: it is refused.
      await page.route('**/api/today', async (route) => {
        const response = await route.fetch();
        const value = await response.json();
        value.layers.day.pull.score = 3.6;
        await route.fulfill({ response, json: value });
      });
      await page.locator('.today-step[data-today-step="1"]').click();
      await page.locator('#today-notice').waitFor({ state: 'visible' });
      assert.match(await page.locator('#today-notice').textContent(), /could not be shown/);
      assert.equal(await page.locator('#today-body').isHidden(), true);
    });

    check('In your chart draws each relationship’s pillars, the chart’s own among them, three members where there are three', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      // The API's own sample, 17 May 1990, 08:30, on 12 October 2026: two summer
      // directional combinations, each of three members.
      await page.goto(new URL(todayLink({ day: '2026-10-12' }, { date: '1990-05-17', time: '08:30' }), process.env.EC_BASE_URL).href);
      await shown(page);
      const { payload } = answers.at(-1);
      const all = ['day', 'month', 'year', 'luck'].flatMap((layer) => payload.layers[layer]?.relationships ?? []);
      assert.ok(all.some((r) => r.members.length === 3), 'a relationship of three members');
      const fifth = { daily: 'day', monthly: 'month', annual: 'year', luck: 'luck' };
      for (const r of all) {
        const item = page.locator(`#today-in-chart .today-relationship[data-relationship="${r.id}"]`);
        const figures = await item.locator('.today-member-pillar').evaluateAll((nodes) => nodes.map((node) => ({
          glyphs: [...node.querySelectorAll('.today-card-glyph')].map((glyph) => glyph.textContent).join(''),
          member: node.querySelector('.today-card.is-member .today-card-glyph')?.textContent,
        })));
        assert.deepEqual(figures, r.members.map((m) => {
          const pillar = fifth[m.pillar] ? payload.layers[fifth[m.pillar]].pillar : payload.natal[m.pillar];
          return { glyphs: pillar.stem.chinese + pillar.branch.chinese, member: m.char };
        }), r.id);
      }
    });

    check('the hours as a dial beside their table: one wedge each, its call’s mark, and the hour now on today alone', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { answers } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      const { payload } = answers.at(-1);
      const wedges = await page.locator('.today-dial-hour').evaluateAll((groups) => groups.map((group) => ({
        branch: group.querySelector('.today-dial-glyph').textContent,
        pinyin: group.querySelector('.today-dial-pinyin').textContent,
        mark: group.querySelector('.today-dial-call')?.tagName ?? null,
        size: group.querySelector('.today-dial-call')?.getAttribute('height') ?? null,
        now: group.classList.contains('is-now'),
      })));
      const marks = { protect: ['circle', null], mixed: ['rect', '2'], avoid: ['rect', '8'] };
      assert.deepEqual(wedges.map(({ branch, pinyin, mark, size }) => [branch, pinyin, mark, size]),
        payload.hours.map((hour) => [hour.branch, hour.pinyin, ...(hour.call === null ? [null, null] : marks[hour.call])]));
      // Noon in Helsinki on the day it is: the hour whose span holds it is outlined.
      const now = payload.hours.filter((hour) => hour.spans.some((span) => Date.parse(span.start) <= NOW.getTime() && NOW.getTime() < Date.parse(span.end)));
      assert.equal(now.length, 1);
      assert.deepEqual(wedges.filter((wedge) => wedge.now).map((wedge) => wedge.branch), [now[0].branch]);
      // The table names it too, for a reader: its row is the current time.
      const rows = await page.locator('.today-hours tbody tr').evaluateAll((trs) => trs.map((tr) => [tr.getAttribute('aria-current'), tr.querySelector('.today-hour-now')?.textContent ?? null]));
      assert.deepEqual(rows, payload.hours.map((hour) => (hour === now[0] ? ['time', '· now'] : [null, null])));
      // Another day has no hour now.
      await page.locator('.today-step[data-today-step="1"]').click();
      await shown(page);
      assert.equal(await page.locator('.today-dial-hour.is-now').count(), 0);
      assert.equal(await page.locator('.today-hours tbody tr[aria-current], .today-hour-now').count(), 0);
      // The table stays, every hour in it.
      assert.equal(await page.locator('.today-hours tbody tr').count(), 12);
    });

    check('the hour now, today’s dot and Today in the bar follow the clock while the day is shown', async (page) => {
      await page.clock.install({ time: NOW });
      const { answers } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      const { payload } = answers.at(-1);
      const holding = (time) => payload.hours.findIndex((hour) => hour.spans.some((span) => Date.parse(span.start) <= time && time < Date.parse(span.end)));
      const marked = () => page.evaluate(() => ({
        dial: [...document.querySelectorAll('.today-dial-hour')].findIndex((wedge) => wedge.classList.contains('is-now')),
        table: [...document.querySelectorAll('.today-hours tbody tr')].findIndex((row) => row.getAttribute('aria-current') === 'time'),
        today: document.querySelector('.today-run-day.is-today')?.dataset.todayDay ?? null,
        todayOff: document.querySelector('#today-steps [data-today-now]').disabled,
      }));
      const first = holding(NOW.getTime());
      assert.notEqual(first, -1);
      assert.deepEqual(await marked(), { dial: first, table: first, today: DAY, todayOff: true });
      // On into the next hour: its wedge and its row are now's.
      const next = (first + 1) % 12;
      await page.clock.pauseAt(new Date(Date.parse(payload.hours[next].spans[0].start) + 60 * 1000));
      await page.clock.runFor(31 * 1000);
      assert.deepEqual(await marked(), { dial: next, table: next, today: DAY, todayOff: true });
      // Past midnight where you are: tomorrow is today, and the day shown has no hour now.
      await page.clock.pauseAt(new Date('2026-10-11T21:30:00Z'));
      await page.clock.runFor(31 * 1000);
      assert.deepEqual(await marked(), { dial: -1, table: -1, today: '2026-10-12', todayOff: false });
    });

    check('printed while a day is on its way, the page says so, and gives nothing of the day before', async (page) => {
      await page.clock.setFixedTime(NOW);
      const { hold } = await recordToday(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await setSettings(page);
      await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
      await shown(page);
      const release = hold('2026-10-12');
      await page.locator('.today-step[data-today-step="1"]').click();
      await page.waitForFunction(() => document.getElementById('today-view').getAttribute('aria-busy') === 'true');
      await page.emulateMedia({ media: 'print' });
      const printed = await page.evaluate(() => ({
        body: getComputedStyle(document.getElementById('today-body')).display,
        note: getComputedStyle(document.querySelector('.today-pending-print')).display,
        noteText: document.querySelector('.today-pending-print').textContent,
      }));
      assert.deepEqual(printed, { body: 'none', note: 'block', noteText: 'The day is still being read.' });
      await page.emulateMedia({ media: 'screen' });
      release();
      await shown(page);
      // Drawn, the day prints its own: the chosen day's cards, not its neighbours, nor the dial.
      await page.emulateMedia({ media: 'print' });
      const drawn = await page.evaluate(() => ({
        body: getComputedStyle(document.getElementById('today-body')).display,
        note: getComputedStyle(document.querySelector('.today-pending-print')).display,
        neighbours: [...document.querySelectorAll('.today-day:not(.is-centre)')].map((node) => getComputedStyle(node).display),
        dial: getComputedStyle(document.querySelector('.today-dial')).display,
      }));
      assert.deepEqual({ ...drawn, neighbours: [...new Set(drawn.neighbours)] }, { body: 'flex', note: 'none', neighbours: ['none'], dial: 'none' });
      await page.emulateMedia({ media: 'screen' });
    });
  });
}

describe(`${engineName} / today and the session`, { concurrency: false }, () => {
  // An account of its own, with where you are kept, and a page signed in to it.
  const ownAccount = async (page, language, label) => {
    const own = await newAccount(playwright, { language, label });
    await asAccount(playwright, own, async (request) => {
      const kept = await request.put('/api/account/place', { data: { place: PLACE, key: own.key, updated_at: null } });
      assert.equal(kept.status(), 200, await kept.text());
    });
    await stubTurnstile(page);
    return own;
  };

  it('a day asked for after the session ended asks for a sign-in, then is drawn', { timeout: 120000 }, () => withPage(profiles[0], async (page) => {
    await page.clock.setFixedTime(NOW);
    const own = await ownAccount(page, 'en', 'today-ended');
    await signInPage(page, own);
    await recordToday(page);
    await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
    await shown(page);
    // Signed out on every device, from another one: the page still holds the account.
    await asAccount(playwright, own, async (request) => {
      assert.equal((await request.delete('/api/account/sessions', { data: { key: own.key } })).status(), 204);
    });
    await page.locator('.today-step[data-today-step="1"]').click();
    await dialogOpens(page);
    await signInThroughDialog(page, own.email);
    await shown(page);
    assert.equal(await part(page, 'day'), '2026-10-12');
    assert.equal(await page.locator('#today-body').isVisible(), true);
    assert.equal(await page.locator('#today-notice').isHidden(), true);
  }, { signedIn: false }));

  it('after a sign-out, the day shows nothing of the account before, even when the next read fails', { timeout: 120000 }, () => withPage(profiles[0], async (page) => {
    await page.clock.setFixedTime(NOW);
    const first = await ownAccount(page, 'en', 'today-first');
    const second = await newAccount(playwright, { language: 'en', label: 'today-second' });
    await asAccount(playwright, first, async (request) => {
      // Made from the settings as they are: the account keeps a place already.
      const now = await (await request.get('/api/account/settings')).json();
      const mine = await request.post('/api/account/charts', { data: { ...SELF, key: first.key, updated_at: now.updated_at } });
      assert.equal(mine.status(), 201, await mine.text());
      const { saved, updated_at: read } = await mine.json();
      const kept = await request.post('/api/account/charts', {
        data: { ...PARTNER, name: 'First partner', couple_with: saved, key: first.key, updated_at: read },
      });
      assert.equal(kept.status(), 201, await kept.text());
    });
    await signInPage(page, first);
    await recordToday(page);
    await page.goto(new URL('/', process.env.EC_BASE_URL).href);
    await keepSecondCouple(page);
    await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
    await shown(page);
    assert.match(await page.locator('#today-chart').textContent(), /at Helsinki/);
    assert.equal(await page.locator('.today-who-name').textContent(), 'First partner');
    assert.deepEqual(await page.locator('#today-partner option').allTextContents(), ['First partner', SECOND.name]);
    // To the start page, whose account menu signs out; the page stays as it is.
    await page.locator('#today-page-switch [data-page="chart"]').click();
    await page.locator('#chart-view').waitFor({ state: 'visible' });
    await page.locator('#new-chart-btn').click();
    await page.locator('#account-btn').click();
    await page.locator('#account-sign-out').click();
    // Signed in to another account in the same page, whose settings cannot be read now.
    await signInThroughDialog(page, second.email);
    await page.route('**/api/account/settings', (route) => route.fulfill({ status: 500, json: { detail: 'Stopped by the test.' } }));
    await page.evaluate((hash) => {
      history.pushState(null, '', hash);
      dispatchEvent(new PopStateEvent('popstate'));
    }, todayLink().slice(1));
    await page.locator('#today-notice').waitFor({ state: 'visible' });
    assert.match(await page.locator('#today-notice').textContent(), /Stopped by the test\./);
    // The chart's own heading names its birth city; where you are is not said.
    assert.doesNotMatch(await page.locator('#today-chart').textContent(), /at Helsinki/);
    assert.equal(await page.locator('#today-who').isHidden(), true);
    assert.equal(await page.locator('.today-who-name').textContent(), '');
    assert.equal(await page.locator('#today-body').isHidden(), true);
    // With goes, names and all.
    assert.equal(await page.locator('#today-partner-choice').isHidden(), true);
    assert.equal(await page.locator('#today-partner option').count(), 0);
    assert.doesNotMatch(await page.locator('#today-view').textContent(), /First partner|Second partner/);
  }, { signedIn: false }));

  it('another account taken while the day is read: the day is read again with its settings, and nothing of the one before stays', { timeout: 120000 }, () => withPage(profiles[0], async (page) => {
    await page.clock.setFixedTime(NOW);
    const first = await ownAccount(page, 'en', 'today-taken-a');
    const second = await ownAccount(page, 'en', 'today-taken-b');
    await asAccount(playwright, first, async (request) => {
      // Made from the settings as they are: the account keeps a place already.
      const now = await (await request.get('/api/account/settings')).json();
      const mine = await request.post('/api/account/charts', { data: { ...SELF, key: first.key, updated_at: now.updated_at } });
      assert.equal(mine.status(), 201, await mine.text());
      const { saved, updated_at: read } = await mine.json();
      const kept = await request.post('/api/account/charts', {
        data: { ...PARTNER, name: 'First partner', couple_with: saved, key: first.key, updated_at: read },
      });
      assert.equal(kept.status(), 201, await kept.text());
    });
    await signInPage(page, first);
    const { answers } = await recordToday(page);
    await page.goto(new URL('/', process.env.EC_BASE_URL).href);
    const ids = await keepSecondCouple(page);
    await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
    await shown(page);
    assert.equal(await page.locator('.today-who-name').textContent(), 'First partner');
    assert.deepEqual(await page.locator('#today-partner option').allTextContents(), ['First partner', SECOND.name]);
    assert.equal(await part(page, 'partner'), ids.first);
    // Another tab signs out of the first account and in to the second: the next read of
    // the settings here is refused for want of a session, and the page takes the second.
    let refused = false;
    await page.route('**/api/account/settings', async (route) => {
      if (refused || route.request().method() !== 'GET') return route.fallback();
      refused = true;
      await page.context().addCookies(second.cookies);
      return route.fulfill({ status: 401, json: { detail: 'Sign in first.' } });
    });
    await page.locator('.today-step[data-today-step="1"]').click();
    await page.waitForFunction(() => document.getElementById('today-date').textContent.includes('October 12'));
    await shown(page);
    assert.equal(await part(page, 'day'), '2026-10-12');
    assert.equal(await page.locator('#today-body').isVisible(), true);
    assert.equal(await page.locator('#today-who').isHidden(), true);
    assert.equal(await page.locator('.today-who-name').textContent(), '');
    assert.doesNotMatch(await page.locator('#today-view').textContent(), /First partner|Second partner/);
    assert.equal(await page.locator('#today-partner-choice').isHidden(), true);
    assert.equal(await page.locator('#today-partner option').count(), 0);
    // The partner the page wrote in was the first account's: it goes from the address,
    // and nothing says this chart is not in a couple.
    assert.equal(await part(page, 'partner'), null);
    assert.equal(await page.locator('#today-notice').isHidden(), true);
    assert.equal(answers.at(-1).request.date, '2026-10-12');
    assert.equal(answers.at(-1).request.charts.partner, undefined);
  }, { signedIn: false }));

  it('another account taken while the day is hidden: opened again, Today shows nothing of the one before', { timeout: 120000 }, () => withPage(profiles[0], async (page) => {
    await page.clock.setFixedTime(NOW);
    const first = await ownAccount(page, 'en', 'today-hidden-a');
    const second = await ownAccount(page, 'en', 'today-hidden-b');
    await asAccount(playwright, first, async (request) => {
      const now = await (await request.get('/api/account/settings')).json();
      const mine = await request.post('/api/account/charts', { data: { ...SELF, key: first.key, updated_at: now.updated_at } });
      assert.equal(mine.status(), 201, await mine.text());
      const { saved, updated_at: read } = await mine.json();
      const kept = await request.post('/api/account/charts', {
        data: { ...PARTNER, name: 'First partner', couple_with: saved, key: first.key, updated_at: read },
      });
      assert.equal(kept.status(), 201, await kept.text());
    });
    await signInPage(page, first);
    const { answers } = await recordToday(page);
    await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
    await shown(page);
    assert.equal(await page.locator('.today-who-name').textContent(), 'First partner');
    // To the chart, where another tab's sign-in to the second account is taken by the
    // account's command.
    await page.locator('#today-page-switch [data-page="chart"]').click();
    await page.locator('#chart-view').waitFor({ state: 'visible' });
    await page.waitForFunction(() => !document.getElementById('chart-view').hasAttribute('aria-busy'));
    await page.context().addCookies(second.cookies);
    await page.keyboard.press('ControlOrMeta+k');
    await page.locator('#palette-input').fill('account');
    await page.keyboard.press('Enter');
    await dialogOpens(page);
    await page.locator('#account-who').filter({ hasText: second.email }).waitFor();
    await page.keyboard.press('Escape');
    // Today again. Chart · Today reads the settings for the date where you are; the
    // day's own read of them is held on its way: nothing of the first account is drawn
    // meanwhile.
    let release;
    const held = new Promise((resolve) => { release = resolve; });
    let reads = 0;
    await page.route('**/api/account/settings', async (route) => {
      if (route.request().method() === 'GET') {
        reads += 1;
        if (reads === 2) await held;
      }
      await route.fallback();
    });
    await page.locator('#page-switch [data-page="today"]').click();
    await page.locator('#today-view').waitFor({ state: 'visible' });
    assert.equal(await page.locator('.today-who-name').textContent(), '');
    assert.equal(await page.locator('#today-who').isHidden(), true);
    assert.equal(await page.locator('#today-body').isHidden(), true);
    assert.doesNotMatch(await page.locator('#today-view').textContent(), /First partner/);
    release();
    await shown(page);
    assert.equal(await page.locator('#today-who').isHidden(), true);
    assert.equal(answers.at(-1).request.charts.partner, undefined);
  }, { signedIn: false }));

  it('signed in on a day’s link, the day is in the account’s language, and so is its address', { timeout: 120000 }, () => withPage(profiles[0], async (page) => {
    await page.clock.setFixedTime(NOW);
    const own = await ownAccount(page, 'fi', 'today-language');
    const { answers } = await recordToday(page);
    await page.goto(new URL(todayLink(), process.env.EC_BASE_URL).href);
    await dialogOpens(page);
    await signInThroughDialog(page, own.email);
    await shown(page);
    assert.equal(await part(page, 'lang'), 'fi');
    assert.equal(await page.evaluate(() => document.documentElement.lang), 'fi');
    assert.equal(answers.at(-1).request.lang, 'fi');
    assert.equal(await page.locator('#today-language [data-today-lang="fi"]').getAttribute('aria-pressed'), 'true');
  }, { signedIn: false }));
});

describe(`${engineName} / today in a comparison`, { concurrency: false }, () => {
  it('a compared chart has no Chart · Today and no library', { timeout: 120000 }, () => withPage(profiles[0], async (page) => {
    await openLink(page, `/?embed=1#chart?${chartParams()}`, { place: HELSINKI });
    assert.equal(await page.locator('#page-switch').isHidden(), true);
    assert.equal(await page.locator('#library-btn').isHidden(), true);
  }));
});
