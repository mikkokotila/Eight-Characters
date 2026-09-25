// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Stage 2 of the Standard view (#17): the chart shows what the engine computed.
import {
  assert, describe, it, engineName, profiles, openChart, withPage, HELSINKI, TROMSO,
} from './chart-helpers.mjs';

async function identities(page) {
  return page.locator('.pillar').evaluateAll((pillars) => Object.fromEntries(pillars.map((pillar) => [
    pillar.dataset.pillar,
    `${pillar.querySelector('.pillar-chars').textContent} ${pillar.querySelector('.pillar-pinyin').textContent}`,
  ])));
}

async function marks(page) {
  return page.locator('.pillar').evaluateAll((pillars) => Object.fromEntries(pillars.map((pillar) => [
    pillar.dataset.pillar,
    pillar.classList.contains('is-near-change') ? pillar.querySelector('.pillar-mark').textContent : '',
  ])));
}

async function changes(page, pillar) {
  await page.locator(`.pillar-identity[data-pillar="${pillar}"]`).click();
  await page.locator('#pillar-detail').waitFor({ state: 'visible' });
  return page.locator('#pillar-detail').evaluate((detail) => ({
    title: detail.querySelector('h3').textContent,
    sides: [...detail.querySelectorAll('.pillar-change')].map((side) => [...side.children].map((line) => line.textContent)),
  }));
}

// What follows the Day Master: the chart, its Ten Gods, roots, relationships and roles.
async function reading(page) {
  const pillars = await identities(page);
  const state = {
    dayMaster: await page.locator('#day-master-heading').textContent(),
    day: pillars.day,
    hour: pillars.hour,
    marks: await marks(page),
    yearStemTenGod: await page.locator('.card.stem[data-pillar="year"] .ten-god-name').textContent(),
    roots: await page.locator('button[data-context="roots"]').textContent(),
    // WebKit's innerText ends a chip with a line break; Chromium's does not.
    relationships: (await page.locator('.relationship-chip').allInnerTexts()).map((text) => text.trim()),
  };
  await page.locator('button[data-context="roles"]').click();
  state.roles = await page.locator('#context-detail').innerText();
  await page.keyboard.press('Escape');
  return state;
}

async function pressConvention(page, convention) {
  const request = page.waitForRequest('**/api/four_pillars');
  await page.locator(`#zi-switch button[data-zi-convention="${convention}"]`).click();
  const conventions = (await request).postDataJSON().conventions;
  await page.waitForFunction((convention) => document.querySelector('#zi-switch button[aria-pressed="true"]')
    ?.dataset.ziConvention === convention, convention);
  return conventions;
}

// Flags that contradict the chart they came with.
const FLAG_CONTRADICTIONS = {
  'a Zi-hour window without the other convention': (payload) => { payload.flags.zi_hour_window = true; },
  'an ambiguous solar term hours from any jie': (payload) => { payload.flags.solar_term_ambiguous = true; },
};

// Each response is the real API's, contradicted in one way.
const CONTRADICTIONS = {
  'without its changes': (payload) => { delete payload.four_pillars.day.changes; },
  'with a change to the same pillar': (payload) => {
    const { stem, branch } = payload.four_pillars.month;
    payload.four_pillars.month.changes.next.pillar = { stem, branch };
  },
  'with a negative distance': (payload) => { payload.four_pillars.hour.changes.previous.seconds = -1; },
  'with other characters than its chart': (payload) => {
    payload.four_pillars.year.stem = { ...payload.four_pillars.year.stem, chinese: '甲' };
  },
};

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / what the engine knows`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 60000 }, () => withPage(profile, run));

    check('the canonical chart names its pillars and gives its true solar time', async (page) => {
      await openChart(page, { lang: 'en' });
      // The solar year is still 1987 (丁卯): the birth is six hours before Lichun.
      assert.deepEqual(await identities(page), {
        hour: '壬申 Ren Shen', day: '己丑 Ji Chou', month: '癸丑 Gui Chou', year: '丁卯 Ding Mao',
      });
      assert.deepEqual(await page.locator('.card .glyph').allTextContents(),
        ['壬', '申', '己', '丑', '癸', '丑', '丁', '卯']);
      assert.equal(await page.locator('#chart-date').textContent(), 'February 4, 1988 · 16:30 · Chengdu');
      assert.equal(await page.locator('#chart-solar-time').textContent(),
        'True solar time 15:12:24 · 1 h 17 min 36 s behind clock time');
    });

    check('Finnish writes its times with periods', async (page) => {
      await openChart(page, { lang: 'fi' });
      assert.equal(await page.locator('#chart-date').textContent(), '4. helmikuuta 1988 · 16.30 · Chengdu');
      assert.equal(await page.locator('#chart-solar-time').textContent(),
        'Todellinen aurinkoaika 15.12.24 · 1 t 17 min 36 s kelloaikaa jäljessä');
    });

    check('a true solar time on another day than the clock gives its date', async (page) => {
      await openChart(page, { lang: 'en', place: HELSINKI, date: '1988-06-15', time: '00:50' });
      assert.equal(await page.locator('#chart-solar-time').textContent(),
        'True solar time June 14, 1988, 23:29:24 · 1 h 20 min 36 s behind clock time');
    });

    check('only a pillar within 30 minutes of a change is marked, on either side of it', async (page) => {
      await openChart(page, { lang: 'en' });
      assert.deepEqual(await marks(page), { hour: 'changed 12 min 24 s ago', day: '', month: '', year: '' });
      await page.locator('#back-btn').click();
      await page.locator('#time').fill('18:10');
      await page.locator('#create-chart-btn').click();
      await page.waitForFunction(() => document.querySelector('.pillar-mark')?.textContent.startsWith('changes'));
      assert.deepEqual(await marks(page), { hour: 'changes in 7 min 36 s', day: '', month: '', year: '' });
    });

    check("the year's exact changes open on demand: Lichun is 6 h 12 min away", async (page) => {
      await openChart(page, { lang: 'en' });
      assert.deepEqual(await changes(page, 'year'), {
        title: 'Life field · 丁卯 Ding Mao',
        sides: [
          ['Previous change', '364 d 23 h 38 min 21.4 s ago', 'Solar term Lichun', '丙寅 Bing Yin then 丁卯 Ding Mao'],
          ['Next change', 'in 6 h 12 min 49.5 s', 'Solar term Lichun', '丁卯 Ding Mao then 戊辰 Wu Chen'],
        ],
      });
      const year = page.locator('.pillar-identity[data-pillar="year"]');
      assert.equal(await year.getAttribute('aria-expanded'), 'true');
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#pillar-detail').isHidden(), true);
      assert.equal(await year.getAttribute('aria-expanded'), 'false');
      assert.equal(await year.evaluate((button) => button === document.activeElement), true);
    });

    check('day and hour changes name the clock they are read on, and its date when it differs', async (page) => {
      await openChart(page, { lang: 'en' });
      assert.deepEqual((await changes(page, 'hour')).sides, [
        ['Previous change', '12 min 24.2 s ago', 'True solar time 15:00', '辛未 Xin Wei then 壬申 Ren Shen'],
        ['Next change', 'in 1 h 47 min 36.3 s', 'True solar time 17:00', '壬申 Ren Shen then 癸酉 Gui You'],
      ]);
      assert.deepEqual((await changes(page, 'day')).sides, [
        ['Previous change', '15 h 12 min 28.1 s ago', 'True solar time 00:00', '戊子 Wu Zi then 己丑 Ji Chou'],
        ['Next change', 'in 8 h 47 min 38.0 s', 'True solar time February 5, 1988, 00:00', '己丑 Ji Chou then 庚寅 Geng Yin'],
      ]);
    });

    check('one detail is open at a time', async (page) => {
      await openChart(page, { lang: 'en' });
      await page.locator('.relationship-chip').first().click();
      await page.locator('#relationship-detail').waitFor({ state: 'visible' });
      await changes(page, 'year');
      assert.equal(await page.locator('#relationship-detail').isHidden(), true);
      await page.locator('button[data-context="season"]').click();
      await page.locator('#context-detail').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#pillar-detail').isHidden(), true);
      await changes(page, 'month');
      assert.equal(await page.locator('#context-detail').isHidden(), true);
      // A second press closes it again.
      await page.locator('.pillar-identity[data-pillar="month"]').click();
      assert.equal(await page.locator('#pillar-detail').isHidden(), true);
    });

    for (const [name, mutate] of Object.entries(CONTRADICTIONS)) {
      check(`a chart ${name} is not shown`, async (page) => {
        await openChart(page, { success: false }, mutate);
        assert.equal(await page.locator('#form-error').textContent(), 'Could not read when the pillars change.');
        assert.equal(await page.locator('#chart-view').isHidden(), true);
      });
    }

    check('the Zi-hour chart offers the other convention, and the whole chart follows it', async (page) => {
      await openChart(page, { lang: 'en', place: HELSINKI, date: '1988-06-15', time: '00:50' });
      assert.deepEqual(await page.locator('#zi-switch button').allTextContents(),
        ['Day changes at midnight', 'Day changes at 23:00']);
      assert.equal(await page.locator('#zi-switch button[aria-pressed="true"]').textContent(), 'Day changes at midnight');
      const geng = {
        dayMaster: 'Day Master · Geng — Yang Metal',
        day: '庚子 Geng Zi',
        hour: '丙子 Bing Zi',
        // The Zi hour began at true solar 23:00 under either convention; this day at midnight.
        marks: { hour: 'changed 29 min 24 s ago', day: '', month: '', year: '' },
        yearStemTenGod: 'Indirect Resource',
        roots: 'No roots detected',
        relationships: ['Month–Day · Branch clash', 'Month–Hour · Branch clash'],
      };
      const before = await reading(page);
      assert.deepEqual({ ...before, roles: undefined }, { ...geng, roles: undefined });
      assert.deepEqual(await pressConvention(page, 'whole_zi_23'), { zi_convention: 'whole_zi_23' });
      assert.equal(await page.locator('#zi-switch button[aria-pressed="true"]').evaluate(
        (button) => button === document.activeElement), true);
      const after = await reading(page);
      assert.deepEqual({ ...after, roles: undefined }, {
        dayMaster: 'Day Master · Xin — Yin Metal',
        day: '辛丑 Xin Chou',
        hour: '戊子 Wu Zi',
        // Under this convention the day and the hour both began at true solar 23:00.
        marks: { hour: 'changed 29 min 24 s ago', day: 'changed 29 min 24 s ago', month: '', year: '' },
        yearStemTenGod: 'Direct Resource',
        roots: 'Root in one branch',
        relationships: ['Day–Hour · Branch combination', 'Month–Hour · Branch clash'],
        roles: undefined,
      });
      assert.notEqual(after.roles, before.roles);
      // And back: the chart is the first one again.
      assert.deepEqual(await pressConvention(page, 'split_midnight'), { zi_convention: 'split_midnight' });
      assert.deepEqual(await reading(page), before);
    });

    check('no switch is offered where both conventions give the same pillars', async (page) => {
      await openChart(page, { lang: 'en' });
      assert.equal(await page.locator('#zi-switch').isHidden(), true);
      await page.locator('#back-btn').click();
      // Clock 01:45 is true solar 00:24: in the Zi hour, but the same day under either convention.
      const payload = await openChart(page, { lang: 'en', place: HELSINKI, date: '1988-06-15', time: '01:45' });
      assert.equal(payload.flags.zi_hour_window, true);
      assert.equal(await page.locator('#zi-switch').isHidden(), true);
    });

    check('a switched chart that cannot be read sends the form back with the reason', async (page) => {
      await openChart(page, { lang: 'en', place: HELSINKI, date: '1988-06-15', time: '00:50' }, (payload) => {
        if (payload.flags.alternative_pillars?.conventions.zi_convention === 'split_midnight') {
          delete payload.solar_time.true_solar_time;
        }
      });
      await page.locator('#zi-switch button[data-zi-convention="whole_zi_23"]').click();
      await page.locator('#form-error').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#form-error').textContent(), 'Could not read the true solar time.');
      assert.equal(await page.locator('#chart-view').isHidden(), true);
    });

    check('a birthplace above latitude 66° carries a notice', async (page) => {
      await openChart(page, { lang: 'en', place: TROMSO, date: '1988-06-15', time: '12:00' });
      assert.deepEqual(await page.locator('#chart-notices li').allTextContents(), [
        'The birthplace lies above latitude 66°, near the polar circle, where the Sun can stay above or below'
          + ' the horizon for days. True solar time is calculated as usual.',
      ]);
      await page.locator('#back-btn').click();
      await openChart(page, { lang: 'en' });
      assert.equal(await page.locator('#chart-notices').isHidden(), true);
    });

    check('a birth within the uncertainty of Lichun says both pillars could differ', async (page) => {
      // The engine's own flag, with the month and year changes moved to agree with it.
      await openChart(page, { lang: 'en' }, (payload) => {
        payload.flags.solar_term_ambiguous = true;
        payload.four_pillars.month.changes.next.seconds = 0.3;
        payload.four_pillars.year.changes.next.seconds = 0.3;
      });
      assert.deepEqual(await page.locator('#chart-notices li').allTextContents(), [
        "The birth lies within the calculation's uncertainty (0.5 s) of Lichun, so the year and month pillars"
          + ' could be the other ones.',
      ]);
    });

    for (const [name, mutate] of Object.entries(FLAG_CONTRADICTIONS)) {
      check(`a chart with ${name} is not shown`, async (page) => {
        await openChart(page, { success: false }, mutate);
        assert.equal(await page.locator('#form-error').textContent(), "Could not read the chart's notices.");
        assert.equal(await page.locator('#chart-view').isHidden(), true);
      });
    }

    check('a chart whose true solar time cannot be read is not shown', async (page) => {
      await openChart(page, { success: false }, (payload) => { delete payload.solar_time.true_solar_time; });
      assert.equal(await page.locator('#form-error').textContent(), 'Could not read the true solar time.');
      assert.equal(await page.locator('#chart-view').isHidden(), true);
    });
  });
}
