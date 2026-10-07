// Run with Node's built-in test runner and an explicitly selected Playwright install.
// The luck pillars of a chart asked for with a gender: a ribbon of its decades under the
// topics, the chosen period standing in the chart as a fifth pillar, and its page in the
// panel. Each decade is a stem phase, its first five years, and a branch phase, its last
// five; a chart without a gender has none.
import {
  assert, describe, it, engineName, profiles, openChart, openLink, settled, geometry, screenshot, withPage,
  openRelationships, showDisplay, HELSINKI, CHENGDU,
} from './chart-helpers.mjs';

// The design's sample: 14 August 1975, 07:45, Helsinki, female. Its luck pillars run
// forward from 乙酉 Yi You, the first at age 8. On 7 October 2026 the fifth, 己丑 Ji Chou,
// is in its stem phase, from 18 December 2023 to 18 December 2028.
const SAMPLE = { date: '1975-08-14', time: '07:45', place: HELSINKI, gender: 'female' };
const TODAY = new Date('2026-10-07T12:00:00Z');
// Characters, names, first and last year, and the age each starts at.
const DECADES = [
  ['乙酉', 'Yi You', 1983, 1993, 8], ['丙戌', 'Bing Xu', 1993, 2003, 18], ['丁亥', 'Ding Hai', 2003, 2013, 28],
  ['戊子', 'Wu Zi', 2013, 2023, 38], ['己丑', 'Ji Chou', 2023, 2033, 48], ['庚寅', 'Geng Yin', 2033, 2043, 58],
  ['辛卯', 'Xin Mao', 2043, 2053, 68], ['壬辰', 'Ren Chen', 2053, 2063, 78], ['癸巳', 'Gui Si', 2063, 2073, 88],
  ['甲午', 'Jia Wu', 2073, 2083, 98],
];
const sampleLink = (parts = {}) => `/#chart?${new URLSearchParams({
  date: SAMPLE.date, time: SAMPLE.time, place: HELSINKI.display, city: HELSINKI.city,
  latitude: String(HELSINKI.latitude), longitude: String(HELSINKI.longitude), timezone: HELSINKI.timezone,
  lang: 'en', gender: 'female', ...parts,
})}`;
// Safari moves Tab only between text fields and tab-indexed elements unless Full Keyboard
// Access is on; Option+Tab reaches every control (keyboard.test.mjs).
const TAB = engineName === 'webkit' ? 'Alt+Tab' : 'Tab';

async function openSample(page, options = {}, now = TODAY) {
  await page.clock.setFixedTime(now);
  return openChart(page, { ...SAMPLE, ...options });
}

// A part of the address, as the app wrote it: the topic open, or the gender.
function linkPart(page, name) {
  return page.evaluate((name) => new URLSearchParams(location.hash.split('?')[1] ?? '').get(name), name);
}

// The four_pillars requests the page sends.
function requests(page) {
  const sent = [];
  page.on('request', (request) => {
    if (request.url().endsWith('/api/four_pillars')) sent.push(request.postDataJSON());
  });
  return sent;
}

// The ribbon as it reads: each group's name and its chips.
function ribbon(page) {
  return page.locator('#luck-ribbon .luck-group').evaluateAll((groups) => groups.map((group) => ({
    name: group.querySelector('.luck-direction').textContent.trim(),
    chips: [...group.querySelectorAll('.luck-chip')].map((chip) => chip.dataset.luck),
  })));
}

// Where the ribbon is: the chosen chip, today's, and the phases each marks.
function ribbonState(page) {
  return page.locator('#luck-ribbon').evaluate((node) => ({
    expanded: [...node.querySelectorAll('.luck-chip[aria-expanded="true"]')].map((chip) => chip.dataset.luck),
    selected: [...node.querySelectorAll('.luck-chip.is-selected')].map((chip) => chip.dataset.luck),
    today: [...node.querySelectorAll('.luck-chip.is-today')].map((chip) => chip.dataset.luck),
    chosenPhase: [...node.querySelectorAll('.luck-chip-phases i.is-chosen')]
      .map((bar) => `${bar.closest('.luck-chip').dataset.luck}/${bar.dataset.phase}`),
    todayPhase: [...node.querySelectorAll('.luck-chip-phases i[data-today]')]
      .map((bar) => `${bar.closest('.luck-chip').dataset.luck}/${bar.dataset.phase}`),
    stop: [...node.querySelectorAll('.luck-chip[tabindex="0"]')].map((chip) => chip.dataset.luck),
    todayDisabled: node.querySelector('[data-luck-today]').disabled,
  }));
}

// The open decade's page as it reads.
function decadePage(page) {
  return page.locator('#luck-detail').evaluate((detail) => {
    const text = (node) => (node ? node.textContent.replace(/\s+/g, ' ').trim() : null);
    const rows = (selector) => [...detail.querySelectorAll(selector)].map((row) => ({
      identity: text(row.querySelector('.context-evidence-identity > span:first-child')),
      type: text(row.querySelector('.hidden-stem-type')),
      role: text(row.querySelector('.context-evidence-role')),
      resting: row.classList.contains('is-resting'),
    }));
    return {
      sequence: text(detail.querySelector('.luck-sequence')),
      title: text(detail.querySelector('#luck-detail-title')),
      meta: text(detail.querySelector('.luck-meta')),
      phases: [...detail.querySelectorAll('[data-luck-phase]')].map((button) => ({
        name: text(button.querySelector('.luck-phase-name')),
        when: text(button.querySelector('.luck-phase-when')),
        pressed: button.getAttribute('aria-pressed'),
      })),
      brings: rows('.luck-occurrence'),
      stage: text(detail.querySelector('.luck-stage')),
      roots: rows('.luck-root'),
      relationships: [...detail.querySelectorAll('.luck-relationship')].map((row) => ({
        kind: row.dataset.kind,
        name: text(row.querySelector('.luck-relationship-name')),
        chars: text(row.querySelector('.luck-relationship-chars')),
        when: text(row.querySelector('.luck-relationship-when')),
        resting: row.classList.contains('is-resting'),
      })),
      elementsHeading: text([...detail.querySelectorAll('.luck-subheading')].at(-1)),
      // Each element's count, and its cells: the natal chart's, then the luck pillar's.
      elements: [...detail.querySelectorAll('.luck-element')].map((row) => [
        row.dataset.element, text(row.querySelector('.luck-element-count')),
        row.querySelectorAll('.luck-element-cells i:not(.is-luck)').length,
        row.querySelectorAll('.luck-element-cells i.is-luck').length,
      ]),
    };
  });
}

// The fifth pillar as it reads: its state, its name, its mark and its cards' parts.
function column(page) {
  return page.locator('.pillar.is-luck').evaluate((node) => ({
    state: node.dataset.luckState,
    inert: node.inert,
    poetic: node.querySelector('.pillar-poetic').textContent,
    name: node.querySelector('[data-luck-identity]').textContent.replace(/\s+/g, ' ').trim(),
    mark: node.querySelector('.luck-mark').textContent,
    parts: [...node.querySelectorAll('.card')].map((card) => `${card.dataset.char}:${card.dataset.luckPart || '-'}`),
    setAside: node.querySelector('.luck-set-aside')?.textContent ?? null,
  }));
}

// Every card's box on the page, and the arcs', by the card's pillar and side.
function boxes(page) {
  return page.evaluate(() => [...document.querySelectorAll('#pillars .card, #pillars .relationship-arc, #pillars .hidden-stems-panel')]
    // What is not drawn has no place (phones draw no arcs).
    .filter((node) => node.getClientRects().length > 0)
    .map((node) => {
      const box = node.getBoundingClientRect();
      const name = node.matches('.card') ? `${node.dataset.pillar} ${node.classList.contains('stem') ? 'stem' : 'branch'}`
        : node.matches('.hidden-stems-panel') ? `${node.dataset.pillar} hidden` : `arc ${node.dataset.relationshipId}`;
      return `${name} ${Math.round(box.x * 10) / 10},${Math.round((box.y + scrollY) * 10) / 10} ${Math.round(box.width * 10) / 10}x${Math.round(box.height * 10) / 10}`;
    }));
}

function focused(page) {
  return page.evaluate(() => {
    const node = document.activeElement;
    if (node.matches('#pillars .card')) return `${node.dataset.pillar} ${node.classList.contains('stem') ? 'stem' : 'branch'}`;
    if (node.dataset.luck) return `chip ${node.dataset.luck}`;
    if (node.dataset.luckStep) return `step ${node.dataset.luckStep}`;
    if (node.dataset.luckPhase) return `phase ${node.dataset.luckPhase}`;
    if (node.hasAttribute('data-luck-today')) return 'today';
    return node.id || node.textContent.replace(/\s+/g, ' ').trim();
  });
}

async function click(page, selector) {
  await page.locator(selector).click();
  await settled(page);
}

// The decade 己丑 Ji Chou in its stem phase, as on 7 October 2026.
const JI_CHOU_STEM = {
  sequence: 'Luck pillar 5 of 10 · forward',
  title: '己丑 Ji Chou',
  meta: 'Dec 18, 2023 – Dec 18, 2033 · age 48–58 · North, winter',
  phases: [
    { name: 'Stem phase · now', when: 'Dec 18, 2023 – Dec 18, 2028', pressed: 'true' },
    { name: 'Branch phase', when: 'Dec 18, 2028 – Dec 18, 2033', pressed: 'false' },
  ],
  brings: [
    { identity: 'Ji 己 · Yin Earth', type: 'Stem phase', role: 'Direct Officer · new to this chart', resting: false },
    { identity: 'Ji 己 · Yin Earth', type: 'Main', role: 'Direct Officer · new to this chart', resting: false },
    { identity: 'Gui 癸 · Yin Water', type: 'Mid', role: 'Rob Wealth', resting: false },
    { identity: 'Xin 辛 · Yin Metal', type: 'Residual', role: 'Direct Resource · new to this chart', resting: false },
  ],
  stage: 'Day Master on Chou 丑: Decline, stage 6 of 12',
  roots: [{ identity: 'Gui 癸 · Yin Water', type: 'Mid', role: 'Same element, opposite polarity', resting: false }],
  relationships: [
    { kind: 'stem_combination', name: 'Month–Luck · Stem combination', chars: 'Jia 甲 – Ji 己', when: 'acts in the stem phase', resting: false },
    { kind: 'stem_combination', name: 'Hour–Luck · Stem combination', chars: 'Jia 甲 – Ji 己', when: 'acts in the stem phase', resting: false },
  ],
  elementsHeading: 'Elements: 10 characters with the luck pillar',
  elements: [['wood', '4', 4, 0], ['fire', '0', 0, 0], ['earth', '2 +2', 2, 2], ['metal', '1', 1, 0], ['water', '1', 1, 0]],
};

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / luck pillars`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 60000 }, () => withPage(profile, run));

    check('the gender is optional, and a chart without one has no luck pillars and asks for none', async (page) => {
      const sent = requests(page);
      await page.goto(new URL('/', process.env.EC_BASE_URL).href);
      await page.locator('[data-lang="fi"]').click();
      assert.equal(await page.locator('.gender-group legend').textContent(), 'Sukupuoli (valinnainen)');
      assert.deepEqual(await page.locator('.gender-option').allTextContents(), ['Ei annettu', 'Nainen', 'Mies']);
      await page.locator('[data-lang="en"]').click();
      assert.equal(await page.locator('.gender-group legend').textContent(), 'Gender (optional)');
      assert.deepEqual(await page.locator('.gender-option').allTextContents(), ['Not given', 'Female', 'Male']);
      assert.equal(await page.locator('#gender-hint').textContent(), 'For the luck pillars, whose direction depends on it.');
      assert.equal(await page.locator('input[name="gender"]:checked').getAttribute('value'), '');
      const payload = await openChart(page);
      assert.equal(sent.length, 1);
      for (const key of ['gender', 'include_luck_pillars', 'include_luck_context']) assert.equal(key in sent[0], false, key);
      assert.equal('luck_pillars' in payload, false);
      assert.equal(await page.locator('#luck-ribbon').isVisible(), false);
      assert.equal(await page.locator('#luck-ribbon').innerHTML(), '');
      assert.equal(await linkPart(page, 'gender'), null);
    });

    check('the ribbon shows each decade by its names, years and age, grouped by direction, with today marked', async (page) => {
      const sent = requests(page);
      const payload = await openSample(page);
      assert.deepEqual([sent[0].gender, sent[0].include_luck_pillars, sent[0].include_luck_context], ['female', true, true]);
      assert.equal(await linkPart(page, 'gender'), 'female');
      assert.equal(await page.locator('#luck-ribbon').isVisible(), true);
      assert.deepEqual(await ribbon(page), [
        { name: 'Before', chips: ['before'] },
        { name: 'West · Autumn', chips: ['1', '2'] },
        { name: 'North · Winter', chips: ['3', '4', '5'] },
        { name: 'East · Spring', chips: ['6', '7', '8'] },
        { name: 'South · Summer', chips: ['9', '10'] },
      ]);
      const chips = await page.locator('.luck-chip:not(.is-before)').evaluateAll((nodes) => nodes.map((chip) => [
        chip.querySelector('.luck-chip-chars').textContent, chip.querySelector('.luck-chip-names').textContent,
        chip.querySelector('.luck-chip-age').textContent, chip.getAttribute('aria-label'),
      ]));
      assert.deepEqual(chips, DECADES.map(([chars, names, from, to, age]) => [chars, names, String(age),
        `${names}, ${from} to ${to}, age ${age}${chars === '己丑' ? ', now' : ''}`]));
      // The characters are the engine's, and so are the stems' names.
      assert.deepEqual(DECADES.map(([chars]) => chars),
        payload.luck_pillars.pillars.map((pillar) => pillar.stem.chinese + pillar.branch.chinese));
      assert.deepEqual(DECADES.map(([, names]) => names.split(' ')[0]),
        payload.luck_context.decades.map((decade) => decade.occurrences[0].pinyin));
      const before = page.locator('.luck-chip.is-before');
      assert.equal((await before.textContent()).trim(), '0–8');
      assert.equal(await before.getAttribute('aria-label'), 'Before the first luck pillar, age 0 to 8');
      assert.deepEqual(await ribbonState(page), {
        expanded: [], selected: [], today: ['5'], chosenPhase: [], todayPhase: ['5/stem'], stop: ['5'], todayDisabled: false,
      });
      assert.equal(await page.locator('#chart-panel').isVisible(), false);
      assert.equal(await linkPart(page, 'topic'), null);
      // The track scrolls within the ribbon, never the page, and shows today's decade.
      const fit = await page.evaluate(() => {
        const track = document.querySelector('.luck-track').getBoundingClientRect();
        const today = document.querySelector('.luck-chip.is-today').getBoundingClientRect();
        return {
          page: document.documentElement.scrollWidth <= innerWidth,
          inSight: today.left >= track.left && today.right <= track.right,
          scrolls: document.querySelector('.luck-track').scrollWidth > document.querySelector('.luck-track').clientWidth,
        };
      });
      assert.deepEqual(fit, { page: true, inSight: true, scrolls: profile.name === 'mobile' });
      await screenshot(page, `${profile.name}-luck-ribbon`);
    });

    check('Today opens the decade at today\'s phase: what it brings, its roots, relationships and elements', async (page) => {
      await openSample(page);
      const before = await geometry(page);
      await click(page, '[data-luck-today]');
      assert.equal(await linkPart(page, 'topic'), 'luck/5/stem');
      assert.equal(await page.locator('#luck-detail').isVisible(), true);
      assert.deepEqual(await decadePage(page), JI_CHOU_STEM);
      assert.deepEqual(await ribbonState(page), {
        expanded: ['5'], selected: ['5'], today: ['5'], chosenPhase: ['5/stem'], todayPhase: ['5/stem'], stop: ['5'], todayDisabled: true,
      });
      // Today is chosen and its button is spent: focus goes to the chosen chip.
      assert.equal(await focused(page), 'chip 5');
      assert.equal(await page.locator('#luck-status').textContent(), 'Shown: Ji Chou, Stem phase.');
      assert.equal(await page.locator('#luck-detail').getAttribute('data-topic'), 'luck/5/stem');
      // The decade stands in the chart, and nothing else on it moves.
      assert.equal(await linkPart(page, 'luck'), '5/stem');
      assert.equal((await column(page)).state, 'on');
      assert.deepEqual(await geometry(page), before);
      // A relationship points at its cards: the natal one and the luck pillar's.
      await page.locator('.luck-relationship').first().click();
      assert.deepEqual(await page.locator('#pillars .is-spotlit').evaluateAll((nodes) =>
        nodes.map((node) => `${node.classList.contains('stem') ? 'stem' : 'branch'}:${node.dataset.pillar}`)), ['stem:month', 'stem:luck']);
      await screenshot(page, `${profile.name}-luck-decade`);
    });

    check('the branch phase sets the stem aside, and the ribbon and the address follow the phase', async (page) => {
      await openSample(page);
      await click(page, '[data-luck-today]');
      await click(page, '[data-luck-phase="branch"]');
      assert.equal(await linkPart(page, 'topic'), 'luck/5/branch');
      assert.equal(await focused(page), 'phase branch');
      assert.equal(await page.locator('#luck-status').textContent(), 'Shown: Ji Chou, Branch phase.');
      const shown = await decadePage(page);
      assert.deepEqual(shown.phases.map((phase) => [phase.name, phase.pressed]),
        [['Stem phase · now', 'false'], ['Branch phase', 'true']]);
      assert.deepEqual(shown.brings.map((row) => [row.type, row.resting]),
        [['Stem phase, not now', true], ['Main', false], ['Mid', false], ['Residual', false]]);
      assert.deepEqual(shown.relationships.map((row) => [row.when, row.resting]),
        [['acts in the stem phase, not now', true], ['acts in the stem phase, not now', true]]);
      assert.equal(shown.elementsHeading, 'Elements: 9 characters with the luck pillar');
      assert.deepEqual(shown.elements, [['wood', '4', 4, 0], ['fire', '0', 0, 0], ['earth', '2 +1', 2, 1], ['metal', '1', 1, 0], ['water', '1', 1, 0]]);
      assert.deepEqual(await ribbonState(page), {
        expanded: ['5'], selected: ['5'], today: ['5'], chosenPhase: ['5/branch'], todayPhase: ['5/stem'], stop: ['5'], todayDisabled: false,
      });
      // The keys step from the page too, and focus stays on its chosen phase.
      await page.keyboard.press(']');
      await settled(page);
      assert.deepEqual([await linkPart(page, 'topic'), await focused(page)], ['luck/6/stem', 'phase stem']);
      await page.keyboard.press('[');
      await page.keyboard.press('[');
      await page.keyboard.press('[');
      await settled(page);
      assert.deepEqual([await linkPart(page, 'topic'), await focused(page)], ['luck/4/branch', 'phase branch']);
      await click(page, '[data-luck="before"]');
      await page.locator('[data-luck="1"]').focus();
      await page.keyboard.press('Enter');
      await settled(page);
      await page.locator('[data-luck-phase="stem"]').focus();
      await page.keyboard.press('{');
      await settled(page);
      assert.deepEqual([await linkPart(page, 'topic'), await focused(page)], ['luck/before', 'chip before']);
      // Back to today.
      await click(page, '[data-luck-today]');
      assert.equal(await linkPart(page, 'topic'), 'luck/5/stem');
      assert.deepEqual(await decadePage(page), JI_CHOU_STEM);
    });

    check('the steps walk the luck pillar through the phases in order, and an open page follows', async (page) => {
      await openSample(page);
      const steps = [];
      const stepBy = async (by) => {
        await click(page, `[data-luck-step="${by}"]`);
        assert.equal(await focused(page), `step ${by}`);
        steps.push(`${await linkPart(page, 'luck')} ${await linkPart(page, 'topic')}`);
      };
      // With the luck pillar hidden, a step goes from today's phase, and shows it; no page opens.
      await stepBy(1);
      await stepBy(1);
      await stepBy(-1);
      await stepBy(-1);
      assert.deepEqual(steps, ['5/branch null', '6/stem null', '5/branch null', '5/stem null']);
      assert.deepEqual((await column(page)).parts, ['己:leading', '丑:acting']);
      // With its page open, the page follows, from the years before the decades to the last.
      await click(page, '[data-luck="before"]');
      steps.length = 0;
      await stepBy(-1);
      await stepBy(1);
      await click(page, '[data-luck="10"]');
      await stepBy(1);
      await stepBy(1);
      assert.deepEqual(steps, ['before luck/before', '1/stem luck/1/stem', '10/branch luck/10/branch', '10/branch luck/10/branch']);
      assert.deepEqual((await ribbonState(page)).chosenPhase, ['10/branch']);
    });

    check('a chip opens its decade and closes it; Escape and Close give focus back to it', async (page) => {
      await openSample(page);
      // Today does not fall in the fourth decade: it opens at its stem phase.
      await click(page, '[data-luck="4"]');
      assert.equal(await linkPart(page, 'topic'), 'luck/4/stem');
      assert.equal(await focused(page), 'chip 4');
      assert.equal((await decadePage(page)).title, '戊子 Wu Zi');
      await click(page, '[data-luck="4"]');
      assert.equal(await linkPart(page, 'topic'), null);
      assert.equal(await page.locator('#chart-panel').isVisible(), false);
      assert.equal(await focused(page), 'chip 4');
      // The page closes; the decade still stands in the chart.
      assert.equal(await linkPart(page, 'luck'), '4/stem');
      assert.deepEqual([(await ribbonState(page)).expanded, (await ribbonState(page)).selected], [[], ['4']]);
      // The fifth opens at today's phase.
      await click(page, '[data-luck="5"]');
      assert.equal(await linkPart(page, 'topic'), 'luck/5/stem');
      await page.keyboard.press('Escape');
      await settled(page);
      assert.equal(await linkPart(page, 'topic'), null);
      assert.equal(await focused(page), 'chip 5');
      await click(page, '[data-luck="7"]');
      await click(page, '[data-close-panel]');
      assert.equal(await linkPart(page, 'topic'), null);
      assert.equal(await focused(page), 'chip 7');
      // Another topic replaces the decade, and the decade replaces it.
      await click(page, '[data-luck="5"]');
      await click(page, 'button[data-context="roots"]');
      assert.equal(await linkPart(page, 'topic'), 'roots');
      assert.equal(await page.locator('#luck-detail').isVisible(), false);
      assert.deepEqual((await ribbonState(page)).expanded, []);
      await click(page, '[data-luck="5"]');
      assert.equal(await linkPart(page, 'topic'), 'luck/5/stem');
      assert.equal(await page.locator('#context-detail').isVisible(), false);
      assert.equal(await page.locator('button[data-context="roots"]').getAttribute('aria-expanded'), 'false');
      await openRelationships(page);
      assert.equal(await page.locator('#luck-detail').isVisible(), false);
      await click(page, '[data-luck="5"]');
      assert.equal(await page.locator('#relationships-panel').isVisible(), false);
      assert.equal(await page.locator('#relationships-topic').getAttribute('aria-expanded'), 'false');
    });

    check('the chips take one tab stop, arrows move between them, and Enter opens one', async (page) => {
      await openSample(page);
      await page.locator('#relationships-topic').focus();
      const reached = [];
      for (let presses = 0; presses < 4; presses += 1) {
        await page.keyboard.press(TAB);
        reached.push(await focused(page));
      }
      assert.deepEqual(reached, ['step -1', 'chip 5', 'step 1', 'today']);
      await page.locator('[data-luck="5"]').focus();
      await page.keyboard.press('ArrowRight');
      assert.equal(await focused(page), 'chip 6');
      await page.keyboard.press('Home');
      assert.equal(await focused(page), 'chip before');
      await page.keyboard.press('ArrowLeft');
      assert.equal(await focused(page), 'chip before');
      await page.keyboard.press('End');
      assert.equal(await focused(page), 'chip 10');
      await page.keyboard.press('ArrowLeft');
      assert.equal(await focused(page), 'chip 9');
      // Moving opens nothing; the chip moved to keeps the stop.
      assert.equal(await linkPart(page, 'topic'), null);
      assert.deepEqual((await ribbonState(page)).stop, ['9']);
      await page.keyboard.press('Enter');
      await settled(page);
      assert.equal(await linkPart(page, 'topic'), 'luck/9/stem');
      assert.deepEqual((await ribbonState(page)).stop, ['9']);
      await page.keyboard.press('Space');
      await settled(page);
      assert.equal(await linkPart(page, 'topic'), null);
      assert.equal(await linkPart(page, 'luck'), '9/stem');
    });

    check('the years before the first decade have their own page', async (page) => {
      await openSample(page);
      await click(page, '[data-luck="before"]');
      assert.equal(await linkPart(page, 'topic'), 'luck/before');
      assert.equal(await page.locator('#luck-detail').innerText().then((text) => text.replace(/\s+/g, ' ').trim()),
        'Before the first luck pillar Aug 14, 1975 – Dec 18, 1983 · age 0–8 '
        + 'No luck pillar falls here: the first starts at 8 y 4 m 4 d. The chart reads as natal.');
      assert.equal(await page.locator('#luck-status').textContent(), 'Shown: Before the first luck pillar.');
      assert.deepEqual((await ribbonState(page)).expanded, ['before']);
    });

    check('a child\'s chart is before its first decade today, an old one past its last, and a birth to come before all', async (page) => {
      // Born 1 June 2025 in Chengdu, male: the decades run backward from age 8.
      await openSample(page, { date: '2025-06-01', time: '12:00', place: CHENGDU, gender: 'male' });
      assert.deepEqual(await ribbonState(page), {
        expanded: [], selected: [], today: ['before'], chosenPhase: [], todayPhase: [], stop: ['before'], todayDisabled: false,
      });
      await click(page, '[data-luck-today]');
      assert.equal(await linkPart(page, 'topic'), 'luck/before');
      assert.equal((await decadePage(page)).title, 'Before the first luck pillar');
      // Born 1 March 1949, female, seen in 2060: the last decade ended in 2050.
      await openSample(page, { date: '1949-03-01', time: '12:00', place: CHENGDU, gender: 'female' }, new Date('2060-01-01T12:00:00Z'));
      assert.deepEqual(await ribbonState(page), {
        expanded: [], selected: [], today: [], chosenPhase: [], todayPhase: [], stop: ['10'], todayDisabled: true,
      });
      // With the luck pillar hidden, a step back goes from just past the end: to the last phase.
      await click(page, '[data-luck-step="-1"]');
      assert.equal(await linkPart(page, 'luck'), '10/branch');
      // Born 1 March 2040, female, seen in 2026: today is before the birth, and no period
      // holds it.
      await openSample(page, { date: '2040-03-01', time: '12:00', place: CHENGDU, gender: 'female' });
      assert.deepEqual(await ribbonState(page), {
        expanded: [], selected: [], today: [], chosenPhase: [], todayPhase: [], stop: ['before'], todayDisabled: true,
      });
      assert.equal(await page.locator('.luck-chip.is-before').getAttribute('aria-label'), 'Before the first luck pillar, age 0 to 8');
      // With the luck pillar hidden, a step goes from just before the start: to the years before.
      await click(page, '[data-luck-step="1"]');
      assert.equal(await linkPart(page, 'luck'), 'before');
      assert.equal((await column(page)).state, 'none');
    });

    check('a birth within the luck pillars\' allowance of a solar term has a nominal timeline, and says so', async (page) => {
      await openSample(page);
      assert.equal(await page.locator('#chart-notices').isVisible(), false);
      // Seconds from Jingzhe on 5 March 1988, and from Lichun on 4 February: further than
      // the natal calculation's 0.5 s, within the luck pillars' 3 s.
      const near = (date, time) => `/#chart?${new URLSearchParams({
        date, time, place: CHENGDU.display, city: CHENGDU.city, latitude: String(CHENGDU.latitude),
        longitude: String(CHENGDU.longitude), timezone: CHENGDU.timezone, lang: 'en', gender: 'female', topic: 'luck/1/stem',
      })}`;
      for (const [date, time, notice] of [
        ['1988-03-05', '16:46:30', 'The birth lies within the luck pillars\' allowance (3 s) of a solar term, so their decades and the age they start at could be other ones.'],
        ['1988-02-04', '22:42:47', 'The birth lies within the luck pillars\' allowance (3 s) of Lichun, so their decades, the age they start at and their direction could be other ones.'],
      ]) {
        await page.goto('about:blank');
        const payload = await openLink(page, near(date, time), { place: CHENGDU });
        assert.deepEqual([payload.flags.solar_term_ambiguous, payload.luck_pillars.uncertainty.boundary_ambiguous], [false, true]);
        assert.deepEqual(await page.locator('#chart-notices li').allTextContents(), [notice]);
        assert.equal(await page.locator('#luck-detail .luck-nominal').textContent(), 'The dates are nominal: see the notice at the top of the chart.');
        await click(page, '[data-luck="before"]');
        assert.equal(await page.locator('#luck-detail .luck-nominal').count(), 1);
      }
    });

    check('a link opens the decade and phase it names, and the form keeps the gender for Edit', async (page) => {
      await page.clock.setFixedTime(TODAY);
      await openLink(page, sampleLink({ topic: 'luck/4/branch' }), { place: HELSINKI });
      assert.equal(await linkPart(page, 'topic'), 'luck/4/branch');
      assert.deepEqual(await decadePage(page), {
        sequence: 'Luck pillar 4 of 10 · forward',
        title: '戊子 Wu Zi',
        meta: 'Dec 18, 2013 – Dec 18, 2023 · age 38–48 · North, winter',
        phases: [
          { name: 'Stem phase', when: 'Dec 18, 2013 – Dec 18, 2018', pressed: 'false' },
          { name: 'Branch phase', when: 'Dec 18, 2018 – Dec 18, 2023', pressed: 'true' },
        ],
        brings: [
          { identity: 'Wu 戊 · Yang Earth', type: 'Stem phase, not now', role: 'Seven Killings', resting: true },
          { identity: 'Gui 癸 · Yin Water', type: 'Main', role: 'Rob Wealth', resting: false },
        ],
        stage: 'Day Master on Zi 子: Emperor\'s Peak, stage 5 of 12',
        roots: [{ identity: 'Gui 癸 · Yin Water', type: 'Main', role: 'Same element, opposite polarity', resting: false }],
        relationships: [
          { kind: 'harmony_frame', name: 'Day–Month–Luck · Three-harmony frame', chars: 'Chen 辰 – Shen 申 – Zi 子', when: 'acts in both phases', resting: false },
          { kind: 'harmony_frame', name: 'Hour–Month–Luck · Three-harmony frame', chars: 'Chen 辰 – Shen 申 – Zi 子', when: 'acts in both phases', resting: false },
          { kind: 'punishment', name: 'Year–Luck · Punishment', chars: 'Mao 卯 – Zi 子', when: 'acts in both phases', resting: false },
        ],
        elementsHeading: 'Elements: 9 characters with the luck pillar',
        elements: [['wood', '4', 4, 0], ['fire', '0', 0, 0], ['earth', '2', 2, 0], ['metal', '1', 1, 0], ['water', '1 +1', 1, 1]],
      });
      assert.deepEqual(await ribbonState(page), {
        expanded: ['4'], selected: ['4'], today: ['5'], chosenPhase: ['4/branch'], todayPhase: ['5/stem'], stop: ['4'], todayDisabled: false,
      });
      // A frame points at both its natal branches and the luck pillar's.
      await page.locator('.luck-relationship').first().click();
      assert.deepEqual(await page.locator('#pillars .is-spotlit').evaluateAll((nodes) =>
        nodes.map((node) => node.dataset.pillar).sort()), ['day', 'luck', 'month']);
      // Edit keeps the birth with its gender; a new chart starts without one.
      await page.locator('#back-btn').click();
      assert.equal(await page.locator('input[name="gender"]:checked').getAttribute('value'), 'female');
      await page.locator('#create-chart-btn').click();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      assert.equal(await linkPart(page, 'gender'), 'female');
      assert.equal(await page.locator('#luck-ribbon').isVisible(), true);
      await page.locator('#new-chart-btn').click();
      assert.equal(await page.locator('input[name="gender"]:checked').getAttribute('value'), '');
    });

    check('a whole the luck pillar completes names the natal half it takes in', async (page) => {
      // 15 April 1960, 12:00, Chengdu, female: the third decade's branch completes the
      // Hour and Day branches' half-frame into a three-harmony frame.
      await page.clock.setFixedTime(TODAY);
      const payload = await openLink(page, `/#chart?${new URLSearchParams({
        date: '1960-04-15', time: '12:00', place: CHENGDU.display, city: CHENGDU.city,
        latitude: String(CHENGDU.latitude), longitude: String(CHENGDU.longitude), timezone: CHENGDU.timezone,
        lang: 'en', gender: 'female', topic: 'luck/3/stem',
      })}`, { place: CHENGDU });
      assert.deepEqual(payload.luck_context.decades[2].absorbed.map((a) => [a.id, a.by]),
        [['half_frame:25:day-hour', ['harmony_frame:21:day-hour-luck']]]);
      const rows = await page.locator('.luck-relationship').evaluateAll((nodes) => nodes.map((node) => [
        node.dataset.relationship,
        [...node.querySelectorAll('.luck-relationship-absorbs')].map((line) => line.textContent),
      ]));
      assert.deepEqual(rows, [
        ['branch_combination:6:year-luck', []],
        ['harmony_frame:21:day-hour-luck', ['takes in the natal Hour–Day · Half-frame for the decade']],
      ]);
    });

    check('a link to a decade the chart has not opens no chart, and says why', async (page) => {
      await page.clock.setFixedTime(TODAY);
      for (const [address, part] of [
        [sampleLink({ topic: 'luck/11/stem' }), 'topic'],
        [sampleLink({ topic: 'luck/0/branch' }), 'topic'],
        [sampleLink({ gender: 'other' }), 'gender'],
        [sampleLink({ luck: '11/stem' }), 'luck'],
        [sampleLink({ luck: '5/leaf' }), 'luck'],
        [sampleLink({ luck: '4/stem', topic: 'luck/5/stem' }), 'topic'],
      ]) {
        await page.goto('about:blank');
        await openLink(page, address, { place: HELSINKI, success: false });
        assert.equal(await page.locator('#form-error').textContent(), `This link does not open a chart: “${part}” is missing or not valid.`, address);
      }
      // Without a gender there are no luck pillars to open.
      const parts = Object.fromEntries(new URLSearchParams(sampleLink({ topic: 'luck/4/stem' }).split('?')[1]));
      delete parts.gender;
      await page.goto('about:blank');
      await openLink(page, `/#chart?${new URLSearchParams(parts)}`, { place: HELSINKI, success: false });
      assert.equal(await page.locator('#form-error').textContent(), 'This link does not open a chart: “topic” is missing or not valid.');
      delete parts.topic;
      await page.goto('about:blank');
      await openLink(page, `/#chart?${new URLSearchParams({ ...parts, luck: '4/stem' })}`, { place: HELSINKI, success: false });
      assert.equal(await page.locator('#form-error').textContent(), 'This link does not open a chart: “luck” is missing or not valid.');
    });

    check('luck pillars that do not hold together are refused, and no chart is drawn', async (page) => {
      const broken = [
        // Asked for with a gender, answered without the context.
        (payload) => { delete payload.luck_context; },
        // An element counted in the stem phase that no character carries.
        (payload) => { payload.luck_context.decades[2].counts.stem.elements.earth += 1; },
        // A relationship of the luck pillar's that names no luck member.
        (payload) => { payload.luck_context.decades[4].interactions[0].members.pop(); },
        // Phases that do not meet.
        (payload) => { payload.luck_pillars.pillars[6].phases[1].start_utc = payload.luck_pillars.pillars[6].phases[1].end_utc; },
        // A stem combination said to act in the branch phase too, against the phase rule.
        (payload) => { payload.luck_context.decades[4].interactions[0].phases = ['stem', 'branch']; },
      ];
      // Each is the real API's answer, changed on its way to the page.
      for (const mutate of broken) {
        await page.clock.setFixedTime(TODAY);
        await openChart(page, { ...SAMPLE, success: false }, mutate);
        assert.equal(await page.locator('#form-error').textContent(), 'Reading the luck pillars failed.');
        assert.equal(await page.locator('#chart-view').isVisible(), false);
        await page.unrouteAll();
      }
    });

    check('in Finnish, and through a change of language that keeps the luck pillars', async (page) => {
      await openSample(page, { lang: 'fi' });
      assert.deepEqual((await ribbon(page)).map((group) => group.name),
        ['Ennen', 'Länsi · Syksy', 'Pohjoinen · Talvi', 'Itä · Kevät', 'Etelä · Kesä']);
      assert.equal(await page.locator('[data-luck-today]').textContent(), 'Tänään');
      assert.equal(await page.locator('[data-luck="5"]').getAttribute('aria-label'), 'Ji Chou, 2023–2033, ikä 48, nyt');
      await click(page, '[data-luck-today]');
      const shown = await decadePage(page);
      assert.equal(shown.sequence, 'Onnenpilari 5/10 · eteenpäin');
      assert.equal(shown.meta, '18.12.2023 – 18.12.2033 · ikä 48–58 · Pohjoinen, talvi');
      assert.deepEqual(shown.phases.map((phase) => phase.name), ['Rungon vaihe · nyt', 'Haaran vaihe']);
      assert.equal(shown.stage, 'Päivän mestari haarassa Chou 丑: Heikkeneminen, vaihe 6/12');
      assert.equal(shown.relationships[0].name, 'Kuukausi–Onnenpilari · Runkojen yhdistelmä');
      await click(page, '[data-chart-lang="en"]');
      await page.locator('#chart-view:not([aria-busy])').waitFor();
      assert.equal(await linkPart(page, 'gender'), 'female');
      assert.equal(await linkPart(page, 'lang'), 'en');
      // The decade still stands in the chart; the page closed with the old language.
      assert.equal(await linkPart(page, 'luck'), '5/stem');
      assert.deepEqual([(await column(page)).state, (await column(page)).mark], ['on', 'Stem phase until 2028']);
      assert.deepEqual((await ribbon(page)).map((group) => group.name),
        ['Before', 'West · Autumn', 'North · Winter', 'East · Spring', 'South · Summer']);
    });

    check('a chart with a gender opens natal, its fifth column kept, and L shows the decade without moving anything', async (page) => {
      await openSample(page);
      assert.deepEqual(await column(page), {
        state: 'off', inert: true, poetic: '5 of 10 · 2023–2033', name: '己丑 Ji Chou', mark: '', parts: ['己:-', '丑:-'], setAside: null,
      });
      assert.equal(await page.locator('.luck-ghost').textContent(), 'L shows the luck pillar');
      const switched = () => page.locator('#luck-switch button').evaluateAll((nodes) =>
        nodes.map((node) => `${node.textContent} ${node.getAttribute('aria-pressed')}`));
      assert.deepEqual(await switched(), ['Natal true', 'With luck false']);
      assert.equal(await linkPart(page, 'luck'), null);
      // Every card, panel and arc stands where it stood, in every display and at every width.
      const widths = profile.name === 'desktop' ? [1440, 1024, 900, 700] : [profile.viewport.width, 320];
      const failures = [];
      for (const display of ['characters', 'ten-gods', 'hidden-stems']) {
        await showDisplay(page, display);
        for (const width of widths) {
          await page.setViewportSize({ width, height: profile.viewport.height });
          await page.locator('.card.stem[data-pillar="year"]').focus();
          // The pointer rests clear of the cards: a branch under it lifts.
          await page.mouse.move(0, 0);
          await settled(page);
          const off = await boxes(page);
          const seen = await page.locator('.pillar.is-luck .card-face, .pillar.is-luck .hidden-stem-item').evaluateAll((nodes) =>
            nodes.filter((node) => node.checkVisibility({ checkVisibilityCSS: true })).length);
          if (seen > 0) failures.push(`${display} ${width}px: ${seen} parts of the hidden luck pillar show`);
          await page.keyboard.press('l');
          await settled(page);
          const on = await boxes(page);
          on.forEach((box, at) => { if (box !== off[at]) failures.push(`${display} ${width}px: ${off[at]} → ${box}`); });
          await page.keyboard.press('l');
          await settled(page);
        }
      }
      assert.deepEqual(failures, []);
      await page.setViewportSize(profile.viewport);
      await showDisplay(page, 'characters');
      // A branch opened by hand keeps its room as L hides and shows the luck pillar.
      await page.locator('.card.stem[data-pillar="year"]').focus();
      await page.keyboard.press('l');
      await click(page, '.card.branch[data-pillar="luck"]');
      await page.mouse.move(0, 0);
      await settled(page);
      const opened = await boxes(page);
      await page.locator('.card.stem[data-pillar="year"]').focus();
      await page.keyboard.press('l');
      await settled(page);
      assert.deepEqual(await boxes(page), opened);
      await page.keyboard.press('l');
      await settled(page);
      assert.equal(await page.locator('.card.branch[data-pillar="luck"]').getAttribute('aria-expanded'), 'true');
      await page.keyboard.press('l');
      await settled(page);
      // The switch does what L does.
      await click(page, '#luck-switch [data-luck-show="on"]');
      assert.deepEqual(await switched(), ['Natal false', 'With luck true']);
      assert.deepEqual(await column(page), {
        state: 'on', inert: false, poetic: '5 of 10 · 2023–2033', name: '己丑 Ji Chou', mark: 'Stem phase until 2028',
        parts: ['己:leading', '丑:acting'], setAside: null,
      });
      assert.equal(await linkPart(page, 'luck'), '5/stem');
      assert.equal(await page.locator('#luck-status').textContent(), 'Luck pillar shown.');
      // In the branch phase the stem is set aside.
      await click(page, '[data-luck-step="1"]');
      assert.deepEqual((await column(page)).parts, ['己:resting', '丑:leading']);
      assert.equal((await column(page)).setAside, 'Set aside');
      assert.equal((await column(page)).mark, 'Branch phase until 2033');
      await screenshot(page, `${profile.name}-luck-column`);
      await click(page, '#luck-switch [data-luck-show="off"]');
      assert.equal((await column(page)).state, 'off');
      assert.equal(await linkPart(page, 'luck'), null);
    });

    check('the keys move the luck pillar while the chart has focus: [ and ] a phase, { and } a decade, N to now, L', async (page) => {
      await openSample(page);
      // Keys act only while the chart has focus (WCAG 2.1.4).
      await page.locator('body').click({ position: { x: 1, y: 1 } });
      await page.keyboard.press(']');
      assert.equal(await linkPart(page, 'luck'), null);
      await page.locator('.card.stem[data-pillar="hour"]').focus();
      const moves = [];
      for (const key of [']', '}', '{', '{', '[']) {
        await page.keyboard.press(key);
        moves.push(await linkPart(page, 'luck'));
      }
      assert.deepEqual(moves, ['5/branch', '6/stem', '5/stem', '4/stem', '3/branch']);
      assert.equal(await linkPart(page, 'topic'), null);
      await page.keyboard.press('n');
      await settled(page);
      assert.deepEqual([await linkPart(page, 'luck'), await linkPart(page, 'topic')], ['5/stem', 'luck/5/stem']);
      // L hides the luck pillar, and its page with it; L again shows it where it was.
      await page.locator('.card.stem[data-pillar="hour"]').focus();
      await page.keyboard.press('l');
      await settled(page);
      assert.deepEqual([await linkPart(page, 'luck'), await linkPart(page, 'topic')], [null, null]);
      assert.equal(await page.locator('#luck-status').textContent(), 'Luck pillar hidden.');
      await page.keyboard.press('Shift+L');
      assert.equal(await linkPart(page, 'luck'), '5/stem');
      // L from the open page closes it with the luck pillar, and focus goes to the chip.
      await page.keyboard.press('n');
      await settled(page);
      await page.locator('[data-luck-phase="branch"]').focus();
      await page.keyboard.press('l');
      await settled(page);
      assert.deepEqual([await linkPart(page, 'luck'), await linkPart(page, 'topic'), await focused(page)], [null, null, 'chip 5']);
      await page.keyboard.press('l');
      assert.equal(await linkPart(page, 'luck'), '5/stem');
      // At the last decade a decade's step stays where it is, in either phase.
      const ends = [];
      for (const key of ['}', '}', '}', '}', '}', '}', ']', '}']) {
        await page.keyboard.press(key);
        ends.push(await linkPart(page, 'luck'));
      }
      assert.deepEqual(ends, ['6/stem', '7/stem', '8/stem', '9/stem', '10/stem', '10/stem', '10/branch', '10/branch']);
      await page.keyboard.press('n');
      await settled(page);
      await page.locator('.card.stem[data-pillar="hour"]').focus();
      // ? lists them.
      await page.keyboard.press('?');
      assert.deepEqual(await page.locator('#keys-dialog .key-row-luck dd').evaluateAll((nodes) =>
        nodes.filter((node) => node.checkVisibility()).map((node) => node.textContent)),
      ['Shows and hides the luck pillar', 'A phase back or forward', 'A decade back or forward', 'The luck pillar now']);
      await page.keyboard.press('Escape');
      // A chart without a gender has none of them.
      await openChart(page);
      await page.locator('.card.stem[data-pillar="hour"]').focus();
      await page.keyboard.press('l');
      await page.keyboard.press('?');
      assert.equal(await page.locator('#keys-dialog .key-row-luck:not(.hidden)').count(), 0);
      assert.equal(await page.locator('.pillar.is-luck').count(), 0);
      assert.equal(await page.locator('#luck-switch').isVisible(), false);
    });

    check('the luck pillar\'s cards show what every card shows, and the cards\' keys reach them while it shows', async (page) => {
      await openSample(page);
      await showDisplay(page, 'ten-gods');
      await click(page, '#luck-switch [data-luck-show="on"]');
      await settled(page);
      const backs = () => page.locator('.pillar.is-luck').evaluate((node) => ({
        flipped: node.querySelectorAll('.card.is-flipped').length,
        stem: node.querySelector('.card.stem .ten-god-name').textContent,
        branch: [...node.querySelectorAll('.card.branch .hidden-stem-item')].map((item) => item.textContent.replace(/\s+/g, ' ').trim()),
      }));
      assert.deepEqual(await backs(), { flipped: 2, stem: 'Direct Officer', branch: ['Direct Officer Main', 'Rob Wealth Mid', 'Direct Resource Residual'] });
      assert.equal(await page.locator('#display-switch button[data-display="ten-gods"]').getAttribute('aria-pressed'), 'true');
      await showDisplay(page, 'hidden-stems');
      assert.deepEqual(await page.locator('#hidden-stems-luck.is-expanded .hidden-stem-item').evaluateAll((nodes) =>
        nodes.map((node) => node.textContent.replace(/\s+/g, ' ').trim())), ['Yin Earth Main', 'Yin Water Mid', 'Yin Metal Residual']);
      await showDisplay(page, 'characters');
      // The arrows reach the luck pillar after the Year, while it shows.
      await page.locator('.card.stem[data-pillar="year"]').focus();
      await page.keyboard.press('ArrowRight');
      assert.equal(await focused(page), 'luck stem');
      await page.keyboard.press('ArrowRight');
      assert.equal(await focused(page), 'luck stem');
      await page.keyboard.press('ArrowDown');
      assert.equal(await focused(page), 'luck branch');
      await page.keyboard.press('Enter');
      await settled(page);
      assert.equal(await page.locator('.card.branch[data-pillar="luck"]').getAttribute('aria-expanded'), 'true');
      await page.keyboard.press('t');
      await settled(page);
      assert.equal(await page.locator('#display-switch button[data-display="characters"]').getAttribute('aria-pressed'), 'mixed');
      // R opens the decade's page.
      await page.keyboard.press('r');
      await settled(page);
      assert.equal(await linkPart(page, 'topic'), 'luck/5/stem');
      // Hidden, the luck pillar's cards take no focus: it goes to the Year's.
      await page.locator('.card.branch[data-pillar="luck"]').focus();
      await page.keyboard.press('l');
      await settled(page);
      assert.equal(await focused(page), 'year branch');
      await page.keyboard.press('ArrowRight');
      assert.equal(await focused(page), 'year branch');
    });

    check('after a luck card had focus, a change of language, of convention or of chart draws the chart', async (page) => {
      await openSample(page);
      const reachLuck = async () => {
        await click(page, '#luck-switch [data-luck-show="on"]');
        await page.locator('.card.stem[data-pillar="year"]').focus();
        await page.keyboard.press('ArrowRight');
        assert.equal(await focused(page), 'luck stem');
      };
      await reachLuck();
      await click(page, '[data-chart-lang="fi"]');
      await page.locator('#chart-view:not([aria-busy])').waitFor();
      assert.equal(await page.locator('#form-error').isVisible(), false);
      assert.deepEqual([await linkPart(page, 'lang'), await linkPart(page, 'luck')], ['fi', '5/stem']);
      assert.equal(await page.locator('.card[tabindex="0"]').getAttribute('data-pillar'), 'year');
      // Another chart, through the address, as Back and Forward reach one.
      await reachLuck();
      const other = sampleLink({ date: '1975-08-15', lang: 'fi' });
      await page.evaluate((hash) => { location.hash = hash; }, other.slice(other.indexOf('#')));
      await page.waitForFunction(() => new URLSearchParams(location.hash.split('?')[1]).get('date') === '1975-08-15'
        && !document.getElementById('chart-view').hasAttribute('aria-busy'));
      await settled(page);
      assert.equal(await page.locator('#form-error').isVisible(), false);
      assert.equal(await page.locator('#chart-view').isVisible(), true);
      assert.equal(await page.locator('.pillar.is-luck').count(), 1);
    });

    check('a link names the luck pillar standing in the chart, with or without its page', async (page) => {
      await page.clock.setFixedTime(TODAY);
      await openLink(page, sampleLink({ luck: '5/branch' }), { place: HELSINKI });
      assert.deepEqual([await linkPart(page, 'luck'), await linkPart(page, 'topic')], ['5/branch', null]);
      assert.deepEqual((await column(page)).parts, ['己:resting', '丑:leading']);
      assert.deepEqual(await ribbonState(page), {
        expanded: [], selected: ['5'], today: ['5'], chosenPhase: ['5/branch'], todayPhase: ['5/stem'], stop: ['5'], todayDisabled: false,
      });
      await page.goto('about:blank');
      await openLink(page, sampleLink({ luck: 'before' }), { place: HELSINKI });
      assert.deepEqual(await column(page), {
        state: 'none', inert: false, poetic: '1975–1983', name: '乙酉 Before', mark: 'No luck pillar until age 8',
        parts: ['乙:-', '酉:-'], setAside: null,
      });
      await page.goto('about:blank');
      await openLink(page, sampleLink({ luck: '4/stem', topic: 'luck/4/stem', display: 'ten-gods' }), { place: HELSINKI });
      assert.deepEqual([await linkPart(page, 'luck'), await linkPart(page, 'topic')], ['4/stem', 'luck/4/stem']);
      assert.equal(await page.locator('.pillar.is-luck .card.is-flipped').count(), 2);
      assert.equal((await decadePage(page)).title, '戊子 Wu Zi');
    });

    check('on a phone the luck pillar stands above the two-by-two chart, its stem beside its branch', async (page) => {
      await openSample(page);
      await click(page, '#luck-switch [data-luck-show="on"]');
      const at = await page.evaluate(() => Object.fromEntries([...document.querySelectorAll('#pillars .card')].map((card) => {
        const box = card.getBoundingClientRect();
        return [`${card.dataset.pillar} ${card.classList.contains('stem') ? 'stem' : 'branch'}`, { x: box.x, y: box.y + scrollY, bottom: box.bottom + scrollY }];
      })));
      if (profile.name === 'mobile') {
        assert.ok(at['luck stem'].x < at['luck branch'].x && at['luck stem'].y === at['luck branch'].y, JSON.stringify(at));
        assert.ok(at['luck branch'].bottom < at['hour stem'].y, JSON.stringify(at));
        assert.ok(at['hour stem'].y === at['day stem'].y && at['month stem'].y > at['hour branch'].bottom, JSON.stringify(at));
      } else {
        // Beside the Year, in the cards' own rows.
        assert.ok(at['luck stem'].x > at['year stem'].x && at['luck stem'].y === at['year stem'].y && at['luck branch'].y === at['year branch'].y, JSON.stringify(at));
      }
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    });

    check('on paper a luck pillar shown stands fifth, and a hidden one leaves the chart its four columns', async (page) => {
      await openSample(page);
      await page.setViewportSize({ width: 1024, height: 900 });
      await page.emulateMedia({ media: 'print' });
      const placed = () => page.evaluate(() => Object.fromEntries([...document.querySelectorAll('#pillars .card.stem')]
        .filter((card) => card.getClientRects().length > 0)
        .map((card) => [card.dataset.pillar, Math.round(card.getBoundingClientRect().left)])));
      const hidden = await placed();
      assert.deepEqual(Object.keys(hidden), ['hour', 'day', 'month', 'year']);
      await page.emulateMedia({ media: 'screen' });
      await click(page, '#luck-switch [data-luck-show="on"]');
      await page.emulateMedia({ media: 'print' });
      const shown = await placed();
      assert.deepEqual(Object.keys(shown), ['hour', 'day', 'month', 'year', 'luck']);
      assert.ok(shown.luck > shown.year, JSON.stringify(shown));
      const tops = await page.locator('#pillars .card.stem').evaluateAll((cards) => new Set(cards.map((card) => Math.round(card.getBoundingClientRect().top))).size);
      assert.equal(tops, 1);
      await page.emulateMedia({ media: 'screen' });
    });

    check('the commands offer the years before the decades and each decade', async (page) => {
      await openSample(page);
      await page.keyboard.press('ControlOrMeta+k');
      await page.keyboard.type('luck pillars');
      const options = await page.locator('.palette-option').evaluateAll((nodes) =>
        nodes.map((node) => node.textContent.replace(/\s+/g, ' ').trim()));
      assert.deepEqual(options, [
        'Before the first luck pillar, age 0 to 8 Luck pillars',
        ...DECADES.map(([chars, names, from, to, age]) => `${names}, ${from} to ${to}, age ${age}${chars === '己丑' ? ', now' : ''} Luck pillars`),
      ]);
      await page.keyboard.type(' wu zi');
      await page.keyboard.press('Enter');
      await settled(page);
      assert.equal(await linkPart(page, 'topic'), 'luck/4/stem');
    });
  });
}
