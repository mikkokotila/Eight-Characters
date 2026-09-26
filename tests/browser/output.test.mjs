// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Stage 5 of the Standard view (#20): the chart out of the page. Copy as text gives its
// pillars and a line with the birth, the true solar time and the convention; printing
// gives the chart, its precision line and the open topic. Both match the screen.
import {
  assert, describe, it, engineName, profiles, openChart, settled, openRelationships, withPage, HELSINKI,
} from './chart-helpers.mjs';

// The clipboard, kept in the page; a refusal can be asked for.
async function stubClipboard(page) {
  await page.addInitScript(() => {
    window.__copied = [];
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: async (text) => {
          if (window.__refuse) throw new DOMException('Write permission denied.', 'NotAllowedError');
          window.__copied.push(text);
        },
      },
    });
  });
}

// The pillars in written order, year to hour, from the API's own record.
const written = (payload) => ['year', 'month', 'day', 'hour']
  .map((name) => `${payload.four_pillars[name].stem.chinese}${payload.four_pillars[name].branch.chinese}`).join(' ');

// What the screen shows of the chart: its name, its true solar time (before the clock
// offset) and the convention the chart was read with.
async function onScreen(page) {
  return page.evaluate(() => ({
    heading: document.getElementById('chart-date').textContent,
    solar: document.getElementById('chart-solar-time').textContent.split(' · ')[0],
    zi: document.querySelector('#zi-switch button[aria-pressed="true"]')?.textContent ?? null,
  }));
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / output`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 60000 }, () => withPage(profile, run));

    check('Copy as text gives the pillars, the birth, the true solar time and the convention, as on screen', async (page) => {
      await stubClipboard(page);
      for (const lang of ['en', 'fi']) {
        const payload = await openChart(page, { lang });
        await page.locator('#copy-text-btn').click();
        await page.waitForFunction(() => document.querySelector('.toast').classList.contains('is-shown'));
        const [pillars, line] = (await page.evaluate(() => window.__copied.at(-1))).split('\n');
        assert.equal(pillars, written(payload));
        assert.equal(pillars, '丁卯 癸丑 己丑 壬申');
        const shown = await onScreen(page);
        // Outside the Zi hour the convention is the engine's default: the day changes at midnight.
        assert.equal(shown.zi, null);
        assert.equal(line, `${shown.heading} · ${shown.solar} · ${lang === 'en' ? 'Day changes at midnight' : 'Päivä vaihtuu keskiyöllä'}`);
        assert.equal(await page.locator('.toast').textContent(), lang === 'en' ? 'Text copied' : 'Teksti kopioitu');
      }
    });

    check('in the Zi hour the copied text follows the chosen convention and its pillars', async (page) => {
      await stubClipboard(page);
      await openChart(page, { lang: 'en', place: HELSINKI, date: '1988-06-15', time: '00:50' });
      const copy = async () => {
        const copied = await page.evaluate(() => window.__copied.length);
        await page.locator('#copy-text-btn').click();
        await page.waitForFunction((count) => window.__copied.length > count, copied);
        return page.evaluate(() => window.__copied.at(-1).split('\n'));
      };
      const cards = () => page.evaluate(() => ['year', 'month', 'day', 'hour'].map((name) =>
        `${document.querySelector(`.card.stem[data-pillar="${name}"]`).dataset.char}${document.querySelector(`.card.branch[data-pillar="${name}"]`).dataset.char}`).join(' '));
      const [before, beforeLine] = await copy();
      assert.equal(before, await cards());
      const first = await onScreen(page);
      assert.equal(beforeLine, `${first.heading} · ${first.solar} · ${first.zi}`);
      await page.locator('#zi-switch button[aria-pressed="false"]').click();
      await page.waitForFunction((zi) => document.querySelector('#zi-switch button[aria-pressed="true"]')?.textContent !== zi, first.zi);
      await settled(page);
      const [after, afterLine] = await copy();
      assert.equal(after, await cards());
      assert.notEqual(after, before, 'the other convention gives other pillars');
      const second = await onScreen(page);
      assert.equal(afterLine, `${second.heading} · ${second.solar} · ${second.zi}`);
    });

    check('a refused copy says so, and the palette offers Copy as text and Print', async (page) => {
      await stubClipboard(page);
      await openChart(page, { lang: 'en' });
      await page.evaluate(() => { window.__refuse = true; });
      await page.locator('#copy-text-btn').click();
      await page.waitForFunction(() => document.querySelector('.toast').textContent === 'Could not copy the text');
      assert.equal(await page.locator('.toast').evaluate((node) => node.classList.contains('is-error')), true);
      assert.deepEqual(await page.evaluate(() => window.__copied), []);
      await page.evaluate(() => { window.print = () => { window.__printed = true; }; });
      await page.keyboard.press('Control+k');
      const labels = await page.locator('#palette-list .palette-label').allTextContents();
      assert.ok(labels.includes('Copy as text') && labels.includes('Print'), labels.join(', '));
      await page.locator('#palette-input').fill('print');
      await page.keyboard.press('Enter');
      assert.equal(await page.evaluate(() => window.__printed), true);
    });

    check('printed, the chart keeps its cards, colours and precision line, loses its controls, and the open topic follows', async (page) => {
      await openChart(page, { lang: 'en' });
      await page.locator('button[data-context="roots"]').click();
      await settled(page);
      const colours = await page.locator('.card-front').evaluateAll((faces) => faces.map((face) => getComputedStyle(face).backgroundColor));
      await page.emulateMedia({ media: 'print' });
      await settled(page);
      const found = await page.evaluate(() => {
        const shows = (node) => node.checkVisibility();
        const box = (node) => node.getBoundingClientRect();
        const cards = [...document.querySelectorAll('#pillars .card')];
        const panel = document.getElementById('chart-panel');
        return {
          identity: shows(document.getElementById('chart-date')) && shows(document.getElementById('chart-solar-time')),
          cards: cards.filter(shows).length,
          controls: [...document.querySelectorAll('.chart-tools, .context-controls, #relationships-topic, .chart-panel-bar, .toast')]
            .filter(shows).map((node) => node.id || node.className),
          topic: shows(panel) && shows(document.getElementById('context-detail-title')),
          below: box(panel).top >= Math.max(...cards.map((card) => box(card).bottom)),
          wide: box(panel).width >= box(document.getElementById('pillars')).width - 1,
          position: getComputedStyle(panel).position,
          colours: [...document.querySelectorAll('.card-front')].map((face) => getComputedStyle(face).backgroundColor),
          exact: [...document.querySelectorAll('.card-face, .hidden-stem-dot')].every((node) =>
            ['exact'].includes(getComputedStyle(node).printColorAdjust ?? getComputedStyle(node).webkitPrintColorAdjust)),
        };
      });
      assert.equal(found.identity, true);
      assert.equal(found.cards, 8);
      assert.deepEqual(found.controls, []);
      assert.equal(found.topic, true);
      assert.equal(found.below, true, 'the topic follows the chart');
      assert.equal(found.wide, true, 'the topic takes the page width');
      assert.equal(found.position, 'static');
      assert.deepEqual(found.colours, colours);
      assert.equal(found.exact, true, 'element colours print as they are');
      // With no topic open, the chart prints alone.
      await page.emulateMedia({ media: 'screen' });
      await page.locator('[data-close-panel]').click();
      await page.emulateMedia({ media: 'print' });
      assert.equal(await page.locator('#chart-panel').isVisible(), false);
    });

    check('printed, each arc stands on its cards as on screen, and a Zi-hour chart shows its convention as text', async (page) => {
      if (profile.name === 'mobile') await page.setViewportSize({ width: 800, height: 1000 });
      const payload = await openChart(page, { date: '1990-01-08', time: '12:00' });
      await openRelationships(page);
      // Each arc against its own cards: its ends from the middles of its first and last
      // card, and its line from their edge (the stems' top, the branches' foot).
      const where = () => page.evaluate((relationships) => relationships.map((relationship) => {
        const order = ['hour', 'day', 'month', 'year'];
        const pillars = relationship.members.map((member) => member.pillar).sort((a, b) => order.indexOf(a) - order.indexOf(b));
        const card = (pillar) => document.querySelector(`.card.${relationship.component}[data-pillar="${pillar}"]`).getBoundingClientRect();
        const [first, last] = [card(pillars[0]), card(pillars.at(-1))];
        const arc = [...document.querySelectorAll('.relationship-arc')].find((node) => node.dataset.relationshipId === relationship.id);
        const line = arc.querySelector('.relationship-arc-line').getBoundingClientRect();
        const stem = relationship.component === 'stem';
        return [relationship.id,
          Math.round(line.left - (first.left + first.width / 2)), Math.round(line.right - (last.left + last.width / 2)),
          Math.round(stem ? first.top - line.bottom : line.top - first.bottom)];
      }), payload.interactions);
      const screen = await where();
      assert.ok(screen.length > 0);
      await page.emulateMedia({ media: 'print' });
      await settled(page);
      assert.deepEqual(await where(), screen);
      // Paged (a PDF), Chromium lays an absolutely placed grid item at the grid's start,
      // not in its area; emulated print is not paged, so the rows' layout is checked too:
      // on paper the arcs' rows are ordinary grid items over pillars in their own places.
      assert.deepEqual(await page.evaluate(() => ({
        bands: [...document.querySelectorAll('.relationship-arcs')].map((band) => getComputedStyle(band).position),
        pillars: [...document.querySelectorAll('.pillar')].map((pillar) => {
          const style = getComputedStyle(pillar);
          return `${style.gridRowStart}/${style.gridRowEnd} ${style.gridColumnStart}`;
        }),
      })), { bands: ['relative', 'relative'], pillars: ['1/span 8 1', '1/span 8 2', '1/span 8 3', '1/span 8 4'] });
      await page.emulateMedia({ media: 'screen' });
      await openChart(page, { lang: 'en', place: HELSINKI, date: '1988-06-15', time: '00:50' });
      await page.emulateMedia({ media: 'print' });
      const zi = await page.evaluate(() => [...document.querySelectorAll('#zi-switch button')]
        .filter((button) => button.checkVisibility()).map((button) => [button.textContent, button.getAttribute('aria-pressed')]));
      assert.deepEqual(zi, [[zi[0][0], 'true']]);
      assert.equal(await page.locator('#zi-switch-note').isVisible(), true);
    });
  });
}
