// Accounts for the browser suites: charts need one. A suite signs in to a new account
// through the app's own API, as the page does, reading the code from the folder the
// app under test writes its emails to (EC_MAIL_DIRECTORY), and gives every page it
// opens that session. Asking for a code asks Cloudflare whether the page's answer to
// Turnstile is good, so the app under test runs with Turnstile's test keys.
import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';

const baseURL = process.env.EC_BASE_URL;
const mailDirectory = process.env.EC_MAIL_DIRECTORY;
assert.ok(baseURL, 'Set EC_BASE_URL to the app under test.');
assert.ok(mailDirectory, 'Set EC_MAIL_DIRECTORY to the folder the app under test writes its emails to.');
// The app takes requests that change an account only from its own origin.
const origin = new URL(baseURL).origin;

// What Turnstile's test site keys answer; their test secret accepts it.
const TURNSTILE_TEST_TOKEN = 'XXXX.DUMMY.TOKEN.XXXX';

// A new address, on a domain kept for examples.
let addresses = 0;
const newAddress = (label = 'reader') => {
  addresses += 1;
  return `${label}-${process.pid}-${Date.now()}-${addresses}@example.com`;
};

// The newest email the app wrote to `email`: its subject, its text and its code.
async function readMail(email) {
  const names = (await readdir(mailDirectory)).filter((name) => name.endsWith('.eml')).sort().reverse();
  for (const name of names) {
    const text = await readFile(join(mailDirectory, name), 'utf8');
    const split = text.search(/\r?\n\r?\n/);
    // Headers, each on one line.
    const headers = text.slice(0, split).replace(/\r?\n[ \t]+/g, ' ');
    const header = (field) => new RegExp(`^${field}: (.*)$`, 'mi').exec(headers)?.[1].trim();
    if (header('To') !== email) continue;
    let body = text.slice(split).trim();
    if (header('Content-Transfer-Encoding')?.toLowerCase() === 'base64') {
      body = Buffer.from(body.replace(/\s+/g, ''), 'base64').toString('utf8');
    }
    const code = /^ {4}(\d{3}) (\d{3})\r?$/m.exec(body);
    return { subject: header('Subject'), body, code: code ? code[1] + code[2] : null };
  }
  throw new Error(`No email to ${email} in ${mailDirectory}.`);
}

async function readCode(email) {
  const { code, subject } = await readMail(email);
  assert.ok(code, `The newest email to ${email} has no code: ${subject}`);
  return code;
}

const apiContext = (playwright, cookies = []) => playwright.request.newContext({
  baseURL, extraHTTPHeaders: { Origin: origin }, storageState: { cookies, origins: [] },
});

// A new account, signed in through the API: its address and its session's cookie. The
// address is a new one, unless `email` names it (an account made again with it).
async function newAccount(playwright, { language = 'en', label = 'reader', email = newAddress(label) } = {}) {
  const request = await apiContext(playwright);
  try {
    const asked = await request.post('/api/account/code', {
      data: { email, purpose: 'create', language, page_language: language, turnstile: TURNSTILE_TEST_TOKEN },
    });
    assert.equal(asked.status(), 202, `Asking for a code: ${await asked.text()}`);
    const signed = await request.post('/api/account/session', { data: { email, code: await readCode(email) } });
    assert.equal(signed.status(), 200, `Signing in: ${await signed.text()}`);
    const { key } = await signed.json();
    const { cookies } = await request.storageState();
    assert.equal(cookies.length, 1, 'Signing in sets one cookie, the session.');
    return { email, key, cookies };
  } finally {
    await request.dispose();
  }
}

// Another session of an existing account, as another tab signing in to it again gets.
async function newSession(playwright, account) {
  const request = await apiContext(playwright);
  try {
    const asked = await request.post('/api/account/code', {
      data: { email: account.email, purpose: 'sign_in', page_language: 'en', turnstile: TURNSTILE_TEST_TOKEN },
    });
    assert.equal(asked.status(), 202, `Asking for a code: ${await asked.text()}`);
    const signed = await request.post('/api/account/session', {
      data: { email: account.email, code: await readCode(account.email) },
    });
    assert.equal(signed.status(), 200, `Signing in: ${await signed.text()}`);
    const { key } = await signed.json();
    const { cookies } = await request.storageState();
    return { email: account.email, key, cookies };
  } finally {
    await request.dispose();
  }
}

// A request on the account's behalf, outside any page: `run` gets the API context.
async function asAccount(playwright, account, run) {
  const request = await apiContext(playwright, account.cookies);
  try {
    return await run(request);
  } finally {
    await request.dispose();
  }
}

async function deleteAccount(playwright, account) {
  await asAccount(playwright, account, async (request) => {
    const deleted = await request.delete('/api/account', { data: { email: account.email, key: account.key } });
    assert.equal(deleted.status(), 204, `Deleting the test account: ${await deleted.text()}`);
  });
}

// Pages share nothing: each gets the session's cookie before it opens the app.
async function signInPage(page, account) {
  await page.context().addCookies(account.cookies);
}

// Cloudflare's Turnstile widget, in place of its script: it answers as the test site
// keys do, at once, and again after each reset, with the token their test secret
// accepts. `window.__turnstile` says what it was given. No test depends on Cloudflare's
// page; with `load: false` the script does not load at all.
const TURNSTILE_STUB = `(() => {
  const widgets = new Map();
  let made = 0;
  const answer = (id) => setTimeout(() => {
    const widget = widgets.get(id);
    if (!widget) return;
    widget.token = ${JSON.stringify(TURNSTILE_TEST_TOKEN)};
    window.__turnstile.token = widget.token;
    widget.options.callback(widget.token);
  }, 0);
  window.turnstile = {
    render(container, options) {
      made += 1;
      const id = 'widget-' + made;
      const box = document.createElement('div');
      box.className = 'turnstile-stub';
      container.append(box);
      widgets.set(id, { options, box, token: '' });
      window.__turnstile = { sitekey: options.sitekey, language: options.language, token: '', resets: 0 };
      answer(id);
      return id;
    },
    getResponse: (id) => widgets.get(id).token,
    reset(id) {
      widgets.get(id).token = '';
      window.__turnstile.token = '';
      window.__turnstile.resets += 1;
      answer(id);
    },
    remove(id) {
      widgets.get(id).box.remove();
      widgets.delete(id);
    },
  };
})();`;
async function stubTurnstile(page, { load = true } = {}) {
  await page.route((url) => url.hostname === 'challenges.cloudflare.com', (route) => (load
    ? route.fulfill({ contentType: 'text/javascript', body: TURNSTILE_STUB })
    : route.abort()));
}
// Until the widget has answered, the dialog asks for no code.
async function turnstileAnswered(page) {
  await page.waitForFunction(() => Boolean(window.__turnstile?.token));
}

export {
  TURNSTILE_TEST_TOKEN, newAddress, readMail, readCode, newAccount, newSession, asAccount, deleteAccount, signInPage,
  stubTurnstile, turnstileAnswered,
};
