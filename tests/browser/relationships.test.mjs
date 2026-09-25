import {
  assert, describe, it, engineName, profiles, openChart, fillChart, count,
  geometry, natalColors, longPress, screenshot, withPage, showDisplay, openRelationships,
} from './chart-helpers.mjs';

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name}`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 30000 }, () => withPage(profile, run));

    check('canonical selection preserves geometry and natal colors', async (page) => {
      await openChart(page);
      assert.equal(await page.locator('.relationship-chip').count(), 1);
      assert.equal(await page.locator('#relationships-topic').textContent(), 'Relationships (1)');
      const before = await geometry(page);
      const colors = await natalColors(page);
      await screenshot(page, `${profile.name}-overview`);
      await openRelationships(page);
      await page.locator('.relationship-chip').click();
      await count(page, '.card.is-related', 2);
      assert.deepEqual(await geometry(page), before);
      assert.deepEqual(await natalColors(page), colors);
      assert.equal(await page.locator('.card.branch.is-related').count(), 0);
      const detail = await page.locator('#relationship-detail').innerText();
      for (const text of ['Non-adjacent pillars', 'Potential element: Wood', 'Indirect Resource', 'Direct Wealth', 'Transformation has not been assessed.']) {
        assert.ok(detail.includes(text), text);
      }
      await screenshot(page, `${profile.name}-selected`);
      await page.locator('.relationship-chip').click();
      await count(page, '.card.is-related', 0);
      assert.equal(await page.locator('#relationship-detail').isVisible(), false);
    });

    check('keyboard selection, Escape, and close return focus', async (page) => {
      await openChart(page);
      const topic = page.locator('#relationships-topic');
      await topic.focus();
      await page.keyboard.press('Enter');
      assert.equal(await topic.getAttribute('aria-expanded'), 'true');
      const chip = page.locator('.relationship-chip');
      await chip.focus();
      await page.keyboard.press('Enter');
      await count(page, '.card.is-related', 2);
      assert.equal(await chip.getAttribute('aria-expanded'), 'true');
      // The first Escape clears the relationship, the next closes their list.
      await page.keyboard.press('Escape');
      await count(page, '.card.is-related', 0);
      assert.equal(await chip.evaluate((node) => node === document.activeElement), true);
      await page.keyboard.press('Escape');
      assert.equal(await topic.getAttribute('aria-expanded'), 'false');
      assert.equal(await page.locator('#chart-panel').isVisible(), false);
      assert.equal(await topic.evaluate((node) => node === document.activeElement), true);
      // Close does both at once.
      await page.keyboard.press('Space');
      await chip.focus();
      await page.keyboard.press('Space');
      await count(page, '.card.is-related', 2);
      await page.locator('[data-close-panel]').click();
      await count(page, '.card.is-related', 0);
      assert.equal(await chip.getAttribute('aria-expanded'), 'false');
      assert.equal(await topic.getAttribute('aria-expanded'), 'false');
      assert.equal(await topic.evaluate((node) => node === document.activeElement), true);
    });

    check('the display reads mixed after a long press or a tap, and pressing it again shows it on every card', async (page) => {
      await openChart(page);
      const pressed = () => page.locator('#display-switch button').evaluateAll((buttons) =>
        buttons.map((button) => `${button.dataset.display} ${button.getAttribute('aria-pressed')}`));
      assert.deepEqual(await pressed(), ['characters true', 'ten-gods false', 'hidden-stems false']);
      await longPress(page, page.locator('.card.stem').first());
      assert.deepEqual(await pressed(), ['characters mixed', 'ten-gods false', 'hidden-stems false']);
      await showDisplay(page, 'characters');
      await count(page, '.card.is-flipped', 0);
      assert.deepEqual(await pressed(), ['characters true', 'ten-gods false', 'hidden-stems false']);
      await longPress(page, page.locator('.card.stem').first());
      await showDisplay(page, 'ten-gods');
      await count(page, '.card.is-flipped', 8);
      assert.deepEqual(await pressed(), ['characters false', 'ten-gods true', 'hidden-stems false']);
      const branch = page.locator('.card.branch').first();
      if (profile.hasTouch) await branch.tap(); else await branch.click();
      await count(page, '.hidden-stems-panel.is-expanded', 1);
      assert.deepEqual(await pressed(), ['characters false', 'ten-gods mixed', 'hidden-stems false']);
      await showDisplay(page, 'ten-gods');
      await count(page, '.hidden-stems-panel.is-expanded', 0);
      await count(page, '.card.is-flipped', 8);
      assert.deepEqual(await pressed(), ['characters false', 'ten-gods true', 'hidden-stems false']);
      await showDisplay(page, 'characters');
      await count(page, '.card.is-flipped', 0);
      await count(page, '.hidden-stems-panel.is-expanded', 0);
    });

    check('branch long press does not expand; quick click or tap still does', async (page) => {
      await openChart(page);
      await openRelationships(page);
      await page.locator('.relationship-chip').click();
      const card = page.locator('.card.branch').first();
      await longPress(page, card);
      await count(page, '.hidden-stems-panel.is-expanded', 0);
      if (profile.hasTouch) await card.tap(); else await card.click();
      await count(page, '.hidden-stems-panel.is-expanded', 1);
      await count(page, '.card.is-related', 2);
      if (profile.hasTouch) await card.tap(); else await card.click();
      await count(page, '.hidden-stems-panel.is-expanded', 0);
    });

    check('cancelled touch hold cannot flip or expand a card', async (page) => {
      await openChart(page);
      const card = page.locator('.card.branch').first();
      const pointer = { pointerId: 9, pointerType: 'touch', isPrimary: true, button: 0, clientX: 20, clientY: 20 };
      await card.dispatchEvent('pointerdown', pointer);
      await card.dispatchEvent('pointercancel', pointer);
      // Wait out the half-second timer after cancellation, not just the immediate state.
      await page.waitForTimeout(1100);
      await count(page, '.card.is-flipped', 0);
      await count(page, '.hidden-stems-panel.is-expanded', 0);
    });

    check('branch clashes expose all hidden roles without changing element colors', async (page) => {
      const payload = await openChart(page, { date: '1990-01-05', time: '12:00' });
      const colors = await natalColors(page);
      await openRelationships(page);
      await page.locator('[data-kind="branch_clash"]').click();
      await count(page, '.card.branch.is-related', 2);
      assert.equal(await page.locator('.card.is-related').first().evaluate((node) => getComputedStyle(node).outlineStyle), 'dashed');
      const clash = payload.interactions.find((relationship) => relationship.kind === 'branch_clash');
      const roleCount = clash.members.reduce((total, member) => total + payload.ten_gods[member.pillar].hidden_stems.length, 0);
      assert.equal(await page.locator('#relationship-detail .hidden-stem-item').count(), roleCount);
      assert.ok((await page.locator('#relationship-detail').innerText()).includes('Strength and effects have not been assessed.'));
      assert.deepEqual(await natalColors(page), colors);
      await screenshot(page, `${profile.name}-clash`);
    });

    check('repeated branch combination occurrences stay independently selectable', async (page) => {
      await openChart(page, { date: '1990-01-07', time: '12:00' });
      await openRelationships(page);
      const chips = page.locator('[data-kind="branch_combination"]');
      assert.equal(await chips.count(), 2);
      await chips.nth(0).click();
      const first = await page.locator('.card.is-related').evaluateAll((cards) => cards.map((card) => card.dataset.pillar));
      await chips.nth(1).click();
      const second = await page.locator('.card.is-related').evaluateAll((cards) => cards.map((card) => card.dataset.pillar));
      assert.equal(first.length, 2);
      assert.equal(second.length, 2);
      assert.notDeepEqual(first, second);
      assert.equal(await page.locator('.relationship-chip.is-active').count(), 1);
    });

    check('complete frames preserve repeated occurrences and three participants', async (page) => {
      await openChart(page, { date: '1990-01-08', time: '12:00' });
      await openRelationships(page);
      const chips = page.locator('[data-kind="harmony_frame"]');
      assert.equal(await chips.count(), 2);
      await chips.first().click();
      await count(page, '.card.branch.is-related', 3);
      assert.ok((await page.locator('#relationship-detail').innerText()).includes('Complete frame present.'));
      assert.equal(await page.locator('#relationship-detail .relationship-member').count(), 3);
      await screenshot(page, `${profile.name}-frame`);
      await chips.last().click();
      await count(page, '.card.branch.is-related', 3);
      assert.equal(await page.locator('.relationship-chip.is-active').count(), 1);
    });

    check('empty charts say what was checked and still expose Ten Gods', async (page) => {
      await openChart(page, { date: '1990-01-01', time: '12:00' });
      assert.equal(await page.locator('.relationship-chip').count(), 0);
      assert.equal(await page.locator('#relationships-topic').textContent(), 'Relationships (0)');
      await openRelationships(page);
      assert.equal(await page.locator('#relationship-empty').isVisible(), true);
      assert.match(await page.locator('#relationship-empty').innerText(), /No combinations, clashes or complete harmony frames/);
      await showDisplay(page, 'ten-gods');
      await count(page, '.card.is-flipped', 8);
    });

    check('Finnish labels and narrow layouts remain readable', async (page) => {
      await openChart(page, { date: '1990-01-08', time: '12:00', lang: 'fi' });
      assert.equal(await page.locator('#relationships-heading').textContent(), 'Yhteydet');
      await openRelationships(page);
      await page.locator('.relationship-chip').first().click();
      assert.match(await page.locator('#relationship-detail').innerText(), /Muuntumista ei ole arvioitu/);
      assert.doesNotMatch(await page.locator('#chart-view').innerText(), /relationship_|ten_god_|qi_/);
      for (const width of [320, 390, 768]) {
        await page.setViewportSize({ width, height: 900 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `overflow at ${width}`);
      }
      await page.setViewportSize(profile.viewport);
      await showDisplay(page, 'ten-gods');
      await count(page, '.card.is-flipped', 8);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      await screenshot(page, `${profile.name}-finnish`);
    });

    check('reduced motion flips immediately without turn animations', async (page) => {
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await openChart(page);
      await page.locator('#display-switch button[data-display="ten-gods"]').click();
      await count(page, '.card.is-flipped', 8);
      assert.equal(await page.locator('.card.is-turning').count(), 0);
    });

    check('returning to the form and creating another chart clears all state', async (page) => {
      await openChart(page);
      await openRelationships(page);
      await page.locator('.relationship-chip').click();
      await showDisplay(page, 'ten-gods');
      await page.locator('#back-btn').click();
      await fillChart(page, { date: '1990-01-01', time: '12:00' });
      await count(page, '.card.is-related', 0);
      await count(page, '.card.is-flipped', 0);
      assert.equal(await page.locator('#display-switch button[data-display="characters"]').getAttribute('aria-pressed'), 'true');
      assert.equal(await page.locator('#chart-panel').isVisible(), false);
      assert.equal(await page.locator('#relationships-topic').getAttribute('aria-expanded'), 'false');
      await openRelationships(page);
      assert.equal(await page.locator('#relationship-detail').isVisible(), false);
      assert.equal(await page.locator('#relationship-empty').isVisible(), true);
    });

    check('missing enrichment fails visibly instead of pretending no relationships', async (page) => {
      await openChart(page, { success: false }, (payload) => { delete payload.interactions; });
      assert.equal(await page.locator('#chart-view').isVisible(), false);
      assert.match(await page.locator('#form-error').innerText(), /Could not read chart relationships/);
    });

    check('malformed relationship semantics fail visibly', async (page) => {
      await openChart(page, { success: false }, (payload) => { payload.interactions[0].transformation = 'applied'; });
      assert.equal(await page.locator('#chart-view').isVisible(), false);
      assert.match(await page.locator('#form-error').innerText(), /Could not read chart relationships/);
    });
  });
}
