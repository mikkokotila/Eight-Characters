// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Stage 3 of the Standard view (#18): one grid for the pillars, and room for what hangs below them.
import { assert, describe, it, engineName, profiles, openChart, settled, withPage } from './chart-helpers.mjs';

const WIDE = [641, 700, 800, 900, 1024, 1440];

// Top edge and height of every stem and branch card, and every pillar's name, by pillar.
async function rows(page) {
  return page.evaluate(() => {
    const box = (node) => {
      const rect = node.getBoundingClientRect();
      return { top: Math.round(rect.top * 10) / 10, height: Math.round(rect.height * 10) / 10 };
    };
    return [...document.querySelectorAll('.pillar')].map((pillar) => ({
      pillar: pillar.dataset.pillar,
      name: box(pillar.querySelector('.pillar-identity')).top,
      stem: box(pillar.querySelector('.card.stem')),
      branch: box(pillar.querySelector('.card.branch')),
    }));
  });
}

// Pillars that share a row of the grid must agree on every edge and height.
function misaligned(pillars, groups, state) {
  const failures = [];
  for (const group of groups) {
    const [first, ...rest] = group.map((name) => pillars.find((pillar) => pillar.pillar === name));
    for (const other of rest) {
      for (const key of ['name', 'stem', 'branch']) {
        if (JSON.stringify(other[key]) !== JSON.stringify(first[key])) {
          failures.push(`${state}: ${other.pillar} ${key} ${JSON.stringify(other[key])} vs ${first.pillar} ${JSON.stringify(first[key])}`);
        }
      }
    }
  }
  return failures;
}

async function turnAll(page) {
  await page.locator('#ten-gods-toggle').click();
  await settled(page);
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / design system`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 120000 }, () => withPage(profile, run));

    check('stem and branch rows share top edges and heights across the pillars, front and back', async (page) => {
      const failures = [];
      const widths = profile.name === 'desktop' ? WIDE : [profile.viewport.width];
      // Four pillars side by side above 640px; below it two rows of two.
      const groups = profile.name === 'desktop' ? [['hour', 'day', 'month', 'year']] : [['hour', 'day'], ['month', 'year']];
      for (const lang of ['en', 'fi']) {
        await openChart(page, { lang });
        for (const width of widths) {
          await page.setViewportSize({ width, height: profile.viewport.height });
          await settled(page);
          failures.push(...misaligned(await rows(page), groups, `${lang} ${width}px front`));
          await turnAll(page);
          failures.push(...misaligned(await rows(page), groups, `${lang} ${width}px back`));
          await turnAll(page);
        }
      }
      assert.deepEqual(failures, []);
    });

    check('a wrapped pillar label keeps the names level', async (page) => {
      // Finnish "SISÄINEN VUODENAIKA" wraps in a narrow column.
      await openChart(page, { lang: 'fi' });
      if (profile.name === 'desktop') await page.setViewportSize({ width: 700, height: profile.viewport.height });
      await settled(page);
      // Lines of each label: its text's line boxes, told apart by their tops.
      const lines = await page.locator('.pillar-label').evaluateAll((nodes) => nodes.map((node) => {
        const range = document.createRange();
        range.selectNodeContents(node);
        return new Set([...range.getClientRects()].map((rect) => Math.round(rect.top))).size;
      }));
      assert.ok(lines.some((count) => count > 1), `a label wraps: ${lines}`);
      const names = await rows(page);
      const groups = profile.name === 'desktop' ? [['hour', 'day', 'month', 'year']] : [['hour', 'day'], ['month', 'year']];
      assert.deepEqual(misaligned(names, groups, 'fi'), []);
    });

    check("the branch chevron clears its card's text", async (page) => {
      const failures = [];
      for (const lang of ['en', 'fi']) {
        await openChart(page, { lang });
        const widths = profile.name === 'desktop' ? [641, 1440] : [profile.viewport.width];
        for (const width of widths) {
          await page.setViewportSize({ width, height: profile.viewport.height });
          await settled(page);
          failures.push(...await page.evaluate((state) => [...document.querySelectorAll('.card.branch')].flatMap((card) => {
            const hint = card.querySelector('.card-front .branch-expand-hint').getBoundingClientRect();
            return [...card.querySelectorAll('.card-front .animal-name, .card-front .animal-element')]
              .filter((text) => {
                const box = text.getBoundingClientRect();
                return box.bottom > hint.top && box.top < hint.bottom && box.right > hint.left && box.left < hint.right;
              })
              .map((text) => `${state}: chevron overlaps ${text.className} on ${card.dataset.pillar}`);
          }), `${lang} ${width}px`));
        }
      }
      assert.deepEqual(failures, []);
    });

    check('the room kept below the pillars holds the tallest hidden-stem panel', async (page) => {
      await openChart(page, { lang: 'en' });
      for (const pillar of ['hour', 'day', 'month', 'year']) await page.locator(`.card.branch[data-pillar="${pillar}"]`).click();
      await settled(page);
      const layout = await page.evaluate(() => ({
        rows: Math.max(...[...document.querySelectorAll('.hidden-stems-panel.is-expanded')]
          .map((panel) => panel.querySelectorAll('.hidden-stem-item').length)),
        lowest: Math.max(...[...document.querySelectorAll('.hidden-stems-panel.is-expanded')]
          .map((panel) => panel.getBoundingClientRect().bottom)),
        back: document.querySelector('.back-row').getBoundingClientRect().top,
      }));
      // The canonical chart has branches with three hidden stems, the most any branch has.
      assert.equal(layout.rows, 3);
      assert.ok(layout.lowest <= layout.back, `panel ends at ${layout.lowest}, back row starts at ${layout.back}`);
    });
  });
}
