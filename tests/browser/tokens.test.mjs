// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Stage 2 of the look-and-feel review (2026-10-17): the token set finished. Every corner
// the views draw is on the radius scale, every line height on the leading scale, and
// every control one of the control heights, wherever it stands: the start page, a chart
// with its luck pillar and a topic open, the life grid, Today, Settings and the dialogs.
import {
  assert, describe, it, engineName, profiles, openLink, settled, withPage, HELSINKI,
} from './chart-helpers.mjs';

const BIRTH = new URLSearchParams({
  date: '1975-08-14', time: '07:45', place: HELSINKI.display, city: HELSINKI.city,
  latitude: String(HELSINKI.latitude), longitude: String(HELSINKI.longitude), timezone: HELSINKI.timezone,
  lang: 'en', gender: 'female',
});
const PLACE = {
  name: HELSINKI.display, city: HELSINKI.city, timezone: HELSINKI.timezone,
  latitude: HELSINKI.latitude, longitude: HELSINKI.longitude,
};
const DAY = '2026-10-07';
// The scales, as style.css defines them: radii in px (and 1px, the gua's lines), and
// leading as a share of the font size; a row of its own height (a hidden stem's line, the
// luck ribbon's direction) is in px.
const RADII = [0, 1, 2, 4, 8, 12, 16, 24, 999];
const LEADING = [1, 1.15, 1.35, 1.5, 1.7];
const ROWS = [16, 20];
// Each control's height, on a desktop and on a phone.
const CONTROLS = {
  '.segmented > button': [36, 44],
  '.bar-action': [36, 44],
  '.topic-button, .chart-topics .context-toggle': [36, 44],
  '.panel-close': [36, 44],
  '.canon-link': [36, 44],
  '.role-choice': [36, 44],
  '.gender-option span': [36, 44],
  '.language-switch': [36, 44],
  '.today-partner select, .settings-choose select': [36, 44],
  '.library-btn': [28, 28],
  '.field-group input, .account-field input[type="email"], .palette-input': [48, 48],
  '.submit-btn': [48, 48],
};
// A group of choices: a control's height, its padding and its hairline.
const GROUPS = { '.segmented, .gender-options, .today-partner': [46, 54] };

// Every corner and line height drawn in the document that is off its scale.
function offScale(page) {
  return page.evaluate(({ radii, leading, rows }) => {
    const problems = [];
    const name = (element, pseudo) => `${element.tagName.toLowerCase()}${element.id ? `#${element.id}` : ''}`
      + `${[...element.classList].map((c) => `.${c}`).join('')}${pseudo ?? ''}`;
    for (const element of document.body.querySelectorAll('*')) {
      if (!element.checkVisibility()) continue;
      for (const pseudo of [null, '::before', '::after']) {
        const style = getComputedStyle(element, pseudo);
        if (pseudo && style.content === 'none') continue;
        for (const part of style.borderRadius.split(/[\s/]+/)) {
          if (part.endsWith('%')) continue;
          if (!radii.includes(parseFloat(part))) problems.push(`radius ${style.borderRadius}: ${name(element, pseudo)}`);
        }
        if (pseudo || style.lineHeight === 'normal') continue;
        const line = parseFloat(style.lineHeight);
        const size = parseFloat(style.fontSize);
        if (!leading.some((share) => Math.abs(line - size * share) < 0.02) && !rows.some((row) => Math.abs(line - row) < 0.02)) {
          problems.push(`line height ${style.lineHeight} at ${style.fontSize}: ${name(element)}`);
        }
      }
    }
    return [...new Set(problems)];
  }, { radii: RADII, leading: LEADING, rows: ROWS });
}

// Every visible control, and group of them, whose height is not its own.
function offHeight(page, mobile) {
  return page.evaluate(({ controls, groups, at }) => {
    const problems = [];
    for (const [selector, heights] of [...Object.entries(controls), ...Object.entries(groups)]) {
      for (const element of document.querySelectorAll(selector)) {
        if (!element.checkVisibility()) continue;
        const height = Math.round(element.getBoundingClientRect().height * 100) / 100;
        if (Math.abs(height - heights[at]) > 0.5) {
          problems.push(`${selector} ${height}px, not ${heights[at]}px: ${element.textContent.trim().slice(0, 30)}`);
        }
      }
    }
    return problems;
  }, { controls: CONTROLS, groups: GROUPS, at: mobile ? 1 : 0 });
}

// The account's place, written as Settings writes it, so that Today reads a day.
async function keepPlace(page) {
  await page.evaluate(async (place) => {
    const read = await (await fetch('/api/account/settings')).json();
    const response = await fetch('/api/account/place', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ place, key: read.key, updated_at: read.updated_at }),
    });
    if (!response.ok) throw new Error(`PUT /api/account/place: ${response.status}`);
  }, PLACE);
}

// The views the audits read, each once nothing moves.
async function eachView(page, visit) {
  await page.goto(new URL('/', process.env.EC_BASE_URL).href);
  await page.locator('#input-view').waitFor({ state: 'visible' });
  await settled(page);
  await visit('the start page');
  await page.locator('#account-btn').click();
  await page.locator('#account-dialog[open]').waitFor();
  await settled(page);
  await visit('the account dialog');
  await page.keyboard.press('Escape');
  await openLink(page, `/#chart?${BIRTH}&luck=5/stem&topic=relationships`, { place: HELSINKI });
  await visit('a chart with its luck pillar, the relationships open');
  await page.locator('.pillar-identity[data-pillar="hour"]').focus();
  await page.keyboard.press('?');
  await page.locator('#keys-dialog[open]').waitFor();
  await settled(page);
  await visit('the keys');
  await page.keyboard.press('Escape');
  await page.keyboard.press('ControlOrMeta+k');
  await page.locator('#command-palette[open]').waitFor();
  await settled(page);
  await visit('the commands');
  await page.keyboard.press('Escape');
  await page.locator('#library-btn').click();
  await page.locator('#library-dialog[open]').waitFor();
  await settled(page);
  await visit('the saved charts');
  await page.keyboard.press('Escape');
  await openLink(page, `/#chart?${BIRTH}&topic=roles`, { place: HELSINKI });
  await visit('a chart with its roles open');
  await keepPlace(page);
  await page.goto(new URL(`/#today?${BIRTH}&day=${DAY}`, process.env.EC_BASE_URL).href);
  await page.locator('#today-body:not(.hidden)').waitFor();
  await page.waitForFunction(() => !document.getElementById('today-view').hasAttribute('aria-busy'));
  await settled(page);
  await visit('Today');
  await page.goto(new URL('/#settings', process.env.EC_BASE_URL).href);
  await page.locator('#settings-schools-body .settings-school').first().waitFor();
  await settled(page);
  await visit('Settings');
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / tokens`, { concurrency: false }, () => {
    const check = (name, run) => it(name, () => withPage(profile, run));

    check('every corner and line height in the views is on its scale', async (page) => {
      const found = [];
      await eachView(page, async (view) => {
        for (const problem of await offScale(page)) found.push(`${view}: ${problem}`);
      });
      assert.deepEqual(found, []);
    });

    check('every control stands at its height, and every group of them at one height', async (page) => {
      const found = [];
      await eachView(page, async (view) => {
        for (const problem of await offHeight(page, profile.isMobile)) found.push(`${view}: ${problem}`);
      });
      assert.deepEqual(found, []);
    });
  });
}
