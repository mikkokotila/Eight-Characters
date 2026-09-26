// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Stage 5 of the Standard view (#20): the dark theme. The system's setting chooses it; its
// colours are the embers palette; paper keeps the day's colours. Its contrast in every
// state is checked with the day's, in foundations.test.mjs.
import { assert, describe, it, engineName, profiles, openChart, settled, withPage } from './chart-helpers.mjs';

const DAY = {
  bg: 'rgb(245, 240, 232)', ink: 'rgb(42, 37, 32)',
  metal: ['rgb(200, 194, 184)', 'rgb(51, 48, 44)'], fire: ['rgb(196, 133, 122)', 'rgb(46, 21, 15)'],
  wood: ['rgb(122, 158, 114)', 'rgb(15, 32, 13)'], earth: ['rgb(187, 168, 98)', 'rgb(42, 38, 16)'],
  water: ['rgb(122, 143, 160)', 'rgb(15, 26, 34)'],
};
// The embers palette: deep element colours with light type, on a dark page.
const DARK = {
  bg: 'rgb(28, 25, 22)', ink: 'rgb(238, 231, 220)',
  metal: ['rgb(92, 88, 81)', 'rgb(243, 239, 232)'], fire: ['rgb(124, 62, 52)', 'rgb(248, 230, 225)'],
  wood: ['rgb(61, 92, 56)', 'rgb(231, 241, 228)'], earth: ['rgb(107, 94, 46)', 'rgb(245, 238, 212)'],
  water: ['rgb(56, 78, 95)', 'rgb(228, 238, 245)'],
};

// The page's colours as drawn: its tone, its ink, and each card's face and type.
async function drawn(page) {
  return page.evaluate(() => ({
    bg: getComputedStyle(document.body).backgroundColor,
    ink: getComputedStyle(document.body).color,
    scheme: getComputedStyle(document.documentElement).colorScheme,
    cards: [...document.querySelectorAll('#pillars .card')].map((card) => [
      ['metal', 'fire', 'wood', 'earth', 'water'].find((element) => card.classList.contains(element)),
      getComputedStyle(card.querySelector('.card-front')).backgroundColor,
      getComputedStyle(card).color,
    ]),
  }));
}
function matches(found, palette) {
  assert.equal(found.bg, palette.bg);
  assert.equal(found.ink, palette.ink);
  for (const [element, face, type] of found.cards) assert.deepEqual([face, type], palette[element], element);
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / theme`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 60000 }, () => withPage(profile, run));

    check('the system\'s setting chooses the day\'s colours or the dark theme, and changes them on the page as it changes', async (page) => {
      await page.emulateMedia({ colorScheme: 'light' });
      await openChart(page);
      const day = await drawn(page);
      matches(day, DAY);
      assert.equal(day.scheme, 'light');
      await page.emulateMedia({ colorScheme: 'dark' });
      await settled(page);
      const dark = await drawn(page);
      matches(dark, DARK);
      assert.equal(dark.scheme, 'dark');
      assert.equal(dark.cards.length, 8);
      await page.emulateMedia({ colorScheme: 'light' });
      await settled(page);
      matches(await drawn(page), DAY);
    });

    check('paper keeps the day\'s colours when the screen is dark', async (page) => {
      await page.emulateMedia({ colorScheme: 'dark' });
      await openChart(page);
      await page.locator('button[data-context="roots"]').click();
      await page.emulateMedia({ colorScheme: 'dark', media: 'print' });
      await settled(page);
      const paper = await drawn(page);
      matches(paper, DAY);
      assert.equal(paper.scheme, 'light');
      // The open topic prints in the day's ink.
      assert.equal(await page.locator('#context-detail-title').evaluate((node) => getComputedStyle(node).color), DAY.ink);
    });
  });
}
