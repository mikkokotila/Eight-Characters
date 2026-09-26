// Whole-chart natal role presence. Roots stay separate from exact hidden/visible matches.
(() => {
  const ORDER = ['year', 'month', 'day', 'hour'];
  const DISPLAY = ['hour', 'day', 'month', 'year'];
  const ELEMENTS = ['wood', 'fire', 'earth', 'metal', 'water'];
  const GROUPS = [
    ['companion', ['friend', 'rob_wealth']],
    ['output', ['eating_god', 'hurting_officer']],
    ['wealth', ['indirect_wealth', 'direct_wealth']],
    ['authority', ['seven_killings', 'direct_officer']],
    ['resource', ['indirect_resource', 'direct_resource']],
  ];
  const FIELDS = ['id', 'pillar', 'component', 'branch', 'char', 'element', 'polarity', 'qi_type', 'ten_god'];
  const presence = (visible, hidden) => visible && hidden ? 'visible_and_hidden' : visible ? 'visible_only' : hidden ? 'hidden_only' : 'absent';
  const occurrenceId = (e) => e.component === 'stem' ? `visible:${e.pillar}` : `hidden:${e.pillar}:${e.char}`;
  const create = ({ root, translate: t, escape: esc, makePage, branchMarkup, evidenceMarkup, show }) => {
    const detail = root.querySelector('#context-detail');
    if (!detail || typeof show !== 'function') throw new Error('Roles view is incomplete.');
    let profile;
    let chart = {};
    let roleMap = {};
    let stemMap = {};
    let rolePages = {};
    let rootPages = {};
    let overviewPage;
    const require = (ok) => { if (!ok) throw new Error(t('roles_error')); };
    const same = (a, b, fields) => require(a && b && fields.every((key) => a[key] === b[key]));
    const compare = (actual, expected, inspected = null) => {
      require(Array.isArray(actual) && actual.length === expected.length);
      actual.forEach((e, i) => {
        same(e, expected[i], FIELDS);
        require(typeof e.pinyin === 'string' && e.pinyin.length > 0);
        if (inspected) require(e.match === (e.char === inspected.char ? 'exact_stem' : 'opposite_polarity'));
      });
    };
    const sorted = (records) => DISPLAY.flatMap((pillar) => records.filter((e) => e.pillar === pillar));
    const rootsLabel = (records) => {
      const count = new Set(records.map((r) => r.pillar)).size;
      return t(count === 0 ? 'context_roots_none' : count === 1 ? 'context_roots_one' : 'context_roots_many', { count });
    };
    const stemTitle = (s) => `${t('pillar_' + s.pillar)} · ${s.pinyin} ${s.char}`;
    const roleName = (name) => t('ten_god_' + name);
    const pLabel = (value) => t('roles_presence_' + value);
    const rootButton = (s, fromRole = '') => `
      <button type="button" class="reading-toggle" data-root-pillar="${esc(s.pillar)}" data-from-role="${esc(fromRole)}"
        aria-controls="context-detail" aria-label="${esc(t('roles_inspect_stem', { stem: stemTitle(s) }))}">${esc(rootsLabel(s.roots))}</button>`;
    const backButton = (name = '', pillar = '', roleFocus = '') => `
      <button type="button" class="reading-toggle roles-back" data-role-back="${esc(name)}" data-return-pillar="${esc(pillar)}" data-return-role="${esc(roleFocus)}"
        aria-controls="context-detail">${esc(name ? roleName(name) : t('roles_all'))}</button>`;

    const validate = (data, chartData, gods) => {
      require(data && data.policy === 'natal_roles_v1' && Array.isArray(data.groups) && data.groups.length === 5
        && Array.isArray(data.visible_stems) && data.visible_stems.length === 4);
      chart = Object.fromEntries(DISPLAY.map((name, i) => [name, chartData.pillars[i]]));
      same(data.day_master, chart.day.stem, ['char', 'pinyin', 'element', 'polarity']);
      const expected = [];
      ORDER.forEach((pillar) => {
        const g = gods[pillar];
        require(g && Array.isArray(g.hidden_stems));
        if (pillar !== 'day') expected.push({ ...g.stem, pillar, component: 'stem', branch: null, qi_type: null });
        g.hidden_stems.forEach((e) => expected.push({ ...e, pillar, component: 'hidden_stem', branch: g.branch }));
      });
      expected.forEach((e) => { e.id = occurrenceId(e); });
      const dmElement = ELEMENTS.indexOf(data.day_master.element);
      require(dmElement >= 0);
      data.groups.forEach((group, i) => {
        require(group && group.group === GROUPS[i][0] && group.element === ELEMENTS[(dmElement + i) % 5]
          && Array.isArray(group.roles) && group.roles.length === 2);
        group.roles.forEach((role, j) => {
          require(role && role.ten_god === GROUPS[i][1][j]);
          const visible = expected.filter((e) => e.ten_god === role.ten_god && e.component === 'stem');
          const hidden = expected.filter((e) => e.ten_god === role.ten_god && e.component === 'hidden_stem');
          compare(role.visible, visible); compare(role.hidden, hidden);
          require(role.presence === presence(visible.length > 0, hidden.length > 0));
        });
        require(group.presence === presence(group.roles.some((r) => r.visible.length), group.roles.some((r) => r.hidden.length)));
      });
      data.visible_stems.forEach((s, i) => {
        const pillar = ORDER[i];
        require(s && s.pillar === pillar && s.id === `visible:${pillar}`);
        same(s, chart[pillar].stem, ['char', 'pinyin', 'element', 'polarity']);
        require(s.ten_god === (pillar === 'day' ? 'day_master' : gods[pillar].stem.ten_god));
        const roots = expected.filter((e) => e.component === 'hidden_stem' && e.element === s.element);
        compare(s.roots, roots, s);
        const exact = roots.filter((e) => e.char === s.char).map((e) => e.id);
        require(Array.isArray(s.exact_hidden_matches) && s.exact_hidden_matches.length === exact.length
          && exact.every((id, index) => id === s.exact_hidden_matches[index]));
      });
    };

    // Each page carries its path, as the chart's address names it: roles, roles/<role>,
    // roles/stem/<pillar>, or roles/<role>/stem/<pillar> when reached from that role.
    const buildOverview = () => ({
      path: 'roles', title: t('roles_title'), evidence: [],
      markup: makePage(t('roles_title'), t('roles_overview_meta'), `
        <div class="role-overview">${profile.groups.map((group) => `
          <div class="role-group" data-role-group="${esc(group.group)}">
            <div class="role-group-heading"><h4 class="relationship-position">${esc(t('roles_group_' + group.group))}</h4>
              <span class="relationship-element">${esc(t('element_' + group.element))}</span>
              <span class="role-presence">${esc(pLabel(group.presence))}</span></div>
            ${group.roles.map((role) => `
              <button type="button" class="role-choice" data-role="${esc(role.ten_god)}" aria-controls="context-detail">
                <span class="role-choice-name">${esc(roleName(role.ten_god))}</span>
                <span class="role-presence">${esc(pLabel(role.presence))}</span>
              </button>`).join('')}
          </div>`).join('')}</div>
        <section class="role-visible-stems" aria-labelledby="visible-stems-heading">
          <h4 id="visible-stems-heading" class="relationship-position">${esc(t('roles_visible_stems'))}</h4>
          <p class="relationship-meta">${esc(t('roles_visible_meta'))}</p>
          <div class="role-stem-grid">${DISPLAY.map((pillar) => {
            const s = stemMap[pillar];
            return `<div class="role-stem-entry">
              <div class="context-source-position">${esc(t('pillar_' + pillar))}</div>
              <div class="relationship-identity">${esc(s.pinyin)} ${esc(s.char)}</div>
              <div class="role-presence">${esc(roleName(s.ten_god))}</div>${rootButton(s)}
            </div>`;
          }).join('')}</div>
        </section>`, t('roles_overview_note')),
    });

    const exactVisibleMarkup = (record, name) => {
      const matches = DISPLAY.map((pillar) => stemMap[pillar]).filter((s) => s.exact_hidden_matches.includes(record.id));
      if (!matches.length) return `<p class="role-exact">${esc(t('roles_no_exact_visible'))}</p>`;
      return `<div class="role-exact"><span>${esc(t('roles_exact_visible'))}</span> ${matches.map((s) => `
        <button type="button" class="reading-toggle" data-root-pillar="${esc(s.pillar)}" data-from-role="${esc(name)}" aria-controls="context-detail">
          ${esc(t('pillar_' + s.pillar))}${s.pillar === 'day' ? ` · ${esc(roleName('day_master'))}` : ''}
        </button>`).join(' · ')}</div>`;
    };
    const roleSource = (record, name) => `
      <div class="role-occurrence" data-role-occurrence="${esc(record.id)}">
        <div class="context-source-position">${esc(t('pillar_' + record.pillar))}${record.branch ? ` · ${esc(chart[record.pillar].branch.pinyin)} ${esc(record.branch)}` : ''}</div>
        ${evidenceMarkup(record)}
        ${record.component === 'stem' ? rootButton(stemMap[record.pillar], name) : exactVisibleMarkup(record, name)}
      </div>`;
    const buildRolePage = (name) => {
      const role = roleMap[name];
      const content = role.presence === 'absent'
        ? `<p class="relationship-note role-empty">${esc(t('roles_absent_scope', { role: roleName(name) }))}</p>`
        : `<div class="role-sources">${['visible', 'hidden'].map((kind) => `
            <section class="role-source-kind" data-role-surface="${kind}">
              <h4 class="relationship-position">${esc(t('roles_' + kind))}</h4>
              <div class="context-evidence-list">${role[kind].length ? sorted(role[kind]).map((e) => roleSource(e, name)).join('')
                : `<p class="relationship-meta">${esc(t('context_absent'))}</p>`}</div>
            </section>`).join('')}</div>`;
      return { path: `roles/${name}`, title: roleName(name), evidence: [...role.visible, ...role.hidden],
        markup: makePage(roleName(name), pLabel(role.presence), `${backButton('', '', name)}${content}`, t('roles_role_note')) };
    };
    const buildRootPage = (pillar, fromRole) => {
      const s = stemMap[pillar];
      const rootPillars = DISPLAY.filter((name) => s.roots.some((r) => r.pillar === name));
      const content = s.roots.length ? `<div class="relationship-members" style="--member-count: ${rootPillars.length}">
        ${rootPillars.map((name) => branchMarkup(name, s.roots.filter((r) => r.pillar === name), true)).join('')}</div>`
        : `<p class="relationship-note role-empty">${esc(t('roles_no_roots', { stem: `${s.pinyin} ${s.char}` }))}</p>`;
      const reference = { ...s, component: 'stem', branch: null, qi_type: null };
      return { path: fromRole ? `roles/${fromRole}/stem/${pillar}` : `roles/stem/${pillar}`,
        title: `${t('roles_stem_roots')} · ${stemTitle(s)}`, evidence: s.roots, reference,
        markup: makePage(`${t('roles_stem_roots')} · ${stemTitle(s)}`,
          `${roleName(s.ten_god)} · ${rootsLabel(s.roots)}`,
          `${backButton(fromRole, pillar)}${content}
            <p class="relationship-meta role-exact-summary">${esc(t('roles_exact_count', { count: s.exact_hidden_matches.length }))}</p>`,
          t('roles_roots_note')) };
    };

    detail.addEventListener('click', (event) => {
      const roleButton = event.target.closest('button[data-role]');
      if (roleButton) {
        const name = roleButton.dataset.role;
        require(Object.hasOwn(rolePages, name));
        show(rolePages[name], '#context-detail-title');
        return;
      }
      const stemButton = event.target.closest('button[data-root-pillar]');
      if (stemButton) {
        const { rootPillar: pillar, fromRole } = stemButton.dataset;
        require(Object.hasOwn(stemMap, pillar) && (fromRole === '' || Object.hasOwn(roleMap, fromRole)));
        show(rootPages[`${pillar}:${fromRole}`], '#context-detail-title');
        return;
      }
      const back = event.target.closest('button[data-role-back]');
      if (back) {
        const { roleBack: name, returnPillar: pillar, returnRole: roleFocus } = back.dataset;
        require(name === '' || Object.hasOwn(rolePages, name));
        require(pillar === '' || Object.hasOwn(stemMap, pillar));
        // The source control is restored with the page, so keyboard users keep their place.
        require(roleFocus === '' || Object.hasOwn(roleMap, roleFocus));
        const selector = pillar ? `[data-root-pillar="${pillar}"]`
          : roleFocus ? `[data-role="${roleFocus}"]` : null;
        show(name ? rolePages[name] : overviewPage, selector || '#visible-stems-heading');
      }
    });

    const render = (data, chartData, gods) => {
      profile = null; roleMap = {}; stemMap = {}; rolePages = {}; rootPages = {};
      validate(data, chartData, gods);
      profile = data;
      roleMap = Object.fromEntries(data.groups.flatMap((g) => g.roles).map((r) => [r.ten_god, r]));
      stemMap = Object.fromEntries(data.visible_stems.map((s) => [s.pillar, s]));
      overviewPage = buildOverview();
      // Build every detail now: missing translations fail before a partial chart is shown.
      Object.keys(roleMap).forEach((name) => { rolePages[name] = buildRolePage(name); });
      ORDER.forEach((pillar) => {
        ['', ...Object.keys(roleMap)].forEach((fromRole) => {
          rootPages[`${pillar}:${fromRole}`] = buildRootPage(pillar, fromRole);
        });
      });
      return overviewPage;
    };
    return { render };
  };
  window.EC_ROLES = { create };
})();
