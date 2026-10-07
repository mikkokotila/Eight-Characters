// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Covers the explorer's parameter pane: what it shows, what a recompute sends and
// applies, and that the graph keeps its measure as the pane opens and closes.
import assert from 'node:assert/strict';
import { before, after, describe, it } from 'node:test';

const moduleName = process.env.EC_PLAYWRIGHT_MODULE;
const baseURL = process.env.EC_BASE_URL;
const engineName = process.env.EC_BROWSER;
assert.ok(moduleName, 'Set EC_PLAYWRIGHT_MODULE to playwright or its index.mjs path.');
assert.ok(baseURL, 'Set EC_BASE_URL to the app under test.');
assert.ok(['chromium', 'webkit'].includes(engineName), 'Set EC_BROWSER to chromium or webkit.');
const playwright = await import(moduleName);
let browser;
before(async () => { browser = await playwright[engineName].launch({ headless: true }); });
after(async () => { if (browser) await browser.close(); });

const profiles = [
  { name: 'desktop', viewport: { width: 1440, height: 1000 }, hasTouch: false, isMobile: false },
  { name: 'mobile', viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true },
];

const BIRTH = {
  date: '1988-02-04',
  time: '16:30',
  location: { timezone: 'Asia/Shanghai', latitude: 30.658, longitude: 104.066 },
};
const EXPLORER = '/explorer/?date=1988-02-04&time=16:30&latitude=30.658&longitude=104.066&timezone=Asia%2FShanghai';
const catalogue = await (await fetch(new URL('/api/evolution_controls', baseURL))).json();
const controlsIn = (section) => catalogue[section];
const controlOf = (id) =>
  [...catalogue.run, ...catalogue.conventions, ...catalogue.model].find((control) => control.id === id);

// Every request the page makes to the API, as method, path and JSON body.
function recordRequests(page) {
  const requests = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/api/')) return;
    requests.push({ method: request.method(), path: url.pathname, body: request.postDataJSON() });
  });
  return requests;
}

async function openExplorer(page, link = EXPLORER) {
  await page.goto(new URL(link, baseURL).href);
  await page.waitForFunction(() => /nodes visible/.test(document.getElementById('statusBar').textContent));
}

const statusOf = (page) => page.locator('#parameterStatus').textContent();

async function openPane(page) {
  await page.locator('#parameterToggle').click();
  await page.waitForFunction(() => /^Computed with/.test(document.getElementById('parameterStatus').textContent));
}

async function openGroups(page, ...names) {
  await page.evaluate((names) => {
    document.querySelectorAll('.parameter-group').forEach((group) => {
      group.open = names.includes(group.querySelector('summary').textContent);
    });
  }, names);
}

const inputFor = (page, section, id) => page.locator(`#param-${section}-${id}`);

async function slide(page, section, id, value) {
  await page.evaluate(({ key, value }) => {
    const range = document.querySelector(`.param[data-key="${key}"] input[type="range"]`);
    range.value = String(value);
    range.dispatchEvent(new Event('input', { bubbles: true }));
    return range.value;
  }, { key: `${section}.${id}`, value });
}

async function recompute(page) {
  const sent = page.waitForRequest((request) =>
    request.url().endsWith('/api/evolution_explorer') && request.method() === 'POST');
  await page.locator('#parameterRecompute').click();
  const body = (await sent).postDataJSON();
  await page.waitForFunction(() => /^(Recomputed|Recompute failed)/.test(document.getElementById('parameterStatus').textContent));
  return body;
}

const graphMeasure = (page) => page.evaluate(() => {
  const canvas = document.querySelector('.canvas-wrap').getBoundingClientRect();
  const viewBox = document.getElementById('graph').getAttribute('viewBox').split(' ').map(Number);
  return {
    canvas: [Math.round(canvas.width), Math.round(canvas.height)],
    viewBox: [Math.round(viewBox[2]), Math.round(viewBox[3])],
  };
});

async function graphFitsItsCanvas(page) {
  await page.waitForFunction(() => {
    const canvas = document.querySelector('.canvas-wrap').getBoundingClientRect();
    const viewBox = document.getElementById('graph').getAttribute('viewBox').split(' ').map(Number);
    return Math.round(canvas.width) === Math.round(viewBox[2])
      && Math.round(canvas.height) === Math.round(viewBox[3]);
  });
  const { canvas, viewBox } = await graphMeasure(page);
  assert.deepEqual(viewBox, canvas);
  return canvas;
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / explorer parameters`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 60000 }, async () => {
      const { name: _name, ...options } = profile;
      const page = await browser.newPage(options);
      const errors = [];
      page.on('pageerror', (error) => errors.push(error.message));
      try {
        await run(page);
        assert.deepEqual(errors, [], 'Uncaught browser errors');
      } finally {
        await page.close();
      }
    });

    check('the chart loads as before, and the pane asks for its controls only when opened', async (page) => {
      const requests = recordRequests(page);
      await openExplorer(page);
      assert.deepEqual(requests, [{ method: 'POST', path: '/api/evolution_explorer', body: BIRTH }]);
      assert.equal(await page.locator('#parameterPane').isHidden(), true);
      assert.equal(await page.locator('#parameterToggle').getAttribute('aria-expanded'), 'false');

      await openPane(page);
      assert.equal(await page.locator('#parameterToggle').getAttribute('aria-expanded'), 'true');
      assert.deepEqual(requests.slice(1).map(({ method, path }) => [method, path]), [['GET', '/api/evolution_controls']]);
      assert.equal(await statusOf(page), 'Computed with the defaults.');
      assert.equal(await page.locator('#parameterRecompute').isDisabled(), true);
    });

    check('every control shows the value the graph was computed with, in its range and step', async (page) => {
      await openExplorer(page);
      await openPane(page);
      const shown = await page.evaluate(() => [...document.querySelectorAll('.param[data-key]')].map((param) => ({
        key: param.dataset.key,
        number: param.querySelector('input[type="number"]:not([data-index])')?.value ?? null,
        range: param.querySelector('input[type="range"]')
          ? ['min', 'max', 'step', 'value'].map((name) => param.querySelector('input[type="range"]')[name])
          : null,
        entries: [...param.querySelectorAll('input[data-index]')].map((input) => input.value),
        checked: param.querySelector('input[type="radio"]:checked')?.value ?? null,
      })));
      const expected = ['run', 'conventions', 'model'].flatMap((section) =>
        controlsIn(section).map((control) => ({ section, control })));
      assert.equal(shown.length, expected.length);
      const byKey = new Map(shown.map((field) => [field.key, field]));
      expected.forEach(({ section, control }) => {
        const field = byKey.get(`${section}.${control.id}`);
        assert.ok(field, `${section}.${control.id} is shown`);
        if (control.kind === 'choice') {
          assert.equal(field.checked, control.default);
        } else if (control.kind === 'vector' || control.kind === 'matrix') {
          assert.deepEqual(field.entries.map(Number), [control.default].flat(2));
        } else {
          assert.equal(Number(field.number), control.default, control.id);
          if (control.id !== 'seed') {
            assert.deepEqual(field.range.slice(0, 3).map(Number), [control.min, control.max, control.step], control.id);
            assert.equal(Number(field.range[3]), control.default, control.id);
          }
        }
      });
    });

    check('a recompute applies the changes and keeps what was applied before', async (page) => {
      await openExplorer(page);
      await openPane(page);
      await openGroups(page, 'Run', 'Structure Mode');
      await inputFor(page, 'model', 'LAMBDA_MODE').fill('6.5');
      assert.equal(await statusOf(page), 'Computed with the defaults. 1 change to apply.');
      const first = await recompute(page);
      assert.deepEqual(first, { ...BIRTH, basin_index: 0, model: { LAMBDA_MODE: 6.5 } });
      assert.equal(await statusOf(page), 'Recomputed. Computed with 1 value changed from its default.');
      assert.equal(await page.locator('.param[data-key="model.LAMBDA_MODE"]').getAttribute('class'), 'param is-changed');

      await inputFor(page, 'run', 'particles').fill('8');
      const second = await recompute(page);
      assert.deepEqual(second, { ...BIRTH, basin_index: 0, run: { particles: 8 }, model: { LAMBDA_MODE: 6.5 } });
      assert.equal(await statusOf(page), 'Recomputed. Computed with 2 values changed from their defaults.');
      assert.equal(await inputFor(page, 'model', 'LAMBDA_MODE').inputValue(), '6.5');
      assert.match(await page.locator('#statusBar').textContent(), /nodes visible/);
    });

    check('sliders take fractional values, and every slider moves', async (page) => {
      await openExplorer(page);
      await openPane(page);
      await openGroups(page, 'Structure Mode', 'Polarity');
      // A step taken from the default's type made 6.5 unreachable and pinned this
      // slider, whose default is the whole number 1.0, to its minimum.
      await slide(page, 'model', 'LAMBDA_MODE', 6.5);
      assert.equal(await inputFor(page, 'model', 'LAMBDA_MODE').inputValue(), '6.5');
      await slide(page, 'model', 'DIFF_POLARITY_MULTIPLIER', 1.23);
      assert.equal(await inputFor(page, 'model', 'DIFF_POLARITY_MULTIPLIER').inputValue(), '1.23');
      assert.equal(await statusOf(page), 'Computed with the defaults. 2 changes to apply.');
    });

    check('a new seed each run sends a fresh seed and shows it', async (page) => {
      await openExplorer(page);
      await openPane(page);
      await inputFor(page, 'run', 'particles').fill('8');
      await page.locator('[data-seed-each-run]').check();
      assert.equal(await inputFor(page, 'run', 'seed').isDisabled(), true);
      const seeds = [];
      for (let index = 0; index < 2; index += 1) {
        const body = await recompute(page);
        assert.equal(body.run.particles, 8);
        assert.ok(Number.isInteger(body.run.seed) && body.run.seed >= 0 && body.run.seed < 2 ** 31);
        assert.equal(await inputFor(page, 'run', 'seed').inputValue(), String(body.run.seed));
        seeds.push(body.run.seed);
      }
      assert.notEqual(seeds[0], seeds[1]);
      assert.match(await statusOf(page), /Each recompute draws a new seed\.$/);
    });

    check('edits made while a recompute runs are kept, and only one runs at a time', async (page) => {
      await openExplorer(page);
      await openPane(page);
      await openGroups(page, 'Run', 'Energy Weights');
      await page.route('**/api/evolution_explorer', async (route) => {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        await route.continue();
      });
      await inputFor(page, 'run', 'particles').fill('8');
      await page.locator('#parameterRecompute').click();
      await page.waitForFunction(() => document.getElementById('parameterStatus').textContent === 'Recomputing…');
      assert.equal(await page.locator('#parameterRecompute').isDisabled(), true);
      assert.equal(await page.locator('#parameterPane').getAttribute('aria-busy'), 'true');
      await inputFor(page, 'model', 'LAMBDA_INTER').fill('2');
      await page.waitForFunction(() => /^Recomputed/.test(document.getElementById('parameterStatus').textContent));
      assert.equal(await statusOf(page), 'Recomputed. Computed with 1 value changed from its default. 1 change to apply.');
      assert.equal(await inputFor(page, 'model', 'LAMBDA_INTER').inputValue(), '2');
      assert.equal(await inputFor(page, 'run', 'particles').inputValue(), '8');
    });

    check('a reset during a recompute drops the answer that was on its way', async (page) => {
      await openExplorer(page);
      await openPane(page);
      let delivered;
      const answer = new Promise((resolve) => { delivered = resolve; });
      await page.route('**/api/evolution_explorer', async (route) => {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        // The page aborted this request; its answer, had it come, was to be ignored.
        await route.continue().catch((error) => {
          if (!/aborted|closed|disposed|handled/i.test(error.message)) throw error;
        });
        delivered();
      });
      await inputFor(page, 'run', 'particles').fill('8');
      await page.locator('#parameterRecompute').click();
      await page.waitForFunction(() => document.getElementById('parameterStatus').textContent === 'Recomputing…');
      await page.locator('#parameterReset').click();
      await answer;
      await page.evaluate(() => new Promise((resolve) => setTimeout(resolve, 200)));
      assert.equal(await statusOf(page), 'Computed with the defaults.');
      assert.equal(await inputFor(page, 'run', 'particles').inputValue(), '24');
      assert.equal(await page.evaluate(() => window.EC_EXPLORER.activeBasinIndex()), 0);
    });

    check('a refused recompute says why and leaves the chart and the edits', async (page) => {
      await openExplorer(page);
      await openPane(page);
      await openGroups(page, 'Run', 'Clustering');
      const statusBar = await page.locator('#statusBar').textContent();
      await inputFor(page, 'run', 'particles').fill('8');
      await inputFor(page, 'run', 'dbscan_min_samples').fill('9');
      await recompute(page);
      assert.equal(
        await statusOf(page),
        'Recompute failed: run.dbscan_min_samples (9) must not exceed run.particles (8). '
          + 'The chart is unchanged. Computed with the defaults. 2 changes to apply.',
      );
      assert.equal(await page.locator('#parameterStatus').getAttribute('class'), 'parameter-status is-error');
      assert.equal(await page.locator('#statusBar').textContent(), statusBar);
      assert.equal(await page.locator('#parameterRecompute').isDisabled(), false);
    });

    check('an emptied entry is no zero: it is marked and nothing is sent', async (page) => {
      await openExplorer(page);
      await openPane(page);
      await openGroups(page, 'Tables');
      const cell = page.locator('.param-matrix input[data-key="model.WUXING_MATRIX"][data-index="0,1"]');
      assert.equal(await cell.getAttribute('aria-label'), 'Wood to Fire');
      await cell.fill('');
      assert.equal(await cell.getAttribute('aria-invalid'), 'true');
      assert.equal(
        await statusOf(page),
        'Computed with the defaults. Fix Element Interaction Matrix, Wood to Fire before recomputing: it needs a number.',
      );
      assert.equal(await page.locator('#parameterRecompute').isDisabled(), true);
      await cell.fill('0.9');
      assert.equal(await cell.getAttribute('aria-invalid'), 'false');
      assert.equal(await statusOf(page), 'Computed with the defaults. 1 change to apply.');
    });

    check('the tables name their rows and columns, and every bar rescales to the largest entry', async (page) => {
      await openExplorer(page);
      await openPane(page);
      await openGroups(page, 'Tables');
      const headers = await page.locator('.param[data-key="model.DOMAIN_RESONANCE_MATRIX"] th').allTextContents();
      assert.deepEqual(headers, ['Self', 'Output', 'Wealth', 'Authority', 'Resource', 'Year', 'Month', 'Day', 'Hour']);
      const widths = () => page.locator('[data-bar^="model.STAGE_AMPLITUDE_BY_STAGE"]')
        .evaluateAll((bars) => bars.map((bar) => Number.parseFloat(bar.style.width)));
      assert.deepEqual((await widths()).slice(0, 5), [80, 60, 70, 90, 100]);
      await page.locator('#param-STAGE_AMPLITUDE_BY_STAGE-4').fill('1.5');
      const rescaled = await widths();
      assert.deepEqual(rescaled.slice(0, 5).map((width) => Math.round(width * 100) / 100), [53.33, 40, 46.67, 60, 100]);
    });

    check('the clustering weights stay shares of one', async (page) => {
      await openExplorer(page);
      await openPane(page);
      await openGroups(page, 'Run', 'Clustering');
      await inputFor(page, 'model', 'CLUSTER_ALPHA').fill('0.7');
      const weights = await Promise.all(['ALPHA', 'BETA', 'GAMMA']
        .map((name) => inputFor(page, 'model', `CLUSTER_${name}`).inputValue().then(Number)));
      assert.deepEqual(weights, [0.7, 0.23, 0.07]);
      await inputFor(page, 'run', 'particles').fill('8');
      const body = await recompute(page);
      assert.deepEqual(body.model, { CLUSTER_ALPHA: 0.7, CLUSTER_BETA: 0.23, CLUSTER_GAMMA: 0.07 });
      assert.match(await statusOf(page), /^Recomputed\./);
    });

    check('the graph is measured again whenever the pane opens or closes', async (page) => {
      await openExplorer(page);
      const before = await graphFitsItsCanvas(page);
      await openPane(page);
      const open = await graphFitsItsCanvas(page);
      await page.locator('#parameterClose').click();
      const closed = await graphFitsItsCanvas(page);
      assert.deepEqual(closed, before);
      if (profile.name === 'desktop') {
        assert.ok(open[0] < before[0], 'the pane takes a column of its own');
        assert.equal(await page.locator('.right-panel').isVisible(), true);
        // Where both do not fit, the pane takes the basin column while open.
        await page.setViewportSize({ width: 1100, height: 1000 });
        await graphFitsItsCanvas(page);
        await openPane(page);
        assert.equal(await page.locator('.right-panel').isVisible(), false);
        await graphFitsItsCanvas(page);
        await page.locator('#parameterToggle').click();
        assert.equal(await page.locator('.right-panel').isVisible(), true);
        await graphFitsItsCanvas(page);
      } else {
        // On a phone the pane is a sheet over the page, and the graph keeps its size.
        assert.deepEqual(open, before);
        assert.equal(await page.locator('#parameterPane').isVisible(), false);
      }
    });

    check('the keyboard closes the pane and returns to its button', async (page) => {
      await openExplorer(page);
      await openPane(page);
      await inputFor(page, 'run', 'particles').focus();
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#parameterPane').isHidden(), true);
      assert.equal(await page.evaluate(() => document.activeElement.id), 'parameterToggle');
    });

    check('the sample chart has nothing to recompute', async (page) => {
      const requests = recordRequests(page);
      await openExplorer(page, '/explorer/');
      await page.locator('#parameterToggle').click();
      assert.equal(
        await statusOf(page),
        'This is the bundled sample chart. Open the explorer from a chart to change its parameters.',
      );
      assert.equal(await page.locator('#parameterRecompute').isDisabled(), true);
      assert.deepEqual(requests, []);
    });
  });
}
