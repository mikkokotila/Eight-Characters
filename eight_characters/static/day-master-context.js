// Inspectable natal evidence. No scores, transformed colors, or changed card state.
(() => {
  const ORDER = ['year', 'month', 'day', 'hour'];
  const DISPLAY = ['hour', 'day', 'month', 'year'];
  const SEASONS = {
    spring: ['wood', '寅卯辰'], summer: ['fire', '巳午未'],
    autumn: ['metal', '申酉戌'], winter: ['water', '亥子丑'],
  };
  const COMPANIONS = ['friend', 'rob_wealth'];
  const RESOURCES = ['direct_resource', 'indirect_resource'];
  const create = ({ root, translate: t, escape: esc, spot, canon, beforeSelect }) => {
    const summary = root.querySelector('#day-master-context');
    const heading = root.querySelector('#day-master-heading');
    const controls = root.querySelector('#context-controls');
    const detail = root.querySelector('#context-detail');
    const status = root.querySelector('#context-status');
    if (!summary || !heading || !controls || !detail || !status || !spot || !canon) {
      throw new Error('Day Master context view is incomplete.');
    }
    let selected = null;
    let pages = {};
    let chart = {};
    // The luck pillar's period (luck.js): its roots and the roles it brings, which the
    // Roots and Roles topics add while it stands in the chart.
    let luck = null;
    let natal = null;
    const require = (condition) => {
      if (!condition) throw new Error(t('context_error'));
    };
    const elementLabel = (e) => `${e.polarity} ${t('element_' + e.element)}`;
    const sourcesFor = (e) => {
      const component = e.component === 'stem' ? 'stem' : 'branch';
      const card = root.querySelector(`.card.${component}[data-pillar="${e.pillar}"]`);
      require(card && card.dataset.char === (component === 'stem' ? e.char : e.branch));
      const rows = component === 'branch' ? [...root.querySelectorAll(
        `.card.branch[data-pillar="${e.pillar}"] [data-hidden-stem="${e.char}"], .hidden-stems-panel[data-pillar="${e.pillar}"] [data-hidden-stem="${e.char}"]`
      )] : [];
      // Both existing hidden-stem surfaces must exist before this chart is shown.
      require(component === 'stem' || rows.length === 2);
      return { card, rows };
    };
    const sameIdentity = (a, b) => {
      require(a && b && ['char', 'pinyin', 'element', 'polarity'].every((key) => a[key] === b[key]));
    };
    const checkEvidence = (actual, expected, dm = null) => {
      require(Array.isArray(actual) && actual.length === expected.length);
      actual.forEach((e, index) => {
        const reference = expected[index];
        require(e && typeof e.pinyin === 'string' && e.pinyin.length > 0);
        require(['pillar', 'component', 'branch', 'char', 'element', 'polarity', 'qi_type', 'ten_god']
          .every((key) => e[key] === reference[key]));
        if (dm) require(e.match === (e.char === dm.char ? 'exact_stem' : 'opposite_polarity'));
      });
    };
    const validate = (data, chartData, gods, hiddenStems) => {
      require(data && data.policy === 'natal_presence_v1' && Array.isArray(chartData.pillars)
        && chartData.pillars.length === 4 && gods);
      chart = Object.fromEntries(DISPLAY.map((name, index) => [name, chartData.pillars[index]]));
      sameIdentity(data.day_master, chart.day.stem);
      const expected = [];
      ORDER.forEach((pillar) => {
        const g = gods[pillar];
        require(g && g.stem.char === chart[pillar].stem.char && g.branch === chart[pillar].branch.char
          && Array.isArray(g.hidden_stems));
        // Both rendered hidden-stem surfaces must describe the same natal data.
        const hidden = hiddenStems?.[pillar];
        require(hidden && hidden.branch === g.branch && Array.isArray(hidden.hidden_stems)
          && hidden.hidden_stems.length === g.hidden_stems.length);
        hidden.hidden_stems.forEach((e, index) => {
          require(e && ['char', 'element', 'polarity', 'qi_type'].every(
            (key) => e[key] === g.hidden_stems[index][key]
          ));
        });
        if (pillar !== 'day') expected.push({ ...g.stem, pillar, component: 'stem', branch: null, qi_type: null });
        g.hidden_stems.forEach((e) => expected.push({ ...e, pillar, component: 'hidden_stem', branch: g.branch }));
      });
      const season = data.season;
      require(season && season.basis === 'traditional_month_branch_groups'
        && Object.hasOwn(SEASONS, season.name));
      sameIdentity(season.month_branch, chart.month.branch);
      const [element, branches] = SEASONS[season.name];
      require(season.element === element && branches.includes(season.month_branch.char));
      checkEvidence(season.hidden_stems, expected.filter((e) => e.pillar === 'month' && e.component === 'hidden_stem'));
      checkEvidence(data.roots, expected.filter((e) => e.component === 'hidden_stem' && e.element === data.day_master.element), data.day_master);
      require(data.support);
      checkEvidence(data.support.companions, expected.filter((e) => COMPANIONS.includes(e.ten_god)));
      checkEvidence(data.support.resources, expected.filter((e) => RESOURCES.includes(e.ten_god)));
      expected.forEach(sourcesFor);
    };

    // One stem: its element's swatch, the stem, a hidden stem's qi position, and then
    // its role, which a role's own page leaves out, and how a root matches. It points at
    // its card on the chart, and at its row there when hidden stems show.
    const evidenceMarkup = (e, { role = true, rootMatch = false, also = [] } = {}) => {
      const about = [
        ...(role ? [t('ten_god_' + e.ten_god)] : []),
        ...(rootMatch ? [t('context_match_' + e.match)] : []),
        ...also,
      ];
      return `
      <div class="context-evidence-row" data-evidence-pillar="${esc(e.pillar)}" data-evidence-char="${esc(e.char)}"${spot.attr([spot.of(e)])}>
        <span class="hidden-stem-dot ${esc(e.element)}" aria-hidden="true"></span>
        <div class="context-evidence-identity">
          <span>${esc(e.pinyin)} ${esc(e.char)} · ${esc(elementLabel(e))}</span>
          ${e.component === 'stem' ? '' : `<span class="hidden-stem-type">${esc(t('qi_' + e.qi_type))}</span>`}
        </div>
        ${about.length ? `<div class="context-evidence-role">${esc(about.join(' · '))}</div>` : ''}
      </div>`;
    };

    // A branch with its evidence; `reading`, what the canon says of it, follows that.
    const branchMarkup = (pillar, evidence, roots = false, reading = '') => {
      const branch = chart[pillar].branch;
      return `<div class="relationship-member"${spot.attr([`branch:${pillar}`])}>
        <div class="relationship-position">${esc(t('pillar_' + pillar))}</div>
        <div class="relationship-identity">${esc(branch.pinyin)} ${esc(branch.char)}</div>
        <div class="relationship-element">${esc(branch.element_label)}</div>
        <div class="context-evidence-list">${evidence.map((e) => evidenceMarkup(e, { rootMatch: roots })).join('')}</div>
        ${reading}
      </div>`;
    };
    const makePage = (title, meta, content, note) => `
      <div class="relationship-detail-heading">
        <h3 id="context-detail-title">${esc(title)}</h3>
      </div>
      <p class="relationship-meta">${esc(meta)}</p>
      ${content}
      <p class="relationship-note">${esc(note)}</p>`;

    const clearHighlights = () => {
      root.querySelectorAll('.is-context-source, .is-context-evidence, .is-context-reference').forEach((node) => {
        node.classList.remove('is-context-source', 'is-context-evidence', 'is-context-reference');
      });
    };
    const roles = window.EC_ROLES.create({
      root, translate: t, escape: esc, spot, canon, makePage, branchMarkup, evidenceMarkup,
      show: (page, focusSelector) => {
        require(selected === 'roles');
        clearHighlights();
        showPage(page);
        if (focusSelector) {
          const target = detail.querySelector(focusSelector);
          require(target);
          if (!target.matches('button')) target.setAttribute('tabindex', '-1');
          target.focus({ preventScroll: true });
        }
      },
    });
    const clear = () => {
      selected = null;
      clearHighlights();
      summary.querySelectorAll('button[data-context]').forEach((button) => button.setAttribute('aria-expanded', 'false'));
      detail.classList.add('hidden');
      detail.innerHTML = '';
      delete detail.dataset.topic;
      status.textContent = '';
    };
    const highlight = (e) => {
      const { card, rows } = sourcesFor(e);
      card.classList.add('is-context-source');
      // Mark exact rows on both surfaces; never open or flip cards automatically.
      rows.forEach((row) => row.classList.add('is-context-evidence'));
    };
    // The luck pillar's roots, as a member beside the natal root branches.
    const luckRootsMarkup = () => `
      <div class="relationship-member"${spot.attr(['branch:luck'])}>
        <div class="relationship-position">${esc(t('pillar_luck'))}</div>
        <div class="relationship-identity">${esc(luck.cards.branch.pinyin)} ${esc(luck.cards.branch.char)}</div>
        <div class="relationship-element">${esc(luck.cards.branch.element_label)}</div>
        <div class="context-evidence-list">${luck.roots.map((e) => evidenceMarkup(e, { rootMatch: true })).join('')}</div>
      </div>`;
    const rootsPage = () => {
      const withLuck = luck !== null && luck.shown && luck.roots.length > 0;
      const members = natal.rootPillars.length + (withLuck ? 1 : 0);
      const content = members > 0
        ? `<div class="relationship-members" style="--member-count: ${members}">${natal.rootPillars.map((pillar) =>
          branchMarkup(pillar, natal.data.roots.filter((e) => e.pillar === pillar), true, canon.rootGround(pillar))).join('')}${withLuck ? luckRootsMarkup() : ''}</div>`
        : `<p class="relationship-empty">${esc(t('context_no_roots'))}</p>`;
      return {
        path: 'roots', title: t('context_roots'), evidence: [...natal.data.roots, ...(withLuck ? luck.roots : [])],
        markup: makePage(t('context_roots'), natal.rootsLabel, content, natal.withReadings(t('context_roots_note'))),
      };
    };
    // The roles the luck pillar brings in its phase, under the roles overview.
    const withLuckRoles = (page) => {
      if (page.path !== 'roles' || luck === null || !luck.shown || luck.occurrences.length === 0) return page;
      return {
        ...page,
        evidence: [...page.evidence, ...luck.occurrences],
        markup: `${page.markup}
          <h4 class="panel-subheading">${esc(t('roles_luck_heading'))}</h4>
          <div class="context-evidence-list">${luck.occurrences.map((e) => evidenceMarkup(e, { also: e.new_to_chart ? [t('luck_new')] : [] })).join('')}</div>`,
      };
    };
    // The page shown names itself on the detail, for the chart's address.
    const showPage = (shownPage) => {
      const page = withLuckRoles(shownPage);
      require(typeof page.path === 'string');
      page.evidence.forEach(highlight);
      if (page.reference) sourcesFor(page.reference).card.classList.add('is-context-reference');
      detail.innerHTML = page.markup;
      detail.dataset.topic = page.path;
      detail.classList.remove('hidden');
      status.textContent = t('context_selected', { topic: page.title });
    };
    // The topics: the Day Master line, when it opens a page, and the controls beside it.
    summary.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-context]');
      if (!button) return;
      const key = button.dataset.context;
      require(Object.hasOwn(pages, key));
      const wasSelected = selected === key;
      clear();
      if (wasSelected) return;
      beforeSelect();
      selected = key;
      button.setAttribute('aria-expanded', 'true');
      showPage(pages[key]);
    });
    const clearAndReturnFocus = () => {
      const button = summary.querySelector('button[data-context][aria-expanded="true"]');
      clear();
      if (button) button.focus();
    };
    // Pointer activation need not move keyboard focus into the chart.
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && selected !== null) {
        event.preventDefault();
        clearAndReturnFocus();
      }
    });

    const render = (data, chartData, gods, hiddenStems, roleProfile) => {
      clear();
      pages = {};
      controls.innerHTML = '';
      heading.textContent = '';
      validate(data, chartData, gods, hiddenStems);
      const dm = data.day_master;
      const season = data.season;
      const rootPillars = DISPLAY.filter((pillar) => data.roots.some((e) => e.pillar === pillar));
      const rootsLabel = t(rootPillars.length === 0 ? 'context_roots_none' : rootPillars.length === 1 ? 'context_roots_one' : 'context_roots_many', { count: rootPillars.length });
      const line = `${t('ten_god_day_master')} · ${dm.pinyin} — ${elementLabel(dm)}`;
      // With a reading, the line opens the Day Master's page; otherwise it stays a heading.
      heading.innerHTML = canon.has()
        ? `<button type="button" class="canon-day-master-line" data-context="day-master" aria-expanded="false" aria-controls="context-detail">${esc(line)}</button>`
        : esc(line);
      const labels = {
        season: t('context_month', { month: season.month_branch.pinyin }),
        roots: rootsLabel,
        roles: t('roles_title'),
      };
      const withReadings = (note) => [note, canon.note()].filter(Boolean).join(' ');
      natal = { data, rootPillars, rootsLabel, withReadings };
      pages = {
        season: {
          path: 'season', title: t('context_season'), evidence: season.hidden_stems,
          markup: makePage(t('context_season'), t('context_season_group', { season: t('context_' + season.name), element: t('element_' + season.element) }),
            `<div class="relationship-members" style="--member-count: 1">${branchMarkup('month', season.hidden_stems, false, canon.season())}</div>`, withReadings(t('context_season_note'))),
        },
        roots: rootsPage(),
        roles: roles.render(roleProfile, chartData, gods),
      };
      // The Day Master's own page, which only the canon's readings fill.
      if (canon.has()) {
        pages['day-master'] = {
          path: 'day-master', title: line, evidence: [],
          markup: makePage(line, canon.dayMasterTitle(), canon.dayMaster(), canon.note()),
        };
      }
      controls.innerHTML = Object.entries(labels).map(([key, label]) => `
        <button type="button" class="reading-toggle context-toggle" data-context="${key}" data-label="${esc(pages[key].title + ' · ' + label)}" aria-expanded="false" aria-controls="context-detail" aria-label="${esc(pages[key].title + ' · ' + label)}">${esc(label)}${
          ['roots', 'roles'].includes(key) ? '<span class="topic-delta is-hidden"></span>' : ''}</button>`).join('');
      setLuck(luck);
    };
    // What the luck pillar's period adds to the Roots and Roles topics: a word on each
    // button, kept in its place while the luck pillar is hidden so the topics' row never
    // rewraps on L, and its part of their pages while it shows.
    const setLuck = (period) => {
      luck = period;
      if (natal === null) return;
      const words = {
        roots: luck !== null && luck.roots.length > 0 ? t('topic_luck_roots') : '',
        roles: luck !== null && luck.newRoles > 0 ? t('topic_luck_roles', { count: luck.newRoles }) : '',
      };
      Object.entries(words).forEach(([key, word]) => {
        const button = controls.querySelector(`button[data-context="${key}"]`);
        const delta = button.querySelector('.topic-delta');
        delta.textContent = word ? ` ${word}` : '';
        delta.classList.toggle('is-hidden', !(luck !== null && luck.shown));
        button.setAttribute('aria-label', [button.dataset.label, luck !== null && luck.shown ? word : ''].filter(Boolean).join(' '));
      });
      pages.roots = rootsPage();
      // A topic open shows the luck pillar's part as it comes and goes.
      if (selected === 'roots') {
        clearHighlights();
        showPage(pages.roots);
      } else if (selected === 'roles' && detail.dataset.topic === 'roles') {
        clearHighlights();
        showPage(pages.roles);
      }
    };
    return { render, clear, setLuck };
  };
  window.EC_DAY_MASTER_CONTEXT = { create };
})();
