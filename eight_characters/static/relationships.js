// Presence only: the cards keep their natal elements and their existing gestures.
(() => {
  const DISPLAY_ORDER = ['hour', 'day', 'month', 'year'];
  const KINDS = ['stem_combination', 'branch_combination', 'branch_clash', 'harmony_frame'];

  const create = ({ root, translate: t, escape: esc, beforeSelect }) => {
    const list = root.querySelector('#relationship-list');
    const empty = root.querySelector('#relationship-empty');
    const detail = root.querySelector('#relationship-detail');
    const status = root.querySelector('#relationship-status');
    if (!list || !empty || !detail || !status) {
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

    const labelFor = (relationship) => {
      const positions = relationship.members.map((member) => t('pillar_' + member.pillar));
      return `${positions.join('–')} · ${t('relationship_' + relationship.kind)}`;
    };

    const clear = () => {
      selected = null;
      root.removeAttribute('data-relationship-kind');
      root.querySelectorAll('.card.is-related').forEach((card) => card.classList.remove('is-related'));
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
          <div class="relationship-position">${esc(chart.label)}</div>
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
          <button type="button" class="reading-toggle" data-clear-relationship>${esc(t('relationship_clear'))}</button>
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
    detail.addEventListener('click', (event) => {
      if (event.target.closest('[data-clear-relationship]')) clearAndReturnFocus();
    });
    root.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && selected !== null) {
        event.preventDefault();
        clearAndReturnFocus();
      }
    });

    const render = (relationships, chartData, tenGodsData) => {
      clear();
      entries = [];
      list.innerHTML = '';
      empty.classList.add('hidden');
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
      list.innerHTML = relationships.map((relationship, index) => `
        <button type="button" class="relationship-chip" data-kind="${esc(relationship.kind)}"
          data-relationship-index="${index}" aria-expanded="false" aria-controls="relationship-detail">
          <span class="relationship-mark" aria-hidden="true"></span>
          <span>${esc(labelFor(relationship))}</span>
        </button>`).join('');
      empty.classList.toggle('hidden', relationships.length !== 0);
    };

    return { render, clear };
  };

  window.EC_RELATIONSHIPS = { create };
})();
