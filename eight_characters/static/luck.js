// The luck pillars of a chart with a gender: a ribbon of the decades under the chart's
// topics, the chosen period standing in the chart as a fifth pillar, and its page in the
// panel. Each decade is a stem phase, its first five years, and a branch phase, its last
// five (luck_pillars.py); a choice is a phase, and a decade opens at today's phase when
// today falls in it. The ribbon groups the decades by the direction their branch
// travels: San Ming Tong Hui judges the luck cycle by its travel east, south, west or
// north.
//
// One choice drives it all: the ribbon, the fifth pillar, the page and the keys show
// and move the same period. The luck pillar is shown or hidden as a whole (L); hidden,
// its column keeps its place and its size, so showing it moves nothing on the chart.
(() => {
  const STEMS = '甲乙丙丁戊己庚辛壬癸';
  const BRANCHES = '子丑寅卯辰巳午未申酉戌亥';
  // As in eight_characters/data.py; a unit test keeps the two the same.
  const PINYIN = {
    甲: 'Jia', 乙: 'Yi', 丙: 'Bing', 丁: 'Ding', 戊: 'Wu', 己: 'Ji', 庚: 'Geng', 辛: 'Xin', 壬: 'Ren', 癸: 'Gui',
    子: 'Zi', 丑: 'Chou', 寅: 'Yin', 卯: 'Mao', 辰: 'Chen', 巳: 'Si', 午: 'Wu', 未: 'Wei', 申: 'Shen', 酉: 'You',
    戌: 'Xu', 亥: 'Hai',
  };
  // The direction each branch travels, with its season (day_master_context.SEASON_GROUPS).
  const DIRECTION = {
    寅: ['east', 'spring'], 卯: ['east', 'spring'], 辰: ['east', 'spring'],
    巳: ['south', 'summer'], 午: ['south', 'summer'], 未: ['south', 'summer'],
    申: ['west', 'autumn'], 酉: ['west', 'autumn'], 戌: ['west', 'autumn'],
    亥: ['north', 'winter'], 子: ['north', 'winter'], 丑: ['north', 'winter'],
  };
  const PHASES = ['stem', 'branch'];
  const ELEMENTS = ['wood', 'fire', 'earth', 'metal', 'water'];
  const LINES = ['B', 'L'];
  // The visible characters counted: the natal eight, and the luck pillar's that act.
  const CHARACTERS = { natal: 8, stem: 10, branch: 9 };
  const total = (elements) => ELEMENTS.reduce((sum, e) => sum + elements[e], 0);
  // The phase rule, stem_then_branch_v1: what the stem brings acts in the stem phase only,
  // and what the branch brings acts in both.
  const ruled = (component, phases) => Array.isArray(phases)
    && phases.join() === (component === 'stem' ? ['stem'] : PHASES).join();
  const DISPLAY_ORDER = ['hour', 'day', 'month', 'year', 'luck'];
  // Drawn, as the page's other arrows are: the page fonts have no arrow glyphs.
  const CHEVRON = (points) => `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="${points}"></polyline></svg>`;
  const EXPAND_HINT = `<svg class='branch-expand-hint' aria-hidden='true' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>`;

  // `pillars` is the chart's grid, where the luck pillar stands as its fifth column, and
  // `onCards(column, focused, redrawn)` is told whenever the column changes, with the
  // part of it that had focus ('stem', 'branch', 'identity' or null) and whether its
  // cards were drawn anew.
  const create = ({ root, pillars, translate: t, escape: esc, spot, locale, beforeSelect, onCards }) => {
    const ribbon = root.querySelector('#luck-ribbon');
    const detail = root.querySelector('#luck-detail');
    const status = root.querySelector('#luck-status');
    const switcher = root.querySelector('#luck-switch');
    if (!ribbon || !detail || !status || !switcher || !pillars || !spot || !onCards) throw new Error('Luck pillar view is incomplete.');
    let luck = null;
    // The period chosen ('before' or a decade's phase), whether the luck pillar stands in
    // the chart, and whether the period's page is open. An open page shows the period
    // chosen, which then stands in the chart.
    let cursor = null;
    let shown = false;
    let open = false;
    let column = null;

    const fail = () => { throw new Error(t('luck_error')); };
    const require = (condition) => { if (!condition) fail(); };
    const instant = (text) => {
      require(typeof text === 'string' && text.endsWith('Z'));
      const value = new Date(text);
      require(!Number.isNaN(value.getTime()));
      return value;
    };
    const names = (chars) => [...chars].map((char) => PINYIN[char]).join(' ');
    const date = (when) => new Intl.DateTimeFormat(locale(), { dateStyle: 'medium', timeZone: luck.timezone }).format(when);
    const year = (when) => Number(new Intl.DateTimeFormat('en', { year: 'numeric', timeZone: luck.timezone }).format(when));

    // A card's face as the chart draws it (luck_chart), checked against the pillar.
    const readCard = (card, char, component) => {
      require(card?.char === char && ELEMENTS.includes(card.element) && Array.isArray(card.lines)
        && card.lines.length === (component === 'stem' ? 3 : 6) && card.lines.every((line) => LINES.includes(line)));
      require(component === 'stem' ? typeof card.label === 'string' && card.label !== ''
        : typeof card.animal_name === 'string' && card.animal_name !== '' && typeof card.element_label === 'string' && card.element_label !== '');
      return card;
    };

    // The API's luck pillars, their context and their cards, read strictly: a decade the
    // page cannot stand behind is an error, not a gap.
    const read = (pillars, context, cards, chart) => {
      require(pillars && context && context.policy === 'luck_context_v1' && pillars.phase_rule === 'stem_then_branch_v1');
      require(['forward', 'backward'].includes(pillars.direction));
      require(Array.isArray(pillars.pillars) && pillars.pillars.length > 0
        && Array.isArray(context.decades) && context.decades.length === pillars.pillars.length
        && Array.isArray(cards?.pillars) && cards.pillars.length === pillars.pillars.length);
      require(ELEMENTS.every((e) => Number.isInteger(context.natal_counts?.elements?.[e]))
        && total(context.natal_counts.elements) === CHARACTERS.natal);
      const decades = pillars.pillars.map((pillar, index) => {
        const stem = pillar?.stem?.chinese;
        const branch = pillar?.branch?.chinese;
        require(pillar.sequence === index + 1 && STEMS.includes(stem) && BRANCHES.includes(branch)
          && stem.length === 1 && branch.length === 1);
        const found = context.decades[index];
        const drawn = cards.pillars[index];
        require(found.sequence === pillar.sequence && drawn.sequence === pillar.sequence
          && Array.isArray(pillar.phases) && pillar.phases.length === 2);
        const phases = pillar.phases.map((phase, at) => {
          require(phase.phase === PHASES[at]);
          return { phase: phase.phase, start: instant(phase.start_utc), end: instant(phase.end_utc) };
        });
        const start = instant(pillar.start_utc);
        const end = instant(pillar.end_utc);
        require(phases[0].start.getTime() === start.getTime() && phases[1].end.getTime() === end.getTime()
          && phases[0].end.getTime() === phases[1].start.getTime() && start < phases[0].end && phases[1].start < end);
        require(Number.isInteger(pillar.start_age?.years) && Number.isInteger(pillar.end_age?.years));
        const [visible, ...hidden] = found.occurrences;
        require(visible?.component === 'stem' && visible.char === stem && ruled('stem', visible.phases) && hidden.length > 0
          && hidden.every((e) => e.component === 'hidden_stem' && e.branch === branch && ruled('branch', e.phases)));
        require(Array.isArray(found.roots) && found.roots.every((r) => r.branch === branch && ruled('branch', r.phases)));
        require(Number.isInteger(found.day_master_stage) && found.day_master_stage >= 1 && found.day_master_stage <= 12);
        // Each phase counts the natal characters and adds the luck pillar's.
        PHASES.forEach((phase) => {
          const counts = found.counts?.[phase];
          require(counts && ELEMENTS.every((e) => Number.isInteger(counts.elements?.[e])
            && counts.elements[e] >= context.natal_counts.elements[e]));
          require(total(counts.elements) === CHARACTERS[phase]);
        });
        require(Array.isArray(found.interactions) && Array.isArray(found.absorbed));
        found.interactions.forEach((r) => require(['stem', 'branch'].includes(r.component)
          && r.members.some((m) => m.pillar === 'luck') && ruled(r.component, r.phases)));
        // A natal half is taken in, for the decade, by a whole the luck pillar forms.
        found.absorbed.forEach((a) => require(typeof a.id === 'string' && Array.isArray(a.by) && a.by.length > 0
          && a.by.every((id) => found.interactions.some((r) => r.id === id)) && ruled('branch', a.phases)));
        return {
          sequence: pillar.sequence,
          stem,
          branch,
          chars: stem + branch,
          start,
          end,
          startAge: pillar.start_age.years,
          endAge: pillar.end_age.years,
          phases,
          visible,
          hidden,
          stage: found.day_master_stage,
          roots: found.roots,
          interactions: found.interactions,
          absorbed: found.absorbed,
          counts: found.counts,
          direction: DIRECTION[branch],
          cards: { stem: readCard(drawn.stem, stem, 'stem'), branch: readCard(drawn.branch, branch, 'branch') },
        };
      });
      decades.slice(1).forEach((decade, index) => require(decade.start.getTime() === decades[index].end.getTime()));
      const before = { start: instant(pillars.pre_luck_period.start_utc), end: instant(pillars.pre_luck_period.end_utc) };
      require(before.end.getTime() === decades[0].start.getTime());
      require(['years', 'months', 'days'].every((part) => Number.isInteger(pillars.start_age?.[part]))
        && pillars.start_age.years === decades[0].startAge);
      require(typeof pillars.uncertainty?.boundary_ambiguous === 'boolean');
      return {
        decades,
        before,
        direction: pillars.direction,
        startAge: pillars.start_age,
        // A birth within the allowance of a jie: the dates are nominal (the chart's notice).
        nominal: pillars.uncertainty.boundary_ambiguous,
        natalElements: context.natal_counts.elements,
        chart,
      };
    };

    // Where a moment falls: 'before', a decade's phase, or null before the birth (a birth
    // still to come) or after the last decade.
    const phaseAt = (when) => {
      if (when < luck.before.start) return null;
      if (when < luck.before.end) return 'before';
      for (const decade of luck.decades) {
        if (when < decade.end) return { sequence: decade.sequence, phase: when < decade.phases[1].start ? 'stem' : 'branch' };
      }
      return null;
    };
    const today = () => phaseAt(new Date());
    const toCome = () => new Date() < luck.before.start;
    // Every choice in order, the period before the first decade first.
    const steps = () => ['before', ...luck.decades.flatMap((d) => PHASES.map((phase) => ({ sequence: d.sequence, phase })))];
    const same = (a, b) => (a === 'before' || b === 'before' ? a === b
      : Boolean(a && b) && a.sequence === b.sequence && a.phase === b.phase);
    const decadeOf = (choice) => luck.decades.find((d) => d.sequence === choice.sequence);
    const pathOf = (choice) => (choice === 'before' ? 'before' : `${choice.sequence}/${choice.phase}`);
    const topicOf = (choice) => `luck/${pathOf(choice)}`;
    const keyOf = (choice) => (choice === 'before' ? 'before' : String(choice.sequence));
    // Where the luck pillar starts: today's phase, else the end today lies beyond.
    const home = () => today() ?? (toCome() ? 'before' : { sequence: luck.decades.length, phase: 'branch' });
    // A path as the address names it, before or <sequence>/<phase>, as a choice; null when
    // this chart has no such period.
    const choiceOf = (path) => {
      if (path === 'before') return 'before';
      const [sequence, phase] = path.split('/');
      const choice = { sequence: Number(sequence), phase };
      return PHASES.includes(phase) && decadeOf(choice) ? choice : null;
    };

    // A period as its chip names it, a decade by its names, its years and the age it
    // starts at, and whether today falls in it.
    const chipLabel = (key, now) => {
      const decade = key === 'before' ? null : luck.decades[Number(key) - 1];
      const label = decade === null
        ? t('luck_before_label', { age: luck.startAge.years })
        : t('luck_chip_label', { names: names(decade.chars), from: year(decade.start), to: year(decade.end), age: decade.startAge });
      return now !== null && keyOf(now) === key ? t('luck_chip_today', { label }) : label;
    };

    // The chip a reader is at, the chosen period's or else today's, is kept in sight: the
    // track scrolls to centre it only when it is out of view.
    const reveal = () => {
      const track = ribbon.querySelector('.luck-track');
      const chip = ribbon.querySelector('.luck-chip.is-selected') ?? ribbon.querySelector('.luck-chip.is-today');
      if (!track || !chip || track.clientWidth === 0) return;
      const room = track.getBoundingClientRect();
      const box = chip.getBoundingClientRect();
      if (box.left >= room.left && box.right <= room.right) return;
      track.scrollLeft += (box.left + box.right - room.left - room.right) / 2;
    };
    // The track has its width once the chart is shown, and a new one with the page's.
    new ResizeObserver(reveal).observe(ribbon);

    // What is chosen and what is today, on the ribbon. Its chips stay the same elements,
    // so focus and a reader's place stay on them. The chips take one tab stop, as the
    // cards do, and arrows move between them: the chosen period's chip has it while the
    // luck pillar shows, else today's, else the chip at the end today lies beyond.
    const syncRibbon = () => {
      const now = today();
      const stop = keyOf(shown ? cursor : home());
      ribbon.querySelectorAll('.luck-chip').forEach((chip) => {
        const key = chip.dataset.luck;
        const on = shown && keyOf(cursor) === key;
        const isToday = now !== null && keyOf(now) === key;
        chip.classList.toggle('is-selected', on);
        chip.classList.toggle('is-today', isToday);
        chip.setAttribute('aria-expanded', String(open && on));
        chip.setAttribute('aria-label', chipLabel(key, now));
        chip.tabIndex = key === stop ? 0 : -1;
        chip.querySelectorAll('.luck-chip-phases i').forEach((bar) => {
          bar.classList.toggle('is-chosen', on && cursor.phase === bar.dataset.phase);
          bar.toggleAttribute('data-today', isToday && now.phase === bar.dataset.phase);
        });
      });
      ribbon.querySelector('[data-luck-today]').disabled = now === null || (open && same(now, cursor));
      switcher.querySelectorAll('[data-luck-show]').forEach((button) => {
        button.setAttribute('aria-pressed', String((button.dataset.luckShow === 'on') === shown));
      });
      reveal();
    };

    // The ribbon of a chart, drawn once.
    const drawRibbon = () => {
      const groups = [];
      luck.decades.forEach((decade) => {
        const last = groups[groups.length - 1];
        if (last && last.direction === decade.direction[0]) last.decades.push(decade);
        else groups.push({ direction: decade.direction[0], season: decade.direction[1], decades: [decade] });
      });
      const chip = (key, content) => `<button type="button" class="luck-chip${key === 'before' ? ' is-before' : ''}" data-luck="${key}" aria-controls="luck-detail">
          <span class="luck-today-dot" aria-hidden="true"></span>${content}</button>`;
      ribbon.innerHTML = `
        <span id="luck-ribbon-label" class="luck-ribbon-label">${esc(t('luck_ribbon_label'))}</span>
        <button type="button" class="luck-step" data-luck-step="-1" aria-label="${esc(t('luck_previous'))}">${CHEVRON('15 6 9 12 15 18')}</button>
        <div class="luck-track">
          <div class="luck-group">
            <span class="luck-direction">${esc(t('luck_before'))}</span>
            <div class="luck-chips">${chip('before', `0–${luck.startAge.years}`)}</div>
          </div>
          ${groups.map((group) => `
          <div class="luck-group" data-direction="${group.direction}">
            <span class="luck-direction">${esc(t('luck_group', { direction: t('luck_direction_' + group.direction), season: t('context_' + group.season) }))}</span>
            <div class="luck-chips">${group.decades.map((decade) => chip(String(decade.sequence), `
              <span class="luck-chip-chars" lang="zh-Hant" aria-hidden="true">${decade.chars}</span>
              <span class="luck-chip-names" aria-hidden="true">${esc(names(decade.chars))}</span>
              <span class="luck-chip-age" aria-hidden="true">${decade.startAge}</span>
              <span class="luck-chip-phases" aria-hidden="true">${PHASES.map((phase) => `<i data-phase="${phase}"></i>`).join('')}</span>`)).join('')}</div>
          </div>`).join('')}
        </div>
        <button type="button" class="luck-step" data-luck-step="1" aria-label="${esc(t('luck_next'))}">${CHEVRON('9 6 15 12 9 18')}</button>
        <button type="button" class="luck-today" data-luck-today>${esc(t('luck_today'))}</button>`;
      ribbon.classList.remove('hidden');
    };

    // ── The fifth pillar ──
    // Its cards are drawn as the natal cards are (app.js renderChart), from luck_chart,
    // with the Ten Gods and hidden stems of the luck context. In the stem phase the stem
    // leads and the branch acts too; in the branch phase the branch leads and the stem is
    // set aside. Hidden, or before the first decade, the column keeps the first decade's
    // or the chosen decade's cards laid out unseen, so nothing on the chart moves.
    const lines = (codes) => codes.map((code) => `<div class='${code}'></div>`).join('');
    const hiddenItem = (e, label) => `
      <div class='hidden-stem-item' data-hidden-stem='${esc(e.char)}'>
        <span class='hidden-stem-dot ${esc(e.element)}'></span>
        <span class='hidden-stem-label'>${esc(label)}</span>
        <span class='hidden-stem-type'>${esc(t('qi_' + e.qi_type))}</span>
      </div>`;
    const columnState = () => (!shown ? 'off' : cursor === 'before' ? 'none' : 'on');
    const cardsMarkup = (decade) => {
      const { stem, branch } = decade.cards;
      return `
        <div class='card ${stem.element} stem' data-pillar='luck' data-char='${esc(stem.char)}'
          role='group' tabindex='-1' aria-keyshortcuts='T' aria-labelledby='pillar-name-luck card-luck-stem-front'>
          <div class='card-inner'>
            <div class='card-face card-front' id='card-luck-stem-front'>
              <div class='glyph' lang='zh-Hant'>${esc(stem.char)}</div>
              <div class='gua'>${lines(stem.lines)}</div>
              <div class='element-name'>${esc(stem.label)}</div>
            </div>
            <div class='card-face card-back' id='card-luck-stem-back'>
              <div class='ten-god-name'>${esc(t('ten_god_' + decade.visible.ten_god))}</div>
            </div>
          </div>
        </div>
        <div class='card ${branch.element} branch' data-pillar='luck' data-char='${esc(branch.char)}'
          role='button' tabindex='-1' aria-expanded='false' aria-controls='hidden-stems-luck' aria-keyshortcuts='Enter Space T'
          aria-labelledby='pillar-name-luck card-luck-branch-front'>
          <div class='card-inner'>
            <div class='card-face card-front' id='card-luck-branch-front'>
              <div class='glyph' lang='zh-Hant'>${esc(branch.char)}</div>
              <div class='gua'>${lines(branch.lines)}</div>
              <div class='animal-name'>${esc(branch.animal_name)}</div>
              <div class='animal-element'>${esc(branch.element_label)}</div>
              ${EXPAND_HINT}
            </div>
            <div class='card-face card-back' id='card-luck-branch-back'>
              <div class='ten-god-list'>${decade.hidden.map((e) => hiddenItem(e, t('ten_god_' + e.ten_god))).join('')}</div>
              ${EXPAND_HINT}
            </div>
          </div>
        </div>
        <div class='hidden-stems-panel ${branch.element}' data-pillar='luck' id='hidden-stems-luck'>
          <div class='hidden-stems-list'>${decade.hidden.map((e) => hiddenItem(e, `${e.polarity} ${t('element_' + e.element)}`)).join('')}</div>
        </div>`;
    };
    const drawColumn = () => {
      const state = columnState();
      const decade = state === 'on' || (state === 'off' && cursor !== 'before') ? decadeOf(cursor) : luck.decades[0];
      const mark = state === 'on'
        ? t(`luck_mark_${cursor.phase}`, { year: year(cursor.phase === 'stem' ? decade.phases[0].end : decade.end) })
        : state === 'none' ? t('luck_mark_before', { age: luck.startAge.years }) : '';
      const poetic = state === 'none'
        ? `${year(luck.before.start)}–${year(luck.before.end)}`
        : t('luck_column_poetic', { n: decade.sequence, count: luck.decades.length, from: year(decade.start), to: year(decade.end) });
      // The part of the column that had focus, for focus to come back to it when redrawn.
      const active = document.activeElement;
      const focused = column?.contains(active)
        ? (active.matches('.card') ? (active.classList.contains('stem') ? 'stem' : 'branch') : 'identity')
        : null;
      if (column === null || !column.isConnected) {
        column = document.createElement('div');
        column.className = 'pillar is-luck';
        column.dataset.pillar = 'luck';
        pillars.append(column);
      }
      // The cards are drawn for a decade, and kept as they are while it stays: hiding and
      // showing the luck pillar leaves a card turned or a branch opened by hand as it was.
      const redrawn = column.dataset.decade !== String(decade.sequence) || column.querySelector('.pillar-cards') === null;
      column.dataset.luckState = state;
      column.dataset.decade = decade.sequence;
      column.inert = state === 'off';
      if (redrawn) column.innerHTML = `<div class='pillar-header'></div><div class='pillar-cards'>${cardsMarkup(decade)}</div>`;
      column.querySelector('.pillar-header').innerHTML = `
          <div class='pillar-label'>
            <span class='pillar-plain' id='pillar-name-luck'>${esc(t('pillar_luck'))}</span>
            <span class='pillar-poetic'>${esc(poetic)}</span>
          </div>
          <button type='button' class='luck-identity' data-luck-identity aria-expanded='${open}' aria-controls='luck-detail'
            ${state === 'none' ? `aria-label='${esc(t('luck_title_before'))}'` : ''}>
            <span class='pillar-chars' lang='zh-Hant'${state === 'none' ? ' aria-hidden="true"' : ''}>${decade.chars}</span>
            <span class='pillar-pinyin'>${esc(state === 'none' ? t('luck_before') : names(decade.chars))}</span>
          </button>
          <p class='pillar-mark luck-mark'>${esc(mark)}</p>`;
      // In the stem phase the stem leads and the branch acts too; in the branch phase the
      // branch leads and the stem is set aside. Hidden, the stem's room says what brings it
      // back. Before the first decade there are no cards to read: they only keep the room.
      const phase = state === 'on' ? cursor.phase : null;
      column.querySelectorAll('.pillar-cards > .card').forEach((card) => {
        const component = card.classList.contains('stem') ? 'stem' : 'branch';
        const part = phase === null ? '' : component === phase ? 'leading' : phase === 'stem' ? 'acting' : 'resting';
        card.dataset.luckPart = part;
        card.inert = state !== 'on';
        card.querySelectorAll(':scope > .luck-set-aside, :scope > .luck-ghost').forEach((note) => note.remove());
        if (part === 'resting') card.insertAdjacentHTML('afterbegin', `<span class='luck-set-aside'>${esc(t('luck_set_aside'))}</span>`);
        if (state === 'off' && component === 'stem') card.insertAdjacentHTML('afterbegin', `<span class='luck-ghost'>${esc(t('luck_ghost_off'))}</span>`);
      });
      onCards(column, focused, redrawn);
      drawArcs();
    };
    const removeColumn = () => {
      column?.remove();
      column = null;
      pillars.querySelectorAll('.luck-arcs').forEach((band) => band.remove());
      pillars.classList.remove('has-luck', 'is-luck-shown');
    };

    // ── The luck pillar's arcs ──
    // Its relationships, drawn as the natal ones are (relationships.js), in the outer
    // band: above the stems' arcs and below the branches'. Every one ends on the luck
    // pillar, so the narrower stands lower. A relationship of the families the canon
    // adds joins an arc over the same columns as a strand. On a natal card their feet
    // stand beyond the natal arcs' feet, so showing them moves no natal foot. A stem's
    // relationship rests in the branch phase, and its arc recedes.
    const OWN_ARC = ['stem_combination', 'branch_combination', 'branch_clash', 'harmony_frame'];
    const LUCK_LEVELS = 4;
    const LUCK_STRANDS = 3;
    const arcsFor = (relationships, component) => {
      const slots = [];
      const strands = relationships.map((relationship) => {
        const columns = relationship.members.map((m) => DISPLAY_ORDER.indexOf(m.pillar)).sort((a, b) => a - b);
        const from = columns[0];
        const to = columns[columns.length - 1];
        let slot = OWN_ARC.includes(relationship.kind) ? null : slots.find((other) => other.from === from && other.to === to);
        if (!slot) {
          slot = { from, to, strands: [] };
          slots.push(slot);
        }
        const strand = { relationship, columns, from, to, slot, strand: slot.strands.length, feet: {} };
        slot.strands.push(strand);
        return strand;
      });
      [...slots].sort((a, b) => (a.to - a.from) - (b.to - b.from) || a.from - b.from).forEach((slot, index) => { slot.level = index + 1; });
      require(slots.length <= LUCK_LEVELS && slots.every((slot) => slot.strands.length <= LUCK_STRANDS));
      const height = (strand) => strand.slot.level - strand.strand / LUCK_STRANDS;
      // The feet on one card, left to right, as the natal arcs order theirs: arcs from the
      // left, lowest first; a triple's middle member; arcs to the right, highest first.
      // Separate arcs' feet stand a spread apart, the strands of one arc half a spread.
      DISPLAY_ORDER.forEach((pillar, column) => {
        const feet = [
          ...strands.filter((s) => s.to === column).sort((a, b) => height(a) - height(b)).map((s) => [s, 'to']),
          ...strands.filter((s) => s.columns.length === 3 && s.columns[1] === column).map((s) => [s, 'middle']),
          ...strands.filter((s) => s.from === column).sort((a, b) => height(b) - height(a)).map((s) => [s, 'from']),
        ];
        const at = [];
        feet.forEach(([strand], index) => {
          at.push(index === 0 ? 0 : at[index - 1] + (feet[index - 1][0].slot === strand.slot ? 0.5 : 1));
        });
        const edge = pillar === 'luck' ? null : luck.chart.feetEdge(component, pillar);
        const start = pillar === 'luck' ? -(at.length ? at[at.length - 1] / 2 : 0) : edge === null ? 0 : edge + 1;
        feet.forEach(([strand, end], index) => { strand.feet[end] = start + at[index]; });
      });
      return strands;
    };
    const arcMarkup = (arc, phase) => {
      const style = [
        `grid-column: ${arc.from + 1} / ${arc.to + 2}`, `--span: ${arc.to - arc.from}`, `--level: ${arc.slot.level}`,
        `--strand: ${arc.strand}`, `--foot-from: ${arc.feet.from}`, `--foot-to: ${arc.feet.to}`,
      ].join('; ');
      // A triple's middle member stands under the arc where it is (at) of the way across;
      // half an ellipse is sqrt(1 - x²) of its rise there, x from -1 to 1.
      const at = arc.columns.length === 3 ? (arc.columns[1] - arc.from) / (arc.to - arc.from) : null;
      const middle = at === null ? ''
        : `<span class="relationship-arc-foot" style="--at: ${at}; --reach: ${Math.sqrt(1 - (2 * at - 1) ** 2)}; --foot: ${arc.feet.middle}"></span>`;
      const rises = arc.relationship.component === 'branch'
        ? '<span class="relationship-arc-rise is-from"></span><span class="relationship-arc-rise is-to"></span>' : '';
      const resting = !arc.relationship.phases.includes(phase);
      return `<span class="relationship-arc${resting ? ' is-resting' : ''}" data-arc-kind="${esc(arc.relationship.kind)}" data-relationship-id="${esc(arc.relationship.id)}" style="${style}">
        <span class="relationship-arc-line"></span>${rises}${middle}
      </span>`;
    };
    const drawArcs = () => {
      pillars.querySelectorAll('.luck-arcs').forEach((band) => band.remove());
      const on = columnState() === 'on';
      pillars.classList.toggle('is-luck-shown', on);
      if (!on) return;
      const decade = decadeOf(cursor);
      ['stem', 'branch'].forEach((component) => {
        const relationships = decade.interactions.filter((relationship) => relationship.component === component);
        if (relationships.length === 0) return;
        const band = document.createElement('div');
        band.className = 'luck-arcs';
        band.dataset.component = component;
        band.setAttribute('aria-hidden', 'true');
        band.innerHTML = arcsFor(relationships, component).map((arc) => arcMarkup(arc, cursor.phase)).join('');
        pillars.append(band);
      });
    };

    // ── The page ──
    const memberLabel = (relationship) => [...relationship.members]
      .sort((a, b) => DISPLAY_ORDER.indexOf(a.pillar) - DISPLAY_ORDER.indexOf(b.pillar))
      .map((m) => t('pillar_' + m.pillar)).join('–');
    // One character reads as the other pages read it: its name, then the character.
    const named = (pinyin, char) => `${esc(pinyin)} <span lang="zh-Hant">${esc(char)}</span>`;
    const memberChars = (relationship) => [...relationship.members]
      .sort((a, b) => DISPLAY_ORDER.indexOf(a.pillar) - DISPLAY_ORDER.indexOf(b.pillar))
      .map((m) => named(m.pinyin, m.char)).join(' – ');
    // What a relationship with the luck pillar names on the chart: its cards, the natal
    // ones and the luck pillar's, which the page shows standing in the chart, and its arc.
    const tokens = (relationship) => [
      ...relationship.members.map((m) => `${relationship.component}:${m.pillar}`), `arc:${relationship.id}`,
    ];

    const occurrenceMarkup = (e, phase) => {
      const resting = !e.phases.includes(phase);
      const about = [t('ten_god_' + e.ten_god), ...(e.new_to_chart ? [t('luck_new')] : [])];
      const type = e.component === 'stem' ? t('luck_stem_phase_only') : t('qi_' + e.qi_type);
      return `<div class="context-evidence-row luck-occurrence${resting ? ' is-resting' : ''}" data-luck-char="${esc(e.char)}" data-component="${esc(e.component)}">
        <span class="hidden-stem-dot ${esc(e.element)}" aria-hidden="true"></span>
        <div class="context-evidence-identity">
          <span>${named(e.pinyin, e.char)} · ${esc(`${e.polarity} ${t('element_' + e.element)}`)}</span>
          <span class="hidden-stem-type">${esc(resting ? t('luck_resting', { when: type }) : type)}</span>
        </div>
        <div class="context-evidence-role">${esc(about.join(' · '))}</div>
      </div>`;
    };

    // A relationship of the luck pillar's, when it acts, and the natal halves it takes in.
    const relationshipMarkup = (decade, relationship, phase) => {
      const acts = relationship.phases.includes(phase);
      const when = relationship.phases.length === 2 ? t('luck_acts_both') : t('luck_acts_stem');
      const takesIn = decade.absorbed.filter((a) => a.by.includes(relationship.id))
        .map((a) => t('luck_absorbs', { relationship: luck.chart.relationshipLabel(a.id) }));
      return `<li class="luck-relationship${acts ? '' : ' is-resting'}" data-relationship="${esc(relationship.id)}" data-kind="${esc(relationship.kind)}"${spot.attr(tokens(relationship))}>
        <span class="relationship-mark" aria-hidden="true"></span>
        <span class="luck-relationship-name">${esc(`${memberLabel(relationship)} · ${t('relationship_' + relationship.kind)}`)}</span>
        <span class="luck-relationship-chars">${memberChars(relationship)}</span>
        <span class="luck-relationship-when">${esc(acts ? when : t('luck_resting', { when }))}</span>
        ${takesIn.map((line) => `<span class="luck-relationship-absorbs">${esc(line)}</span>`).join('')}
      </li>`;
    };

    const elementsMarkup = (decade, phase) => {
      const counts = decade.counts[phase].elements;
      return `<div class="luck-elements" role="list" aria-labelledby="luck-elements-heading">${ELEMENTS.map((e) => {
        const natal = luck.natalElements[e];
        const added = counts[e] - natal;
        return `<div class="luck-element" role="listitem" data-element="${e}">
          <span class="luck-element-name"><span class="hidden-stem-dot ${e}" aria-hidden="true"></span>${esc(t('element_' + e))}</span>
          <span class="luck-element-cells" aria-hidden="true">${'<i></i>'.repeat(natal)}${'<i class="is-luck"></i>'.repeat(added)}</span>
          <span class="luck-element-count">${natal}${added ? ` <b>+${added}</b>` : ''}</span>
        </div>`;
      }).join('')}</div>`;
    };

    // What a screen reader hears for a choice: names, not characters.
    const spoken = (choice) => (choice === 'before' ? t('luck_title_before')
      : `${names(decadeOf(choice).chars)}, ${t('luck_phase_' + choice.phase)}`);

    const nominalMarkup = () => (luck.nominal ? `<p class="luck-nominal">${esc(t('luck_nominal'))}</p>` : '');

    const beforeMarkup = () => {
      const age = luck.startAge;
      return `
        <div class="relationship-detail-heading">
          <h3 id="luck-detail-title">${esc(t('luck_title_before'))}</h3>
        </div>
        <p class="luck-meta">${esc(t('luck_before_meta', { from: date(luck.before.start), to: date(luck.before.end), age: age.years }))}</p>
        ${nominalMarkup()}
        <p class="relationship-note">${esc(t('luck_before_note', { years: age.years, months: age.months, days: age.days }))}</p>`;
    };

    const decadeMarkup = (choice) => {
      const decade = decadeOf(choice);
      const now = today();
      const phase = choice.phase;
      const phaseRow = (p) => {
        const isNow = now !== null && now !== 'before' && now.sequence === decade.sequence && now.phase === p.phase;
        const heading = isNow ? t('luck_phase_now', { phase: t('luck_phase_' + p.phase) }) : t('luck_phase_' + p.phase);
        return `<button type="button" class="luck-phase${p.phase === phase ? ' is-chosen' : ''}" data-luck-phase="${p.phase}" aria-pressed="${p.phase === phase}">
          <span class="luck-phase-name">${esc(heading)}</span>
          <span class="luck-phase-when">${esc(`${date(p.start)} – ${date(p.end)}`)}</span>
          <span class="luck-phase-what">${esc(t(`luck_phase_${p.phase}_what`))}</span>
        </button>`;
      };
      // The Day Master's roots in the luck branch, as the roots page shows natal ones.
      const rootsMarkup = decade.roots.length
        ? `<div class="context-evidence-list">${decade.roots.map((r) => `
          <div class="context-evidence-row luck-root" data-luck-char="${esc(r.char)}">
            <span class="hidden-stem-dot ${esc(r.element)}" aria-hidden="true"></span>
            <div class="context-evidence-identity">
              <span>${named(r.pinyin, r.char)} · ${esc(`${r.polarity} ${t('element_' + r.element)}`)}</span>
              <span class="hidden-stem-type">${esc(t('qi_' + r.qi_type))}</span>
            </div>
            <div class="context-evidence-role">${esc(t('context_match_' + r.match))}</div>
          </div>`).join('')}</div>`
        : `<p class="luck-roots">${esc(t('luck_roots_none'))}</p>`;
      const [direction, season] = decade.direction;
      return `
        <div class="relationship-detail-heading">
          <p class="luck-sequence">${esc(t('luck_sequence', { n: decade.sequence, count: luck.decades.length, direction: t('luck_' + luck.direction) }))}</p>
          <h3 id="luck-detail-title"><span lang="zh-Hant">${decade.chars}</span> ${esc(names(decade.chars))}</h3>
        </div>
        <p class="luck-meta">${esc(t('luck_meta', {
          from: date(decade.start), to: date(decade.end), start: decade.startAge, end: decade.endAge,
          direction: t('luck_direction_' + direction), season: t('context_' + season).toLowerCase(),
        }))}</p>
        ${nominalMarkup()}
        <div class="luck-phases" role="group" aria-label="${esc(t('luck_phases'))}">${decade.phases.map(phaseRow).join('')}</div>
        <h4 class="panel-subheading luck-subheading">${esc(t('luck_brings'))}</h4>
        <div class="context-evidence-list">${[decade.visible, ...decade.hidden].map((e) => occurrenceMarkup(e, phase)).join('')}</div>
        <p class="luck-stage">${esc(t('luck_stage', { branch: `${PINYIN[decade.branch]} ${decade.branch}`, stage: t('luck_stage_' + decade.stage), n: decade.stage }))}</p>
        <h4 class="panel-subheading luck-subheading">${esc(t('luck_roots'))}</h4>
        ${rootsMarkup}
        <h4 class="panel-subheading luck-subheading">${esc(t('luck_with_chart'))}</h4>
        ${decade.interactions.length
          ? `<ul class="luck-relationships">${decade.interactions.map((r) => relationshipMarkup(decade, r, phase)).join('')}</ul>`
          : `<p class="relationship-note">${esc(t('luck_none'))}</p>`}
        <h4 id="luck-elements-heading" class="panel-subheading luck-subheading">${esc(t('luck_elements', { count: CHARACTERS[phase] }))}</h4>
        ${elementsMarkup(decade, phase)}
        <p class="relationship-note">${esc(t('luck_note'))}</p>`;
    };

    // ── Moving the choice ──
    // Everything follows the choice: the ribbon, the fifth pillar, and the page when open.
    const sync = () => {
      const pageFocus = open && detail.contains(document.activeElement);
      syncRibbon();
      drawColumn();
      if (open) {
        detail.innerHTML = cursor === 'before' ? beforeMarkup() : decadeMarkup(cursor);
        detail.dataset.topic = topicOf(cursor);
        detail.classList.remove('hidden');
        // Focus in the page stays in it, on the phase now chosen; the years before have
        // none, and it goes to their chip.
        if (pageFocus) {
          (detail.querySelector('[data-luck-phase][aria-pressed="true"]') ?? ribbon.querySelector(`[data-luck="${keyOf(cursor)}"]`))
            .focus({ preventScroll: true });
        }
      }
    };
    // Choosing a period shows it in the chart; `page` opens its page too.
    const go = (choice, { page = false } = {}) => {
      if (page && !open) beforeSelect();
      cursor = choice;
      shown = true;
      if (page) open = true;
      sync();
      status.textContent = t('luck_selected', { title: spoken(choice) });
    };
    // Closes the page; what stands in the chart stays. Focus that was in the page goes
    // to the period's chip.
    const close = () => {
      if (luck === null || !open) return;
      const pageFocus = detail.contains(document.activeElement);
      open = false;
      detail.classList.add('hidden');
      detail.innerHTML = '';
      delete detail.dataset.topic;
      status.textContent = '';
      syncRibbon();
      drawColumn();
      if (pageFocus) ribbon.querySelector(`[data-luck="${keyOf(cursor)}"]`).focus({ preventScroll: true });
    };
    // Shows or hides the luck pillar. Hiding it closes its page.
    const setShown = (on) => {
      if (luck === null || on === shown) return;
      if (!on) close();
      shown = on;
      syncRibbon();
      drawColumn();
      status.textContent = t(on ? 'luck_shown' : 'luck_hidden');
    };

    // A decade opens at today's phase when today falls in it, else at its stem phase.
    const opening = (sequence) => {
      const now = today();
      return now !== null && now !== 'before' && now.sequence === sequence ? now : { sequence, phase: 'stem' };
    };
    // A chip opens its period, in the chart and in the panel; the open one's chip closes
    // its page.
    const choosePeriod = (key) => {
      if (open && keyOf(cursor) === key) { close(); return; }
      go(key === 'before' ? 'before' : opening(Number(key)), { page: true });
    };
    // A step goes from the choice shown, else from today; before the birth, or past the
    // last decade, from just beyond that end. The page, when open, follows.
    const step = (by) => {
      const all = steps();
      const from = shown ? cursor : today();
      const at = from === null ? (toCome() ? -1 : all.length) : all.findIndex((choice) => same(choice, from));
      const next = all[Math.min(all.length - 1, Math.max(0, at + by))];
      if (!shown || !same(next, cursor)) go(next);
    };
    // A decade at a time: to the next decade's opening phase, or back to the years before.
    const stepDecade = (by) => {
      const from = shown ? cursor : home();
      const at = from === 'before' ? 0 : from.sequence;
      const to = Math.min(luck.decades.length, Math.max(0, at + by));
      // At either end, a decade's step stays where it is.
      const next = to === at ? from : to === 0 ? 'before' : opening(to);
      if (!shown || !same(next, cursor)) go(next);
    };
    const toToday = () => {
      const now = today();
      if (now === null) return false;
      go(now, { page: true });
      return true;
    };

    ribbon.addEventListener('click', (event) => {
      const chip = event.target.closest('[data-luck]');
      if (chip) {
        choosePeriod(chip.dataset.luck);
        chip.focus();
        return;
      }
      const stepper = event.target.closest('[data-luck-step]');
      if (stepper) {
        step(Number(stepper.dataset.luckStep));
        stepper.focus();
        return;
      }
      if (event.target.closest('[data-luck-today]') && toToday()) {
        // Today is now open, and its button is spent: focus goes to its chip.
        ribbon.querySelector(`[data-luck="${keyOf(cursor)}"]`).focus();
      }
    });
    ribbon.addEventListener('keydown', (event) => {
      const chip = event.target.closest('[data-luck]');
      if (!chip || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const chips = [...ribbon.querySelectorAll('[data-luck]')];
      const at = chips.indexOf(chip);
      const to = { ArrowLeft: at - 1, ArrowRight: at + 1, Home: 0, End: chips.length - 1 }[event.key];
      if (to === undefined) return;
      event.preventDefault();
      const next = chips[Math.max(0, Math.min(chips.length - 1, to))];
      chips.forEach((node) => { node.tabIndex = node === next ? 0 : -1; });
      next.focus();
    });
    switcher.addEventListener('click', (event) => {
      const button = event.target.closest('[data-luck-show]');
      if (button) setShown(button.dataset.luckShow === 'on');
    });
    // The fifth pillar's name opens its page, and closes it.
    pillars.addEventListener('click', (event) => {
      const identity = event.target.closest('[data-luck-identity]');
      if (!identity) return;
      if (open) close();
      else go(cursor, { page: true });
      column.querySelector('[data-luck-identity]').focus();
    });
    detail.addEventListener('click', (event) => {
      const row = event.target.closest('[data-luck-phase]');
      if (!row || !open || cursor === 'before') return;
      go({ sequence: cursor.sequence, phase: row.dataset.luckPhase }, { page: true });
      detail.querySelector(`[data-luck-phase="${row.dataset.luckPhase}"]`).focus();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && open && !event.defaultPrevented) {
        event.preventDefault();
        close();
        ribbon.querySelector(`[data-luck="${keyOf(cursor)}"]`).focus();
      }
    });

    // `cards` is the API's luck_chart, `chart.relationshipLabel` names a natal
    // relationship by its id, as the list does, and `chart.feetEdge` says where the natal
    // arcs' feet stand on a card. Without luck pillars the ribbon and the
    // fifth pillar are gone.
    const render = (pillarsData, context, cards, chart, timezone) => {
      open = false;
      detail.classList.add('hidden');
      detail.innerHTML = '';
      delete detail.dataset.topic;
      status.textContent = '';
      if (!pillarsData && !context && !cards) {
        luck = null;
        cursor = null;
        shown = false;
        ribbon.innerHTML = '';
        ribbon.classList.add('hidden');
        switcher.classList.add('hidden');
        removeColumn();
        return;
      }
      require(typeof timezone === 'string' && timezone);
      luck = { ...read(pillarsData, context, cards, chart), timezone };
      // A chart opens natal: the luck pillar waits, hidden, at today's phase.
      shown = false;
      cursor = home();
      pillars.classList.add('has-luck');
      switcher.classList.remove('hidden');
      drawRibbon();
      syncRibbon();
      drawColumn();
    };

    // A link's topic: the page of before or <sequence>/<phase>; whether this chart has it.
    const select = (path) => {
      if (luck === null) return false;
      const choice = choiceOf(path);
      if (choice === null) return false;
      go(choice, { page: true });
      return true;
    };
    // A link's luck pillar: the period standing in the chart; whether this chart has it.
    const stand = (path) => {
      if (luck === null) return false;
      const choice = choiceOf(path);
      if (choice === null) return false;
      go(choice);
      return true;
    };
    const has = () => luck !== null;
    const topic = () => (open ? topicOf(cursor) : null);
    // The period standing in the chart, as the address names it, or null.
    const standing = () => (luck !== null && shown ? pathOf(cursor) : null);
    // The fifth pillar's cards take part in the chart's keys only while they show a decade.
    const cardsActive = () => luck !== null && columnState() === 'on';
    // What the ribbon offers, for the commands: each choice as its chip names it, and the
    // topic its chip opens.
    const choices = () => {
      if (luck === null) return [];
      const now = today();
      return [
        { label: chipLabel('before', now), topic: 'luck/before' },
        ...luck.decades.map((decade) => ({ label: chipLabel(String(decade.sequence), now), topic: topicOf(opening(decade.sequence)) })),
      ];
    };
    // A key's change can take focus from under the reader: a page redrawn, a button
    // spent. Focus that was on the luck pillars and is lost then goes to the chosen
    // period's chip, so the chart's keys go on acting; elsewhere it stays.
    const keeping = (change) => (...args) => {
      const active = document.activeElement;
      const held = active !== null && [ribbon, detail, column].some((part) => part?.contains(active));
      const result = change(...args);
      const now = document.activeElement;
      if (held && luck !== null && (now === null || now === document.body || !now.isConnected || now.disabled || now.closest('[inert]'))) {
        ribbon.querySelector(`[data-luck="${keyOf(shown ? cursor : home())}"]`).focus({ preventScroll: true });
      }
      return result;
    };
    return {
      render, close, select, stand, has, topic, standing, cardsActive, choices,
      shown: () => shown,
      setShown,
      toggle: keeping(() => setShown(!shown)),
      step: keeping(step),
      stepDecade: keeping(stepDecade),
      toToday: keeping(toToday),
    };
  };

  window.EC_LUCK = { create };
})();
