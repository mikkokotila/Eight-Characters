// UI protocol fixtures only. Native six-offer/payment acceptance is separate.
import {
  assert, describe, it, engineName, profiles, withPage, settled,
} from './chart-helpers.mjs';
import { visit } from './account-page.mjs';

const baseURL = process.env.EC_BASE_URL;
const BASE = new URL(baseURL).origin;
const billing = (key, changes = {}) => ({
  key, tier: 'free', status: 'free', paid_through: null, reason: null, ...changes,
});

async function prepare(page, { enabled = true, state = {} } = {}) {
  const account = await (await page.request.get(new URL('/api/account', baseURL).href)).json();
  if (enabled) {
    await page.route((url) => url.origin === BASE && url.pathname === '/', async (route) => {
      const response = await route.fetch();
      const body = (await response.text()).replace('data-billing-enabled="false"', 'data-billing-enabled="true"');
      await route.fulfill({ response, body });
    });
  }
  await page.route('**/api/account/billing', (route) => route.fulfill({ json: billing(account.key, state) }));
  await visit(page);
  await page.locator('#account-btn').click();
  await page.waitForFunction(() => !document.getElementById('account-export').disabled);
  return account;
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / sandbox Plan controls`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 90000 }, () => withPage(profile, run));

    check('disabled billing exposes no controls or requests', async (page) => {
      const requests = [];
      page.on('request', (request) => { if (request.url().includes('/api/account/billing')) requests.push(request.url()); });
      await prepare(page, { enabled: false });
      assert.equal(await page.locator('#account-billing-open').isVisible(), false);
      assert.equal(await page.locator('#account-billing').isVisible(), false);
      assert.deepEqual(requests, []);
    });

    check('all six offers keep their account and open only hosted test checkout', async (page) => {
      const requests = [];
      const destination = 'https://checkout.stripe.com/c/pay/cs_test_ui_fixture';
      await page.route('https://checkout.stripe.com/**', (route) => route.fulfill({ contentType: 'text/html', body: '<p>Hosted test checkout fixture</p>' }));
      await page.route('**/api/account/billing/checkout', (route) => {
        requests.push(route.request().postDataJSON());
        return route.fulfill({ json: { status: 'open', checkout_url: destination } });
      });
      for (const period of ['yearly', 'monthly']) {
        for (const plan of ['basic', 'plus', 'pro']) {
          const account = await prepare(page);
          await page.locator('#account-billing-open').click();
          await page.locator('#account-billing-offers').waitFor({ state: 'visible' });
          assert.match(await page.locator('#account-billing').textContent(), /Private sandbox: no real charges/);
          await page.locator('#account-billing-period').selectOption(period);
          const button = page.locator(`[data-billing-plan="${plan}"]`);
          assert.match(await button.textContent(), /USD/);
          await button.click();
          await page.waitForURL(destination);
          assert.deepEqual(requests.at(-1), { key: account.key, plan, period });
        }
      }
      assert.equal(requests.length, 6);
    });

    check('paid cancellation has no second purchase or false success on failure', async (page) => {
      const account = await prepare(page, { state: { tier: 'plus', status: 'paid', paid_through: 1792926000 } });
      let calls = 0;
      let fail = true;
      await page.route('**/api/account/billing/cancel', async (route) => {
        calls += 1;
        assert.deepEqual(route.request().postDataJSON(), { key: account.key });
        await route.fulfill(fail ? { status: 503, json: { detail: 'Unverified' } }
          : { json: billing(account.key, { tier: 'plus', status: 'paid', paid_through: 1792926000 }) });
      });
      await page.locator('#account-billing-open').click();
      await page.locator('#account-billing-cancel').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#account-billing-offers').isVisible(), false);
      await page.locator('#account-billing-cancel').click();
      await page.waitForFunction(() => document.getElementById('account-status').textContent.includes('503'));
      assert.equal(await page.locator('#account-billing-result').textContent(), '');
      fail = false;
      await page.locator('#account-billing-cancel').click();
      await page.waitForFunction(() => document.getElementById('account-billing-result').textContent.includes('Renewal is stopped'));
      assert.equal(calls, 2);
      await page.locator('[data-account-lang="fi"]').click();
      await page.waitForFunction(() => document.getElementById('account-billing-open').textContent === 'Tilaus');
      assert.match(await page.locator('#account-billing-summary').textContent(), /Plus · maksettu/);
      await page.locator('[data-account-lang="en"]').click();
      await page.waitForFunction(() => document.getElementById('account-billing-open').textContent === 'Plan');
      await settled(page);
    });

    check('held, foreign-account and malformed replies never enable purchases', async (page) => {
      await prepare(page, { state: { status: 'held', reason: 'native_unavailable' } });
      await page.locator('#account-billing-open').click();
      await page.waitForFunction(() => document.getElementById('account-billing-summary').textContent.includes('verification held'));
      assert.equal(await page.locator('#account-billing-offers').isVisible(), false);
      await page.route('**/api/account/billing', (route) => route.fulfill({ json: billing('a'.repeat(64), { tier: 'pro', status: 'paid' }) }));
      await page.locator('#account-billing-open').click();
      await page.waitForFunction(() => document.getElementById('account-status').textContent.includes('account changed'));
      assert.equal(await page.locator('#account-billing-summary').textContent(), '');
      assert.equal(await page.locator('#account-billing-offers').isVisible(), false);
    });

    check('closing a pending checkout discards its late redirect and duplicate clicks', async (page) => {
      let release;
      const gate = new Promise((resolve) => { release = resolve; });
      let calls = 0;
      await prepare(page);
      await page.route('**/api/account/billing/checkout', async (route) => {
        calls += 1;
        await gate;
        await route.fulfill({ json: { status: 'open', checkout_url: 'https://checkout.stripe.com/c/pay/cs_test_late' } });
      });
      await page.locator('#account-billing-open').click();
      await page.locator('#account-billing-offers').waitFor({ state: 'visible' });
      await page.locator('[data-billing-plan="plus"]').dblclick();
      await page.waitForFunction(() => document.querySelector('[data-billing-plan="plus"]').disabled);
      await page.locator('#account-dialog [data-close-dialog]').click();
      release();
      await page.waitForFunction(() => !document.querySelector('[data-billing-plan="plus"]').disabled);
      assert.equal(calls, 1);
      assert.equal(new URL(page.url()).origin, BASE);
      await page.locator('#account-btn').click();
      assert.equal(await page.locator('#account-billing').isVisible(), false);
    });

    check('an untrusted checkout destination stays a visible failure', async (page) => {
      await prepare(page);
      await page.route('**/api/account/billing/checkout', (route) => route.fulfill({ json: { status: 'open', checkout_url: 'https://example.invalid/pay' } }));
      await page.locator('#account-billing-open').click();
      await page.locator('#account-billing-offers').waitFor({ state: 'visible' });
      await page.locator('[data-billing-plan="basic"]').click();
      await page.waitForFunction(() => document.getElementById('account-status').textContent.includes('could not be verified'));
      assert.equal(new URL(page.url()).origin, BASE);
    });
  });
}
