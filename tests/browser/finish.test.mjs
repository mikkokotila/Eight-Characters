// Run with Node's built-in test runner and an explicitly selected Playwright install.
// The finish (#108): what the look-and-feel review of 2026-10-17 found broken on screen.
// Days that do not collide and whose words stay readable, numbers that keep their units,
// opaque lists, the page's ink on native controls, real italics, a place pin that follows
// the theme, dialogs and forms that hold together, the life grid's labels whole, a Create
// button that keeps its width, text on the type scale; and no way into the Evolution
// explorer from the classic view, which still opens at its address.
import {
  assert, describe, it, engineName, profiles, openChart, openLink, settled, withPage, CHENGDU, HELSINKI,
} from './chart-helpers.mjs';

const BIRTH = { date: '1988-02-04', time: '16:30', gender: 'female' };
const chartParams = (parts = {}) => new URLSearchParams({
  date: BIRTH.date, time: BIRTH.time, place: CHENGDU.display, city: CHENGDU.city,
  latitude: String(CHENGDU.latitude), longitude: String(CHENGDU.longitude), timezone: CHENGDU.timezone,
  lang: 'en', gender: BIRTH.gender, ...parts,
});
// On this day the day before is strongly supportive (+2.00): the longest verdict, beside
// the day in the middle.
const DAY = '2026-10-17';
const PLACE = {
  name: HELSINKI.display, city: HELSINKI.city, timezone: HELSINKI.timezone,
  latitude: HELSINKI.latitude, longitude: HELSINKI.longitude,
};
const SCALE = [13, 15, 18, 22, 32, 44, 52];
const INK = { light: 'rgb(42, 37, 32)', dark: 'rgb(238, 231, 220)' };
const LONG = 'Saara Kristiina Virtanen-Lindqvist';

// The account's settings, written as Settings writes them; every chart saved before is
// removed first. Gives the ids of the charts saved, in order.
async function keep(page, { place = PLACE, charts = [] } = {}) {
  return page.evaluate(async ({ place, charts }) => {
    const write = async (method, path, body) => {
      const read = await (await fetch('/api/account/settings')).json();
      const response = await fetch(path, {
        method, headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...body, key: read.key, updated_at: read.updated_at }),
      });
      const value = await response.json();
      if (!response.ok) throw new Error(`${method} ${path}: ${response.status} ${JSON.stringify(value)}`);
      return value;
    };
    for (const chart of (await (await fetch('/api/account/settings')).json()).charts) {
      await write('DELETE', `/api/account/charts/${chart.id}`, {});
    }
    await write('PUT', '/api/account/place', { place });
    const ids = [];
    for (const { couple, ...chart } of charts) {
      const reply = await write('POST', '/api/account/charts', {
        ...chart, ...(couple === undefined ? {} : { couple_with: ids[couple] }),
      });
      ids.push(reply.saved);
    }
    return ids;
  }, { place, charts });
}
const SAVED = (name, date, time, gender, extra = {}) => ({ name, date, time, gender, place: PLACE, zi: 'split_midnight', ...extra });

async function openToday(page) {
  await page.locator('#today-view').waitFor({ state: 'visible' });
  await page.waitForFunction(() => !document.getElementById('today-view').hasAttribute('aria-busy')
    && !document.getElementById('today-body').classList.contains('hidden'));
  await settled(page);
}

// Every word drawn inside `root`, at the size it reaches the screen: its font size times
// the scale of everything around it.
function renderedWords(page, root) {
  return page.evaluate((root) => {
    const words = [];
    const scope = document.querySelector(root);
    const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const element = node.parentElement;
      if (!node.textContent.trim() || element.closest('.sr-only, .hidden, dialog:not([open])')) continue;
      if (!element.checkVisibility({ checkOpacity: true, visibilityProperty: true })) continue;
      const box = element.getBoundingClientRect();
      if (!box.width || !box.height) continue;
      let scale = 1;
      for (let up = element; up && up !== document.documentElement; up = up.parentElement) {
        const style = getComputedStyle(up);
        if (style.transform !== 'none') { const m = new DOMMatrix(style.transform); scale *= Math.hypot(m.a, m.b); }
        if (style.scale !== 'none') scale *= parseFloat(style.scale);
      }
      words.push({ text: node.textContent.trim().slice(0, 40), size: parseFloat(getComputedStyle(element).fontSize) * scale, scale });
    }
    return words;
  }, root);
}

// A colour as the browser gives it back: rgb(), rgba() or color(srgb ...), with its alpha.
function alphaOf(value) {
  const srgb = value.match(/^color\(srgb [\d.]+ [\d.]+ [\d.]+(?: \/ ([\d.]+))?\)$/);
  if (srgb) return srgb[1] === undefined ? 1 : Number(srgb[1]);
  const rgb = value.match(/^rgba?\([\d.]+, [\d.]+, [\d.]+(?:, ([\d.]+))?\)$/);
  assert.ok(rgb, `a colour: ${value}`);
  return rgb[1] === undefined ? 1 : Number(rgb[1]);
}

// The lightness of a picture's pixels (0 dark, 1 light), its darkest and its lightest.
async function lightness(page, png) {
  return page.evaluate(async (data) => {
    const image = new Image();
    image.src = `data:image/png;base64,${data}`;
    await image.decode();
    const canvas = document.createElement('canvas');
    [canvas.width, canvas.height] = [image.width, image.height];
    const context = canvas.getContext('2d');
    context.drawImage(image, 0, 0);
    const pixels = context.getImageData(0, 0, image.width, image.height).data;
    let [least, most] = [1, 0];
    for (let at = 0; at < pixels.length; at += 4) {
      const value = (0.2126 * pixels[at] + 0.7152 * pixels[at + 1] + 0.0722 * pixels[at + 2]) / 255;
      least = Math.min(least, value);
      most = Math.max(most, value);
    }
    return { least, most };
  }, png.toString('base64'));
}

// The start page, for an account with nothing saved: one with a chart of its own would land
// on that chart.
async function startPage(page) {
  // Only geocoding is stubbed, as openChart stubs it.
  await page.route('**/api/location_suggest', (route) => route.fulfill({ json: { suggestions: [HELSINKI] } }));
  await page.goto(new URL('/', process.env.EC_BASE_URL).href);
  await keep(page);
  await page.goto(new URL('/#', process.env.EC_BASE_URL).href);
  await page.reload();
  await page.locator('#input-view').waitFor({ state: 'visible' });
  await settled(page);
}

async function pickPlace(page) {
  await page.locator('#location').fill(HELSINKI.city);
  await page.locator('.location-suggestion').waitFor({ state: 'visible' });
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / finish`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 120000 }, () => withPage(profile, run));

    check('Today: the days never overlap, whatever their verdicts, and every word on them is at least 13px', async (page) => {
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await keep(page);
      await page.goto(new URL(`/#today?${chartParams()}&day=${DAY}`, process.env.EC_BASE_URL).href);
      await openToday(page);
      const days = await page.evaluate(() => [...document.querySelectorAll('.today-day')]
        .filter((day) => day.checkVisibility({ visibilityProperty: true }))
        .map((day) => {
          const cards = day.querySelector('.today-cards').getBoundingClientRect();
          return { date: day.dataset.todayPick, pull: day.querySelector('.today-day-pull').textContent, left: cards.left, right: cards.right };
        })
        .sort((a, b) => a.left - b.left));
      assert.ok(days.length >= 3, `days shown: ${days.length}`);
      // The case the review found: the strongest verdict, beside the day in the middle.
      assert.ok(days.some((day) => day.date === '2026-10-16' && day.pull.startsWith('Strongly supportive')),
        JSON.stringify(days.map((day) => day.pull)));
      for (let at = 1; at < days.length; at += 1) {
        assert.ok(days[at - 1].right <= days[at].left + 0.5,
          `${days[at - 1].date} ends at ${days[at - 1].right.toFixed(1)}, ${days[at].date} starts at ${days[at].left.toFixed(1)}`);
      }
      const small = (await renderedWords(page, '#today-days')).filter((word) => word.size < 12.95);
      assert.deepEqual(small.map((word) => `${word.text} ${word.size.toFixed(1)}px`), []);
    });

    check('a number keeps its unit on its line, and a pillar\'s mark leaves no word alone', async (page) => {
      await openLink(page, `/#chart?${chartParams()}`);
      const mark = page.locator('.pillar[data-pillar="hour"] .pillar-mark');
      assert.match(await mark.textContent(), /^changed 12 min 24 s ago$/);
      assert.match(await page.locator('#chart-solar-time').textContent(), /· 1 h 17 min 36 s behind clock time$/);
      // Every line of the mark holds more than one word.
      const lines = await mark.evaluate((node) => {
        const text = node.firstChild;
        const rows = new Map();
        let at = 0;
        for (const word of text.textContent.split(' ')) {
          const range = document.createRange();
          range.setStart(text, at);
          range.setEnd(text, at + word.length);
          const top = Math.round(range.getClientRects()[0].top);
          rows.set(top, [...(rows.get(top) ?? []), word]);
          at += word.length + 1;
        }
        return [...rows.values()];
      });
      for (const line of lines) assert.ok(line.length > 1, `a line alone: ${JSON.stringify(lines)}`);
    });

    check('a list floating over the page is opaque, by day and at night', async (page) => {
      await startPage(page);
      for (const scheme of ['light', 'dark']) {
        await page.emulateMedia({ colorScheme: scheme });
        await pickPlace(page);
        await settled(page);
        const background = await page.locator('#location-suggestions').evaluate((node) => getComputedStyle(node).backgroundColor);
        assert.equal(alphaOf(background), 1, `${scheme}: ${background}`);
        await page.locator('#location').fill('');
      }
    });

    check('radio buttons take the page\'s ink, by day and at night', async (page) => {
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await keep(page);
      await page.goto(new URL('/#settings', process.env.EC_BASE_URL).href);
      await page.locator('#settings-schools-body input[type="radio"]').first().waitFor({ state: 'visible' });
      for (const scheme of ['light', 'dark']) {
        await page.emulateMedia({ colorScheme: scheme });
        await settled(page);
        const accents = await page.locator('#settings-schools-body input[type="radio"]').evaluateAll((radios) =>
          [...new Set(radios.map((radio) => getComputedStyle(radio).accentColor))]);
        assert.deepEqual(accents, [INK[scheme]], scheme);
      }
    });

    check('every italic is set in a real italic face', async (page) => {
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await keep(page);
      const italics = async () => page.evaluate(async () => {
        await document.fonts.ready;
        const found = [];
        for (const element of document.querySelectorAll('body *')) {
          if (!element.checkVisibility({ visibilityProperty: true }) || element.closest('.sr-only, .hidden')) continue;
          const own = [...element.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
          const style = getComputedStyle(element);
          if (!own || style.fontStyle === 'normal') continue;
          const family = style.fontFamily.split(',')[0].trim().replace(/^["']|["']$/g, '');
          const face = [...document.fonts].some((font) => font.family.replace(/^["']|["']$/g, '') === family
            && font.style === 'italic' && font.status === 'loaded');
          found.push({ text: element.textContent.trim().slice(0, 30), family, face });
        }
        return found;
      });
      // Today's relationships, each with a line of the canon.
      await page.goto(new URL(`/#today?${chartParams()}&day=${DAY}`, process.env.EC_BASE_URL).href);
      await openToday(page);
      const today = await italics();
      assert.ok(today.length > 0, 'Today shows italic lines');
      assert.deepEqual(today.filter((line) => !line.face), []);
      // The roles' page: its reading's emphasis.
      await openLink(page, `/#chart?${chartParams({ topic: 'roles' })}`);
      await page.locator('#context-detail').waitFor({ state: 'visible' });
      await settled(page);
      const roles = await italics();
      assert.ok(roles.length > 0, 'the roles\' reading shows emphasis');
      assert.deepEqual(roles.filter((line) => !line.face), []);
    });

    check('the place pin is drawn in the page\'s ink, by day and at night', async (page) => {
      await startPage(page);
      const field = page.locator('#location');
      for (const scheme of ['light', 'dark']) {
        await page.emulateMedia({ colorScheme: scheme });
        await settled(page);
        const box = await field.boundingBox();
        // The pin, at the field's right end: 22px square, 14px in from the edge.
        const png = await page.screenshot({ clip: { x: box.x + box.width - 38, y: box.y + box.height / 2 - 11, width: 24, height: 22 } });
        const { least, most } = await lightness(page, png);
        if (scheme === 'light') assert.ok(least < 0.25, `light: darkest ${least.toFixed(2)}`);
        else assert.ok(most > 0.6, `dark: lightest ${most.toFixed(2)}`);
      }
    });

    check('the account dialog: the language switch hugs its two options, and Delete account stands apart', async (page) => {
      await startPage(page);
      await page.locator('#account-btn').click();
      await page.locator('#account-menu').waitFor({ state: 'visible' });
      await settled(page);
      const { switchWidth, optionsWidth } = await page.locator('#account-language-switch').evaluate((node) => {
        const buttons = [...node.querySelectorAll('button')].map((button) => button.getBoundingClientRect());
        const style = getComputedStyle(node);
        const frame = ['paddingLeft', 'paddingRight', 'borderLeftWidth', 'borderRightWidth'].reduce((sum, side) => sum + parseFloat(style[side]), 0);
        return { switchWidth: node.getBoundingClientRect().width, optionsWidth: buttons.at(-1).right - buttons[0].left + frame };
      });
      assert.ok(switchWidth <= optionsWidth + 1, `the switch is ${switchWidth.toFixed(1)}px for ${optionsWidth.toFixed(1)}px of options`);
      const { gap, color, error } = await page.evaluate(() => {
        const remove = document.getElementById('account-delete-open').getBoundingClientRect();
        const others = [...document.querySelectorAll('#account-menu .account-actions button')]
          .filter((button) => button.id !== 'account-delete-open' && button.checkVisibility());
        return {
          gap: remove.top - Math.max(...others.map((button) => button.getBoundingClientRect().bottom)),
          color: getComputedStyle(document.getElementById('account-delete-open')).color,
          error: getComputedStyle(document.querySelector('.form-error')).color,
        };
      });
      assert.ok(gap >= 16, `Delete account is ${gap.toFixed(1)}px below the other actions`);
      assert.equal(color, error);
    });

    check('the life grid shows its labels whole', async (page) => {
      await openLink(page, `/#chart?${chartParams({ luck: '4/branch' })}`);
      await page.locator('#life-body .life-phase').first().waitFor({ state: 'visible' });
      await settled(page);
      const cut = await page.evaluate(() => [...document.querySelectorAll('#life *')]
        .filter((node) => node.checkVisibility() && !node.closest('.sr-only') && node.scrollWidth > node.clientWidth + 1
          && ['hidden', 'clip'].includes(getComputedStyle(node).overflowX))
        .map((node) => node.textContent.trim()));
      assert.deepEqual(cut, []);
    });

    check('the place fields: Settings\' label sits on its field\'s edge, and no hole follows a field', async (page) => {
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await keep(page);
      await page.goto(new URL('/#settings', process.env.EC_BASE_URL).href);
      await page.locator('#settings-location').waitFor({ state: 'visible' });
      await settled(page);
      const settings = await page.evaluate(() => {
        const box = (id) => document.getElementById(id).getBoundingClientRect();
        return { label: box('settings-location-label').left, field: box('settings-location').left, below: box('settings-place-save').top - box('settings-location').bottom };
      });
      assert.ok(Math.abs(settings.label - settings.field) <= 1, `label at ${settings.label}, field at ${settings.field}`);
      // The field's status, one line, between them.
      assert.ok(settings.below <= 44, `Save is ${settings.below.toFixed(1)}px below the field`);
      await startPage(page);
      const start = await page.evaluate(() => document.querySelector('.gender-group legend').getBoundingClientRect().top
        - document.getElementById('location').getBoundingClientRect().bottom);
      assert.ok(start <= 104, `Gender is ${start.toFixed(1)}px below the place`);
    });

    check('Saved charts closes from its bar, as Keys and Account do', async (page) => {
      await startPage(page);
      await openChart(page);
      await page.locator('#library-btn').click();
      await page.waitForFunction(() => document.getElementById('library-dialog').open);
      await settled(page);
      const close = page.locator('#library-dialog .chart-dialog-bar #library-close');
      assert.equal(await close.isVisible(), true);
      assert.equal(await page.locator('#library-dialog .chart-dialog-bar h2').textContent(), 'Saved charts');
      await close.click();
      await page.waitForFunction(() => !document.getElementById('library-dialog').open);
    });

    check('scrollbars take the page\'s lines', async (page) => {
      await startPage(page);
      await openChart(page);
      const supported = await page.evaluate(() => CSS.supports('scrollbar-color', 'red blue'));
      // WebKit draws its own scrollbars and has no scrollbar-color to give them.
      assert.equal(supported, engineName === 'chromium');
      if (!supported) return;
      for (const [scheme, line] of [['light', 'rgba(42, 37, 32, 0.3)'], ['dark', 'rgba(238, 231, 220, 0.34)']]) {
        await page.emulateMedia({ colorScheme: scheme });
        assert.equal(await page.evaluate(() => getComputedStyle(document.documentElement).scrollbarColor), `${line} rgba(0, 0, 0, 0)`);
      }
    });

    check('the Create button keeps its width while it works', async (page) => {
      await startPage(page);
      await page.locator('#date').fill(BIRTH.date);
      await page.locator('#time').fill(BIRTH.time);
      await pickPlace(page);
      await page.locator('.location-suggestion').click();
      await settled(page);
      const button = page.locator('#create-chart-btn');
      const before = (await button.boundingBox()).width;
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      await page.route('**/api/four_pillars', async (route) => { await held; await route.fallback(); });
      await button.click();
      await page.waitForFunction(() => document.getElementById('create-chart-btn').classList.contains('is-pending'));
      await settled(page);
      const during = (await button.boundingBox()).width;
      release();
      assert.ok(Math.abs(during - before) <= 0.5, `${before.toFixed(1)}px, then ${during.toFixed(1)}px while working`);
      await page.locator('#chart-view').waitFor({ state: 'visible' });
    });

    check('Settings\' pair form keeps each label with its list', async (page) => {
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await keep(page, {
        charts: [
          SAVED(LONG, '1985-11-02', '23:40', 'female'),
          SAVED('Mikael Johannes Lindqvist-Korhonen', '1990-07-21', '08:15', 'male'),
        ],
      });
      await page.goto(new URL('/#settings', process.env.EC_BASE_URL).href);
      await page.locator('#settings-pair-second').waitFor({ state: 'visible' });
      await settled(page);
      const pairs = await page.locator('#settings-view .settings-choose label').evaluateAll((labels) => labels.map((label) => {
        const own = label.getBoundingClientRect();
        const list = document.getElementById(label.htmlFor).getBoundingClientRect();
        const beside = Math.abs((own.top + own.bottom) / 2 - (list.top + list.bottom) / 2) <= 2 && own.right <= list.left;
        const above = own.bottom <= list.top + 0.5 && Math.abs(own.left - list.left) <= 1;
        return { label: label.textContent, beside, above };
      }));
      await keep(page);
      assert.ok(pairs.length >= 2);
      for (const pair of pairs) assert.ok(pair.beside || pair.above, `${pair.label} is apart from its list`);
    });

    check('no text is drawn off the type scale', async (page) => {
      const off = async (where) => (await renderedWords(page, 'body'))
        .filter((word) => Math.abs(word.scale - 1) < 0.001 && !SCALE.some((size) => Math.abs(size - word.size) < 0.3))
        .map((word) => `${where}: ${word.text} ${word.size.toFixed(2)}px`);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      const [mine, partner] = await keep(page, {
        charts: [
          SAVED('Aino', BIRTH.date, BIRTH.time, BIRTH.gender, { place: { ...PLACE, name: CHENGDU.display, city: CHENGDU.city, timezone: CHENGDU.timezone, latitude: CHENGDU.latitude, longitude: CHENGDU.longitude }, mine: true }),
          SAVED('Mikael', '1990-07-21', '08:15', 'male', { couple: 0 }),
        ],
      });
      assert.ok(mine && partner);
      const found = [];
      await page.goto(new URL(`/#today?${chartParams()}&day=${DAY}&partner=${partner}`, process.env.EC_BASE_URL).href);
      await openToday(page);
      await page.locator('#today-couple').waitFor({ state: 'visible' });
      found.push(...await off('Today'));
      await page.goto(new URL('/#settings', process.env.EC_BASE_URL).href);
      await page.locator('#settings-schools-body input[type="radio"]').first().waitFor({ state: 'visible' });
      await settled(page);
      found.push(...await off('Settings'));
      await openLink(page, `/#chart?${chartParams({ luck: '4/branch' })}`);
      await page.locator('#life-body .life-phase').first().waitFor({ state: 'visible' });
      await settled(page);
      found.push(...await off('the chart with its luck'));
      await keep(page);
      assert.deepEqual(found, []);
    });

    check('no control leads to the Evolution explorer, and it still opens at its address', async (page) => {
      await startPage(page);
      await openChart(page);
      assert.equal(await page.locator('#view-switch, [data-view="evolution"], a[href*="/explorer"]').count(), 0);
      await page.locator('.pillar-identity[data-pillar="hour"]').focus();
      await page.keyboard.press('ControlOrMeta+k');
      await page.waitForFunction(() => document.getElementById('command-palette').open);
      const commands = await page.locator('#palette-list [role="option"]').allTextContents();
      assert.ok(commands.length > 0);
      assert.deepEqual(commands.filter((command) => /evolution|evoluutio/i.test(command)), []);
      await page.keyboard.press('Escape');
      const address = new URLSearchParams({
        date: BIRTH.date, time: BIRTH.time, latitude: String(CHENGDU.latitude), longitude: String(CHENGDU.longitude),
        timezone: CHENGDU.timezone, lang: 'en',
      });
      const answered = page.waitForResponse((response) => response.url().endsWith('/api/evolution_explorer'));
      await page.goto(new URL(`/explorer/?${address}`, process.env.EC_BASE_URL).href);
      assert.equal((await answered).status(), 200);
      await page.waitForFunction(() => document.querySelectorAll('#graph circle').length > 0);
    });
  });
}
