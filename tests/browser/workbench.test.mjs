// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Stage 4 of the Standard view (#19): the chart as a workbench. One bar above it, and a panel
// that explains the chosen topic beside it (a sheet over the foot of the page below 1200px).
import {
  assert, describe, it, engineName, profiles, openChart, count, settled, showDisplay, openRelationships, withPage,
} from './chart-helpers.mjs';

// Where the pillars stand on the page, to a tenth of a pixel.
async function placement(page) {
  return page.locator('.pillar').evaluateAll((pillars) => pillars.map((pillar) => {
    const r = pillar.getBoundingClientRect();
    const tenth = (value) => Math.round(value * 10) / 10;
    return { x: tenth(r.x + scrollX), y: tenth(r.y + scrollY), width: tenth(r.width), height: tenth(r.height) };
  }));
}

// Each topic as a reader opens it, from a closed panel.
const TOPICS = {
  season: (page) => page.locator('button[data-context="season"]').click(),
  roots: (page) => page.locator('button[data-context="roots"]').click(),
  'a role': async (page) => {
    await page.locator('button[data-context="roles"]').click();
    await page.locator('[data-role="direct_wealth"]').click();
  },
  "a stem's roots": async (page) => {
    await page.locator('button[data-context="roles"]').click();
    await page.locator('.role-stem-entry button[data-root-pillar="year"]').click();
  },
  'a relationship': async (page) => {
    await openRelationships(page);
    await page.locator('.relationship-chip').first().click();
  },
};

async function fields(page) {
  return page.evaluate(() => Object.fromEntries(['date', 'time', 'location']
    .map((id) => [id, document.getElementById(id).value])));
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / workbench`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 60000 }, () => withPage(profile, run));

    if (profile.name === 'desktop') {
      it('at 1440×900 a topic shows its highlighted cards and its explanation together, without scrolling', {
        timeout: 60000,
      }, () => withPage({ ...profile, viewport: { width: 1440, height: 900 } }, async (page) => {
        await openChart(page);
        const failures = [];
        for (const [name, open] of Object.entries(TOPICS)) {
          await open(page);
          await settled(page);
          failures.push(...await page.evaluate((name) => {
            const problems = [];
            if (scrollY !== 0) problems.push(`${name}: the page scrolled by ${scrollY}px`);
            const onScreen = (r) => r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth;
            const panel = document.getElementById('chart-panel').getBoundingClientRect();
            const cards = [...document.querySelectorAll('.card.is-related, .card.is-context-source, .card.is-context-reference')];
            if (!cards.length) problems.push(`${name}: nothing is highlighted`);
            for (const card of cards) {
              const r = card.getBoundingClientRect();
              if (!onScreen(r)) problems.push(`${name}: the ${card.dataset.pillar} card is off screen`);
              if (r.right > panel.left) problems.push(`${name}: the panel covers the ${card.dataset.pillar} card`);
            }
            const detail = [...document.querySelectorAll('#context-detail, #relationship-detail, #pillar-detail')]
              .find((section) => section.checkVisibility());
            const heading = detail?.querySelector('h3');
            if (!heading || !onScreen(heading.getBoundingClientRect())) problems.push(`${name}: its explanation is off screen`);
            return problems;
          }, name));
          await page.locator('[data-close-panel]').click();
          assert.equal(await page.locator('#chart-panel').isVisible(), false);
        }
        assert.deepEqual(failures, []);
      }));
    }

    check('the chart moves over once when the panel first opens, and back when it closes', async (page) => {
      await openChart(page);
      const centred = await placement(page);
      await page.locator('button[data-context="season"]').click();
      const beside = await placement(page);
      if (profile.name === 'desktop') {
        // Beside the panel, and as wide as before.
        const shift = beside[0].x - centred[0].x;
        assert.ok(shift < 0, `the chart moves left: ${shift}px`);
        assert.deepEqual(beside, centred.map((box) => ({ ...box, x: Math.round((box.x + shift) * 10) / 10 })));
      } else {
        // The sheet lies over the page: nothing under it moves.
        assert.deepEqual(beside, centred);
      }
      const steps = {
        roots: () => page.locator('button[data-context="roots"]').click(),
        roles: () => page.locator('button[data-context="roles"]').click(),
        relationships: () => openRelationships(page),
        'a relationship': () => page.locator('.relationship-chip').first().click(),
        "the year's changes": () => page.locator('.pillar-identity[data-pillar="year"]').click(),
      };
      for (const [name, step] of Object.entries(steps)) {
        await step();
        assert.deepEqual(await placement(page), beside, name);
      }
      await page.locator('[data-close-panel]').click();
      assert.equal(await page.locator('#chart-panel').isVisible(), false);
      assert.deepEqual(await placement(page), centred);
    });

    check('below 1200px the panel is a sheet over the foot of the page, and the chart scrolls clear of it', async (page) => {
      if (profile.name === 'desktop') await page.setViewportSize({ width: 900, height: 900 });
      await openChart(page);
      await page.locator('button[data-context="roots"]').click();
      const viewport = page.viewportSize();
      const sheet = await page.locator('#chart-panel').evaluate((panel) => {
        const r = panel.getBoundingClientRect();
        return { position: getComputedStyle(panel).position, bottom: r.bottom, width: r.width, height: r.height };
      });
      assert.equal(sheet.position, 'fixed');
      assert.equal(sheet.bottom, viewport.height);
      assert.equal(sheet.width, viewport.width);
      assert.ok(sheet.height <= viewport.height / 2 + 0.5, `the sheet is ${sheet.height}px tall`);
      // Scrolled to its end, the page shows its lowest card above the sheet.
      const end = await page.evaluate(() => {
        scrollTo(0, document.documentElement.scrollHeight);
        return {
          lowest: Math.max(...[...document.querySelectorAll('#pillars .card')].map((card) => card.getBoundingClientRect().bottom)),
          sheet: document.getElementById('chart-panel').getBoundingClientRect().top,
        };
      });
      assert.ok(end.lowest <= end.sheet, `the lowest card ends at ${end.lowest}, the sheet starts at ${end.sheet}`);
    });

    check('the display switch shows characters, Ten Gods or hidden stems on every card', async (page) => {
      await openChart(page);
      const shown = () => page.evaluate(() => ({
        turned: document.querySelectorAll('#pillars .card.is-flipped').length,
        open: document.querySelectorAll('#pillars .hidden-stems-panel.is-expanded').length,
      }));
      await showDisplay(page, 'ten-gods');
      assert.deepEqual(await shown(), { turned: 8, open: 0 });
      await showDisplay(page, 'hidden-stems');
      assert.deepEqual(await shown(), { turned: 0, open: 4 });
      await showDisplay(page, 'characters');
      assert.deepEqual(await shown(), { turned: 0, open: 0 });
    });

    check('a card turns after half a second held', async (page) => {
      await openChart(page);
      const card = page.locator('.card.stem[data-pillar="day"]');
      await card.scrollIntoViewIfNeeded();
      await card.evaluate((node) => {
        window.__press = {};
        node.addEventListener('pointerdown', () => { window.__press.down = performance.now(); }, { once: true });
        new MutationObserver((records, observer) => {
          if (!node.classList.contains('is-flipped')) return;
          window.__press.turned = performance.now();
          observer.disconnect();
        }).observe(node, { attributes: true, attributeFilter: ['class'] });
      });
      const box = await card.boundingBox();
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down();
      await page.waitForFunction(() => window.__press.turned);
      await page.mouse.up();
      const held = await page.evaluate(() => window.__press.turned - window.__press.down);
      // Not before half a second, and well before the second it used to take.
      assert.ok(held >= 495 && held < 900, `turned after ${held} ms`);
    });

    if (profile.name === 'desktop') {
      check('the mouse finds a hint that a card turns when held, right above the card', async (page) => {
        // Short enough to scroll: the hint must follow the card on screen.
        await page.setViewportSize({ width: 1440, height: 600 });
        await openChart(page);
        await page.evaluate(() => scrollTo(0, 200));
        const card = page.locator('.card.stem[data-pillar="day"]');
        await card.hover();
        const hint = page.locator('.card-hint');
        await hint.waitFor({ state: 'visible' });
        assert.equal(await hint.textContent(), 'Press and hold: Ten Gods');
        const placed = () => page.evaluate(() => {
          const h = document.querySelector('.card-hint').getBoundingClientRect();
          const c = document.querySelector('.card.stem[data-pillar="day"]').getBoundingClientRect();
          return { above: h.bottom <= c.top && h.top >= 0, centred: Math.abs((h.left + h.right) / 2 - (c.left + c.right) / 2) < 1 };
        });
        assert.deepEqual(await placed(), { above: true, centred: true });
        assert.equal(await hint.getAttribute('aria-hidden'), 'true');
        // Scrolled a little, the card stays under the mouse and the hint follows it.
        const top = await card.evaluate((node) => node.getBoundingClientRect().top);
        await page.mouse.wheel(0, 40);
        await page.waitForFunction((top) => document.querySelector('.card.stem[data-pillar="day"]').getBoundingClientRect().top < top - 30, top);
        await page.waitForFunction(() => document.querySelector('.card-hint').getBoundingClientRect().bottom
          <= document.querySelector('.card.stem[data-pillar="day"]').getBoundingClientRect().top);
        assert.equal(await hint.isVisible(), true);
        assert.deepEqual(await placed(), { above: true, centred: true });
        await page.mouse.down();
        await hint.waitFor({ state: 'hidden' });
        await page.mouse.up();
        await settled(page);
        await page.mouse.move(2, 2);
        await hint.waitFor({ state: 'hidden' });
      });
    }

    check('the chart asks for itself again in the other language, and keeps how it is shown', async (page) => {
      await openChart(page, { lang: 'en' });
      await showDisplay(page, 'ten-gods');
      const request = page.waitForRequest('**/api/four_pillars');
      await page.locator('#chart-language button[data-chart-lang="fi"]').click();
      assert.equal((await request).postDataJSON().lang, 'fi');
      await page.waitForFunction(() => document.getElementById('chart-date').textContent === '4. helmikuuta 1988 · 16.30 · Chengdu');
      await settled(page);
      const finnish = page.locator('#chart-language button[data-chart-lang="fi"]');
      assert.equal(await finnish.getAttribute('aria-pressed'), 'true');
      assert.equal(await finnish.evaluate((button) => button === document.activeElement), true);
      assert.equal(await page.locator('#display-switch button[data-display="ten-gods"]').getAttribute('aria-pressed'), 'true');
      await count(page, '.card.is-flipped', 8);
      assert.equal(await page.locator('.card.stem[data-pillar="year"] .ten-god-name').textContent(), 'Epäsuora voimavara');
      // Back at the form, the page speaks Finnish too.
      await page.locator('#back-btn').click();
      assert.equal(await page.locator('#create-chart-btn').textContent(), 'Luo kartta');
    });

    check('while the chart is asked for again it takes no other clicks', async (page) => {
      await openChart(page, { lang: 'en' });
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      const langs = [];
      // Held until the other clicks are made, then handed on to the real API.
      await page.route('**/api/four_pillars', async (route) => {
        langs.push(route.request().postDataJSON().lang);
        await held;
        await route.fallback();
      });
      await page.locator('#chart-language button[data-chart-lang="fi"]').click();
      await page.waitForFunction(() => document.getElementById('chart-view').getAttribute('aria-busy') === 'true');
      for (const control of ['#chart-language button[data-chart-lang="en"]', '#back-btn', '#new-chart-btn']) {
        await page.locator(control).click();
      }
      release();
      await page.waitForFunction(() => !document.getElementById('chart-view').hasAttribute('aria-busy'));
      assert.deepEqual(langs, ['fi']);
      assert.equal(await page.locator('#chart-view').isVisible(), true);
      assert.equal(await page.locator('#input-view').isVisible(), false);
      assert.equal(await page.locator('#chart-date').textContent(), '4. helmikuuta 1988 · 16.30 · Chengdu');
      assert.equal(await page.locator('#chart-language button[data-chart-lang="fi"]').getAttribute('aria-pressed'), 'true');
      assert.equal(await page.locator('[data-context="roots"]').textContent(), 'Juuria 3 haarassa');
    });

    check('Edit keeps the birth for another chart; New chart starts from an empty form', async (page) => {
      await openChart(page, { lang: 'en' });
      assert.equal(await page.locator('#back-btn').textContent(), 'Edit');
      await page.locator('#back-btn').click();
      assert.deepEqual(await fields(page), { date: '1988-02-04', time: '16:30', location: 'Chengdu, Sichuan, China' });
      await page.locator('#create-chart-btn').click();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await page.locator('[data-context="roots"]').click();
      await page.locator('#new-chart-btn').click();
      assert.deepEqual(await fields(page), { date: '', time: '', location: '' });
      assert.equal(await page.evaluate(() => document.activeElement.id), 'date');
      assert.equal(await page.locator('#location-status').textContent(), '');
      assert.equal(await page.locator('#create-chart-btn').isDisabled(), true);
      assert.equal(await page.title(), 'BaZi — Four pillars');
      assert.equal(await page.locator('#chart-view').isVisible(), false);
    });

    check('column headers pair the plain pillar name with its poetic one; the panel uses the plain names in chart order', async (page) => {
      const names = {
        en: { plain: ['Hour', 'Day', 'Month', 'Year'], poetic: ['Action gate', 'Inner light', 'Inner season', 'Life field'] },
        fi: { plain: ['Tunti', 'Päivä', 'Kuukausi', 'Vuosi'], poetic: ['Teon portti', 'Sisäinen valo', 'Sisäinen vuodenaika', 'Elämän kenttä'] },
      };
      for (const [lang, { plain, poetic }] of Object.entries(names)) {
        await openChart(page, { lang });
        assert.deepEqual(await page.locator('.pillar-plain').allTextContents(), plain);
        assert.equal(await page.locator('.pillar-plain').first().evaluate((node) => getComputedStyle(node).textTransform), 'uppercase');
        assert.deepEqual(await page.locator('.pillar-poetic').allTextContents(), poetic);
        await openRelationships(page);
        // The chart's only relationship joins its hour and year stems.
        const pair = `${plain[0]}–${plain[3]}`;
        assert.match((await page.locator('.relationship-chip').textContent()).trim(), new RegExp(`^${pair} · `));
        await page.locator('.relationship-chip').click();
        assert.match(await page.locator('#relationship-detail h3').textContent(), new RegExp(`^${pair} · `));
        assert.deepEqual(await page.locator('#relationship-detail .relationship-member > .relationship-position').allTextContents(),
          [plain[0], plain[3]]);
        await page.locator('[data-context="roots"]').click();
        assert.deepEqual(await page.locator('#context-detail .relationship-member > .relationship-position').allTextContents(),
          plain.slice(0, 3));
        await page.locator('.pillar-identity[data-pillar="year"]').click();
        assert.equal(await page.locator('#pillar-detail h3').textContent(), `${plain[3]} · 丁卯 Ding Mao`);
      }
    });
  });
}
