// Run with Node's built-in test runner and an explicitly selected Playwright install.
// The first chart (first.js, docs/Standard-First-Chart.md): what a birth settles without
// its time, or without an account, from POST /api/first_chart. Every pillar, change and
// Day Master shown is the API's own. Only the place search and Cloudflare's widget are
// stubbed.
import {
  assert, describe, it, engineName, profiles, settled, withPage, CHENGDU,
} from './chart-helpers.mjs';
import { newAddress } from './account-helpers.mjs';
import { BIRTH, link, visit, chartsAskedFor, dialogOpens, text, sendCode, enterCode } from './account-page.mjs';

const ORDER = ['hour', 'day', 'month', 'year'];
const LOCATION = { timezone: CHENGDU.timezone, latitude: CHENGDU.latitude, longitude: CHENGDU.longitude };
// The API's first chart of the suite's birth, with its time or without one.
async function firstChart(page, time = null) {
  const response = await page.request.post(new URL('/api/first_chart', process.env.EC_BASE_URL).href, {
    data: { date: BIRTH.date, ...(time === null ? {} : { time }), location: LOCATION },
  });
  assert.equal(response.status(), 200);
  return response.json();
}
const named = (pillar) => `${pillar.stem.chinese}${pillar.branch.chinese} ${pillar.stem.pinyin} ${pillar.branch.pinyin}`;
// What the first chart shows: its address, its heading and lead, each pillar by its
// name and characters, its changes, its Day Master, and whether it offers an account.
const shown = (page) => page.evaluate(() => ({
  time: new URLSearchParams(location.hash.split('?')[1] ?? '').get('time'),
  heading: document.getElementById('first-birth').textContent,
  lead: document.getElementById('first-lead').textContent,
  pillars: [...document.querySelectorAll('.first-pillar')].map((pillar) => [
    pillar.dataset.pillar, pillar.querySelector('.first-pillar-chars').textContent.replace(/\s+/g, ' ').trim()]),
  changes: [...document.querySelectorAll('#first-changes li')].map((item) => item.textContent),
  dayMaster: document.getElementById('first-day-master-title').textContent,
  note: document.getElementById('first-day-master-note').checkVisibility() ? document.getElementById('first-day-master-note').textContent : null,
  offer: document.getElementById('first-offer').checkVisibility(),
  overflow: document.documentElement.scrollWidth > innerWidth,
}));
const firstDrawn = (page) => page.locator('#first-view:not(.hidden):not([aria-busy])').waitFor();
const fields = (page) => page.evaluate(() => ({
  date: document.getElementById('date').value,
  time: document.getElementById('time').value,
  unknown: document.getElementById('time-unknown').getAttribute('aria-pressed') === 'true',
  timeOff: document.getElementById('time').disabled,
  location: document.getElementById('location').value,
}));

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / first chart`, { concurrency: false }, () => {
    const check = (name, run, options) => it(name, { timeout: 120000 }, () => withPage(profile, run, options));

    check('without its time, the form opens what the date and place settle: the hour open, and each change of the day', async (page) => {
      const asked = chartsAskedFor(page);
      await visit(page, { lang: 'en' });
      await page.locator('#date').fill(BIRTH.date);
      await page.locator('#time').fill(BIRTH.time);
      await page.locator('#time-unknown').click();
      assert.deepEqual(await fields(page), { date: BIRTH.date, time: '', unknown: true, timeOff: true, location: '' });
      await page.locator('#location').fill(CHENGDU.city);
      await page.locator('.location-suggestion').click();
      await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
      await page.locator('#create-chart-btn').click();
      await firstDrawn(page);
      await settled(page);
      // It opens at its top, wherever the form was scrolled to.
      assert.equal(await page.evaluate(() => scrollY), 0);
      const api = await firstChart(page);
      // Chengdu keeps Beijing's clock, an hour ahead of its sun: the day pillar changes
      // during the date, at true solar midnight.
      assert.ok(api.changes.some((change) => change.pillar === 'day'), JSON.stringify(api.changes));
      const dayChange = api.changes.find((change) => change.pillar === 'day');
      const [, at, offset] = dayChange.at.match(/^(\d{2}:\d{2}:\d{2})([+-]\d{2}:\d{2})$/);
      const found = await shown(page);
      assert.deepEqual(found, {
        time: 'unknown',
        heading: 'February 4, 1988 · time unknown · Chengdu',
        lead: 'Without the birth time the hour pillar stays open, and so do the luck pillars and the days, which need it.',
        pillars: [['hour', 'Open'], ...ORDER.slice(1).map((name) => [name, named(api.pillars[name])])],
        changes: api.changes.map((change) => {
          const [, time, zone] = change.at.match(/^(\d{2}:\d{2}:\d{2})([+-]\d{2}:\d{2})$/);
          const pillar = { day: 'Day', month: 'Month', year: 'Year' }[change.pillar];
          return `The ${pillar} pillar changes at ${time} (UTC${zone}). Born before then: ${named(change.before)}; from then on: ${named(change.after)}. The cards show ${named(api.pillars[change.pillar])}.`;
        }),
        dayMaster: `Day Master · ${api.day_master.pinyin} — ${api.day_master.polarity} ${api.day_master.element[0].toUpperCase()}${api.day_master.element.slice(1)}`,
        note: `This is the Day Master of a birth from ${at} (UTC${offset}) on; before then it is ${dayChange.before.stem.pinyin} ${dayChange.before.stem.chinese} — ${dayChange.before.stem.polarity} ${dayChange.before.stem.element[0].toUpperCase()}${dayChange.before.stem.element.slice(1)}.`,
        offer: false,
        overflow: false,
      });
      assert.equal(await page.title(), 'February 4, 1988 · time unknown · Chengdu — Eightchord');
      // Its core passage reads in full, as on eightchord.com.
      assert.equal(await page.locator('#first-passage .canon-line-toggle').getAttribute('aria-expanded'), 'true');
      assert.equal(await page.locator('#first-passage .canon-line-key').textContent(), api.day_master.title);
      assert.deepEqual(asked, [], 'no whole chart is asked for');
      // A reload shows it again, from its address.
      await page.reload();
      await firstDrawn(page);
      assert.deepEqual((await shown(page)).pillars, found.pillars);
      // Edit finds the birth in the form, its time still unknown; the choice unticked
      // gives the time field back.
      await page.locator('#first-edit').click();
      await page.locator('#input-view').waitFor({ state: 'visible' });
      assert.deepEqual(await fields(page), { date: BIRTH.date, time: '', unknown: true, timeOff: true, location: CHENGDU.display });
      assert.equal(await page.locator('#first-view').isVisible(), false);
      await page.locator('#time-unknown').click();
      assert.equal(await page.locator('#time').isDisabled(), false);
      assert.equal(await page.locator('#time-unknown').getAttribute('aria-pressed'), 'false');
    });

    check('a visitor\'s link opens the birth\'s first chart, and its offer signs up for the whole chart', async (page) => {
      const asked = chartsAskedFor(page);
      await visit(page, { lang: 'en', address: `#chart?${link(BIRTH.date, BIRTH.time, 'en')}` });
      await firstDrawn(page);
      await settled(page);
      const api = await firstChart(page, BIRTH.time);
      const found = await shown(page);
      assert.deepEqual(found.pillars, ORDER.map((name) => [name, named(api.pillars[name])]));
      assert.deepEqual([found.heading, found.lead, found.changes, found.note, found.offer, found.overflow],
        ['February 4, 1988 · 16:30 · Chengdu', 'Your first chart, without an account.', [], null, true, false]);
      assert.equal(await text(page, '#first-offer-text'), 'The whole chart opens with a free account: its relationships, roles, luck pillars and days.');
      assert.equal(await text(page, '#first-account'), 'Create my free account');
      assert.deepEqual(asked, [], 'no whole chart is asked for without an account');
      // Closed without signing up, the dialog leaves the first chart as it was.
      await page.locator('#first-account').click();
      await dialogOpens(page);
      assert.equal(await text(page, '#account-title'), 'Create a free account');
      await page.keyboard.press('Escape');
      await page.waitForFunction(() => !document.getElementById('account-dialog').open);
      assert.equal(await page.locator('#first-view').isVisible(), true);
      assert.equal(await page.locator('#form-error').isVisible(), false);
      // Signed up, the whole chart of the link opens.
      await page.locator('#first-account').click();
      await dialogOpens(page);
      const email = newAddress('first');
      await sendCode(page, email, 'en');
      await enterCode(page, email);
      await page.locator('#chart-view:not(.hidden) #pillars .card').first().waitFor();
      await settled(page);
      assert.equal(await page.locator('#first-view').isVisible(), false);
      assert.equal(asked.length, 1);
      assert.deepEqual([asked[0].date, asked[0].time], [BIRTH.date, BIRTH.time]);
    }, { signedIn: false });

    check('a visitor\'s link without the time opens the first chart of its date and place, and says the whole chart needs the time too', async (page) => {
      // As eightchord.com links a visitor who gave no birth time.
      await visit(page, { lang: 'en', address: `#chart?${link(BIRTH.date, 'unknown', 'en')}` });
      await firstDrawn(page);
      const api = await firstChart(page);
      const found = await shown(page);
      assert.deepEqual(found.pillars, [['hour', 'Open'], ...ORDER.slice(1).map((name) => [name, named(api.pillars[name])])]);
      assert.deepEqual([found.lead, found.offer], [
        'Your first chart, without an account. Without the birth time the hour pillar stays open.', true]);
      assert.equal(await text(page, '#first-offer-text'),
        'The whole chart opens with a free account and the birth time: its relationships, roles, luck pillars and days.');
    }, { signedIn: false });

    check('the first chart reads the Zi-hour convention its link names, as the whole chart does', async (page) => {
      // 00:30 on Beijing's clock in Chengdu is 23:13 true solar time the evening before:
      // with the whole Zi hour, already the next day.
      const whole = new URLSearchParams(link(BIRTH.date, '00:30', 'en'));
      whole.set('zi', 'whole_zi_23');
      await visit(page, { lang: 'en', address: `#chart?${whole}` });
      await firstDrawn(page);
      const response = await page.request.post(new URL('/api/first_chart', process.env.EC_BASE_URL).href, {
        data: { date: BIRTH.date, time: '00:30', location: LOCATION, conventions: { zi_convention: 'whole_zi_23' } },
      });
      assert.equal(response.status(), 200);
      const api = await response.json();
      assert.equal(named(api.pillars.day), '己丑 Ji Chou');
      assert.deepEqual((await shown(page)).pillars, ORDER.map((name) => [name, named(api.pillars[name])]));
    }, { signedIn: false });

    check('a chart made from the form opens at its top, wherever the form was scrolled to', async (page) => {
      await visit(page, { lang: 'en' });
      await page.locator('#date').fill(BIRTH.date);
      await page.locator('#time').fill(BIRTH.time);
      await page.locator('#location').fill(CHENGDU.city);
      await page.locator('.location-suggestion').click();
      await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
      await page.locator('#create-chart-btn').click();
      await page.locator('#chart-view:not(.hidden) #pillars .card').first().waitFor();
      await settled(page);
      assert.equal(await page.evaluate(() => scrollY), 0);
    });

    check('a link without the time opens no day, no comparison and no topic, and the form keeps its birth', async (page) => {
      const unknown = link(BIRTH.date, 'unknown', 'en');
      await visit(page, { lang: 'en' });
      for (const [address, why] of [
        [`#today?${unknown}&day=2026-10-11`, 'the day needs the birth time'],
        [`#compare?${new URLSearchParams({ a: unknown.toString() })}`, 'Chart 1 needs the birth time'],
        [`#chart?${unknown}&display=ten-gods`, 'what the cards show is not valid'],
        [`#chart?${unknown}&topic=season`, 'the open topic is not valid'],
      ]) {
        await page.goto(new URL(`/${address}`, process.env.EC_BASE_URL).href);
        await page.waitForFunction((why) => document.getElementById('form-error').textContent.endsWith(`${why}.`), why);
        assert.equal(await text(page, '#form-error'), `This link does not open a chart: ${why}.`, address);
        assert.equal(await page.locator('#first-view').isVisible(), false, address);
        if (!address.startsWith('#compare')) {
          assert.deepEqual(await fields(page), { date: BIRTH.date, time: '', unknown: true, timeOff: true, location: CHENGDU.display }, address);
        }
      }
    });

    check('a birth saved or compared takes its time: the choice is not offered there', async (page) => {
      await visit(page, { lang: 'en', address: `#compare?${new URLSearchParams({ a: link(BIRTH.date, BIRTH.time, 'en').toString() })}` });
      await page.locator('#compare-note').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#time-unknown').isVisible(), false);
      await page.goto(new URL('/#save?as=mine', process.env.EC_BASE_URL).href);
      await page.locator('#save-note').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#time-unknown').isVisible(), false);
      // The plain form offers it again.
      await page.locator('#save-cancel').click();
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await page.locator('#input-view').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#time-unknown').isVisible(), true);
    });
  });
}
