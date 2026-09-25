import {
  assert, describe, it, engineName, profiles, openChart, fillChart, count, settled,
  geometry, natalColors, longPress, screenshot, withPage,
} from './chart-helpers.mjs';

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name}`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 30000 }, () => withPage(profile, run));

    check('Day Master and exact roots are visible without changing chart geometry', async (page) => {
      await openChart(page);
      assert.equal(await page.locator('#day-master-heading').innerText(), 'Day Master · Ji — Yin Earth');
      assert.equal(await page.locator('[data-context]').count(), 3);
      assert.equal(await page.locator('[data-context="roots"]').innerText(), 'Roots in 3 branches');
      const before = await geometry(page);
      const colors = await natalColors(page);
      await screenshot(page, `${profile.name}-context-overview`);
      await page.locator('[data-context="roots"]').click();
      assert.deepEqual(await geometry(page), before);
      assert.deepEqual(await natalColors(page), colors);
      await count(page, '.card.branch.is-context-source', 3);
      await count(page, '.card.stem.is-context-source', 0);
      await count(page, '#pillars .is-context-evidence', 6);
      await count(page, '#context-detail .context-evidence-row', 3);
      const text = await page.locator('#context-detail').innerText();
      assert.equal((text.match(/Exact stem/g) || []).length, 2);
      assert.equal((text.match(/Same element, opposite polarity/g) || []).length, 1);
      for (const word of ['Wu 戊', 'Ji 己', 'residual', 'main', 'Presence does not measure']) assert.ok(text.includes(word), word);
      assert.deepEqual(await page.locator('.card.branch.is-context-source').evaluateAll(nodes => nodes.map(n => n.dataset.pillar)), ['hour', 'day', 'month']);
      assert.deepEqual(await page.locator('.card.branch .is-context-evidence').evaluateAll(nodes => nodes.map(n => [n.closest('.card').dataset.pillar, n.dataset.hiddenStem])), [['hour', '戊'], ['day', '己'], ['month', '己']]);
      await count(page, '.card.is-flipped, .hidden-stems-panel.is-expanded', 0);
      await screenshot(page, `${profile.name}-context-roots`);
    });

    check('seasonal group remains distinct from the month branch composition', async (page) => {
      await openChart(page);
      const before = await geometry(page);
      await page.locator('[data-context="season"]').click();
      await count(page, '.card.is-context-source', 1);
      assert.equal(await page.locator('.card.is-context-source').getAttribute('data-pillar'), 'month');
      await count(page, '#pillars .is-context-evidence', 6);
      const text = await page.locator('#context-detail').innerText();
      for (const word of ['Traditional season: Winter · Water', 'Chou 丑', 'Yin Earth', 'Ji 己', 'Gui 癸', 'Xin 辛', 'not local weather']) assert.ok(text.includes(word), word);
      assert.deepEqual(await geometry(page), before);
      await screenshot(page, `${profile.name}-context-season`);
    });

    check('Roles retains Companion and Resource evidence without counting the Day Master', async (page) => {
      await openChart(page);
      await page.locator('[data-context="roles"]').click();
      assert.match(await page.locator('[data-role-group="companion"]').innerText(), /Hidden only/);
      assert.match(await page.locator('[data-role-group="resource"]').innerText(), /Visible only/);
      await page.locator('[data-role="friend"]').click();
      await count(page, '[data-role-surface="visible"] [data-role-occurrence]', 0);
      await count(page, '[data-role-surface="hidden"] [data-role-occurrence]', 2);
      assert.equal(await page.locator('.card.stem[data-pillar="day"]').evaluate(n => n.classList.contains('is-context-source')), false);
      await page.locator('[data-role-back]').click();
      await page.locator('[data-role="indirect_resource"]').click();
      assert.match(await page.locator('#context-detail').innerText(), /Ding 丁/);
      assert.deepEqual(await page.locator('.card.stem.is-context-source').evaluateAll(nodes => nodes.map(n => n.dataset.pillar)), ['year']);
    });

    check('relationship and context selections replace one another and clear all old evidence', async (page) => {
      await openChart(page);
      const before = await geometry(page);
      await page.locator('[data-context="roots"]').click();
      await page.locator('.relationship-chip').click();
      await count(page, '.card.is-context-source, #pillars .is-context-evidence', 0);
      assert.equal(await page.locator('#context-detail').isVisible(), false);
      await count(page, '.card.is-related', 2);
      for (const key of ['season', 'roots', 'roles']) {
        await page.locator(`[data-context="${key}"]`).click();
        await count(page, '.card.is-related', 0);
        assert.equal(await page.locator('#relationship-detail').isVisible(), false);
        await count(page, '#context-controls [aria-expanded="true"]', 1);
      }
      await page.locator('[data-context="roles"]').click();
      await count(page, '.card.is-context-source, #pillars .is-context-evidence', 0);
      assert.equal(await page.locator('#context-detail').isVisible(), false);
      assert.deepEqual(await geometry(page), before);
    });

    check('keyboard, clear and Escape preserve focus and announce the selected topic', async (page) => {
      await openChart(page);
      const roots = page.locator('[data-context="roots"]');
      await roots.focus(); await page.keyboard.press('Enter');
      assert.equal(await roots.getAttribute('aria-controls'), 'context-detail');
      assert.equal(await roots.getAttribute('aria-expanded'), 'true');
      assert.match(await page.locator('#context-status').textContent(), /Highlighted: Roots/);
      await page.locator('[data-clear-context]').focus(); await page.keyboard.press('Escape');
      assert.equal(await roots.evaluate(n => n === document.activeElement), true);
      assert.equal(await roots.getAttribute('aria-expanded'), 'false');
      await page.keyboard.press('Space');
      await page.locator('[data-clear-context]').click();
      assert.equal(await roots.evaluate(n => n === document.activeElement), true);
      await count(page, '.card.is-context-source, #pillars .is-context-evidence', 0);
      assert.equal(await page.locator('#context-status').textContent(), '');
    });

    check('root row highlights survive individual and global flips and existing branch clicks', async (page) => {
      await openChart(page);
      const dayBranch = page.locator('.card.branch[data-pillar="day"]');
      if (profile.hasTouch) await dayBranch.tap(); else await dayBranch.click();
      await count(page, '.hidden-stems-panel.is-expanded', 1);
      await page.locator('[data-context="roots"]').click();
      await count(page, '.hidden-stems-panel.is-expanded', 1);
      await count(page, '.hidden-stems-panel[data-pillar="day"] .is-context-evidence', 1);
      const hourBranch = page.locator('.card.branch[data-pillar="hour"]');
      await longPress(page, hourBranch);
      await count(page, '.hidden-stems-panel.is-expanded', 1);
      assert.equal(await page.locator('#ten-gods-toggle').getAttribute('aria-pressed'), 'mixed');
      await page.locator('#ten-gods-toggle').click(); await settled(page);
      await count(page, '.card.is-flipped', 8);
      await count(page, '.card.is-context-source', 3);
      await count(page, '#pillars .is-context-evidence', 6);
      await count(page, '.hidden-stems-panel.is-expanded', 1);
      if (profile.hasTouch) await dayBranch.tap(); else await dayBranch.click();
      await count(page, '.hidden-stems-panel.is-expanded', 0);
      await screenshot(page, `${profile.name}-context-flipped`);
    });

    check('Resource roles remain separate from the Day Master root view', async (page) => {
      const payload=await openChart(page,{date:'1990-01-02',time:'12:00'});
      await page.locator('[data-context="roles"]').click();
      assert.match(await page.locator('[data-role-group="resource"]').innerText(), /Visible and hidden/);
      await page.locator('[data-context="roots"]').click();
      const resourceChars=payload.day_master_context.support.resources.map(e=>e.char);
      const rootChars=await page.locator('#context-detail .context-evidence-row').evaluateAll(nodes=>nodes.map(n=>n.dataset.evidenceChar));
      assert.equal(rootChars.some(char=>resourceChars.includes(char)),false);
    });

    check('no roots is explicit even when hidden Resource exists', async (page) => {
      await openChart(page, { date: '1990-01-09', time: '12:00' });
      assert.equal(await page.locator('[data-context="roots"]').innerText(), 'No roots detected');
      await page.locator('[data-context="roots"]').click();
      await count(page, '.card.is-context-source', 0);
      await count(page, '#context-detail .context-evidence-row', 0);
      assert.match(await page.locator('#context-detail').innerText(), /No hidden stems contain/);
      await page.locator('[data-context="roles"]').click();
      assert.match(await page.locator('[data-role-group="resource"]').innerText(), /Hidden/);
      await screenshot(page, `${profile.name}-context-no-roots`);
    });

    check('absence of both support groups is retained in the complete Roles view', async (page) => {
      await openChart(page,{date:'1990-05-09',time:'12:00'});
      await page.locator('[data-context="roles"]').click();
      await count(page,'.card.is-context-source',0);
      assert.match(await page.locator('[data-role-group="companion"]').innerText(),/Not present/);
      assert.match(await page.locator('[data-role-group="resource"]').innerText(),/Not present/);
      await page.locator('[data-context="season"]').click();
      await count(page,'.card.is-context-source',1);
    });

    check('one and four root branches use correct labels and retain all occurrences', async (page) => {
      await openChart(page, { date: '1990-01-08', time: '12:00' });
      assert.equal(await page.locator('[data-context="roots"]').innerText(), 'Root in one branch');
      await page.locator('#back-btn').click();
      await fillChart(page, { date: '1990-01-13', time: '12:00' });
      assert.equal(await page.locator('[data-context="roots"]').innerText(), 'Roots in 4 branches');
      const before = await geometry(page);
      await page.locator('[data-context="roots"]').click();
      await count(page, '.card.branch.is-context-source', 4);
      await count(page, '#context-detail .relationship-member', 4);
      assert.deepEqual(await geometry(page), before);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      await screenshot(page, `${profile.name}-context-four-roots`);
    });

    check('the resolved solar-month boundary changes seasonal context within one date', async (page) => {
      await openChart(page);
      await page.locator('[data-context="season"]').click();
      assert.match(await page.locator('#context-detail').innerText(), /Winter · Water/);
      await page.locator('#back-btn').click();
      await fillChart(page, { time: '23:30' });
      assert.equal(await page.locator('[data-context="season"]').innerText(), 'Yin month');
      await page.locator('[data-context="season"]').click();
      assert.match(await page.locator('#context-detail').innerText(), /Spring · Wood/);
      assert.doesNotMatch(await page.locator('#context-detail').innerText(), /Winter/);
    });

    check('Finnish context and four-root layouts fit narrow and desktop viewports', async (page) => {
      await openChart(page, { date: '1990-01-13', time: '12:00', lang: 'fi' });
      assert.match(await page.locator('#day-master-heading').innerText(), /Päivän mestari/);
      for (const key of ['season', 'roots', 'roles']) {
        await page.locator(`[data-context="${key}"]`).click();
        for (const width of [320, 390, 641, 768, 1440]) {
          await page.setViewportSize({ width, height: 900 });
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${key}: overflow at ${width}`);
        }
        assert.doesNotMatch(await page.locator('#chart-view').innerText(), /context_|ten_god_|qi_/);
      }
      await page.setViewportSize(profile.viewport);
      await page.locator('[data-context="roots"]').click();
      await page.locator('#ten-gods-toggle').click(); await settled(page);
      await count(page, '.card.is-flipped', 8);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      await screenshot(page, `${profile.name}-context-finnish`);
    });

    check('reduced motion does not introduce animations when inspecting evidence', async (page) => {
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await openChart(page);
      await page.locator('[data-context="roots"]').click();
      await page.locator('#ten-gods-toggle').click();
      await count(page, '.card.is-flipped', 8);
      await count(page, '.card.is-turning', 0);
      assert.equal(await page.locator('[data-context="roots"]').evaluate(n => getComputedStyle(n).transitionDuration), '0s');
      await page.keyboard.press('Escape');
      await count(page, '.card.is-context-source', 0);
    });

    check('new charts reset detail, highlights and card state without stale root evidence', async (page) => {
      await openChart(page);
      await page.locator('[data-context="roots"]').click();
      await page.locator('#ten-gods-toggle').click(); await settled(page);
      await page.locator('#back-btn').click();
      await fillChart(page, { date: '1990-05-09', time: '12:00' });
      await count(page, '.card.is-context-source, #pillars .is-context-evidence, .card.is-flipped', 0);
      assert.equal(await page.locator('#context-detail').isVisible(), false);
      assert.equal(await page.locator('[data-context="roots"]').innerText(), 'No roots detected');
      assert.match(await page.locator('#day-master-heading').innerText(), /Jia — Yang Wood/);
    });

    const corruptions = [
      ['missing context', p => { delete p.day_master_context; }],
      ['unsupported policy', p => { p.day_master_context.policy = 'weighted_v2'; }],
      ['wrong Day Master', p => { p.day_master_context.day_master.char = '甲'; }],
      ['missing root evidence', p => { p.day_master_context.roots.pop(); }],
      ['wrong root match', p => { p.day_master_context.roots[0].match = 'opposite_polarity'; }],
      ['wrong season group', p => { p.day_master_context.season.name = 'summer'; }],
      ['fabricated visible companion', p => { p.day_master_context.support.companions.push({...p.day_master_context.support.companions[0], pillar:'day', component:'stem', branch:null, qi_type:null}); }],
      ['missing hidden-stem surface data', p => { delete p.hidden_stems; }],
      ['inconsistent hidden-stem element', p => { p.hidden_stems.month.hidden_stems[0].element = 'fire'; }],
      ['inconsistent hidden-stem qi position', p => { p.hidden_stems.month.hidden_stems[0].qi_type = 'residual'; }],
      ['inconsistent hidden-stem branch', p => { p.hidden_stems.month.branch = '寅'; }],
    ];
    for (const [name, mutate] of corruptions) {
      check(`${name} fails visibly instead of showing misleading context`, async (page) => {
        await openChart(page, { success: false }, mutate);
        assert.equal(await page.locator('#chart-view').isVisible(), false);
        assert.match(await page.locator('#location-status').innerText(), /Could not read Day Master context/);
      });
    }
  });
}
