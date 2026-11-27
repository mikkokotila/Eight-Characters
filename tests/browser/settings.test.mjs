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
// The charts chart `id`'s Pair with… offers, by name, in their order: opened, read and
// closed again.
async function choices(page, id) {
  await page.locator(`[data-settings-action="pair-start"][data-chart="${id}"]`).click();
  const group = page.locator(`.saved-item[data-chart="${id}"] .settings-pair-choices`);
  const names = await group.locator('[data-settings-action="pair"]').evaluateAll((items) => items.map((item) => item.textContent.split(' · ')[0]));
  await page.locator(`[data-settings-action="pair-cancel"][data-chart="${id}"]`).click();
  await group.waitFor({ state: 'detached' });
  return names;
}
// Chart `id` paired with chart `other` from its own row: Pair with…, then the other.
async function pairFrom(page, id, other) {
  await page.locator(`[data-settings-action="pair-start"][data-chart="${id}"]`).click();
  await page.locator(`[data-settings-action="pair"][data-chart="${id}"][data-with="${other}"]`).click();
}
// The couples the page draws: each has an End button on both its charts' rows.
const couplesDrawn = (page) => page.locator('#settings-charts-body [data-settings-action="end"]')
  .evaluateAll((buttons) => new Set(buttons.map((button) => button.dataset.couple)).size);
// Settings (`part` 'settings': where you are, the schools, the toolbar) or the saved
// charts ('charts': one list, your chart first, each with what can be done with it),
// each a page of its own.
async function openSettings(page, part = 'settings') {
  await page.goto(new URL(`/#${part}`, process.env.EC_BASE_URL).href);
  await page.locator('#settings-view').waitFor({ state: 'visible' });
  await page.waitForFunction(() => !document.getElementById('settings-view').hasAttribute('aria-busy'));
  await settled(page);
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / settings`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 120000 }, () => withPage(profile, run));

    check('sandbox billing status stays separate from legacy plan and translates held access', async (page) => {
      await reset(page);
      let state = 'paid';
      await page.route('**/api/account/settings', async (route) => {
        const response = await route.fetch();
        const value = await response.json();
        await route.fulfill({ response, json: { ...value, chart_limit: state === 'paid' ? 25 : 1,
          billing: { tier: state === 'paid' ? 'plus' : 'free', status: state,
            paid_through: state === 'paid' ? 1795082400 : null, reason: state === 'held' ? 'unverified' : null } } });
      });
      for (const [next, words] of [['paid', /Sandbox access: Plus · paid.*Paid access ends/],
        ['pending', /payment pending/], ['held', /verification held/], ['expired', /paid time expired/]]) {
        state = next;
        await openSettings(page, 'charts');
        assert.match(await page.locator('[data-billing-status]').textContent(), words);
      }
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await page.locator('[data-lang="fi"]').click();
      await goTo(page, '#charts');
      await page.locator('[data-billing-status]').waitFor();
      assert.match(await page.locator('[data-billing-status]').textContent(), /Testikäyttö: Maksuton · käyttöaika päättynyt/);
    });

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
      // Settings are where you are, the schools and the toolbar; the saved charts have a
      // page of their own, opened from the account's window too.
      assert.equal(await page.locator('.settings-bar h1').innerText(), 'Settings');
      assert.equal(await page.evaluate(() => document.title), 'Settings — Eightchord');
      for (const part of ['#settings-place', '#settings-schools', '#settings-toolbar']) assert.equal(await page.locator(part).isVisible(), true, part);
      assert.equal(await page.locator('#settings-charts').isVisible(), false);
      await page.locator('#settings-account').click();
      await page.locator('#account-charts').click();
      // The view shows the saved charts once it is drawn for them (the address moves first).
      await page.waitForFunction(() => {
        const view = document.getElementById('settings-view');
        return location.hash === '#charts' && view.dataset.part === 'charts' && !view.classList.contains('hidden') && !view.hasAttribute('aria-busy');
      });
      assert.equal(await page.locator('.settings-bar h1').innerText(), 'Saved charts');
      assert.equal(await page.evaluate(() => document.title), 'Saved charts — Eightchord');
      assert.equal(await page.locator('#settings-charts').isVisible(), true);
      for (const part of ['#settings-place', '#settings-schools', '#settings-toolbar']) assert.equal(await page.locator(part).isVisible(), false, part);
      // No chart saved: the page says so, and starts with your own birth.
      assert.match(await page.locator('#settings-charts-body').textContent(), /No saved charts/);
      assert.equal(await page.locator('#settings-charts-body [data-settings-action="add-mine"]').innerText(), 'Add your own birth');
      assert.equal(await page.locator('#settings-charts-body select').count(), 0);
      // Close goes back to the page the first of them was opened from.
      assert.equal(await page.locator('#settings-close').textContent(), 'Close');
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
      await goTo(page, '#charts');
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
      await goTo(page, '#charts');
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
      await goTo(page, '#charts');
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
      await goTo(page, '#charts');
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
      // On paper a chart not saved says nothing of it.
      await page.emulateMedia({ media: 'print' });
      assert.equal(await page.locator('#library-btn').isVisible(), false);
      await page.emulateMedia({ media: 'screen' });
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
      // On paper the saved chart's name is text under the date, not a button.
      await page.emulateMedia({ media: 'print' });
      assert.deepEqual(await page.locator('#library-btn').evaluate((node) => {
        const style = getComputedStyle(node);
        return [node.checkVisibility(), node.innerText, style.borderTopStyle, style.backgroundColor];
      }), [true, name, 'none', 'rgba(0, 0, 0, 0)']);
      await page.emulateMedia({ media: 'screen' });
      // Saved once: the library offers no second save, and marks the chart on screen.
      await openLibrary(page);
      assert.equal(await page.locator('#library-save').isHidden(), true);
      assert.equal(await page.locator('#library-list [aria-current="true"] .saved-name').textContent(), name);
      assert.equal(await page.evaluate(() => window.__named), undefined, 'a name is text');
      await page.keyboard.press('Escape');
      await page.locator('#library-dialog').waitFor({ state: 'hidden' });
      assert.equal(await page.evaluate(() => document.activeElement?.id), 'library-btn');
      await openSettings(page, 'charts');
      // Under the settings, the website's own pages, as under the start page.
      assert.deepEqual(await page.locator('.site-links a').evaluateAll((nodes) => nodes
        .filter((node) => node.checkVisibility()).map((node) => node.textContent)),
      ['Method', 'Terms', 'Privacy Policy']);
      const card = page.locator(`#settings-charts-body .saved-item[data-chart="${kept.id}"]`);
      assert.equal(await card.locator('.saved-name').textContent(), name);
      // Its pillars in the chart's order, hour first, each character with its pinyin.
      const tiles = await card.locator('.saved-glyph').evaluateAll((items) => items.map((item) => [
        item.querySelector('.saved-char').textContent, item.querySelector('.saved-pinyin').textContent,
      ]));
      assert.deepEqual(tiles, ['hour', 'day', 'month', 'year'].flatMap((p) => [
        [kept.pillars[p].stem.chinese, kept.pillars[p].stem.pinyin],
        [kept.pillars[p].branch.chinese, kept.pillars[p].branch.pinyin],
      ]));
      await card.locator('[data-settings-action="open"]').click();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      assert.equal(await page.evaluate(() => new URLSearchParams(location.hash.split('?')[1]).get('date')), BIRTH.date);
      await openSettings(page, 'charts');
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
      await openSettings(page, 'charts');
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
      await openSettings(page, 'charts');
      // No chart is yours yet: the page says so, and each chart can be marked.
      assert.ok((await page.locator('#settings-charts-body').textContent()).includes('Which one is yours? Mark it as yours, and each visit opens its day.'));
      // Marked from the keyboard, the focus moves to Unmark, in its place.
      await page.locator(`[data-settings-action="mark"][data-chart="${mine}"]`).focus();
      await page.keyboard.press('Enter');
      await page.locator(`.saved-item[data-chart="${mine}"] .saved-mark.is-mine`).waitFor();
      assert.equal((await read(page)).my_chart, mine);
      assert.deepEqual(await page.evaluate(() => [document.activeElement?.dataset.settingsAction, document.activeElement?.dataset.chart]), ['unmark', mine]);
      // A partner for my chart, as a new birth: Pair with… offers it, and the form says
      // what it saves.
      await page.locator(`[data-settings-action="pair-start"][data-chart="${mine}"]`).click();
      assert.match(await page.locator(`#settings-pair-${mine}`).textContent(), /^No other saved chart can pair with Unnamed chart · /);
      await page.locator(`[data-settings-action="add-partner"][data-chart="${mine}"]`).click();
      await page.locator('#save-note').waitFor({ state: 'visible' });
      assert.match(await page.evaluate(() => location.hash), /^#save\?as=partner&with=/);
      assert.match(await page.locator('#save-note-text').textContent(), /paired with Unnamed chart/);
      // A saved birth needs a gender: "Not given" is no choice here, and none is made.
      assert.equal(await page.locator('.gender-group legend').textContent(), 'Gender (needed)');
      assert.equal(await page.locator('#chart-form .gender-option:has(input[value=""])').isVisible(), false);
      assert.equal(await page.locator('#chart-form .gender-option input:checked').count(), 0);
      await page.locator('#save-name').fill('New partner');
      await page.locator('#date').fill('1988-11-02');
      await page.locator('#time').fill('21:05');
      await page.locator('#location').fill('Helsinki');
      await page.locator('#location-suggestions .location-suggestion').click();
      // Without a gender the form says so, and saves nothing.
      await page.locator('#create-chart-btn').click();
      await page.waitForFunction(() => document.getElementById('form-error').textContent.includes('gender'));
      assert.equal((await read(page)).charts.length, 1);
      await page.locator('#chart-form .gender-option input[value="male"]').check();
      await page.locator('#create-chart-btn').click();
      await page.locator('#settings-view').waitFor({ state: 'visible' });
      assert.equal(await page.evaluate(() => location.hash), '#charts');
      const now = await read(page);
      const partner = now.charts.find((chart) => chart.name === 'New partner');
      assert.deepEqual(now.couples.map((couple) => couple.charts), [[mine, partner.id]]);
      // Each chart of the couple can end it, from its own row.
      const end = page.locator(`[data-settings-action="end"][data-chart="${mine}"]`);
      assert.equal(await end.textContent(), 'End the couple with New partner');
      assert.match(await page.locator(`[data-settings-action="end"][data-chart="${partner.id}"]`).textContent(), /^End the couple with an unnamed chart \(born /);
      // Ended, both charts stay saved.
      await end.click();
      await page.waitForFunction(() => document.querySelector('#settings-charts-body [data-settings-action="end"]') === null);
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
      await openSettings(page, 'charts');
      // My chart names every partner in the order paired, an unnamed one by its birth
      // date, and past three says how many more.
      const marks = await page.locator(`#settings-charts-body .saved-item[data-chart="${mine}"] .saved-head`).textContent();
      assert.ok(marks.includes('Couple with First, an unnamed chart (born January 2, 1981), Third, and 1 more'), marks);
      // Each partner names my chart; each couple can be ended from my chart's row.
      assert.match(await page.locator(`#settings-charts-body .saved-item[data-chart="${partners[3]}"] .saved-head`).textContent(), /Couple with Mine/);
      assert.deepEqual(await page.locator(`.saved-item[data-chart="${mine}"] [data-settings-action="end"]`).allTextContents(), [
        'End the couple with First', 'End the couple with an unnamed chart (born January 2, 1981)',
        'End the couple with Third', 'End the couple with Fourth',
      ]);
      assert.equal(await couplesDrawn(page), 4);
      // Removing my chart names each couple it ends.
      const remove = page.locator(`#settings-charts-body [data-settings-action="remove"][data-chart="${mine}"]`);
      await remove.click();
      assert.equal(await remove.textContent(), 'Remove Mine? It is your chart, and its couples with First, an unnamed chart (born January 2, 1981), Third, and 1 more end too.');
      // My chart is paired with every other: its Pair with… offers only a new birth, and
      // the others offer each other, never my chart again.
      assert.deepEqual(await choices(page, mine), []);
      assert.deepEqual(await choices(page, partners[0]), ['Unnamed chart', 'Third', 'Fourth']);
    });

    check('Pair with…: each chart offers the charts it can pair with, never itself or its partners; with no pair left the page says so, and a new birth can still be a partner', async (page) => {
      await reset(page);
      await page.route('**/api/location_suggest', (route) => route.fulfill({ json: { suggestions: [HELSINKI] } }));
      const mine = await saveElsewhere(page, { ...SCREEN, name: 'Mine' });
      const first = await saveElsewhere(page, partnerNamed('First', '1980-01-02'));
      const second = await saveElsewhere(page, partnerNamed('Second', '1981-01-02'));
      await changeElsewhere(page, 'PUT', '/api/account/my-chart', { chart: mine });
      await changeElsewhere(page, 'POST', '/api/account/couples', { charts: [mine, first] });
      await openSettings(page, 'charts');
      // Your chart first, then the others as saved; each offers what it can pair with.
      assert.deepEqual(await page.locator('#settings-charts-body .saved-item').evaluateAll((items) => items.map((item) => item.dataset.chart)), [mine, first, second]);
      assert.deepEqual(await choices(page, mine), ['Second']);
      assert.deepEqual(await choices(page, first), ['Second']);
      assert.deepEqual(await choices(page, second), ['Mine', 'First']);
      // Opened, the choices take the focus, under their question; closed, the focus goes
      // back to Pair with…, whether by Cancel or by Pair with… again.
      const start = page.locator(`[data-settings-action="pair-start"][data-chart="${second}"]`);
      const focus = () => page.evaluate(() => ['settingsAction', 'chart', 'with'].map((key) => document.activeElement?.dataset[key] ?? null));
      assert.equal(await start.getAttribute('aria-expanded'), 'false');
      await start.focus();
      await page.keyboard.press('Enter');
      assert.equal(await start.getAttribute('aria-expanded'), 'true');
      assert.deepEqual(await focus(), ['pair', second, mine]);
      assert.equal(await page.locator(`.saved-item[data-chart="${second}"] .settings-pair-choices`).getAttribute('aria-labelledby'), `settings-pair-${second}`);
      assert.equal(await page.locator(`#settings-pair-${second}`).textContent(), 'Pair Second with:');
      assert.deepEqual(await page.locator(`.saved-item[data-chart="${second}"] .settings-pair-choices button`).allInnerTexts(),
        ['Mine', 'First', 'A new birth', 'Cancel']);
      await page.locator(`[data-settings-action="pair-cancel"][data-chart="${second}"]`).focus();
      await page.keyboard.press('Enter');
      assert.deepEqual(await focus(), ['pair-start', second, null]);
      assert.equal(await start.getAttribute('aria-expanded'), 'false');
      await page.keyboard.press('Enter');
      assert.equal(await page.locator('.settings-pair-choices').count(), 1);
      await start.focus();
      await page.keyboard.press('Enter');
      assert.equal(await page.locator('.settings-pair-choices').count(), 0);
      assert.deepEqual(await focus(), ['pair-start', second, null]);
      // Paired from Second's row: my chart is in two couples now, the choices close and
      // the focus is on Pair with… again.
      await page.keyboard.press('Enter');
      await page.keyboard.press('Enter');
      await page.waitForFunction(() => new Set([...document.querySelectorAll('#settings-charts-body [data-settings-action="end"]')].map((end) => end.dataset.couple)).size === 2);
      assert.deepEqual((await read(page)).couples.map((couple) => couple.charts), [[mine, first], [second, mine]]);
      assert.equal(await page.locator('.settings-pair-choices').count(), 0);
      assert.deepEqual(await focus(), ['pair-start', second, null]);
      // My chart is paired with every other now: it offers none, and First offers Second.
      assert.deepEqual(await choices(page, mine), []);
      assert.deepEqual(await choices(page, first), ['Second']);
      await pairFrom(page, first, second);
      await page.waitForFunction(() => new Set([...document.querySelectorAll('#settings-charts-body [data-settings-action="end"]')].map((end) => end.dataset.couple)).size === 3);
      // No pair is left to form: the page says so.
      assert.ok((await page.locator('#settings-charts-body').textContent()).includes('No pair is left to form: each chart is paired with every other it can be.'));
      // A new birth can still be the partner of a chart paired with every other.
      await page.locator(`[data-settings-action="pair-start"][data-chart="${mine}"]`).click();
      assert.equal(await page.locator(`#settings-pair-${mine}`).textContent(), 'No other saved chart can pair with Mine.');
      await page.locator(`[data-settings-action="add-partner"][data-chart="${mine}"]`).click();
      await page.locator('#save-note').waitFor({ state: 'visible' });
      await page.locator('#save-name').fill('Fourth');
      await page.locator('#date').fill('1983-01-02');
      await page.locator('#time').fill('07:45');
      await page.locator('#location').fill('Helsinki');
      await page.locator('#location-suggestions .location-suggestion').click();
      await page.locator('#chart-form .gender-option input[value="female"]').check();
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
      await openSettings(page, 'charts');
      // Mine and First, at the cap, offer no pairing and are offered to none.
      for (const id of [mine, first]) assert.equal(await page.locator(`[data-settings-action="pair-start"][data-chart="${id}"]`).count(), 0);
      assert.deepEqual(await choices(page, second), ['Third']);
      assert.deepEqual(await choices(page, third), ['Second']);
      assert.ok((await page.locator('#settings-charts-body').textContent()).includes('On your plan a chart is in one couple at most: a chart in a couple already is not offered.'));
      assert.equal(await page.locator(`.saved-item[data-chart="${third}"] .saved-mark`).last().textContent(), 'Waiting to pair');
      // Mine, at the cap, marked as yours: the API's answer, on the same plan, has no
      // couple with Third, and the page says why.
      await page.route('**/api/account/my-chart', async (route) => {
        if (route.request().method() !== 'PUT') return route.fallback();
        const response = await route.fetch();
        return route.fulfill({ response, json: { ...(await response.json()), couples_per_chart: 1 } });
      });
      await page.locator(`[data-settings-action="mark"][data-chart="${mine}"]`).click();
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
      await openSettings(page, 'charts');
      await page.evaluate(() => {
        window.__toasts = [];
        new MutationObserver(() => {
          const said = document.querySelector('.toast')?.textContent ?? '';
          if (said !== '' && window.__toasts.at(-1) !== said) window.__toasts.push(said);
        }).observe(document.body, { subtree: true, childList: true, characterData: true });
      });
      await page.locator(`[data-settings-action="mark"][data-chart="${first}"]`).click();
      // Marked again, another chart, while the first is on its way.
      await page.locator(`[data-settings-action="mark"][data-chart="${second}"]`).click();
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
      await openSettings(page, 'charts');
      const marks = await page.locator(`#settings-charts-body .saved-item[data-chart="${mine}"] .saved-head`).textContent();
      assert.ok(marks.includes('Couple with Partner 1, Partner 2, Partner 3, and 7 more'), marks);
      assert.equal(await couplesDrawn(page), 10);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'no sideways scroll');
    });

    check('a pair formed already is refused in the page’s language, without asking', async (page) => {
      await reset(page);
      const mine = await saveElsewhere(page, { ...SCREEN, name: 'Mine' });
      const first = await saveElsewhere(page, partnerNamed('First', '1980-01-02'));
      await saveElsewhere(page, partnerNamed('Second', '1981-01-02'));
      await changeElsewhere(page, 'POST', '/api/account/couples', { charts: [mine, first] });
      await openSettings(page, 'charts');
      // Pair with… never offers it; chosen all the same (as a stale choice might be), it
      // is refused before the API is asked.
      const asked = [];
      page.on('request', (request) => {
        if (new URL(request.url()).pathname === '/api/account/couples') asked.push(request.method());
      });
      await page.locator(`[data-settings-action="pair-start"][data-chart="${mine}"]`).click();
      await page.locator(`.saved-item[data-chart="${mine}"] .settings-pair-choices .settings-actions`).evaluate((actions, { chart, other }) => {
        const stale = document.createElement('button');
        stale.type = 'button';
        stale.className = 'bar-action';
        Object.assign(stale.dataset, { settingsAction: 'pair', chart, with: other });
        stale.textContent = 'First';
        actions.prepend(stale);
      }, { chart: mine, other: first });
      await page.locator(`[data-settings-action="pair"][data-chart="${mine}"][data-with="${first}"]`).click();
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
        await openSettings(page, 'charts');
        await page.waitForFunction(() => document.getElementById('settings-status').textContent.includes('could not be read'));
        assert.equal(await page.locator('#settings-charts-body .saved-item').count(), 0);
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
        await openSettings(page, 'charts');
        await page.waitForFunction(() => document.getElementById('settings-status').textContent.includes('could not be read'));
        assert.equal(await page.locator('#settings-charts-body .saved-item').count(), 0, String(cap));
      }
    });

    check('Cancel on a birth added from Settings saves nothing and goes back', async (page) => {
      await reset(page);
      await openSettings(page, 'charts');
      await page.locator('[data-settings-action="add-mine"]').click();
      await page.locator('#save-note').waitFor({ state: 'visible' });
      assert.match(await page.locator('#save-note-text').textContent(), /saved as your chart/);
      await page.locator('#save-cancel').click();
      await page.locator('#settings-view').waitFor({ state: 'visible' });
      assert.equal(await page.evaluate(() => location.hash), '#charts');
      assert.deepEqual((await read(page)).charts, []);
      // The form, opened anew, is the plain form again.
      await page.locator('#settings-close').click();
      await page.locator('#input-view').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#save-note').isHidden(), true);
      assert.equal(await page.locator('#save-name-group').isHidden(), true);
      assert.equal(await page.locator('#create-chart-btn').textContent(), 'Create chart');
      // A chart may go without a gender again, and does until one is chosen.
      assert.equal(await page.locator('.gender-group legend').textContent(), 'Gender (optional)');
      assert.equal(await page.locator('#chart-form .gender-option:has(input[value=""])').isVisible(), true);
      assert.equal(await page.locator('#chart-form .gender-option input[value=""]').isChecked(), true);
    });

    check('Edit on a saved chart corrects it where it is kept, and the chart comes back on screen', async (page) => {
      await reset(page);
      const id = await saveElsewhere(page, { ...SCREEN, name: 'Kept' });
      await openLink(page, chartLink(), { place: HELSINKI });
      await page.waitForFunction(() => document.querySelector('#library-btn .library-label').textContent === 'Kept');
      // Edit: the form corrects the saved birth, filled with it, and says so.
      await press(page, '#back-btn');
      await page.locator('#save-note').waitFor({ state: 'visible' });
      assert.equal(await page.evaluate(() => location.hash), `#save?as=correct&chart=${id}&back=chart`);
      assert.equal(await page.locator('#save-note-text').textContent(), 'This corrects the birth of Kept.');
      assert.equal(await page.locator('#date').inputValue(), SCREEN.date);
      // Cancelled, the chart comes back as it was, and nothing is changed.
      await page.locator('#save-cancel').click();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      assert.equal(await page.evaluate(() => new URLSearchParams(location.hash.split('?')[1]).get('time')), SCREEN.time);
      assert.equal((await read(page)).charts[0].time, SCREEN.time);
      // Corrected, the saved chart is the corrected one, and it is on screen, still Kept.
      await press(page, '#back-btn');
      await page.locator('#save-note').waitFor({ state: 'visible' });
      await page.locator('#time').fill('21:15');
      await page.locator('#create-chart-btn').click();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await page.waitForFunction(() => !document.getElementById('chart-view').hasAttribute('aria-busy'));
      assert.equal(await page.evaluate(() => new URLSearchParams(location.hash.split('?')[1]).get('time')), '21:15');
      await page.waitForFunction(() => document.querySelector('#library-btn .library-label').textContent === 'Kept');
      const kept = (await read(page)).charts;
      assert.deepEqual(kept.map((chart) => [chart.id, chart.time]), [[id, '21:15']]);
      assert.equal(await page.locator('.toast').textContent(), 'The birth is corrected.');
    });

    check('a chart born in an hour the clocks repeat opens as its chart, at its pass, and is named', async (page) => {
      await reset(page);
      // 25 October 2020 in Helsinki: the clocks went back at 04:00, so 03:30 came twice.
      const REPEATED = { name: 'Repeated', date: '2020-10-25', time: '03:30', place: PLACE, fold: 1, gender: 'female', zi: 'split_midnight' };
      await saveElsewhere(page, REPEATED);
      await openSettings(page, 'charts');
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

    check('a chart without a gender is given one where it is saved, and the chart on screen takes it; My own chart marks it as yours', async (page) => {
      await reset(page);
      const genderless = chartLink({ gender: '' }).replace('&gender=', '');
      await openLink(page, genderless, { place: HELSINKI });
      await openLibrary(page);
      await page.locator('#library-save').click();
      await page.locator('#save-chart-dialog').waitFor({ state: 'visible' });
      // Asked here, with none chosen for the reader; nor is My own chart.
      assert.equal(await page.locator('#save-chart-gender').isVisible(), true);
      assert.deepEqual(await page.locator('#save-chart-gender input').evaluateAll((radios) => radios.map((radio) => [radio.value, radio.checked])),
        [['female', false], ['male', false]]);
      assert.equal(await page.locator('#save-chart-mine').isChecked(), false);
      assert.equal(await page.locator('#save-chart-mine-note').isHidden(), true);
      // Saved without one: nothing is saved, and the dialog says why.
      await page.locator('#save-chart-save').click();
      assert.equal(await page.locator('#save-chart-gender-status').textContent(), 'Choose female or male: a saved chart needs it.');
      assert.equal(await page.locator('#save-chart-dialog').isVisible(), true);
      assert.deepEqual((await read(page)).charts, []);
      // My own chart says what it does once chosen.
      await page.locator('#save-chart-mine').check();
      assert.equal(await page.locator('#save-chart-mine-note').textContent(), 'Each visit then opens its day.');
      await page.locator('#save-chart-gender input[value="male"]').check();
      assert.equal(await page.locator('#save-chart-gender-status').textContent(), '');
      await page.locator('#save-chart-name').fill('Given');
      await page.locator('#save-chart-save').click();
      await page.locator('#save-chart-dialog').waitFor({ state: 'hidden' });
      const kept = await read(page);
      assert.deepEqual([kept.charts.length, kept.charts[0].gender, kept.charts[0].name, kept.my_chart], [1, 'male', 'Given', kept.charts[0].id]);
      assert.equal(await page.locator('.toast').textContent(), 'The chart is saved as yours: each visit opens its day.');
      // The chart on screen takes the gender: its link names it, and it is the one saved.
      await page.waitForFunction(() => new URLSearchParams(location.hash.split('?')[1]).get('gender') === 'male');
      await page.waitForFunction(() => document.querySelector('#library-btn .library-label').textContent === 'Given');
      assert.equal(await page.locator('#luck-switch').isVisible(), true);
      // The same birth given the same gender is that chart: said, in the dialog, and not
      // asked of the API. The chart on screen was the saved one: the link's own is drawn
      // once the chart takes clicks again and its button says it is unsaved.
      await openLink(page, genderless, { place: HELSINKI });
      await page.waitForFunction(() => !document.getElementById('chart-view').hasAttribute('aria-busy')
        && document.querySelector('#library-btn .library-label').textContent === 'Unsaved chart');
      await openLibrary(page);
      await page.locator('#library-save').click();
      await page.locator('#save-chart-dialog').waitFor({ state: 'visible' });
      // Another chart is yours now: what My own chart would do says so.
      await page.locator('#save-chart-mine').check();
      assert.equal(await page.locator('#save-chart-mine-note').textContent(), 'Each visit then opens its day. Given is yours no longer, and stays saved.');
      await page.locator('#save-chart-gender input[value="male"]').check();
      const posted = [];
      const record = (request) => {
        if (new URL(request.url()).pathname === '/api/account/charts' && request.method() === 'POST') posted.push(request.url());
      };
      page.on('request', record);
      await page.locator('#save-chart-save').click();
      assert.equal(await page.locator('#save-chart-status').textContent(), 'This chart is saved already, as Given.');
      await page.waitForTimeout(300);
      page.off('request', record);
      assert.deepEqual(posted, [], 'the API is not asked to save it');
      assert.equal((await read(page)).charts.length, 1);
    });

    check('the save window is every window: its title in the bar with Close, which saves nothing, and Save its one action', async (page) => {
      await reset(page);
      await openLink(page, chartLink(), { place: HELSINKI });
      await openLibrary(page);
      await page.locator('#library-save').click();
      await page.locator('#save-chart-dialog').waitFor({ state: 'visible' });
      // As the library's and the account's windows: a serif title, and Close beside it.
      const looks = (selector) => page.locator(selector).evaluate((node) => {
        const style = getComputedStyle(node);
        return [style.fontFamily, style.fontSize, style.fontWeight];
      });
      assert.deepEqual(await looks('#save-chart-title'), await looks('#library-title'));
      assert.equal(await page.locator('#save-chart-dialog .chart-dialog-bar #save-chart-close').isVisible(), true);
      assert.equal(await page.locator('#save-chart-save').getAttribute('class'), 'submit-btn');
      assert.equal(await page.locator('#save-chart-dialog button').filter({ hasText: 'Cancel' }).count(), 0);
      await page.locator('#save-chart-name').fill('Not kept');
      await page.locator('#save-chart-close').click();
      await page.locator('#save-chart-dialog').waitFor({ state: 'hidden' });
      assert.deepEqual((await read(page)).charts, []);
      assert.equal(await nameOnScreen(page), 'Unsaved chart');
    });

    check('an error said about a page goes when another page opens; a confirmation stays its time', async (page) => {
      await page.addInitScript(() => {
        Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async () => { throw new Error('Refused by the test.'); } } });
      });
      await reset(page);
      await changeElsewhere(page, 'PUT', '/api/account/place', { place: PLACE });
      await openLink(page, chartLink(), { place: HELSINKI });
      await press(page, '#copy-link-btn');
      await page.waitForFunction(() => document.querySelector('.toast.is-error.is-shown') !== null);
      // The chart's error is not the day's.
      await page.locator('#page-switch [data-page="today"]').click();
      await page.locator('#today-view').waitFor({ state: 'visible' });
      await page.waitForFunction(() => !document.querySelector('.toast').classList.contains('is-shown'));
      assert.equal(await page.locator('.toast').textContent(), '');
    });

    check('a name with quotes is changed from the name itself, quotes and all', async (page) => {
      await reset(page);
      const name = 'Quoted "name" <b>bold</b> & \'single\'';
      const id = await saveElsewhere(page, { ...SCREEN, name });
      await openSettings(page, 'charts');
      await page.locator(`#settings-charts-body [data-settings-action="rename"][data-chart="${id}"]`).click();
      const field = page.locator(`#settings-rename-${id}`);
      assert.equal(await field.inputValue(), name);
      // Saved as it stands, the name is the same.
      await field.press('Enter');
      await page.waitForFunction(() => document.querySelector('.settings-rename') === null);
      assert.equal((await read(page)).charts.at(-1).name, name);
      assert.equal(await page.locator(`#settings-charts-body .saved-item[data-chart="${id}"] .saved-name`).textContent(), name);
    });

    check('pressed again while it is on its way, a pairing is asked for once', async (page) => {
      await reset(page);
      const first = await saveElsewhere(page, SCREEN);
      const second = await saveElsewhere(page, partnerNamed('Second'));
      await openSettings(page, 'charts');
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
      await page.locator(`[data-settings-action="pair-start"][data-chart="${first}"]`).click();
      const pair = page.locator(`[data-settings-action="pair"][data-chart="${first}"][data-with="${second}"]`);
      await pair.click();
      await pair.click();
      // The same couple, chosen from the other chart's row, is the same change.
      await pairFrom(page, second, first);
      release();
      await page.locator('#settings-charts-body [data-settings-action="end"]').first().waitFor();
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
      await openSettings(page, 'charts');
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
      await page.locator(`[data-settings-action="mark"][data-chart="${second}"]`).click();
      await page.locator(`[data-settings-action="unmark"][data-chart="${first}"]`).click();
      await page.locator(`[data-settings-action="mark"][data-chart="${second}"]`).click();
      release();
      await page.waitForFunction(() => document.querySelector('#settings-charts-body .saved-item .saved-mark.is-mine')?.closest('.saved-item').querySelector('.saved-name').textContent === 'Second');
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

    check('an unlimited library can save the chart and start another from Settings', async (page) => {
      await reset(page);
      // This release's server still writes finite allowances. Exercise the reader
      // contract against its real settings, changing only that future value.
      await page.route('**/api/account/settings', async (route) => {
        const response = await route.fetch();
        const value = await response.json();
        await route.fulfill({ response, json: { ...value, chart_limit: null } });
      });
      await openLink(page, chartLink(), { place: HELSINKI });
      await openLibrary(page);
      await page.locator('#library-save').click();
      await page.locator('#save-chart-dialog').waitFor({ state: 'visible' });
      await page.locator('#save-chart-name').fill('Unlimited reader');
      await page.locator('#save-chart-save').click();
      await page.locator('#save-chart-dialog').waitFor({ state: 'hidden' });
      assert.deepEqual((await read(page)).charts.map((chart) => chart.name), ['Unlimited reader']);
      await openSettings(page, 'charts');
      await page.locator('#settings-charts-body [data-settings-action="add-mine"]').click();
      await page.locator('#save-note').waitFor({ state: 'visible' });
      assert.match(await page.locator('#save-note-text').textContent(), /saved as your chart/);
      await page.route('**/api/location_suggest', (route) => route.fulfill({ json: { suggestions: [HELSINKI] } }));
      await page.locator('#save-name').fill('Unlimited form');
      await page.locator('#date').fill('1975-08-14');
      await page.locator('#time').fill('07:45');
      await page.locator('#location').fill('Helsinki');
      await page.locator('#location-suggestions .location-suggestion').click();
      await page.locator('#chart-form .gender-option input[value="female"]').check();
      await page.locator('#create-chart-btn').click();
      await page.locator('#settings-view').waitFor({ state: 'visible' });
      assert.deepEqual((await read(page)).charts.map((chart) => chart.name), ['Unlimited reader', 'Unlimited form']);
    });

    check('malformed library allowances are refused visibly', async (page) => {
      await reset(page);
      for (const limit of [undefined, 0, -1, 1.5, '50', false]) {
        await page.route('**/api/account/settings', async (route) => {
          const response = await route.fetch();
          const value = await response.json();
          await route.fulfill({ response, json: { ...value, chart_limit: limit } });
        });
        await openSettings(page, 'charts');
        assert.match(await page.locator('#settings-status').textContent(), /200/);
        assert.equal(await page.locator('#settings-charts-body [data-settings-action="open"]').count(), 0);
        await page.unroute('**/api/account/settings');
      }
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
      await openSettings(page, 'charts');
      await page.locator('#settings-charts-body [data-settings-action="add-mine"]').click();
      await page.waitForFunction((message) => document.getElementById('settings-status').textContent === message, message);
      assert.equal(await page.evaluate(() => location.hash), '#charts');
      assert.deepEqual(asked, []);
    });

    check('removing a chart says first what else ends with it', async (page) => {
      await reset(page);
      const mine = await saveElsewhere(page, { ...SCREEN, name: 'Mine' });
      const partner = await saveElsewhere(page, partnerNamed('Partner'));
      const single = await saveElsewhere(page, partnerNamed('Single', '1980-01-02'));
      await changeElsewhere(page, 'PUT', '/api/account/my-chart', { chart: mine });
      await changeElsewhere(page, 'POST', '/api/account/couples', { charts: [mine, partner] });
      await openSettings(page, 'charts');
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
      await openSettings(page, 'charts');
      assert.equal(await asking(mine), 'Remove Mine? It is your chart: none is marked as yours then.');
      // A chart waiting to pair with your chart, as a partner kept from before charts
      // waits, stops waiting.
      await changeElsewhere(page, 'DELETE', '/api/account/my-chart', {});
      await page.route('**/api/account/settings', async (route) => {
        if (route.request().method() !== 'GET') return route.fallback();
        const response = await route.fetch();
        return route.fulfill({ response, json: { ...(await response.json()), pending_partner: single } });
      });
      await openSettings(page, 'charts');
      assert.equal(await asking(single), 'Remove Single? Then it won’t pair with your chart.');
      assert.equal((await read(page)).charts.length, 3, 'nothing was removed');
    });

    check('a birth saved already is said so by the form, in the page’s language, and the API is not asked', async (page) => {
      await reset(page);
      await page.route('**/api/location_suggest', (route) => route.fulfill({ json: { suggestions: [HELSINKI] } }));
      await saveElsewhere(page, { ...SCREEN, time: '21:05', name: 'Kept' });
      await openSettings(page, 'charts');
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
      await page.locator(`#chart-form .gender-option input[value="${BIRTH.gender}"]`).check();
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
      await openSettings(page, 'charts');
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
      await page.locator(`[data-settings-action="mark"][data-chart="${mine}"]`).click();
      await page.waitForFunction(() => document.querySelector('.toast').textContent !== '');
      assert.equal(await page.locator('.toast').textContent(), 'Your chart is marked, and paired with Waiting.');
      // Saved as yours from the form, the same.
      await changeElsewhere(page, 'DELETE', '/api/account/my-chart', {});
      await page.route('**/api/account/charts', paired('POST', null));
      await openSettings(page, 'charts');
      await page.locator('[data-settings-action="add-mine"]').click();
      await page.locator('#save-note').waitFor({ state: 'visible' });
      await page.locator('#date').fill('1990-01-02');
      await page.locator('#time').fill('10:00');
      await page.locator('#location').fill('Helsinki');
      await page.locator('#location-suggestions .location-suggestion').click();
      await page.locator('#chart-form .gender-option input[value="female"]').check();
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
  it('signed in, the bare address opens my chart\'s day, today where I am, replacing the address; a chart link opens itself', { timeout: 120000 }, () => withPage(profiles[0], async (page) => {
    const own = await newAccount(playwright, { language: 'en', label: 'settings-mine' });
    await asAccount(playwright, own, async (request) => {
      const kept = await request.post('/api/account/charts', { data: { ...SCREEN, name: 'Mine', mine: true, key: own.key, updated_at: null } });
      assert.equal(kept.status(), 201, await kept.text());
    });
    await signInPage(page, own);
    await page.goto(new URL('/', process.env.EC_BASE_URL).href);
    const entries = await page.evaluate(() => history.length);
    await page.locator('#today-view').waitFor({ state: 'visible' });
    // Its day, by its name, on today's date: with no place kept, the browser's own.
    const part = (name) => page.evaluate((name) => new URLSearchParams(location.hash.split('?')[1]).get(name), name);
    assert.equal(await page.evaluate(() => location.hash.startsWith('#today?')), true);
    assert.equal(await part('date'), BIRTH.date);
    assert.equal(await part('day'), await page.evaluate(() => new Date().toLocaleDateString('sv-SE')));
    await page.waitForFunction(() => document.querySelector('#today-library-btn .library-label').textContent === 'Mine');
    // The address was replaced, not added to: Back does not come to it again.
    assert.equal(await page.evaluate(() => history.length), entries);
    assert.equal(await page.locator('#start-charts').isHidden(), true);
    // A chart link opens its own chart; New chart still opens the form, and only the form.
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
    await page.waitForTimeout(300);
    assert.equal(await page.locator('#start-charts').isHidden(), true);
  }, { signedIn: false }));

  it('signed in without a chart of my own, the start page begins with my saved charts: each opens its chart, and Mark as yours opens its day', { timeout: 120000 }, () => withPage(profiles[0], async (page) => {
    const own = await newAccount(playwright, { language: 'en', label: 'settings-start' });
    await signInPage(page, own);
    // With nothing saved, the start page is the form alone.
    await page.goto(new URL('/', process.env.EC_BASE_URL).href);
    await page.locator('#input-view').waitFor({ state: 'visible' });
    await page.waitForTimeout(500);
    assert.equal(await page.locator('#start-charts').isHidden(), true);
    await saveElsewhere(page, { ...SCREEN, name: 'Aino' });
    await saveElsewhere(page, partnerNamed('Ville'));
    await page.reload();
    await page.locator('#start-charts').waitFor({ state: 'visible' });
    const names = () => page.locator('#start-charts-list .saved-name').allTextContents();
    assert.deepEqual(await names(), ['Aino', 'Ville']);
    assert.equal(await page.locator('#start-charts-note').textContent(), 'Which one is yours? Mark it as yours, and each visit opens its day.');
    assert.deepEqual(await page.locator('[data-start-mine]').allTextContents(), ['Mark as yours', 'Mark as yours']);
    assert.equal(await page.locator('#input-view').isVisible(), true);
    // In the page's language, as it changes.
    await page.locator('.lang-btn[data-lang="fi"]').click();
    await page.waitForFunction(() => document.querySelector('[data-start-mine]')?.textContent === 'Merkitse omaksi');
    await page.locator('.lang-btn[data-lang="en"]').click();
    await page.waitForFunction(() => document.querySelector('[data-start-mine]')?.textContent === 'Mark as yours');
    // Each opens its chart, and Back comes to the start page again.
    await page.locator('#start-charts-list [data-start-chart]').nth(1).click();
    await page.locator('#chart-view').waitFor({ state: 'visible' });
    await page.waitForFunction(() => document.querySelector('#library-btn .library-label').textContent === 'Ville');
    await page.goBack();
    await page.locator('#start-charts').waitFor({ state: 'visible' });
    assert.deepEqual(await names(), ['Aino', 'Ville']);
    // A mark made from settings another tab has changed since is refused, said, and the
    // list is drawn as the settings are now.
    const [aino] = (await read(page)).charts;
    await changeElsewhere(page, 'PUT', `/api/account/charts/${aino.id}/name`, { name: 'Aino K' });
    await page.locator('[data-start-mine]').first().click();
    await page.waitForFunction(() => document.querySelector('.toast')?.textContent === 'Your settings changed elsewhere. They are shown as they are now: choose again.');
    await page.waitForFunction(() => document.querySelector('#start-charts-list .saved-name')?.textContent === 'Aino K');
    assert.equal((await read(page)).my_chart, null);
    // Marked: its day opens, as each visit now opens it.
    await page.locator('[data-start-mine]').first().click();
    await page.locator('#today-view').waitFor({ state: 'visible' });
    await page.waitForFunction(() => document.querySelector('.toast')?.textContent === 'Your chart is marked.');
    assert.equal((await read(page)).my_chart, aino.id);
    assert.equal(await page.evaluate(() => new URLSearchParams(location.hash.split('?')[1]).get('date')), BIRTH.date);
    await page.goto(new URL('/', process.env.EC_BASE_URL).href);
    await page.locator('#today-view').waitFor({ state: 'visible' });
    await page.waitForFunction(() => document.querySelector('#today-library-btn .library-label').textContent === 'Aino K');
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
