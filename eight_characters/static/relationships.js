// Presence only: the cards keep their natal elements and their existing gestures.
(() => {
  const DISPLAY_ORDER = ['hour', 'day', 'month', 'year'];
  const KINDS = ['stem_combination', 'branch_combination', 'branch_clash', 'harmony_frame'];
  // The arcs' rows hold four levels. No combination of stems or branches needs
  // more (tests/test_api_interactions.py walks every one with this layout).
  const ARC_LEVELS = 4;

  // Each arc spans its members' columns. It rises one level for each column it
  // spans, and higher still to stand above every arc it spans or crosses: narrow
  // arcs are placed first, each at least one level above the highest it
  // overlaps. Arcs that only meet at a card may share a level.
  const arcLayout = (relationships) => {
    const arcs = relationships.map((relationship) => {
      const columns = relationship.members.map((member) => DISPLAY_ORDER.indexOf(member.pillar)).sort((a, b) => a - b);
      return { relationship, columns, from: columns[0], to: columns[columns.length - 1], feet: {} };
    });
    const byWidth = [...arcs].sort((a, b) => (a.to - a.from) - (b.to - b.from) || a.from - b.from);
    byWidth.forEach((arc, index) => {
      const overlapped = byWidth.slice(0, index)
        .filter((other) => Math.max(arc.from, other.from) < Math.min(arc.to, other.to));
      arc.level = Math.max(arc.to - arc.from, 1 + Math.max(0, ...overlapped.map((other) => other.level)));
    });
    if (arcs.some((arc) => arc.level > ARC_LEVELS)) {
      throw new Error(`Relationship arcs need more than ${ARC_LEVELS} levels.`);
    }
    // The feet on one card, left to right: arcs from the left, lowest first; a frame's
    // middle member; arcs to the right, highest first. No arc's foot then crosses
    // another arc that ends on the same card.
    DISPLAY_ORDER.forEach((_, column) => {
      const feet = [
        ...arcs.filter((arc) => arc.to === column).sort((a, b) => a.level - b.level).map((arc) => [arc, 'to']),
        ...arcs.filter((arc) => arc.columns.length === 3 && arc.columns[1] === column).map((arc) => [arc, 'middle']),
        ...arcs.filter((arc) => arc.from === column).sort((a, b) => b.level - a.level).map((arc) => [arc, 'from']),
      ];
      feet.forEach(([arc, end], index) => { arc.feet[end] = index - (feet.length - 1) / 2; });
    });
    return arcs;
  };

  const create = ({ root, translate: t, escape: esc, beforeSelect }) => {
    const list = root.querySelector('#relationship-list');
    const empty = root.querySelector('#relationship-empty');
    const detail = root.querySelector('#relationship-detail');
    const status = root.querySelector('#relationship-status');
    const pillars = root.querySelector('#pillars');
    if (!list || !empty || !detail || !status || !pillars) {
      throw new Error('Relationship view is incomplete.');
    }
    let entries = [];
    let selected = null;
    let chartByPillar = {};
    let tenGods = {};

    const cardFor = (relationship, member) => {
      const card = root.querySelector(
        `.card.${relationship.component}[data-pillar="${member.pillar}"]`
      );
      if (!card || card.dataset.char !== member.char) {
        throw new Error(`Relationship does not match the ${member.pillar} card.`);
      }
      return card;
    };

    // Plain names, in the chart's own order (Hour, Day, Month, Year).
    const labelFor = (relationship) => {
      const positions = DISPLAY_ORDER.filter((pillar) => relationship.members.some((member) => member.pillar === pillar))
        .map((pillar) => t('pillar_' + pillar));
      return `${positions.join('–')} · ${t('relationship_' + relationship.kind)}`;
    };

    const clear = () => {
      selected = null;
      root.removeAttribute('data-relationship-kind');
      root.querySelectorAll('.card.is-related').forEach((card) => card.classList.remove('is-related'));
      pillars.querySelectorAll('.relationship-arcs').forEach((band) => band.classList.remove('has-selection'));
      pillars.querySelectorAll('.relationship-arc.is-active').forEach((arc) => arc.classList.remove('is-active'));
      list.querySelectorAll('button').forEach((button) => {
        button.setAttribute('aria-expanded', 'false');
        button.classList.remove('is-active');
      });
      detail.classList.add('hidden');
      detail.innerHTML = '';
      status.textContent = '';
    };

    const memberMarkup = (relationship, member) => {
      const chart = chartByPillar[member.pillar];
      const data = tenGods[member.pillar];
      const component = chart[relationship.component];
      const identity = `${member.pinyin} ${member.char}`;
      const elementLabel = relationship.component === 'stem' ? component.label : component.element_label;
      const roles = relationship.component === 'stem' ? [data.stem] : data.hidden_stems;
      return `
        <div class="relationship-member">
          <div class="relationship-position">${esc(t('pillar_' + member.pillar))}</div>
          <div class="relationship-identity">${esc(identity)}</div>
          <div class="relationship-element">${esc(elementLabel)}</div>
          <div class="relationship-roles">${roles.map((role) => `
            <div class="hidden-stem-item">
              <span class="hidden-stem-dot ${esc(role.element)}"></span>
              <span class="hidden-stem-label">${esc(t('ten_god_' + role.ten_god))}</span>
              ${role.qi_type ? `<span class="hidden-stem-type">${esc(t('qi_' + role.qi_type))}</span>` : ''}
            </div>`).join('')}
          </div>
        </div>`;
    };

    const select = (relationship, button) => {
      const wasSelected = selected === relationship.id;
      clear();
      if (wasSelected) return;
      beforeSelect();
      selected = relationship.id;
      root.dataset.relationshipKind = relationship.kind;
      relationship.members.forEach((member) => cardFor(relationship, member).classList.add('is-related'));
      const arc = [...pillars.querySelectorAll('.relationship-arc')]
        .find((node) => node.dataset.relationshipId === relationship.id);
      if (!arc) throw new Error(`Relationship ${relationship.id} has no arc.`);
      pillars.querySelectorAll('.relationship-arcs').forEach((band) => band.classList.add('has-selection'));
      arc.classList.add('is-active');
      button.setAttribute('aria-expanded', 'true');
      button.classList.add('is-active');
      const meta = [t(relationship.adjacent ? 'relationship_adjacent' : 'relationship_non_adjacent')];
      if (relationship.potential_element !== null) {
        meta.push(t('relationship_potential_element', {element: t('element_' + relationship.potential_element)}));
      }
      const noteKey = relationship.kind === 'branch_clash'
        ? 'relationship_clash_note'
        : relationship.kind === 'harmony_frame' ? 'relationship_frame_note' : 'relationship_combination_note';
      const displayMembers = [...relationship.members].sort(
        (a, b) => DISPLAY_ORDER.indexOf(a.pillar) - DISPLAY_ORDER.indexOf(b.pillar)
      );
      detail.innerHTML = `
        <div class="relationship-detail-heading">
          <h3 id="relationship-detail-title">${esc(labelFor(relationship))}</h3>
        </div>
        <p class="relationship-meta">${esc(meta.join(' · '))}</p>
        <div class="relationship-members" style="--member-count: ${relationship.members.length}">
          ${displayMembers.map((member) => memberMarkup(relationship, member)).join('')}
        </div>
        <p class="relationship-note">${esc(t(noteKey))}</p>`;
      detail.classList.remove('hidden');
      status.textContent = t('relationship_selected', {relationship: labelFor(relationship)});
    };

    list.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-relationship-index]');
      if (!button) return;
      const relationship = entries[Number(button.dataset.relationshipIndex)];
      if (!relationship) throw new Error('Unknown relationship selection.');
      select(relationship, button);
    });
    const clearAndReturnFocus = () => {
      const button = list.querySelector('button.is-active');
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

    const arcMarkup = (arc) => {
      const style = [
        `grid-column: ${arc.from + 1} / ${arc.to + 2}`, `--span: ${arc.to - arc.from}`, `--level: ${arc.level}`,
        `--foot-from: ${arc.feet.from}`, `--foot-to: ${arc.feet.to}`,
      ].join('; ');
      // A frame's middle member stands under the arc where it is (at) of the way
      // across; half an ellipse is sqrt(1 - x²) of its rise there, x from -1 to 1.
      const at = arc.columns.length === 3 ? (arc.columns[1] - arc.from) / (arc.to - arc.from) : null;
      const middle = at === null ? ''
        : `<span class="relationship-arc-foot" style="--at: ${at}; --reach: ${Math.sqrt(1 - (2 * at - 1) ** 2)}; --foot: ${arc.feet.middle}"></span>`;
      // A branch arc's feet rise through the hidden stems' row to its cards.
      const rises = arc.relationship.component === 'branch'
        ? '<span class="relationship-arc-rise is-from"></span><span class="relationship-arc-rise is-to"></span>' : '';
      return `<span class="relationship-arc" data-arc-kind="${esc(arc.relationship.kind)}" data-relationship-id="${esc(arc.relationship.id)}" style="${style}">
        <span class="relationship-arc-line"></span>${rises}${middle}
      </span>`;
    };

    const render = (relationships, chartData, tenGodsData) => {
      clear();
      entries = [];
      list.innerHTML = '';
      empty.classList.add('hidden');
      pillars.querySelectorAll('.relationship-arcs').forEach((band) => band.remove());
      if (!Array.isArray(relationships) || chartData.pillars.length !== DISPLAY_ORDER.length) {
        throw new Error(t('interactions_error'));
      }
      chartByPillar = Object.fromEntries(DISPLAY_ORDER.map((name, index) => [name, chartData.pillars[index]]));
      tenGods = tenGodsData;
      const ids = new Set();
      relationships.forEach((relationship) => {
        const size = relationship.kind === 'harmony_frame' ? 3 : 2;
        if (!KINDS.includes(relationship.kind) || typeof relationship.id !== 'string' || ids.has(relationship.id)
          || relationship.component !== (relationship.kind === 'stem_combination' ? 'stem' : 'branch')
          || !Array.isArray(relationship.members) || relationship.members.length !== size
          || new Set(relationship.members.map((member) => member.pillar)).size !== size
          || typeof relationship.adjacent !== 'boolean'
          || relationship.completeness !== (size === 3 ? 'complete' : 'pair')
          || relationship.transformation !== (relationship.kind === 'branch_clash' ? 'not_applicable' : 'not_assessed')) {
          throw new Error(t('interactions_error'));
        }
        ids.add(relationship.id);
        relationship.members.forEach((member) => {
          if (!DISPLAY_ORDER.includes(member.pillar) || typeof member.pinyin !== 'string') {
            throw new Error(t('interactions_error'));
          }
          cardFor(relationship, member);
          const data = tenGods[member.pillar];
          if (!data || (relationship.component === 'stem' ? data.stem.char : data.branch) !== member.char) {
            throw new Error(t('interactions_error'));
          }
          // Validate every detail translation before showing a partially usable chart.
          memberMarkup(relationship, member);
        });
        if (relationship.potential_element !== null) t('element_' + relationship.potential_element);
      });
      entries = relationships;
      // Stem combinations above the stems, branch relations below the branches. The
      // list in the panel says what the arcs draw.
      ['stem', 'branch'].forEach((component) => {
        const band = document.createElement('div');
        band.className = 'relationship-arcs';
        band.dataset.component = component;
        band.setAttribute('aria-hidden', 'true');
        band.innerHTML = arcLayout(relationships.filter((relationship) => relationship.component === component))
          .map(arcMarkup).join('');
        pillars.append(band);
      });
      list.innerHTML = relationships.map((relationship, index) => `
        <button type="button" class="relationship-chip" data-kind="${esc(relationship.kind)}"
          data-relationship-index="${index}" data-relationship="${esc(relationship.id)}"
          aria-expanded="false" aria-controls="relationship-detail">
          <span class="relationship-mark" aria-hidden="true"></span>
          <span>${esc(labelFor(relationship))}</span>
        </button>`).join('');
      empty.classList.toggle('hidden', relationships.length !== 0);
    };

    return { render, clear };
  };

  window.EC_RELATIONSHIPS = { create };
})();
