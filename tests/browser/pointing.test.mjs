// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Stage 4 of the Standard view (#19): the panel points at the chart. A line resting under
// the pointer for half a second rings on the chart what it names, and the next line rings at
// once; a click or tap keeps a line's ring; keyboard focus on a control rings at once. What a
// line names is read here from the API's own records, not from the page's markup.
import {
  assert, describe, it, engineName, profiles, openChart, settled, geometry, natalColors, openRelationships, withPage,
} from './chart-helpers.mjs';

const TAB = engineName === 'webkit' ? 'Alt+Tab' : 'Tab';

// What is ringed on the chart, as the reader would name it: "day branch", "day row 癸"
// (a hidden stem's row, on the card's back and in the opened hidden stems), "arc <id>".
async function ringed(page) {
  return page.evaluate(() => [...document.querySelectorAll('#pillars .is-spotlit')].map((node) => {
    if (node.classList.contains('card')) return `${node.dataset.pillar} ${node.classList.contains('stem') ? 'stem' : 'branch'}`;
    if (node.classList.contains('relationship-arc')) return `arc ${node.dataset.relationshipId}`;
    return `${node.closest('[data-pillar]').dataset.pillar} row ${node.dataset.hiddenStem}`;
  }).sort());
}
// The same, from records of the API: a visible stem is its card; a hidden stem is its
// branch's card and its two rows.
const expected = (records) => {
  const cards = new Set();
  const rows = [];
  for (const e of records) {
    if (e.component === 'stem') cards.add(`${e.pillar} stem`);
    else {
      cards.add(`${e.pillar} branch`);
      rows.push(`${e.pillar} row ${e.char}`, `${e.pillar} row ${e.char}`);
    }
  }
  return [...cards, ...rows].sort();
};

// Points at a line: at once while a ring shows, else after the half second at rest.
async function rest(page, locator) {
  await locator.hover();
  await page.waitForFunction(() => document.getElementById('pillars').hasAttribute('data-spotlight'));
}

// Somewhere that names nothing: the chart's bar.
async function away(page) {
  const bar = await page.locator('.chart-identity').boundingBox();
  await page.mouse.move(bar.x + 4, bar.y + 4);
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / pointing`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 90000 }, () => withPage(profile, run));

    if (profile.name === 'desktop') {
      check('a line rings what it names after half a second at rest, the next line at once, and none once left', async (page) => {
        const payload = await openChart(page);
        await page.locator('button[data-context="roots"]').click();
        await settled(page);
        // When the pointer first came onto a line (read as the event arrives, before the
        // page's own handler: WebKit stamps synthetic events on another clock), and when
        // the ring showed.
        await page.evaluate(() => {
          document.addEventListener('pointermove', (event) => {
            if (window.__came === undefined && event.target.closest('#chart-panel [data-spot]')) window.__came = performance.now();
          }, true);
          new MutationObserver(() => {
            if (window.__lit === undefined && document.getElementById('pillars').hasAttribute('data-spotlight')) window.__lit = performance.now();
          }).observe(document.getElementById('pillars'), { attributes: true, attributeFilter: ['data-spotlight'] });
        });
        const rows = page.locator('#context-detail .context-evidence-row');
        await rest(page, rows.nth(0));
        const waited = await page.evaluate(() => window.__lit - window.__came);
        assert.ok(waited >= 500, `the ring showed after ${waited}ms`);
        const roots = ['hour', 'day', 'month', 'year'].flatMap((pillar) => payload.day_master_context.roots.filter((e) => e.pillar === pillar));
        assert.deepEqual(await ringed(page), expected([roots[0]]));
        // The page's other outlines step back meanwhile; the ring keeps within half the gap.
        const looks = await page.evaluate(() => [...document.querySelectorAll('#pillars .card.is-context-source')].map((card) => {
          const style = getComputedStyle(card);
          return [card.classList.contains('is-spotlit'), style.outlineColor, style.outlineWidth, style.outlineOffset];
        }));
        for (const [lit, color, width, offset] of looks) {
          if (lit) assert.deepEqual([color, width, offset], ['rgb(42, 37, 32)', '2px', '0px']);
          else assert.equal(color, 'rgba(0, 0, 0, 0)');
        }
        // Once a ring shows, the next line rings as soon as the pointer is on it.
        await rows.nth(1).hover();
        assert.deepEqual(await ringed(page), expected([roots[1]]));
        await away(page);
        await page.waitForFunction(() => !document.getElementById('pillars').hasAttribute('data-spotlight'));
        assert.deepEqual(await ringed(page), []);
        // And after a pause, the next ring waits its half second again.
        await page.waitForTimeout(300);
        await rows.nth(2).hover();
        await page.waitForTimeout(250);
        assert.deepEqual(await ringed(page), []);
        await page.waitForFunction(() => document.getElementById('pillars').hasAttribute('data-spotlight'));
        assert.deepEqual(await ringed(page), expected([roots[2]]));
      });

      check('every line that names something on the chart rings exactly that', async (page) => {
        const payload = await openChart(page);
        const profile = payload.role_profile;
        const roles = profile.groups.flatMap((group) => group.roles);
        const occurrences = (role) => [...role.visible, ...role.hidden];
        const failures = [];
        const compare = async (what, want) => {
          const got = await ringed(page);
          if (JSON.stringify(got) !== JSON.stringify(want)) failures.push(`${what}: ${got.join(', ')} ≠ ${want.join(', ')}`);
        };

        // The season: the month branch, and each of its hidden stems.
        await page.locator('button[data-context="season"]').click();
        await rest(page, page.locator('#context-detail .relationship-member > .relationship-identity'));
        await compare('the month branch', ['month branch']);
        for (const stem of payload.day_master_context.season.hidden_stems) {
          await rest(page, page.locator(`#context-detail .context-evidence-row:has-text("${stem.pinyin} ${stem.char}")`));
          await compare(`season ${stem.char}`, expected([stem]));
        }

        // The roles: each role where it occurs, each group where its roles do, each
        // visible stem, and each stem's roots.
        await page.locator('button[data-context="roles"]').click();
        await rest(page, page.locator(`[data-role="${roles.find((role) => role.presence !== 'absent').ten_god}"]`));
        for (const role of roles.filter((role) => role.presence !== 'absent')) {
          await rest(page, page.locator(`[data-role="${role.ten_god}"]`));
          await compare(role.ten_god, expected(occurrences(role)));
        }
        for (const group of profile.groups.filter((group) => group.presence !== 'absent')) {
          await rest(page, page.locator(`[data-role-group="${group.group}"] .role-group-heading`));
          await compare(group.group, expected(group.roles.flatMap(occurrences)));
        }
        for (const stem of profile.visible_stems) {
          await rest(page, page.locator(`.role-stem-entry:has([data-root-pillar="${stem.pillar}"]) .role-occurrence-place`));
          await compare(`${stem.pillar} stem`, [`${stem.pillar} stem`]);
          if (stem.roots.length) {
            await rest(page, page.locator(`.role-stem-entry [data-root-pillar="${stem.pillar}"]`));
            await compare(`${stem.pillar} roots`, expected(stem.roots));
          }
        }
        // An absent role names nothing on the chart.
        for (const role of roles.filter((role) => role.presence === 'absent')) {
          assert.equal(await page.locator(`[data-role="${role.ten_god}"]`).getAttribute('data-spot'), null, role.ten_god);
        }

        // A role's page: each occurrence, and each visible stem an occurrence leads to.
        for (const role of roles.filter((role) => role.presence !== 'absent')) {
          await page.locator(`[data-role="${role.ten_god}"]`).click();
          for (const record of occurrences(role)) {
            const id = record.component === 'stem' ? `visible:${record.pillar}` : `hidden:${record.pillar}:${record.char}`;
            await rest(page, page.locator(`[data-role-occurrence="${id}"] .role-occurrence-place`));
            await compare(`${role.ten_god} ${id}`, expected([record]));
          }
          for (const link of await page.locator('.role-exact [data-root-pillar]').all()) {
            await rest(page, link);
            await compare(`${role.ten_god} exact`, [`${await link.getAttribute('data-root-pillar')} stem`]);
          }
          await page.locator('[data-role-back]').click();
        }

        // Relationships: each entry its cards and its arc; a chosen one's members, and a
        // branch member's hidden stems.
        await page.locator('[data-close-panel]').click();
        await openRelationships(page);
        for (const relationship of payload.interactions) {
          const entry = page.locator(`.relationship-chip[data-relationship="${relationship.id}"]`);
          await rest(page, entry);
          await compare(relationship.id, [...relationship.members.map((member) => `${member.pillar} ${relationship.component}`),
            `arc ${relationship.id}`].sort());
          await entry.click();
          const names = {};
          for (const pillar of ['hour', 'day', 'month', 'year']) names[await page.locator(`#pillar-name-${pillar}`).textContent()] = pillar;
          const seen = [];
          for (const member of await page.locator('#relationship-detail .relationship-member').all()) {
            const pillar = names[await member.locator('.relationship-position').textContent()];
            seen.push(pillar);
            await rest(page, member.locator('.relationship-identity'));
            await compare(`${relationship.id} ${pillar}`, [`${pillar} ${relationship.component}`]);
          }
          assert.deepEqual(seen.sort(), relationship.members.map((member) => member.pillar).sort());
          await entry.click();
        }
        assert.deepEqual(failures, []);
      });

      check('a click keeps a line\'s ring, a second lets it go, and a control keeps its own action', async (page) => {
        const payload = await openChart(page);
        await page.locator('button[data-context="season"]').click();
        await settled(page);
        const stem = payload.day_master_context.season.hidden_stems[1];
        const row = page.locator(`#context-detail .context-evidence-row:has-text("${stem.pinyin} ${stem.char}")`);
        await row.click();
        assert.deepEqual(await ringed(page), expected([stem]));
        assert.equal(await row.evaluate((node) => node.classList.contains('is-spot-pinned')), true);
        // Kept while the pointer goes over to the chart to look.
        await page.locator('.card.branch[data-pillar="month"]').hover();
        await page.waitForTimeout(700);
        assert.deepEqual(await ringed(page), expected([stem]));
        await row.click();
        assert.deepEqual(await ringed(page), []);
        // A role opens its page; nothing is kept, and nothing rings until the pointer moves.
        await page.locator('button[data-context="roles"]').click();
        await page.locator('[data-role="indirect_wealth"]').click();
        await page.waitForTimeout(700);
        assert.deepEqual(await ringed(page), []);
        assert.equal(await page.locator('#context-detail-title').textContent(), 'Indirect Wealth');
      });

      check('keyboard focus on a control in the panel rings what it names at once', async (page) => {
        const payload = await openChart(page);
        await page.locator('button[data-context="roles"]').click();
        await page.locator('[data-close-panel]').focus();
        await page.keyboard.press(TAB);
        const roles = payload.role_profile.groups.flatMap((group) => group.roles);
        const first = roles[0];
        assert.equal(await page.evaluate(() => document.activeElement.dataset.role), first.ten_god);
        assert.deepEqual(await ringed(page), expected([...first.visible, ...first.hidden]));
        await page.keyboard.press(TAB);
        assert.deepEqual(await ringed(page), expected([...roles[1].visible, ...roles[1].hidden]));
        await page.keyboard.press(`Shift+${TAB}`);
        await page.keyboard.press(`Shift+${TAB}`);
        assert.equal(await page.evaluate(() => document.activeElement.matches('[data-close-panel]')), true);
        assert.deepEqual(await ringed(page), []);
      });
    }

    check('a tap keeps a line\'s ring and a second tap lets it go', async (page) => {
      const payload = await openChart(page);
      await page.locator('button[data-context="roots"]').click();
      await settled(page);
      const root = payload.day_master_context.roots.find((e) => e.pillar === 'day');
      const row = page.locator(`#context-detail .context-evidence-row[data-evidence-pillar="day"]`);
      if (profile.hasTouch) await row.tap(); else await row.click();
      assert.deepEqual(await ringed(page), expected([root]));
      if (profile.hasTouch) await row.tap(); else await row.click();
      assert.deepEqual(await ringed(page), []);
    });

    check('pointing moves, opens, turns and recolours nothing, and a closed page takes its rings', async (page) => {
      await openChart(page);
      await page.locator('button[data-context="roots"]').click();
      await settled(page);
      const before = { geometry: await geometry(page), colors: await natalColors(page) };
      const row = page.locator('#context-detail .context-evidence-row').first();
      if (profile.hasTouch) await row.tap(); else await row.click();
      assert.notDeepEqual(await ringed(page), []);
      await settled(page);
      assert.deepEqual(await geometry(page), before.geometry);
      assert.deepEqual(await natalColors(page), before.colors);
      assert.equal(await page.locator('.card.is-flipped, .hidden-stems-panel.is-expanded').count(), 0);
      // The ring keeps within half the 4px gap between a pillar's stem and branch.
      const reach = await page.locator('#pillars .card.is-spotlit').evaluateAll((cards) => cards.map((card) => {
        const style = getComputedStyle(card);
        return parseFloat(style.outlineWidth) + parseFloat(style.outlineOffset);
      }));
      assert.ok(reach.every((value) => value <= 2), `reach ${reach}`);
      // Another topic, and the panel closed: no ring stays behind.
      await page.locator('button[data-context="season"]').click();
      assert.deepEqual(await ringed(page), []);
      const season = page.locator('#context-detail .context-evidence-row').first();
      if (profile.hasTouch) await season.tap(); else await season.click();
      assert.notDeepEqual(await ringed(page), []);
      await page.locator('[data-close-panel]').click();
      assert.deepEqual(await ringed(page), []);
      assert.equal(await page.locator('#pillars').getAttribute('data-spotlight'), null);
    });
  });
}
