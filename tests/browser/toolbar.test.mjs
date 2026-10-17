// Run with Node's built-in test runner and an explicitly selected Playwright install.
// The toolbar's two ways (docs/Standard-Toolbar.md, toolbar.js). In words, the default,
// every switch says what it does, the topics say their names, and the chart's and the
// day's actions gather in one menu, Actions; in icons, which Settings chooses for this
// browser, the bar is the icons it was (controls.test.mjs reads them).
import {
  assert, describe, it, engineName, profiles, openLink, settled, withPage, press, HELSINKI,
} from './chart-helpers.mjs';

const BIRTH = {
  date: '1975-08-14', time: '07:45', place: HELSINKI.display, city: HELSINKI.city,
  latitude: String(HELSINKI.latitude), longitude: String(HELSINKI.longitude), timezone: HELSINKI.timezone,
  lang: 'en', gender: 'female',
};
const chartLink = (parts = {}) => `/#chart?${new URLSearchParams({ ...BIRTH, ...parts })}`;
const PLACE = {
  name: HELSINKI.display, city: HELSINKI.city, timezone: HELSINKI.timezone,
  latitude: HELSINKI.latitude, longitude: HELSINKI.longitude,
};
const way = (page) => page.evaluate(() => document.documentElement.dataset.toolbar);
const focused = (page) => page.evaluate(() => document.activeElement.id || document.activeElement.className);
// What a control shows: its words, read from what is drawn (a label clipped away for a
// screen reader is not), with its count after them; and whether its icon shows.
function seen(node) {
  const clipped = (element) => {
    const label = element.closest('.sr-only');
    return label !== null && getComputedStyle(label).position === 'absolute';
  };
  const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
  const words = [];
  while (walker.nextNode()) {
    const parent = walker.currentNode.parentElement;
    if (parent.checkVisibility() && !clipped(parent)) words.push(walker.currentNode.textContent);
  }
  const caption = node.querySelector(':scope > .control-caption');
  if (caption?.checkVisibility()) words.push(` ${caption.dataset.caption}`);
  return [words.join('').replace(/\s+/g, ' ').trim(), node.querySelector('[data-control-icon]')?.checkVisibility() ?? false];
}
const shown = (page, selector) => page.locator(selector).evaluateAll((nodes, source) => {
  const read = new Function(`return ${source}`)();
  return nodes.map(read);
}, seen.toString());
// The chart's menu: its button's state, its role, and its items' roles.
const menu = (page) => page.evaluate(() => {
  const list = document.getElementById('chart-actions');
  return {
    expanded: document.getElementById('chart-actions-button').getAttribute('aria-expanded'),
    open: list.classList.contains('is-open'),
    role: list.getAttribute('role'),
    items: [...list.querySelectorAll(':scope > button')].map((item) => `${item.getAttribute('role')} ${item.id}`),
    rules: [...list.querySelectorAll(':scope > .bar-menu-rule')].map((rule) => rule.getAttribute('role')),
  };
});
const ITEMS = ['copy-link-btn', 'copy-text-btn', 'back-btn', 'new-chart-btn', 'compare-btn'];
// Where you are, kept for the account as Settings keeps it, so that Today draws a day.
async function keepPlace(page) {
  const status = await page.evaluate(async (place) => {
    const read = await (await fetch('/api/account/settings')).json();
    const reply = await fetch('/api/account/place', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ place, key: read.key, updated_at: read.updated_at }),
    });
    return reply.status;
  }, PLACE);
  assert.equal(status, 200);
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / toolbar`, { concurrency: false }, () => {
    const check = (name, run, options) => it(name, { timeout: 120000 }, () => withPage(profile, run, options));

    check('in words, the default, every switch says what it does, the topics their names, and the actions are one menu', async (page) => {
      await openLink(page, chartLink(), { place: HELSINKI });
      assert.equal(await way(page), 'words');
      assert.deepEqual(await shown(page, '#page-switch button'), [['Chart', false], ['Today', false]]);
      assert.deepEqual(await shown(page, '#display-switch button'), [['Characters', false], ['Ten Gods', false], ['Hidden stems', false]]);
      assert.deepEqual(await shown(page, '#luck-switch button'), [['Natal', false], ['With luck', false]]);
      // A topic: its icon, its name and its count; its full name for a screen reader.
      assert.deepEqual(await shown(page, '#relationships-topic'), [['Relationships 3', true]]);
      assert.equal(await page.locator('#relationships-topic .control-label').textContent(), 'Relationships (3)');
      assert.deepEqual(await shown(page, '[data-context="roles"]'), [['Roles', true]]);
      // The actions: one button, its menu closed and out of sight.
      assert.deepEqual(await shown(page, '#chart-actions-button'), [['Actions', false]]);
      assert.equal(await page.locator('#chart-actions-button').getAttribute('aria-haspopup'), 'menu');
      assert.deepEqual(await menu(page), {
        expanded: 'false', open: false, role: 'menu', items: ITEMS.map((id) => `menuitem ${id}`), rules: ['separator'],
      });
      assert.equal(await page.locator('#copy-link-btn').isVisible(), false);
      // Each item: its icon and its words, and no tooltip over it.
      await page.locator('#chart-actions-button').click();
      assert.deepEqual(await shown(page, '#chart-actions > button'),
        [['Copy link', true], ['Copy as text', true], ['Edit', true], ['New chart', true], ['Compare', true]]);
      await page.locator('#copy-text-btn').hover();
      await page.waitForTimeout(700);
      assert.equal(await page.locator('#control-tooltip').evaluate((tip) => tip.matches(':popover-open')), false);
      // Nothing in the bar runs past the page's edge.
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    });

    check('the menu takes the keys a menu takes, and the page\'s own keys rest while it is open', async (page) => {
      await openLink(page, chartLink(), { place: HELSINKI });
      const button = page.locator('#chart-actions-button');
      // Enter opens it at its first item, and Escape closes it back to its button.
      await button.focus();
      await page.keyboard.press('Enter');
      assert.equal((await menu(page)).expanded, 'true');
      assert.equal(await focused(page), 'copy-link-btn');
      await page.keyboard.press('Escape');
      assert.deepEqual([(await menu(page)).expanded, (await menu(page)).open, await focused(page)], ['false', false, 'chart-actions-button']);
      // Down opens it at its first item and Up at its last; the arrows move round it, and
      // Home and End go to its ends.
      await page.keyboard.press('ArrowUp');
      assert.equal(await focused(page), 'compare-btn');
      await page.keyboard.press('ArrowDown');
      assert.equal(await focused(page), 'copy-link-btn');
      await page.keyboard.press('ArrowUp');
      assert.equal(await focused(page), 'compare-btn');
      await page.keyboard.press('Home');
      assert.equal(await focused(page), 'copy-link-btn');
      await page.keyboard.press('End');
      assert.equal(await focused(page), 'compare-btn');
      await page.keyboard.press('Escape');
      await page.keyboard.press('ArrowDown');
      assert.equal(await focused(page), 'copy-link-btn');
      // The page's keys (] steps the luck pillar, ? lists the keys) do nothing in it.
      await page.keyboard.press('?');
      assert.equal(await page.locator('#keys-dialog').isVisible(), false);
      assert.equal((await menu(page)).open, true);
      // Tab leaves it, and closes it.
      await page.keyboard.press('Tab');
      assert.deepEqual([(await menu(page)).expanded, (await menu(page)).open], ['false', false]);
      // A press outside closes it, and leaves the focus where it was pressed.
      await button.click();
      assert.equal((await menu(page)).open, true);
      await page.locator('#day-master-context h2').click();
      assert.deepEqual([(await menu(page)).expanded, (await menu(page)).open], ['false', false]);
    });

    check('an item chosen does what its button does, and the menu closes, giving its button the focus', async (page) => {
      await page.addInitScript(() => {
        window.__copied = [];
        Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async (text) => { window.__copied.push(text); } } });
      });
      await openLink(page, chartLink(), { place: HELSINKI });
      await press(page, '#copy-link-btn');
      await page.waitForFunction(() => window.__copied.length === 1);
      assert.equal(await page.evaluate(() => window.__copied[0]), page.url());
      assert.deepEqual([(await menu(page)).expanded, (await menu(page)).open], ['false', false]);
      assert.equal(await focused(page), 'chart-actions-button');
      // One that leaves the chart takes the focus with it: New chart opens the form.
      await press(page, '#new-chart-btn');
      await page.locator('#input-view').waitFor({ state: 'visible' });
      assert.equal((await menu(page)).open, false);
    });

    check('the day\'s actions are its menu too: Copy as text waits there until the day is drawn, and Settings is one', async (page) => {
      await page.addInitScript(() => {
        window.__copied = [];
        Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async (text) => { window.__copied.push(text); } } });
      });
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await keepPlace(page);
      await page.goto(new URL(`/#today?${new URLSearchParams(BIRTH)}&day=2026-10-11`, process.env.EC_BASE_URL).href);
      await page.locator('#today-body').waitFor({ state: 'visible' });
      await settled(page);
      assert.deepEqual(await shown(page, '#today-page-switch button'), [['Chart', false], ['Today', false]]);
      await page.locator('#today-actions-button').click();
      assert.deepEqual(await shown(page, '#today-actions > button'), [['Copy link', true], ['Copy as text', true], ['Print', true], ['Settings', true]]);
      assert.deepEqual(await page.locator('#today-actions > button').evaluateAll((items) => items.map((item) => item.getAttribute('role'))),
        ['menuitem', 'menuitem', 'menuitem', 'menuitem']);
      await page.keyboard.press('Escape');
      await press(page, '#today-copy-text');
      await page.waitForFunction(() => window.__copied.length === 1);
      assert.match(await page.evaluate(() => window.__copied[0]), /2026/);
      assert.equal(await page.locator('#today-actions').isVisible(), false);
      await press(page, '#today-settings');
      await page.locator('#settings-view').waitFor({ state: 'visible' });
    });

    check('Settings chooses icons for this browser, at once and after a reload, and words again', async (page) => {
      await page.goto(new URL('/#settings', process.env.EC_BASE_URL).href);
      await page.locator('#settings-toolbar').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#settings-toolbar-words').isChecked(), true);
      assert.equal(await page.locator('#settings-toolbar-icons').isChecked(), false);
      assert.equal(await page.locator('#settings-toolbar label[for="settings-toolbar-words"]').innerText(), 'Words (default)');
      await page.locator('#settings-toolbar-icons').check();
      assert.equal(await way(page), 'icons');
      assert.equal(await page.evaluate(() => localStorage.getItem('eight_characters_toolbar')), 'icons');
      // The bar is its icons: the switches and the actions, each a button in the bar,
      // and no menu.
      await openLink(page, chartLink(), { place: HELSINKI });
      assert.equal(await way(page), 'icons');
      assert.deepEqual(await shown(page, '#display-switch button'), [['', true], ['', true], ['', true]]);
      assert.equal(await page.locator('#chart-actions-button').isHidden(), true);
      assert.deepEqual(await menu(page), {
        expanded: 'false', open: false, role: null, items: ITEMS.map((id) => `null ${id}`), rules: [null],
      });
      assert.deepEqual(await shown(page, '#chart-actions > button'), ITEMS.map(() => ['', true]));
      assert.equal(await page.locator('#copy-link-btn').isVisible(), true);
      assert.equal(await page.locator('#copy-link-btn').getAttribute('tabindex'), null);
      // Words again: the menu, and the switches' words.
      await page.goto(new URL('/#settings', process.env.EC_BASE_URL).href);
      await page.locator('#settings-toolbar').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#settings-toolbar-icons').isChecked(), true);
      await page.locator('#settings-toolbar-words').check();
      await openLink(page, chartLink(), { place: HELSINKI });
      assert.equal(await way(page), 'words');
      assert.equal((await menu(page)).role, 'menu');
      assert.deepEqual(await shown(page, '#display-switch button'), [['Characters', false], ['Ten Gods', false], ['Hidden stems', false]]);
    });

    check('another page of this browser follows the toolbar chosen in one', async (page) => {
      await openLink(page, chartLink(), { place: HELSINKI });
      // Another page of the same site, as another tab is: a frame of the start page.
      await page.evaluate(() => new Promise((resolve) => {
        const frame = document.createElement('iframe');
        frame.id = 'other-page';
        frame.src = '/';
        frame.addEventListener('load', resolve, { once: true });
        document.body.append(frame);
      }));
      const other = () => page.evaluate(() => document.getElementById('other-page').contentDocument.documentElement.dataset.toolbar);
      assert.equal(await other(), 'words');
      await page.evaluate(() => window.EC_TOOLBAR.choose('icons'));
      await page.waitForFunction(() => document.getElementById('other-page').contentDocument.documentElement.dataset.toolbar === 'icons');
      await page.evaluate(() => window.EC_TOOLBAR.choose('words'));
      await page.waitForFunction(() => document.getElementById('other-page').contentDocument.documentElement.dataset.toolbar === 'words');
      assert.equal(await other(), 'words');
    });

    for (const toolbar of ['words', 'icons']) {
      check(`a comparison's frames keep Copy as text in their bar, and no menu (${toolbar})`, async (page) => {
        const second = { ...BIRTH, date: '1979-03-21', time: '06:10', gender: 'male' };
        await page.goto(new URL(`/#compare?${new URLSearchParams({ a: new URLSearchParams(BIRTH).toString(), b: new URLSearchParams(second).toString() })}`,
          process.env.EC_BASE_URL).href);
        const frame = page.frameLocator('#compare-charts .compare-frame[data-side="a"]');
        await frame.locator('#pillars .card').first().waitFor();
        assert.equal(await frame.locator('#copy-text-btn').isVisible(), true);
        assert.equal(await frame.locator('#chart-actions-button').isVisible(), false);
        assert.equal(await frame.locator('#chart-actions').getAttribute('role'), null);
        assert.equal(await frame.locator('#copy-text-btn').getAttribute('role'), null);
        for (const hidden of ['#copy-link-btn', '#back-btn', '#new-chart-btn', '#compare-btn']) {
          assert.equal(await frame.locator(hidden).isVisible(), false, hidden);
        }
        // In the frame's order: the display, the luck pillar, then Copy as text.
        const places = await frame.locator('#display-switch, #luck-switch, #copy-text-btn').evaluateAll((nodes) => nodes.map((node) => {
          const box = node.getBoundingClientRect();
          return [Math.round(box.top), Math.round(box.left)];
        }));
        assert.ok(places[0][0] <= places[1][0] && places[1][0] <= places[2][0], JSON.stringify(places));
        assert.ok(places[1][0] < places[2][0] || places[1][1] < places[2][1], JSON.stringify(places));
        // The comparison's own actions: in words, an icon and words each.
        assert.deepEqual(await shown(page, '#compare-swap, #compare-copy-link, #compare-close'),
          toolbar === 'words' ? [['Swap sides', true], ['Copy link', true], ['Close comparison', true]] : [['', true], ['', true], ['', true]]);
      }, { toolbar });
    }

    if (profile.name === 'mobile') {
      check('on a phone, in words, the bar is three lines: the page and Actions, the display, the luck pillar and the language', async (page) => {
        await openLink(page, chartLink(), { place: HELSINKI });
        const lines = await page.evaluate(() => {
          const tops = new Map();
          for (const part of document.querySelectorAll('#chart-view .chart-tools > *')) {
            if (!part.checkVisibility()) continue;
            const top = Math.round(part.getBoundingClientRect().top);
            tops.set(top, [...(tops.get(top) ?? []), part.id || part.className]);
          }
          return [...tops.entries()].sort((a, b) => a[0] - b[0]).map(([, parts]) => parts);
        });
        assert.deepEqual(lines, [['page-switch', 'bar-menu'], ['display-switch'], ['luck-switch', 'chart-language']]);
        for (const width of [390, 320]) {
          await page.setViewportSize({ width, height: 844 });
          await settled(page);
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, `${width}px`);
        }
      });
    }
  });
}
