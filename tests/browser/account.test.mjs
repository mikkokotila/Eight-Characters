// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Accounts: charts need one, the start page does not. A new account is made, or an
// account signed in, with a code sent by email; signed in, the dialog is the account
// itself. A session that ends meanwhile asks for a sign-in once more. Codes are read
// from the app's mail folder (account-helpers.mjs); Cloudflare's widget is stubbed.
import { readFile } from 'node:fs/promises';
import {
  assert, describe, it, engineName, profiles, settled, withPage, playwright, CHENGDU,
} from './chart-helpers.mjs';
import {
  newAddress, readMail, readCode, newAccount, asAccount, signInPage, stubTurnstile, turnstileAnswered,
} from './account-helpers.mjs';

const baseURL = process.env.EC_BASE_URL;
const BIRTH = { date: '1988-02-04', time: '16:30' };
// The canonical chart's link, and a second birth's, as the app writes them.
const link = (date, time, lang) => new URLSearchParams({
  date, time, place: CHENGDU.display, city: CHENGDU.city, latitude: String(CHENGDU.latitude),
  longitude: String(CHENGDU.longitude), timezone: CHENGDU.timezone, lang,
});
const EXPLORER = '/explorer/?date=1988-02-04&time=16:30&latitude=30.658&longitude=104.066&timezone=Asia%2FShanghai';

// The start page as a visitor finds it, in a language; or a link's address. Only the
// place search and Cloudflare's widget are stubbed.
async function visit(page, { lang = 'en', address = '', turnstile = true } = {}) {
  await stubTurnstile(page, { load: turnstile });
  await page.route('**/api/location_suggest', (route) => route.fulfill({ json: { suggestions: [CHENGDU] } }));
  // A first visit has no language of its own: the browser's decides it.
  await page.addInitScript((lang) => {
    if (!localStorage.getItem('eight_characters_lang')) localStorage.setItem('eight_characters_lang', lang);
  }, lang);
  await page.goto(new URL(`/${address}`, baseURL).href);
}

// Every chart the page asks for, as it asks.
function chartsAskedFor(page) {
  const asked = [];
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/api/four_pillars') asked.push(request.postDataJSON());
  });
  return asked;
}

async function askForChart(page) {
  await page.locator('#date').fill(BIRTH.date);
  await page.locator('#time').fill(BIRTH.time);
  await page.locator('#location').fill(CHENGDU.city);
  await page.locator('.location-suggestion').click();
  await page.locator('#create-chart-btn').click();
}

const dialogIsOpen = (page) => page.evaluate(() => document.getElementById('account-dialog').open);
async function dialogOpens(page) {
  await page.waitForFunction(() => document.getElementById('account-dialog').open);
}
async function dialogCloses(page) {
  await page.waitForFunction(() => !document.getElementById('account-dialog').open);
}
const text = (page, selector) => page.locator(selector).textContent();

// In the open dialog: the address (and a new account's language), then the code.
async function sendCode(page, email, language = null) {
  await page.locator('#account-email').fill(email);
  if (language) await page.locator(`#account-language input[value="${language}"]`).check();
  await turnstileAnswered(page);
  await page.locator('#account-send').click();
  await page.locator('#account-code-step').waitFor({ state: 'visible' });
}
async function enterCode(page, email) {
  await page.locator('#account-code').fill(await readCode(email));
  await page.locator('#account-verify').click();
}
// An existing account, from the dialog's sign-in side.
async function signInThroughDialog(page, email) {
  if (await page.locator('#account-language').isVisible()) await page.locator('#account-mode').click();
  await sendCode(page, email);
  await enterCode(page, email);
  await dialogCloses(page);
}
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

    check('a session that ended asks for a sign-in once, and the chart is drawn again', async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'ended' });
      await signInPage(page, account);
      const asked = chartsAskedFor(page);
      await visit(page, { lang: 'en' });
      await askForChart(page);
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      // Signed out on every device, from another one.
      await asAccount(playwright, account, async (request) => {
        assert.equal((await request.delete('/api/account/sessions')).status(), 204);
      });
      await page.locator('#chart-language button[data-chart-lang="fi"]').click();
      await dialogOpens(page);
      assert.equal(await text(page, '#account-notice'), 'Istuntosi päättyi. Kirjaudu uudelleen.');
      assert.equal(await text(page, '#account-title'), 'Kirjaudu sisään');
      await signInThroughDialog(page, account.email);
      await page.waitForFunction(() => !document.getElementById('chart-view').hasAttribute('aria-busy'));
      await settled(page);
      // Asked again once, in the account's language, which the page took when signing in.
      assert.deepEqual(asked.map((body) => body.lang), ['en', 'fi', 'en']);
      assert.equal(await page.evaluate(() => document.documentElement.lang), 'en');
      assert.equal(await page.locator('#chart-view').isVisible(), true);
    });

    check('a chart refused after a newer one signed in leaves that sign-in alone', async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'late' });
      await signInPage(page, account);
      await visit(page, { lang: 'en', address: `#chart?${link(BIRTH.date, BIRTH.time, 'en')}` });
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      // A second chart, after the first in the history.
      await page.locator('#new-chart-btn').click();
      await page.locator('#date').fill(BIRTH.date);
      await page.locator('#time').fill('12:00');
      await page.locator('#location').fill(CHENGDU.city);
      await page.locator('.location-suggestion').click();
      await page.locator('#create-chart-btn').click();
      await page.waitForFunction(() => document.getElementById('chart-date').textContent.includes('12:00'));
      await settled(page);
      // The next chart asked for is held on its way. Its answer comes last: the
      // server's refusal for this session, which ends meanwhile. (Continuing the held
      // request instead would send the cookie the browser holds by then.)
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      let sent;
      const asked = new Promise((resolve) => { sent = resolve; });
      let holding = true;
      await page.route('**/api/four_pillars', async (route) => {
        if (!holding) return route.continue();
        holding = false;
        sent();
        await held;
        return route.fulfill({ status: 401, json: { detail: 'Sign in to continue.' } });
      });
      await page.locator('#chart-language button[data-chart-lang="fi"]').click();
      await asked;
      // Signed out on every device, from another one; then back past the form to the
      // first chart, which is refused, asks for a sign-in, and is drawn.
      await asAccount(playwright, account, async (request) => {
        assert.equal((await request.delete('/api/account/sessions')).status(), 204);
      });
      await page.goBack();
      await page.goBack();
      await dialogOpens(page);
      await signInThroughDialog(page, account.email);
      await page.waitForFunction(() => document.getElementById('chart-date').textContent.includes('16:30'));
      await settled(page);
      // The held chart's refusal arrives.
      const late = page.waitForResponse((response) =>
        new URL(response.url()).pathname === '/api/four_pillars' && response.status() === 401);
      release();
      await late;
      // Time for the page to act on it, as it would have, by opening the dialog.
      await page.waitForTimeout(500);
      assert.equal(await dialogIsOpen(page), false);
      assert.equal(await text(page, '#account-btn'), 'Account');
      assert.match(await text(page, '#chart-date'), /^February 4, 1988 · 16:30 · Chengdu$/);
      assert.equal(await page.locator('#chart-view').isVisible(), true);
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

    check('a comparison started after the session ended asks for a sign-in before its frames', async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'pair' });
      await signInPage(page, account);
      await visit(page, { lang: 'en' });
      await askForChart(page);
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      await page.locator('#compare-btn').click();
      await page.locator('#compare-note').waitFor({ state: 'visible' });
      // Signed out on every device, from another one, while the second birth is typed.
      await asAccount(playwright, account, async (request) => {
        assert.equal((await request.delete('/api/account/sessions')).status(), 204);
      });
      await page.locator('#date').fill('1990-05-09');
      await page.locator('#time').fill('12:00');
      await page.locator('#location').fill(CHENGDU.city);
      await page.locator('.location-suggestion').click();
      await page.locator('#create-chart-btn').click();
      await dialogOpens(page);
      assert.equal(await page.locator('#compare-charts iframe').count(), 0);
      assert.equal(await text(page, '#account-notice'), 'Your session ended. Sign in again.');
      await signInThroughDialog(page, account.email);
      await page.locator('#compare-view').waitFor({ state: 'visible' });
      for (const side of ['a', 'b']) {
        const frame = page.frameLocator(`#compare-charts .compare-frame[data-side="${side}"]`);
        await frame.locator('#chart-view:not(.hidden) #pillars .card').first().waitFor({ state: 'attached' });
      }
    });

    check("a comparison's session check refused after a newer one signed in leaves that sign-in alone", async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'pairs' });
      await signInPage(page, account);
      await visit(page, { lang: 'en' });
      await askForChart(page);
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      // The first comparison's check of the session is held on its way. Its answer
      // comes last: the server's refusal for this session, which ends meanwhile.
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      let sent;
      const checking = new Promise((resolve) => { sent = resolve; });
      let holding = true;
      await page.route('**/api/account', async (route) => {
        if (!holding || route.request().method() !== 'GET') return route.continue();
        holding = false;
        sent();
        await held;
        return route.fulfill({ status: 401, json: { detail: 'Sign in to continue.' } });
      });
      const compareWith = async (date, time) => {
        await page.locator('#compare-note').waitFor({ state: 'visible' });
        await page.locator('#date').fill(date);
        await page.locator('#time').fill(time);
        await page.locator('#location').fill(CHENGDU.city);
        await page.locator('.location-suggestion').click();
        await page.locator('#create-chart-btn').click();
      };
      await page.locator('#compare-btn').click();
      await compareWith('1990-05-09', '12:00');
      await checking;
      // Signed out on every device, from another one; then back to the second birth, and
      // another one compared, which asks for a sign-in and shows its frames.
      await asAccount(playwright, account, async (request) => {
        assert.equal((await request.delete('/api/account/sessions')).status(), 204);
      });
      await page.goBack();
      await compareWith('1991-01-01', '08:00');
      await dialogOpens(page);
      await signInThroughDialog(page, account.email);
      await page.locator('#compare-view').waitFor({ state: 'visible' });
      // The held check's refusal arrives.
      const late = page.waitForResponse((response) =>
        new URL(response.url()).pathname === '/api/account' && response.status() === 401);
      release();
      await late;
      // Time for the page to act on it, as it would have, by opening the dialog.
      await page.waitForTimeout(500);
      assert.equal(await dialogIsOpen(page), false);
      assert.equal(await text(page, '#account-btn'), 'Account');
      assert.equal(await page.locator('#compare-view').isVisible(), true);
      const address = new URLSearchParams(new URL(page.url()).hash.slice('#compare?'.length));
      assert.equal(new URLSearchParams(address.get('b')).get('date'), '1991-01-01');
    });

    check("a comparison's late answer leaves the account signed in since", async (page) => {
      const earlier = await newAccount(playwright, { language: 'en', label: 'earlier' });
      const later = await newAccount(playwright, { language: 'en', label: 'later' });
      await signInPage(page, earlier);
      await visit(page, { lang: 'en' });
      await askForChart(page);
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      // The comparison's check of the session is answered at once, for the earlier
      // account, and the answer is held on its way.
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      let sent;
      const answered = new Promise((resolve) => { sent = resolve; });
      let holding = true;
      await page.route('**/api/account', async (route) => {
        if (!holding || route.request().method() !== 'GET') return route.continue();
        holding = false;
        const response = await route.fetch();
        sent();
        await held;
        return route.fulfill({ response });
      });
      await page.locator('#compare-btn').click();
      await page.locator('#compare-note').waitFor({ state: 'visible' });
      await page.locator('#date').fill('1990-05-09');
      await page.locator('#time').fill('12:00');
      await page.locator('#location').fill(CHENGDU.city);
      await page.locator('.location-suggestion').click();
      await page.locator('#create-chart-btn').click();
      await answered;
      // Signed out, and in as another account, while that answer is on its way.
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      await page.locator('#account-sign-out').click();
      await page.locator('#account-notice').filter({ hasText: 'You are signed out.' }).waitFor();
      await signInThroughDialog(page, later.email);
      release();
      // Time for the page to act on it, as it would have: the comparison abandoned by
      // signing out came back, and the menu named the earlier account.
      await page.waitForTimeout(500);
      assert.equal(await page.locator('#compare-view').isVisible(), false);
      assert.equal(new URL(page.url()).hash.startsWith('#compare'), false);
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      assert.equal(await text(page, '#account-who'), `Signed in as ${later.email}`);
    });

    check("a comparison's late answer leaves a language set since", async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'tongue' });
      await signInPage(page, account);
      await visit(page, { lang: 'en' });
      await askForChart(page);
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      // The comparison's check of the session is answered at once, while the account is
      // still in English, and the answer is held on its way.
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      let sent;
      const answered = new Promise((resolve) => { sent = resolve; });
      let holding = true;
      await page.route('**/api/account', async (route) => {
        if (!holding || route.request().method() !== 'GET') return route.continue();
        holding = false;
        const response = await route.fetch();
        sent();
        await held;
        return route.fulfill({ response });
      });
      await page.locator('#compare-btn').click();
      await page.locator('#compare-note').waitFor({ state: 'visible' });
      await page.locator('#date').fill('1990-05-09');
      await page.locator('#time').fill('12:00');
      await page.locator('#location').fill(CHENGDU.city);
      await page.locator('.location-suggestion').click();
      await page.locator('#create-chart-btn').click();
      await answered;
      // The account's language is set to Finnish meanwhile, in the dialog.
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      await page.locator('[data-account-lang="fi"]').click();
      await page.waitForFunction(() =>
        document.querySelector('[data-account-lang="fi"]').getAttribute('aria-pressed') === 'true');
      await page.locator('#account-dialog [data-close-dialog]').click();
      await dialogCloses(page);
      release();
      await page.locator('#compare-view').waitFor({ state: 'visible' });
      // Time for the page to act on the answer, as it would have, by naming English.
      await page.waitForTimeout(500);
      assert.equal(await page.locator('[data-account-lang="fi"]').getAttribute('aria-pressed'), 'true');
      assert.equal(await page.locator('[data-account-lang="en"]').getAttribute('aria-pressed'), 'false');
      const stored = await asAccount(playwright, account, async (request) => (await request.get('/api/account')).json());
      assert.equal(stored.language, 'fi');
    });

    // Another tab of the same browser signs out, and in to another account: the
    // session it signed out of ends, and the cookie the tabs share becomes the other
    // account's.
    const switchInAnotherTab = async (page, from, to) => {
      await asAccount(playwright, from, async (request) => {
        assert.equal((await request.delete('/api/account/session')).status(), 204);
      });
      await page.context().addCookies(to.cookies);
    };

    check('the menu names the account another tab signed in to, and exports its data', async (page) => {
      const earlier = await newAccount(playwright, { language: 'en', label: 'tab-a' });
      const later = await newAccount(playwright, { language: 'en', label: 'tab-b' });
      await signInPage(page, earlier);
      await visit(page, { lang: 'en' });
      await switchInAnotherTab(page, earlier, later);
      // The menu asks who the session belongs to before it acts for it.
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      await page.locator('#account-who').filter({ hasText: `Signed in as ${later.email}` }).waitFor();
      const [download] = await Promise.all([page.waitForEvent('download'), page.locator('#account-export').click()]);
      const exported = JSON.parse(await readFile(await download.path(), 'utf8'));
      assert.equal(exported.account.email, later.email);
    });

    check("a comparison's check takes the account another tab signed in to", async (page) => {
      const earlier = await newAccount(playwright, { language: 'en', label: 'pair-a' });
      const later = await newAccount(playwright, { language: 'fi', label: 'pair-b' });
      await signInPage(page, earlier);
      await visit(page, { lang: 'en' });
      await askForChart(page);
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      await switchInAnotherTab(page, earlier, later);
      await page.locator('#compare-btn').click();
      await page.locator('#compare-note').waitFor({ state: 'visible' });
      await page.locator('#date').fill('1990-05-09');
      await page.locator('#time').fill('12:00');
      await page.locator('#location').fill(CHENGDU.city);
      await page.locator('.location-suggestion').click();
      await page.locator('#create-chart-btn').click();
      // Taken as a sign-in here: the page speaks the account's language.
      await page.waitForFunction(() => document.documentElement.lang === 'fi');
    });

    check("a menu action's late refusal leaves an account taken meanwhile", async (page) => {
      const earlier = await newAccount(playwright, { language: 'en', label: 'act-a' });
      const later = await newAccount(playwright, { language: 'en', label: 'act-b' });
      await signInPage(page, earlier);
      await visit(page, { lang: 'en' });
      // Download my data is asked for, and its answer held on its way: the server's
      // refusal for the earlier session, which ends meanwhile.
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      let sent;
      const asked = new Promise((resolve) => { sent = resolve; });
      await page.route('**/api/account/export', async (route) => {
        sent();
        await held;
        return route.fulfill({ status: 401, json: { detail: 'Sign in to continue.' } });
      });
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      await page.locator('#account-who').filter({ hasText: `Signed in as ${earlier.email}` }).waitFor();
      await page.locator('#account-export').click();
      await asked;
      await page.locator('#account-dialog [data-close-dialog]').click();
      await dialogCloses(page);
      await askForChart(page);
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      // Another tab signs in to another account, which a comparison here takes.
      await switchInAnotherTab(page, earlier, later);
      await page.locator('#compare-btn').click();
      await page.locator('#compare-note').waitFor({ state: 'visible' });
      await page.locator('#date').fill('1990-05-09');
      await page.locator('#time').fill('12:00');
      await page.locator('#location').fill(CHENGDU.city);
      await page.locator('.location-suggestion').click();
      await page.locator('#create-chart-btn').click();
      await page.locator('#compare-view').waitFor({ state: 'visible' });
      release();
      // Time for the page to act on the refusal, as it would have, by signing out.
      await page.waitForTimeout(500);
      assert.equal(await text(page, '#account-btn'), 'Account');
      assert.equal(await text(page, '#account-who'), `Signed in as ${later.email}`);
      assert.equal(await text(page, '#account-status'), 'The account changed meanwhile: nothing was done.');
    });

    check('a menu reopened during an action asks who the session is once the action ends', async (page) => {
      const earlier = await newAccount(playwright, { language: 'en', label: 'busy-a' });
      const later = await newAccount(playwright, { language: 'en', label: 'busy-b' });
      await signInPage(page, earlier);
      await visit(page, { lang: 'en' });
      // Download my data is answered at once, for the earlier account, and the answer
      // held on its way.
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      let sent;
      const asked = new Promise((resolve) => { sent = resolve; });
      await page.route('**/api/account/export', async (route) => {
        const response = await route.fetch();
        sent();
        await held;
        return route.fulfill({ response });
      });
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      await page.locator('#account-who').filter({ hasText: `Signed in as ${earlier.email}` }).waitFor();
      const downloaded = page.waitForEvent('download');
      await page.locator('#account-export').click();
      await asked;
      // Another tab signs in to another account; the menu is closed and opened again
      // while the download is still on its way.
      await switchInAnotherTab(page, earlier, later);
      await page.locator('#account-dialog [data-close-dialog]').click();
      await dialogCloses(page);
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      release();
      await downloaded;
      await page.locator('#account-who').filter({ hasText: `Signed in as ${later.email}` }).waitFor();
    });

    check('the menu shows a language another tab set, and can set it back', async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'tongue-tab' });
      await signInPage(page, account);
      await visit(page, { lang: 'en' });
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      await page.locator('#account-who').filter({ hasText: `Signed in as ${account.email}` }).waitFor();
      await page.locator('#account-dialog [data-close-dialog]').click();
      await dialogCloses(page);
      // Another tab sets the account's language to Finnish.
      await asAccount(playwright, account, async (request) => {
        assert.equal((await request.patch('/api/account', { data: { language: 'fi' } })).status(), 200);
      });
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      await page.waitForFunction(() =>
        document.querySelector('[data-account-lang="fi"]').getAttribute('aria-pressed') === 'true');
      // And English can be set again from here.
      await page.locator('[data-account-lang="en"]').click();
      await page.waitForFunction(() =>
        document.querySelector('[data-account-lang="en"]').getAttribute('aria-pressed') === 'true');
      const stored = await asAccount(playwright, account, async (request) => (await request.get('/api/account')).json());
      assert.equal(stored.language, 'en');
    });

    check("a menu reopened during its own question asks again once that one is answered", async (page) => {
      const earlier = await newAccount(playwright, { language: 'en', label: 'ask-a' });
      const later = await newAccount(playwright, { language: 'en', label: 'ask-b' });
      await signInPage(page, earlier);
      await visit(page, { lang: 'en' });
      // The menu's first question of who the session is is answered at once, for the
      // earlier account, and the answer held on its way.
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      let sent;
      const asked = new Promise((resolve) => { sent = resolve; });
      let holding = true;
      await page.route('**/api/account', async (route) => {
        if (!holding || route.request().method() !== 'GET') return route.continue();
        holding = false;
        const response = await route.fetch();
        sent();
        await held;
        return route.fulfill({ response });
      });
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      await asked;
      // Another tab signs in to another account; the menu is closed and opened again
      // while that answer is still on its way.
      await switchInAnotherTab(page, earlier, later);
      await page.locator('#account-dialog [data-close-dialog]').click();
      await dialogCloses(page);
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      release();
      await page.locator('#account-who').filter({ hasText: `Signed in as ${later.email}` }).waitFor();
    });

    check('a session found ended while the menu is open asks for a sign-in, with its check', async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'menu-end' });
      await signInPage(page, account);
      await visit(page, { lang: 'en' });
      await askForChart(page);
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      await page.locator('#compare-btn').click();
      await page.locator('#compare-note').waitFor({ state: 'visible' });
      await page.locator('#date').fill('1990-05-09');
      await page.locator('#time').fill('12:00');
      await page.locator('#location').fill(CHENGDU.city);
      await page.locator('.location-suggestion').click();
      await page.locator('#create-chart-btn').click();
      await page.locator('#compare-view').waitFor({ state: 'visible' });
      // Back to the second birth; the menu opens there, before the check's script has
      // loaded; the session ends elsewhere; and the comparison comes forward again.
      await page.goBack();
      await page.locator('#compare-note').waitFor({ state: 'visible' });
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      await page.locator('#account-who').filter({ hasText: `Signed in as ${account.email}` }).waitFor();
      await asAccount(playwright, account, async (request) => {
        assert.equal((await request.delete('/api/account/sessions')).status(), 204);
      });
      await page.goForward();
      await page.locator('#account-notice').filter({ hasText: 'Your session ended. Sign in again.' }).waitFor();
      await turnstileAnswered(page);
      await signInThroughDialog(page, account.email);
      await page.locator('#compare-view').waitFor({ state: 'visible' });
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
