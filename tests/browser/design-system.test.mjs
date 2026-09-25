// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Stage 3 of the Standard view (#18): one grid for the pillars, and hidden stems in the flow below
// them (#19). Text on the cards fits them at every width.
import {
  assert, describe, it, engineName, profiles, openChart, settled, showDisplay, withPage,
} from './chart-helpers.mjs';

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

// Text on a card's facing side, or in an opened hidden-stem panel, that its box clips, or
// a word that breaks across two lines.
const FIT_AUDIT = () => {
  const problems = [];
  const boxes = [...document.querySelectorAll('#pillars .card')]
    .map((card) => card.querySelector(card.classList.contains('is-flipped') ? '.card-back' : '.card-front'));
  boxes.push(...document.querySelectorAll('#pillars .hidden-stems-panel.is-expanded'));
  for (const box of boxes) {
    const edges = box.getBoundingClientRect();
    const walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!node.textContent.trim() || !node.parentElement.getClientRects().length) continue;
      const text = document.createRange();
      text.selectNodeContents(node);
      if ([...text.getClientRects()].some((r) => r.width > 0 && (r.left < edges.left - 0.5 || r.right > edges.right + 0.5))) {
        problems.push(`clipped "${node.textContent.trim()}"`);
      }
      for (const match of node.textContent.matchAll(/\S+/g)) {
        const word = document.createRange();
        word.setStart(node, match.index);
        word.setEnd(node, match.index + match[0].length);
        if (new Set([...word.getClientRects()].filter((r) => r.width > 0).map((r) => Math.round(r.top))).size > 1) {
          problems.push(`broken "${match[0]}"`);
        }
      }
    }
  }
  return [...new Set(problems)];
};

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
          await showDisplay(page, 'ten-gods');
          failures.push(...misaligned(await rows(page), groups, `${lang} ${width}px back`));
          await showDisplay(page, 'characters');
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

    check('opened hidden stems share a row in the flow and cover nothing', async (page) => {
      await openChart(page, { lang: 'en' });
      await showDisplay(page, 'hidden-stems');
      const layout = await page.evaluate(() => {
        const panels = [...document.querySelectorAll('.hidden-stems-panel.is-expanded')];
        const boxOf = (node) => node.getBoundingClientRect();
        const overlaps = panels.flatMap((panel) => [...document.querySelectorAll('#pillars .pillar-header, #pillars .card')]
          .filter((node) => {
            const a = boxOf(panel);
            const b = boxOf(node);
            return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
          })
          .map((node) => `the ${panel.dataset.pillar} panel covers ${node.className} of ${node.closest('.pillar').dataset.pillar}`));
        return {
          rows: Math.max(...panels.map((panel) => panel.querySelectorAll('.hidden-stem-item').length)),
          tops: Object.fromEntries(panels.map((panel) => [panel.dataset.pillar, Math.round(boxOf(panel).top * 10) / 10])),
          lowest: Math.max(...panels.map((panel) => boxOf(panel).bottom)),
          end: boxOf(document.getElementById('pillars')).bottom,
          overlaps,
        };
      });
      // The canonical chart has branches with three hidden stems, the most any branch has.
      assert.equal(layout.rows, 3);
      assert.deepEqual(layout.overlaps, []);
      assert.ok(layout.lowest <= layout.end, `a panel ends at ${layout.lowest}, below the pillars' end at ${layout.end}`);
      const groups = profile.name === 'desktop' ? [['hour', 'day', 'month', 'year']] : [['hour', 'day'], ['month', 'year']];
      for (const group of groups) {
        assert.equal(new Set(group.map((pillar) => layout.tops[pillar])).size, 1, JSON.stringify(layout.tops));
      }
    });

    check('text on the cards and in their hidden stems is never clipped or broken inside a word', async (page) => {
      // Motion off: the text is measured, not the turn.
      await page.emulateMedia({ reducedMotion: 'reduce' });
      const widths = profile.name === 'desktop' ? [641, 700, 900, 1024, 1200, 1440] : [320, 360, profile.viewport.width];
      const failures = [];
      for (const lang of ['en', 'fi']) {
        // The longest words: Lohikäärme and Hevonen among the animals, Ruokajumala among the Ten Gods.
        for (const [date, time] of [['2000-06-15', '08:00'], ['1985-05-20', '10:10']]) {
          await openChart(page, { lang, date, time });
          for (const width of widths) {
            await page.setViewportSize({ width, height: profile.viewport.height });
            for (const mode of ['characters', 'ten-gods', 'hidden-stems']) {
              await showDisplay(page, mode);
              failures.push(...(await page.evaluate(FIT_AUDIT)).map((problem) => `${lang} ${date} ${width}px ${mode}: ${problem}`));
            }
          }
        }
      }
      assert.deepEqual(failures, []);
    });
  });
}
