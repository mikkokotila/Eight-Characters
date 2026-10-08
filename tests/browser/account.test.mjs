// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Accounts: charts need one, the start page does not. A new account is made, or an
// account signed in, with a code sent by email; signed in, the dialog is the account
// itself. Codes are read from the app's mail folder (account-helpers.mjs); Cloudflare's
// widget is stubbed. Sessions that end, late answers and other tabs are in
// account-sessions.test.mjs.
import { readFile } from 'node:fs/promises';
import {
  assert, describe, it, engineName, profiles, settled, withPage, playwright, CHENGDU,
} from './chart-helpers.mjs';
import { newAddress, readMail, newAccount, asAccount, signInPage, turnstileAnswered } from './account-helpers.mjs';
import {
  BIRTH, link, visit, chartsAskedFor, askForChart, dialogIsOpen, dialogOpens, dialogCloses, text, sendCode, enterCode,
  signInThroughDialog,
} from './account-page.mjs';

const baseURL = process.env.EC_BASE_URL;
const EXPLORER = '/explorer/?date=1988-02-04&time=16:30&latitude=30.658&longitude=104.066&timezone=Asia%2FShanghai';
const statusOf = (account) => asAccount(playwright, account, async (request) => (await request.get('/api/account')).status());

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / account`, { concurrency: false }, () => {
    // Every page here starts without the suite's session; each test signs in as it says.
    const check = (name, run) => it(name, { timeout: 90000 }, () => withPage(profile, run, { signedIn: false }));

    check('the start page needs no account, and a chart asks for one before anything is sent', async (page) => {
      const failed = [];
      const foreign = [];
      page.on('response', (response) => { if (response.status() >= 400) failed.push(`${response.status()} ${response.url()}`); });
      page.on('request', (request) => {
        if (new URL(request.url()).origin !== new URL(baseURL).origin) foreign.push(request.url());
      });
      const asked = chartsAskedFor(page);
      await visit(page);
      assert.equal(await text(page, '#account-btn'), 'Sign in');
      await page.locator('#location').fill(CHENGDU.city);
      await page.locator('.location-suggestion').waitFor();
      // Nothing failed, and nothing came from another site, before the dialog opened.
      assert.deepEqual(failed, []);
      assert.deepEqual(foreign, []);
      await page.locator('#location').fill('');
      await askForChart(page);
      await dialogOpens(page);
      assert.equal(await text(page, '#account-title'), 'Create a free account');
      assert.equal(await text(page, '#account-lead'),
        'Charts need an account. It is free and needs no password: we send a code to your email.');
      assert.equal(await page.evaluate(() => document.activeElement.id), 'account-email');
      // No language is chosen for the reader.
      assert.equal(await page.locator('#account-language input:checked').count(), 0);
      // The widget has the page's site key, and speaks the page's language.
      await turnstileAnswered(page);
      assert.deepEqual(await page.evaluate(() => [window.__turnstile.sitekey, window.__turnstile.language]),
        [await page.locator('#account-dialog').getAttribute('data-site-key'), 'en']);
      assert.deepEqual(asked, []);
    });

    check('a new account needs its language, which the page and the chart then take', async (page) => {
      const asked = chartsAskedFor(page);
      const codes = [];
      page.on('request', (request) => {
        if (new URL(request.url()).pathname === '/api/account/code') codes.push(request.postDataJSON());
      });
      await visit(page, { lang: 'en' });
      await askForChart(page);
      await dialogOpens(page);
      const email = newAddress('new');
      await page.locator('#account-email').fill(email);
      await turnstileAnswered(page);
      await page.locator('#account-send').click();
      assert.equal(await text(page, '#account-language-status'), "Choose the account's language.");
      assert.deepEqual(codes, []);
      await page.locator('#account-language input[value="fi"]').check();
      await page.locator('#account-send').click();
      await page.locator('#account-code-step').waitFor({ state: 'visible' });
      assert.deepEqual(codes, [{
        email, purpose: 'create', language: 'fi', page_language: 'en', turnstile: 'XXXX.DUMMY.TOKEN.XXXX',
      }]);
      assert.equal(await text(page, '#account-title'), 'Check your email');
      assert.equal(await text(page, '#account-sent'), `We sent a code to ${email}. It works once, for 10 minutes.`);
      // Each answer of the check is used once.
      assert.equal(await page.evaluate(() => window.__turnstile.resets), 1);
      // The email speaks the account's language.
      const mail = await readMail(email);
      assert.match(mail.subject, /^Koodi tilisi luomiseen: \d{3} \d{3}$/);
      // A wrong code is said, and the dialog stays at the code.
      await page.locator('#account-code').fill(String((Number(mail.code) + 1) % 1000000).padStart(6, '0'));
      await page.locator('#account-verify').click();
      await page.locator('#account-code-status.is-error').waitFor();
      assert.equal(await text(page, '#account-code-status'), 'That code is wrong or no longer works.');
      // The right one, as the email writes it.
      await page.locator('#account-code').fill(`${mail.code.slice(0, 3)} ${mail.code.slice(3)}`);
      await page.locator('#account-verify').click();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      assert.equal(await dialogIsOpen(page), false);
      // The account's language is the page's now, and the chart was asked for in it, once.
      assert.equal(await page.evaluate(() => document.documentElement.lang), 'fi');
      assert.deepEqual(asked.map((body) => body.lang), ['fi']);
      assert.equal(new URLSearchParams(new URL(page.url()).hash.split('?')[1]).get('lang'), 'fi');
      assert.equal(await text(page, '#account-btn'), 'Tili');
    });

    check('an account signs in in its own language, without choosing one', async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'returning' });
      await visit(page, { lang: 'fi' });
      assert.equal(await text(page, '#account-btn'), 'Kirjaudu');
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      assert.equal(await text(page, '#account-title'), 'Luo maksuton tili');
      await page.locator('#account-mode').click();
      assert.equal(await text(page, '#account-title'), 'Kirjaudu sisään');
      assert.equal(await page.locator('#account-language').isVisible(), false);
      assert.equal(await text(page, '#account-mode'), 'Ei vielä tiliä? Luo maksuton tili');
      // The address in another case is the same account's.
      const typed = account.email.toUpperCase();
      await sendCode(page, typed);
      assert.equal(await text(page, '#account-sent'),
        `Jos osoitteella ${typed} on tili, lähetimme sille koodin. Se toimii kerran, 10 minuutin ajan.`);
      assert.match((await readMail(account.email)).subject, /^Your sign-in code: \d{3} \d{3}$/);
      await enterCode(page, account.email);
      await dialogCloses(page);
      assert.equal(await page.evaluate(() => document.documentElement.lang), 'en');
      assert.equal(await text(page, '#account-btn'), 'Account');
    });

    check('closing the dialog asks for no chart, and the form says why', async (page) => {
      const asked = chartsAskedFor(page);
      await visit(page);
      await askForChart(page);
      await dialogOpens(page);
      await page.keyboard.press('Escape');
      await page.locator('#form-error').waitFor({ state: 'visible' });
      assert.equal(await text(page, '#form-error'), 'Sign in to see charts.');
      assert.deepEqual(asked, []);
      assert.equal(await text(page, '#create-chart-btn'), 'Create chart');
      // The birth stays, to try again.
      assert.equal(await page.locator('#date').inputValue(), BIRTH.date);
      await page.locator('#create-chart-btn').click();
      await dialogOpens(page);
    });

    check('a check that does not load is said, tried again, and no code is asked for', async (page) => {
      const codes = [];
      page.on('request', (request) => {
        if (new URL(request.url()).pathname === '/api/account/code') codes.push(request.url());
      });
      const unloaded = 'The check that you are a person did not load. '
        + 'Check the connection, or allow challenges.cloudflare.com, and open this again.';
      await visit(page, { turnstile: false });
      await page.locator('#account-btn').click();
      await page.locator('#account-start-error').waitFor({ state: 'visible' });
      assert.equal(await text(page, '#account-start-error'), unloaded);
      await page.locator('#account-email').fill(newAddress());
      await page.locator('#account-language input[value="en"]').check();
      await page.locator('#account-send').click();
      await page.waitForFunction(() => document.querySelectorAll('script[src*="challenges.cloudflare.com"]').length === 2);
      assert.equal(await text(page, '#account-start-error'), unloaded);
      assert.deepEqual(codes, []);
    });

    check('the account sets its language, gives its data, and signs out', async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'menu' });
      await signInPage(page, account);
      await visit(page, { lang: 'en' });
      assert.equal(await text(page, '#account-btn'), 'Account');
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      assert.equal(await text(page, '#account-title'), 'Account');
      assert.equal(await text(page, '#account-who'), `Signed in as ${account.email}`);
      assert.equal(await text(page, '#account-plan'), 'Plan: Free');
      assert.equal(await page.locator('[data-account-lang="en"]').getAttribute('aria-pressed'), 'true');
      // The account's language: the page takes it, and so do the account's emails.
      await page.locator('[data-account-lang="fi"]').click();
      await page.locator('#account-status').filter({ hasText: 'Tallennettu.' }).waitFor();
      assert.equal(await page.evaluate(() => document.documentElement.lang), 'fi');
      assert.equal(await page.locator('[data-account-lang="fi"]').getAttribute('aria-pressed'), 'true');
      const stored = await asAccount(playwright, account, async (request) => (await request.get('/api/account')).json());
      assert.equal(stored.language, 'fi');
      // Everything kept for the account, as a file.
      const [download] = await Promise.all([page.waitForEvent('download'), page.locator('#account-export').click()]);
      assert.equal(download.suggestedFilename(), 'bazi-account.json');
      const exported = JSON.parse(await readFile(await download.path(), 'utf8'));
      assert.deepEqual([exported.account.email, exported.account.language], [account.email, 'fi']);
      await page.locator('#account-status').filter({ hasText: 'bazi-account.json' }).waitFor();
      // Signing out: the dialog says so and offers signing in again; the session is gone.
      await page.locator('#account-sign-out').click();
      await page.locator('#account-notice').filter({ hasText: 'Olet kirjautunut ulos.' }).waitFor();
      assert.equal(await text(page, '#account-title'), 'Kirjaudu sisään');
      assert.equal(await text(page, '#account-btn'), 'Kirjaudu');
      assert.equal(await statusOf(account), 401);
      await page.locator('#account-dialog [data-close-dialog]').click();
      await dialogCloses(page);
      await askForChart(page);
      await dialogOpens(page);
    });

    check('signing out leaves nothing of the chart on screen', async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'out' });
      await signInPage(page, account);
      await visit(page, { lang: 'en' });
      await askForChart(page);
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await page.keyboard.press('ControlOrMeta+k');
      await page.locator('#palette-input').fill('account');
      await page.keyboard.press('Enter');
      await dialogOpens(page);
      await page.locator('#account-sign-out-everywhere').click();
      await page.locator('#account-notice').filter({ hasText: 'You are signed out on every device.' }).waitFor();
      assert.equal(await page.locator('#chart-view').isVisible(), false);
      assert.equal(await page.locator('#date').inputValue(), '');
      assert.equal(new URL(page.url()).hash, '');
      assert.equal(await statusOf(account), 401);
    });

    check('deleting the account needs its address typed again', async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'delete' });
      await signInPage(page, account);
      await visit(page, { lang: 'en' });
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      assert.equal(await page.locator('#account-delete').isVisible(), false);
      await page.locator('#account-delete-open').click();
      assert.equal(await page.locator('#account-delete-open').getAttribute('aria-expanded'), 'true');
      await page.locator('#account-delete-email').fill('someone-else@example.com');
      await page.locator('#account-delete-confirm').click();
      await page.locator('#account-delete-status.is-error').waitFor();
      assert.equal(await text(page, '#account-delete-status'), "That is not the account's address.");
      assert.equal(await statusOf(account), 200);
      await page.locator('#account-delete-email').fill(account.email.toUpperCase());
      await page.locator('#account-delete-confirm').click();
      await page.locator('#account-notice').filter({ hasText: 'The account is deleted.' }).waitFor();
      assert.equal(await text(page, '#account-btn'), 'Sign in');
      assert.equal(await statusOf(account), 401);
    });

    check('a chart link opened without an account asks for one, then shows its chart', async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'link' });
      await visit(page, { lang: 'en', address: `#chart?${link(BIRTH.date, BIRTH.time, 'en')}&topic=season` });
      await dialogOpens(page);
      await signInThroughDialog(page, account.email);
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      assert.match(await text(page, '#chart-date'), /^February 4, 1988 · 16:30 · Chengdu$/);
      assert.equal(new URLSearchParams(new URL(page.url()).hash.split('?')[1]).get('topic'), 'season');
    });

    check('a comparison opened without an account asks once, before its frames do', async (page) => {
      const account = await newAccount(playwright, { language: 'fi', label: 'compare' });
      const pair = new URLSearchParams({
        a: link(BIRTH.date, BIRTH.time, 'en').toString(), b: link('1990-05-09', '12:00', 'en').toString(),
      });
      await visit(page, { lang: 'en', address: `#compare?${pair}` });
      await dialogOpens(page);
      assert.equal(await page.locator('#compare-charts iframe').count(), 0);
      await signInThroughDialog(page, account.email);
      await page.locator('#compare-view').waitFor({ state: 'visible' });
      // Both charts in the account's language, which the page took.
      for (const side of ['a', 'b']) {
        const frame = page.frameLocator(`#compare-charts .compare-frame[data-side="${side}"]`);
        await frame.locator('#chart-view:not(.hidden) #pillars .card').first().waitFor({ state: 'attached' });
        assert.equal(await frame.locator('html').getAttribute('lang'), 'fi');
      }
      const address = new URLSearchParams(new URL(page.url()).hash.slice('#compare?'.length));
      assert.deepEqual(['a', 'b'].map((side) => new URLSearchParams(address.get(side)).get('lang')), ['fi', 'fi']);
    });

    check('a code asked for is said as asked, even if the dialog changes side meanwhile', async (page) => {
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      await page.route('**/api/account/code', async (route) => {
        await held;
        await route.continue();
      });
      await visit(page, { lang: 'en' });
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      await page.locator('#account-mode').click();
      const email = newAddress('side');
      await page.locator('#account-email').fill(email);
      await turnstileAnswered(page);
      await page.locator('#account-send').click();
      await page.locator('#account-send.is-pending').waitFor();
      // To creating an account, while the sign-in request is on its way.
      await page.locator('#account-mode').click();
      release();
      await page.locator('#account-code-step').waitFor({ state: 'visible' });
      assert.equal(await text(page, '#account-sent'),
        `If ${email} has an account, we sent it a code. It works once, for 10 minutes.`);
    });

    check('the explorer sends a visitor to the start page to sign in', async (page) => {
      await page.goto(new URL(EXPLORER, baseURL).href);
      const status = page.locator('#statusBar');
      await status.locator('a').waitFor();
      assert.equal(await status.textContent(), 'Sign in on the start page to see this chart in the explorer.');
      assert.equal(await status.locator('a').getAttribute('href'), '/');
    });

    check('the dialog fits the screen, and scrolls inside itself', async (page) => {
      await visit(page, { lang: 'fi' });
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      const viewport = page.viewportSize();
      const box = await page.locator('#account-dialog').boundingBox();
      assert.ok(box.x >= 0 && box.x + box.width <= viewport.width, `${JSON.stringify(box)} in ${JSON.stringify(viewport)}`);
      assert.ok(box.y >= 0 && box.y + box.height <= viewport.height, `${JSON.stringify(box)} in ${JSON.stringify(viewport)}`);
      assert.equal(await page.locator('#account-dialog').evaluate((dialog) => dialog.scrollWidth <= dialog.clientWidth), true);
      await page.locator('#account-start .account-note').last().scrollIntoViewIfNeeded();
      assert.equal(await page.locator('#account-start .account-note').last().isVisible(), true);
    });
  });
}
