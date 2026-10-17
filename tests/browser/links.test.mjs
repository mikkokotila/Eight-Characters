// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Stage 4 of the Standard view (#19), part 3: chart links. The address names the chart on
// screen, its open topic and its display; a reload, a new tab, and Back and Forward show
// them again.
import {
  assert, describe, it, engineName, profiles, openChart, openLink, fillChart, settled, showDisplay,
  withPage, signIn, HELSINKI, press,
} from './chart-helpers.mjs';

// The canonical chart's link, as the app writes it.
const CANONICAL = {
  date: '1988-02-04', time: '16:30', place: 'Chengdu, Sichuan, China', city: 'Chengdu',
  latitude: '30.658', longitude: '104.066', timezone: 'Asia/Shanghai', lang: 'en',
};
const link = (parts) => `/#chart?${new URLSearchParams(parts)}`;

// The link's parts, or the bare fragment when it names no chart.
function linkParts(page) {
  return page.evaluate(() => (location.hash.startsWith('#chart?')
    ? Object.fromEntries(new URLSearchParams(location.hash.slice('#chart?'.length))) : location.hash));
}

// What a reader sees: the view, the chart's face, and what is open in the panel.
function onScreen(page) {
  return page.evaluate(() => {
    const visible = (node) => node && !node.closest('.hidden');
    // The panel's last open section: a chosen relationship's detail follows their list.
    const detail = [...document.querySelectorAll('#chart-panel > .chart-panel-body > section')].filter(visible).at(-1);
    return {
      view: visible(document.getElementById('chart-view')) ? 'chart' : 'form',
      heading: document.getElementById('chart-date').textContent,
      chars: [...document.querySelectorAll('#pillars .card')].map((card) => card.dataset.char).join(''),
      opened: [...document.querySelectorAll('.chart-column [aria-expanded="true"]')].map((node) => node.textContent.trim()),
      panel: detail ? (detail.querySelector('h3') ?? detail).textContent.trim().split('\n')[0] : null,
      chosen: document.querySelector('.relationship-chip.is-active')?.dataset.relationship ?? null,
      flipped: document.querySelectorAll('#pillars .card.is-flipped').length,
    };
  });
}

function fields(page) {
  return page.evaluate(() => ({
    date: document.getElementById('date').value,
    time: document.getElementById('time').value,
    location: document.getElementById('location').value,
  }));
}

const entries = (page) => page.evaluate(() => history.length);

// A step through the history: waits until the address has changed and the page has followed it.
async function step(page, direction) {
  const from = page.url();
  await page.evaluate((direction) => history.go(direction), direction);
  await page.waitForFunction((from) => location.href !== from, from);
  await page.waitForFunction(() => !document.getElementById('chart-view').hasAttribute('aria-busy')
    && !document.getElementById('chart-form').hasAttribute('aria-busy'));
  await settled(page);
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / chart links`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 60000 }, () => withPage(profile, run));

    // Another tab, with nothing of this one's: no stored language, and a Finnish browser.
    async function inNewTab(page, run) {
      const { name, ...options } = profile;
      const tab = await page.context().browser().newPage({ ...options, locale: 'fi-FI' });
      await signIn(tab);
      const errors = [];
      tab.on('pageerror', (error) => errors.push(error.message));
      try { await run(tab); assert.deepEqual(errors, [], 'Uncaught browser errors in the new tab'); }
      finally { await tab.close(); }
    }

    check('a new chart\'s address names it, and a reload shows the same chart', async (page) => {
      await openChart(page, { lang: 'en' });
      assert.deepEqual(await linkParts(page), CANONICAL);
      const before = { ...(await onScreen(page)), title: await page.title() };
      assert.equal(before.chars, '壬申己丑癸丑丁卯');
      await page.reload();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      assert.deepEqual({ ...(await onScreen(page)), title: await page.title() }, before);
      assert.deepEqual(await linkParts(page), CANONICAL);
      // The birth is in the form, for Edit.
      await press(page, '#back-btn');
      assert.deepEqual(await fields(page), { date: '1988-02-04', time: '16:30', location: 'Chengdu, Sichuan, China' });
      assert.equal(await page.locator('#create-chart-btn').isDisabled(), false);
    });

    check('the open topic and the display come back in a new tab, in the link\'s language', async (page) => {
      await openChart(page, { lang: 'en' });
      await page.locator('button[data-context="roles"]').click();
      await page.locator('[data-role="direct_wealth"]').click();
      // The role's page offers the hour stem's roots once for each of its occurrences there.
      await page.locator('#context-detail button[data-root-pillar="hour"][data-from-role="direct_wealth"]').first().click();
      await showDisplay(page, 'ten-gods');
      assert.deepEqual(await linkParts(page),
        { ...CANONICAL, display: 'ten-gods', topic: 'roles/direct_wealth/stem/hour' });
      const before = await onScreen(page);
      assert.equal(before.flipped, 8);
      const address = page.url();
      await inNewTab(page, async (tab) => {
        await openLink(tab, address);
        assert.deepEqual(await onScreen(tab), before);
        assert.equal(tab.url(), address);
        assert.equal(await tab.evaluate(() => document.documentElement.lang), 'en');
        // Back to the roles of Direct Wealth, as the page's own back link would go.
        await tab.locator('#context-detail .roles-back').click();
        assert.equal((await linkParts(tab)).topic, 'roles/direct_wealth');
      });
    });

    check('every kind of topic comes back from its link', async (page) => {
      const topics = {
        season: 'Seasonal context',
        roots: 'Roots',
        roles: 'Roles',
        'roles/direct_wealth': 'Direct Wealth',
        'roles/stem/year': 'Stem roots · Year · Ding 丁',
        relationships: 'Relationships',
        'relationships/stem_combination:4:year-hour': 'Hour–Year · Stem combination',
        'pillar/month': 'Month · 癸丑 Gui Chou',
      };
      for (const [topic, heading] of Object.entries(topics)) {
        await page.goto('about:blank');
        await openLink(page, link({ ...CANONICAL, topic }));
        assert.equal((await linkParts(page)).topic, topic);
        const seen = await onScreen(page);
        assert.equal(seen.panel, heading, topic);
        assert.equal(seen.chosen, topic.startsWith('relationships/') ? topic.split('/')[1] : null, topic);
      }
    });

    check('Back and Forward walk through the topics, the chart and the form', async (page) => {
      await openChart(page, { lang: 'en' });
      await page.locator('button[data-context="season"]').click();
      await page.locator('button[data-context="roots"]').click();
      await page.locator('#relationships-topic').click();
      await page.locator('.relationship-chip').click();
      assert.equal((await linkParts(page)).topic, 'relationships/stem_combination:4:year-hour');
      const walk = [];
      for (const direction of [-1, -1, -1, -1, -1, 1, 1, 1]) {
        await step(page, direction);
        const seen = await onScreen(page);
        const parts = await linkParts(page);
        walk.push(`${seen.view} ${typeof parts === 'string' ? parts : parts.topic ?? '-'} ${seen.panel ?? '-'}`);
      }
      assert.deepEqual(walk, [
        'chart relationships Relationships',
        'chart roots Roots',
        'chart season Seasonal context',
        'chart - -',
        'form  -',
        'chart - -',
        'chart season Seasonal context',
        'chart roots Roots',
      ]);
    });

    check('Edit and New chart are steps back to the form; Back returns to the chart', async (page) => {
      await openChart(page, { lang: 'en' });
      const first = await onScreen(page);
      await press(page, '#back-btn');
      assert.equal(await linkParts(page), '');
      await step(page, -1);
      assert.deepEqual(await onScreen(page), first);
      await step(page, 1);
      assert.equal((await onScreen(page)).view, 'form');
      await page.locator('#create-chart-btn').click();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await press(page, '#new-chart-btn');
      assert.deepEqual(await fields(page), { date: '', time: '', location: '' });
      await fillChart(page, { date: '1990-01-01', time: '12:00' });
      const second = await onScreen(page);
      assert.notEqual(second.chars, first.chars);
      await step(page, -1);
      assert.equal((await onScreen(page)).view, 'form');
      // The chart before is asked for again, and its birth goes back into the form.
      await step(page, -1);
      assert.deepEqual(await onScreen(page), first);
      assert.deepEqual(await fields(page), { date: '1988-02-04', time: '16:30', location: 'Chengdu, Sichuan, China' });
      await step(page, 1);
      await step(page, 1);
      assert.deepEqual(await onScreen(page), second);
    });

    check('the display, the Zi-hour convention and the language replace the current entry', async (page) => {
      await openChart(page, { lang: 'en', place: HELSINKI, date: '1988-06-15', time: '00:50' });
      const count = await entries(page);
      await showDisplay(page, 'hidden-stems');
      await page.locator('#zi-switch button[data-zi-convention="whole_zi_23"]').click();
      await page.waitForFunction(() => !document.getElementById('chart-view').hasAttribute('aria-busy'));
      await page.locator('#chart-language button[data-chart-lang="fi"]').click();
      await page.waitForFunction(() => !document.getElementById('chart-view').hasAttribute('aria-busy'));
      await settled(page);
      assert.equal(await entries(page), count);
      const parts = await linkParts(page);
      assert.deepEqual([parts.display, parts.zi, parts.lang], ['hidden-stems', 'whole_zi_23', 'fi']);
      const before = await onScreen(page);
      await page.reload();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      await settled(page);
      assert.deepEqual(await onScreen(page), before);
      assert.equal(await page.locator('#zi-switch button[aria-pressed="true"]').getAttribute('data-zi-convention'), 'whole_zi_23');
      assert.equal(await page.locator('#pillars .hidden-stems-panel.is-expanded').count(), 4);
      // One step back leaves the chart: nothing above was a step of its own.
      await step(page, -1);
      assert.equal((await onScreen(page)).view, 'form');
    });

    check('links that open no chart say why, keep a valid birth, and leave the form\'s address', async (page) => {
      // Each part is named in words, never as the address spells it; a part the app does
      // not know is quoted as the link has it.
      const { date, ...undated } = CANONICAL;
      const bad = [
        ['#elsewhere', 'the app has no page at its address'],
        [link(undated), 'the birth date is missing'],
        [link({ ...CANONICAL, date: '1988-02-30' }), 'the birth date is not valid'],
        [link({ ...CANONICAL, time: '25:10' }), 'the birth time is not valid'],
        [link({ ...CANONICAL, latitude: '91' }), 'the latitude is not valid'],
        [link({ ...CANONICAL, lang: 'de' }), 'the language is not valid'],
        [link({ ...CANONICAL, zi: 'midnight' }), 'the Zi hour convention is not valid'],
        [link({ ...CANONICAL, fold: '2' }), 'the choice of a repeated clock time is not valid'],
        [link({ ...CANONICAL, display: 'glyphs' }), 'what the cards show is not valid'],
        [link({ ...CANONICAL, colour: 'red' }), 'the app does not know its part “colour”'],
        [`${link(CANONICAL)}&lang=fi`, 'it gives the language more than once'],
        [link({ ...CANONICAL, city: '' }), 'the city is missing'],
        [link({ ...CANONICAL, topic: 'roles/stem/noon' }), 'the open topic is not valid'],
        // Settings' own links, to save a birth.
        ['#save?as=nothing', 'what to save is not valid'],
        ['#save?as=partner', 'the chart to pair it with is missing'],
        [`#save?as=correct&chart=${'g'.repeat(32)}`, 'the chart to correct is not valid'],
      ];
      for (const [address, why] of bad) {
        await page.goto('about:blank');
        await openLink(page, address, { success: false });
        assert.equal(await page.locator('#form-error').textContent(), `This link does not open a chart: ${why}.`, address);
        assert.equal(await linkParts(page), '', address);
        assert.equal((await onScreen(page)).view, 'form', address);
      }
      // In the page's language, the reader's, whatever language the link names.
      await page.goto('about:blank');
      await openLink(page, link({ ...CANONICAL, lang: 'fi' }));
      await page.goto('about:blank');
      await openLink(page, link({ ...CANONICAL, date: '1988-02-30' }), { success: false });
      assert.equal(await page.locator('#form-error').textContent(), 'Linkki ei avaa karttaa: syntymäpäivä ei kelpaa.');
      await page.goto('about:blank');
      await openLink(page, `${link(CANONICAL)}&lang=en`, { success: false });
      assert.equal(await page.locator('#form-error').textContent(), 'Linkki ei avaa karttaa: siinä on kieli useammin kuin kerran.');
      await page.goto('about:blank');
      await openLink(page, link({ ...CANONICAL, colour: 'red' }), { success: false });
      assert.equal(await page.locator('#form-error').textContent(), 'Linkki ei avaa karttaa: sovellus ei tunne sen osaa ”colour”.');
      await page.goto('about:blank');
      await openLink(page, link({ ...CANONICAL, city: '' }), { success: false });
      assert.equal(await page.locator('#form-error').textContent(), 'Linkki ei avaa karttaa: kaupunki puuttuu.');
      await page.goto('about:blank');
      await openLink(page, link({ ...CANONICAL, lang: 'en' }));
      // A birth the chart has, with a relationship it has not: the chart is not shown, but
      // the birth waits in the form.
      await page.goto('about:blank');
      await openLink(page, link({ ...CANONICAL, topic: 'relationships/branch_clash:17:month-day' }), { success: false });
      assert.equal(await page.locator('#form-error').textContent(), 'This link does not open a chart: the open topic is not valid.');
      assert.deepEqual(await fields(page), { date: '1988-02-04', time: '16:30', location: 'Chengdu, Sichuan, China' });
      assert.equal(await linkParts(page), '');
    });

    check('an answer that arrives after a later step is not drawn', async (page) => {
      await openChart(page, { lang: 'en' });
      await press(page, '#new-chart-btn');
      await fillChart(page, { date: '1990-01-01', time: '12:00' });
      await step(page, -1);
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      let asked = 0;
      await page.route('**/api/four_pillars', async (route) => {
        asked += 1;
        await held;
        await route.fallback();
      });
      // Back to the first chart, and forward again before it arrives.
      await page.evaluate(() => history.back());
      await page.waitForFunction(() => document.getElementById('chart-form').getAttribute('aria-busy') === 'true');
      await page.evaluate(() => history.forward());
      await page.waitForFunction(() => location.hash === '' && !document.getElementById('chart-form').hasAttribute('aria-busy'));
      const answered = page.waitForResponse('**/api/four_pillars');
      release();
      await answered;
      await settled(page);
      assert.equal(asked, 1);
      assert.equal((await onScreen(page)).view, 'form');
      assert.equal(await linkParts(page), '');
      assert.equal(await page.locator('#create-chart-btn').textContent(), 'Create chart');
    });

    check('Copy link puts the address on the clipboard and says so; a refusal is said too', async (page) => {
      await page.addInitScript(() => {
        window.__copied = [];
        Object.defineProperty(navigator, 'clipboard', {
          configurable: true,
          value: {
            writeText: async (text) => {
              if (window.__refuse) throw new DOMException('Write permission denied.', 'NotAllowedError');
              window.__copied.push(text);
            },
          },
        });
      });
      await openChart(page, { lang: 'en' });
      await page.locator('button[data-context="roots"]').click();
      const toast = page.locator('.toast[role="status"]');
      assert.equal(await toast.textContent(), '');
      await press(page, '#copy-link-btn');
      await page.waitForFunction(() => document.querySelector('.toast').classList.contains('is-shown'));
      assert.deepEqual(await page.evaluate(() => window.__copied), [page.url()]);
      assert.equal(await toast.textContent(), 'Link copied');
      assert.equal(await toast.evaluate((node) => node.classList.contains('is-error')), false);
      await page.evaluate(() => { window.__refuse = true; });
      await press(page, '#copy-link-btn');
      await page.waitForFunction(() => document.querySelector('.toast').textContent === 'Could not copy the link');
      assert.equal(await toast.evaluate((node) => node.classList.contains('is-error')), true);
      assert.equal(await page.evaluate(() => window.__copied.length), 1);
    });
  });
}
