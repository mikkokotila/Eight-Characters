// The life grid: under the chart while the luck pillar shows, its five columns run on
// through the whole life, a row for each five years, a decade's stem phase above its
// branch phase (luck.js). Natal, there is none: the chart is as without luck pillars. The Luck
// column holds the decades, each a small pillar of its stem over its branch, and choosing
// a phase there chooses it everywhere. Under each natal character a mark shows each
// relationship the luck pillar forms with it, for as long as it acts: a stem's for its
// decade's stem phase, a branch's for the whole decade. A compact copy of the chart heads
// the grid and stays in sight while the grid scrolls by, with the chosen pair in its Luck
// column and a ring on each character the chosen phase's relationships touch. Pillars
// only folds the natal columns away, and the Luck column becomes the life path, a list.
(() => {
  const NATAL = ['hour', 'day', 'month', 'year'];
  const MEMBER_ORDER = [...NATAL, 'luck'];
  const PHASES = ['stem', 'branch'];
  const VIEWS = ['grid', 'pillars'];

  // `onChoose(path)` is told when a row is pressed, with its period as the address names
  // it: before, or <sequence>/<phase>.
  const create = ({ root, translate: t, escape: esc, onChoose }) => {
    const section = root.querySelector('#life');
    const meta = root.querySelector('#life-meta');
    const head = root.querySelector('#life-head');
    const body = root.querySelector('#life-body');
    const switcher = root.querySelector('#life-view');
    if (!section || !meta || !head || !body || !switcher || !onChoose) throw new Error('Life grid view is incomplete.');
    // What the grid draws: the luck pillars as luck.js reads them, the natal pillars as
    // the chart draws them, and how luck.js names years and characters.
    let life = null;
    // The line across the natal columns where today falls, moved to its row.
    let todayLine = null;
    // The grid with the chart's columns, or the pillars only: the reader's, from chart to chart.
    let view = 'grid';

    const pathOf = (choice) => (choice === 'before' ? 'before' : `${choice.sequence}/${choice.phase}`);
    const decadeOf = (sequence) => life.decades.find((decade) => decade.sequence === sequence);
    const ordered = (relationship) => [...relationship.members]
      .sort((a, b) => MEMBER_ORDER.indexOf(a.pillar) - MEMBER_ORDER.indexOf(b.pillar));
    // A relationship as the lists name it: its places, then its kind.
    const nameOf = (relationship) => `${ordered(relationship).map((m) => t('pillar_' + m.pillar)).join('–')} · ${t('relationship_' + relationship.kind)}`;

    // ── The head: the chart, compact, each pillar's stem beside its branch ──
    const mini = (part, char, pinyin, element) => `<span class="life-mini ${esc(element)}" data-part="${part}">
        <span class="life-mini-char" lang="zh-Hant">${esc(char)}</span>
        <span class="life-mini-name">${esc(pinyin)}</span>
      </span>`;
    const drawHead = () => {
      head.innerHTML = `${NATAL.map((pillar, index) => {
        const { stem, branch } = life.natal[index];
        return `<div class="life-head-cell" data-pillar="${pillar}">
          <span class="life-head-name">${esc(t('pillar_' + pillar))}</span>
          <span class="life-mini-pair">${mini('stem', stem.char, stem.pinyin, stem.element)}${mini('branch', branch.char, branch.pinyin, branch.element)}</span>
        </div>`;
      }).join('')}
        <div class="life-head-cell is-luck" data-pillar="luck">
          <span class="life-head-name">${esc(t('life_luck'))}</span>
          <span class="life-head-state"></span>
          <span class="life-mini-pair"></span>
        </div>`;
    };
    // The Luck column holds the period chosen: its pair, the stem set aside in the branch
    // phase. The natal characters that the chosen phase's relationships touch are ringed.
    const syncHead = (cursor) => {
      const decade = cursor === 'before' ? null : decadeOf(cursor.sequence);
      const cell = head.querySelector('.life-head-cell.is-luck');
      cell.querySelector('.life-head-state').textContent = decade === null ? t('luck_before') : t('luck_phase_' + cursor.phase);
      const pair = cell.querySelector('.life-mini-pair');
      const parts = decade === null ? '' : PHASES.map((part) => {
        const card = decade.cards[part];
        return mini(part, card.char, life.names(card.char), card.element);
      }).join('');
      if (pair.dataset.drawn !== parts) {
        pair.innerHTML = parts;
        pair.dataset.drawn = parts;
      }
      pair.querySelector('[data-part="stem"]')?.classList.toggle('is-resting', decade !== null && cursor.phase === 'branch');
      const ringed = new Set();
      if (decade !== null) {
        decade.interactions.filter((r) => r.phases.includes(cursor.phase)).forEach((r) => r.members
          .filter((m) => m.pillar !== 'luck').forEach((m) => ringed.add(`${m.pillar}:${r.component}`)));
      }
      head.querySelectorAll('.life-head-cell:not(.is-luck) .life-mini').forEach((node) => {
        node.classList.toggle('is-ringed', ringed.has(`${node.closest('[data-pillar]').dataset.pillar}:${node.dataset.part}`));
      });
    };

    // ── The body: the years before the first decade, then each decade in its direction's
    // group, as the ribbon groups them ──
    // A decade's marks, each where it acts, as fractions of the decade's height: a stem's
    // relationship in the stem phase, a branch's through the decade. When the stem phase
    // has marks of its own, the decade's stand in the branch phase, clear of them. A
    // phase is as tall as its marks need (--need slots), and never less than its height.
    const layout = (decade) => {
      const stems = decade.interactions.filter((r) => r.phases.length === 1);
      const whole = decade.interactions.filter((r) => r.phases.length === 2);
      const marks = [
        ...stems.map((r, index) => ({ r, to: 0.5, at: (0.5 * (index + 1)) / (stems.length + 1) })),
        ...whole.map((r, index) => ({
          r, to: 1, at: stems.length ? 0.5 + (0.5 * (index + 1)) / (whole.length + 1) : (index + 1) / (whole.length + 1),
        })),
      ];
      return { marks, need: Math.max(stems.length, whole.length) + 1 };
    };
    const decadeMarkup = (decade, row) => {
      const { marks, need } = layout(decade);
      const cells = Object.fromEntries(NATAL.map((pillar) => [pillar, { bars: new Set(), marks: '' }]));
      const links = [];
      marks.forEach(({ r, to, at }) => {
        const natal = ordered(r).filter((m) => m.pillar !== 'luck');
        const label = nameOf(r);
        const attrs = `data-kind="${esc(r.kind)}" data-lane="${r.component}" data-relationship="${esc(r.id)}" data-phases="${r.phases.join(' ')}"`;
        natal.forEach((m, index) => {
          cells[m.pillar].bars.add(`<span class="life-run" data-lane="${r.component}" style="--to: ${to}"></span>`);
          // The first natal member's mark names the characters, in the chart's order.
          cells[m.pillar].marks += `<span class="life-mark" ${attrs} style="--at: ${at}" title="${esc(label)}">
              <span class="relationship-mark"></span>${index === 0 ? `<b>${esc(ordered(r).map((x) => x.pinyin).join('-'))}</b>` : ''}</span>`;
        });
        if (natal.length > 1) {
          const first = NATAL.indexOf(natal[0].pillar);
          const last = NATAL.indexOf(natal[natal.length - 1].pillar);
          links.push(`<span class="life-link" aria-hidden="true" ${attrs} style="grid-column: ${first + 1} / ${last + 2}; --span: ${last - first + 1}; --at: ${at}"></span>`);
        }
      });
      return `<div class="life-row" data-life-row="${decade.sequence}" style="--row: ${row}; --need: ${need}">
          <div class="life-block" aria-hidden="true">${PHASES.map((phase) => `<span class="life-half" data-life-half="${decade.sequence}/${phase}"></span>`).join('')}</div>
          ${NATAL.map((pillar) => `<div class="life-cell" data-pillar="${pillar}" aria-hidden="true">${[...cells[pillar].bars].join('')}${cells[pillar].marks}</div>`).join('')}
          ${links.join('')}
          <div class="life-rail">${PHASES.map((phase) => phaseButton(decade, phase)).join('')}</div>
        </div>`;
    };
    // A phase as its row shows it: its character, named, the role it brings (a branch's
    // by its main qi) and whether that role is new to the chart, and its years.
    const phaseButton = (decade, phase) => {
      const card = decade.cards[phase];
      const brings = phase === 'stem' ? decade.visible : decade.hidden[0];
      const span = decade.phases[PHASES.indexOf(phase)];
      const age = phase === 'stem' ? decade.startAge : decade.startAge + 5;
      return `<button type="button" class="life-phase" data-life="${decade.sequence}/${phase}" data-part="${phase}"
          tabindex="-1" aria-controls="luck-detail" aria-expanded="false">
          <span class="life-tile ${esc(card.element)}" lang="zh-Hant">${esc(card.char)}</span>
          <span class="life-phase-name">${esc(life.names(card.char))}<span class="life-now">${esc(t('luck_today'))}</span></span>
          <span class="life-phase-role">${esc(t('ten_god_' + brings.ten_god))}${brings.new_to_chart ? `<span class="life-new"> · ${esc(t('life_new'))}</span>` : ''}</span>
          <span class="life-phase-years">${life.year(span.start)}<span class="life-phase-to">–${life.year(span.end)}</span><span class="life-phase-age"> · ${esc(t('life_age', { age }))}</span></span>
          <span class="life-phase-more">${esc(phase === 'stem' ? `${brings.polarity} ${t('element_' + brings.element)}` : branchMore(decade))}</span>
        </button>`;
    };
    // What the life path lists for a branch: the Day Master's stage on it, and its roots.
    const branchMore = (decade) => [
      t('life_stage', { stage: t('luck_stage_' + decade.stage) }),
      decade.roots.length ? t('life_roots', { roots: decade.roots.map((r) => `${r.pinyin} ${r.char}`).join(', ') }) : t('life_roots_none'),
    ].join(' · ');
    const beforeMarkup = () => `<div class="life-row is-before" data-life-row="before" style="--row: 1; --need: 1">
        <div class="life-block" aria-hidden="true"><span class="life-half" data-life-half="before"></span></div>
        <div class="life-rail">
          <button type="button" class="life-phase is-before" data-life="before" tabindex="-1" aria-controls="luck-detail" aria-expanded="false">
            <span class="life-tile"></span>
            <span class="life-phase-name">${esc(t('luck_before'))}<span class="life-now">${esc(t('luck_today'))}</span></span>
            <span class="life-phase-role">${esc(t('life_before_none'))}</span>
            <span class="life-phase-years">${life.year(life.before.start)}<span class="life-phase-to">–${life.year(life.before.end)}</span><span class="life-phase-age"> · ${esc(t('life_age', { age: `0–${life.startAge}` }))}</span></span>
            <span class="life-phase-more">${esc(t('life_before_natal'))}</span>
          </button>
        </div>
      </div>`;
    const drawBody = () => {
      const groups = [];
      life.decades.forEach((decade) => {
        const last = groups[groups.length - 1];
        if (last && last.direction === decade.direction[0]) last.decades.push(decade);
        else groups.push({ direction: decade.direction[0], season: decade.direction[1], decades: [decade] });
      });
      const rows = [beforeMarkup()];
      let row = 1;
      groups.forEach((group) => {
        row += 1;
        rows.push(`<div class="life-group" style="--row: ${row}">
            <span class="life-group-name">${esc(t('luck_group', { direction: t('luck_direction_' + group.direction), season: t('context_' + group.season) }))}</span>
            <span class="life-group-years">${life.year(group.decades[0].start)}–${life.year(group.decades[group.decades.length - 1].end)}</span>
          </div>`);
        group.decades.forEach((decade) => {
          row += 1;
          rows.push(decadeMarkup(decade, row));
        });
      });
      body.innerHTML = `<div class="life-lane" style="grid-row: 1 / ${row + 1}" aria-hidden="true"></div>${rows.join('')}`;
      todayLine = document.createElement('span');
      todayLine.className = 'life-today';
      todayLine.setAttribute('aria-hidden', 'true');
    };

    // A row as a screen reader hears it: names, not characters, and whether it is now.
    const labelOf = (path, nowPath) => {
      let label;
      if (path === 'before') label = t('luck_before_label', { age: life.startAge });
      else {
        const [sequence, phase] = path.split('/');
        const decade = decadeOf(Number(sequence));
        const span = decade.phases[PHASES.indexOf(phase)];
        label = t('life_phase_label', {
          names: life.names(decade.chars), phase: t('luck_phase_' + phase), from: life.year(span.start), to: life.year(span.end),
        });
      }
      return path === nowPath ? t('luck_chip_today', { label }) : label;
    };

    // Where today falls: its row, and how far down it, from 0 to 1.
    const todayAt = (now) => {
      const when = new Date();
      if (now === 'before') return { row: 'before', at: (when - life.before.start) / (life.before.end - life.before.start) };
      const decade = decadeOf(now.sequence);
      const index = PHASES.indexOf(now.phase);
      const span = decade.phases[index];
      return { row: String(decade.sequence), at: (index + (when - span.start) / (span.end - span.start)) / 2 };
    };

    // The grid shows while the luck pillar does. What is chosen and what is now, drawn in
    // place: the rows stay the same elements, so focus and a reader's place stay on them.
    // The rows take one tab stop, as the ribbon's chips do: the chosen period's row.
    const sync = ({ cursor, shown, open, now }) => {
      if (life === null) return;
      section.classList.toggle('hidden', !shown);
      if (!shown) return;
      const chosen = pathOf(cursor);
      const nowPath = now === null ? null : pathOf(now);
      body.querySelectorAll('[data-life]').forEach((button) => {
        const path = button.dataset.life;
        const on = path === chosen;
        button.classList.toggle('is-chosen', on);
        button.classList.toggle('is-now', path === nowPath);
        button.setAttribute('aria-expanded', String(open && on));
        button.setAttribute('aria-label', labelOf(path, nowPath));
        button.tabIndex = on ? 0 : -1;
      });
      body.querySelectorAll('.life-half').forEach((half) => half.classList.toggle('is-chosen', half.dataset.lifeHalf === chosen));
      // The chosen decade's pair as the fifth pillar stands: in the branch phase its stem
      // is set aside, and the marks of what rests until the other phase grow quiet.
      const decade = cursor !== 'before' ? cursor : null;
      body.querySelectorAll('.life-phase[data-part="stem"]').forEach((button) => {
        button.classList.toggle('is-resting', decade !== null && button.dataset.life === `${decade.sequence}/stem` && decade.phase === 'branch');
      });
      body.querySelectorAll('.life-row[data-life-row]').forEach((row) => {
        const here = decade !== null && row.dataset.lifeRow === String(decade.sequence);
        row.querySelectorAll('.life-mark, .life-link').forEach((mark) => {
          mark.classList.toggle('is-quiet', here && !mark.dataset.phases.split(' ').includes(decade.phase));
        });
      });
      if (now === null) todayLine.remove();
      else {
        const { row, at } = todayAt(now);
        todayLine.style.setProperty('--at', String(at));
        body.querySelector(`.life-row[data-life-row="${row}"]`).append(todayLine);
      }
      syncHead(cursor);
    };

    // The grid with the chart's columns, or the pillars only.
    const setView = (next) => {
      if (!VIEWS.includes(next)) throw new Error(t('luck_error'));
      view = next;
      section.classList.toggle('is-only', view === 'pillars');
      switcher.querySelectorAll('[data-life-view]').forEach((button) => {
        button.setAttribute('aria-pressed', String(button.dataset.lifeView === view));
      });
    };
    switcher.addEventListener('click', (event) => {
      const button = event.target.closest('[data-life-view]');
      if (button) setView(button.dataset.lifeView);
    });

    // The rows: one tab stop, the arrows between them, Home and End to either end.
    body.addEventListener('click', (event) => {
      const button = event.target.closest('[data-life]');
      if (!button) return;
      onChoose(button.dataset.life);
      button.focus();
    });
    body.addEventListener('keydown', (event) => {
      const button = event.target.closest('[data-life]');
      if (!button || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const buttons = [...body.querySelectorAll('[data-life]')];
      const at = buttons.indexOf(button);
      const to = { ArrowUp: at - 1, ArrowDown: at + 1, Home: 0, End: buttons.length - 1 }[event.key];
      if (to === undefined) return;
      event.preventDefault();
      const next = buttons[Math.max(0, Math.min(buttons.length - 1, to))];
      buttons.forEach((node) => { node.tabIndex = node === next ? 0 : -1; });
      next.focus();
    });

    // `data` is the luck pillars as luck.js reads them, with the natal pillars and luck.js's
    // ways of naming: { decades, before, startAge, natal, year, names }. Null: no grid.
    // Drawn, it shows when sync says the luck pillar does.
    const render = (data) => {
      life = data;
      if (life === null) {
        section.classList.add('hidden');
        meta.textContent = '';
        head.innerHTML = '';
        body.innerHTML = '';
        todayLine = null;
        return;
      }
      if (!Array.isArray(life.natal) || life.natal.length !== NATAL.length) throw new Error(t('luck_error'));
      meta.textContent = t('life_meta', {
        count: life.decades.length, age: life.startAge,
        from: life.year(life.decades[0].start), to: life.year(life.decades[life.decades.length - 1].end),
      });
      drawHead();
      drawBody();
      setView(view);
    };
    // The row of a period, for focus to come back to.
    const rowOf = (choice) => body.querySelector(`[data-life="${pathOf(choice)}"]`);
    // Whether a node is in the grid, as focus is when a key opens a page from it.
    const holds = (node) => node !== null && section.contains(node);
    return { render, sync, rowOf, holds, setView, view: () => view };
  };

  window.EC_LIFE = { create };
})();
