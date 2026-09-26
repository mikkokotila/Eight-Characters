// Run with Node's built-in test runner and an explicitly selected Playwright install.
// Stage 4 of the Standard view (#19), part 4: the chart by keyboard. The cards take one tab
// stop and arrows move between them; Enter or Space opens a branch's hidden stems; T turns
// a card; ? lists the keys; ⌘K or Ctrl+K finds a command and runs it.
import {
  assert, describe, it, engineName, profiles, openChart, settled, withPage,
} from './chart-helpers.mjs';

// The element with focus: a card by its pillar and side, anything else by its id or text.
function focused(page) {
  return page.evaluate(() => {
    const node = document.activeElement;
    if (node.matches('#pillars .card')) return `${node.dataset.pillar} ${node.classList.contains('stem') ? 'stem' : 'branch'}`;
    return node.id || node.textContent.replace(/\s+/g, ' ').trim();
  });
}

// The cards that take the tab stop.
function stops(page) {
  return page.locator('#pillars .card[tabindex="0"]').evaluateAll((cards) =>
    cards.map((card) => `${card.dataset.pillar} ${card.classList.contains('stem') ? 'stem' : 'branch'}`));
}

// Safari moves Tab only between text fields and tab-indexed elements, unless Full Keyboard
// Access is on; Option+Tab reaches every control. The cards are tab-indexed, so plain Tab
// reaches them there too.
const TAB = engineName === 'webkit' ? 'Alt+Tab' : 'Tab';
const BACK_TAB = engineName === 'webkit' ? 'Alt+Shift+Tab' : 'Shift+Tab';

async function press(page, ...keys) {
  for (const key of keys) await page.keyboard.press(key);
  await settled(page);
}

// Focus on the hour stem, as Tab brings it from the hour pillar's name.
async function intoCards(page) {
  await page.locator('.pillar-identity[data-pillar="hour"]').focus();
  await press(page, TAB);
  assert.equal(await focused(page), 'hour stem');
}

const topicOf = (page) => page.evaluate(() => new URLSearchParams(location.hash.slice('#chart?'.length)).get('topic'));
const openDialogs = (page) => page.evaluate(() => [...document.querySelectorAll('dialog')].filter((dialog) => dialog.open).map((dialog) => dialog.id));

for (const profile of profiles) {
  describe(`${engineName} / ${profile.name} / keyboard`, { concurrency: false }, () => {
    const check = (name, run) => it(name, { timeout: 60000 }, () => withPage(profile, run));

    check('the cards take one tab stop, and the arrows move between them', async (page) => {
      await openChart(page, { lang: 'en' });
      const pillars = page.getByRole('group', { name: 'Pillars' });
      assert.equal(await pillars.getAttribute('id'), 'pillars');
      assert.match(await page.locator('#pillars-keys').textContent(), /^Arrow keys move between the cards\./);
      assert.deepEqual(await stops(page), ['hour stem']);
      await intoCards(page);
      const walk = [];
      const scrolled = await page.evaluate(() => scrollY);
      for (const key of ['ArrowRight', 'ArrowRight', 'ArrowRight', 'ArrowRight', 'ArrowDown', 'ArrowDown',
        'ArrowLeft', 'ArrowUp', 'ArrowUp', 'ArrowLeft', 'ArrowLeft', 'ArrowLeft']) {
        await press(page, key);
        walk.push(await focused(page));
        assert.deepEqual(await stops(page), [walk.at(-1)], `one tab stop after ${key}`);
      }
      assert.deepEqual(walk, ['day stem', 'month stem', 'year stem', 'year stem', 'year branch', 'year branch',
        'month branch', 'month stem', 'month stem', 'day stem', 'hour stem', 'hour stem']);
      // Four pillars side by side: the page itself does not move under the arrows.
      if (profile.name === 'desktop') assert.equal(await page.evaluate(() => scrollY), scrolled);
      // Tab leaves the cards for the next pillar's name; coming back finds the card last used.
      await press(page, 'ArrowRight', 'ArrowDown', TAB);
      assert.equal(await focused(page), '癸丑 Gui Chou');
      await press(page, BACK_TAB);
      assert.equal(await focused(page), 'day branch');
    });

    check('Enter and Space open and close a branch\'s hidden stems; on a stem they do nothing', async (page) => {
      await openChart(page, { lang: 'en' });
      await intoCards(page);
      const scrolled = await page.evaluate(() => scrollY);
      await press(page, 'Enter', 'Space');
      assert.equal(await page.locator('.hidden-stems-panel.is-expanded').count(), 0);
      assert.equal(await page.locator('.card.is-flipped').count(), 0);
      if (profile.name === 'desktop') assert.equal(await page.evaluate(() => scrollY), scrolled);
      await press(page, 'ArrowRight', 'ArrowDown');
      const branch = page.locator('.card.branch[data-pillar="day"]');
      assert.equal(await branch.getAttribute('aria-controls'), 'hidden-stems-day');
      assert.equal(await branch.getAttribute('aria-expanded'), 'false');
      await press(page, 'Enter');
      assert.equal(await page.locator('#hidden-stems-day').evaluate((node) => node.classList.contains('is-expanded')), true);
      assert.equal(await branch.getAttribute('aria-expanded'), 'true');
      assert.equal(await page.locator('#display-switch button[data-display="characters"]').getAttribute('aria-pressed'), 'mixed');
      await press(page, 'Space');
      assert.equal(await page.locator('.hidden-stems-panel.is-expanded').count(), 0);
      assert.equal(await branch.getAttribute('aria-expanded'), 'false');
      // The display switch keeps the button's state in step.
      await page.locator('#display-switch button[data-display="hidden-stems"]').click();
      await settled(page);
      assert.equal(await branch.getAttribute('aria-expanded'), 'true');
    });

    check('T turns the card with focus, and only while a card has focus', async (page) => {
      await openChart(page, { lang: 'en' });
      await intoCards(page);
      await press(page, 'ArrowRight', 'ArrowRight', 'ArrowRight');
      const stem = page.locator('.card.stem[data-pillar="year"]');
      assert.equal(await page.getByRole('group', { name: 'Year 丁 Yin Fire' }).count(), 1);
      await press(page, 't');
      assert.equal(await stem.evaluate((node) => node.classList.contains('is-flipped')), true);
      assert.equal(await stem.getAttribute('aria-labelledby'), 'pillar-name-year card-year-stem-back');
      assert.equal(await page.getByRole('group', { name: 'Year Indirect Resource' }).count(), 1);
      assert.equal(await page.locator('#display-switch button[data-display="characters"]').getAttribute('aria-pressed'), 'mixed');
      // Held down, the key turns the card once.
      await page.keyboard.down('T');
      await page.keyboard.down('T');
      await page.keyboard.up('T');
      await settled(page);
      assert.equal(await stem.evaluate((node) => node.classList.contains('is-flipped')), false);
      assert.equal(await page.getByRole('group', { name: 'Year 丁 Yin Fire' }).count(), 1);
      // Elsewhere the letter is only a letter.
      await page.locator('button[data-context="roots"]').focus();
      await press(page, 't');
      assert.equal(await page.locator('.card.is-flipped').count(), 0);
      assert.equal(await page.getByRole('button', { name: 'Hour 申 Monkey Yang Metal' }).count(), 1);
    });

    if (profile.name === 'desktop') {
      check('a hint above the card with keyboard focus says its keys', async (page) => {
        await openChart(page, { lang: 'en' });
        const hint = page.locator('.card-hint');
        await intoCards(page);
        const place = async (selector) => {
          const [card, box] = await Promise.all([page.locator(selector).boundingBox(), hint.boundingBox()]);
          return { above: box.y + box.height <= card.y + 0.5, centred: Math.abs(box.x + box.width / 2 - (card.x + card.width / 2)) < 1 };
        };
        assert.equal(await hint.textContent(), 'T: Ten Gods');
        assert.deepEqual(await place('.card.stem[data-pillar="hour"]'), { above: true, centred: true });
        await press(page, 'ArrowDown');
        assert.equal(await hint.textContent(), 'Enter: hidden stems · T: Ten Gods');
        assert.deepEqual(await place('.card.branch[data-pillar="hour"]'), { above: true, centred: true });
        await press(page, TAB);
        assert.equal(await hint.isHidden(), true);
        // A click gives focus without the keyboard's hint: the pointer's own hint shows instead.
        await page.locator('.card.stem[data-pillar="month"]').click();
        assert.equal(await focused(page), 'month stem');
        assert.equal(await hint.textContent(), 'Press and hold: Ten Gods');
      });
    }

    check('Escape closes the open topic while a card has focus', async (page) => {
      await openChart(page, { lang: 'en' });
      await page.locator('button[data-context="roots"]').click();
      assert.equal(await topicOf(page), 'roots');
      await intoCards(page);
      await press(page, 'Escape');
      assert.equal(await page.locator('button[data-context="roots"]').getAttribute('aria-expanded'), 'false');
      assert.equal(await topicOf(page), null);
    });

    check('? lists the keys while the chart has focus, and Escape gives focus back', async (page) => {
      await openChart(page, { lang: 'en' });
      await page.locator('#relationships-topic').click();
      await intoCards(page);
      await press(page, 'ArrowDown', '?');
      assert.deepEqual(await openDialogs(page), ['keys-dialog']);
      const dialog = page.getByRole('dialog', { name: 'Keys' });
      assert.equal(await dialog.locator('.key-row').count(), 7);
      assert.deepEqual(await dialog.locator('dd').allTextContents(), ['Between pillars', 'Between stem and branch',
        "A branch's hidden stems", 'A card to its Ten Gods and back', 'Closes what is open', 'Commands', 'These keys']);
      assert.equal(await dialog.locator('.key-arrow .sr-only').first().textContent(), 'Left arrow');
      assert.equal(await page.evaluate(() => document.getElementById('keys-dialog').contains(document.activeElement)), true);
      await press(page, 'Escape');
      assert.deepEqual(await openDialogs(page), []);
      assert.equal(await focused(page), 'hour branch');
      // Escape in the dialog closed only the dialog.
      assert.equal(await page.locator('#relationships-topic').getAttribute('aria-expanded'), 'true');
      await press(page, '?');
      await page.locator('#keys-dialog [data-close-dialog]').click();
      assert.deepEqual(await openDialogs(page), []);
      assert.equal(await focused(page), 'hour branch');
      // Without focus in the chart, ? is only a character. Focus moved away as the dialog
      // closes stays away: nothing gives it back to the chart a moment later.
      await press(page, '?');
      await page.evaluate(async () => {
        document.querySelector('#keys-dialog [data-close-dialog]').click();
        document.activeElement.blur();
        await new Promise((resolve) => { setTimeout(resolve, 100); });
      });
      assert.equal(await page.evaluate(() => document.activeElement === document.body), true);
      await press(page, '?');
      assert.deepEqual(await openDialogs(page), []);
    });

    check('⌘K or Ctrl+K finds a command and runs it as its control would', async (page) => {
      await openChart(page, { lang: 'en' });
      await intoCards(page);
      const entries = await page.evaluate(() => history.length);
      const options = () => page.locator('.palette-option').evaluateAll((nodes) =>
        nodes.map((node) => node.textContent.replace(/\s+/g, ' ').trim()));
      await press(page, 'ControlOrMeta+k');
      assert.deepEqual(await openDialogs(page), ['command-palette']);
      assert.equal(await focused(page), 'palette-input');
      const all = await options();
      for (const expected of ['Chou month Topic', 'Relationships (1) Topic', 'Hour–Year · Stem combination Relationships',
        'Direct Wealth Roles', 'Hour · 壬申 Ren Shen Pillar', 'Ten Gods Show', 'FI Language', 'Evolution View',
        'Copy link Chart', 'Edit Chart', 'New chart Chart', 'Keys Chart']) {
        assert.ok(all.includes(expected), `${expected} in ${JSON.stringify(all)}`);
      }
      assert.equal(all.includes('EN Language'), false);
      // Words narrow the list; Enter runs the chosen one, as one step of the history.
      await page.keyboard.type('hour year');
      assert.deepEqual(await options(), ['Hour–Year · Stem combination Relationships']);
      await press(page, 'Enter');
      assert.deepEqual(await openDialogs(page), []);
      assert.equal(await topicOf(page), 'relationships/stem_combination:4:year-hour');
      assert.equal(await page.locator('.relationship-chip.is-active').count(), 1);
      assert.equal(await page.evaluate(() => history.length), entries + 1);
      assert.equal(await focused(page), 'hour stem');
      // Arrows choose among the matches; the display replaces the current entry.
      await press(page, 'ControlOrMeta+k');
      await page.keyboard.type('show');
      assert.deepEqual(await options(), ['Characters Show', 'Ten Gods Show', 'Hidden stems Show']);
      await press(page, 'ArrowDown', 'Enter');
      assert.equal(await page.locator('.card.is-flipped').count(), 8);
      assert.equal(await page.evaluate(() => history.length), entries + 1);
      // Nothing matches: nothing runs, and Escape closes the palette, not the topic.
      await press(page, 'ControlOrMeta+k');
      await page.keyboard.type('zzz');
      assert.deepEqual(await options(), []);
      assert.equal(await page.locator('#palette-empty').textContent(), 'No command matches');
      await press(page, 'Enter', 'Escape');
      assert.deepEqual(await openDialogs(page), []);
      assert.equal(await topicOf(page), 'relationships/stem_combination:4:year-hour');
      assert.equal(await focused(page), 'hour stem');
      // A command chosen with the pointer.
      await press(page, 'ControlOrMeta+k');
      await page.keyboard.type('chou');
      await page.locator('.palette-option').first().click();
      await settled(page);
      assert.equal(await topicOf(page), 'season');
      // Only while a chart is shown.
      await page.locator('#back-btn').click();
      await press(page, 'ControlOrMeta+k');
      assert.deepEqual(await openDialogs(page), []);
    });

    check('every control of the chart is reached by Tab, the cards at one stop', async (page) => {
      await openChart(page, { lang: 'en' });
      await page.locator('#display-switch button').first().focus();
      const reached = [];
      for (let presses = 0; presses < 40; presses += 1) {
        const inChart = await page.evaluate(() => document.getElementById('chart-view').contains(document.activeElement));
        if (!inChart) break;
        reached.push(await focused(page));
        await press(page, TAB);
      }
      assert.deepEqual(reached, ['Characters', 'Ten Gods', 'Hidden stems', 'Standard', 'Evolution', 'FI', 'EN',
        'copy-link-btn', 'copy-text-btn', 'back-btn', 'new-chart-btn', 'Chou month', 'Roots in 3 branches', 'Roles', 'relationships-topic',
        '壬申 Ren Shen', 'hour stem', '己丑 Ji Chou', '癸丑 Gui Chou', '丁卯 Ding Mao']);
    });
  });
}
