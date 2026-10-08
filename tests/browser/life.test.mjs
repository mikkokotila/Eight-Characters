// Run with Node's built-in test runner and an explicitly selected Playwright install.
// The life grid of a chart asked for with a gender: under the chart, its five columns run
// on through the life, a row for each five years, a decade's stem phase over its branch
// phase. The Luck column holds the decades, and choosing a phase there chooses it
// everywhere; under each natal character a mark shows each relationship the luck pillar
// forms with it, for as long as it acts.
import {
  assert, describe, it, engineName, profiles, openChart, openLink, settled, screenshot, withPage, HELSINKI,
} from './chart-helpers.mjs';
import { TODAY, sampleLink, openSample, linkPart, click } from './luck-helpers.mjs';

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
      years: text(button.querySelector('.life-phase-years')),
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
    bars: [...row.querySelectorAll('.life-bar')].map((bar) => [
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
      luckHidden: life.querySelector('.life-head-cell.is-luck').classList.contains('is-hidden'),
      ringed: [...life.querySelectorAll('.life-head-cell:not(.is-luck) .life-mini.is-ringed')]
        .map((mini) => `${mini.closest('[data-pillar]').dataset.pillar} ${mini.dataset.part}`),
      setAside: [...life.querySelectorAll('.life-head-cell.is-luck .life-mini.is-resting')].map((mini) => mini.dataset.part),
    };
  });
}

function focused(page) {
  return page.evaluate(() => {
    const node = document.activeElement;
    if (node.dataset.life) return `row ${node.dataset.life}`;
    if (node.dataset.luck) return `chip ${node.dataset.luck}`;
    return node.id || node.textContent.replace(/\s+/g, ' ').trim();
  });
}

// Every box the grid draws, for what L must not move.
function gridBoxes(page) {
  return page.evaluate(() => [...document.querySelectorAll('#life .life-head-cell, #life .life-block, #life .life-mark, #life .life-bar, #life [data-life]')]
    .filter((node) => node.getClientRects().length > 0)
    .map((node) => {
      const box = node.getBoundingClientRect();
      return `${node.className} ${Math.round(box.x)},${Math.round(box.y + scrollY)} ${Math.round(box.width)}x${Math.round(box.height)}`;
    }));
}

const PHASE_ROWS = ['before', ...Array.from({ length: 10 }, (_, index) => [`${index + 1}/stem`, `${index + 1}/branch`]).flat()];

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / life grid`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 60000 }, () => withPage(profile, run));

    check('a chart with a gender has its life under the chart, by phase and by direction; one without has none', async (page) => {
      await page.clock.setFixedTime(TODAY);
      await openChart(page, { date: '1975-08-14', time: '07:45', place: HELSINKI });
      assert.equal(await page.locator('#life').isVisible(), false);
      await page.goto('about:blank');
      await openSample(page);
      assert.equal(await page.locator('#life').isVisible(), true);
      const read = await grid(page);
      assert.equal(read.title, 'Life');
      assert.equal(read.meta, '10 decades from age 8, 1983–2083. Each row is five years: a decade’s stem phase, then its branch phase.');
      // The head: the chart, each stem beside its branch; the luck pillar waits, hidden, at today.
      assert.deepEqual(read.head, [
        'Hour 甲 Jia 辰 Chen', 'Day 壬 Ren 辰 Chen', 'Month 甲 Jia 申 Shen', 'Year 乙 Yi 卯 Mao', 'Luck Hidden 己 Ji 丑 Chou',
      ]);
      assert.deepEqual(read.groups, ['West · Autumn 1983–2003', 'North · Winter 2003–2033', 'East · Spring 2033–2063', 'South · Summer 2063–2083']);
      assert.deepEqual(read.rows, PHASE_ROWS);
      // Each phase: its character and name, the role it brings, and its years.
      assert.deepEqual(await row(page, 'before'), {
        tile: '', name: 'Before', role: 'No luck pillar', years: '1975–1983', label: 'Before the first luck pillar, age 0 to 8',
      });
      assert.deepEqual(await row(page, '5/stem'), {
        tile: '己', name: 'Ji', role: 'Direct Officer · new', years: '2023–2028', label: 'Ji Chou, Stem phase, 2023 to 2028, now',
      });
      // A branch brings the role of its main qi.
      assert.deepEqual(await row(page, '5/branch'), {
        tile: '丑', name: 'Chou', role: 'Direct Officer · new', years: '2028–2033', label: 'Ji Chou, Branch phase, 2028 to 2033',
      });
      assert.deepEqual(await row(page, '4/stem'), {
        tile: '戊', name: 'Wu', role: 'Seven Killings', years: '2013–2018', label: 'Wu Zi, Stem phase, 2013 to 2018',
      });
      await screenshot(page, `${profile.name}-life`);
    });

    check('its columns are the chart\'s, and each mark stands under what it touches', async (page) => {
      await openSample(page);
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
        const bar = document.querySelector(`#life .life-row[data-life-row="${sequence}"] .life-bar`).getBoundingClientRect();
        return [sequence, Math.round((bar.height / decade.height) * 10) / 10];
      })));
      assert.ok(lines[4] > 0.8 && lines[5] > 0.3 && lines[5] < 0.5, JSON.stringify(lines));
      // Marks are drawn on wide screens; on a phone their lines say it.
      const shown = await page.locator('#life .life-mark').evaluateAll((marks) => marks.filter((mark) => mark.getClientRects().length > 0).length);
      assert.equal(shown > 0, profile.name === 'desktop');
      assert.ok(await page.locator('#life .life-bar').evaluateAll((bars) => bars.every((bar) => bar.getClientRects().length > 0)));
    });

    check('a phase chosen in the grid is chosen everywhere, and pressed again closes its page', async (page) => {
      await openSample(page);
      await click(page, '#life [data-life="4/branch"]');
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
      assert.equal(chosen.luckHidden, false);
      assert.deepEqual(chosen.setAside, ['stem']);
      assert.deepEqual(chosen.ringed, ['hour branch', 'day branch', 'month branch', 'year branch']);
      // Pressed again, the page closes and the decade stays in the chart.
      await click(page, '#life [data-life="4/branch"]');
      assert.equal(await page.locator('#luck-detail').isVisible(), false);
      assert.equal(await linkPart(page, 'luck'), '4/branch');
      assert.deepEqual((await state(page)).expanded, []);
      assert.deepEqual((await state(page)).chosen, ['4/branch']);
      // 己丑 Ji Chou's stem phase: its stem combinations ring the stems; in its branch phase
      // they rest, and their marks grow quiet.
      await click(page, '#life [data-life="5/stem"]');
      assert.deepEqual((await state(page)).ringed, ['hour stem', 'month stem']);
      assert.deepEqual((await state(page)).quiet, []);
      await click(page, '#life [data-life="5/branch"]');
      assert.deepEqual((await state(page)).ringed, []);
      assert.deepEqual((await state(page)).quiet, ['stem_combination:1:hour-luck', 'stem_combination:1:month-luck']);
      await screenshot(page, `${profile.name}-life-chosen`);
    });

    check('a page opened from the grid gives focus back to its row; one opened from the ribbon, to its chip', async (page) => {
      await openSample(page);
      await click(page, '#life [data-life="4/stem"]');
      await page.keyboard.press('Escape');
      await settled(page);
      assert.equal(await page.locator('#luck-detail').isVisible(), false);
      assert.equal(await focused(page), 'row 4/stem');
      await click(page, '#life [data-life="4/stem"]');
      await click(page, '#chart-panel [data-close-panel]');
      assert.equal(await focused(page), 'row 4/stem');
      // The page's phases move the choice; closing then gives focus to the row now chosen.
      await click(page, '#life [data-life="2/branch"]');
      await click(page, '#luck-detail [data-luck-phase="stem"]');
      await page.keyboard.press('Escape');
      await settled(page);
      assert.equal(await focused(page), 'row 2/stem');
      // From the ribbon, as before.
      await click(page, '#luck-ribbon [data-luck="6"]');
      await click(page, '#chart-panel [data-close-panel]');
      assert.equal(await focused(page), 'chip 6');
    });

    check('the rows take one tab stop, the arrows move between them, and the chart\'s keys act from them', async (page) => {
      await openSample(page);
      // Hidden, the stop is today's row.
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
      // The chart's keys act from a row: [ steps back, L hides, and focus stays on the row.
      await page.keyboard.press('[');
      await settled(page);
      assert.equal(await linkPart(page, 'luck'), '10/stem');
      assert.deepEqual((await state(page)).chosen, ['10/stem']);
      assert.equal(await focused(page), 'row 10/branch');
      await page.keyboard.press('l');
      await settled(page);
      assert.equal(await linkPart(page, 'luck'), null);
      const hidden = await state(page);
      assert.deepEqual(hidden.chosen, []);
      assert.equal(hidden.luckHidden, true);
      assert.deepEqual(hidden.ringed, []);
      assert.equal(await page.locator('#life').evaluate((life) => life.contains(document.activeElement)), true);
      // ? lists the grid's arrows among the luck pillar's keys.
      await page.keyboard.press('?');
      assert.equal(await page.locator('#keys-dialog .key-row-luck').filter({ visible: true }).last().locator('dd').textContent(),
        'Between the life grid’s phases');
    });

    check('today stands in its row, and L shows and hides the luck pillar without moving the grid', async (page) => {
      await openSample(page);
      assert.deepEqual((await state(page)).now, ['5/stem']);
      // 7 October 2026 lies 56% into Ji Chou's stem phase, the first half of its decade.
      const today = await page.locator('#life .life-today').evaluate((line) => ({
        row: line.closest('.life-row').dataset.lifeRow, at: Number(line.style.getPropertyValue('--at')),
      }));
      assert.equal(today.row, '5');
      assert.ok(today.at > 0.27 && today.at < 0.29, String(today.at));
      const before = await gridBoxes(page);
      await page.locator('.card.stem[data-pillar="year"]').focus();
      await page.keyboard.press('l');
      await settled(page);
      const shown = await state(page);
      assert.equal(shown.luck, 'Luck Stem phase 己 Ji 丑 Chou');
      assert.deepEqual(shown.chosen, ['5/stem']);
      assert.deepEqual(shown.ringed, ['hour stem', 'month stem']);
      assert.deepEqual(await gridBoxes(page), before);
      await page.keyboard.press('l');
      await settled(page);
      assert.deepEqual(await gridBoxes(page), before);
    });

    check('the head stays in sight while the grid scrolls by, and in Finnish the grid reads in Finnish', async (page) => {
      await openSample(page);
      await page.locator('#life [data-life="9/branch"]').scrollIntoViewIfNeeded();
      const head = await page.locator('#life-head').evaluate((node) => Math.round(node.getBoundingClientRect().top));
      assert.equal(head, 0);
      await page.goto('about:blank');
      await page.clock.setFixedTime(TODAY);
      await openLink(page, sampleLink({ lang: 'fi' }), { place: HELSINKI });
      const read = await grid(page);
      assert.equal(read.title, 'Elämä');
      assert.equal(read.meta, '10 vuosikymmentä iästä 8, 1983–2083. Kukin rivi on viisi vuotta: vuosikymmenen rungon vaihe, sitten sen haaran vaihe.');
      assert.deepEqual(read.head.map((cell) => cell.split(' ')[0]), ['Tunti', 'Päivä', 'Kuukausi', 'Vuosi', 'Onni']);
      assert.equal((await row(page, '5/stem')).label, 'Ji Chou, Rungon vaihe, 2023–2028, nyt');
      // Nothing runs past the page's edge.
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    });

    check('on paper the grid follows the chart, its head where it stands', async (page) => {
      await openSample(page);
      await page.emulateMedia({ media: 'print' });
      assert.equal(await page.locator('#life').isVisible(), true);
      assert.equal(await page.locator('#life-head').evaluate((node) => getComputedStyle(node).position), 'static');
      await page.emulateMedia({ media: 'screen' });
    });
  });
}
