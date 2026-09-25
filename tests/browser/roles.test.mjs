import {
  assert, describe, it, profiles, openChart, fillChart, count, settled,
  geometry, natalColors, longPress, screenshot, withPage,
} from './chart-helpers.mjs';

async function openRoles(page, options = {}) {
  const payload = await openChart(page, options);
  await page.locator('[data-context="roles"]').click();
  return payload;
}

for (const profile of profiles) {
  describe(`roles / ${profile.name}`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 30000 }, () => withPage(profile, run));

    check('overview shows five groups and ten roles without changing the chart', async (page) => {
      await openChart(page);
      const before = await geometry(page);
      const colors = await natalColors(page);
      assert.equal(await page.locator('[data-context="support"]').count(), 0);
      assert.equal(await page.locator('[data-context]').count(), 3);
      await page.locator('[data-context="roles"]').click();
      await count(page, '[data-role-group]', 5);
      await count(page, '[data-role]', 10);
      await count(page, '#context-detail [data-root-pillar]', 4);
      const expected = {
        friend:'Hidden only', rob_wealth:'Hidden only', eating_god:'Hidden only', hurting_officer:'Hidden only',
        indirect_wealth:'Visible and hidden', direct_wealth:'Visible and hidden', seven_killings:'Hidden only',
        direct_officer:'Not present', indirect_resource:'Visible only', direct_resource:'Not present',
      };
      for (const [name, state] of Object.entries(expected)) {
        assert.equal(await page.locator(`[data-role="${name}"] .role-presence`).textContent(), state);
      }
      assert.deepEqual(await geometry(page), before);
      assert.deepEqual(await natalColors(page), colors);
      await count(page, '.card.is-context-source, .card.is-context-reference, .card.is-flipped', 0);
      await screenshot(page, `${profile.name}-roles-overview`);
    });

    check('individual role highlights only its visible and hidden occurrences', async (page) => {
      await openRoles(page);
      await page.locator('[data-role="direct_wealth"]').click();
      await count(page, '.card.stem.is-context-source', 1);
      await count(page, '.card.branch.is-context-source', 1);
      await count(page, '#pillars .is-context-evidence', 2);
      assert.equal(await page.locator('.card.stem.is-context-source').getAttribute('data-pillar'), 'hour');
      assert.equal(await page.locator('.card.branch.is-context-source').getAttribute('data-pillar'), 'hour');
      await count(page, '[data-role-occurrence]', 2);
      assert.equal(await page.locator('[data-role-occurrence="hidden:hour:壬"]').count(), 1);
      assert.match(await page.locator('#context-detail').innerText(), /Exact stem visible:/);
      await screenshot(page, `${profile.name}-roles-direct-wealth`);
    });

    check('Ren roots preserve natal roles and separate exact matches from opposite polarity', async (page) => {
      await openRoles(page);
      await page.locator('[data-role="direct_wealth"]').click();
      await page.locator('[data-root-pillar="hour"]').first().click();
      await count(page, '.card.is-context-reference', 1);
      assert.equal(await page.locator('.card.is-context-reference').getAttribute('data-pillar'), 'hour');
      assert.equal(await page.locator('.card.is-context-reference').evaluate(n => getComputedStyle(n).outlineStyle), 'dotted');
      await count(page, '.card.branch.is-context-source', 3);
      await count(page, '#pillars .is-context-evidence', 6);
      const text = await page.locator('#context-detail').innerText();
      assert.match(text, /Exact hidden-stem matches: 1/);
      assert.equal((text.match(/Same element, opposite polarity/g) || []).length, 2);
      assert.match(text, /Indirect Wealth/);
      assert.match(text, /relative to the natal Day Master/);
      await screenshot(page, `${profile.name}-roles-ren-roots`);
    });

    check('unrooted visible Resource remains present without an effectiveness verdict', async (page) => {
      await openRoles(page);
      await page.locator('[data-role="indirect_resource"]').click();
      await count(page, '.card.stem.is-context-source', 1);
      await count(page, '.card.branch.is-context-source', 0);
      await page.locator('[data-root-pillar="year"]').click();
      await count(page, '.card.is-context-reference', 1);
      await count(page, '.card.is-context-source', 0);
      const text = await page.locator('#context-detail').innerText();
      assert.match(text, /No same-element hidden-stem roots detected for Ding 丁/);
      assert.match(text, /does not establish effectiveness or overall support/);
      assert.match(text, /Exact hidden-stem matches: 0/);
      await screenshot(page, `${profile.name}-roles-unrooted`);
    });

    check('exact hidden matches identify the Day Master without adding a visible Companion', async (page) => {
      await openRoles(page);
      assert.match(await page.locator('[data-role="friend"]').innerText(), /Hidden only/);
      await page.locator('[data-role="friend"]').click();
      await count(page, '[data-role-surface="visible"] [data-role-occurrence]', 0);
      await count(page, '[data-role-surface="hidden"] [data-role-occurrence]', 2);
      await count(page, '[data-root-pillar="day"]', 2);
      assert.match(await page.locator('.role-exact').first().innerText(), /Day Master/);
      await page.locator('[data-root-pillar="day"]').first().click();
      assert.equal(await page.locator('.card.is-context-reference').getAttribute('data-pillar'), 'day');
      await count(page, '.card.branch.is-context-source', 3);
    });

    check('hidden-to-visible matches require the same stem, not only the same element', async (page) => {
      await openRoles(page);
      await page.locator('[data-role="rob_wealth"]').click();
      await count(page, '[data-role-occurrence]', 1);
      await count(page, '#context-detail [data-root-pillar]', 0);
      assert.match(await page.locator('#context-detail').innerText(), /No exact visible match/);
      await page.locator('[data-role-back]').click();
      await page.locator('[data-root-pillar="day"]').click();
      assert.match(await page.locator('#context-detail').innerText(), /Wu 戊/);
      assert.match(await page.locator('#context-detail').innerText(), /Same element, opposite polarity/);
    });

    check('absent individual roles stay inspectable even when their group is present', async (page) => {
      await openRoles(page);
      assert.match(await page.locator('[data-role-group="authority"] .role-group-heading').innerText(), /Hidden only/);
      await page.locator('[data-role="direct_officer"]').click();
      await count(page, '.card.is-context-source, .card.is-context-reference', 0);
      assert.match(await page.locator('.role-empty').innerText(), /Direct Officer is not present in the natal visible or hidden stems/);
      await screenshot(page, `${profile.name}-roles-absent`);
    });

    check('all four visible stems have separate root inspection entries', async (page) => {
      await openRoles(page);
      for (const pillar of ['hour','day','month','year']) {
        await page.locator(`[data-root-pillar="${pillar}"]`).click();
        assert.equal(await page.locator('.card.is-context-reference').getAttribute('data-pillar'), pillar);
        await page.locator('[data-role-back]').click();
        assert.equal(await page.locator(`[data-root-pillar="${pillar}"]`).evaluate(n => n === document.activeElement), true);
      }
    });

    check('root and role detail navigation returns keyboard focus to the source control', async (page) => {
      await openRoles(page);
      const choice = page.locator('[data-role="indirect_wealth"]');
      await choice.focus(); await page.keyboard.press('Enter');
      assert.equal(await page.locator('#context-detail-title').evaluate(n=>n===document.activeElement), true);
      await page.locator('[data-root-pillar="month"]').first().focus(); await page.keyboard.press('Enter');
      await page.locator('[data-role-back]').click();
      assert.equal(await page.locator('[data-root-pillar="month"]').first().evaluate(n=>n===document.activeElement), true);
      await page.locator('[data-role-back]').click();
      assert.equal(await choice.evaluate(n=>n===document.activeElement), true);
      await page.keyboard.press('Space');
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('[data-context="roles"]').evaluate(n=>n===document.activeElement), true);
      assert.equal(await page.locator('#context-detail').isVisible(), false);
    });

    check('roles, context and relationship selections replace one another completely', async (page) => {
      await openRoles(page);
      const before=await geometry(page);
      await page.locator('[data-root-pillar="hour"]').click();
      await page.locator('.relationship-chip').click();
      await count(page,'.card.is-context-reference, .card.is-context-source, #pillars .is-context-evidence',0);
      assert.equal(await page.locator('#context-detail').isVisible(),false);
      await page.locator('[data-context="roles"]').click();
      await count(page,'.card.is-related',0);
      assert.equal(await page.locator('#relationship-detail').isVisible(),false);
      await page.locator('[data-role="indirect_wealth"]').click();
      await page.locator('[data-context="roots"]').click();
      await count(page,'.card.is-context-reference',0);
      await count(page,'.card.branch.is-context-source',3);
      await page.locator('[data-context="roles"]').click();
      await count(page,'.card.is-context-source, #pillars .is-context-evidence',0);
      await count(page,'[data-role]',10);
      assert.deepEqual(await geometry(page),before);
    });

    check('role highlights survive flips and taps without changing card state automatically', async (page) => {
      await openRoles(page);
      await page.locator('[data-role="indirect_wealth"]').click();
      const dayBranch=page.locator('.card.branch[data-pillar="day"]');
      if(profile.hasTouch) await dayBranch.tap(); else await dayBranch.click();
      await count(page,'.hidden-stems-panel.is-expanded',1);
      await count(page,'.hidden-stems-panel[data-pillar="day"] .is-context-evidence',1);
      await longPress(page,page.locator('.card.branch[data-pillar="month"]'));
      await count(page,'.hidden-stems-panel.is-expanded',1);
      await page.locator('#ten-gods-toggle').click(); await settled(page);
      await count(page,'.card.is-flipped',8);
      await count(page,'.card.is-context-source',3);
      await count(page,'#pillars .is-context-evidence',4);
      await screenshot(page,`${profile.name}-roles-flipped`);
    });

    check('repeated identical visible stems remain independently inspectable', async (page) => {
      const payload=await openRoles(page,{date:'1990-01-08',time:'12:00'});
      const stems=payload.role_profile.visible_stems;
      const pair=stems.filter(s=>s.char===stems[1].char);
      assert.ok(pair.length>=2);
      for(const s of pair) {
        await page.locator(`[data-root-pillar="${s.pillar}"]`).click();
        assert.equal(await page.locator('.card.is-context-reference').getAttribute('data-pillar'),s.pillar);
        await page.locator('[data-role-back]').click();
      }
    });

    check('all ten role details and four-root layouts fit Finnish narrow viewports', async (page) => {
      const payload=await openRoles(page,{date:'1990-01-13',time:'12:00',lang:'fi'});
      assert.equal(await page.locator('[data-context="roles"]').textContent(),'Roolit');
      for(const width of [320,390,641,768,1440]) {
        await page.setViewportSize({width,height:900});
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      }
      await page.setViewportSize({width:320,height:900});
      for(const group of payload.role_profile.groups) for(const role of group.roles) {
        await page.locator(`[data-role="${role.ten_god}"]`).click();
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,role.ten_god);
        assert.doesNotMatch(await page.locator('#context-detail').innerText(),/roles_|ten_god_|qi_/);
        await page.locator('[data-role-back]').click();
      }
      await page.locator('[data-root-pillar="day"]').click();
      await count(page,'#context-detail .relationship-member',4);
      await page.setViewportSize(profile.viewport);
      await screenshot(page,`${profile.name}-roles-finnish-roots`);
    });

    check('reduced motion and clearing nested root details remove all evidence', async (page) => {
      await page.emulateMedia({reducedMotion:'reduce'});
      await openRoles(page);
      assert.equal(await page.locator('[data-role]').first().evaluate(n=>getComputedStyle(n).transitionDuration),'0s');
      await page.locator('[data-root-pillar="month"]').click();
      await page.locator('#ten-gods-toggle').click();
      await count(page,'.card.is-turning',0);
      await page.locator('[data-clear-context]').click();
      await count(page,'.card.is-context-reference, .card.is-context-source, #pillars .is-context-evidence',0);
      assert.equal(await page.locator('[data-context="roles"]').evaluate(n=>n===document.activeElement),true);
    });

    check('new charts reset the overview and contain no previous role or root state', async (page) => {
      await openRoles(page);
      await page.locator('[data-root-pillar="hour"]').click();
      await page.locator('#back-btn').click();
      await fillChart(page,{date:'1990-05-09',time:'12:00'});
      await count(page,'.card.is-context-reference, .card.is-context-source, #pillars .is-context-evidence',0);
      assert.equal(await page.locator('#context-detail').isVisible(),false);
      await page.locator('[data-context="roles"]').click();
      assert.match(await page.locator('[data-role-group="companion"]').innerText(),/Not present/);
      assert.match(await page.locator('[data-role-group="resource"]').innerText(),/Not present/);
      await count(page,'[data-role]',10);
    });

    const corruptions = [
      ['missing role profile',p=>{delete p.role_profile;}],
      ['unsupported role policy',p=>{p.role_profile.policy='scored';}],
      ['missing individual role',p=>{p.role_profile.groups[0].roles.pop();}],
      ['wrong role-group element',p=>{p.role_profile.groups[0].element='fire';}],
      ['incorrect presence state',p=>{p.role_profile.groups[0].roles[0].presence='visible_only';}],
      ['missing visible occurrence',p=>{p.role_profile.groups[2].roles[0].visible.pop();}],
      ['duplicate hidden occurrence',p=>{p.role_profile.groups[0].roles[0].hidden.push(p.role_profile.groups[0].roles[0].hidden[0]);}],
      ['wrong stable occurrence identity',p=>{p.role_profile.groups[0].roles[0].hidden[0].id='hidden:hour:己';}],
      ['missing visible-stem roots',p=>{p.role_profile.visible_stems[1].roots.pop();}],
      ['opposite-polarity root passed as an exact match',p=>{p.role_profile.visible_stems[3].exact_hidden_matches.push('hidden:month:癸');}],
      ['root Ten Gods silently recentered',p=>{p.role_profile.visible_stems[3].roots[0].ten_god='rob_wealth';}],
      ['Day Master counted as visible Companion',p=>{p.role_profile.groups[0].roles[0].visible.push({...p.role_profile.visible_stems[2],component:'stem',branch:null,qi_type:null});}],
    ];
    for(const [name,mutate] of corruptions) {
      check(`${name} fails visibly before showing a partial chart`,async(page)=>{
        await openChart(page,{success:false},mutate);
        assert.equal(await page.locator('#chart-view').isVisible(),false);
        assert.match(await page.locator('#form-error').innerText(),/Could not read the natal role profile/);
      });
    }
  });
}
