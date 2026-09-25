// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Stage 2 of the Standard view (#17): the chart shows what the engine computed.
import { assert, describe, it, engineName, profiles, openChart, withPage } from './chart-helpers.mjs';

const HELSINKI = {
  city: 'Helsinki', region: 'Uusimaa', country: 'Finland', display: 'Helsinki, Uusimaa, Finland',
  timezone: 'Europe/Helsinki', longitude: 24.94, latitude: 60.17,
};

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

    check('a chart whose true solar time cannot be read is not shown', async (page) => {
      await openChart(page, { success: false }, (payload) => { delete payload.solar_time.true_solar_time; });
      assert.equal(await page.locator('#form-error').textContent(), 'Could not read the true solar time.');
      assert.equal(await page.locator('#chart-view').isHidden(), true);
    });
  });
}
