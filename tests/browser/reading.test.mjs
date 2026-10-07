// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Readings: the canon's taxonomy in the pages the chart already has. In English each page
// reads the canon's words for this chart, one line each, and the rest opens in place; the
// cards stay as they are. A Finnish chart asks for no reading and shows none.
import {
  assert, describe, it, engineName, profiles, openChart, openRelationships, settled, geometry, natalColors,
  screenshot, withPage, HELSINKI,
} from './chart-helpers.mjs';

// The canon's own example (canon/Background.md): 癸卯 壬子 甲午 丙辰, Yang Water on the Rat.
const EXAMPLE = { lang: 'en', place: HELSINKI, date: '1976-06-29', time: '07:02' };
// Charts with each kind of relationship, each well clear of an hour's or a month's change.
const JIA_JI_WITH_THE_DAY_MASTER = { lang: 'en', place: HELSINKI, date: '1990-01-09', time: '06:40' };
const YI_GENG_YEAR_AND_HOUR = { lang: 'en', place: HELSINKI, date: '1990-02-11', time: '10:40' };
const METAL_FRAME = { lang: 'en', place: HELSINKI, date: '1990-01-09', time: '18:40' };
const ZI_WU_IN_WINTER = { lang: 'en', place: HELSINKI, date: '1990-12-11', time: '06:40' };

const PILLAR_PARTS = ['lens', 'stem', 'own-stage', 'ground', 'ground-about', 'meets', 'stage', 'about-pillar'];
const DAY_MASTER_PARTS = ['dm-core', 'dm-grounds', 'dm-lens-hour', 'dm-lens-day', 'dm-lens-month', 'dm-lens-year',
  'dm-cycle', 'dm-stages', 'dm-reconception', 'about-lens'];

// The canon's text as a reader sees it: its two inline marks are type, not characters, and
// its arrow is drawn.
const plain = (text) => text.replace(/\*\*([^*]+)\*\*/g, '$1').replace(/\*([^*]+)\*/g, '$1').replace(/→/g, '')
  .replace(/\s+/g, ' ').trim();
// A passage's words: a paragraph after the first says its own label (the first gives its
// label to the line's key).
const words = (paragraphs) => plain(paragraphs.map((p, i) => (i > 0 && p.label !== null ? `${p.label}: ${p.text}` : p.text)).join(' '));
const firstSentence = (text) => text.split(/(?<=[.!?])\s+/)[0];
const topicOf = (page) => page.evaluate(() => new URLSearchParams(location.hash.slice('#chart?'.length)).get('topic'));

// The lines of the page open in the panel: their kind, key and first sentence, and whether
// they are open.
function lines(page, section) {
  return page.locator(`${section} .canon-line`).evaluateAll((nodes) => nodes.map((node) => ({
    part: node.dataset.canonPart,
    key: node.querySelector('.canon-line-key').textContent.replace(/\s+/g, ' ').trim(),
    head: node.querySelector('.canon-line-head').textContent.replace(/\s+/g, ' ').trim(),
    open: node.querySelector('.canon-line-toggle').getAttribute('aria-expanded') === 'true',
    shown: node.querySelector('.canon-line-passage').checkVisibility(),
    arrived: node.classList.contains('is-arrived'),
  })));
}

// Everything a line reads, once open: its first sentence and the passage beneath it.
function readOf(page, section, part) {
  return page.locator(`${section} .canon-line[data-canon-part="${part}"]`).evaluate((node) => [
    node.querySelector('.canon-line-head').textContent,
    ...[...node.querySelectorAll('.canon-line-passage .canon-text')].map((p) => p.textContent),
  ].join(' ').replace(/\s+/g, ' ').trim());
}

async function toggle(page, section, part) {
  await page.locator(`${section} .canon-line[data-canon-part="${part}"] .canon-line-toggle`).click();
}

async function openAll(page, section) {
  for (const button of await page.locator(`${section} .canon-line-toggle`).all()) {
    if (await button.getAttribute('aria-expanded') === 'false') await button.click();
  }
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / readings`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 60000 }, () => withPage(profile, run));

    check('an English chart asks for the canon\'s reading; a Finnish chart asks for none and shows none', async (page) => {
      const asked = [];
      page.on('request', (request) => {
        if (request.url().endsWith('/api/four_pillars')) asked.push(request.postDataJSON().include_reading);
      });
      const english = await openChart(page, EXAMPLE);
      assert.equal(english.reading.policy, 'canon_taxonomy_v1');
      assert.equal(await page.locator('#day-master-heading .canon-day-master-line').count(), 1);
      await page.locator('.canon-day-master-line').click();
      assert.equal(await page.locator('#context-detail .canon-line').count(), DAY_MASTER_PARTS.length);

      const finnish = await openChart(page, { ...EXAMPLE, lang: 'fi' });
      assert.equal(finnish.reading, undefined);
      assert.deepEqual(asked, [true, false]);
      const empty = async (state) => {
        assert.equal(await page.locator('.canon-line, .canon-lines, .canon-chip-line, .canon-day-master-line').count(), 0, state);
      };
      await empty('fi chart');
      assert.equal(await page.locator('#relationship-about').innerHTML(), '');
      assert.equal(await page.locator('#day-master-heading').innerHTML(), 'Päivän mestari · Ren — Yang Vesi');
      await page.locator('.pillar-identity[data-pillar="hour"]').click();
      await empty('fi hour pillar');
      await openRelationships(page);
      await empty('fi relationships');
      // Each relationship's page, in Finnish, holds no reading either.
      for (const chip of await page.locator('.relationship-chip').all()) {
        await chip.click();
        await empty(`fi relationship ${await chip.getAttribute('data-relationship')}`);
      }
      for (const topic of ['season', 'roots', 'roles']) {
        await page.locator(`#context-controls button[data-context="${topic}"]`).click();
        await empty(`fi ${topic}`);
      }
      await page.locator('button.role-choice[data-role="rob_wealth"]').click();
      await empty('fi role');

      // In place, the other language asks again: the readings come and go with English.
      await page.locator('button[data-chart-lang="en"]').click();
      await page.waitForFunction(() => !document.getElementById('chart-view').hasAttribute('aria-busy'));
      assert.equal(await page.locator('#day-master-heading .canon-day-master-line').count(), 1);
      await page.locator('button[data-chart-lang="fi"]').click();
      await page.waitForFunction(() => !document.getElementById('chart-view').hasAttribute('aria-busy'));
      await empty('fi again');
      assert.deepEqual(asked, [true, false, true, false]);
    });

    check('a pillar\'s page reads the canon\'s words for this chart, a line each, and opens them in place', async (page) => {
      const { reading } = await openChart(page, EXAMPLE);
      const colors = await natalColors(page);
      await page.locator('.pillar-identity[data-pillar="hour"]').click();
      const before = await geometry(page);
      const hour = await lines(page, '#pillar-detail');
      assert.deepEqual(hour.map((line) => line.part), PILLAR_PARTS);
      assert.deepEqual(hour.map((line) => line.key), [
        'Your Water in the Hour', 'Who stands here · Rob Wealth', 'Rob Wealth’s own stage here · Birth 长生',
        'The ground · Rabbit', 'About the Rabbit', 'Your Water on this ground · 壬 on 卯',
        'Your Water’s stage here · Death 死', 'About these readings',
      ]);
      assert.deepEqual(hour.filter((line) => line.open || line.shown), []);
      // Each line's first sentence is its passage's own, and open, it reads the whole passage.
      const r = reading.pillars.hour;
      const passages = {
        lens: r.lens, stem: r.stem_reading.paragraphs, 'own-stage': r.own_stage.paragraphs, ground: r.ground,
        'ground-about': r.ground_about, meets: r.meets, stage: r.stage.paragraphs,
        'about-pillar': [...reading.branches_introduction, ...reading.day_master.grounds_introduction],
      };
      for (const line of hour) assert.equal(line.head, plain(firstSentence(passages[line.part][0].text)), line.part);
      await openAll(page, '#pillar-detail');
      for (const [part, paragraphs] of Object.entries(passages)) {
        assert.equal(await readOf(page, '#pillar-detail', part), words(paragraphs), part);
      }
      await screenshot(page, `${profile.name}-reading-pillar`);
      // Closed again, a line keeps only its first sentence.
      await toggle(page, '#pillar-detail', 'stem');
      assert.equal((await lines(page, '#pillar-detail')).find((line) => line.part === 'stem').shown, false);
      // Nothing on the chart moved or changed colour.
      assert.deepEqual(await geometry(page), before);
      assert.deepEqual(await natalColors(page), colors);

      // What is open stays open on the next page that has it; the Day Master has no stage
      // of its own on its seat, and its stem reads as the Day Master.
      await page.locator('.pillar-identity[data-pillar="day"]').click();
      const day = await lines(page, '#pillar-detail');
      assert.deepEqual(day.map((line) => line.part), PILLAR_PARTS.filter((part) => part !== 'own-stage'));
      assert.deepEqual(day.filter((line) => line.open).map((line) => line.part),
        ['lens', 'ground', 'ground-about', 'meets', 'stage', 'about-pillar']);
      assert.equal(day.find((line) => line.part === 'stem').key, 'Who stands here · the Day Master');
      assert.equal(day.find((line) => line.part === 'meets').key, 'Your seat · 壬 on 子');
      assert.equal(await readOf(page, '#pillar-detail', 'meets'), words(reading.pillars.day.meets));
    });

    check('the Day Master line opens the Day Master\'s own page, which its link keeps', async (page) => {
      const { reading } = await openChart(page, EXAMPLE);
      const line = page.locator('.canon-day-master-line');
      assert.equal(await line.textContent(), 'Day Master · Ren — Yang Water');
      await line.click();
      assert.equal(await line.getAttribute('aria-expanded'), 'true');
      assert.equal(await topicOf(page), 'day-master');
      assert.equal(await page.locator('#context-detail h3').textContent(), 'Day Master · Ren — Yang Water');
      const page1 = await lines(page, '#context-detail');
      assert.deepEqual(page1.map((l) => l.part), DAY_MASTER_PARTS);
      // Where Yang Water stands on each branch, from the year to the hour.
      assert.equal(page1.find((l) => l.part === 'dm-cycle').head, 'Tomb · Embryo · Emperor\'s Peak · Death');
      await toggle(page, '#context-detail', 'dm-cycle');
      assert.deepEqual(await page.locator('.canon-clause').allTextContents(),
        ['year', 'month', 'day', 'hour'].map((name) => plain(firstSentence(reading.pillars[name].stage.paragraphs[0].text))));
      assert.equal(await page.locator('.canon-ring .canon-ring-on').count(), 4);
      assert.deepEqual((await page.locator('.canon-ring-pillar').allTextContents()).sort(), ['DAY', 'HOUR', 'MONTH', 'YEAR']);
      assert.equal(await readOf(page, '#context-detail', 'dm-core'), words(reading.day_master.core));
      await screenshot(page, `${profile.name}-reading-day-master`);

      // The link opens the page again; what was open is a reader's own, and opens closed.
      await page.reload();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      assert.equal(await page.locator('#context-detail h3').textContent(), 'Day Master · Ren — Yang Water');
      assert.equal(await page.locator('.canon-day-master-line').getAttribute('aria-expanded'), 'true');
      assert.deepEqual((await lines(page, '#context-detail')).filter((l) => l.open), []);
      // Escape closes it and gives focus back to the line that opened it.
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#chart-panel').isHidden(), true);
      assert.equal(await page.evaluate(() => document.activeElement.matches('.canon-day-master-line')), true);
      assert.equal(await topicOf(page), null);
    });

    check('a reading\'s link opens the page it names at the line it names, a step in the history', async (page) => {
      await openChart(page, EXAMPLE);
      await page.locator('.canon-day-master-line').click();
      await toggle(page, '#context-detail', 'dm-lens-year');
      await page.locator('#context-detail .canon-line[data-canon-part="dm-lens-year"] .canon-link').click();
      assert.equal(await topicOf(page), 'pillar/year');
      const lens = (await lines(page, '#pillar-detail')).find((line) => line.part === 'lens');
      assert.deepEqual([lens.open, lens.shown, lens.arrived], [true, true, true]);
      await page.goBack();
      await page.waitForFunction(() => new URLSearchParams(location.hash.slice('#chart?'.length)).get('topic') === 'day-master');

      // A pillar's relationships, with the canon's first sentence for each.
      await page.locator('.pillar-identity[data-pillar="month"]').click();
      const here = page.locator('#pillar-detail .canon-here .canon-link');
      assert.deepEqual(await here.allTextContents(), ['Day–Month · Branch clashThe career collides with the self.']);
      await here.click();
      assert.equal(await topicOf(page), 'relationships/branch_clash:12:month-day');

      // The stage's link opens the whole cycle, open.
      await page.locator('.pillar-identity[data-pillar="hour"]').click();
      await toggle(page, '#pillar-detail', 'stage');
      await page.locator('#pillar-detail .canon-line[data-canon-part="stage"] .canon-link').click();
      assert.equal(await topicOf(page), 'day-master');
      const cycle = (await lines(page, '#context-detail')).find((line) => line.part === 'dm-cycle');
      assert.deepEqual([cycle.open, cycle.arrived], [true, true]);
      // A clause of the cycle opens its pillar at its stage.
      await page.locator('.canon-clause').nth(2).click();
      assert.equal(await topicOf(page), 'pillar/day');
      const stage = (await lines(page, '#pillar-detail')).find((line) => line.part === 'stage');
      assert.deepEqual([stage.open, stage.arrived], [true, true]);
      // A role's link opens the role.
      await toggle(page, '#pillar-detail', 'ground');
      await page.locator('#pillar-detail .canon-line[data-canon-part="ground"] .canon-link', { hasText: 'Rob Wealth' }).click();
      assert.equal(await topicOf(page), 'roles/rob_wealth');
      assert.equal((await lines(page, '#context-detail')).find((line) => line.part === 'role-core').key,
        'What it is · same element, opposite polarity');
    });

    if (profile.name === 'desktop') {
      check('R reads the focused card, and while a pillar\'s page is open the arrow keys turn it', async (page) => {
        await openChart(page, EXAMPLE);
        await page.locator('.pillar-identity[data-pillar="hour"]').focus();
        await page.keyboard.press(engineName === 'webkit' ? 'Alt+Tab' : 'Tab');
        assert.equal(await page.locator('.card-hint').textContent(), 'R: read · T: Ten Gods');
        await page.keyboard.press('r');
        assert.equal(await topicOf(page), 'pillar/hour');
        const opened = async () => (await lines(page, '#pillar-detail')).filter((line) => line.open).map((line) => line.part);
        const arrived = async () => (await lines(page, '#pillar-detail')).filter((line) => line.arrived).map((line) => line.part);
        assert.deepEqual([await opened(), await arrived()], [['stem'], ['stem']]);
        assert.equal(await page.evaluate(() => document.activeElement.matches('.card.stem[data-pillar="hour"]')), true);
        await page.keyboard.press('ArrowRight');
        assert.equal(await topicOf(page), 'pillar/day');
        assert.deepEqual([await opened(), await arrived()], [['stem'], ['stem']]);
        await page.keyboard.press('ArrowDown');
        assert.equal(await page.locator('.card-hint').textContent(), 'Enter: hidden stems · R: read · T: Ten Gods');
        assert.deepEqual([await topicOf(page), await arrived()], ['pillar/day', ['ground']]);
        await page.keyboard.press('ArrowRight');
        assert.deepEqual([await topicOf(page), await opened(), await arrived()], ['pillar/month', ['stem'], ['ground']]);
        // Each page a step back.
        await page.goBack();
        await page.waitForFunction(() => new URLSearchParams(location.hash.slice('#chart?'.length)).get('topic') === 'pillar/day');
        // In Finnish there is no reading to open.
        await openChart(page, { ...EXAMPLE, lang: 'fi' });
        await page.locator('.pillar-identity[data-pillar="hour"]').focus();
        await page.keyboard.press(engineName === 'webkit' ? 'Alt+Tab' : 'Tab');
        await page.keyboard.press('r');
        assert.equal(await topicOf(page), null);
      });

      check('a full panel keeps the page\'s margins: the page does not scroll, and the chart stays put', async (page) => {
        await openChart(page, EXAMPLE);
        await page.locator('button[data-context="season"]').click();
        const beside = await geometry(page);
        const open = {
          "the Day Master's page": () => page.locator('.canon-day-master-line').click(),
          roles: () => page.locator('button[data-context="roles"]').click(),
          'a role': () => page.locator('button.role-choice[data-role="rob_wealth"]').click(),
          "the hour's page": () => page.locator('.pillar-identity[data-pillar="hour"]').click(),
        };
        for (const [name, run] of Object.entries(open)) {
          await run();
          await settled(page);
          const { panel, room } = await page.evaluate(() => ({
            panel: document.getElementById('chart-panel').scrollHeight > document.getElementById('chart-panel').clientHeight,
            room: document.documentElement.scrollHeight - innerHeight,
          }));
          assert.equal(panel, true, `${name} fills the panel`);
          assert.ok(room <= 0, `${name}: the page scrolls by ${room}px`);
          assert.deepEqual(await geometry(page), beside, name);
        }
      });
    }

    check('relationships read their first sentence in the list, and their pairing, entry and condition', async (page) => {
      const { reading } = await openChart(page, EXAMPLE);
      await openRelationships(page);
      const id = 'branch_clash:12:month-day';
      const chip = page.locator(`.relationship-chip[data-relationship="${id}"]`);
      assert.equal(await chip.locator('.canon-chip-line').textContent(), 'The career collides with the self.');
      // Beside the clash: a half-frame, the Zi-Mao punishment and a harm, each family once.
      assert.deepEqual((await lines(page, '#relationship-about')).map((line) => [line.part, line.key]), [
        ['about-branch_clash', 'About clashes'], ['about-harmony_frame', 'About the three harmonies'],
        ['about-punishment', 'About punishments'], ['about-harm', 'About harms'],
      ]);
      // The commands name the relationship as the list does, without its reading.
      await page.keyboard.press('ControlOrMeta+k');
      await page.keyboard.type('clash');
      assert.deepEqual(await page.locator('.palette-option').evaluateAll((nodes) => nodes
        .map((node) => node.textContent.replace(/\s+/g, ' ').trim())), ['Day–Month · Branch clash Relationships']);
      await page.keyboard.press('Escape');
      await chip.click();
      assert.deepEqual((await lines(page, '#relationship-detail')).map((line) => [line.part, line.key]), [
        ['pairing', 'Month–Day'], ['entry', '子午冲 · Zi-Wu Clash (Rat vs Horse: Water vs Fire)'],
      ]);
      await toggle(page, '#relationship-detail', 'entry');
      const summer = reading.relationships[id].condition;
      assert.equal(summer.season, 'summer');
      assert.equal(await page.locator('#relationship-detail .canon-condition').textContent(),
        `In this chart: born in the Wu month, in summer. The entry reads ${summer.sentence}`);
      assert.equal(await readOf(page, '#relationship-detail', 'entry'), words(reading.relationships[id].entry.paragraphs));
      await screenshot(page, `${profile.name}-reading-relationship`);

      // The same clash, born in winter, reads the entry's winter sentence.
      const winter = await openChart(page, ZI_WU_IN_WINTER);
      await openRelationships(page);
      await page.locator('.relationship-chip[data-relationship="branch_clash:12:year-month"]').click();
      await toggle(page, '#relationship-detail', 'entry');
      assert.equal(await page.locator('#relationship-detail .canon-condition').textContent(),
        `In this chart: born in the Zi month, in winter. The entry reads ${winter.reading.relationships['branch_clash:12:year-month'].condition.sentence}`);
    });

    check('a stem combination names the Day Master\'s part in it, and a frame reads its entry', async (page) => {
      const withDayMaster = await openChart(page, JIA_JI_WITH_THE_DAY_MASTER);
      await openRelationships(page);
      await page.locator('.relationship-chip[data-relationship="stem_combination:1:year-day"]').click();
      const combination = withDayMaster.reading.relationships['stem_combination:1:year-day'];
      const found = await lines(page, '#relationship-detail');
      assert.deepEqual(found.map((line) => line.part), ['pairing', 'with-day-master', 'entry', 'dynamic', 'mechanics']);
      assert.equal(found[1].key, 'When Jia is the Day Master combining with Ji');
      assert.equal(found[1].key, combination.with_day_master.label);
      // The canon's arrow in the entry's title is drawn, and the words around it are its own.
      assert.equal(found[2].key, plain(combination.entry.title.replace(' — ', ' · ')));
      assert.equal(await page.locator('#relationship-detail .canon-line[data-canon-part="entry"] .canon-line-key .canon-arrow').count(), 1);

      const yearAndHour = await openChart(page, YI_GENG_YEAR_AND_HOUR);
      await openRelationships(page);
      await page.locator('.relationship-chip[data-relationship="stem_combination:2:year-hour"]').click();
      const apart = await lines(page, '#relationship-detail');
      assert.deepEqual(apart.map((line) => line.part), ['pairing', 'neither-day-master', 'entry', 'dynamic', 'mechanics']);
      // The canon's own label says what this pairing is in a natal chart.
      assert.equal(apart[0].key, 'Year–Hour (separated by two pillars — no bond in the natal chart)');
      assert.equal(apart[0].head, plain(firstSentence(yearAndHour.reading.relationships['stem_combination:2:year-hour'].pairing.text)));

      await openChart(page, METAL_FRAME);
      await openRelationships(page);
      await page.locator('.relationship-chip[data-relationship="harmony_frame:21:year-month-hour"]').click();
      assert.deepEqual((await lines(page, '#relationship-detail')).map((line) => line.part), ['entry']);
      assert.ok((await lines(page, '#relationship-about')).some((line) => line.part === 'about-harmony_frame'));
    });

    check('a reading that does not match its chart is refused', async (page) => {
      const refusals = {
        'The chart\'s reading is incomplete: the hour pillar.': (payload) => { payload.reading.pillars.hour.stem = '甲'; },
        'The chart\'s reading is incomplete: its policy.': (payload) => { payload.reading.policy = 'canon_taxonomy_v0'; },
        'The chart\'s reading is incomplete: the year stem\'s role.': (payload) => {
          payload.reading.pillars.year.stem_reading.ten_god = 'friend';
        },
        'Chart rendering failed.': (payload) => { delete payload.reading; },
      };
      for (const [message, mutate] of Object.entries(refusals)) {
        await openChart(page, { ...EXAMPLE, success: false }, mutate);
        assert.equal(await page.locator('#form-error').textContent(), message);
        assert.equal(await page.locator('#chart-view').isHidden(), true);
      }
    });

    check('on paper, open readings print as text, and their controls do not', async (page) => {
      await openChart(page, EXAMPLE);
      await page.locator('.canon-day-master-line').click();
      await toggle(page, '#context-detail', 'dm-cycle');
      await toggle(page, '#context-detail', 'dm-lens-year');
      await page.emulateMedia({ media: 'print' });
      const printed = await page.evaluate(() => {
        const shown = (selector) => [...document.querySelectorAll(selector)].filter((node) => node.checkVisibility()).length;
        return {
          lines: shown('#context-detail .canon-line'),
          passages: shown('#context-detail .canon-line-passage'),
          ring: shown('.canon-ring'),
          controls: shown('.canon-line-chevron') + shown('.canon-link') + shown('.canon-here'),
          underlined: getComputedStyle(document.querySelector('.canon-day-master-line')).textDecorationLine,
        };
      });
      assert.deepEqual(printed, { lines: DAY_MASTER_PARTS.length, passages: 2, ring: 1, controls: 0, underlined: 'none' });
    });
  });
}
