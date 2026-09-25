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

    check('a chart whose true solar time cannot be read is not shown', async (page) => {
      await openChart(page, { success: false }, (payload) => { delete payload.solar_time.true_solar_time; });
      assert.equal(await page.locator('#form-error').textContent(), 'Could not read the true solar time.');
      assert.equal(await page.locator('#chart-view').isHidden(), true);
    });
  });
}
