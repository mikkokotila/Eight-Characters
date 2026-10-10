// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Today: the day of the chart on screen (docs/Standard-Today.md). Every number the page
// shows is the API's (POST /api/today), asked for with the partner's chart, the place
// and the schools the account keeps. The address names the chart, the day, whose day
// and the topic; a step replaces it and a topic adds to it; late answers are dropped.
import {
  assert, describe, it, engineName, profiles, openLink, settled, withPage, HELSINKI,
} from './chart-helpers.mjs';

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

// The account's settings, changed from the page as Settings changes them.
async function setSettings(page, { place = PLACE, partner = null } = {}) {
  const statuses = await page.evaluate(async ({ place, partner }) => {
    const write = async (method, path, body) => {
      const read = await (await fetch('/api/account/settings')).json();
      const response = await fetch(path, {
        method, headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...body, key: read.key, updated_at: read.updated_at }),
      });
      return response.status;
    };
    return [
      place === null ? await write('DELETE', '/api/account/place', {}) : await write('PUT', '/api/account/place', { place }),
      partner === null ? await write('DELETE', '/api/account/partner', {}) : await write('PUT', '/api/account/partner', partner),
    ];
  }, { place, partner });
  assert.deepEqual(statuses, [200, 200]);
}
// Every answer to POST /api/today, with what the page asked; `hold` keeps one back.
async function recordToday(page) {
  const answers = [];
  const held = [];
  await page.route('**/api/today', async (route) => {
    const response = await route.fetch();
    const entry = { request: route.request().postDataJSON(), payload: await response.json() };
    answers.push(entry);
    if (held.length && held[0].day === entry.request.date) {
      const wait = held.shift();
      await wait.released;
    }
    await route.fulfill({ response });
  });
  const hold = (day) => {
    let release;
    const released = new Promise((resolve) => { release = resolve; });
    held.push({ day, released });
    return release;
  };
  return { answers, hold };
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
      // The four pillars of the day, each with its characters, pinyin and pull.
      for (const layer of ['day', 'month', 'year', 'luck']) {
        const card = page.locator(`.today-pillar[data-layer="${layer}"]`);
        const data = payload.layers[layer];
        assert.ok(data !== null, `the sample has a ${layer} pillar`);
        assert.equal(await card.locator('.today-chars').textContent(), data.pillar.stem.chinese + data.pillar.branch.chinese);
        assert.equal(await card.locator('.today-pinyin').textContent(), `${data.pillar.stem.pinyin} ${data.pillar.branch.pinyin}`);
        assert.equal((await card.locator('.today-pillar-pull').textContent()).trim(), pull(data.pull));
      }
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
      await page.keyboard.press('Escape');
      // A field's own keys are its own.
      await page.locator('#today-copy-link').focus();
      await page.evaluate(() => document.activeElement.blur());
      await page.keyboard.press(']');
      assert.equal(await part(page, 'day'), DAY, 'nothing on the page has focus');
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
      assert.equal(answers.at(-1).request.charts.partner.pillars, undefined);
      await page.locator('[data-today-topic="marriage"]').click();
      await shown(page);
      const marriage = answers.at(-1).payload.marriage;
      assert.match(await page.locator('#today-detail').textContent(), new RegExp(pull(marriage.partner.pull).replace(/[()+]/g, '\\$&')));
      await page.locator('#today-who [data-who="partner"]').click();
      await shown(page);
      assert.equal(await part(page, 'who'), 'partner');
      assert.equal(answers.at(-1).request.chart, 'partner');
      assert.match(await page.locator('#today-notice').textContent(), /your partner’s day/);
      // Removed elsewhere: the page says so, and offers the chart's own day.
      await setSettings(page);
      await page.reload();
      await page.locator('#today-notice').waitFor({ state: 'visible' });
      assert.match(await page.locator('#today-notice').textContent(), /no longer saved/);
      await page.locator('[data-today-action="self"]').click();
      await shown(page);
      assert.equal(await part(page, 'who'), null);
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
  });
}

describe(`${engineName} / today in a comparison`, { concurrency: false }, () => {
  it('a compared chart has no Chart · Today and no Save as partner', { timeout: 120000 }, () => withPage(profiles[0], async (page) => {
    await openLink(page, `/?embed=1#chart?${chartParams()}`, { place: HELSINKI });
    assert.equal(await page.locator('#page-switch').isHidden(), true);
    assert.equal(await page.locator('#save-partner-btn').isHidden(), true);
  }));
});
