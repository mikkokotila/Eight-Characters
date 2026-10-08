// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Account sessions: one that ends asks for a sign-in once more; an answer that comes
// late, for a chart, a comparison or the account's menu, changes nothing it should
// not; and tabs share the session cookie, so another tab signing out, or in to another
// account, is followed here. Late answers are held on their way with page.route; the
// other tab is played by the API (account-helpers.mjs).
import { readFile } from 'node:fs/promises';
import {
  assert, describe, it, engineName, profiles, settled, withPage, playwright, CHENGDU,
} from './chart-helpers.mjs';
import { newAccount, newSession, asAccount, readCode, signInPage, turnstileAnswered } from './account-helpers.mjs';
import {
  BIRTH, link, visit, chartsAskedFor, askForChart, dialogIsOpen, dialogOpens, dialogCloses, text, sendCode,
  signInThroughDialog,
} from './account-page.mjs';

// Another tab of the same browser signs out, and in to another account: the
// session it signed out of ends, and the cookie the tabs share becomes the other
// account's.
const switchInAnotherTab = async (page, from, to) => {
  await asAccount(playwright, from, async (request) => {
    assert.equal((await request.delete('/api/account/session')).status(), 204);
  });
  await page.context().addCookies(to.cookies);
};

// Holds the first GET of `pattern` after the server has answered it: `answered`
// resolves when it has, and `release` lets the answer reach the page.
const holdAnswer = async (page, pattern, method = 'GET') => {
  let release;
  const held = new Promise((resolve) => { release = resolve; });
  let sent;
  const answered = new Promise((resolve) => { sent = resolve; });
  let holding = true;
  // Once it has the request it holds, the route is removed: the page's later
  // requests go to the server untouched.
  const hold = async (route) => {
    if (!holding || route.request().method() !== method) return route.continue();
    holding = false;
    await page.unroute(pattern, hold);
    const response = await route.fetch();
    sent();
    await held;
    return route.fulfill({ response });
  };
  await page.route(pattern, hold);
  return { answered, release };
};

// Holds the page's first `method` request to `pattern` before it reaches the server:
// `sent` resolves when the page has made it, and `release` sends it on.
const holdRequest = async (page, pattern, method) => {
  let release;
  const held = new Promise((resolve) => { release = resolve; });
  let made;
  const sent = new Promise((resolve) => { made = resolve; });
  let holding = true;
  const hold = async (route) => {
    if (!holding || route.request().method() !== method) return route.continue();
    holding = false;
    await page.unroute(pattern, hold);
    made();
    await held;
    return route.continue();
  };
  await page.route(pattern, hold);
  return { sent, release };
};

// Holds the account in the page's next sign-in answer: the answer reaches the page, and
// with it the session cookie it sets, but its body waits until `release`. Later
// sign-ins are not held. `answered` resolves once the answer has reached the page;
// `checked(n)`, once the answers to n of the page's questions of who the session is
// have reached it, from now on.
const holdSignInBody = async (page) => {
  await page.evaluate(() => {
    const fetched = window.fetch.bind(window);
    let holding = true;
    window.__checks = 0;
    window.__signInAnswered = new Promise((resolve) => { window.__signInAnswer = resolve; });
    window.fetch = async (url, init) => {
      const response = await fetched(url, init);
      const method = init?.method ?? 'GET';
      if (String(url) === '/api/account' && method === 'GET') window.__checks += 1;
      if (!holding || String(url) !== '/api/account/session' || method !== 'POST') return response;
      holding = false;
      const released = new Promise((resolve) => { window.__releaseSignIn = resolve; });
      const json = response.json.bind(response);
      response.json = async () => { await released; return json(); };
      window.__signInAnswer();
      return response;
    };
  });
  return {
    answered: () => page.evaluate(() => window.__signInAnswered),
    release: () => page.evaluate(() => window.__releaseSignIn()),
    checked: (count) => page.waitForFunction((n) => window.__checks >= n, count),
  };
};

// From a chart on screen, signed in to `first`: that session ends elsewhere, the next
// chart is refused, and the refusal is held on its way (`chart.release` lets it go).
// The account's menu, opened meanwhile, finds the session ended and asks for a sign-in.
const refusedWhileSigningIn = async (page, first) => {
  await visit(page, { lang: 'en' });
  await askForChart(page);
  await page.locator('#chart-view').waitFor({ state: 'visible' });
  await settled(page);
  await asAccount(playwright, first, async (request) => {
    assert.equal((await request.delete('/api/account/session')).status(), 204);
  });
  const chart = await holdAnswer(page, '**/api/four_pillars', 'POST');
  await page.locator('#chart-language button[data-chart-lang="fi"]').click();
  await chart.answered;
  await page.keyboard.press('ControlOrMeta+k');
  await page.locator('#palette-input').fill('tili');
  await page.keyboard.press('Enter');
  await dialogOpens(page);
  await page.locator('#account-start').waitFor({ state: 'visible' });
  return chart;
};

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / account sessions`, { concurrency: false }, () => {
    // Every page here starts without the suite's session; each test signs in as it says.
    const check = (name, run) => it(name, { timeout: 90000 }, () => withPage(profile, run, { signedIn: false }));

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
        assert.equal((await request.delete('/api/account/sessions', { data: { email: account.email } })).status(), 204);
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
        assert.equal((await request.delete('/api/account/sessions', { data: { email: account.email } })).status(), 204);
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
        assert.equal((await request.delete('/api/account/sessions', { data: { email: account.email } })).status(), 204);
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
        assert.equal((await request.delete('/api/account/sessions', { data: { email: account.email } })).status(), 204);
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
        assert.equal((await request.patch('/api/account', { data: { language: 'fi', email: account.email } })).status(), 200);
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

    check('an action for an account another tab has left does nothing, and says so', async (page) => {
      const earlier = await newAccount(playwright, { language: 'en', label: 'name-a' });
      const later = await newAccount(playwright, { language: 'en', label: 'name-b' });
      await signInPage(page, earlier);
      await visit(page, { lang: 'en' });
      let downloads = 0;
      page.on('download', () => { downloads += 1; });
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      await page.locator('#account-who').filter({ hasText: `Signed in as ${earlier.email}` }).waitFor();
      // Another tab signs in to another account while this menu stays open.
      await switchInAnotherTab(page, earlier, later);
      await page.locator('#account-export').click();
      await page.locator('#account-status').filter({ hasText: 'The account changed meanwhile: nothing was done.' }).waitFor();
      await page.locator('#account-who').filter({ hasText: `Signed in as ${later.email}` }).waitFor();
      assert.equal(downloads, 0);
    });

    check("the menu's late refusal leaves a session another tab signed in to", async (page) => {
      const earlier = await newAccount(playwright, { language: 'en', label: 'refused-a' });
      const later = await newAccount(playwright, { language: 'en', label: 'refused-b' });
      await signInPage(page, earlier);
      await visit(page, { lang: 'en' });
      // The earlier session ends elsewhere. The menu's question of who the session is
      // is refused at once, and the answer held on its way.
      await asAccount(playwright, earlier, async (request) => {
        assert.equal((await request.delete('/api/account/session')).status(), 204);
      });
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
      // Another tab signs in to another account; the menu is closed and opened again.
      await page.context().addCookies(later.cookies);
      await page.locator('#account-dialog [data-close-dialog]').click();
      await dialogCloses(page);
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      release();
      await page.locator('#account-who').filter({ hasText: `Signed in as ${later.email}` }).waitFor();
      assert.equal(await page.locator('#account-notice').isVisible(), false);
    });

    check("a chart's late refusal leaves a new session of the same account", async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'renewed-tab' });
      await signInPage(page, account);
      await visit(page, { lang: 'en' });
      await askForChart(page);
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      // The chart asked for next is held on its way. Its answer comes last: the
      // server's refusal for the session it was sent with, which ends meanwhile.
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
      // Another tab signs out, and in again to the same account.
      const renewed = await newSession(playwright, account);
      await switchInAnotherTab(page, account, renewed);
      release();
      // The refusal is checked: the browser holds a session, and the chart is drawn
      // in Finnish without asking for a sign-in.
      await page.waitForFunction(() => document.documentElement.lang === 'fi'
        && !document.getElementById('chart-view').hasAttribute('aria-busy'));
      await settled(page);
      assert.equal(await dialogIsOpen(page), false);
      assert.equal(await text(page, '#account-btn'), 'Tili');
      assert.equal(await page.locator('#chart-view').isVisible(), true);
    });

    check('a chart left while its refusal is checked asks for no sign-in', async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'left' });
      await signInPage(page, account);
      await visit(page, { lang: 'en' });
      await askForChart(page);
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      // The session ends elsewhere: the next chart is refused, and the page's check of
      // the session that follows is refused too, and held on its way.
      await asAccount(playwright, account, async (request) => {
        assert.equal((await request.delete('/api/account/sessions', { data: { email: account.email } })).status(), 204);
      });
      const check = await holdAnswer(page, '**/api/account');
      await page.locator('#chart-language button[data-chart-lang="fi"]').click();
      await check.answered;
      // Back to the form meanwhile: that chart is no longer wanted.
      await page.goBack();
      await page.locator('#chart-form').waitFor({ state: 'visible' });
      check.release();
      await page.waitForTimeout(500);
      assert.equal(await dialogIsOpen(page), false);
    });

    check('signing out everywhere signs the page out, though it took another account meanwhile', async (page) => {
      const earlier = await newAccount(playwright, { language: 'en', label: 'everywhere-a' });
      const later = await newAccount(playwright, { language: 'en', label: 'everywhere-b' });
      await signInPage(page, earlier);
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
      await page.goBack();
      await page.locator('#compare-note').waitFor({ state: 'visible' });
      // Sign out on every device goes through for the earlier account, and its answer,
      // which removes the session cookie, is held on its way.
      const everywhere = await holdAnswer(page, '**/api/account/sessions', 'DELETE');
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      await page.locator('#account-who').filter({ hasText: `Signed in as ${earlier.email}` }).waitFor();
      await page.locator('#account-sign-out-everywhere').click();
      await everywhere.answered;
      // Another tab signs in to another account, which the comparison, come forward
      // again, takes.
      await page.context().addCookies(later.cookies);
      await page.goForward();
      await page.locator('#compare-view').waitFor({ state: 'visible' });
      everywhere.release();
      await page.locator('#account-notice').filter({ hasText: 'You are signed out on every device.' }).waitFor();
      assert.equal(await text(page, '#account-btn'), 'Sign in');
    });

    check("a chart's check of its refusal leaves a language set meanwhile", async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'recheck-tongue' });
      await signInPage(page, account);
      await visit(page, { lang: 'en' });
      // The chart asked for is refused (sent, say, with a session replaced since), and
      // the page's check that follows is answered at once, for the account in English,
      // and held on its way.
      let refusing = true;
      await page.route('**/api/four_pillars', async (route) => {
        if (!refusing) return route.continue();
        refusing = false;
        return route.fulfill({ status: 401, json: { detail: 'Sign in to continue.' } });
      });
      const check = await holdAnswer(page, '**/api/account');
      await askForChart(page);
      await check.answered;
      // The account's language is set to Finnish meanwhile, in its menu.
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      await page.locator('[data-account-lang="fi"]:not([disabled])').click();
      await page.waitForFunction(() =>
        document.querySelector('[data-account-lang="fi"]').getAttribute('aria-pressed') === 'true');
      check.release();
      // The chart, asked for again once the check found the session, is drawn.
      await page.locator('#account-dialog [data-close-dialog]').click();
      await dialogCloses(page);
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      assert.equal(await page.locator('[data-account-lang="fi"]').getAttribute('aria-pressed'), 'true');
      const stored = await asAccount(playwright, account, async (request) => (await request.get('/api/account')).json());
      assert.equal(stored.language, 'fi');
    });

    check("a sign-in answered after the page took another tab's session leaves that one", async (page) => {
      const earlier = await newAccount(playwright, { language: 'fi', label: 'late-in-a' });
      const later = await newAccount(playwright, { language: 'en', label: 'late-in-b' });
      await signInPage(page, earlier);
      const chart = await refusedWhileSigningIn(page, earlier);
      // The earlier account signs in again. The answer has set its cookie; its body is
      // held on its way.
      const signIn = await holdSignInBody(page);
      await sendCode(page, earlier.email);
      await page.locator('#account-code').fill(await readCode(earlier.email));
      await page.locator('#account-verify').click();
      await signIn.answered();
      // Another tab signs in to another account, which the refused chart's check,
      // released now, takes: the page speaks its language.
      await page.context().addCookies(later.cookies);
      chart.release();
      await page.waitForFunction(() => document.documentElement.lang === 'en');
      // The sign-in's answer comes last. The page keeps the account the browser holds,
      // and its language (taking the sign-in's would turn the page Finnish).
      await signIn.release();
      await dialogCloses(page);
      await page.waitForTimeout(300);
      assert.equal(await page.evaluate(() => document.documentElement.lang), 'en');
      await page.keyboard.press('ControlOrMeta+k');
      await page.locator('#palette-input').fill('account');
      await page.keyboard.press('Enter');
      await dialogOpens(page);
      await page.locator('#account-who').filter({ hasText: `Signed in as ${later.email}` }).waitFor();
    });

    check("a sign-in that sets its cookie after the page took another tab's session signs the page in", async (page) => {
      const first = await newAccount(playwright, { language: 'en', label: 'set-late-a' });
      const signing = await newAccount(playwright, { language: 'fi', label: 'set-late-b' });
      const other = await newAccount(playwright, { language: 'en', label: 'set-late-c' });
      await signInPage(page, first);
      const chart = await refusedWhileSigningIn(page, first);
      // Another account signs in here, and its request is held before it reaches the
      // server, so its answer sets its cookie last.
      const signIn = await holdRequest(page, '**/api/account/session', 'POST');
      await sendCode(page, signing.email);
      await page.locator('#account-code').fill(await readCode(signing.email));
      await page.locator('#account-verify').click();
      await signIn.sent;
      // Another tab signs in to a third account, which the refused chart's check,
      // released now, takes: the page speaks its language.
      await page.context().addCookies(other.cookies);
      chart.release();
      await page.waitForFunction(() => document.documentElement.lang === 'en');
      // The sign-in goes through now. The browser holds its session: the page is signed
      // in to its account, and speaks its language.
      signIn.release();
      await dialogCloses(page);
      await page.waitForFunction(() => document.documentElement.lang === 'fi');
      assert.equal(await text(page, '#account-btn'), 'Tili');
      await page.keyboard.press('ControlOrMeta+k');
      await page.locator('#palette-input').fill('tili');
      await page.keyboard.press('Enter');
      await dialogOpens(page);
      await page.locator('#account-who').filter({ hasText: signing.email }).waitFor();
    });

    check('a sign-in whose session ends before its account arrives asks for a sign-in again', async (page) => {
      const first = await newAccount(playwright, { language: 'en', label: 'end-late-a' });
      const signing = await newAccount(playwright, { language: 'en', label: 'end-late-b' });
      await signInPage(page, first);
      const asked = chartsAskedFor(page);
      const chart = await refusedWhileSigningIn(page, first);
      // Another account signs in. The answer has set its cookie; its body is held on its
      // way.
      const signIn = await holdSignInBody(page);
      await sendCode(page, signing.email);
      await page.locator('#account-code').fill(await readCode(signing.email));
      await page.locator('#account-verify').click();
      await signIn.answered();
      // Another tab signs out of that session, which the refused chart's check, released
      // now, finds ended.
      const cookies = await page.context().cookies();
      await asAccount(playwright, { cookies }, async (request) => {
        assert.equal((await request.delete('/api/account/session')).status(), 204);
      });
      await page.context().clearCookies();
      const check = page.waitForResponse((response) => new URL(response.url()).pathname === '/api/account'
        && response.request().method() === 'GET');
      chart.release();
      assert.equal((await check).status(), 401);
      await signIn.checked(1);
      // The sign-in's account comes last. The browser holds no session: the dialog asks
      // for a sign-in again, and no chart is asked for without one.
      const charts = asked.length;
      await signIn.release();
      await page.locator('#account-start').waitFor({ state: 'visible' });
      assert.equal(await text(page, '#account-notice'), 'Istuntosi päättyi. Kirjaudu uudelleen.');
      assert.equal(await text(page, '#account-btn'), 'Kirjaudu');
      await page.waitForTimeout(300);
      assert.equal(await dialogIsOpen(page), true);
      assert.equal(asked.length, charts);
      // Signed in again, the chart is drawn.
      await signInThroughDialog(page, signing.email);
      await page.waitForFunction(() => !document.getElementById('chart-view').hasAttribute('aria-busy'));
      await settled(page);
      assert.equal(await page.locator('#chart-view').isVisible(), true);
      assert.equal(asked.length, charts + 1);
    });

    check('a language set while an older check finds the session ended keeps the session it was set in', async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'set-ended' });
      await signInPage(page, account);
      await visit(page, { lang: 'en' });
      const asked = chartsAskedFor(page);
      await askForChart(page);
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      // The next chart is refused, and the refusal held on its way.
      let releaseChart;
      const chartHeld = new Promise((resolve) => { releaseChart = resolve; });
      let refusing = true;
      await page.route('**/api/four_pillars', async (route) => {
        if (!refusing) return route.continue();
        refusing = false;
        await chartHeld;
        return route.fulfill({ status: 401, json: { detail: 'Sign in to continue.' } });
      });
      await page.locator('#chart-language button[data-chart-lang="fi"]').click();
      // The account's menu opens, and names the account.
      await page.keyboard.press('ControlOrMeta+k');
      await page.locator('#palette-input').fill('tili');
      await page.keyboard.press('Enter');
      await dialogOpens(page);
      await page.locator('#account-who').filter({ hasText: account.email }).waitFor();
      // The session ends elsewhere, and the refused chart's check of the session, sent
      // now, is refused too and held on its way.
      await asAccount(playwright, account, async (request) => {
        assert.equal((await request.delete('/api/account/session')).status(), 204);
      });
      const check = await holdAnswer(page, '**/api/account');
      releaseChart();
      await check.answered;
      // Another tab signs in to the account again. Finnish is set in the menu, in that
      // session, and the answer held on its way.
      const renewed = await newSession(playwright, account);
      await page.context().addCookies(renewed.cookies);
      const patch = await holdAnswer(page, '**/api/account', 'PATCH');
      await page.locator('[data-account-lang="fi"]:not([disabled])').click();
      await patch.answered;
      // The check's refusal, the older answer, comes first: the dialog asks for a sign-in.
      check.release();
      await page.locator('#account-start').waitFor({ state: 'visible' });
      // The language's answer, the newer, comes last: the session holds, and the page is
      // signed in to it, in Finnish, and draws the chart.
      const charts = asked.length;
      patch.release();
      await dialogCloses(page);
      await page.waitForFunction(() => !document.getElementById('chart-view').hasAttribute('aria-busy'));
      await settled(page);
      assert.equal(await text(page, '#account-btn'), 'Tili');
      assert.equal(await page.evaluate(() => document.documentElement.lang), 'fi');
      assert.equal(asked.length, charts + 1);
      assert.equal(await page.locator('#chart-view').isVisible(), true);
      const stored = await asAccount(playwright, renewed, async (request) => (await request.get('/api/account')).json());
      assert.equal(stored.language, 'fi');
    });

    check('a language answered after newer checks keeps the language they found', async (page) => {
      const account = await newAccount(playwright, { language: 'en', label: 'set-stale-a' });
      const other = await newAccount(playwright, { language: 'en', label: 'set-stale-b' });
      await signInPage(page, account);
      await visit(page, { lang: 'en' });
      await askForChart(page);
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      // A comparison, then back to its second birth, so that coming forward checks the
      // session again.
      await page.locator('#compare-btn').click();
      await page.locator('#compare-note').waitFor({ state: 'visible' });
      await page.locator('#date').fill('1990-05-09');
      await page.locator('#time').fill('12:00');
      await page.locator('#location').fill(CHENGDU.city);
      await page.locator('.location-suggestion').click();
      await page.locator('#create-chart-btn').click();
      await page.locator('#compare-view').waitFor({ state: 'visible' });
      await page.goBack();
      await page.locator('#compare-note').waitFor({ state: 'visible' });
      // Finnish is set in the menu, and the answer held on its way.
      await page.locator('#account-btn').click();
      await dialogOpens(page);
      await page.locator('#account-who').filter({ hasText: `Signed in as ${account.email}` }).waitFor();
      const patch = await holdAnswer(page, '**/api/account', 'PATCH');
      await page.locator('[data-account-lang="fi"]:not([disabled])').click();
      await patch.answered;
      // Another tab signs in to another account, which the comparison, come forward, takes.
      await page.context().addCookies(other.cookies);
      await page.goForward();
      await page.locator('#account-who').filter({ hasText: `Signed in as ${other.email}` }).waitFor();
      // Another tab signs in to the first account again and sets its language back to
      // English, and the comparison, come forward again, takes it.
      const renewed = await newSession(playwright, account);
      await asAccount(playwright, renewed, async (request) => {
        assert.equal((await request.patch('/api/account', { data: { language: 'en', email: account.email } })).status(), 200);
      });
      await page.context().addCookies(renewed.cookies);
      await page.goBack();
      await page.locator('#compare-note').waitFor({ state: 'visible' });
      await page.goForward();
      await page.locator('#account-who').filter({ hasText: `Signed in as ${account.email}` }).waitFor();
      // Finnish's answer, the older, comes last: the page keeps English, the newer, and
      // says that nothing was done.
      patch.release();
      await page.locator('#account-status').filter({ hasText: 'The account changed meanwhile: nothing was done.' }).waitFor();
      assert.equal(await page.locator('[data-account-lang="en"]').getAttribute('aria-pressed'), 'true');
      assert.equal(await page.locator('[data-account-lang="fi"]').getAttribute('aria-pressed'), 'false');
      assert.equal(await page.evaluate(() => document.documentElement.lang), 'en');
      const stored = await asAccount(playwright, renewed, async (request) => (await request.get('/api/account')).json());
      assert.equal(stored.language, 'en');
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
        assert.equal((await request.delete('/api/account/sessions', { data: { email: account.email } })).status(), 204);
      });
      await page.goForward();
      await page.locator('#account-notice').filter({ hasText: 'Your session ended. Sign in again.' }).waitFor();
      await turnstileAnswered(page);
      await signInThroughDialog(page, account.email);
      await page.locator('#compare-view').waitFor({ state: 'visible' });
    });
  });
}
