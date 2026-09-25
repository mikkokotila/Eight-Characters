// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Page foundations of the Standard view: typography, contrast, form, location list, identity.
import { assert, describe, it, engineName, profiles, openChart, withPage } from './chart-helpers.mjs';

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
