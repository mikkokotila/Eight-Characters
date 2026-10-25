// Explicit opt-in contract: real HTTP/SQLite and UI, injected Stripe transport.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { once } from 'node:events';

assert.ok(process.env.EC_PYTHON, 'Set EC_PYTHON to the product Python executable.');
assert.ok(process.env.EC_PLAYWRIGHT_MODULE, 'Set EC_PLAYWRIGHT_MODULE.');
assert.ok(['chromium', 'webkit'].includes(process.env.EC_BROWSER), 'Set EC_BROWSER.');
const playwright = await import(process.env.EC_PLAYWRIGHT_MODULE);
const engine = process.env.EC_BROWSER;

for (const [name, width, height] of [['desktop', 1280, 1000], ['mobile-320', 320, 844]]) {
  test(`${engine} / ${name} / real sandbox route contract`, { timeout: 180000 }, async () => {
    const child = spawn(process.env.EC_PYTHON, ['-m', 'tests.browser.billing_contract_server'], { stdio: ['ignore', 'pipe', 'pipe'] });
    let diagnostics = '';
    child.stderr.on('data', (data) => { diagnostics += data.toString(); });
    let browser;
    try {
      const metadata = await new Promise((resolve, reject) => {
        const lines = createInterface({ input: child.stdout });
        const timeout = setTimeout(() => reject(new Error(`Fixture startup timed out: ${diagnostics}`)), 20000);
        child.once('exit', (code) => { clearTimeout(timeout); reject(new Error(`Fixture exited ${code}: ${diagnostics}`)); });
        lines.once('line', (line) => { clearTimeout(timeout); resolve(JSON.parse(line)); });
      });
      process.env.EC_BASE_URL = metadata.origin;
      process.env.EC_MAIL_DIRECTORY = metadata.mail;
      const helpers = await import(`./account-helpers.mjs?contract=${engine}-${name}`);
      const account = await helpers.newAccount(playwright);
      browser = await playwright[engine].launch({ headless: true });
      const context = await browser.newContext({ viewport: { width, height } });
      const page = await context.newPage();
      await helpers.signInPage(page, account);
      await page.addInitScript(() => localStorage.setItem('eight_characters_lang', 'en'));
      await page.route('https://checkout.stripe.com/**', (route) => route.fulfill({ contentType: 'text/html', body: '<p>Injected hosted test checkout</p>' }));
      await page.goto(metadata.origin);
      assert.equal(await page.locator('#account-dialog').getAttribute('data-billing-enabled'), 'true');
      await page.locator('#account-btn').click();
      await page.locator('#account-billing-open').click();
      await page.locator('#account-billing-offers').waitFor({ state: 'visible' });
      await page.locator('#account-billing-period').selectOption('monthly');
      await page.locator('[data-billing-plan="plus"]').click();
      await page.waitForURL('https://checkout.stripe.com/**');
      await page.goto(metadata.origin + '/account/billing/return');
      await page.locator('#account-billing-resume').waitFor({ state: 'visible' });
      assert.match(await page.locator('#account-billing-summary').textContent(), /payment pending/);
      assert.equal(await page.locator('#account-billing-cancel').isVisible(), false);
      await page.locator('#account-billing-resume').click();
      await page.waitForURL('https://checkout.stripe.com/**');
      const state = await (await page.request.get(metadata.origin + '/__test/billing/state')).json();
      assert.equal(state.sessions, 1, 'Resume must reuse the original session.');
      assert.equal((await page.request.post(metadata.origin + '/__test/billing/complete')).status(), 200);
      await page.goto(metadata.origin + '/account/billing/return');
      await page.locator('#account-billing-cancel').waitFor({ state: 'visible' });
      assert.match(await page.locator('#account-billing-summary').textContent(), /Plus · paid/);
      assert.equal((await page.request.post(metadata.origin + '/__test/billing/overdue')).status(), 200);
      await page.locator('#account-billing-open').click();
      await page.waitForFunction(() => document.getElementById('account-billing-summary').textContent.includes('paid time expired'));
      assert.equal(await page.locator('#account-billing-offers').isVisible(), false);
      assert.equal(await page.locator('#account-billing-cancel').isVisible(), true);
      await page.locator('#account-billing-cancel').click();
      await page.waitForFunction(() => document.getElementById('account-billing-renewal').textContent.includes('Renewal is stopped'));
      await page.reload();
      await page.waitForFunction(() => document.getElementById('account-billing-renewal').textContent.includes('Renewal is stopped'));
      assert.equal(await page.locator('#account-billing-cancel').isVisible(), false);
      const stopped = await (await page.request.get(metadata.origin + '/__test/billing/state')).json();
      assert.deepEqual(stopped, { sessions: 1, subscriptions: 1, stopped: 1 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    } finally {
      if (browser) await browser.close();
      if (child.exitCode === null && child.signalCode === null) {
        const exited = once(child, 'exit');
        child.kill('SIGTERM');
        await exited;
      }
    }
  });
}
