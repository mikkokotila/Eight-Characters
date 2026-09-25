// Run with Node's built-in test runner and an explicitly selected Playwright install.
// No frontend build step or production dependencies are required.
import assert from 'node:assert/strict';
import { before, after, describe, it } from 'node:test';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';

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

const location = { timezone: 'Asia/Shanghai', longitude: 104.066, latitude: 30.658 };
const profiles = [
  { name: 'desktop', viewport: { width: 1440, height: 1000 }, hasTouch: false, isMobile: false },
  { name: 'mobile', viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true },
];

async function count(page, selector, expected) {
  await page.waitForFunction(({ selector, expected }) =>
    document.querySelectorAll(selector).length === expected, { selector, expected });
}

async function settled(page) {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(document.getAnimations().map((animation) => animation.finished));
  });
  await count(page, '.is-turning', 0);
}

async function fillChart(page, { date = '1988-02-04', time = '16:30', lang = 'en', success = true } = {}) {
  await page.locator(`[data-lang="${lang}"]`).click();
  await page.locator('#date').fill(date);
  await page.locator('#time').fill(time);
  await page.locator('#location').fill('Chengdu');
  await page.locator('.location-suggestion').click();
  await page.locator('#create-chart-btn').click();
  await page.locator(success ? '#chart-view' : '#form-error').waitFor({ state: 'visible' });
  if (success) await settled(page);
}

async function openChart(page, options = {}, mutate = null) {
  // Only geocoding is stubbed. Every chart and context record is calculated by the real API.
  let calculated;
  await page.route('**/api/location_suggest', (route) => route.fulfill({ json: { suggestions: [
    { city: 'Chengdu', region: 'Sichuan', country: 'China', ...location, display: 'Chengdu, Sichuan, China' },
  ] } }));
  await page.route('**/api/four_pillars', async (route) => {
    const body = route.request().postDataJSON();
    assert.equal(body.include_interactions, true);
    assert.equal(body.include_day_master_context, true);
    assert.equal(body.include_role_profile, true);
    // Assert the actual picked coordinates; do not rewrite the app's request.
    assert.deepEqual(body.location, location);
    assert.equal(body.city, undefined);
    assert.equal(body.country, undefined);
    const response = await route.fetch();
    assert.equal(response.status(), 200);
    const payload = await response.json();
    calculated = payload;
    if (mutate) mutate(payload);
    await route.fulfill({ response, json: payload });
  });
  await page.goto(baseURL);
  await fillChart(page, options);
  return calculated;
}

async function geometry(page) {
  return page.locator('.pillar').evaluateAll((pillars) => pillars.map((pillar) => {
    const r = pillar.getBoundingClientRect();
    return { x: r.x + scrollX, y: r.y + scrollY, width: r.width, height: r.height };
  }));
}

async function natalColors(page) {
  return page.locator('.card-front').evaluateAll((cards) => cards.map((card) => getComputedStyle(card).backgroundColor));
}

async function longPress(page, card) {
  await card.scrollIntoViewIfNeeded();
  const box = await card.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  const component = await card.evaluate((node) => node.classList.contains('stem') ? 'stem' : 'branch');
  const pillar = await card.getAttribute('data-pillar');
  await page.mouse.down();
  try {
    await page.waitForFunction((selector) => document.querySelector(selector).classList.contains('is-flipped'),
      `.card.${component}[data-pillar="${pillar}"]`);
  } finally {
    await page.mouse.up();
  }
  await settled(page);
}

async function screenshot(page, name) {
  if (!process.env.EC_SCREENSHOT_DIR) return;
  await mkdir(process.env.EC_SCREENSHOT_DIR, { recursive: true });
  await page.screenshot({ path: join(process.env.EC_SCREENSHOT_DIR, `${engineName}-${name}.png`), fullPage: true });
}

export { assert, describe, it, engineName, profiles, openChart, fillChart, count, settled, geometry, natalColors, longPress, screenshot };
export async function withPage(profile, run) {
  const { name, ...options } = profile;
  const page = await browser.newPage(options);
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  try { await run(page); assert.deepEqual(errors, [], 'Uncaught browser errors'); }
  finally { await page.close(); }
}
