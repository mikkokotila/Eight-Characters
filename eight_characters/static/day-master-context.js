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
  const create = ({ root, translate: t, escape: esc, beforeSelect }) => {
    const summary = root.querySelector('#day-master-context');
    const heading = root.querySelector('#day-master-heading');
    const controls = root.querySelector('#context-controls');
    const detail = root.querySelector('#context-detail');
    const status = root.querySelector('#context-status');
    if (!summary || !heading || !controls || !detail || !status) {
      throw new Error('Day Master context view is incomplete.');
    }
    let selected = null;
    let pages = {};
    let chart = {};
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
    const validate = (data, chartData, gods) => {
      require(data && data.policy === 'natal_presence_v1' && Array.isArray(chartData.pillars)
        && chartData.pillars.length === 4 && gods);
      chart = Object.fromEntries(DISPLAY.map((name, index) => [name, chartData.pillars[index]]));
      sameIdentity(data.day_master, chart.day.stem);
      const expected = [];
      ORDER.forEach((pillar) => {
        const g = gods[pillar];
        require(g && g.stem.char === chart[pillar].stem.char && g.branch === chart[pillar].branch.char
          && Array.isArray(g.hidden_stems));
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

    const evidenceMarkup = (e, rootMatch = false) => `
      <div class="context-evidence-row${rootMatch ? ' is-context-evidence' : ''}" data-evidence-pillar="${esc(e.pillar)}" data-evidence-char="${esc(e.char)}">
        <div class="context-evidence-identity">
          <span>${esc(e.pinyin)} ${esc(e.char)} · ${esc(elementLabel(e))}</span>
          <span class="hidden-stem-type">${esc(e.component === 'stem' ? t('context_visible') : t('qi_' + e.qi_type))}</span>
        </div>
        <div class="context-evidence-role">${esc(t('ten_god_' + e.ten_god))}${rootMatch ? ` · ${esc(t('context_match_' + e.match))}` : ''}</div>
      </div>`;

    const branchMarkup = (pillar, evidence, roots = false) => {
      const branch = chart[pillar].branch;
      return `<div class="relationship-member">
        <div class="relationship-position">${esc(chart[pillar].label)}</div>
        <div class="relationship-identity">${esc(branch.pinyin)} ${esc(branch.char)}</div>
        <div class="relationship-element">${esc(branch.element_label)}</div>
        <div class="context-evidence-list">${evidence.map((e) => evidenceMarkup(e, roots)).join('')}</div>
      </div>`;
    };
    const presence = (records) => {
      const visible = records.some((e) => e.component === 'stem');
      const hidden = records.some((e) => e.component === 'hidden_stem');
      return t(visible && hidden ? 'context_both' : visible ? 'context_visible' : hidden ? 'context_hidden' : 'context_absent');
    };
    const supportMarkup = (name, records) => `<div class="context-support-group" data-support-group="${esc(name)}">
      <h4 class="relationship-position">${esc(t('context_' + name))}</h4>
      <p class="relationship-meta">${esc(presence(records))}</p>
      <div class="context-evidence-list">${DISPLAY.flatMap((pillar) => records.filter((e) => e.pillar === pillar)).map((e) => `
        <div class="context-support-source">
          <div class="context-source-position">${esc(chart[e.pillar].label)}${e.branch ? ` · ${esc(chart[e.pillar].branch.pinyin)} ${esc(e.branch)}` : ''}</div>
          ${evidenceMarkup(e)}
        </div>`).join('')}</div>
    </div>`;
    const makePage = (title, meta, content, note) => `
      <div class="relationship-detail-heading">
        <h3 id="context-detail-title">${esc(title)}</h3>
        <button type="button" class="reading-toggle" data-clear-context>${esc(t('relationship_clear'))}</button>
      </div>
      <p class="relationship-meta">${esc(meta)}</p>
      ${content}
      <p class="relationship-note">${esc(note)}</p>`;

    const clear = () => {
      selected = null;
      root.querySelectorAll('.is-context-source, .is-context-evidence').forEach((node) => {
        node.classList.remove('is-context-source', 'is-context-evidence');
      });
      controls.querySelectorAll('button').forEach((button) => button.setAttribute('aria-expanded', 'false'));
      detail.classList.add('hidden');
      detail.innerHTML = '';
      status.textContent = '';
    };
    const highlight = (e) => {
      const { card, rows } = sourcesFor(e);
      card.classList.add('is-context-source');
      // Mark exact rows on both surfaces; never open or flip cards automatically.
      rows.forEach((row) => row.classList.add('is-context-evidence'));
    };
    controls.addEventListener('click', (event) => {
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
      const page = pages[key];
      page.evidence.forEach(highlight);
      detail.innerHTML = page.markup;
      detail.classList.remove('hidden');
      status.textContent = t('context_selected', { topic: page.title });
    });
    const clearAndReturnFocus = () => {
      const button = controls.querySelector('[aria-expanded="true"]');
      clear();
      if (button) button.focus();
    };
    detail.addEventListener('click', (event) => {
      if (event.target.closest('[data-clear-context]')) clearAndReturnFocus();
    });
    root.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && selected !== null) {
        event.preventDefault();
        clearAndReturnFocus();
      }
    });

    const render = (data, chartData, gods) => {
      clear();
      pages = {};
      controls.innerHTML = '';
      heading.textContent = '';
      validate(data, chartData, gods);
      const dm = data.day_master;
      const season = data.season;
      const rootPillars = DISPLAY.filter((pillar) => data.roots.some((e) => e.pillar === pillar));
      const rootsLabel = t(rootPillars.length === 0 ? 'context_roots_none' : rootPillars.length === 1 ? 'context_roots_one' : 'context_roots_many', { count: rootPillars.length });
      heading.textContent = `${t('ten_god_day_master')} · ${dm.pinyin} — ${elementLabel(dm)}`;
      const labels = {
        season: t('context_month', { month: season.month_branch.pinyin }),
        roots: rootsLabel,
        support: t('context_support'),
      };
      const rootsContent = rootPillars.length
        ? `<div class="relationship-members" style="--member-count: ${rootPillars.length}">${rootPillars.map((pillar) => branchMarkup(pillar, data.roots.filter((e) => e.pillar === pillar), true)).join('')}</div>`
        : `<p class="relationship-note">${esc(t('context_no_roots'))}</p>`;
      pages = {
        season: {
          title: t('context_season'), evidence: season.hidden_stems,
          markup: makePage(t('context_season'), t('context_season_group', { season: t('context_' + season.name), element: t('element_' + season.element) }),
            `<div class="context-month-composition"><h4 class="relationship-position">${esc(t('context_month_composition'))}</h4>${branchMarkup('month', season.hidden_stems)}</div>`, t('context_season_note')),
        },
        roots: {
          title: t('context_roots'), evidence: data.roots,
          markup: makePage(t('context_roots'), rootsLabel, rootsContent, t('context_roots_note')),
        },
        support: {
          title: t('context_support'), evidence: [...data.support.companions, ...data.support.resources],
          markup: makePage(t('context_support'), t('context_support_meta'),
            `<div class="context-support-groups">${supportMarkup('companions', data.support.companions)}${supportMarkup('resources', data.support.resources)}</div>`, t('context_support_note')),
        },
      };
      controls.innerHTML = Object.entries(labels).map(([key, label]) => `
        <button type="button" class="reading-toggle context-toggle" data-context="${key}" aria-expanded="false" aria-controls="context-detail" aria-label="${esc(pages[key].title + ' · ' + label)}">${esc(label)}</button>`).join('');
    };
    return { render, clear };
  };
  window.EC_DAY_MASTER_CONTEXT = { create };
})();
