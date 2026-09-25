// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Page foundations of the Standard view: typography, contrast, form, location list, identity.
import { assert, describe, it, engineName, profiles, openChart, settled, withPage } from './chart-helpers.mjs';

const BRAND_FAMILIES = ['Manrope', 'Cormorant Garamond'];

// In-page helpers, installed before the page's own scripts run.
const AUDIT = () => {
  // Elements that directly hold text a reader can see.
  const textElements = () => {
    const elements = new Set();
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const element = walker.currentNode.parentElement;
      if (!walker.currentNode.textContent.trim() || elements.has(element)) continue;
      if (element.closest('.sr-only, script, style, title')) continue;
      if (!element.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) continue;
      const box = element.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) continue;
      // Collapsed hidden-stem panels clip their rows to nothing.
      if (element.closest('.hidden-stems-panel:not(.is-expanded)')) continue;
      elements.add(element);
    }
    return [...elements];
  };
  const describe = (element) => `${element.tagName.toLowerCase()}${element.id ? `#${element.id}` : ''}`
    + `${element.classList.length ? `.${[...element.classList].join('.')}` : ''} "${element.textContent.trim().slice(0, 40)}"`;
  const firstFamily = (element) => getComputedStyle(element).fontFamily.split(',')[0].trim().replace(/^["']|["']$/g, '');
  window.__ecAudit = { textElements, describe, firstFamily };
};

async function installAudit(page) {
  await page.addInitScript(AUDIT);
}

// Glyphs drawn from a font the page did not load, per visible text element (DevTools protocol).
// CJK characters are exempt: the page fonts have none, and chart characters are stage 2 of #16's plan.
async function systemGlyphFailures(page, cdp, state) {
  const texts = await page.evaluate(() => window.__ecAudit.textElements().map((element, index) => {
    element.setAttribute('data-glyph-audit', String(index));
    const own = [...element.childNodes].filter((node) => node.nodeType === Node.TEXT_NODE)
      .map((node) => node.textContent).join('');
    return { label: window.__ecAudit.describe(element), cjk: [...own].filter((char) => /\p{Script=Han}/u.test(char)).length };
  }));
  const { root } = await cdp.send('DOM.getDocument', { depth: -1 });
  const { nodeIds } = await cdp.send('DOM.querySelectorAll', { nodeId: root.nodeId, selector: '[data-glyph-audit]' });
  assert.equal(nodeIds.length, texts.length);
  const failures = [];
  for (const nodeId of nodeIds) {
    const { attributes } = await cdp.send('DOM.getAttributes', { nodeId });
    const text = texts[Number(attributes[attributes.indexOf('data-glyph-audit') + 1])];
    const { fonts } = await cdp.send('CSS.getPlatformFontsForNode', { nodeId });
    const system = fonts.filter((font) => !font.isCustomFont);
    if (system.reduce((sum, font) => sum + font.glyphCount, 0) > text.cjk) {
      failures.push(`${state}: ${text.label} → ${system.map((font) => `${font.familyName} ×${font.glyphCount}`).join(', ')}`);
    }
  }
  await page.evaluate(() => document.querySelectorAll('[data-glyph-audit]')
    .forEach((element) => element.removeAttribute('data-glyph-audit')));
  return failures;
}

async function fontFamilyFailures(page, families) {
  return page.evaluate((families) => window.__ecAudit.textElements()
    .filter((element) => !families.includes(window.__ecAudit.firstFamily(element)))
    .map((element) => `${window.__ecAudit.describe(element)} → ${getComputedStyle(element).fontFamily}`), families);
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / page foundations`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 60000 }, () => withPage(profile, run));

    check('every visible text is set in the page fonts, in both languages', async (page) => {
      await installAudit(page);
      for (const lang of ['en', 'fi']) {
        await openChart(page, { lang });
        await page.locator('#back-btn').click();
        await page.locator('#location').fill('Chengdu');
        await page.locator('.location-suggestion').first().waitFor();
        assert.deepEqual(await fontFamilyFailures(page, BRAND_FAMILIES), [], `${lang} landing with suggestions`);
        await page.locator('.location-suggestion').first().click();
        await page.locator('#create-chart-btn').click();
        await page.locator('#chart-view').waitFor({ state: 'visible' });
        await page.locator('button[data-context="roles"]').click();
        assert.deepEqual(await fontFamilyFailures(page, BRAND_FAMILIES), [], `${lang} chart with roles`);
      }
    });

    it('every glyph is drawn from the page fonts, except CJK characters', {
      timeout: 120000,
      skip: engineName !== 'chromium' && 'Platform-font inspection needs the Chromium DevTools protocol.',
    }, () => withPage(profile, async (page) => {
      await installAudit(page);
      const cdp = await page.context().newCDPSession(page);
      await cdp.send('DOM.enable');
      await cdp.send('CSS.enable');
      const failures = [];
      for (const lang of ['en', 'fi']) {
        await openChart(page, { lang });
        await page.locator('#back-btn').click();
        await page.locator('#location').fill('Chengdu');
        await page.locator('.location-suggestion').first().waitFor();
        failures.push(...await systemGlyphFailures(page, cdp, `${lang} landing`));
        await page.locator('.location-suggestion').first().click();
        await page.locator('#create-chart-btn').click();
        await page.locator('#chart-view').waitFor({ state: 'visible' });
        for (const pillar of ['hour', 'day', 'month', 'year']) await page.locator(`.card.branch[data-pillar="${pillar}"]`).click();
        await page.locator('#ten-gods-toggle').click();
        await settled(page);
        failures.push(...await systemGlyphFailures(page, cdp, `${lang} chart`));
        for (const topic of ['season', 'roots', 'roles']) {
          await page.locator(`button[data-context="${topic}"]`).click();
          failures.push(...await systemGlyphFailures(page, cdp, `${lang} ${topic}`));
        }
        await page.locator('button.role-choice[data-role="friend"]').click();
        failures.push(...await systemGlyphFailures(page, cdp, `${lang} role`));
        await page.locator('button[data-role-back]').click();
        await page.locator('.role-stem-entry button[data-root-pillar="year"]').click();
        failures.push(...await systemGlyphFailures(page, cdp, `${lang} stem roots`));
        await page.keyboard.press('Escape');
        await page.locator('.relationship-chip').first().click();
        failures.push(...await systemGlyphFailures(page, cdp, `${lang} relationship`));
        await page.keyboard.press('Escape');
      }
      assert.deepEqual(failures, []);
    }));

    check('the page requests nothing from other origins and loads one face per font', async (page) => {
      const origin = new URL(process.env.EC_BASE_URL).origin;
      const foreign = [];
      page.on('request', (request) => {
        const url = new URL(request.url());
        if (url.protocol !== 'data:' && url.origin !== origin) foreign.push(request.url());
      });
      await openChart(page, { lang: 'en' });
      const loaded = await page.evaluate(async () => {
        await document.fonts.ready;
        return [...document.fonts].filter((face) => face.status === 'loaded')
          .map((face) => face.family.replace(/["']/g, '')).sort();
      });
      assert.deepEqual(foreign, []);
      assert.deepEqual(loaded, ['Cormorant Garamond', 'Manrope']);
    });
  });
}
