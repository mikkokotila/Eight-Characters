// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Covers picking the birth place and handing it to the chart and the explorer.
import assert from 'node:assert/strict';
import { before, after, describe, it } from 'node:test';

const moduleName = process.env.EC_PLAYWRIGHT_MODULE;
const baseURL = process.env.EC_BASE_URL;
const engineName = process.env.EC_BROWSER;
assert.ok(moduleName, 'Set EC_PLAYWRIGHT_MODULE to playwright or its index.mjs path.');
assert.ok(baseURL, 'Set EC_BASE_URL to the app under test.');
assert.ok(['chromium', 'webkit'].includes(engineName), 'Set EC_BROWSER to chromium or webkit.');
const playwright = await import(moduleName);
let browser;
before(async () => { browser = await playwright[engineName].launch({ headless: true }); });
after(async () => { if (browser) await browser.close(); });

const profiles = [
  { name: 'desktop', viewport: { width: 1440, height: 1000 }, hasTouch: false, isMobile: false },
  { name: 'mobile', viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true },
];

// Suggestions as /api/location_suggest returns them, from open-meteo results (2026-09-25).
function place(city, region, country, timezone, latitude, longitude) {
  const display = [city, region, country].filter(Boolean).join(', ');
  return { city, region, country, timezone, latitude, longitude, display };
}
const CHENGDU_SICHUAN = place('Chengdu', 'Sichuan', 'China', 'Asia/Shanghai', 30.66667, 104.06667);
const CHENGDU_JIANGXI = place('Chengdu', 'Jiangxi', 'China', 'Asia/Shanghai', 26.36828, 115.34289);
const CHENGDU_JIAN = place('Chengdu', 'Jiangxi', 'China', 'Asia/Shanghai', 26.983, 114.207);
const ZHENGZHOU = place('Zhengzhou', 'Henan', 'China', 'Asia/Shanghai', 34.75778, 113.64861);
const HELSINKI = place('Helsinki', 'Uusimaa', 'Finland', 'Europe/Helsinki', 60.16952, 24.93545);
const SUGGESTIONS = {
  // The partial query ranks another city first.
  Cheng: [ZHENGZHOU, CHENGDU_SICHUAN],
  Chengdu: [CHENGDU_SICHUAN, CHENGDU_JIANGXI, CHENGDU_JIAN],
  // A full list: eight settlements, the most the page asks for.
  Chengd: [
    CHENGDU_SICHUAN,
    place('Chengde', 'Hebei', 'China', 'Asia/Shanghai', 40.9519, 117.95883),
    place('Chengdi', 'Shanxi', 'China', 'Asia/Shanghai', 36.71667, 113.1),
    place('Xiabancheng', 'Hebei', 'China', 'Asia/Shanghai', 40.77028, 118.16972),
    place('Chengde', 'Jilin', 'China', 'Asia/Shanghai', 43.24478, 126.06567),
    place('Chengde', 'Taiwan', 'Taiwan', 'Asia/Taipei', 22.6105, 120.60327),
    place('Chengdi', 'Fujian', 'China', 'Asia/Shanghai', 26.13078, 116.96451),
    place('Chengdi', 'Jiangxi', 'China', 'Asia/Shanghai', 26.14101, 116.07928),
  ],
  Helsinki: [HELSINKI],
};

const locationOf = ({ timezone, latitude, longitude }) => ({ timezone, latitude, longitude });

// Only geocoding is stubbed; charts and explorer graphs are calculated by the real API.
async function stubSuggestions(page, delays = {}) {
  await page.route('**/api/location_suggest', async (route) => {
    const { query } = route.request().postDataJSON();
    if (delays[query]) await new Promise((resolve) => setTimeout(resolve, delays[query]));
    await route.fulfill({ json: { suggestions: SUGGESTIONS[query] ?? [] } });
  });
}

async function rows(page) {
  return page.locator('.location-suggestion').evaluateAll((buttons) => buttons.map((button) => [
    button.querySelector('.location-suggestion-city').textContent,
    button.querySelector('.location-suggestion-meta').textContent,
  ]));
}

async function search(page, query, firstDisplay) {
  await page.locator('#location').fill(query);
  await page.waitForFunction(({ query, firstDisplay }) =>
    document.getElementById('location').value === query
    && !document.getElementById('location-suggestions').classList.contains('hidden')
    && document.querySelector('.location-suggestion-city')?.textContent === firstDisplay,
  { query, firstDisplay });
}

async function createChart(page) {
  const request = page.waitForRequest('**/api/four_pillars');
  await page.locator('#create-chart-btn').click();
  const body = (await request).postDataJSON();
  await page.locator('#chart-view').waitFor({ state: 'visible' });
  return body;
}

async function hourPillar(page) {
  return page.evaluate(() => ['stem', 'branch']
    .map((kind) => document.querySelector(`#pillars .card.${kind}[data-pillar="hour"]`).dataset.char)
    .join(''));
}

async function formState(page) {
  return page.evaluate(() => ({
    value: document.getElementById('location').value,
    status: document.getElementById('location-status').textContent,
    found: document.getElementById('location-status').classList.contains('is-found'),
    createDisabled: document.getElementById('create-chart-btn').disabled,
  }));
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / location`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 30000 }, async () => {
      const { name: _name, ...options } = profile;
      const page = await browser.newPage(options);
      const errors = [];
      page.on('pageerror', (error) => errors.push(error.message));
      try {
        await run(page);
        assert.deepEqual(errors, [], 'Uncaught browser errors');
      } finally {
        await page.close();
      }
    });

    check('places sharing a name are told apart and the picked one is charted', async (page) => {
      await stubSuggestions(page);
      await page.goto(baseURL);
      await page.locator('[data-lang="en"]').click();
      await page.locator('#date').fill('1988-02-04');
      await page.locator('#time').fill('15:40');
      await search(page, 'Chengdu', CHENGDU_SICHUAN.display);
      assert.deepEqual(await rows(page), [
        ['Chengdu, Sichuan, China', '30.67° N, 104.07° E · Asia/Shanghai'],
        ['Chengdu, Jiangxi, China', '26.37° N, 115.34° E · Asia/Shanghai'],
        ['Chengdu, Jiangxi, China', '26.98° N, 114.21° E · Asia/Shanghai'],
      ]);
      await page.locator('.location-suggestion').nth(1).click();
      assert.deepEqual(await formState(page), {
        value: 'Chengdu, Jiangxi, China',
        status: 'Chengdu (26.37° N, 115.34° E, Asia/Shanghai) selected',
        found: true,
        createDisabled: false,
      });
      const body = await createChart(page);
      assert.deepEqual(body.location, locationOf(CHENGDU_JIANGXI));
      assert.equal('city' in body || 'country' in body, false);
      // True solar time is 15:07 there; the Sichuan Chengdu would give 14:22, a 未 hour.
      assert.equal(await hourPillar(page), '壬申');
      assert.match(await page.locator('#chart-date').textContent(), / · Chengdu$/);
    });

    check('a slower answer for an earlier query never replaces the list', async (page) => {
      await stubSuggestions(page, { Cheng: 1500 });
      const aborted = [];
      page.on('requestfailed', (request) => {
        if (request.url().endsWith('/api/location_suggest')) aborted.push(request.postDataJSON().query);
      });
      await page.goto(baseURL);
      await page.locator('[data-lang="en"]').click();
      await page.evaluate(() => {
        // Every list the page shows, with the text it was shown under.
        window.shownLists = [];
        const list = document.getElementById('location-suggestions');
        new MutationObserver(() => {
          const first = list.querySelector('.location-suggestion-city');
          if (!list.classList.contains('hidden') && first) {
            window.shownLists.push([document.getElementById('location').value, first.textContent]);
          }
        }).observe(list, { childList: true, attributes: true, subtree: true });
      });
      const partial = page.waitForRequest((request) => request.url().endsWith('/api/location_suggest')
        && request.postDataJSON().query === 'Cheng');
      await page.locator('#location').fill('Cheng');
      await partial;
      await search(page, 'Chengdu', CHENGDU_SICHUAN.display);
      await page.waitForTimeout(2000);
      assert.deepEqual(aborted, ['Cheng']);
      assert.deepEqual(await page.evaluate(() => window.shownLists), [['Chengdu', CHENGDU_SICHUAN.display]]);
      assert.equal(await page.locator('#location-status').textContent(), 'Select a city from the list.');
    });

    check('editing a picked place drops the pick until another is chosen', async (page) => {
      await stubSuggestions(page);
      await page.goto(baseURL);
      await page.locator('[data-lang="en"]').click();
      await search(page, 'Chengdu', CHENGDU_SICHUAN.display);
      await page.locator('.location-suggestion').nth(1).click();
      assert.equal(await page.locator('#location').isEditable(), true);
      await page.locator('#location').fill('Helsinki');
      const edited = await formState(page);
      assert.equal(edited.createDisabled, true);
      assert.equal(edited.found, false);
      await search(page, 'Helsinki', HELSINKI.display);
      await page.locator('.location-suggestion').first().click();
      assert.deepEqual(await formState(page), {
        value: 'Helsinki, Uusimaa, Finland',
        status: 'Helsinki (60.17° N, 24.94° E, Europe/Helsinki) selected',
        found: true,
        createDisabled: false,
      });
    });

    check('returning from the chart keeps the pick for another date', async (page) => {
      await stubSuggestions(page);
      await page.goto(baseURL);
      await page.locator('[data-lang="en"]').click();
      await page.locator('#date').fill('1990-06-12');
      await page.locator('#time').fill('09:40');
      await search(page, 'Helsinki', HELSINKI.display);
      await page.locator('.location-suggestion').first().click();
      const picked = await formState(page);
      assert.deepEqual((await createChart(page)).location, locationOf(HELSINKI));
      await page.locator('#back-btn').click();
      assert.deepEqual(await formState(page), picked);
      await page.locator('#date').fill('1991-07-13');
      const again = await createChart(page);
      assert.equal(again.date, '1991-07-13');
      assert.deepEqual(again.location, locationOf(HELSINKI));
      assert.match(await page.locator('#chart-date').textContent(), /1991 · 09:40 · Helsinki$/);
      await page.locator('#back-btn').click();
      await page.locator('#location').fill(HELSINKI.display.slice(0, -1));
      const edited = await formState(page);
      assert.equal(edited.createDisabled, true);
      assert.equal(edited.found, false);
    });

    check('suggestions are a listbox hanging from the field, showing all eight without scrolling', async (page) => {
      await stubSuggestions(page);
      await page.goto(baseURL);
      await page.locator('[data-lang="en"]').click();
      await search(page, 'Chengd', CHENGDU_SICHUAN.display);
      const layout = await page.evaluate(() => {
        const field = document.getElementById('location').getBoundingClientRect();
        const list = document.getElementById('location-suggestions');
        const box = list.getBoundingClientRect();
        // The list hangs one step of the spacing scale below the field.
        const step = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--space-2'));
        return {
          gap: Math.round(box.top - field.bottom) - step, left: box.left - field.left, width: box.width - field.width,
          scrolls: list.scrollHeight > list.clientHeight,
        };
      });
      assert.deepEqual(layout, { gap: 0, left: 0, width: 0, scrolls: false });
      const field = page.locator('#location');
      assert.equal(await field.getAttribute('role'), 'combobox');
      assert.equal(await field.getAttribute('aria-expanded'), 'true');
      assert.equal(await field.getAttribute('aria-controls'), 'location-suggestions');
      assert.equal(await page.locator('#location-suggestions').getAttribute('role'), 'listbox');
      assert.equal(await page.locator('#location-suggestions [role="option"]').count(), 8);
      await field.press('ArrowDown');
      await field.press('ArrowDown');
      assert.equal(await field.getAttribute('aria-activedescendant'), 'location-option-1');
      assert.deepEqual(await page.locator('[role="option"]').evaluateAll((options) =>
        options.map((option) => option.getAttribute('aria-selected'))),
      ['false', 'true', 'false', 'false', 'false', 'false', 'false', 'false']);
      await field.press('Escape');
      assert.equal(await field.getAttribute('aria-expanded'), 'false');
      assert.equal(await field.getAttribute('aria-activedescendant'), null);
    });

    check('a place picked with the pointer leaves focus in the field', async (page) => {
      await stubSuggestions(page);
      await page.goto(baseURL);
      await page.locator('[data-lang="en"]').click();
      await search(page, 'Chengdu', CHENGDU_SICHUAN.display);
      await page.locator('.location-suggestion').nth(1).click();
      assert.equal(await page.evaluate(() => document.activeElement.id), 'location');
      assert.equal((await formState(page)).value, 'Chengdu, Jiangxi, China');
    });

    check('a search with no place says so, and a malformed answer is an error', async (page) => {
      await stubSuggestions(page);
      await page.goto(baseURL);
      await page.locator('[data-lang="en"]').click();
      await page.locator('#location').fill('Atlantis');
      await page.waitForFunction(() => document.getElementById('location-status').textContent === 'No matching places.');
      assert.equal(await page.locator('#location-suggestions').isVisible(), false);
      assert.equal(await page.locator('#location').getAttribute('aria-expanded'), 'false');
      await page.route('**/api/location_suggest', (route) => route.fulfill({ json: { places: [] } }));
      await page.locator('#location').fill('Helsinki');
      await page.waitForFunction(() => document.getElementById('location-status').classList.contains('is-error'));
      assert.equal(await page.locator('#location-status').textContent(), 'Location search failed.');
    });

    check("the chart's Evolution view opens the explorer for the picked place", async (page) => {
      await stubSuggestions(page);
      await page.goto(baseURL);
      await page.locator('#date').fill('1988-02-04');
      await page.locator('#time').fill('15:40');
      await search(page, 'Chengdu', CHENGDU_SICHUAN.display);
      await page.locator('.location-suggestion').nth(1).click();
      assert.deepEqual((await createChart(page)).location, locationOf(CHENGDU_JIANGXI));
      const request = page.waitForRequest('**/api/evolution_explorer');
      await page.locator('#view-switch button[data-view="evolution"]').click();
      const body = (await request).postDataJSON();
      assert.deepEqual(body, { date: '1988-02-04', time: '15:40', location: locationOf(CHENGDU_JIANGXI) });
      const { lang: _lang, ...link } = Object.fromEntries(new URL(page.url()).searchParams);
      assert.deepEqual(link, {
        date: '1988-02-04', time: '15:40', latitude: '26.36828', longitude: '115.34289',
        timezone: 'Asia/Shanghai',
      });
      await page.waitForFunction(() => /nodes visible/.test(document.getElementById('statusBar').textContent));
    });

    check('explorer links name the place once, completely', async (page) => {
      const sent = [];
      await page.route('**/api/evolution_explorer', (route) => {
        sent.push(route.request().postDataJSON());
        return route.fulfill({ status: 400, json: { detail: 'Stopped by the test.' } });
      });
      const open = async (query) => {
        await page.goto(`${baseURL}/explorer/?${query}`);
        await page.waitForFunction(() => document.getElementById('statusBar').textContent.trim() !== '');
        return page.locator('#statusBar').textContent();
      };
      assert.match(await open('date=1988-02-04&time=15:40&latitude=26.36828'),
        /needs a numeric latitude and longitude and a timezone/);
      assert.match(await open('date=1988-02-04&time=15:40&latitude=26.36828&longitude=115.34289'
        + '&timezone=Asia%2FShanghai&city=Chengdu&country=China'), /names the place twice/);
      assert.match(await open('date=1988-02-04&time=15:40&city=Hong+Kong&country='),
        /needs both the city and the country/);
      assert.deepEqual(sent, []);
      // Links from before coordinates were passed still resolve the place by name.
      assert.match(await open('date=1988-02-04&time=15:40&city=Chengdu&country=China'), /Stopped by the test/);
      assert.deepEqual(sent, [{ date: '1988-02-04', time: '15:40', city: 'Chengdu', country: 'China' }]);
    });
  });
}
