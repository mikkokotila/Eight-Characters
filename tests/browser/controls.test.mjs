// Real charts retain their actions and names when the classic controls become icons.
import {
  assert, describe, it, engineName, profiles, openChart, settled, withPage,
  HELSINKI, screenshot,
} from './chart-helpers.mjs';

const tipSelector = '#control-tooltip';
const tipOpen = (page) => page.waitForFunction(() => document.getElementById('control-tooltip').classList.contains('is-visible'));
const tipClosed = (page) => page.waitForFunction(() => !document.getElementById('control-tooltip').matches(':popover-open'));

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / classic icon controls`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 120000 }, () => withPage(profile, run));

    check('icon actions retain their names, language, state and original command labels', async (page) => {
      for (const lang of ['en', 'fi']) {
        await openChart(page, { lang });
        const labels = lang === 'en'
          ? ['Characters', 'Ten Gods', 'Hidden stems', 'Standard', 'Evolution', 'Copy link', 'Copy as text', 'Edit', 'New chart', 'Compare']
          : ['Merkit', 'Kymmenen jumalaa', 'Piilorungot', 'Standardi', 'Evoluutio', 'Kopioi linkki', 'Kopioi tekstinä', 'Muokkaa', 'Uusi kartta', 'Vertaa'];
        for (const label of labels) {
          const button = page.locator('#chart-view').getByRole('button', { name: label, exact: true });
          assert.equal(await button.locator(':scope > svg[aria-hidden="true"]').count(), 1, label);
          assert.equal(await button.textContent(), label, 'command palette text is preserved');
          assert.equal(await button.locator('.control-label.sr-only').count(), 1);
        }
        assert.deepEqual(await page.locator('#chart-language button').allTextContents(), ['FI', 'EN']);
        await page.locator('[data-display="ten-gods"]').click(); await settled(page);
        assert.equal(await page.locator('[data-display="ten-gods"]').getAttribute('aria-pressed'), 'true');
        assert.equal(await page.locator('#pillars .card.is-flipped').count(), 8);
        await page.locator('[data-display="hidden-stems"]').click(); await settled(page);
        assert.equal(await page.locator('#pillars .hidden-stems-panel.is-expanded').count(), 4);
        await page.locator('[data-display="characters"]').click(); await settled(page);
        await screenshot(page, `controls-${profile.name}-${lang}`);
      }
    });

    check('dynamic context and panel controls preserve evidence and receive the same icon vocabulary', async (page) => {
      const payload = await openChart(page);
      const roots = new Set(payload.day_master_context.roots.map(root => root.pillar)).size;
      const rootButton = page.locator('button[data-context="roots"]');
      assert.equal(await rootButton.getAttribute('data-control-count'), String(roots));
      if (roots) assert.equal(await rootButton.locator('.control-caption').getAttribute('data-caption'), String(roots));
      const relationships = page.locator('#relationships-topic');
      assert.equal(await relationships.locator('.control-caption').getAttribute('data-caption'), String(payload.interactions.length));
      await page.locator('[data-context="roles"]').click();
      assert.equal(await page.locator('.role-choice svg[data-control-icon="chevron-right"]').count(), 10);
      await page.locator('[data-role="direct_wealth"]').click();
      assert.equal(await page.locator('[data-role-back] svg[data-control-icon="arrow-left"]').count(), 1);
      assert.ok(await page.locator('[data-root-pillar] svg[data-control-icon="sprout"]').count() > 0);
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#chart-panel').isVisible(), false);
      await page.locator('#relationships-topic').click();
      assert.equal(await page.locator('.relationship-chip svg[data-control-icon="chevron-right"]').count(), payload.interactions.length);
      await page.locator('.relationship-chip').first().click();
      await page.keyboard.press('Escape'); await tipClosed(page);
      assert.equal(await page.locator('.relationship-chip.is-active, .relationship-arc.is-active').count(), 0);
      assert.equal(await page.locator('.relationship-chip').first().evaluate(node => node === document.activeElement), true);
      await page.locator('[data-close-panel]').click();
      assert.equal(await page.locator('#chart-panel').isVisible(), false);
    });

    check('luck phases and Zi conventions keep their period and calculation labels', async (page) => {
      await openChart(page, { place: HELSINKI, date: '1975-08-14', time: '23:50', gender: 'female' });
      assert.equal(await page.locator('#luck-switch svg[data-control-icon]').count(), 2);
      assert.equal(await page.locator('.luck-step svg[data-control-icon]').count(), 2);
      assert.equal(await page.locator('[data-luck-today] svg[data-control-icon="calendar-check"]').count(), 1);
      assert.equal(await page.locator('[data-zi-convention="split_midnight"] .control-caption').getAttribute('data-caption'), '00:00');
      assert.equal(await page.locator('[data-zi-convention="whole_zi_23"] .control-caption').getAttribute('data-caption'), '23:00');
      await page.locator('.luck-chip[data-luck="5"]').click();
      assert.equal(await page.locator('[data-luck-phase="stem"] svg[data-control-icon="panel-top"]').count(), 1);
      assert.equal(await page.locator('[data-luck-phase="branch"] svg[data-control-icon="panel-bottom"]').count(), 1);
      await page.locator('[data-luck-phase="branch"]').click();
      assert.equal(await page.locator('[data-luck-phase="branch"]').getAttribute('aria-pressed'), 'true');
      await screenshot(page, `controls-${profile.name}-luck`);
    });

    check('printing retains the full selected Zi convention as visible text', async (page) => {
      await openChart(page, { place: HELSINKI, date: '1988-06-15', time: '00:50' });
      const selected = page.locator('[data-zi-convention][aria-pressed="true"]');
      const label = await selected.textContent();
      await page.emulateMedia({ media: 'print' });
      assert.equal(await selected.innerText(), label);
      assert.equal(await selected.locator('.control-icon').isVisible(), false);
      assert.equal(await selected.locator('.control-caption').isVisible(), false);
    });

    check('keyboard descriptions preserve focus, close with Escape and translate after a rerender', async (page) => {
      await openChart(page);
      await page.keyboard.press('Tab');
      const copy = page.locator('#copy-link-btn'); await copy.focus(); await tipOpen(page);
      assert.equal(await page.locator(tipSelector + ' strong').textContent(), 'Copy link');
      assert.match(await page.locator(tipSelector).textContent(), /shareable address/);
      assert.equal(await copy.getAttribute('aria-describedby'), 'control-tooltip');
      assert.equal(await copy.evaluate(node => node === document.activeElement), true);
      await page.keyboard.press('Escape'); await tipClosed(page);
      assert.equal(await copy.getAttribute('aria-describedby'), null);
      await page.locator('[data-chart-lang="fi"]').click(); await settled(page);
      await page.keyboard.press('Tab'); await page.locator('#copy-text-btn').focus(); await tipOpen(page);
      assert.equal(await page.locator(tipSelector).textContent(), 'Kopioi teksti · Kopioi kartan tekstinä.');
      await page.locator('[data-context="roots"]').click();
      await page.keyboard.press('Tab'); await page.locator('[data-context="roots"]').focus(); await tipOpen(page);
      await page.keyboard.press('Escape'); await tipClosed(page);
      assert.equal(await page.locator('#chart-panel').isVisible(), false, 'Escape keeps the chart’s existing behavior');
    });

    check('gender help describes the focused radio and preserves its other descriptions', async (page) => {
      await openChart(page);
      await page.locator('#back-btn').click();
      const radio = page.locator('input[name="gender"][value="female"]');
      await radio.evaluate(node => node.setAttribute('aria-describedby', 'gender-hint'));
      await page.keyboard.press('Tab'); await radio.focus(); await tipOpen(page);
      assert.equal(await radio.getAttribute('aria-describedby'), 'gender-hint control-tooltip');
      assert.equal(await radio.locator('..').getAttribute('aria-describedby'), null);
      assert.match(await page.locator(tipSelector).textContent(), /^Female · Set the gender/);
      await page.keyboard.press('Escape'); await tipClosed(page);
      assert.equal(await radio.getAttribute('aria-describedby'), 'gender-hint');
    });

    check('controls and tooltip fit the narrow screen and respect reduced motion', async (page) => {
      await page.emulateMedia({ reducedMotion: 'reduce', colorScheme: 'dark' });
      await openChart(page); await page.setViewportSize({ width: 320, height: 844 });
      await page.keyboard.press('Tab'); await page.locator('#copy-text-btn').focus(); await tipOpen(page);
      const layout = await page.evaluate(() => {
        const tip = document.getElementById('control-tooltip'); const box = tip.getBoundingClientRect();
        const controls = [...document.querySelectorAll('#chart-view .icon-control')].filter(node => node.checkVisibility());
        return {
          overflow: document.documentElement.scrollWidth > innerWidth,
          inside: box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight,
          transition: getComputedStyle(tip).transitionDuration,
          targets: controls.map(node => { const r = node.getBoundingClientRect(); return [r.width, r.height]; }),
        };
      });
      assert.equal(layout.overflow, false); assert.equal(layout.inside, true); assert.equal(layout.transition, '0s');
      assert.ok(layout.targets.every(([width, height]) => width >= 44 && height >= 44), JSON.stringify(layout.targets));
      await screenshot(page, `controls-${profile.name}-dark-tooltip`);
    });

    check('tooltip text passes clicks through to a nearby control', async (page) => {
      await openChart(page); await page.setViewportSize({ width: 320, height: 844 });
      await page.keyboard.press('Tab'); await page.locator('#copy-text-btn').focus(); await tipOpen(page); await settled(page);
      const button = page.locator('[data-chart-lang="fi"]');
      const control = await button.boundingBox(); const tip = await page.locator(tipSelector).boundingBox();
      assert.ok(control && tip);
      const left = Math.max(control.x, tip.x); const right = Math.min(control.x + control.width, tip.x + tip.width);
      const top = Math.max(control.y, tip.y); const bottom = Math.min(control.y + control.height, tip.y + tip.height);
      assert.ok(right > left && bottom > top, 'the narrow layout exercises a tooltip over another control');
      const recalculated = page.waitForResponse(response => new URL(response.url()).pathname === '/api/four_pillars');
      await page.mouse.click((left + right) / 2, (top + bottom) / 2);
      await (await recalculated).finished();
      await page.waitForFunction(() => document.documentElement.lang === 'fi'
        && document.querySelector('#chart-view').getAttribute('aria-busy') !== 'true'
        && document.querySelector('[data-context="roots"]').getAttribute('aria-label').startsWith('Juuret'));
      await settled(page);
      await tipClosed(page);
      assert.equal(await button.getAttribute('aria-pressed'), 'true');
    });

    if (!profile.hasTouch) {
      check('hover waits half a second, cancelled hovers stay closed and the tooltip itself is hoverable', async (page) => {
        await openChart(page);
        const copy = page.locator('#copy-link-btn'); const tip = page.locator(tipSelector);
        await copy.hover(); await page.waitForTimeout(300);
        assert.equal(await tip.isVisible(), false, 'hover does not open prematurely');
        await page.mouse.move(0, 0); await page.waitForTimeout(600);
        assert.equal(await tip.isVisible(), false, 'leaving cancels the timer');
        await page.locator('[data-display="ten-gods"]').click(); await settled(page); await page.waitForTimeout(650);
        assert.equal(await tip.isVisible(), false, 'activation cancels pending hover help');
        await page.locator('[data-display="characters"]').click(); await settled(page);
        await copy.hover(); await tipOpen(page);
        assert.equal(await tip.locator('strong').textContent(), 'Copy link');
        const box = await tip.boundingBox(); assert.ok(box);
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2); await page.waitForTimeout(300);
        assert.equal(await tip.isVisible(), true, 'supplementary content remains available while hovered');
        await copy.hover(); await page.waitForTimeout(300);
        assert.equal(await tip.isVisible(), true, 'returning to the trigger cancels the pending exit');
        await page.mouse.move(0, 0); await tipClosed(page);
      });

      check('branch help leaves the existing turn instructions visible', async (page) => {
        await openChart(page);
        await page.locator('.card.branch[data-pillar="hour"]').hover(); await tipOpen(page); await settled(page);
        const tip = await page.locator(tipSelector).boundingBox();
        const hint = await page.locator('.card-hint').boundingBox();
        assert.ok(tip && hint);
        assert.ok(tip.y + tip.height <= hint.y || hint.y + hint.height <= tip.y, 'the two hints do not overlap');
        assert.match(await page.locator('.card-hint').textContent(), /Press and hold/);
      });
    } else {
      check('a touch hold reveals the action without running it, while a quick tap still selects', async (page) => {
        await openChart(page);
        const gods = page.locator('[data-display="ten-gods"]');
        const point = { pointerType: 'touch', pointerId: 41, isPrimary: true, clientX: 100, clientY: 100, bubbles: true };
        await gods.dispatchEvent('pointerdown', point); await tipOpen(page);
        await gods.dispatchEvent('pointerup', point); await gods.dispatchEvent('click');
        assert.equal(await gods.getAttribute('aria-pressed'), 'false', 'help does not activate the action');
        assert.equal(await page.locator(tipSelector + ' strong').textContent(), 'Ten Gods');
        await page.waitForTimeout(650); await gods.tap(); await settled(page);
        assert.equal(await gods.getAttribute('aria-pressed'), 'true');
        const characters = page.locator('[data-display="characters"]');
        await characters.dispatchEvent('pointerdown', point);
        await characters.dispatchEvent('pointercancel', point); await page.waitForTimeout(650);
        assert.equal(await page.locator(tipSelector).isVisible(), false, 'cancelled touch holds stay closed');
        assert.equal(await gods.getAttribute('aria-pressed'), 'true');
      });
    }
  });
}
