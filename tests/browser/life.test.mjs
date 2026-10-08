// Run with Node's built-in test runner and an explicitly selected Playwright install.
// The life grid of a chart asked for with a gender, while its luck pillar shows: under the
// chart, its five columns run on through the life, a row for each five years, a decade's
// stem phase over its branch phase. The Luck column holds the decades, and choosing a
// phase there chooses it everywhere; under each natal character a mark shows each
// relationship the luck pillar forms with it, for as long as it acts. Natal, there is no
// grid, as there is none without a gender.
import {
  assert, describe, it, engineName, profiles, openChart, openLink, settled, screenshot, withPage, HELSINKI,
} from './chart-helpers.mjs';
import { TODAY, sampleLink, openSample, linkPart, click, showLuck } from './luck-helpers.mjs';

const text = (node) => (node ? node.textContent.replace(/\s+/g, ' ').trim() : null);

// The grid as it reads: its title and meta, its head, its groups and its rows.
function grid(page) {
  return page.locator('#life').evaluate((life) => {
    const text = (node) => (node ? node.textContent.replace(/\s+/g, ' ').trim() : null);
    return {
      title: text(life.querySelector('#life-title')),
      meta: text(life.querySelector('#life-meta')),
      head: [...life.querySelectorAll('.life-head-cell')].map(text),
      groups: [...life.querySelectorAll('.life-group')].map(text),
      rows: [...life.querySelectorAll('[data-life]')].map((row) => row.dataset.life),
    };
  });
}

// A row as it reads: its tile, its name, the role it brings and its years, and what it
// says to a screen reader.
function row(page, path) {
  return page.locator(`#life [data-life="${path}"]`).evaluate((button) => {
    const text = (node) => (node ? node.textContent.replace(/\s+/g, ' ').trim() : null);
    return {
      tile: text(button.querySelector('.life-tile')),
      name: text(button.querySelector('.life-phase-name').firstChild),
      role: text(button.querySelector('.life-phase-role')),
      // As shown: the age at its start shows only with Pillars only.
      years: button.querySelector('.life-phase-years').innerText.replace(/\s+/g, ' ').trim(),
      label: button.getAttribute('aria-label'),
    };
  });
}

// A decade's marks: where each stands (its pillar and lane), what it is, what it names,
// how far down the decade it stands and how long its line runs; and its links.
function decadeMarks(page, sequence) {
  return page.locator(`#life .life-row[data-life-row="${sequence}"]`).evaluate((row) => ({
    marks: [...row.querySelectorAll('.life-mark')].map((mark) => [
      mark.closest('.life-cell').dataset.pillar, mark.dataset.lane, mark.dataset.relationship,
      mark.querySelector('b')?.textContent ?? '', mark.style.getPropertyValue('--at').trim(),
    ]),
    bars: [...row.querySelectorAll('.life-run')].map((bar) => [
      bar.closest('.life-cell').dataset.pillar, bar.dataset.lane, bar.style.getPropertyValue('--to').trim(),
    ]),
    links: [...row.querySelectorAll('.life-link')].map((link) => [link.dataset.relationship, link.style.gridColumn]),
  }));
}

// What is chosen and what is now, in the grid and its head.
function state(page) {
  return page.locator('#life').evaluate((life) => {
    const text = (node) => (node ? node.textContent.replace(/\s+/g, ' ').trim() : null);
    return {
      chosen: [...life.querySelectorAll('[data-life].is-chosen')].map((row) => row.dataset.life),
      expanded: [...life.querySelectorAll('[data-life][aria-expanded="true"]')].map((row) => row.dataset.life),
      now: [...life.querySelectorAll('[data-life].is-now')].map((row) => row.dataset.life),
      halves: [...life.querySelectorAll('.life-half.is-chosen')].map((half) => half.dataset.lifeHalf),
      resting: [...life.querySelectorAll('[data-life].is-resting')].map((row) => row.dataset.life),
      quiet: [...life.querySelectorAll('.life-mark.is-quiet')].map((mark) => mark.dataset.relationship),
      stop: [...life.querySelectorAll('[data-life][tabindex="0"]')].map((row) => row.dataset.life),
      luck: text(life.querySelector('.life-head-cell.is-luck')),
      ringed: [...life.querySelectorAll('.life-head-cell:not(.is-luck) .life-mini.is-ringed')]
        .map((mini) => `${mini.closest('[data-pillar]').dataset.pillar} ${mini.dataset.part}`),
      setAside: [...life.querySelectorAll('.life-head-cell.is-luck .life-mini.is-resting')].map((mini) => mini.dataset.part),
    };
  });
}

function focused(page) {
  return page.evaluate(() => {
    const node = document.activeElement;
    if (node.matches('#pillars .card')) return `${node.dataset.pillar} ${node.classList.contains('stem') ? 'stem' : 'branch'}`;
    if (node.dataset.life) return `row ${node.dataset.life}`;
    if (node.dataset.luck) return `chip ${node.dataset.luck}`;
    return node.id || node.textContent.replace(/\s+/g, ' ').trim();
  });
}

// A row chosen as a reader reaches it: scrolled to just under the grid's head, which
// stays at the top, and so clear of a page open as a sheet over the foot of a phone.
async function choose(page, path) {
  await page.locator(`#life [data-life="${path}"]`).evaluate((node) => {
    const head = document.getElementById('life-head');
    node.scrollIntoView({ block: 'start' });
    window.scrollBy(0, -(parseFloat(getComputedStyle(head).top) + head.offsetHeight + 8));
  });
  await click(page, `#life [data-life="${path}"]`);
}

const PHASE_ROWS = ['before', ...Array.from({ length: 10 }, (_, index) => [`${index + 1}/stem`, `${index + 1}/branch`]).flat()];

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / life grid`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 60000 }, () => withPage(profile, run));

    check('with its luck pillar a chart has its life under the chart, by phase and by direction; natal or without a gender, none', async (page) => {
      await page.clock.setFixedTime(TODAY);
      await openChart(page, { date: '1975-08-14', time: '07:45', place: HELSINKI });
      assert.equal(await page.locator('#life').isVisible(), false);
      await page.goto('about:blank');
      // A chart with a gender opens natal, without its grid; the luck pillar brings it.
      await openSample(page);
      assert.equal(await page.locator('#life').isVisible(), false);
      await showLuck(page);
      assert.equal(await page.locator('#life').isVisible(), true);
      const read = await grid(page);
      assert.equal(read.title, 'Life');
      assert.equal(read.meta, '10 decades from age 8, 1983–2083. Each row is five years: a decade’s stem phase, then its branch phase.');
      // The head: the chart, each stem beside its branch, and the luck pillar at today's phase.
      assert.deepEqual(read.head, [
        'Hour 甲 Jia 辰 Chen', 'Day 壬 Ren 辰 Chen', 'Month 甲 Jia 申 Shen', 'Year 乙 Yi 卯 Mao', 'Luck Stem phase 己 Ji 丑 Chou',
      ]);
      assert.deepEqual(read.groups, ['West · Autumn 1983–2003', 'North · Winter 2003–2033', 'East · Spring 2033–2063', 'South · Summer 2063–2083']);
      assert.deepEqual(read.rows, PHASE_ROWS);
      // Each phase: its character and name, the role it brings, and its years; on a phone,
      // the year it starts.
      const years = (from, to) => (profile.name === 'mobile' ? String(from) : `${from}–${to}`);
      assert.deepEqual(await row(page, 'before'), {
        tile: '', name: 'Before', role: 'No luck pillar', years: years(1975, 1983), label: 'Before the first luck pillar, age 0 to 8',
      });
      assert.deepEqual(await row(page, '5/stem'), {
        tile: '己', name: 'Ji', role: 'Direct Officer · new', years: years(2023, 2028), label: 'Ji Chou, Stem phase, 2023 to 2028, now',
      });
      // A branch brings the role of its main qi.
      assert.deepEqual(await row(page, '5/branch'), {
        tile: '丑', name: 'Chou', role: 'Direct Officer · new', years: years(2028, 2033), label: 'Ji Chou, Branch phase, 2028 to 2033',
      });
      assert.deepEqual(await row(page, '4/stem'), {
        tile: '戊', name: 'Wu', role: 'Seven Killings', years: years(2013, 2018), label: 'Wu Zi, Stem phase, 2013 to 2018',
      });
      await screenshot(page, `${profile.name}-life`);
    });

    check('its columns are the chart\'s, and each mark stands under what it touches', async (page) => {
      await openSample(page);
      await showLuck(page);
      if (profile.name === 'desktop') {
        for (const width of [1440, 1024, 900, 700]) {
          await page.setViewportSize({ width, height: 1000 });
          await settled(page);
          const columns = await page.evaluate(() => ['hour', 'day', 'month', 'year', 'luck'].map((pillar) => {
            const chart = document.querySelector(`#pillars .pillar[data-pillar="${pillar}"]`).getBoundingClientRect();
            const head = document.querySelector(`#life .life-head-cell[data-pillar="${pillar}"]`).getBoundingClientRect();
            return [pillar, Math.abs(chart.x - head.x) <= 1 && Math.abs(chart.width - head.width) <= 1];
          }));
          assert.deepEqual(columns, ['hour', 'day', 'month', 'year', 'luck'].map((pillar) => [pillar, true]), String(width));
          // A mark stands under the character in the head it touches.
          const misplaced = await page.evaluate(() => [...document.querySelectorAll('#life .life-mark')].filter((mark) => {
            const pillar = mark.closest('.life-cell').dataset.pillar;
            const mini = document.querySelector(`#life .life-head-cell[data-pillar="${pillar}"] .life-mini[data-part="${mark.dataset.lane}"]`).getBoundingClientRect();
            const box = mark.getBoundingClientRect();
            return Math.abs((box.left + box.right) / 2 - (mini.left + mini.right) / 2) > 1;
          }).map((mark) => mark.dataset.relationship));
          assert.deepEqual(misplaced, [], String(width));
        }
      }
      // 戊子 Wu Zi's Zi completes two Water frames, Day–Month and Hour–Month, and punishes the
      // Year's Mao: a branch's relationships, under the branches, for the whole decade. The
      // first natal member's mark names the characters, and a line joins the members.
      assert.deepEqual(await decadeMarks(page, 4), {
        marks: [
          ['hour', 'branch', 'harmony_frame:18:month-hour-luck', 'Chen-Shen-Zi', '0.5'],
          ['day', 'branch', 'harmony_frame:18:month-day-luck', 'Chen-Shen-Zi', '0.25'],
          ['month', 'branch', 'harmony_frame:18:month-day-luck', '', '0.25'],
          ['month', 'branch', 'harmony_frame:18:month-hour-luck', '', '0.5'],
          ['year', 'branch', 'punishment:34:year-luck', 'Mao-Zi', '0.75'],
        ],
        bars: [['hour', 'branch', '1'], ['day', 'branch', '1'], ['month', 'branch', '1'], ['year', 'branch', '1']],
        links: [['harmony_frame:18:month-day-luck', '2 / 4'], ['harmony_frame:18:month-hour-luck', '1 / 4']],
      });
      // 己丑 Ji Chou's Ji combines with the Month's and the Hour's Jia: a stem's, under the
      // stems, for the stem phase only.
      assert.deepEqual(await decadeMarks(page, 5), {
        marks: [
          ['hour', 'stem', 'stem_combination:1:hour-luck', 'Jia-Ji', '0.3333333333333333'],
          ['month', 'stem', 'stem_combination:1:month-luck', 'Jia-Ji', '0.16666666666666666'],
        ],
        bars: [['hour', 'stem', '0.5'], ['month', 'stem', '0.5']],
        links: [],
      });
      // A stem's line runs for its phase; a branch's for the decade.
      const lines = await page.evaluate(() => Object.fromEntries([4, 5].map((sequence) => {
        const decade = document.querySelector(`#life .life-row[data-life-row="${sequence}"] .life-block`).getBoundingClientRect();
        const bar = document.querySelector(`#life .life-row[data-life-row="${sequence}"] .life-run`).getBoundingClientRect();
        return [sequence, Math.round((bar.height / decade.height) * 10) / 10];
      })));
      assert.ok(lines[4] > 0.8 && lines[5] > 0.3 && lines[5] < 0.5, JSON.stringify(lines));
      // Marks are drawn on wide screens; on a phone their lines say it.
      const shown = await page.locator('#life .life-mark').evaluateAll((marks) => marks.filter((mark) => mark.getClientRects().length > 0).length);
      assert.equal(shown > 0, profile.name === 'desktop');
      assert.ok(await page.locator('#life .life-run').evaluateAll((bars) => bars.every((bar) => bar.getClientRects().length > 0)));
    });

    check('a phase chosen in the grid is chosen everywhere, and pressed again closes its page', async (page) => {
      await openSample(page);
      await showLuck(page);
      await choose(page, '4/branch');
      assert.equal(await linkPart(page, 'luck'), '4/branch');
      assert.equal(await linkPart(page, 'topic'), 'luck/4/branch');
      assert.equal(await page.locator('.pillar.is-luck').getAttribute('data-luck-state'), 'on');
      assert.equal(await page.locator('#luck-detail-title').textContent(), '戊子 Wu Zi');
      assert.deepEqual(await page.locator('#luck-ribbon .luck-chip.is-selected').evaluateAll((chips) => chips.map((chip) => chip.dataset.luck)), ['4']);
      assert.equal(await focused(page), 'row 4/branch');
      const chosen = await state(page);
      assert.deepEqual(chosen.chosen, ['4/branch']);
      assert.deepEqual(chosen.expanded, ['4/branch']);
      assert.deepEqual(chosen.halves, ['4/branch']);
      assert.deepEqual(chosen.stop, ['4/branch']);
      // In the branch phase the stem is set aside, in the grid and in its head; its
      // relationships ring the natal branches they touch.
      assert.deepEqual(chosen.resting, ['4/stem']);
      assert.equal(chosen.luck, 'Luck Branch phase 戊 Wu 子 Zi');
      assert.deepEqual(chosen.setAside, ['stem']);
      assert.deepEqual(chosen.ringed, ['hour branch', 'day branch', 'month branch', 'year branch']);
      // Pressed again, the page closes and the decade stays in the chart.
      await choose(page, '4/branch');
      assert.equal(await page.locator('#luck-detail').isVisible(), false);
      assert.equal(await linkPart(page, 'luck'), '4/branch');
      assert.deepEqual((await state(page)).expanded, []);
      assert.deepEqual((await state(page)).chosen, ['4/branch']);
      // 己丑 Ji Chou's stem phase: its stem combinations ring the stems; in its branch phase
      // they rest, and their marks grow quiet.
      await choose(page, '5/stem');
      assert.deepEqual((await state(page)).ringed, ['hour stem', 'month stem']);
      assert.deepEqual((await state(page)).quiet, []);
      await choose(page, '5/branch');
      assert.deepEqual((await state(page)).ringed, []);
      assert.deepEqual((await state(page)).quiet, ['stem_combination:1:hour-luck', 'stem_combination:1:month-luck']);
      await screenshot(page, `${profile.name}-life-chosen`);
    });

    check('a page opened from the grid gives focus back to its row; one opened from the ribbon, to its chip', async (page) => {
      await openSample(page);
      await showLuck(page);
      await choose(page, '4/stem');
      await page.keyboard.press('Escape');
      await settled(page);
      assert.equal(await page.locator('#luck-detail').isVisible(), false);
      assert.equal(await focused(page), 'row 4/stem');
      await choose(page, '4/stem');
      await click(page, '#chart-panel [data-close-panel]');
      assert.equal(await focused(page), 'row 4/stem');
      // The page's phases move the choice; closing then gives focus to the row now chosen.
      await choose(page, '2/branch');
      await click(page, '#luck-detail [data-luck-phase="stem"]');
      await page.keyboard.press('Escape');
      await settled(page);
      assert.equal(await focused(page), 'row 2/stem');
      // From the ribbon, as before, even when its chip takes over a page the grid opened.
      await click(page, '#luck-ribbon [data-luck="6"]');
      await click(page, '#chart-panel [data-close-panel]');
      assert.equal(await focused(page), 'chip 6');
      await choose(page, '3/stem');
      await click(page, '#luck-ribbon [data-luck="7"]');
      await click(page, '#chart-panel [data-close-panel]');
      assert.equal(await focused(page), 'chip 7');
      // N from a row opens today's page, and Escape gives focus back to today's row.
      await page.locator('#life [data-life="2/stem"]').focus();
      await page.keyboard.press('n');
      await settled(page);
      assert.equal(await linkPart(page, 'topic'), 'luck/5/stem');
      await page.keyboard.press('Escape');
      await settled(page);
      assert.equal(await focused(page), 'row 5/stem');
    });

    check('the rows take one tab stop, the arrows move between them, and the chart\'s keys act from them', async (page) => {
      await openSample(page);
      // The stop is the chosen phase's row: shown, the luck pillar stands at today's.
      await showLuck(page);
      assert.deepEqual((await state(page)).stop, ['5/stem']);
      await page.locator('#life [data-life="5/stem"]').focus();
      await page.keyboard.press('ArrowDown');
      assert.equal(await focused(page), 'row 5/branch');
      await page.keyboard.press('ArrowUp');
      await page.keyboard.press('ArrowUp');
      assert.equal(await focused(page), 'row 4/branch');
      await page.keyboard.press('Home');
      assert.equal(await focused(page), 'row before');
      await page.keyboard.press('End');
      assert.equal(await focused(page), 'row 10/branch');
      await page.keyboard.press('Enter');
      await settled(page);
      assert.equal(await linkPart(page, 'topic'), 'luck/10/branch');
      // The chart's keys act from a row: [ steps back, and focus stays on the row. L hides
      // the luck pillar and its grid with it, and focus goes to the chart's cards.
      await page.keyboard.press('[');
      await settled(page);
      assert.equal(await linkPart(page, 'luck'), '10/stem');
      assert.deepEqual((await state(page)).chosen, ['10/stem']);
      assert.equal(await focused(page), 'row 10/branch');
      await page.keyboard.press('l');
      await settled(page);
      assert.equal(await linkPart(page, 'luck'), null);
      assert.equal(await page.locator('#life').isVisible(), false);
      assert.equal(await focused(page), 'hour stem');
      // ? lists the grid's arrows among the luck pillar's keys.
      await page.keyboard.press('?');
      assert.equal(await page.locator('#keys-dialog .key-row-luck').filter({ visible: true }).last().locator('dd').textContent(),
        'Between the life grid’s phases');
    });

    check('L brings the grid with the luck pillar and takes it away, and today stands in its row', async (page) => {
      await openSample(page);
      assert.equal(await page.locator('#life').isVisible(), false);
      await page.locator('.card.stem[data-pillar="year"]').focus();
      await page.keyboard.press('l');
      await settled(page);
      assert.equal(await page.locator('#life').isVisible(), true);
      const shown = await state(page);
      assert.equal(shown.luck, 'Luck Stem phase 己 Ji 丑 Chou');
      assert.deepEqual(shown.chosen, ['5/stem']);
      assert.deepEqual(shown.now, ['5/stem']);
      assert.deepEqual(shown.ringed, ['hour stem', 'month stem']);
      // 7 October 2026 lies 56% into Ji Chou's stem phase, the first half of its decade.
      const today = await page.locator('#life .life-today').evaluate((line) => ({
        row: line.closest('.life-row').dataset.lifeRow, at: Number(line.style.getPropertyValue('--at')),
      }));
      assert.equal(today.row, '5');
      assert.ok(today.at > 0.27 && today.at < 0.29, String(today.at));
      // L again takes it away; focus stays on the card it was on.
      await page.keyboard.press('l');
      await settled(page);
      assert.equal(await page.locator('#life').isVisible(), false);
      assert.equal(await focused(page), 'year stem');
    });

    check('the head stays in sight while the grid scrolls by, and in Finnish the grid reads in Finnish', async (page) => {
      await openSample(page);
      await showLuck(page);
      await page.locator('#life [data-life="9/branch"]').scrollIntoViewIfNeeded();
      const head = await page.locator('#life-head').evaluate((node) => Math.round(node.getBoundingClientRect().top));
      assert.equal(head, 0);
      await page.goto('about:blank');
      await page.clock.setFixedTime(TODAY);
      await openLink(page, sampleLink({ lang: 'fi', luck: '5/stem' }), { place: HELSINKI });
      const read = await grid(page);
      assert.equal(read.title, 'Elämä');
      assert.equal(read.meta, '10 vuosikymmentä iästä 8, 1983–2083. Kukin rivi on viisi vuotta: vuosikymmenen rungon vaihe, sitten sen haaran vaihe.');
      assert.deepEqual(read.head.map((cell) => cell.split(' ')[0]), ['Tunti', 'Päivä', 'Kuukausi', 'Vuosi', 'Onni']);
      assert.equal((await row(page, '5/stem')).label, 'Ji Chou, Rungon vaihe, 2023–2028, nyt');
      // Nothing runs past the page's edge.
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    });

    check('Pillars only folds the natal columns away and lists the life path, and a link keeps it', async (page) => {
      await openSample(page);
      await showLuck(page);
      const only = () => page.locator('#life').evaluate((node) => node.classList.contains('is-only'));
      assert.equal(await only(), false);
      assert.deepEqual(await page.locator('#life-view [data-life-view]').evaluateAll((buttons) =>
        buttons.map((button) => `${button.textContent} ${button.getAttribute('aria-pressed')}`)), ['With the chart true', 'Pillars only false']);
      await click(page, '#life-view [data-life-view="pillars"]');
      assert.equal(await only(), true);
      assert.equal(await linkPart(page, 'life'), 'pillars');
      // The head, the marks and today's line fold away; every phase is a line of the list.
      assert.equal(await page.locator('#life-head').isVisible(), false);
      assert.equal(await page.locator('#life .life-mark, #life .life-run, #life .life-link, #life .life-today')
        .evaluateAll((nodes) => nodes.filter((node) => node.getClientRects().length > 0).length), 0);
      // A line's name, then its role, years and what else it lists, where shown.
      const list = (path) => page.locator(`#life [data-life="${path}"]`).evaluate((button) => {
        const shown = (selector) => {
          const node = button.querySelector(selector);
          return node.getClientRects().length > 0 ? node.innerText.replace(/\s+/g, ' ').trim() : null;
        };
        return [button.querySelector('.life-phase-name').firstChild.textContent, shown('.life-phase-role'),
          shown('.life-phase-years'), shown('.life-phase-more')];
      });
      if (profile.name === 'desktop') {
        assert.deepEqual(await list('before'), ['Before', 'No luck pillar', '1975–1983 · age 0–8', 'The chart reads as natal']);
        assert.deepEqual(await list('5/stem'), ['Ji', 'Direct Officer · new', '2023–2028 · age 48', 'Yin Earth']);
        assert.deepEqual(await list('5/branch'), ['Chou', 'Direct Officer · new', '2028–2033 · age 53', 'Day Master: Decline · Roots: Gui 癸']);
        // Each line runs across the page.
        const widths = await page.evaluate(() => {
          const row = document.querySelector('#life [data-life="5/stem"]').getBoundingClientRect();
          const grid = document.querySelector('#life-body').getBoundingClientRect();
          return Math.abs(row.width - grid.width) <= 1;
        });
        assert.equal(widths, true);
      } else {
        assert.deepEqual(await list('5/branch'), ['Chou', 'Direct Officer · new', null, null]);
      }
      // A line chooses its phase as a row does.
      await choose(page, '5/branch');
      assert.equal(await linkPart(page, 'topic'), 'luck/5/branch');
      assert.equal(await linkPart(page, 'life'), 'pillars');
      // A link names the view; without a gender it names no life at all. Natal, the view
      // waits for the luck pillar.
      await page.goto('about:blank');
      await page.clock.setFixedTime(TODAY);
      await openLink(page, sampleLink({ life: 'pillars' }), { place: HELSINKI });
      assert.equal(await page.locator('#life').isVisible(), false);
      await showLuck(page);
      assert.equal(await only(), true);
      assert.equal(await page.locator('#life-view [data-life-view="pillars"]').getAttribute('aria-pressed'), 'true');
      await click(page, '#life-view [data-life-view="grid"]');
      assert.equal(await only(), false);
      assert.equal(await linkPart(page, 'life'), null);
      for (const address of [sampleLink({ life: 'list' }), sampleLink({ life: 'grid' })]) {
        await page.goto('about:blank');
        await openLink(page, address, { place: HELSINKI, success: false });
        assert.equal(await page.locator('#form-error').textContent(), 'This link does not open a chart: “life” is missing or not valid.', address);
      }
      const parts = Object.fromEntries(new URLSearchParams(sampleLink({ life: 'pillars' }).split('?')[1]));
      delete parts.gender;
      await page.goto('about:blank');
      await openLink(page, `/#chart?${new URLSearchParams(parts)}`, { place: HELSINKI, success: false });
      assert.equal(await page.locator('#form-error').textContent(), 'This link does not open a chart: “life” is missing or not valid.');
      await screenshot(page, `${profile.name}-life-pillars`);
    });

    check('on paper the grid follows the chart, its head where it stands; a natal chart prints none', async (page) => {
      await openSample(page);
      await page.emulateMedia({ media: 'print' });
      assert.equal(await page.locator('#life').isVisible(), false);
      await page.emulateMedia({ media: 'screen' });
      await showLuck(page);
      await page.emulateMedia({ media: 'print' });
      assert.equal(await page.locator('#life').isVisible(), true);
      assert.equal(await page.locator('#life-head').evaluate((node) => getComputedStyle(node).position), 'static');
      await page.emulateMedia({ media: 'screen' });
    });
  });
}
