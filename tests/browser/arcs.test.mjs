// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Stage 4 of the Standard view (#19), part 2: the relationships drawn on the chart. Stem
// combinations arch above the stems and branch relations hang below the branches, wherever
// the four pillars stand side by side; the pillars stand in the same place whatever the
// relationships.
import {
  assert, describe, it, engineName, profiles, openChart, settled, showDisplay, openRelationships, withPage, screenshot,
} from './chart-helpers.mjs';

// Charts the API calculates for Chengdu, by what their arcs show.
const CHARTS = [
  ['no relationships', { date: '1990-01-15', time: '12:00' }],
  ['one stem combination across the chart', {}],
  ['a stem combination and a branch clash', { date: '1990-01-05', time: '12:00' }],
  ['a stem combination and two branch combinations', { date: '1990-01-07', time: '12:00' }],
  ['two harmony frames on shared branches', { date: '1990-01-08', time: '12:00' }],
  ['stem arcs four levels deep', { date: '1950-04-20', time: '19:17' }],
  ['branch arcs four levels deep', { date: '1950-05-25', time: '17:17' }],
  ['ten relationships', { date: '2004-05-20', time: '11:17' }],
  ['a directional combination', { date: '1950-01-04', time: '12:00' }],
  ['a self-punishment', { date: '1950-09-10', time: '20:00' }],
  ['a half-frame', { date: '1951-01-14', time: '20:00' }],
  ['two punishment triangles and a harm on one arc', { date: '1950-08-17', time: '12:00' }],
  ['six feet on one card', { date: '1950-02-12', time: '12:00' }],
];
const TEN = { date: '2004-05-20', time: '11:17' };
const THREE_STRANDS = { date: '1950-08-17', time: '12:00' };
const ORDER = ['hour', 'day', 'month', 'year'];
// Each kind's line, and its width in pixels.
const LINE = {
  stem_combination: ['solid', 1], branch_combination: ['solid', 1], directional_combination: ['solid', 2],
  branch_clash: ['dashed', 1], punishment: ['dashed', 2], half_punishment: ['dashed', 2], self_punishment: ['dashed', 2],
  harm: ['dotted', 2], harmony_frame: ['double', 3], half_frame: ['double', 3],
};
// The shared families keep an arc each; a relationship of another family joins an arc
// that already spans its columns, as a strand (relationships.js, arcLayout).
const OWN_ARC = ['stem_combination', 'branch_combination', 'branch_clash', 'harmony_frame'];
// Feet that meet on one card stand 6px apart, the strands of one arc 3px. Over every
// combination of four branches the widest set of feet spans 24px (寅寅巳申 on the day
// card), so none is more than 12px off the middle.
const FOOT = 12.5;

// Each relationship's arc, as the page lays them out.
function slotsOf(relationships) {
  const slots = [];
  const slotOf = new Map();
  for (const relationship of relationships) {
    const columns = relationship.members.map((member) => ORDER.indexOf(member.pillar));
    const from = Math.min(...columns);
    const to = Math.max(...columns);
    let slot = OWN_ARC.includes(relationship.kind) ? null
      : slots.find((other) => other.component === relationship.component && other.from === from && other.to === to);
    if (!slot) {
      slot = { component: relationship.component, from, to, strands: [] };
      slots.push(slot);
    }
    slot.strands.push(relationship.id);
    slotOf.set(relationship.id, slot);
  }
  return slotOf;
}
const INK = { rest: 'rgb(101, 95, 88)', chosen: 'rgb(42, 37, 32)', receded: 'rgba(42, 37, 32, 0.3)' };

// Every arc as drawn, with the cards and the rows it is drawn in.
function drawn(page) {
  return page.evaluate(() => {
    const box = (node) => {
      const r = node.getBoundingClientRect();
      return { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
    };
    return {
      bands: Object.fromEntries([...document.querySelectorAll('.relationship-arcs')]
        .map((band) => [band.dataset.component, box(band)])),
      cards: Object.fromEntries([...document.querySelectorAll('#pillars .card')]
        .map((card) => [`${card.dataset.pillar} ${card.classList.contains('stem') ? 'stem' : 'branch'}`, box(card)])),
      arcs: [...document.querySelectorAll('.relationship-arc')].map((arc) => {
        const line = arc.querySelector('.relationship-arc-line');
        const style = getComputedStyle(line);
        const foot = arc.querySelector('.relationship-arc-foot');
        return {
          id: arc.dataset.relationshipId,
          component: arc.parentElement.dataset.component,
          line: box(line),
          style: style.borderLeftStyle,
          width: style.borderLeftWidth,
          color: style.borderLeftColor,
          rises: [...arc.querySelectorAll('.relationship-arc-rise')].map(box),
          foot: foot && box(foot),
        };
      }),
    };
  });
}

// Where each card stands, with x taken within the chart column.
function places(page) {
  return page.evaluate(() => {
    const column = document.querySelector('.chart-column').getBoundingClientRect();
    const tenth = (value) => Math.round(value * 10) / 10;
    return [...document.querySelectorAll('#pillars .card')].map((card) => {
      const r = card.getBoundingClientRect();
      return {
        card: `${card.dataset.pillar} ${card.classList.contains('stem') ? 'stem' : 'branch'}`,
        x: tenth(r.x - column.x), y: tenth(r.y + scrollY), width: tenth(r.width), height: tenth(r.height),
      };
    });
  });
}

// What an arc must look like, from its relationship and the cards it joins.
function misdrawn(relationship, picture, state) {
  const failures = [];
  const fail = (text) => failures.push(`${state} ${relationship.id}: ${text}`);
  const arc = picture.arcs.find((candidate) => candidate.id === relationship.id);
  if (!arc) return [`${state} ${relationship.id}: not drawn`];
  const members = [...relationship.members].sort((a, b) => ORDER.indexOf(a.pillar) - ORDER.indexOf(b.pillar));
  const cards = members.map((member) => picture.cards[`${member.pillar} ${relationship.component}`]);
  const middle = (card) => (card.left + card.right) / 2;
  const band = picture.bands[relationship.component];
  if (arc.component !== relationship.component) fail(`drawn with the ${arc.component}s`);
  if (Math.abs(arc.line.left - middle(cards[0])) > FOOT) fail(`starts at ${arc.line.left}, the ${members[0].pillar} card's middle is ${middle(cards[0])}`);
  if (Math.abs(arc.line.right - middle(cards.at(-1))) > FOOT) fail(`ends at ${arc.line.right}, the ${members.at(-1).pillar} card's middle is ${middle(cards.at(-1))}`);
  const [style, width] = LINE[relationship.kind];
  if (arc.style !== style) fail(`a ${arc.style} line`);
  if (arc.width !== `${width}px`) fail(`a line ${arc.width} wide`);
  if (relationship.component === 'stem') {
    // Standing on the stems, within its row.
    if (Math.abs(arc.line.bottom - cards[0].top) > 0.5) fail(`its feet end at ${arc.line.bottom}, the stems' tops are at ${cards[0].top}`);
    if (arc.line.top < band.top - 0.5) fail(`rises to ${arc.line.top}, above its row at ${band.top}`);
  } else {
    // Hanging from the branches, the feet rising past any opened hidden stems.
    for (const rise of arc.rises) {
      if (Math.abs(rise.top - cards[0].bottom) > 0.5) fail(`a foot starts at ${rise.top}, the branches' feet are at ${cards[0].bottom}`);
    }
    if (arc.rises.length !== 2) fail(`${arc.rises.length} rising feet`);
    if (arc.line.bottom > band.bottom + 0.5) fail(`falls to ${arc.line.bottom}, below its row at ${band.bottom}`);
  }
  if (members.length === 3) {
    if (!arc.foot) fail('no foot on the middle member');
    else if (Math.abs(arc.foot.left - middle(cards[1])) > FOOT) fail(`the middle foot is at ${arc.foot.left}, the ${members[1].pillar} card's middle is ${middle(cards[1])}`);
  } else if (arc.foot) {
    fail('a middle foot on a pair');
  }
  return failures;
}

// The feet on each card: 6px apart, the strands of one arc 3px, and centred on the
// card's middle.
function unevenFeet(relationships, picture, state) {
  const slotOf = slotsOf(relationships);
  const feet = {};
  const add = (component, pillar, x, slot) => { (feet[`${pillar} ${component}`] ??= []).push({ x, slot }); };
  for (const relationship of relationships) {
    const arc = picture.arcs.find((candidate) => candidate.id === relationship.id);
    const slot = slotOf.get(relationship.id);
    const members = [...relationship.members].sort((a, b) => ORDER.indexOf(a.pillar) - ORDER.indexOf(b.pillar));
    add(relationship.component, members[0].pillar, arc.line.left, slot);
    add(relationship.component, members.at(-1).pillar, arc.line.right, slot);
    if (members.length === 3) add(relationship.component, members[1].pillar, arc.foot.left, slot);
  }
  const failures = [];
  for (const [card, found] of Object.entries(feet)) {
    const box = picture.cards[card];
    const middle = (box.left + box.right) / 2;
    const sorted = [...found].sort((a, b) => a.x - b.x);
    const centre = (sorted[0].x + sorted.at(-1).x) / 2;
    if (Math.abs(centre - middle) > 0.5) failures.push(`${state}: the feet on the ${card} card centre on ${centre}, the card's middle is ${middle}`);
    sorted.slice(1).forEach((foot, index) => {
      const gap = foot.slot === sorted[index].slot ? 3 : 6;
      if (Math.abs(foot.x - sorted[index].x - gap) > 0.5) failures.push(`${state}: feet ${foot.x - sorted[index].x}px apart on the ${card} card, not ${gap}px`);
    });
  }
  return failures;
}

// Arcs that span or cross each other stand at different heights, the wider above.
function tangled(relationships, picture, state) {
  const failures = [];
  const span = (relationship) => {
    const columns = relationship.members.map((member) => ORDER.indexOf(member.pillar));
    return [Math.min(...columns), Math.max(...columns)];
  };
  const height = (relationship) => {
    const arc = picture.arcs.find((candidate) => candidate.id === relationship.id);
    return Math.round((arc.line.bottom - arc.line.top) * 10) / 10;
  };
  for (const a of relationships) {
    for (const b of relationships) {
      if (a === b || a.component !== b.component) continue;
      const [aFrom, aTo] = span(a);
      const [bFrom, bTo] = span(b);
      if (Math.max(aFrom, bFrom) >= Math.min(aTo, bTo)) continue;
      if (height(a) === height(b)) failures.push(`${state}: ${a.id} and ${b.id} overlap at one height`);
      const aHoldsB = aFrom <= bFrom && bTo <= aTo && aTo - aFrom > bTo - bFrom;
      if (aHoldsB && height(a) <= height(b)) failures.push(`${state}: ${a.id} spans ${b.id} but is not above it`);
    }
  }
  return failures;
}

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / relationship arcs`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 120000 }, () => withPage(profile, run));

    if (profile.name === 'desktop') {
      check('each relationship is drawn from the middle of its first card to the middle of its last, in its line', async (page) => {
        const failures = [];
        for (const [name, chart] of CHARTS) {
          const payload = await openChart(page, chart);
          for (const width of [1440, 1024, 700]) {
            await page.setViewportSize({ width, height: 1000 });
            const picture = await drawn(page);
            const state = `${name} at ${width}px`;
            assert.equal(picture.arcs.length, payload.interactions.length, state);
            const wrong = payload.interactions.flatMap((relationship) => misdrawn(relationship, picture, state));
            // The arcs' feet and heights, once every arc is where it belongs.
            failures.push(...(wrong.length > 0 ? wrong
              : [...unevenFeet(payload.interactions, picture, state), ...tangled(payload.interactions, picture, state)]));
          }
          await page.setViewportSize(profile.viewport);
          await screenshot(page, `${profile.name}-arcs-${name.replaceAll(' ', '-')}`);
        }
        assert.deepEqual(failures, []);
      });

      check('relationships on the same columns share an arc, each strand inside the one before', async (page) => {
        const payload = await openChart(page, THREE_STRANDS);
        const ids = ['punishment:30:year-month-hour', 'punishment:30:year-day-hour', 'harm:41:year-hour'];
        assert.deepEqual(ids.filter((id) => payload.interactions.some((relationship) => relationship.id === id)), ids);
        const picture = await drawn(page);
        const [outer, middle, inner] = ids.map((id) => picture.arcs.find((arc) => arc.id === id).line);
        const depth = (line) => line.bottom - line.top;
        for (const [wider, narrower] of [[outer, middle], [middle, inner]]) {
          assert.ok(Math.abs(depth(wider) - depth(narrower) - 3) <= 0.5, `strands ${depth(wider)} and ${depth(narrower)} deep`);
          assert.ok(Math.abs(narrower.left - wider.left - 3) <= 0.5, `inner strand starts ${narrower.left - wider.left}px in`);
          assert.ok(Math.abs(wider.right - narrower.right - 3) <= 0.5, `inner strand ends ${wider.right - narrower.right}px in`);
        }
        await screenshot(page, `${profile.name}-arcs-three-strands`);
      });

      check('a chosen relationship darkens its arc; the others recede until it is cleared', async (page) => {
        const payload = await openChart(page, TEN);
        const inks = async () => Object.fromEntries((await drawn(page)).arcs.map((arc) => [arc.id, arc.color]));
        const everyArc = (color) => Object.fromEntries(payload.interactions.map((relationship) => [relationship.id, color]));
        assert.deepEqual(await inks(), everyArc(INK.rest));
        await openRelationships(page);
        const chosen = payload.interactions[2];
        await page.locator('.relationship-chip').nth(2).click();
        await settled(page);
        assert.deepEqual(await inks(), { ...everyArc(INK.receded), [chosen.id]: INK.chosen });
        await page.keyboard.press('Escape');
        await settled(page);
        assert.equal(await page.locator('.relationship-chip').nth(2).getAttribute('aria-expanded'), 'false');
        assert.equal(await page.locator('.relationship-arcs.has-selection, .relationship-arc.is-active').count(), 0);
        assert.equal(await page.locator('.relationship-chip').nth(2).evaluate((node) => node === document.activeElement), true);
        // Escape returns keyboard focus to the chip, whose spotlight can still light
        // its arc. Moving focus outside the panel clears that independent spotlight.
        await page.locator('#relationships-topic').focus();
        await settled(page);
        assert.deepEqual(await inks(), everyArc(INK.rest));
      });

      check('opened hidden stems cover the feet that pass behind them, and the arcs keep their shape', async (page) => {
        await openChart(page, TEN);
        const closed = await drawn(page);
        await showDisplay(page, 'hidden-stems');
        const open = await drawn(page);
        const height = (arc) => Math.round((arc.line.bottom - arc.line.top) * 10) / 10;
        for (const arc of open.arcs) {
          const before = closed.arcs.find((candidate) => candidate.id === arc.id);
          assert.equal(height(arc), height(before), `${arc.id} changed its shape`);
        }
        // Branches with three hidden stems, and the day's with two, whose panel ends higher.
        const panels = await page.locator('.hidden-stems-panel').evaluateAll((nodes) => Object.fromEntries(nodes.map((node) => {
          const r = node.getBoundingClientRect();
          return [node.dataset.pillar, { left: r.left, right: r.right, top: r.top, bottom: r.bottom, rows: node.querySelectorAll('.hidden-stem-item').length }];
        })));
        assert.deepEqual(Object.fromEntries(Object.entries(panels).map(([pillar, panel]) => [pillar, panel.rows])),
          { hour: 3, day: 2, month: 3, year: 3 });
        const arcsHidden = async (hidden) => page.evaluate((hidden) => {
          document.querySelectorAll('.relationship-arcs').forEach((band) => { band.style.visibility = hidden ? 'hidden' : ''; });
        }, hidden);
        const region = async (clip) => {
          const shown = await page.screenshot({ clip });
          await arcsHidden(true);
          const bare = await page.screenshot({ clip });
          await arcsHidden(false);
          return shown.equals(bare);
        };
        const middle = (pillar) => (panels[pillar].left + panels[pillar].right) / 2;
        // Inside the hour's panel its two feet run behind it: nothing of them shows.
        assert.equal(await region({ x: middle('hour') - 10, y: panels.hour.top + 8, width: 20, height: panels.hour.bottom - panels.hour.top - 16 }), true,
          'a foot shows through the hour panel');
        // Below the day's shorter panel, down to the foot of the row, its two feet are seen on
        // their way to the arcs.
        assert.equal(await region({ x: middle('day') - 10, y: panels.day.bottom + 2, width: 20, height: panels.hour.bottom - panels.day.bottom - 4 }), false,
          'no foot below the day panel');
        await screenshot(page, `${profile.name}-arcs-hidden-stems`);
      });

      check('arcs the rows cannot hold fail visibly', async (page) => {
        // Two more copies of the canonical Hour–Year combination would stand five levels high.
        await openChart(page, { success: false }, (payload) => {
          const [only] = payload.interactions;
          payload.interactions.push({ ...only, id: `${only.id}:again` }, { ...only, id: `${only.id}:and-again` });
        });
        assert.equal(await page.locator('#chart-view').isVisible(), false);
        assert.match(await page.locator('#form-error').innerText(), /Relationship arcs need more than 4 levels/);
      });
    }

    check('the pillars stand in the same place with none to all ten of a chart\'s relationships', async (page) => {
      // One chart, so that nothing else about it changes: its first n relationships, n from 0 to 10.
      let first = null;
      for (let shown = 0; shown <= 10; shown += 1) {
        await openChart(page, TEN, (payload) => {
          assert.equal(payload.interactions.length, 10);
          payload.interactions = payload.interactions.slice(0, shown);
        });
        assert.equal(await page.locator('.relationship-arc').count(), shown);
        const displays = await page.locator('.relationship-arcs').evaluateAll((bands) => bands.map((band) => getComputedStyle(band).display));
        // Two pillars to a row on phones: nothing to span, and the sheet lists the relationships.
        assert.deepEqual(displays, profile.name === 'desktop' ? ['grid', 'grid'] : ['none', 'none']);
        const placed = await places(page);
        if (first === null) first = placed;
        else assert.deepEqual(placed, first, `${shown} relationships move the cards`);
      }
    });
  });
}
