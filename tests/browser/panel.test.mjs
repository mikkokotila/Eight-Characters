// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Stage 4 of the Standard view (#19), its last part: what the panel says. Every page reads
// from the left and ends with one note; the roles are a matrix of marks; a stem is a line
// of text, never a box; and nothing is said twice.
import {
  assert, describe, it, engineName, profiles, openChart, settled, openRelationships, withPage,
} from './chart-helpers.mjs';

// Every page of the panel, opened from a closed panel.
const PAGES = {
  season: (page) => page.locator('button[data-context="season"]').click(),
  roots: (page) => page.locator('button[data-context="roots"]').click(),
  roles: (page) => page.locator('button[data-context="roles"]').click(),
  'a role': async (page) => {
    await page.locator('button[data-context="roles"]').click();
    await page.locator('[data-role="indirect_wealth"]').click();
  },
  'an absent role': async (page) => {
    await page.locator('button[data-context="roles"]').click();
    await page.locator('[data-role="direct_officer"]').click();
  },
  "a stem's roots": async (page) => {
    await page.locator('button[data-context="roles"]').click();
    await page.locator('.role-stem-entry button[data-root-pillar="hour"]').click();
  },
  'a relationship': async (page) => {
    await openRelationships(page);
    await page.locator('.relationship-chip').first().click();
  },
  "a pillar's changes": (page) => page.locator('.pillar-identity[data-pillar="hour"]').click(),
};

async function visit(page, run) {
  for (const [name, open] of Object.entries(PAGES)) {
    await open(page);
    await settled(page);
    await run(name);
    await page.locator('[data-close-panel]').click();
  }
}

// The canonical chart's roles (1988-02-04 16:30 Chengdu), as roles.test.mjs reads them.
const PRESENCE = {
  friend: 'hidden_only', rob_wealth: 'hidden_only', eating_god: 'hidden_only', hurting_officer: 'hidden_only',
  indirect_wealth: 'visible_and_hidden', direct_wealth: 'visible_and_hidden', seven_killings: 'hidden_only',
  direct_officer: 'absent', indirect_resource: 'visible_only', direct_resource: 'absent',
};
const MARKS = {
  visible_and_hidden: ['visible', 'hidden'], visible_only: ['visible', 'absent'],
  hidden_only: ['absent', 'hidden'], absent: ['absent', 'absent'],
};
const INK = { 1: 'rgb(42, 37, 32)', 2: 'rgb(101, 95, 88)' };

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / panel`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 90000 }, () => withPage(profile, run));

    check('the roles are a matrix: a drawn mark for each role under the visible and the hidden stems', async (page) => {
      const payload = await openChart(page);
      await page.locator('button[data-context="roles"]').click();
      await settled(page);
      const found = await page.locator('#context-detail').evaluate((detail) => {
        const centre = (node) => { const r = node.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; };
        const columns = [...detail.querySelectorAll('.role-overview-columns > span')].map(centre);
        return {
          columns: columns.length,
          typed: /[●○]/.test(detail.innerText),
          roles: Object.fromEntries([...detail.querySelectorAll('button[data-role]')].map((button) => {
            const marks = [...button.querySelectorAll('.role-mark')];
            const name = button.querySelector('.role-choice-name');
            return [button.dataset.role, {
              marks: marks.map((mark) => mark.dataset.mark),
              text: marks.map((mark) => mark.textContent).join(''),
              // Each mark stands under its column's heading.
              drift: marks.map((mark, i) => Math.abs(centre(mark).x - columns[i].x)),
              sizes: marks.map((mark) => [mark.getBoundingClientRect().width, getComputedStyle(mark).backgroundColor,
                getComputedStyle(mark).boxShadow]),
              ink: getComputedStyle(name).color,
              weight: getComputedStyle(name).fontWeight,
              absent: button.classList.contains('is-absent'),
            }];
          })),
          groups: Object.fromEntries([...detail.querySelectorAll('[data-role-group]')].map((group) => {
            const heading = group.querySelector('.role-group-heading');
            const parts = [heading.querySelector('.hidden-stem-dot'), heading.querySelector('h4'),
              heading.querySelector('.relationship-element')];
            return [group.dataset.roleGroup, {
              swatch: parts[0].className,
              // The swatch, the group's name and its element on one line.
              spread: Math.max(...parts.map((node) => centre(node).y)) - Math.min(...parts.map((node) => centre(node).y)),
            }];
          })),
        };
      });
      assert.equal(found.columns, 2);
      assert.equal(found.typed, false, 'the marks are drawn, not typed');
      for (const [role, presence] of Object.entries(PRESENCE)) {
        const row = found.roles[role];
        assert.deepEqual(row.marks, MARKS[presence], role);
        assert.equal(row.text, '', role);
        assert.ok(row.drift.every((drift) => drift <= 1), `${role}: marks off their columns by ${row.drift}`);
        for (const [mark, [width, fill, ring]] of row.marks.map((mark, i) => [mark, row.sizes[i]])) {
          if (mark === 'visible') assert.deepEqual([width, fill, ring], [10, INK[1], 'none'], `${role} ${mark}`);
          if (mark === 'hidden') {
            assert.deepEqual([width, fill], [10, 'rgba(0, 0, 0, 0)'], `${role} ${mark}`);
            assert.match(ring, /inset/, `${role} ${mark}`);
          }
          if (mark === 'absent') assert.deepEqual([width, fill], [4, INK[2]], `${role} ${mark}`);
        }
        // A role the chart lacks is dimmed to the secondary ink, and stays a choice.
        assert.equal(row.absent, presence === 'absent', role);
        assert.deepEqual([row.ink, row.weight], presence === 'absent' ? [INK[2], '400'] : [INK[1], '500'], role);
      }
      for (const group of payload.role_profile.groups) {
        const heading = found.groups[group.group];
        assert.equal(heading.swatch, `hidden-stem-dot ${group.element}`, group.group);
        assert.ok(heading.spread <= 3, `${group.group}: its heading takes ${heading.spread}px more than one line`);
      }
      // The words stay for assistive technology: each role says its presence.
      const words = {
        visible_and_hidden: 'Visible and hidden', visible_only: 'Visible only', hidden_only: 'Hidden only', absent: 'Not present',
      };
      for (const [role, presence] of Object.entries(PRESENCE)) {
        const name = await page.locator(`[data-role="${role}"] .role-choice-name`).textContent();
        assert.equal(await page.getByRole('button', { name: `${name} ${words[presence]}`, exact: true }).count(), 1, role);
      }
    });

    check('a stem in the panel is a line of text with its element\'s swatch, never a box', async (page) => {
      await openChart(page);
      const failures = [];
      await visit(page, async (name) => {
        failures.push(...await page.locator('#chart-panel').evaluate((panel, name) => {
          const rows = [...panel.querySelectorAll('.context-evidence-row')].filter((row) => row.checkVisibility());
          const elements = ['wood', 'fire', 'earth', 'metal', 'water'];
          return [
            ...(panel.querySelector('.is-context-evidence') ? [`${name}: the chart's highlight is in the panel`] : []),
            ...rows.flatMap((row) => {
              const style = getComputedStyle(row);
              const box = [style.outlineStyle, style.borderTopStyle, style.borderRightStyle, style.borderBottomStyle,
                style.borderLeftStyle, style.boxShadow, style.backgroundColor];
              const swatches = [...row.querySelectorAll(':scope > .hidden-stem-dot')];
              return [
                ...(box.join() === 'none,none,none,none,none,none,rgba(0, 0, 0, 0)' ? [] : [`${name}: ${row.dataset.evidenceChar} is boxed: ${box}`]),
                ...(swatches.length === 1 && elements.some((element) => swatches[0].classList.contains(element))
                  ? [] : [`${name}: ${row.dataset.evidenceChar} has no element swatch`]),
              ];
            }),
          ];
        }, name));
      });
      assert.deepEqual(failures, []);
    });

    check('nothing is said twice: a role\'s page names it once, and no label stands over another', async (page) => {
      for (const lang of ['en', 'fi']) {
        const payload = await openChart(page, { lang });
        await page.locator('button[data-context="roles"]').click();
        // An absent role's page says, in a sentence, that it is not present.
        for (const role of payload.role_profile.groups.flatMap((group) => group.roles).filter((role) => role.presence !== 'absent')) {
          await page.locator(`[data-role="${role.ten_god}"]`).click();
          const found = await page.locator('#context-detail').evaluate((detail) => {
            const title = detail.querySelector('h3').textContent;
            const text = detail.innerText;
            return { title, times: text.split(title).length - 1 };
          });
          assert.equal(found.times, 1, `${lang} ${found.title}: named ${found.times} times`);
          // Where each occurrence is stands beside it, on its first line.
          const places = await page.locator('#context-detail .role-occurrence').evaluateAll((rows) => rows.map((row) => {
            const place = row.querySelector('.role-occurrence-place .relationship-position').getBoundingClientRect();
            const stem = row.querySelector('.context-evidence-identity').getBoundingClientRect();
            return { beside: place.right < stem.left, rise: Math.abs(place.top - stem.top) };
          }));
          for (const place of places) {
            assert.equal(place.beside, true, `${lang} ${role.ten_god}`);
            assert.ok(place.rise <= 2, `${lang} ${role.ten_god}: the place is ${place.rise}px off the stem's line`);
          }
          await page.locator('[data-role-back]').click();
        }
      }
      // A label, in the capitals of the pillars' names, never stands directly over another.
      const failures = [];
      await openChart(page);
      await visit(page, async (name) => {
        failures.push(...await page.locator('#chart-panel').evaluate((panel, name) => {
          const labels = [];
          const walker = document.createTreeWalker(panel, NodeFilter.SHOW_TEXT);
          for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            const element = node.parentElement;
            if (!node.textContent.trim() || !element.checkVisibility() || element.closest('.sr-only')) continue;
            if (labels.at(-1)?.element === element) continue;
            const style = getComputedStyle(element);
            labels.push({ element, label: style.textTransform === 'uppercase', box: element.getBoundingClientRect() });
          }
          return labels.slice(1).flatMap((next, i) => {
            const previous = labels[i];
            return previous.label && next.label && next.box.top >= previous.box.bottom - 1
              ? [`${name}: "${previous.element.textContent.trim()}" over "${next.element.textContent.trim()}"`] : [];
          });
        }, name));
      });
      assert.deepEqual(failures, []);
    });

    check('every page reads from the left and ends with one note, in one style', async (page) => {
      for (const lang of ['en', 'fi']) {
        await openChart(page, { lang });
        const styles = new Set();
        const failures = [];
        await visit(page, async (name) => {
          const found = await page.locator('#chart-panel').evaluate((panel) => {
            const page = [...panel.querySelectorAll(':scope > section')].filter((section) => section.checkVisibility()).at(-1);
            const notes = [...panel.querySelectorAll('.relationship-note')].filter((note) => note.checkVisibility());
            const texts = [...page.querySelectorAll('*')].filter((node) => node.checkVisibility()
              && [...node.childNodes].some((child) => child.nodeType === Node.TEXT_NODE && child.textContent.trim()));
            const left = page.getBoundingClientRect().left + parseFloat(getComputedStyle(page).paddingLeft);
            const style = (node) => ['fontFamily', 'fontSize', 'fontWeight', 'lineHeight', 'letterSpacing', 'color']
              .map((key) => getComputedStyle(node)[key]).join(' ');
            return {
              notes: notes.length,
              last: notes.length === 1 && texts.at(-1) === notes[0],
              // Its title, its first line under the title and its note begin at the page's edge.
              edges: [page.querySelector('h3'), page.querySelector('h3 ~ *, .relationship-detail-heading ~ *'), notes[0]]
                .map((node) => Math.round(node.getBoundingClientRect().left - left)),
              // The matrix's column headings stand centred over their marks; a button is as
              // wide as its words.
              aligned: texts.filter((node) => !node.closest('.role-overview-columns, button'))
                .every((node) => ['start', 'left'].includes(getComputedStyle(node).textAlign)),
              style: notes[0] ? style(notes[0]) : null,
            };
          });
          if (found.notes !== 1 || !found.last) failures.push(`${lang} ${name}: ${found.notes} notes, last: ${found.last}`);
          if (found.edges.some((edge) => edge !== 0)) failures.push(`${lang} ${name}: begins at ${found.edges}`);
          if (!found.aligned) failures.push(`${lang} ${name}: centred text`);
          styles.add(found.style);
        });
        assert.deepEqual(failures, []);
        assert.equal(styles.size, 1, `${lang}: the notes differ: ${[...styles].join(' | ')}`);
      }
    });

    if (profile.name === 'desktop') {
      it('a note holds 60–75 characters to the line where there is room, and never more than 75', {
        timeout: 90000,
      }, () => withPage(profile, async (page) => {
        const perLine = (page) => page.locator('#chart-panel').evaluate((panel) => {
          const note = [...panel.querySelectorAll('.relationship-note')].find((node) => node.checkVisibility());
          const range = document.createRange();
          const lines = new Map();
          const text = note.firstChild;
          for (let i = 0; i < text.length; i += 1) {
            range.setStart(text, i);
            range.setEnd(text, i + 1);
            const rect = range.getClientRects()[0];
            if (rect) lines.set(Math.round(rect.top), (lines.get(Math.round(rect.top)) ?? 0) + 1);
          }
          // The count includes the space that ends each line but the last.
          return [...lines.values()].map((count, i, all) => (i < all.length - 1 ? count - 1 : count));
        });
        const failures = [];
        for (const lang of ['en', 'fi']) {
          // A sheet the width of a tablet, and the panel beside the chart.
          for (const width of [1024, 1440]) {
            await page.setViewportSize({ width, height: 900 });
            await openChart(page, { lang });
            const full = [];
            await visit(page, async (name) => {
              const lines = await perLine(page);
              full.push(...lines.slice(0, -1));
              if (lines.some((count) => count > 75)) failures.push(`${lang} ${width} ${name}: ${lines}`);
            });
            // Where the page is wider than the note, its lines hold 60–75 characters: a long
            // word left for the next line makes one shorter now and then.
            const average = full.reduce((sum, count) => sum + count, 0) / full.length;
            if (width === 1024 && (average < 60 || average > 75)) failures.push(`${lang} ${width}: ${average.toFixed(1)} on average`);
          }
        }
        assert.deepEqual(failures, []);
      }));
    }

    check('the panel writes a pillar\'s name as its column header does', async (page) => {
      for (const lang of ['en', 'fi']) {
        await openChart(page, { lang });
        const header = await page.locator('.pillar-plain').first().evaluate((node) => {
          const style = getComputedStyle(node);
          return [style.fontFamily, style.fontSize, style.fontWeight, style.letterSpacing, style.textTransform, style.color].join(' ');
        });
        const names = await page.locator('.pillar-plain').allTextContents();
        const failures = [];
        let seen = 0;
        await visit(page, async (name) => {
          // Labels, not the links that lead to a pillar's stem.
          const found = await page.locator('#chart-panel').evaluate((panel, names) => [...panel.querySelectorAll('*')]
            .filter((node) => node.checkVisibility() && names.includes(node.textContent.trim()) && node.children.length === 0
              && !node.closest('button'))
            .map((node) => {
              const style = getComputedStyle(node);
              return [node.textContent.trim(),
                [style.fontFamily, style.fontSize, style.fontWeight, style.letterSpacing, style.textTransform, style.color].join(' ')];
            }), names);
          seen += found.length;
          for (const [text, style] of found) if (style !== header) failures.push(`${lang} ${name}: ${text} in ${style}`);
        });
        assert.ok(seen >= 8, `${lang}: only ${seen} pillar names in the panel`);
        assert.deepEqual(failures, []);
      }
    });
  });
}
