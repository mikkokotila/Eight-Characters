// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Stage 2 of the look-and-feel review (2026-10-17), part two: one card and one label.
// Every stem or branch card the views draw, the chart's, Today's, a saved chart's and
// the life grid's, is the same card at its size: its face the sheen over its element's
// colour in its element's ink, its shape, its character, its pinyin and its names. Every
// label, a field's, a pillar's, a place's or a group's, is set the same way.
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
// The chart on screen, saved, with a partner: Today draws the couple's day, and Settings
// the saved charts' pillars.
const SELF = { date: '1975-08-14', time: '07:45', place: PLACE, gender: 'female', zi: 'split_midnight' };
const PARTNER = { name: 'Partner', date: '1988-02-04', time: '16:30', place: PLACE, gender: 'male', zi: 'split_midnight' };
// The cards, by their size: the chart's and Today's day are full, Today's pillars at noon
// and the couple's day small, a saved chart's and the life grid's tiles, Today's
// relationships tiny.
const CARDS = [
  ['full', '#pillars .card'],
  ['full', '.today-day.is-centre .today-card'],
  ['small', '.today-cards.is-small .today-card'],
  ['tile', '.saved-glyph'],
  ['tile', '.life-mini'],
  ['tile', '.life-tile'],
  ['tiny', '.today-cards.is-tiny .today-card'],
];
// Each size's corners: the outer, then where a stem meets its branch.
const SHAPES = { full: [16, 4], small: [12, 4], tile: [12, 4], tiny: [8, 2] };
const LABELS = [
  '.field-group label', '.gender-group legend', '.account-field > label', '.account-field > legend', '.account-label',
  '.settings-choose label', '.settings-rename label', '.today-partner-label', '.pillar-plain', '.life-head-name',
  '.today-pillar-name', '.today-member-place', '.relationship-position', '.pillar-change-side', '.canon-line-key',
  '.luck-sequence', '.luck-ribbon-label', '.today-run-label', '.today-pillars-note',
];

// Every card on the page: its size, its element, and what it draws.
function cards(page) {
  return page.evaluate(({ cards }) => {
    const root = getComputedStyle(document.documentElement);
    const colour = (value) => {
      const probe = document.createElement('i');
      probe.style.color = value;
      document.body.append(probe);
      const used = getComputedStyle(probe).color;
      probe.remove();
      return used;
    };
    const found = [];
    for (const [size, selector] of cards) {
      for (const card of document.querySelectorAll(selector)) {
        if (!card.checkVisibility({ visibilityProperty: true })) continue;
        const element = ['wood', 'fire', 'earth', 'metal', 'water'].find((name) => card.classList.contains(name));
        if (!element) continue;
        const face = card.matches('.card') ? card.querySelector(card.classList.contains('is-flipped') ? '.card-back' : '.card-front') : card;
        const part = card.matches('.stem, .is-stem, [data-part="stem"]') || card.closest('[data-part="stem"]') ? 'stem' : 'branch';
        const style = getComputedStyle(face);
        const resting = card.matches('[data-luck-part="resting"], .is-resting') || !!card.closest('.is-stem-resting, .life-phase.is-resting') && part === 'stem';
        const glyph = card.querySelector('.glyph') ?? (card.matches('.glyph') ? card : null);
        const text = (node) => {
          if (!node) return null;
          const s = getComputedStyle(node);
          return { family: s.fontFamily.split(',')[0].replaceAll('"', ''), size: s.fontSize, weight: s.fontWeight, tracking: s.letterSpacing, transform: s.textTransform };
        };
        const outer = getComputedStyle(card);
        found.push({
          selector, size, part, element, resting,
          sheen: style.backgroundImage.startsWith('linear-gradient'),
          ground: style.backgroundColor === colour(root.getPropertyValue(`--${element}-${resting ? 'tint' : 'bg'}`)),
          ink: outer.color === colour(root.getPropertyValue(`--${element}-text`)),
          corners: [outer.borderTopLeftRadius, outer.borderTopRightRadius, outer.borderBottomRightRadius, outer.borderBottomLeftRadius].map(parseFloat),
          glyph: text(glyph),
          pinyin: text(card.querySelector('.card-pinyin')),
          name: text(card.querySelector('.card-front .element-name, .card-front .animal-element, :scope > .element-name, :scope > .animal-element')),
          animal: text(card.querySelector('.card-front .animal-name, :scope > .animal-name')),
          animalRoom: card.querySelector('.animal-name') ? parseFloat(getComputedStyle(face).width) - parseFloat(getComputedStyle(face).paddingLeft) - parseFloat(getComputedStyle(face).paddingRight) : null,
        });
      }
    }
    return found;
  }, { cards: CARDS });
}

// Every label on the page, and how it is set; a label in a column too narrow for its
// capitals says so.
function labels(page) {
  return page.evaluate((selectors) => {
    const found = [];
    for (const selector of selectors) {
      for (const label of document.querySelectorAll(selector)) {
        if (!label.checkVisibility({ visibilityProperty: true }) || !label.textContent.trim()) continue;
        const s = getComputedStyle(label);
        const column = label.closest('.life-head-cell');
        found.push({
          selector,
          text: label.textContent.trim().slice(0, 30),
          narrow: column ? column.getBoundingClientRect().width <= 100 : false,
          set: {
            family: s.fontFamily.split(',')[0].replaceAll('"', ''), size: s.fontSize, weight: s.fontWeight,
            line: s.lineHeight, tracking: s.letterSpacing, transform: s.textTransform, color: s.color,
          },
        });
      }
    }
    return found;
  }, LABELS);
}

// The account's place and charts, as Settings writes them; every chart saved before is
// removed first.
async function keepCouple(page) {
  await page.evaluate(async ({ place, self, partner }) => {
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
    const mine = await write('POST', '/api/account/charts', self);
    await write('POST', '/api/account/charts', { ...partner, couple_with: mine.saved });
  }, { place: PLACE, self: SELF, partner: PARTNER });
}

// The views read: the start page and its account dialog, a chart with its luck pillar,
// the relationships and the life grid, the day master's and a pillar's pages, Today for
// a chart in a couple, and Settings.
async function eachView(page, visit) {
  await page.goto(new URL('/', process.env.EC_BASE_URL).href);
  await keepCouple(page);
  await page.goto(new URL('/#', process.env.EC_BASE_URL).href);
  await page.locator('#input-view').waitFor({ state: 'visible' });
  await settled(page);
  await visit('the start page');
  await page.locator('#account-btn').click();
  await page.locator('#account-dialog[open]').waitFor();
  await settled(page);
  await visit('the account dialog');
  await page.keyboard.press('Escape');
  for (const topic of ['relationships', 'day-master', 'pillar/day', 'luck/5/branch']) {
    await openLink(page, `/#chart?${BIRTH}&luck=5/stem&topic=${topic}`, { place: HELSINKI });
    await visit(`a chart with its luck pillar, ${topic} open`);
  }
  await page.goto(new URL(`/#today?${BIRTH}&day=${DAY}`, process.env.EC_BASE_URL).href);
  await page.locator('#today-body:not(.hidden)').waitFor();
  await page.waitForFunction(() => !document.getElementById('today-view').hasAttribute('aria-busy'));
  await settled(page);
  await visit('Today');
  await page.goto(new URL('/#settings', process.env.EC_BASE_URL).href);
  await page.locator('#settings-charts .saved-glyph').first().waitFor();
  await settled(page);
  await visit('Settings');
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / components`, { concurrency: false }, () => {
    const check = (name, run) => it(name, () => withPage(profile, run));

    check('every stem and branch card is the one card, at its size', async (page) => {
      const found = [];
      await eachView(page, async (view) => { found.push(...(await cards(page)).map((card) => ({ view, ...card }))); });
      for (const size of ['full', 'small', 'tile', 'tiny']) assert.ok(found.some((card) => card.size === size), `no ${size} card was read`);
      const problems = [];
      const glyph = found[0].glyph;
      const pinyin = found.find((card) => card.pinyin)?.pinyin;
      const name = found.find((card) => card.name)?.name;
      for (const card of found) {
        const where = `${card.view}: ${card.selector} (${card.part}, ${card.element})`;
        if (!card.sheen) problems.push(`${where} has no sheen`);
        if (!card.ground) problems.push(`${where} is not on its element's ${card.resting ? 'tint' : 'colour'}`);
        if (!card.ink) problems.push(`${where} is not in its element's ink`);
        const [outer, join] = SHAPES[card.size];
        const expected = card.selector === '.life-mini' && !profile.isMobile ? [outer, outer, outer, outer]
          : card.part === 'stem' ? [outer, outer, join, join] : [join, join, outer, outer];
        // An opened branch runs on into its hidden stems.
        if (JSON.stringify(card.corners) !== JSON.stringify(expected) && !(card.selector === '#pillars .card' && card.corners[2] === 0)) {
          problems.push(`${where} has corners ${card.corners}, not ${expected}`);
        }
        if (card.glyph.family !== glyph.family || card.glyph.weight !== glyph.weight) problems.push(`${where} draws its character as ${JSON.stringify(card.glyph)}`);
        if (card.pinyin && JSON.stringify(card.pinyin) !== JSON.stringify(pinyin)) problems.push(`${where} sets its pinyin as ${JSON.stringify(card.pinyin)}`);
        if (card.name && JSON.stringify(card.name) !== JSON.stringify(name)) problems.push(`${where} sets its name as ${JSON.stringify(card.name)}`);
        if (card.animal) {
          const capitals = card.animalRoom > 130;
          if (card.animal.family !== name.family || card.animal.weight !== name.weight || card.animal.size !== '15px'
            || card.animal.transform !== (capitals ? 'uppercase' : 'none')) problems.push(`${where} sets its animal as ${JSON.stringify(card.animal)} in ${card.animalRoom}px`);
        }
      }
      assert.deepEqual(problems, []);
      assert.deepEqual({ glyph: [glyph.family, glyph.weight], pinyin: [pinyin.family, pinyin.size, pinyin.weight], name: [name.family, name.size, name.weight] },
        { glyph: ['Noto Serif TC', '500'], pinyin: ['Manrope', '13px', '600'], name: ['Cormorant Garamond', '18px', '600'] });
    });

    check('every label in the views is set one way', async (page) => {
      const found = [];
      await eachView(page, async (view) => { found.push(...(await labels(page)).map((label) => ({ view, ...label }))); });
      const read = new Set(found.map((label) => label.selector));
      for (const selector of ['.field-group label', '.gender-group legend', '.account-label', '.pillar-plain', '.life-head-name',
        '.today-pillar-name', '.today-member-place', '.relationship-position', '.canon-line-key', '.luck-sequence', '.today-run-label',
        '.today-pillars-note', '.settings-choose label']) {
        assert.ok(read.has(selector), `no ${selector} was read`);
      }
      const ink = await page.evaluate(() => getComputedStyle(document.body).getPropertyValue('--ink-2'));
      const problems = [];
      const expected = {
        family: 'Cormorant Garamond', size: '13px', weight: '500', line: '17.55px', tracking: '2.34px', transform: 'uppercase',
      };
      for (const label of found) {
        const set = { ...label.set };
        delete set.color;
        const own = label.narrow ? { ...expected, tracking: '0.26px', transform: 'none' } : expected;
        if (JSON.stringify(set) !== JSON.stringify(own)) problems.push(`${label.view}: ${label.selector} "${label.text}" is set ${JSON.stringify(set)}`);
      }
      const colours = new Set(found.map((label) => label.set.color));
      assert.deepEqual(problems, []);
      assert.equal(colours.size, 1, `labels in ${[...colours].join(', ')} (--ink-2 is ${ink})`);
    });
  });
}
