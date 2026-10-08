// The account pages as the account suites drive them: the start page as a visitor
// finds it, the chart form, and the account dialog. Imported by account.test.mjs and
// account-sessions.test.mjs.
import { CHENGDU } from './chart-helpers.mjs';
import { readCode, stubTurnstile, turnstileAnswered } from './account-helpers.mjs';

const baseURL = process.env.EC_BASE_URL;
export const BIRTH = { date: '1988-02-04', time: '16:30' };
// The canonical chart's link, and a second birth's, as the app writes them.
export const link = (date, time, lang) => new URLSearchParams({
  date, time, place: CHENGDU.display, city: CHENGDU.city, latitude: String(CHENGDU.latitude),
  longitude: String(CHENGDU.longitude), timezone: CHENGDU.timezone, lang,
});

// The start page as a visitor finds it, in a language; or a link's address. Only the
// place search and Cloudflare's widget are stubbed.
export async function visit(page, { lang = 'en', address = '', turnstile = true } = {}) {
  await stubTurnstile(page, { load: turnstile });
  await page.route('**/api/location_suggest', (route) => route.fulfill({ json: { suggestions: [CHENGDU] } }));
  // A first visit has no language of its own: the browser's decides it.
  await page.addInitScript((lang) => {
    if (!localStorage.getItem('eight_characters_lang')) localStorage.setItem('eight_characters_lang', lang);
  }, lang);
  await page.goto(new URL(`/${address}`, baseURL).href);
}

// Every chart the page asks for, as it asks.
export function chartsAskedFor(page) {
  const asked = [];
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/api/four_pillars') asked.push(request.postDataJSON());
  });
  return asked;
}

export async function askForChart(page) {
  await page.locator('#date').fill(BIRTH.date);
  await page.locator('#time').fill(BIRTH.time);
  await page.locator('#location').fill(CHENGDU.city);
  await page.locator('.location-suggestion').click();
  await page.locator('#create-chart-btn').click();
}

export const dialogIsOpen = (page) => page.evaluate(() => document.getElementById('account-dialog').open);
export async function dialogOpens(page) {
  await page.waitForFunction(() => document.getElementById('account-dialog').open);
}
export async function dialogCloses(page) {
  await page.waitForFunction(() => !document.getElementById('account-dialog').open);
}
export const text = (page, selector) => page.locator(selector).textContent();

// In the open dialog: the address (and a new account's language), then the code.
export async function sendCode(page, email, language = null) {
  await page.locator('#account-email').fill(email);
  if (language) await page.locator(`#account-language input[value="${language}"]`).check();
  await turnstileAnswered(page);
  await page.locator('#account-send').click();
  await page.locator('#account-code-step').waitFor({ state: 'visible' });
}
export async function enterCode(page, email) {
  await page.locator('#account-code').fill(await readCode(email));
  await page.locator('#account-verify').click();
}
// An existing account, from the dialog's sign-in side.
export async function signInThroughDialog(page, email) {
  if (await page.locator('#account-language').isVisible()) await page.locator('#account-mode').click();
  await sendCode(page, email);
  await enterCode(page, email);
  await dialogCloses(page);
}
