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

  // WCAG 2.2 contrast, with backgrounds and opacity composited through every ancestor.
  const parse = (value) => {
    const match = value.match(/^rgba?\(([^)]+)\)$/);
    if (!match) throw new Error(`Unexpected colour value: ${value}`);
    const [r, g, b, a = 1] = match[1].split(/[\s,/]+/).filter(Boolean).map(Number);
    return [r, g, b, a];
  };
  const over = ([r, g, b, a], below) => [r, g, b].map((channel, i) => channel * a + below[i] * (1 - a));
  const opacity = (element) => {
    let product = 1;
    for (let node = element; node; node = node.parentElement) product *= Number(getComputedStyle(node).opacity);
    return product;
  };
  const backdrop = (element) => {
    const chain = [];
    for (let node = element; node; node = node.parentElement) chain.unshift(node);
    return chain.reduce((below, node) => {
      const [r, g, b, a] = parse(getComputedStyle(node).backgroundColor);
      return a > 0 ? over([r, g, b, a * opacity(node)], below) : below;
    }, [255, 255, 255]);
  };
  const luminance = (rgb) => {
    const [r, g, b] = rgb.map((c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const ratio = (a, b) => {
    const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (light + 0.05) / (dark + 0.05);
  };
  const inkOn = (element, colour, surface) => {
    const [r, g, b, a] = parse(colour);
    return ratio(over([r, g, b, a * opacity(element)], surface), surface);
  };
  const contrastFailures = () => textElements().flatMap((element) => {
    // Disabled controls are exempt (WCAG 1.4.3).
    if (element.closest('button:disabled')) return [];
    const style = getComputedStyle(element);
    const size = parseFloat(style.fontSize);
    const needed = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700) ? 3 : 4.5;
    const got = inkOn(element, style.color, backdrop(element));
    return got < needed ? [`${describe(element)} ${got.toFixed(2)}:1, needs ${needed}:1`] : [];
  });
  // The branch expand chevron is the only cue that a branch card opens (WCAG 1.4.11: 3:1).
  const chevronFailures = () => [...document.querySelectorAll('.branch-expand-hint')]
    .filter((hint) => hint.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }))
    .flatMap((hint) => {
      const got = inkOn(hint, getComputedStyle(hint).color, backdrop(hint.parentElement));
      const card = hint.closest('.card');
      return got < 3 ? [`chevron on ${card.dataset.pillar} ${[...card.classList].join('.')} ${got.toFixed(2)}:1`] : [];
    });
  // Hidden-stem dots encode the element: its own colour, and a ring of 3:1 on the surface.
  const dotFailures = () => {
    const root = getComputedStyle(document.documentElement);
    const hex = (value) => {
      const digits = value.trim().replace('#', '');
      return [0, 2, 4].map((i) => parseInt(digits.slice(i, i + 2), 16));
    };
    return [...document.querySelectorAll('.hidden-stem-dot')]
      .filter((dot) => dot.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })
        && !dot.closest('.hidden-stems-panel:not(.is-expanded)'))
      .flatMap((dot) => {
        const element = ['metal', 'fire', 'wood', 'earth', 'water'].find((name) => dot.classList.contains(name));
        const style = getComputedStyle(dot);
        const fill = parse(style.backgroundColor).slice(0, 3);
        const expected = hex(root.getPropertyValue(`--${element}-bg`));
        const ring = style.boxShadow.match(/rgba?\([^)]+\)/);
        const where = `${element} dot in ${describe(dot.parentElement)}`;
        if (fill.join() !== expected.join()) return [`${where}: fill ${fill} is not the ${element} colour ${expected}`];
        if (!ring) return [`${where}: no ring`];
        const got = inkOn(dot, ring[0], backdrop(dot.parentElement));
        return got < 3 ? [`${where}: ring ${got.toFixed(2)}:1`] : [];
      });
  };
  window.__ecAudit = { textElements, describe, firstFamily, contrastFailures, chevronFailures, dotFailures, parse, backdrop, inkOn };
};

// Every chart state and detail page, in both languages; `inspect` runs in each.
async function visitStates(page, inspect) {
  for (const lang of ['en', 'fi']) {
    await openChart(page, { lang });
    await page.locator('#back-btn').click();
    await page.locator('#location').fill('Chengdu');
    await page.locator('.location-suggestion').first().waitFor();
    await inspect(`${lang} landing with suggestions`);
    await page.locator('.location-suggestion').first().click();
    await inspect(`${lang} landing with a picked place`);
    await page.locator('#date').fill('1947-10-04');
    await page.locator('#create-chart-btn').click();
    await page.locator('#date-status.is-error').waitFor();
    await inspect(`${lang} landing with a date error`);
    await page.locator('#date').fill('1988-02-04');
    await page.locator('#create-chart-btn').click();
    await page.locator('#chart-view').waitFor({ state: 'visible' });
    await settled(page);
    await inspect(`${lang} chart`);
    const pillars = ['hour', 'day', 'month', 'year'];
    for (const pillar of pillars) await page.locator(`.card.branch[data-pillar="${pillar}"]`).click();
    await settled(page);
    await inspect(`${lang} chart with hidden stems`);
    await page.locator('#ten-gods-toggle').click();
    await settled(page);
    await inspect(`${lang} Ten Gods with hidden stems`);
    for (const pillar of pillars) await page.locator(`.card.branch[data-pillar="${pillar}"]`).click();
    await page.locator('#ten-gods-toggle').click();
    await settled(page);
    for (const topic of ['season', 'roots', 'roles']) {
      await page.locator(`button[data-context="${topic}"]`).click();
      await inspect(`${lang} ${topic}`);
    }
    await page.locator('button.role-choice[data-role="friend"]').click();
    await inspect(`${lang} role`);
    await page.locator('button[data-role-back]').click();
    await page.locator('.role-stem-entry button[data-root-pillar="year"]').click();
    await inspect(`${lang} stem roots`);
    await page.keyboard.press('Escape');
    await page.locator('.relationship-chip').first().click();
    await inspect(`${lang} relationship`);
    await page.keyboard.press('Escape');
  }
}

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

    check('text meets WCAG AA contrast, and the chevron and element dots 3:1, in every state', async (page) => {
      await installAudit(page);
      const failures = [];
      await visitStates(page, async (state) => {
        // Measure settled colours, not a fade or a flip in progress.
        await settled(page);
        const found = await page.evaluate(() => [...window.__ecAudit.contrastFailures(),
          ...window.__ecAudit.chevronFailures(), ...window.__ecAudit.dotFailures()]);
        failures.push(...found.map((failure) => `${state}: ${failure}`));
      });
      assert.deepEqual([...new Set(failures)], []);
    });

    check('the birth-data fields share one height and one text alignment', async (page) => {
      await openChart(page, { lang: 'en' });
      await page.locator('#back-btn').click();
      const fields = await page.locator('#date, #time, #location').evaluateAll((inputs) => inputs.map((input) => ({
        height: input.getBoundingClientRect().height, align: getComputedStyle(input).textAlign,
      })));
      assert.equal(new Set(fields.map((field) => field.height)).size, 1, JSON.stringify(fields));
      assert.equal(new Set(fields.map((field) => field.align)).size, 1, JSON.stringify(fields));
    });

    check('dates outside the engine range are refused on the date field, before any request', async (page) => {
      const sent = [];
      page.on('request', (request) => {
        if (request.url().endsWith('/api/four_pillars')) sent.push(request.postDataJSON().date);
      });
      const messages = { en: 'Charts can be calculated for 1949–2100.', fi: 'Karttoja voi laskea vuosille 1949–2100.' };
      for (const [lang, message] of Object.entries(messages)) {
        await openChart(page, { lang });
        await page.locator('#back-btn').click();
        for (const date of ['1948-12-31', '2101-01-01']) {
          await page.locator('#date').fill(date);
          await page.locator('#create-chart-btn').click();
          assert.equal(await page.locator('#date-status.is-error').textContent(), message);
          assert.equal(await page.locator('#date').getAttribute('aria-invalid'), 'true');
          assert.equal(await page.evaluate(() => document.activeElement.id), 'date');
          assert.equal(await page.locator('#input-view').isVisible(), true);
        }
        // Editing clears the message; the range's first day is accepted.
        await page.locator('#date').fill('1949-01-01');
        assert.equal(await page.locator('#date-status').textContent(), '');
        assert.equal(await page.locator('#date').getAttribute('aria-invalid'), null);
        await page.locator('#create-chart-btn').click();
        await page.locator('#chart-view').waitFor({ state: 'visible' });
      }
      assert.deepEqual(sent, ['1988-02-04', '1949-01-01', '1988-02-04', '1949-01-01']);
    });

    check('a missing date or time is named on its own field', async (page) => {
      await openChart(page, { lang: 'en' });
      await page.locator('#back-btn').click();
      await page.locator('#date').fill('');
      await page.locator('#time').fill('');
      await page.locator('#create-chart-btn').click();
      assert.equal(await page.locator('#date-status.is-error').textContent(), 'Enter the birth date.');
      assert.equal(await page.locator('#time-status.is-error').textContent(), 'Enter the time of birth.');
      assert.equal(await page.evaluate(() => document.activeElement.id), 'date');
      assert.equal(await page.locator('#input-view').isVisible(), true);
    });

    check('a chart that cannot be created is reported above the button, not under the place', async (page) => {
      await openChart(page, { lang: 'en' });
      await page.locator('#back-btn').click();
      const placeStatus = await page.locator('#location-status').textContent();
      await page.route('**/api/four_pillars', (route) => route.fulfill({ status: 500, json: { detail: 'Stopped by the test.' } }));
      await page.locator('#create-chart-btn').click();
      const error = page.locator('#form-error');
      await error.waitFor({ state: 'visible' });
      assert.equal(await error.textContent(), 'Stopped by the test.');
      assert.equal(await error.getAttribute('role'), 'alert');
      assert.equal(await page.locator('#location-status').textContent(), placeStatus);
      assert.equal(await page.locator('#chart-view').isVisible(), false);
      assert.equal(await page.locator('#create-chart-btn').isEnabled(), true);
      assert.equal(await page.locator('#create-chart-btn').textContent(), 'Create chart');
      await page.locator('#time').fill('16:31');
      assert.equal(await error.isVisible(), false);
    });

    check('creating a chart shows progress and takes no second submit', async (page) => {
      await openChart(page, { lang: 'fi' });
      await page.locator('#back-btn').click();
      let release;
      const held = new Promise((resolve) => { release = resolve; });
      let requests = 0;
      // Held until inspected, then handed to the real API.
      await page.route('**/api/four_pillars', async (route) => { requests += 1; await held; await route.fallback(); });
      const button = page.locator('#create-chart-btn');
      await button.click();
      await page.waitForFunction(() => document.getElementById('create-chart-btn').classList.contains('is-pending'));
      assert.equal(await button.isDisabled(), true);
      assert.equal(await button.textContent(), 'Luodaan karttaa…');
      assert.equal(await page.locator('#chart-form').getAttribute('aria-busy'), 'true');
      await page.locator('#time').press('Enter');
      await page.evaluate(() => document.getElementById('chart-form').requestSubmit());
      release();
      await page.locator('#chart-view').waitFor({ state: 'visible' });
      assert.equal(requests, 1);
      await page.locator('#back-btn').click();
      assert.equal(await button.isEnabled(), true);
      assert.equal(await button.textContent(), 'Luo kartta');
      assert.equal(await page.locator('#chart-form').getAttribute('aria-busy'), null);
    });

    check('each view has one top-level heading: the title it shows', async (page) => {
      const headings = () => page.evaluate(() => [...document.querySelectorAll('h1, h2')]
        .filter((heading) => heading.checkVisibility())
        .map((heading) => `${heading.tagName} ${heading.textContent.trim()}`));
      await page.goto(process.env.EC_BASE_URL);
      await page.locator('[data-lang="en"]').click();
      assert.deepEqual(await headings(), ['H1 Eight characters']);
      await openChart(page, { lang: 'en' });
      assert.deepEqual(await headings(), [
        'H1 February 4, 1988 · 16:30 · Chengdu', 'H2 Day Master · Ji — Yin Earth', 'H2 Relationships']);
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
