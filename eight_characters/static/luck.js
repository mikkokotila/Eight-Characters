// The luck pillars of a chart with a gender: a ribbon of the decades under the chart's
// topics, and the chosen decade's page in the panel. Each decade is a stem phase, its
// first five years, and a branch phase, its last five (luck_pillars.py); a choice is a
// phase, and a decade opens at today's phase when today falls in it. The ribbon groups
// the decades by the direction their branch travels: San Ming Tong Hui judges the luck
// cycle by its travel east, south, west or north.
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

  const create = ({ root, translate: t, escape: esc, spot, locale, beforeSelect }) => {
    const ribbon = root.querySelector('#luck-ribbon');
    const detail = root.querySelector('#luck-detail');
    const status = root.querySelector('#luck-status');
    if (!ribbon || !detail || !status || !spot) throw new Error('Luck pillar view is incomplete.');
    let luck = null;
    let selected = null;

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

    // The API's luck pillars and their context, read strictly: a decade the page cannot
    // stand behind is an error, not a gap.
    const read = (pillars, context, chart) => {
      require(pillars && context && context.policy === 'luck_context_v1' && pillars.phase_rule === 'stem_then_branch_v1');
      require(['forward', 'backward'].includes(pillars.direction));
      require(Array.isArray(pillars.pillars) && pillars.pillars.length > 0
        && Array.isArray(context.decades) && context.decades.length === pillars.pillars.length);
      require(ELEMENTS.every((e) => Number.isInteger(context.natal_counts?.elements?.[e]))
        && total(context.natal_counts.elements) === CHARACTERS.natal);
      const decades = pillars.pillars.map((pillar, index) => {
        const stem = pillar?.stem?.chinese;
        const branch = pillar?.branch?.chinese;
        require(pillar.sequence === index + 1 && STEMS.includes(stem) && BRANCHES.includes(branch)
          && stem.length === 1 && branch.length === 1);
        const found = context.decades[index];
        require(found.sequence === pillar.sequence && Array.isArray(pillar.phases) && pillar.phases.length === 2);
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
        };
      });
      decades.slice(1).forEach((decade, index) => require(decade.start.getTime() === decades[index].end.getTime()));
      const before = { start: instant(pillars.pre_luck_period.start_utc), end: instant(pillars.pre_luck_period.end_utc) };
      require(before.end.getTime() === decades[0].start.getTime());
      require(['years', 'months', 'days'].every((part) => Number.isInteger(pillars.start_age?.[part]))
        && pillars.start_age.years === decades[0].startAge);
      return {
        decades,
        before,
        direction: pillars.direction,
        startAge: pillars.start_age,
        natalElements: context.natal_counts.elements,
        chart,
      };
    };

    // Where now falls: 'before', a decade's phase, or null past the last decade.
    const phaseAt = (when) => {
      if (when < luck.before.end) return 'before';
      for (const decade of luck.decades) {
        if (when < decade.end) return { sequence: decade.sequence, phase: when < decade.phases[1].start ? 'stem' : 'branch' };
      }
      return null;
    };
    const today = () => phaseAt(new Date());
    // Every choice in order, the period before the first decade first.
    const steps = () => ['before', ...luck.decades.flatMap((d) => PHASES.map((phase) => ({ sequence: d.sequence, phase })))];
    const same = (a, b) => (a === 'before' || b === 'before' ? a === b
      : Boolean(a && b) && a.sequence === b.sequence && a.phase === b.phase);
    const decadeOf = (choice) => luck.decades.find((d) => d.sequence === choice.sequence);
    const topicOf = (choice) => (choice === 'before' ? 'luck/before' : `luck/${choice.sequence}/${choice.phase}`);

    const keyOf = (choice) => (choice === 'before' ? 'before' : String(choice.sequence));
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
    // cards do, and arrows move between them: the chosen period's chip has it, else
    // today's, else the last decade's.
    const syncRibbon = () => {
      const now = today();
      const stop = keyOf(selected ?? now ?? luck.decades[luck.decades.length - 1]);
      ribbon.querySelectorAll('.luck-chip').forEach((chip) => {
        const key = chip.dataset.luck;
        const on = selected !== null && keyOf(selected) === key;
        const isToday = now !== null && keyOf(now) === key;
        chip.classList.toggle('is-selected', on);
        chip.classList.toggle('is-today', isToday);
        chip.setAttribute('aria-expanded', String(on));
        chip.setAttribute('aria-label', chipLabel(key, now));
        chip.tabIndex = key === stop ? 0 : -1;
        chip.querySelectorAll('.luck-chip-phases i').forEach((bar) => {
          bar.classList.toggle('is-chosen', on && selected.phase === bar.dataset.phase);
          bar.toggleAttribute('data-today', isToday && now.phase === bar.dataset.phase);
        });
      });
      ribbon.querySelector('[data-luck-today]').disabled = now === null || same(now, selected);
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
      syncRibbon();
    };

    const memberLabel = (relationship) => [...relationship.members]
      .sort((a, b) => DISPLAY_ORDER.indexOf(a.pillar) - DISPLAY_ORDER.indexOf(b.pillar))
      .map((m) => t('pillar_' + m.pillar)).join('–');
    // One character reads as the other pages read it: its name, then the character.
    const named = (pinyin, char) => `${esc(pinyin)} <span lang="zh-Hant">${esc(char)}</span>`;
    const memberChars = (relationship) => [...relationship.members]
      .sort((a, b) => DISPLAY_ORDER.indexOf(a.pillar) - DISPLAY_ORDER.indexOf(b.pillar))
      .map((m) => named(m.pinyin, m.char)).join(' – ');
    // The natal cards a relationship with the luck pillar names; the luck pillar has none yet.
    const natalTokens = (relationship) => relationship.members
      .filter((m) => m.pillar !== 'luck').map((m) => `${relationship.component}:${m.pillar}`);

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
      return `<li class="luck-relationship${acts ? '' : ' is-resting'}" data-relationship="${esc(relationship.id)}" data-kind="${esc(relationship.kind)}"${spot.attr(natalTokens(relationship))}>
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

    const beforeMarkup = () => {
      const age = luck.startAge;
      return `
        <div class="relationship-detail-heading">
          <h3 id="luck-detail-title">${esc(t('luck_title_before'))}</h3>
        </div>
        <p class="luck-meta">${esc(t('luck_before_meta', { from: date(luck.before.start), to: date(luck.before.end), age: age.years }))}</p>
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

    const clear = () => {
      if (luck === null) return;
      selected = null;
      detail.classList.add('hidden');
      detail.innerHTML = '';
      delete detail.dataset.topic;
      status.textContent = '';
      syncRibbon();
    };

    const show = (choice) => {
      if (!same(choice, selected)) {
        if (selected === null) beforeSelect();
        selected = choice;
      }
      detail.innerHTML = choice === 'before' ? beforeMarkup() : decadeMarkup(choice);
      detail.dataset.topic = topicOf(choice);
      detail.classList.remove('hidden');
      syncRibbon();
      status.textContent = t('luck_selected', { title: spoken(choice) });
    };

    // A path as the address names it, before or <sequence>/<phase>: whether this chart
    // has it to show.
    const select = (path) => {
      if (luck === null) return false;
      if (path === 'before') { show('before'); return true; }
      const [sequence, phase] = path.split('/');
      const choice = { sequence: Number(sequence), phase };
      if (!PHASES.includes(phase) || !decadeOf(choice)) return false;
      show(choice);
      return true;
    };

    // A decade opens at today's phase when today falls in it, else at its stem phase.
    const opening = (sequence) => {
      const now = today();
      return now !== null && now !== 'before' && now.sequence === sequence ? now : { sequence, phase: 'stem' };
    };
    const chooseDecade = (sequence) => {
      if (selected !== null && selected !== 'before' && selected.sequence === sequence) { clear(); return; }
      show(opening(sequence));
    };
    const step = (by) => {
      const all = steps();
      const from = selected ?? today() ?? all[all.length - 1];
      const at = all.findIndex((choice) => same(choice, from));
      const next = all[Math.min(all.length - 1, Math.max(0, at + by))];
      if (selected === null || !same(next, selected)) show(next);
    };

    ribbon.addEventListener('click', (event) => {
      const chip = event.target.closest('[data-luck]');
      if (chip) {
        const value = chip.dataset.luck;
        if (value === 'before') {
          if (selected === 'before') clear();
          else show('before');
        } else chooseDecade(Number(value));
        ribbon.querySelector(`[data-luck="${value}"]`).focus();
        return;
      }
      const stepper = event.target.closest('[data-luck-step]');
      if (stepper) {
        step(Number(stepper.dataset.luckStep));
        ribbon.querySelector(`[data-luck-step="${stepper.dataset.luckStep}"]`).focus();
        return;
      }
      if (event.target.closest('[data-luck-today]')) {
        const now = today();
        if (now === null) return;
        show(now);
        // Today is now chosen, and its button is disabled: focus goes to its chip.
        ribbon.querySelector(`[data-luck="${now === 'before' ? 'before' : now.sequence}"]`).focus();
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
    detail.addEventListener('click', (event) => {
      const row = event.target.closest('[data-luck-phase]');
      if (!row || selected === null || selected === 'before') return;
      show({ sequence: selected.sequence, phase: row.dataset.luckPhase });
      detail.querySelector(`[data-luck-phase="${row.dataset.luckPhase}"]`).focus();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && selected !== null && !event.defaultPrevented) {
        event.preventDefault();
        const chip = selected === 'before' ? 'before' : String(selected.sequence);
        clear();
        ribbon.querySelector(`[data-luck="${chip}"]`).focus();
      }
    });

    // `chart.relationshipLabel` names a natal relationship by its id, as the list does.
    // Without luck pillars the ribbon is gone.
    const render = (pillars, context, chart, timezone) => {
      selected = null;
      detail.classList.add('hidden');
      detail.innerHTML = '';
      delete detail.dataset.topic;
      status.textContent = '';
      if (!pillars && !context) {
        luck = null;
        ribbon.innerHTML = '';
        ribbon.classList.add('hidden');
        return;
      }
      require(typeof timezone === 'string' && timezone);
      luck = { ...read(pillars, context, chart), timezone };
      drawRibbon();
    };

    const topic = () => (selected === null ? null : topicOf(selected));
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
    return { render, clear, select, topic, choices };
  };

  window.EC_LUCK = { create };
})();
