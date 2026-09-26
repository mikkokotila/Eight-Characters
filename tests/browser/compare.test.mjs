// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Stage 5 of the Standard view (#20): two charts side by side. Compare, on a chart, asks
// for the second birth; the pair then shows as two charts, each the chart view embedded in
// a frame of its own, with its own topics. The pair has an address of its own.
import {
  assert, describe, it, engineName, profiles, openChart, settled, withPage, CHENGDU,
} from './chart-helpers.mjs';

const SECOND = { date: '1990-05-09', time: '12:00' };

// A chart's pillars as the API gives them, hour to year: stems, then branches.
async function pillarsOf(page, date, time, lang = 'en') {
  const response = await page.request.post(new URL('/api/four_pillars', page.url()).href, {
    data: { date, time, lang, location: { timezone: CHENGDU.timezone, longitude: CHENGDU.longitude, latitude: CHENGDU.latitude } },
  });
  assert.equal(response.status(), 200);
  const pillars = (await response.json()).four_pillars;
  const order = ['hour', 'day', 'month', 'year'];
  return { stems: order.map((name) => pillars[name].stem.chinese).join(''), branches: order.map((name) => pillars[name].branch.chinese).join('') };
}
// What a side's frame shows: its chart's stems and branches, and whether a topic is open.
// Drawn, whether or not its side is the one shown (a narrow screen shows one at a time).
async function side(page, key) {
  const frame = page.frameLocator(`#compare-charts .compare-frame[data-side="${key}"]`);
  await frame.locator('#chart-view:not(.hidden) #pillars .card').first().waitFor({ state: 'attached' });
  return {
    frame,
    stems: await frame.locator('#pillars .card.stem').evaluateAll((cards) => cards.map((card) => card.dataset.char).join('')),
    branches: await frame.locator('#pillars .card.branch').evaluateAll((cards) => cards.map((card) => card.dataset.char).join('')),
    topic: await frame.locator('#context-detail').evaluate((node) => (node.classList.contains('hidden') ? null : node.dataset.topic)),
  };
}
// Both charts drawn: nothing asked of the API is left in flight when a frame goes.
async function bothDrawn(page) {
  await page.locator('#compare-view').waitFor({ state: 'visible' });
  return [await side(page, 'a'), await side(page, 'b')];
}
const pairIn = (url) => {
  const params = new URLSearchParams(new URL(url).hash.slice('#compare?'.length));
  return { a: new URLSearchParams(params.get('a') ?? ''), b: params.has('b') ? new URLSearchParams(params.get('b')) : null };
};
// From a chart: Compare, and the second birth (openChart answers the place's search).
async function compareWithSecond(page, lang = 'en') {
  await openChart(page, { lang });
  await page.locator('#compare-btn').click();
  await page.locator('#compare-note').waitFor({ state: 'visible' });
  await page.locator('#date').fill(SECOND.date);
  await page.locator('#time').fill(SECOND.time);
  await page.locator('#location').fill(CHENGDU.city);
  await page.locator('.location-suggestion').click();
  await page.locator('#create-chart-btn').click();
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / compare`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 90000 }, () => withPage(profile, run));

    check('Compare asks for the second birth, naming the first, and Cancel goes back to it', async (page) => {
      await openChart(page, { lang: 'en' });
      const first = await page.locator('#chart-date').textContent();
      await page.locator('#compare-btn').click();
      await page.locator('#compare-note').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#compare-note-text').textContent(), `Second chart, to compare with ${first}`);
      assert.equal(await page.locator('#create-chart-btn').textContent(), 'Compare');
      // A new birth: the form starts empty.
      assert.deepEqual(await page.evaluate(() => ['date', 'time', 'location'].map((id) => document.getElementById(id).value)), ['', '', '']);
      const pair = pairIn(page.url());
      assert.equal(pair.a.get('date'), '1988-02-04');
      assert.equal(pair.b, null);
      await page.locator('#compare-cancel').click();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#chart-date').textContent(), first);
      assert.equal(await page.locator('#create-chart-btn').textContent(), 'Create chart');
      assert.equal(await page.locator('#compare-note').isVisible(), false);
    });

    check('the second birth shows both charts side by side, each the chart view with only its own controls', async (page) => {
      await compareWithSecond(page);
      await bothDrawn(page);
      assert.equal(await page.locator('#input-view').isVisible(), false);
      assert.equal(await page.locator('#chart-view').isVisible(), false);
      const expectedA = await pillarsOf(page, '1988-02-04', '16:30');
      const expectedB = await pillarsOf(page, SECOND.date, SECOND.time);
      const [a, b] = [await side(page, 'a'), await side(page, 'b')];
      // Side by side on a wide screen; on a narrow one, one at a time, the other a switch away.
      const shown = () => page.locator('.compare-frame').evaluateAll((frames) => frames.filter((frame) => frame.checkVisibility()).map((frame) => frame.dataset.side));
      assert.deepEqual(await shown(), profile.name === 'mobile' ? ['a'] : ['a', 'b']);
      assert.equal(await page.locator('#compare-sides').isVisible(), profile.name === 'mobile');
      if (profile.name === 'mobile') {
        await page.locator('#compare-sides button[data-compare-side="b"]').click();
        assert.deepEqual(await shown(), ['b']);
        assert.equal(await page.locator('#compare-sides button[data-compare-side="b"]').getAttribute('aria-pressed'), 'true');
        await b.frame.locator('#chart-view').waitFor({ state: 'visible' });
      }
      assert.deepEqual([a.stems, a.branches], [expectedA.stems, expectedA.branches]);
      assert.deepEqual([b.stems, b.branches], [expectedB.stems, expectedB.branches]);
      // Each frame keeps the chart's own display and Copy as text; the page holds the rest.
      assert.deepEqual(await (profile.name === 'mobile' ? b : a).frame.locator('.chart-tools > *').evaluateAll((nodes) => nodes.filter((node) => node.checkVisibility()).map((node) => node.id)),
        ['display-switch', 'copy-text-btn']);
      assert.deepEqual(await page.locator('.compare-frame').evaluateAll((frames) => frames.map((frame) => frame.title)), [
        'Chart 1: February 4, 1988 · 16:30 · Chengdu', 'Chart 2: May 9, 1990 · 12:00 · Chengdu']);
      assert.equal(await page.title(), 'Comparison: February 4, 1988 · 16:30 · Chengdu and May 9, 1990 · 12:00 · Chengdu — BaZi');
      const pair = pairIn(page.url());
      assert.deepEqual([pair.a.get('date'), pair.b.get('date'), pair.b.get('time')], ['1988-02-04', SECOND.date, SECOND.time]);
    });

    check('each chart opens its own topics, the pair\'s address follows, and nothing is added to the history', async (page) => {
      await openChart(page, { lang: 'en' });
      const a = new URLSearchParams(new URL(page.url()).hash.slice('#chart?'.length));
      const b = new URLSearchParams({ ...Object.fromEntries(a), date: SECOND.date, time: SECOND.time });
      await page.goto(new URL(`/#compare?${new URLSearchParams({ a: a.toString(), b: b.toString() })}`, page.url()).href);
      const [first] = await bothDrawn(page);
      const length = await page.evaluate(() => history.length);
      await first.frame.locator('button[data-context="roots"]').click();
      await first.frame.locator('#context-detail').waitFor({ state: 'visible' });
      await page.waitForFunction(() => new URLSearchParams(new URLSearchParams(location.hash.slice('#compare?'.length)).get('a')).get('topic') === 'roots');
      if (profile.name === 'mobile') await page.locator('#compare-sides button[data-compare-side="b"]').click();
      assert.equal((await side(page, 'b')).topic, null);
      assert.equal(await page.evaluate(() => history.length), length);
      // The pair's link, opened anew, shows both charts and the open topic.
      const link = page.url();
      await page.goto('about:blank');
      await page.goto(link);
      assert.equal((await side(page, 'a')).topic, 'roots');
      assert.equal((await side(page, 'b')).topic, null);
    });

    check('Swap sides keeps each chart with what is open in it; Close goes to the first; Back walks the comparison', async (page) => {
      await compareWithSecond(page);
      const [before] = await bothDrawn(page);
      await before.frame.locator('button[data-context="roots"]').click();
      await page.waitForFunction(() => location.hash.includes('topic%3Droots'));
      await page.locator('#compare-swap').click();
      if (profile.name === 'mobile') {
        // The chart shown stays the one shown: it is now on the other side.
        assert.equal(await page.locator('#compare-sides button[data-compare-side="b"]').getAttribute('aria-pressed'), 'true');
        await page.locator('#compare-sides button[data-compare-side="a"]').click();
      }
      const a = await side(page, 'a');
      if (profile.name === 'mobile') await page.locator('#compare-sides button[data-compare-side="b"]').click();
      const b = await side(page, 'b');
      assert.equal(b.stems, before.stems);
      assert.equal(b.topic, 'roots');
      assert.notEqual(a.stems, before.stems);
      const pair = pairIn(page.url());
      assert.equal(pair.a.get('date'), SECOND.date);
      assert.equal(pair.b.get('topic'), 'roots');
      await page.locator('#compare-close').click();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#compare-view').isVisible(), false);
      assert.equal(await page.locator('#pillars .card.stem').evaluateAll((cards) => cards.map((card) => card.dataset.char).join('')), a.stems);
      // Back: the comparison, the form for its second chart, then the first chart.
      await page.goBack();
      await bothDrawn(page);
      await page.goBack();
      await page.locator('#compare-note').waitFor({ state: 'visible' });
      await page.goBack();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#chart-date').textContent(), 'February 4, 1988 · 16:30 · Chengdu');
    });

    check('the comparison\'s language asks both charts again in it', async (page) => {
      await compareWithSecond(page);
      await bothDrawn(page);
      await page.locator('#compare-language button[data-compare-lang="fi"]').click();
      await page.waitForFunction(() => {
        const pair = new URLSearchParams(location.hash.slice('#compare?'.length));
        return ['a', 'b'].every((key) => new URLSearchParams(pair.get(key)).get('lang') === 'fi');
      });
      assert.equal(await page.locator('#compare-close').textContent(), 'Sulje vertailu');
      assert.equal(await page.locator('#compare-language button[data-compare-lang="fi"]').getAttribute('aria-pressed'), 'true');
      for (const key of ['a', 'b']) {
        if (profile.name === 'mobile') await page.locator(`#compare-sides button[data-compare-side="${key}"]`).click();
        const { frame } = await side(page, key);
        assert.equal(await frame.locator('html').getAttribute('lang'), 'fi');
        assert.match(await frame.locator('#chart-solar-time').textContent(), /^Todellinen aurinkoaika/);
      }
    });

    check('a comparison link that names no pair says why, and Copy link copies the pair', async (page) => {
      await page.addInitScript(() => {
        window.__copied = [];
        Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async (text) => { window.__copied.push(text); } } });
      });
      await compareWithSecond(page);
      await bothDrawn(page);
      await page.locator('#compare-copy-link').click();
      await page.waitForFunction(() => document.querySelector('.toast').textContent === 'Comparison link copied');
      assert.deepEqual(await page.evaluate(() => window.__copied), [page.url()]);
      for (const [hash, part] of [['#compare?b=date%3D1990-05-09', 'a'], ['#compare?a=date%3D1990-13-40', 'date'], ['#compare?a=x&c=1', 'c']]) {
        await page.goto(new URL(`/${hash}`, page.url()).href);
        await page.locator('#form-error').waitFor({ state: 'visible' });
        assert.ok((await page.locator('#form-error').textContent()).includes(`“${part}”`), part);
        assert.equal(await page.locator('#compare-view').isVisible(), false);
        assert.equal(new URL(page.url()).hash, '');
      }
    });

    check('the commands offer Compare on a chart, and leave the page\'s actions out of a compared chart', async (page) => {
      await compareWithSecond(page);
      const [{ frame }] = await bothDrawn(page);
      await frame.locator('#pillars .card.stem').first().click();
      await page.keyboard.press('Control+k');
      const inFrame = await frame.locator('#palette-list .palette-label').allTextContents();
      for (const left of ['Compare', 'Edit', 'New chart', 'Copy link', 'Evolution', 'FI']) assert.ok(!inFrame.includes(left), `${left} in ${inFrame}`);
      assert.ok(inFrame.includes('Copy as text') && inFrame.includes('Print'), inFrame.join(', '));
      await page.keyboard.press('Escape');
      await page.locator('#compare-close').click();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      await page.keyboard.press('Control+k');
      assert.ok((await page.locator('#palette-list .palette-label').allTextContents()).includes('Compare'));
    });
  });
}
