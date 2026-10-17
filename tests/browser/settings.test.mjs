// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Settings: what the account keeps (docs/Standard-Settings.md): its saved charts, your
// own among them, the couples they form, where you are and the schools. Every change is
// the API's, made with the account's key and the settings it was made from; one made
// from settings another tab has changed since is refused, and the page shows the
// settings as they are. The library in a chart's heading saves and opens charts.
import {
  assert, describe, it, engineName, profiles, openLink, settled, withPage, playwright, HELSINKI, TROMSO, press,
} from './chart-helpers.mjs';
import { newAccount, asAccount, signInPage, stubTurnstile } from './account-helpers.mjs';
import { dialogOpens, signInThroughDialog } from './account-page.mjs';

const PLACE = {
  name: HELSINKI.display, city: HELSINKI.city, timezone: HELSINKI.timezone,
  latitude: HELSINKI.latitude, longitude: HELSINKI.longitude,
};
// A made-up birth, of nobody, and its chart's link.
const BIRTH = { date: '1988-11-02', time: '21:05:30', gender: 'male' };
const chartLink = (parts = {}) => `/#chart?${new URLSearchParams({
  date: BIRTH.date, time: BIRTH.time, place: HELSINKI.display, city: HELSINKI.city,
  latitude: String(HELSINKI.latitude), longitude: String(HELSINKI.longitude), timezone: HELSINKI.timezone,
  lang: 'en', gender: BIRTH.gender, ...parts,
})}`;

const read = (page) => page.evaluate(async () => (await fetch('/api/account/settings')).json());
// A change made elsewhere, as another tab makes it, from the settings as they are now:
// its answer.
async function changeElsewhere(page, method, path, body) {
  const { status, value } = await page.evaluate(async ({ method, path, body }) => {
    const now = await (await fetch('/api/account/settings')).json();
    const response = await fetch(path, {
      method, headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...body, key: now.key, updated_at: now.updated_at }),
    });
    return { status: response.status, value: await response.json() };
  }, { method, path, body });
  assert.ok(status === 200 || status === 201, `${method} ${path}: ${status}`);
  return value;
}
// A birth saved elsewhere: its id.
const saveElsewhere = async (page, birth, more = {}) => (await changeElsewhere(page, 'POST', '/api/account/charts', { ...birth, ...more })).saved;
// The account starts from nothing kept: no saved chart, no place, the default schools.
// The page ends on the start page: your chart, if one was marked before, may have opened
// at the bare address.
async function reset(page) {
  await page.goto(new URL('/', process.env.EC_BASE_URL).href);
  for (const chart of (await read(page)).charts) await changeElsewhere(page, 'DELETE', `/api/account/charts/${chart.id}`, {});
  await changeElsewhere(page, 'DELETE', '/api/account/place', {});
  await changeElsewhere(page, 'PATCH', '/api/account/schools', { favourable: null, season: null, transits: null });
  await page.goto(new URL('/', process.env.EC_BASE_URL).href);
  await page.locator('#input-view').waitFor({ state: 'visible' });
}
// Another address in the same page, as the page's own links go there.
const goTo = (page, hash) => page.evaluate((hash) => {
  history.pushState(null, '', hash);
  dispatchEvent(new PopStateEvent('popstate'));
}, hash);
const partnerNamed = (name, date = '1975-08-14') => ({ name, date, time: '07:45', place: PLACE, gender: 'female', zi: 'split_midnight' });
// The chart on screen, as the library keeps it.
const SCREEN = { date: BIRTH.date, time: BIRTH.time, place: PLACE, gender: BIRTH.gender, zi: 'split_midnight' };
const nameOnScreen = (page) => page.locator('#library-btn .library-label').textContent();
async function openLibrary(page) {
  await page.locator('#library-btn').click();
  await page.locator('#library-dialog').waitFor({ state: 'visible' });
  await page.waitForFunction(() => !document.getElementById('library-dialog').hasAttribute('aria-busy'));
}
// The charts a list offers, by name, in its order.
const offered = (page, select) => page.locator(`${select} option`).evaluateAll((items) => items.map((item) => item.textContent.split(' · ')[0]));
async function openSettings(page) {
  await page.goto(new URL('/#settings', process.env.EC_BASE_URL).href);
  await page.locator('#settings-view').waitFor({ state: 'visible' });
  await page.waitForFunction(() => !document.getElementById('settings-view').hasAttribute('aria-busy'));
  await settled(page);
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / settings`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 120000 }, () => withPage(profile, run));

    check('Settings opens from the account menu with the schools the API lists, the default marked in words', async (page) => {
      await reset(page);
      await page.locator('#account-btn').click();
      await page.locator('#account-settings').click();
      await page.locator('#settings-view').waitFor({ state: 'visible' });
      await page.waitForFunction(() => !document.getElementById('settings-view').hasAttribute('aria-busy'));
      assert.equal(await page.evaluate(() => location.hash), '#settings');
      const catalog = await page.evaluate(async () => (await fetch('/api/schools')).json());
      for (const setting of catalog.settings) {
        const group = page.locator(`fieldset[data-setting="${setting.id}"]`);
        assert.equal(await group.locator('legend').textContent(), setting.name.en);
        assert.deepEqual(await group.locator('input[type="radio"]').evaluateAll((radios) => radios.map((radio) => radio.value)),
          setting.presets.map((preset) => preset.id));
        const preset = setting.presets.find((p) => p.default);
        assert.equal(await group.locator('input:checked').getAttribute('value'), preset.id);
        assert.match(await group.locator(`label[for="settings-${setting.id}-${preset.id}"]`).textContent(), /\(default\)/);
      }
      assert.equal(await page.locator('fieldset[data-setting="favourable"] input[value="structure"]').count(), 0);
      assert.match(await page.locator('#settings-place-now').textContent(), /No place is set/);
      assert.match(await page.locator('#settings-mine-body').textContent(), /No chart is marked as yours/);
      assert.match(await page.locator('#settings-couples-body').textContent(), /No couples/);
      assert.match(await page.locator('#settings-charts-body').textContent(), /No saved charts/);
      // Close goes back to the page it was opened from.
      await page.locator('#settings-close').click();
      await page.locator('#input-view').waitFor({ state: 'visible' });
    });

    check('where you are is searched, saved and removed', async (page) => {
      await reset(page);
      await page.route('**/api/location_suggest', (route) => route.fulfill({ json: { suggestions: [HELSINKI] } }));
      await openSettings(page);
      assert.equal(await page.locator('#settings-place-save').isDisabled(), true);
      await page.locator('#settings-location').fill('Helsinki');
      await page.locator('#settings-location-suggestions .location-suggestion').click();
      assert.equal(await page.locator('#settings-place-save').isDisabled(), false);
      // Saved and removed from the keyboard: each button, then unavailable, hands its
      // focus to the search.
      await page.locator('#settings-place-save').focus();
      await page.keyboard.press('Enter');
      await page.waitForFunction(() => document.getElementById('settings-place-now').textContent.startsWith('Now:'));
      assert.deepEqual((await read(page)).place, {
        name: HELSINKI.display, city: HELSINKI.city, timezone: HELSINKI.timezone,
        latitude: HELSINKI.latitude, longitude: HELSINKI.longitude,
      });
      await page.waitForFunction(() => document.activeElement?.id === 'settings-location');
      await page.locator('#settings-place-remove').focus();
      await page.keyboard.press('Enter');
      await page.waitForFunction(() => document.getElementById('settings-place-now').textContent.startsWith('No place'));
      assert.equal((await read(page)).place, null);
      assert.equal(await page.locator('#settings-place-remove').isHidden(), true);
      assert.equal(await page.evaluate(() => document.activeElement?.id), 'settings-location');
    });

    check('a showing that ends late changes nothing of a later one, its failure included', async (page) => {
      await reset(page);
      // The first showing's list of schools is held on its way.
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      let holding = true;
      const lists = [];
      page.on('response', (response) => {
        if (new URL(response.url()).pathname === '/api/schools') lists.push(response.status());
      });
      await page.route('**/api/schools', async (route) => {
        if (holding) {
          holding = false;
          await held;
        }
        await route.fallback();
      });
      await page.goto(new URL('/#settings', process.env.EC_BASE_URL).href);
      await page.locator('#settings-view').waitFor({ state: 'visible' });
      // Closed, and opened again from the account menu, now unable to read the settings.
      await page.locator('#settings-close').click();
      await page.route('**/api/account/settings', (route) => route.fulfill({ status: 500, json: { detail: 'Stopped by the test.' } }));
      await page.locator('#account-btn').click();
      await page.locator('#account-settings').click();
      await page.locator('#settings-status').waitFor({ state: 'visible' });
      release();
      for (let tries = 0; lists.length < 2 && tries < 100; tries += 1) await page.waitForTimeout(50);
      assert.equal(lists.length, 2, 'the first showing has its answer');
      await page.evaluate(() => new Promise((resolve) => { setTimeout(resolve, 0); }));
      assert.equal(await page.locator('#settings-status').textContent(), 'Stopped by the test.');
      assert.equal(await page.locator('#settings-schools-body input').count(), 0);
      assert.equal(await page.locator('#settings-view').getAttribute('aria-busy'), null);
    });

    check('a chart saved elsewhere since Settings were drawn is not removed from their old controls', async (page) => {
      await reset(page);
      await saveElsewhere(page, partnerNamed('First'));
      await openLink(page, chartLink(), { place: HELSINKI });
      await goTo(page, '#settings');
      await page.locator('#settings-view').waitFor({ state: 'visible' });
      await page.waitForFunction(() => !document.getElementById('settings-view').hasAttribute('aria-busy'));
      assert.match(await page.locator('#settings-charts-body').textContent(), /First/);
      // Back on the chart, whose library reads the settings: another chart was saved elsewhere.
      await page.goBack();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await saveElsewhere(page, partnerNamed('Second', '1976-03-02'));
      await openLibrary(page);
      assert.equal(await page.locator('#library-list .library-chart').count(), 2);
      await page.locator('#library-close').click();
      // Settings opened again cannot read the settings: the old controls are still there.
      const refuse = (route) => route.fulfill({ status: 500, json: { detail: 'Stopped by the test.' } });
      await page.route('**/api/account/settings', refuse);
      await goTo(page, '#settings');
      await page.locator('#settings-status').waitFor({ state: 'visible' });
      assert.doesNotMatch(await page.locator('#settings-charts-body').textContent(), /Second/);
      const remove = page.locator('#settings-charts-body [data-settings-action="remove"]');
      await remove.click();
      await remove.click();
      await page.waitForFunction(() => document.getElementById('settings-status').textContent.includes('changed elsewhere'));
      await page.unroute('**/api/account/settings', refuse);
      assert.deepEqual((await read(page)).charts.map((chart) => chart.name), ['First', 'Second'], 'nothing was removed unseen');
      await page.waitForFunction(() => document.getElementById('settings-charts-body').textContent.includes('Second'));
    });

    check('Open, on Settings drawn before a removal read elsewhere, opens the chart they show', async (page) => {
      await reset(page);
      const first = await saveElsewhere(page, partnerNamed('First'));
      await openLink(page, chartLink(), { place: HELSINKI });
      await goTo(page, '#settings');
      await page.locator('#settings-view').waitFor({ state: 'visible' });
      await page.waitForFunction(() => !document.getElementById('settings-view').hasAttribute('aria-busy'));
      await page.goBack();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      // Removed elsewhere, and read so by the chart's library.
      await changeElsewhere(page, 'DELETE', `/api/account/charts/${first}`, {});
      await openLibrary(page);
      assert.match(await page.locator('#library-list').textContent(), /No saved charts yet/);
      await page.locator('#library-close').click();
      const refuse = (route) => route.fulfill({ status: 500, json: { detail: 'Stopped by the test.' } });
      await page.route('**/api/account/settings', refuse);
      await goTo(page, '#settings');
      await page.locator('#settings-status').waitFor({ state: 'visible' });
      await page.locator('#settings-charts-body [data-settings-action="open"]').click();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      assert.equal(await page.evaluate(() => new URLSearchParams(location.hash.split('?')[1]).get('date')), '1975-08-14');
      await page.unroute('**/api/account/settings', refuse);
    });

    check('Save the chart on screen is made from the settings its dialog read', async (page) => {
      await reset(page);
      await openLink(page, chartLink(), { place: HELSINKI });
      await openLibrary(page);
      await page.locator('#library-save').click();
      await page.locator('#save-chart-dialog').waitFor({ state: 'visible' });
      // Another chart saved elsewhere meanwhile: the save is refused, and made again from
      // the settings read since.
      await saveElsewhere(page, partnerNamed('Elsewhere'));
      await page.locator('#save-chart-save').click();
      await page.waitForFunction(() => document.getElementById('save-chart-status').textContent !== '');
      assert.match(await page.locator('#save-chart-status').textContent(), /changed elsewhere/);
      assert.deepEqual((await read(page)).charts.map((chart) => chart.name), ['Elsewhere'], 'nothing was saved unseen');
      await page.locator('#save-chart-save').click();
      await page.locator('#save-chart-dialog').waitFor({ state: 'hidden' });
      const kept = (await read(page)).charts.at(-1);
      assert.equal(kept.date, BIRTH.date);
      assert.equal(kept.name, null);
      await page.waitForFunction(() => document.getElementById('library-btn').dataset.saved === 'true');
      assert.equal(await nameOnScreen(page), 'Unnamed chart');
    });

    check('a place picked while the settings cannot be read is not saved, and the page says why', async (page) => {
      await reset(page);
      await page.route('**/api/location_suggest', (route) => route.fulfill({ json: { suggestions: [HELSINKI] } }));
      const refuse = (route) => route.fulfill({ status: 500, json: { detail: 'Stopped by the test.' } });
      await page.route('**/api/account/settings', refuse);
      await page.goto(new URL('/#settings', process.env.EC_BASE_URL).href);
      await page.locator('#settings-status').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#settings-status').textContent(), 'Stopped by the test.');
      await page.locator('#settings-location').fill('Helsinki');
      await page.locator('#settings-location-suggestions .location-suggestion').click();
      await page.locator('#settings-place-save').click();
      await page.waitForFunction(() => document.getElementById('settings-status').textContent === 'The settings could not be loaded.');
      assert.equal(await page.locator('#settings-status').isVisible(), true);
      await page.unroute('**/api/account/settings', refuse);
      assert.equal((await read(page)).place, null);
    });

    check('a place picked while the one before is saved stays picked', async (page) => {
      await reset(page);
      await page.route('**/api/location_suggest', (route) => route.fulfill({ json: { suggestions: [HELSINKI, TROMSO] } }));
      // The save is held on its way until the next place is picked.
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      await page.route('**/api/account/place', async (route) => {
        if (route.request().method() === 'PUT') await held;
        await route.fallback();
      });
      await openSettings(page);
      await page.locator('#settings-location').fill('Hel');
      await page.locator('#settings-location-suggestions .location-suggestion').first().click();
      await page.locator('#settings-place-save').click();
      await page.locator('#settings-location').fill('Tro');
      await page.locator('#settings-location-suggestions .location-suggestion').nth(1).click();
      release();
      await page.waitForFunction(() => document.getElementById('settings-place-now').textContent.startsWith('Now:'));
      assert.equal((await read(page)).place.city, HELSINKI.city);
      assert.equal(await page.locator('#settings-location').inputValue(), TROMSO.display);
      assert.equal(await page.locator('#settings-place-save').isDisabled(), false);
    });

    check('a school is chosen, and choosing the default follows it again', async (page) => {
      await reset(page);
      await openSettings(page);
      await page.locator('#settings-favourable-climate').check();
      await page.waitForFunction(async () => (await (await fetch('/api/account/settings')).json()).chosen.favourable === 'climate');
      await page.locator('#settings-favourable-support').check();
      await page.waitForFunction(async () => (await (await fetch('/api/account/settings')).json()).chosen.favourable === null);
      assert.equal((await read(page)).schools.favourable, 'support');
    });

    check('changes made before the last is answered follow one another, and focus stays on the preset', async (page) => {
      await reset(page);
      await openSettings(page);
      // Each change is slow to reach the server, so the next is made before it is answered.
      const answered = [];
      let bothAnswered;
      const both = new Promise((resolve) => { bothAnswered = resolve; });
      page.on('response', (response) => {
        if (new URL(response.url()).pathname !== '/api/account/schools') return;
        answered.push(response.status());
        if (answered.length === 2) bothAnswered();
      });
      await page.route('**/api/account/schools', async (route) => {
        await new Promise((resolve) => setTimeout(resolve, 400));
        await route.fallback();
      });
      // Arrowing through a school's presets: each one passed is a change.
      await page.evaluate(() => { window.__drawn = document.getElementById('settings-favourable-support'); });
      await page.locator('#settings-favourable-support').focus();
      await page.keyboard.press('ArrowDown');
      await page.keyboard.press('ArrowUp');
      await both;
      assert.deepEqual(answered, [200, 200], 'neither change was refused');
      // Drawn again once both are answered, with focus on the preset it was on.
      await page.waitForFunction(() => document.getElementById('settings-favourable-support') !== window.__drawn);
      assert.equal(await page.evaluate(() => document.activeElement?.id), 'settings-favourable-support');
      assert.equal(await page.locator('#settings-status').isHidden(), true);
      assert.equal((await read(page)).chosen.favourable, null, 'the last change decides');
      assert.equal(await page.locator('input[name="settings-favourable"]:checked').getAttribute('value'), 'support');
    });

    check('a change made from settings another tab has changed since is refused, and the page shows them as they are', async (page) => {
      await reset(page);
      await openSettings(page);
      await changeElsewhere(page, 'PATCH', '/api/account/schools', { transits: 'whole' });
      await page.locator('#settings-season-months').check();
      await page.locator('#settings-status').waitFor({ state: 'visible' });
      assert.match(await page.locator('#settings-status').textContent(), /changed elsewhere/);
      const now = await read(page);
      assert.equal(now.chosen.season, null, 'the change was not made');
      assert.equal(now.chosen.transits, 'whole');
      assert.equal(await page.locator('input[name="settings-transits"]:checked').getAttribute('value'), 'whole');
      assert.equal(await page.locator('input[name="settings-season"]:checked').getAttribute('value'), 'eighteen');
      // Chosen again, the change is made from the settings now shown, and keeps the other's.
      await page.locator('#settings-season-months').click();
      await page.waitForFunction(async () => (await (await fetch('/api/account/settings')).json()).chosen.season === 'months');
      assert.equal((await read(page)).chosen.transits, 'whole');
      await page.waitForFunction(() => document.getElementById('settings-status').classList.contains('hidden'));
    });

    check('the chart on screen is saved, named as text; the library opens it, and Settings removes it', async (page) => {
      await reset(page);
      await openLink(page, chartLink(), { place: HELSINKI });
      await page.waitForFunction(() => document.getElementById('library-btn').dataset.saved === 'false');
      assert.equal(await nameOnScreen(page), 'Unsaved chart');
      await openLibrary(page);
      assert.match(await page.locator('#library-list').textContent(), /No saved charts yet/);
      await page.locator('#library-save').click();
      await page.locator('#save-chart-dialog').waitFor({ state: 'visible' });
      const name = 'Saved <img src=x onerror=window.__named=1>';
      await page.locator('#save-chart-name').fill(name);
      await page.locator('#save-chart-save').click();
      await page.locator('#save-chart-dialog').waitFor({ state: 'hidden' });
      const kept = (await read(page)).charts.at(-1);
      assert.equal(kept.name, name);
      assert.deepEqual([kept.date, kept.time, kept.gender, kept.zi, kept.place.city],
        [BIRTH.date, BIRTH.time, BIRTH.gender, 'split_midnight', HELSINKI.city]);
      await page.waitForFunction((name) => document.querySelector('#library-btn .library-label').textContent === name, name);
      // Saved once: the library offers no second save, and marks the chart on screen.
      await openLibrary(page);
      assert.equal(await page.locator('#library-save').isHidden(), true);
      assert.equal(await page.locator('#library-list [aria-current="true"] .saved-name').textContent(), name);
      assert.equal(await page.evaluate(() => window.__named), undefined, 'a name is text');
      await page.keyboard.press('Escape');
      await page.locator('#library-dialog').waitFor({ state: 'hidden' });
      assert.equal(await page.evaluate(() => document.activeElement?.id), 'library-btn');
      await openSettings(page);
      const card = page.locator(`#settings-charts-body .saved-card[data-chart="${kept.id}"]`);
      assert.equal(await card.locator('.saved-name').textContent(), name);
      // Its pillars, year first, each character with its pinyin.
      const tiles = await card.locator('.saved-glyph').evaluateAll((items) => items.map((item) => [
        item.querySelector('.saved-char').textContent, item.querySelector('.saved-pinyin').textContent,
      ]));
      assert.deepEqual(tiles, ['year', 'month', 'day', 'hour'].flatMap((p) => [
        [kept.pillars[p].stem.chinese, kept.pillars[p].stem.pinyin],
        [kept.pillars[p].branch.chinese, kept.pillars[p].branch.pinyin],
      ]));
      await card.locator('[data-settings-action="open"]').click();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      assert.equal(await page.evaluate(() => new URLSearchParams(location.hash.split('?')[1]).get('date')), BIRTH.date);
      await openSettings(page);
      // Removed from the keyboard, asked once more on the button itself.
      await page.locator('#settings-charts-body [data-settings-action="remove"]').focus();
      await page.keyboard.press('Enter');
      assert.match(await page.locator('#settings-charts-body [data-settings-action="remove"]').textContent(), /^Remove .*\?$/);
      await page.keyboard.press('Enter');
      await page.waitForFunction(() => document.getElementById('settings-charts-body').textContent.includes('No saved charts'));
      assert.deepEqual((await read(page)).charts, []);
    });

    check('a chart renamed in Settings keeps its birth, and the heading takes the name', async (page) => {
      await reset(page);
      const id = await saveElsewhere(page, SCREEN);
      await openSettings(page);
      await page.locator(`#settings-charts-body [data-settings-action="rename"][data-chart="${id}"]`).click();
      await page.locator(`#settings-rename-${id}`).fill('Renamed');
      await page.keyboard.press('Enter');
      await page.waitForFunction(() => document.getElementById('settings-charts-body').textContent.includes('Renamed'));
      const kept = (await read(page)).charts.at(-1);
      assert.deepEqual([kept.id, kept.name, kept.date, kept.time], [id, 'Renamed', BIRTH.date, BIRTH.time]);
      assert.equal(await page.evaluate((id) => document.activeElement?.dataset.chart, id), id);
      await openLink(page, chartLink(), { place: HELSINKI });
      await page.waitForFunction(() => document.querySelector('#library-btn .library-label').textContent === 'Renamed');
    });

    check('my chart is marked, a partner is added as a new birth and paired at once, and the couple ends', async (page) => {
      await reset(page);
      await page.route('**/api/location_suggest', (route) => route.fulfill({ json: { suggestions: [HELSINKI] } }));
      const mine = await saveElsewhere(page, SCREEN);
      await openSettings(page);
      await page.locator('#settings-mine-choice').selectOption(mine);
      await page.locator('[data-settings-action="mark"]').click();
      await page.waitForFunction(() => document.getElementById('settings-mine-body').textContent.includes('Your chart'));
      assert.equal((await read(page)).my_chart, mine);
      // A partner for my chart, as a new birth: the form, saying what it saves.
      await page.locator('#settings-partner-of').selectOption(mine);
      await page.locator('[data-settings-action="add-partner"]').click();
      await page.locator('#save-note').waitFor({ state: 'visible' });
      assert.match(await page.evaluate(() => location.hash), /^#save\?as=partner&with=/);
      assert.match(await page.locator('#save-note-text').textContent(), /paired with Unnamed chart/);
      await page.locator('#save-name').fill('New partner');
      await page.locator('#date').fill('1988-11-02');
      await page.locator('#time').fill('21:05');
      await page.locator('#location').fill('Helsinki');
      await page.locator('#location-suggestions .location-suggestion').click();
      // Without a gender the form says so, and saves nothing.
      await page.locator('#create-chart-btn').click();
      await page.waitForFunction(() => document.getElementById('form-error').textContent.includes('gender'));
      assert.equal((await read(page)).charts.length, 1);
      await page.locator('.gender-option input[value="male"]').check();
      await page.locator('#create-chart-btn').click();
      await page.locator('#settings-view').waitFor({ state: 'visible' });
      assert.equal(await page.evaluate(() => location.hash), '#settings');
      const now = await read(page);
      const partner = now.charts.find((chart) => chart.name === 'New partner');
      assert.deepEqual(now.couples.map((couple) => couple.charts), [[mine, partner.id]]);
      await page.waitForFunction(() => document.getElementById('settings-couples-body').textContent.includes('New partner'));
      // Ended, both charts stay saved.
      await page.locator('[data-settings-action="end"]').click();
      await page.waitForFunction(() => document.getElementById('settings-couples-body').textContent.includes('No couples'));
      const after = await read(page);
      assert.deepEqual(after.couples, []);
      assert.equal(after.charts.length, 2);
    });

    check('a chart in several couples, as #96 will keep them: every partner named, past three as so many more, and removal naming each couple', async (page) => {
      await reset(page);
      const mine = await saveElsewhere(page, { ...SCREEN, name: 'Mine' });
      const partners = [];
      for (const [index, name] of ['First', null, 'Third', 'Fourth'].entries()) {
        partners.push(await saveElsewhere(page, { ...partnerNamed(name, `198${index}-01-02`), name }));
      }
      await changeElsewhere(page, 'PUT', '/api/account/my-chart', { chart: mine });
      await changeElsewhere(page, 'POST', '/api/account/couples', { charts: [mine, partners[0]] });
      // The other couples, as #96's release keeps them: this release reads them, and
      // cannot pair them yet.
      const extra = partners.slice(1).map((id, index) => ({ id: `${'a'.repeat(31)}${index}`, charts: [id, mine] }));
      await page.route('**/api/account/settings', async (route) => {
        if (route.request().method() !== 'GET') return route.fallback();
        const response = await route.fetch();
        const value = await response.json();
        return route.fulfill({ response, json: { ...value, couples: [...value.couples, ...extra] } });
      });
      await openSettings(page);
      // My chart names every partner in the order paired, an unnamed one by its birth
      // date, and past three says how many more.
      const marks = await page.locator(`#settings-charts-body .saved-card[data-chart="${mine}"] .saved-head`).textContent();
      assert.ok(marks.includes('Couple with First, an unnamed chart (born January 2, 1981), Third, and 1 more'), marks);
      // Each partner names my chart; each couple has its own card.
      assert.match(await page.locator(`#settings-charts-body .saved-card[data-chart="${partners[3]}"] .saved-head`).textContent(), /Couple with Mine/);
      assert.equal(await page.locator('#settings-couples-body .couple-card').count(), 4);
      // Removing my chart names each couple it ends.
      const remove = page.locator(`#settings-charts-body [data-settings-action="remove"][data-chart="${mine}"]`);
      await remove.click();
      assert.equal(await remove.textContent(), 'Remove Mine? It is your chart, and its couples with First, an unnamed chart (born January 2, 1981), Third, and 1 more end too.');
      // My chart is paired with every other: Pair offers the others, and never pairs one
      // with my chart again.
      assert.deepEqual(await offered(page, '#settings-pair-first'), ['First', 'Unnamed chart', 'Third', 'Fourth']);
      assert.deepEqual(await offered(page, '#settings-pair-second'), ['Unnamed chart', 'Third', 'Fourth']);
    });

    check('Pair: the second list follows the first, without the chart or its partners; with no pair left the page says so, and a new birth can still be a partner', async (page) => {
      await reset(page);
      await page.route('**/api/location_suggest', (route) => route.fulfill({ json: { suggestions: [HELSINKI] } }));
      const mine = await saveElsewhere(page, { ...SCREEN, name: 'Mine' });
      const first = await saveElsewhere(page, partnerNamed('First', '1980-01-02'));
      const second = await saveElsewhere(page, partnerNamed('Second', '1981-01-02'));
      await changeElsewhere(page, 'PUT', '/api/account/my-chart', { chart: mine });
      await changeElsewhere(page, 'POST', '/api/account/couples', { charts: [mine, first] });
      await openSettings(page);
      // The first list starts at my chart; the second offers what it can pair with.
      assert.deepEqual(await offered(page, '#settings-pair-first'), ['Mine', 'First', 'Second']);
      assert.equal(await page.locator('#settings-pair-first').inputValue(), mine);
      assert.deepEqual(await offered(page, '#settings-pair-second'), ['Second']);
      // Another first: the second list follows it, and the first keeps focus.
      await page.locator('#settings-pair-first').focus();
      await page.locator('#settings-pair-first').selectOption(second);
      assert.deepEqual(await offered(page, '#settings-pair-second'), ['Mine', 'First']);
      assert.equal(await page.evaluate(() => document.activeElement?.id), 'settings-pair-first');
      await page.locator('#settings-pair-first').selectOption(first);
      assert.deepEqual(await offered(page, '#settings-pair-second'), ['Second']);
      // Paired from the lists: my chart is in two couples now.
      await page.locator('#settings-pair-first').selectOption(second);
      await page.locator('#settings-pair-second').selectOption(mine);
      await page.locator('[data-settings-action="pair"]').click();
      await page.waitForFunction(() => document.querySelectorAll('#settings-couples-body .couple-card').length === 2);
      assert.deepEqual((await read(page)).couples.map((couple) => couple.charts), [[mine, first], [second, mine]]);
      // My chart is paired with every other now: the lists start at the first chart left.
      assert.deepEqual(await offered(page, '#settings-pair-first'), ['First', 'Second']);
      assert.deepEqual(await offered(page, '#settings-pair-second'), ['Second']);
      await page.locator('[data-settings-action="pair"]').click();
      await page.waitForFunction(() => document.querySelectorAll('#settings-couples-body .couple-card').length === 3);
      // No pair is left to form: the page says so instead of offering Pair.
      assert.equal(await page.locator('#settings-pair-first').count(), 0);
      assert.ok((await page.locator('#settings-couples-body').textContent()).includes('No pair is left to form: each chart is paired with every other it can be.'));
      // A new birth can still be the partner of a chart paired with every other.
      assert.deepEqual(await offered(page, '#settings-partner-of'), ['Mine', 'First', 'Second']);
      assert.equal(await page.locator('#settings-partner-of').inputValue(), mine);
      await page.locator('[data-settings-action="add-partner"]').click();
      await page.locator('#save-note').waitFor({ state: 'visible' });
      await page.locator('#save-name').fill('Fourth');
      await page.locator('#date').fill('1983-01-02');
      await page.locator('#time').fill('07:45');
      await page.locator('#location').fill('Helsinki');
      await page.locator('#location-suggestions .location-suggestion').click();
      await page.locator('.gender-option input[value="female"]').check();
      await page.locator('#create-chart-btn').click();
      await page.locator('#settings-view').waitFor({ state: 'visible' });
      const now = await read(page);
      const fourth = now.charts.find((chart) => chart.name === 'Fourth').id;
      assert.deepEqual(now.couples.map((couple) => couple.charts).at(-1), [mine, fourth]);
      assert.equal(now.couples.filter((couple) => couple.charts.includes(mine)).length, 3);
    });

    check('under a plan’s cap a chart at it is in neither list, the page says why, and marked past it your chart says the partner kept from before did not pair', async (page) => {
      await reset(page);
      const mine = await saveElsewhere(page, { ...SCREEN, name: 'Mine' });
      const first = await saveElsewhere(page, partnerNamed('First', '1980-01-02'));
      await saveElsewhere(page, partnerNamed('Second', '1981-01-02'));
      const third = await saveElsewhere(page, partnerNamed('Third', '1982-01-02'));
      await changeElsewhere(page, 'POST', '/api/account/couples', { charts: [mine, first] });
      // A plan that keeps one couple per chart, as one may once plans are sold, and Third
      // waiting as a partner kept from before charts: given to the page's reads.
      await page.route('**/api/account/settings', async (route) => {
        if (route.request().method() !== 'GET') return route.fallback();
        const response = await route.fetch();
        return route.fulfill({ response, json: { ...(await response.json()), couples_per_chart: 1, pending_partner: third } });
      });
      await openSettings(page);
      assert.deepEqual(await offered(page, '#settings-pair-first'), ['Second', 'Third']);
      assert.deepEqual(await offered(page, '#settings-pair-second'), ['Third']);
      assert.deepEqual(await offered(page, '#settings-partner-of'), ['Second', 'Third']);
      assert.ok((await page.locator('#settings-couples-body').textContent()).includes('On your plan a chart is in one couple at most: a chart in a couple already is not offered.'));
      // Mine, at the cap, marked as yours: the API's answer, on the same plan, has no
      // couple with Third, and the page says why.
      await page.route('**/api/account/my-chart', async (route) => {
        if (route.request().method() !== 'PUT') return route.fallback();
        const response = await route.fetch();
        return route.fulfill({ response, json: { ...(await response.json()), couples_per_chart: 1 } });
      });
      await page.locator('#settings-mine-choice').selectOption(mine);
      await page.locator('[data-settings-action="mark"]').click();
      await page.waitForFunction(() => document.querySelector('.toast').textContent !== '');
      assert.equal(await page.locator('.toast').textContent(), 'Your chart is marked. It is in as many couples as your plan allows, so Third did not pair with it and waits no longer.');
    });

    check('two marks in turn: the second is read from the settings the first left, and says no cap where there is none', async (page) => {
      await reset(page);
      const first = await saveElsewhere(page, { ...SCREEN, name: 'First' });
      const second = await saveElsewhere(page, partnerNamed('Second', '1980-01-02'));
      const waiting = await saveElsewhere(page, partnerNamed('Waiting', '1981-01-02'));
      // Waiting as a partner kept from before charts, with no cap: given to the page's
      // reads. The first mark's answer, held on its way, pairs it with First, as the API
      // does (test_accounts_settings.py).
      await page.route('**/api/account/settings', async (route) => {
        if (route.request().method() !== 'GET') return route.fallback();
        const response = await route.fetch();
        return route.fulfill({ response, json: { ...(await response.json()), pending_partner: waiting } });
      });
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      let marks = 0;
      await page.route('**/api/account/my-chart', async (route) => {
        if (route.request().method() !== 'PUT') return route.fallback();
        marks += 1;
        if (marks > 1) return route.fallback();
        const response = await route.fetch();
        const value = await response.json();
        await held;
        return route.fulfill({ response, json: { ...value, couples: [...value.couples, { id: 'e'.repeat(32), charts: [first, waiting] }] } });
      });
      await openSettings(page);
      await page.evaluate(() => {
        window.__toasts = [];
        new MutationObserver(() => {
          const said = document.querySelector('.toast')?.textContent ?? '';
          if (said !== '' && window.__toasts.at(-1) !== said) window.__toasts.push(said);
        }).observe(document.body, { subtree: true, childList: true, characterData: true });
      });
      await page.locator('#settings-mine-choice').selectOption(first);
      await page.locator('[data-settings-action="mark"]').click();
      // Marked again, another chart, while the first is on its way.
      await page.locator('#settings-mine-choice').selectOption(second);
      await page.locator('[data-settings-action="mark"]').click();
      release();
      await page.waitForFunction(() => window.__toasts.length >= 2);
      assert.deepEqual(await page.evaluate(() => window.__toasts), [
        'Your chart is marked, and paired with Waiting.',
        'Your chart is marked.',
      ]);
    });

    check('a chart with many partners names three and how many more, and stays inside the page', async (page) => {
      await reset(page);
      const mine = await saveElsewhere(page, { ...SCREEN, name: 'Mine' });
      for (let index = 0; index < 10; index += 1) {
        const partner = await saveElsewhere(page, partnerNamed(`Partner ${index + 1}`, `${1970 + index}-03-04`));
        await changeElsewhere(page, 'POST', '/api/account/couples', { charts: [mine, partner] });
      }
      await openSettings(page);
      const marks = await page.locator(`#settings-charts-body .saved-card[data-chart="${mine}"] .saved-head`).textContent();
      assert.ok(marks.includes('Couple with Partner 1, Partner 2, Partner 3, and 7 more'), marks);
      assert.equal(await page.locator('#settings-couples-body .couple-card').count(), 10);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'no sideways scroll');
    });

    check('a pair formed already is refused in the page’s language, without asking', async (page) => {
      await reset(page);
      const mine = await saveElsewhere(page, { ...SCREEN, name: 'Mine' });
      const first = await saveElsewhere(page, partnerNamed('First', '1980-01-02'));
      await saveElsewhere(page, partnerNamed('Second', '1981-01-02'));
      await changeElsewhere(page, 'POST', '/api/account/couples', { charts: [mine, first] });
      await openSettings(page);
      // The lists never offer it; chosen all the same (as a stale list might), it is
      // refused before the API is asked.
      const asked = [];
      page.on('request', (request) => {
        if (new URL(request.url()).pathname === '/api/account/couples') asked.push(request.method());
      });
      await page.locator('#settings-pair-first').selectOption(mine);
      await page.locator('#settings-pair-second').evaluate((select, id) => {
        select.add(new Option('First', id));
        select.value = id;
      }, first);
      await page.locator('[data-settings-action="pair"]').click();
      await page.waitForFunction(() => document.getElementById('settings-status').textContent.includes('These two charts are a couple already.'));
      assert.deepEqual(asked, []);
      assert.equal((await read(page)).couples.length, 1);
    });

    check('an answer naming one chart twice in a couple, or the same pair twice, is refused, never drawn', async (page) => {
      await reset(page);
      const mine = await saveElsewhere(page, { ...SCREEN, name: 'Mine' });
      const partner = await saveElsewhere(page, partnerNamed('Partner'));
      await changeElsewhere(page, 'POST', '/api/account/couples', { charts: [mine, partner] });
      for (const couples of [
        [{ id: 'b'.repeat(32), charts: [mine, mine] }],
        [{ id: 'b'.repeat(32), charts: [mine, partner] }, { id: 'c'.repeat(32), charts: [partner, mine] }],
      ]) {
        await page.unrouteAll({ behavior: 'ignoreErrors' });
        await page.route('**/api/account/settings', async (route) => {
          if (route.request().method() !== 'GET') return route.fallback();
          const response = await route.fetch();
          return route.fulfill({ response, json: { ...(await response.json()), couples } });
        });
        await openSettings(page);
        await page.waitForFunction(() => document.getElementById('settings-status').textContent.includes('could not be read'));
        assert.equal(await page.locator('#settings-couples-body .couple-card').count(), 0);
      }
      // Nor without the plan's cap, or with one that is no count of couples.
      for (const cap of [undefined, 0, '1', 1.5]) {
        await page.unrouteAll({ behavior: 'ignoreErrors' });
        await page.route('**/api/account/settings', async (route) => {
          if (route.request().method() !== 'GET') return route.fallback();
          const response = await route.fetch();
          const value = await response.json();
          if (cap === undefined) delete value.couples_per_chart;
          else value.couples_per_chart = cap;
          return route.fulfill({ response, json: value });
        });
        await openSettings(page);
        await page.waitForFunction(() => document.getElementById('settings-status').textContent.includes('could not be read'));
        assert.equal(await page.locator('#settings-couples-body .couple-card').count(), 0, String(cap));
      }
    });

    check('Cancel on a birth added from Settings saves nothing and goes back', async (page) => {
      await reset(page);
      await openSettings(page);
      await page.locator('[data-settings-action="add-mine"]').click();
      await page.locator('#save-note').waitFor({ state: 'visible' });
      assert.match(await page.locator('#save-note-text').textContent(), /saved as your chart/);
      await page.locator('#save-cancel').click();
      await page.locator('#settings-view').waitFor({ state: 'visible' });
      assert.equal(await page.evaluate(() => location.hash), '#settings');
      assert.deepEqual((await read(page)).charts, []);
      // The form, opened anew, is the plain form again.
      await page.locator('#settings-close').click();
      await page.locator('#input-view').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#save-note').isHidden(), true);
      assert.equal(await page.locator('#save-name-group').isHidden(), true);
      assert.equal(await page.locator('#create-chart-btn').textContent(), 'Create chart');
    });

    check('a chart born in an hour the clocks repeat opens as its chart, at its pass, and is named', async (page) => {
      await reset(page);
      // 25 October 2020 in Helsinki: the clocks went back at 04:00, so 03:30 came twice.
      const REPEATED = { name: 'Repeated', date: '2020-10-25', time: '03:30', place: PLACE, fold: 1, gender: 'female', zi: 'split_midnight' };
      await saveElsewhere(page, REPEATED);
      await openSettings(page);
      const asked = [];
      page.on('request', (request) => {
        if (new URL(request.url()).pathname === '/api/four_pillars') asked.push(request.postDataJSON());
      });
      await page.locator('#settings-charts-body [data-settings-action="open"]').click();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await page.waitForFunction(() => !document.getElementById('chart-view').hasAttribute('aria-busy'));
      assert.equal(await page.evaluate(() => new URLSearchParams(location.hash.split('?')[1]).get('fold')), '1');
      assert.equal(asked.at(-1).location.fold, 1);
      assert.equal(await page.locator('#form-error').isHidden(), true);
      // The library knows it by its pass.
      await page.waitForFunction(() => document.querySelector('#library-btn .library-label').textContent === 'Repeated');
    });

    check('a chart without a gender is not saved, and says why', async (page) => {
      await reset(page);
      await openLink(page, chartLink({ gender: '' }).replace('&gender=', ''), { place: HELSINKI });
      await openLibrary(page);
      await page.locator('#library-save').click();
      await page.waitForFunction(() => document.querySelector('.toast').classList.contains('is-shown'));
      assert.match(await page.locator('.toast').textContent(), /gender/);
      await settled(page);
      assert.equal(await page.locator('#save-chart-dialog').isHidden(), true);
      assert.deepEqual((await read(page)).charts, []);
    });

    check('a name with quotes is changed from the name itself, quotes and all', async (page) => {
      await reset(page);
      const name = 'Quoted "name" <b>bold</b> & \'single\'';
      const id = await saveElsewhere(page, { ...SCREEN, name });
      await openSettings(page);
      await page.locator(`#settings-charts-body [data-settings-action="rename"][data-chart="${id}"]`).click();
      const field = page.locator(`#settings-rename-${id}`);
      assert.equal(await field.inputValue(), name);
      // Saved as it stands, the name is the same.
      await field.press('Enter');
      await page.waitForFunction(() => document.querySelector('.settings-rename') === null);
      assert.equal((await read(page)).charts.at(-1).name, name);
      assert.equal(await page.locator(`#settings-charts-body .saved-card[data-chart="${id}"] .saved-name`).textContent(), name);
    });

    check('pressed again while it is on its way, a pairing is asked for once', async (page) => {
      await reset(page);
      const first = await saveElsewhere(page, SCREEN);
      const second = await saveElsewhere(page, partnerNamed('Second'));
      await openSettings(page);
      // The pairing is held on its way while Pair is pressed again.
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      const asked = [];
      await page.route('**/api/account/couples', async (route) => {
        if (route.request().method() === 'POST') {
          asked.push(route.request().postDataJSON().charts);
          await held;
        }
        await route.fallback();
      });
      await page.locator('#settings-pair-first').selectOption(first);
      await page.locator('#settings-pair-second').selectOption(second);
      const pair = page.locator('#settings-couples-body [data-settings-action="pair"]');
      await pair.click();
      await pair.click();
      // The same couple, chosen the other way round, is the same change.
      await page.locator('#settings-pair-first').selectOption(second);
      await page.locator('#settings-pair-second').selectOption(first);
      await pair.click();
      release();
      await page.locator('#settings-couples-body .couple-card').waitFor();
      await page.waitForLoadState('networkidle');
      assert.deepEqual(asked, [[first, second]]);
      assert.equal(await page.locator('#settings-status').isHidden(), true);
      assert.deepEqual((await read(page)).couples.map((couple) => couple.charts), [[first, second]]);
    });

    check('marked again after an unmark, while the first mark is on its way, the chart ends marked', async (page) => {
      await reset(page);
      const first = await saveElsewhere(page, { ...SCREEN, name: 'First' });
      const second = await saveElsewhere(page, partnerNamed('Second'));
      await changeElsewhere(page, 'PUT', '/api/account/my-chart', { chart: first });
      await openSettings(page);
      // The first mark is held on its way while Unmark and Mark are pressed.
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      let holding = true;
      const asked = [];
      await page.route('**/api/account/my-chart', async (route) => {
        asked.push(route.request().method());
        if (holding) {
          holding = false;
          await held;
        }
        await route.fallback();
      });
      await page.locator('#settings-mine-choice').selectOption(second);
      await page.locator('[data-settings-action="mark"]').click();
      await page.locator('#settings-mine-body [data-settings-action="unmark"]').click();
      await page.locator('#settings-mine-choice').selectOption(second);
      await page.locator('[data-settings-action="mark"]').click();
      release();
      await page.waitForFunction(() => document.querySelector('#settings-mine-body .saved-card .saved-name')?.textContent === 'Second');
      await page.waitForLoadState('networkidle');
      assert.deepEqual(asked, ['PUT', 'DELETE', 'PUT']);
      assert.equal((await read(page)).my_chart, second);
      assert.equal(await page.locator('#settings-status').isHidden(), true);
    });

    check('Save, pressed again while the chart is being saved, saves it once', async (page) => {
      await reset(page);
      await openLink(page, chartLink(), { place: HELSINKI });
      await openLibrary(page);
      await page.locator('#library-save').click();
      await page.locator('#save-chart-dialog').waitFor({ state: 'visible' });
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      let asked = 0;
      await page.route('**/api/account/charts', async (route) => {
        if (route.request().method() === 'POST') {
          asked += 1;
          await held;
        }
        await route.fallback();
      });
      await page.locator('#save-chart-name').fill('Once');
      await page.locator('#save-chart-name').press('Enter');
      await page.locator('#save-chart-name').press('Enter');
      release();
      await page.locator('#save-chart-dialog').waitFor({ state: 'hidden' });
      await page.waitForLoadState('networkidle');
      assert.equal(asked, 1);
      assert.deepEqual((await read(page)).charts.map((chart) => chart.name), ['Once']);
    });

    check('a full library says so before anything is asked, in the library and in Settings', async (page) => {
      await reset(page);
      const limit = (await read(page)).chart_limit;
      for (let n = 0; n < limit; n += 1) {
        await saveElsewhere(page, partnerNamed(`Kept ${n}`, new Date(Date.UTC(1950, 0, 1 + n)).toISOString().slice(0, 10)));
      }
      const asked = [];
      page.on('request', (request) => {
        if (new URL(request.url()).pathname === '/api/account/charts' && request.method() === 'POST') asked.push(request.url());
      });
      const message = `${limit} charts are saved, the most an account keeps. Remove one in Settings first.`;
      await openLink(page, chartLink(), { place: HELSINKI });
      await openLibrary(page);
      await page.locator('#library-save').click();
      await page.waitForFunction(() => document.querySelector('.toast').classList.contains('is-shown'));
      assert.equal(await page.locator('.toast').textContent(), message);
      await settled(page);
      assert.equal(await page.locator('#save-chart-dialog').isHidden(), true);
      await openSettings(page);
      await page.locator('#settings-mine-body [data-settings-action="add-mine"]').click();
      await page.waitForFunction((message) => document.getElementById('settings-status').textContent === message, message);
      assert.equal(await page.evaluate(() => location.hash), '#settings');
      assert.deepEqual(asked, []);
    });

    check('removing a chart says first what else ends with it', async (page) => {
      await reset(page);
      const mine = await saveElsewhere(page, { ...SCREEN, name: 'Mine' });
      const partner = await saveElsewhere(page, partnerNamed('Partner'));
      const single = await saveElsewhere(page, partnerNamed('Single', '1980-01-02'));
      await changeElsewhere(page, 'PUT', '/api/account/my-chart', { chart: mine });
      await changeElsewhere(page, 'POST', '/api/account/couples', { charts: [mine, partner] });
      await openSettings(page);
      // The first press asks, on the button itself.
      const asking = async (id) => {
        const remove = page.locator(`#settings-charts-body [data-settings-action="remove"][data-chart="${id}"]`);
        await remove.click();
        return remove.textContent();
      };
      assert.equal(await asking(mine), 'Remove Mine? It is your chart, and its couple with Partner ends too.');
      assert.equal(await asking(partner), 'Remove Partner? Its couple with Mine ends too.');
      assert.equal(await asking(single), 'Remove Single?');
      // Parted elsewhere: my chart only stops being yours.
      await changeElsewhere(page, 'DELETE', `/api/account/couples/${(await read(page)).couples[0].id}`, {});
      await openSettings(page);
      assert.equal(await asking(mine), 'Remove Mine? It is your chart: none is marked as yours then.');
      // A chart waiting to pair with your chart, as a partner kept from before charts
      // waits, stops waiting.
      await changeElsewhere(page, 'DELETE', '/api/account/my-chart', {});
      await page.route('**/api/account/settings', async (route) => {
        if (route.request().method() !== 'GET') return route.fallback();
        const response = await route.fetch();
        return route.fulfill({ response, json: { ...(await response.json()), pending_partner: single } });
      });
      await openSettings(page);
      assert.equal(await asking(single), 'Remove Single? Then it won’t pair with your chart.');
      assert.equal((await read(page)).charts.length, 3, 'nothing was removed');
    });

    check('a birth saved already is said so by the form, in the page’s language, and the API is not asked', async (page) => {
      await reset(page);
      await page.route('**/api/location_suggest', (route) => route.fulfill({ json: { suggestions: [HELSINKI] } }));
      await saveElsewhere(page, { ...SCREEN, time: '21:05', name: 'Kept' });
      await openSettings(page);
      const asked = [];
      page.on('request', (request) => {
        if (new URL(request.url()).pathname === '/api/account/charts' && request.method() === 'POST') asked.push(request.url());
      });
      await page.locator('[data-settings-action="add-mine"]').click();
      await page.locator('#save-note').waitFor({ state: 'visible' });
      await page.locator('#date').fill(BIRTH.date);
      await page.locator('#time').fill('21:05');
      await page.locator('#location').fill('Helsinki');
      await page.locator('#location-suggestions .location-suggestion').click();
      await page.locator(`.gender-option input[value="${BIRTH.gender}"]`).check();
      await page.locator('#create-chart-btn').click();
      await page.waitForFunction(() => document.getElementById('form-error').textContent === 'This chart is saved already, as Kept.');
      assert.deepEqual(asked, []);
      assert.equal((await read(page)).charts.length, 1);
    });

    check('marked as yours, or saved as yours, a chart says the couple it forms with a partner kept from before charts', async (page) => {
      await reset(page);
      await page.route('**/api/location_suggest', (route) => route.fulfill({ json: { suggestions: [HELSINKI] } }));
      const mine = await saveElsewhere(page, { ...SCREEN, name: 'Mine' });
      const waiting = await saveElsewhere(page, partnerNamed('Waiting'));
      await openSettings(page);
      // The API pairs a partner kept from before charts with the chart next marked as
      // yours (test_accounts_settings.py); here its answers are given that couple.
      const paired = (method, id) => async (route) => {
        if (route.request().method() !== method) return route.fallback();
        const response = await route.fetch();
        const value = await response.json();
        const chart = id ?? value.saved;
        return route.fulfill({ response, json: { ...value, couples: [...value.couples, { id: chart.split('').reverse().join(''), charts: [chart, waiting] }] } });
      };
      await page.route('**/api/account/my-chart', paired('PUT', mine));
      await page.locator('#settings-mine-choice').selectOption(mine);
      await page.locator('[data-settings-action="mark"]').click();
      await page.waitForFunction(() => document.querySelector('.toast').textContent !== '');
      assert.equal(await page.locator('.toast').textContent(), 'Your chart is marked, and paired with Waiting.');
      // Saved as yours from the form, the same.
      await changeElsewhere(page, 'DELETE', '/api/account/my-chart', {});
      await page.route('**/api/account/charts', paired('POST', null));
      await openSettings(page);
      await page.locator('[data-settings-action="add-mine"]').click();
      await page.locator('#save-note').waitFor({ state: 'visible' });
      await page.locator('#date').fill('1990-01-02');
      await page.locator('#time').fill('10:00');
      await page.locator('#location').fill('Helsinki');
      await page.locator('#location-suggestions .location-suggestion').click();
      await page.locator('.gender-option input[value="female"]').check();
      await page.locator('#create-chart-btn').click();
      await page.locator('#settings-view').waitFor({ state: 'visible' });
      assert.equal(await page.locator('.toast').textContent(), 'The chart is saved as yours, and paired with Waiting.');
    });

    check('Edit, then Create chart, makes the same chart again: its Zi-hour convention, and its pass', async (page) => {
      const asked = [];
      page.on('request', (request) => {
        if (new URL(request.url()).pathname === '/api/four_pillars') asked.push(request.postDataJSON());
      });
      const dayStem = () => page.locator('.card.stem[data-pillar="day"]').getAttribute('data-char');
      const drawn = async () => {
        await page.locator('#chart-view').waitFor({ state: 'visible' });
        await page.waitForFunction(() => !document.getElementById('chart-view').hasAttribute('aria-busy'));
        await settled(page);
      };
      const remade = async () => {
        await press(page, '#back-btn');
        await page.locator('#input-view').waitFor({ state: 'visible' });
        await page.locator('#create-chart-btn').click();
        await drawn();
      };
      // A link opened as in the address bar. While a chart is on screen, it takes no
      // clicks until the link's own is drawn, which its heading then names. (Not
      // openLink: its check of each chart request refuses a pass, and a refusal.)
      const opened = async (link, year) => {
        await page.goto(new URL(link, process.env.EC_BASE_URL).href);
        await page.waitForFunction((year) => document.getElementById('chart-date').textContent.includes(year), year);
        await drawn();
      };
      // Summer clock 00:50 in Helsinki is true solar 23:29 the evening before: under the
      // whole Zi hour from 23:00, the day is the next one.
      await opened(chartLink({ date: '2021-06-15', time: '00:50', zi: 'whole_zi_23' }), '2021');
      const before = await dayStem();
      await remade();
      assert.equal(asked.at(-1).conventions?.zi_convention, 'whole_zi_23');
      assert.equal(await dayStem(), before);
      assert.equal(await page.evaluate(() => new URLSearchParams(location.hash.split('?')[1]).get('zi')), 'whole_zi_23');
      // Back to the chart after New chart, which emptied the form: the chart on screen is
      // the one come back to, asked for nothing, and the form is filled with it again.
      await press(page, '#new-chart-btn');
      await page.locator('#input-view').waitFor({ state: 'visible' });
      const askedBefore = asked.length;
      await page.goBack();
      await drawn();
      assert.equal(asked.length, askedBefore, 'the chart come back to is not asked for again');
      await remade();
      assert.equal(asked.at(-1).conventions?.zi_convention, 'whole_zi_23');
      assert.equal(await dayStem(), before);
      // 25 October 2020 in Helsinki: the clocks went back at 04:00, so 03:30 came twice.
      await opened(chartLink({ date: '2020-10-25', time: '03:30', fold: '1' }), '2020');
      await remade();
      assert.equal(asked.at(-1).location.fold, 1);
      assert.equal(await page.locator('#form-error').isHidden(), true);
      // Another time is another moment: its pass is not carried over.
      await press(page, '#back-btn');
      await page.locator('#time').fill('12:00');
      await page.locator('#create-chart-btn').click();
      await drawn();
      assert.equal(asked.at(-1).time, '12:00');
      assert.equal(asked.at(-1).location.fold, undefined);
      // A link whose chart cannot be drawn (03:30 on 28 March 2021, which Helsinki's clocks
      // skipped) leaves its own birth in the form: corrected, it is made as that link's
      // chart, not with the convention of the chart shown before it.
      await opened(chartLink({ date: '2021-06-15', time: '00:50', zi: 'whole_zi_23' }), '2021');
      await page.goto(new URL(chartLink({ date: '2021-03-28', time: '03:30' }), process.env.EC_BASE_URL).href);
      await page.locator('#form-error').waitFor({ state: 'visible' });
      await page.locator('#time').fill('12:00');
      await page.locator('#create-chart-btn').click();
      await drawn();
      assert.equal(asked.at(-1).date, '2021-03-28');
      assert.equal(asked.at(-1).conventions?.zi_convention, undefined);
      // New chart begins anew: the convention of the chart before is not carried over.
      await opened(chartLink({ date: '2021-06-15', time: '00:50', zi: 'whole_zi_23' }), '2021');
      await press(page, '#new-chart-btn');
      await page.locator('#date').fill('2021-06-15');
      await page.locator('#time').fill('00:50');
      await page.route('**/api/location_suggest', (route) => route.fulfill({ json: { suggestions: [HELSINKI] } }));
      await page.locator('#location').fill('Helsinki');
      await page.locator('#location-suggestions .location-suggestion').click();
      await page.locator('#create-chart-btn').click();
      await drawn();
      assert.equal(asked.at(-1).conventions?.zi_convention, undefined);
    });
  });
}

describe(`${engineName} / settings signed out`, { concurrency: false }, () => {
  it('signed in, the bare address opens my chart, replacing the address; a chart link opens itself', { timeout: 120000 }, () => withPage(profiles[0], async (page) => {
    const own = await newAccount(playwright, { language: 'en', label: 'settings-mine' });
    await asAccount(playwright, own, async (request) => {
      const kept = await request.post('/api/account/charts', { data: { ...SCREEN, name: 'Mine', mine: true, key: own.key, updated_at: null } });
      assert.equal(kept.status(), 201, await kept.text());
    });
    await signInPage(page, own);
    await page.goto(new URL('/', process.env.EC_BASE_URL).href);
    await page.locator('#chart-view').waitFor({ state: 'visible' });
    assert.equal(await page.evaluate(() => new URLSearchParams(location.hash.split('?')[1]).get('date')), BIRTH.date);
    await page.waitForFunction(() => document.querySelector('#library-btn .library-label').textContent === 'Mine');
    // A chart link opens its own chart; New chart still opens the form.
    await page.goto(new URL(chartLink({ date: '1977-02-03' }), process.env.EC_BASE_URL).href);
    // The chart on screen was already shown: the link's own is drawn once its heading
    // names it.
    await page.waitForFunction(() => document.getElementById('chart-date').textContent.includes('1977'));
    await settled(page);
    assert.equal(await page.evaluate(() => new URLSearchParams(location.hash.split('?')[1]).get('date')), '1977-02-03');
    await page.waitForFunction(() => document.querySelector('#library-btn .library-label').textContent === 'Unsaved chart');
    await press(page, '#new-chart-btn');
    await page.locator('#input-view').waitFor({ state: 'visible' });
    assert.equal(await page.evaluate(() => location.hash), '');
  }, { signedIn: false }));

  it('Settings asks for a sign-in first', { timeout: 60000 }, () => withPage(profiles[0], async (page) => {
    await stubTurnstile(page);
    await page.goto(new URL('/#settings', process.env.EC_BASE_URL).href);
    await page.locator('#account-dialog').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#settings-view').isHidden(), true);
  }, { signedIn: false }));

  it('after a sign-out, Settings show nothing of the account before, even when the next read fails', { timeout: 120000 }, () => withPage(profiles[0], async (page) => {
    const first = await newAccount(playwright, { language: 'en', label: 'settings-first' });
    const second = await newAccount(playwright, { language: 'en', label: 'settings-second' });
    await asAccount(playwright, first, async (request) => {
      const kept = await request.put('/api/account/place', { data: { place: PLACE, key: first.key, updated_at: null } });
      assert.equal(kept.status(), 200, await kept.text());
    });
    await signInPage(page, first);
    await stubTurnstile(page);
    await openSettings(page);
    assert.match(await page.locator('#settings-place-now').textContent(), /^Now:/);
    // A change the server makes, whose answer reaches the page only after the sign-out.
    let deliver;
    const delivered = new Promise((resolve) => { deliver = resolve; });
    let answered;
    const fetched = new Promise((resolve) => { answered = resolve; });
    await page.route('**/api/account/schools', async (route) => {
      if (route.request().method() !== 'PATCH') return route.fallback();
      const response = await route.fetch();
      answered();
      await delivered;
      return route.fulfill({ response });
    });
    await page.locator('#settings-favourable-climate').click();
    await fetched;
    // Back on the start page, whose account menu signs out; the page stays as it is.
    await page.locator('#settings-close').click();
    await page.locator('#account-btn').click();
    await page.locator('#account-sign-out').click();
    // The sign-out is answered, and Settings have forgotten the account, before the
    // change's answer arrives.
    await page.waitForFunction(() => document.getElementById('settings-place-now').textContent === '');
    deliver();
    await page.waitForFunction(() => document.getElementById('settings-status').textContent === 'Your session ended. Sign in again.');
    // Signed in to another account in the same page, whose settings cannot be read now.
    await signInThroughDialog(page, second.email);
    await page.route('**/api/account/settings', (route) => route.fulfill({ status: 500, json: { detail: 'Stopped by the test.' } }));
    await page.locator('#account-btn').click();
    await page.locator('#account-settings').click();
    await page.locator('#settings-status').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#settings-status').textContent(), 'Stopped by the test.');
    assert.equal(await page.locator('#settings-view [data-settings-action]').count(), 0);
    assert.equal(await page.locator('#settings-place-now').textContent(), '');
    assert.equal(await page.locator('#settings-place-remove').isHidden(), true);
    assert.equal(await page.locator('#settings-schools-body input').count(), 0);
  }, { signedIn: false }));

  it('a change after the session ended elsewhere asks for a sign-in, and is not repeated', { timeout: 90000 }, () => withPage(profiles[0], async (page) => {
    const own = await newAccount(playwright, { language: 'en', label: 'settings-ended' });
    await signInPage(page, own);
    await stubTurnstile(page);
    await openSettings(page);
    // Signed out on every device, from another one: the page still holds the account.
    await asAccount(playwright, own, async (request) => {
      assert.equal((await request.delete('/api/account/sessions', { data: { key: own.key } })).status(), 204);
    });
    await page.locator('#settings-favourable-climate').click();
    await dialogOpens(page);
    await signInThroughDialog(page, own.email);
    await page.locator('#settings-status').waitFor({ state: 'visible' });
    assert.match(await page.locator('#settings-status').textContent(), /signed in again/);
    assert.equal((await read(page)).chosen.favourable, null, 'the change was not made');
    assert.equal(await page.locator('input[name="settings-favourable"]:checked').getAttribute('value'), 'support');
  }, { signedIn: false }));

  // Two accounts, each keeping a chart of its own: the first keeps the chart on screen.
  const twoAccounts = async (label) => {
    const first = await newAccount(playwright, { language: 'en', label: `${label}-a` });
    const second = await newAccount(playwright, { language: 'en', label: `${label}-b` });
    const keep = (account, birth) => asAccount(playwright, account, async (request) => {
      const kept = await request.post('/api/account/charts', { data: { ...birth, key: account.key, updated_at: null } });
      assert.equal(kept.status(), 201, await kept.text());
      return (await kept.json()).saved;
    });
    const firstChart = await keep(first, { ...SCREEN, name: 'First keeps' });
    await keep(second, partnerNamed('Second keeps'));
    return { first, second, firstChart };
  };

  it('another account taken in this browser: the chart is not named from the one before, even by a read held on its way', { timeout: 120000 }, () => withPage(profiles[0], async (page) => {
    const { first, second } = await twoAccounts('taken-name');
    await signInPage(page, first);
    // The chart's own read of the settings is answered for the first account, and held
    // on its way.
    let release;
    const held = new Promise((resolve) => { release = resolve; });
    let answered;
    const fetched = new Promise((resolve) => { answered = resolve; });
    let holding = true;
    await page.route('**/api/account/settings', async (route) => {
      if (!holding || route.request().method() !== 'GET') return route.fallback();
      holding = false;
      const response = await route.fetch();
      answered();
      await held;
      return route.fulfill({ response });
    });
    await page.goto(new URL(chartLink(), process.env.EC_BASE_URL).href);
    await page.locator('#chart-view').waitFor({ state: 'visible' });
    await fetched;
    // Every name the library's button is given from here on.
    await page.evaluate(() => {
      window.__names = [];
      const label = document.querySelector('#library-btn .library-label');
      new MutationObserver(() => window.__names.push(label.textContent)).observe(label, { childList: true, characterData: true, subtree: true });
    });
    // Another tab signs in to the second account, which the account's command takes.
    await page.context().addCookies(second.cookies);
    await page.keyboard.press('ControlOrMeta+k');
    await page.locator('#palette-input').fill('account');
    await page.keyboard.press('Enter');
    await dialogOpens(page);
    await page.locator('#account-who').filter({ hasText: second.email }).waitFor();
    await page.keyboard.press('Escape');
    release();
    await page.waitForFunction(() => document.querySelector('#library-btn .library-label').textContent === 'Unsaved chart');
    assert.equal((await page.evaluate(() => window.__names)).includes('First keeps'), false, 'the first account’s name is not shown');
    // The library is the second account's.
    await openLibrary(page);
    assert.deepEqual(await page.locator('#library-list .saved-name').allTextContents(), ['Second keeps']);
  }, { signedIn: false }));

  it('another account taken while Settings are open: the change is not made, and Settings show the account taken', { timeout: 120000 }, () => withPage(profiles[0], async (page) => {
    const { first, second } = await twoAccounts('taken-settings');
    await signInPage(page, first);
    await openSettings(page);
    assert.match(await page.locator('#settings-charts-body').textContent(), /First keeps/);
    // Another tab signs in to the second account: a change from these settings, made for
    // the first, is refused, and the page takes the second.
    await page.context().addCookies(second.cookies);
    await page.locator('#settings-favourable-climate').click();
    await page.waitForFunction(() => document.getElementById('settings-charts-body').textContent.includes('Second keeps'));
    await page.waitForFunction(() => !document.getElementById('settings-view').hasAttribute('aria-busy'));
    assert.equal(await page.locator('#settings-status').textContent(), 'This browser is signed in to another account now.');
    assert.doesNotMatch(await page.locator('#settings-view').textContent(), /First keeps/);
    assert.equal(await page.locator('input[name="settings-favourable"]:checked').getAttribute('value'), 'support');
    for (const account of [first, second]) {
      await asAccount(playwright, account, async (request) => {
        assert.equal((await (await request.get('/api/account/settings')).json()).chosen.favourable, null, 'nothing was changed');
      });
    }
  }, { signedIn: false }));

  it('another account taken while a birth is corrected: the form lets the birth go', { timeout: 120000 }, () => withPage(profiles[0], async (page) => {
    const { first, second, firstChart } = await twoAccounts('taken-correct');
    await signInPage(page, first);
    await page.goto(new URL(`/#save?as=correct&chart=${firstChart}`, process.env.EC_BASE_URL).href);
    await page.locator('#save-note').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#date').inputValue(), BIRTH.date);
    assert.equal(await page.locator('#save-name').inputValue(), 'First keeps');
    // Another tab signs in to the second account: the correction, made for the first, is
    // refused, and the page takes the second, which keeps no such chart.
    await page.context().addCookies(second.cookies);
    await page.locator('#create-chart-btn').click();
    await page.waitForFunction(() => document.getElementById('form-error').textContent === 'That saved chart is gone.');
    assert.equal(await page.locator('#save-note').isHidden(), true);
    assert.deepEqual(await Promise.all(['#date', '#time', '#location', '#save-name'].map((field) => page.locator(field).inputValue())), ['', '', '', '']);
    await asAccount(playwright, first, async (request) => {
      const kept = (await (await request.get('/api/account/settings')).json()).charts;
      assert.deepEqual(kept.map((chart) => [chart.name, chart.date, chart.time]), [['First keeps', BIRTH.date, BIRTH.time]]);
    });
  }, { signedIn: false }));
});
