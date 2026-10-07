// Presence only: the cards keep their natal elements and their existing gestures.
(() => {
  const DISPLAY_ORDER = ['hour', 'day', 'month', 'year'];
  // What each kind is, as the API states it: its component, how many members it has,
  // how complete it is, and whether a transformation could be assessed at all.
  const KIND_RULES = {
    stem_combination: { component: 'stem', sizes: [2], transformation: 'not_assessed' },
    branch_combination: { component: 'branch', sizes: [2], transformation: 'not_assessed' },
    branch_clash: { component: 'branch', sizes: [2], transformation: 'not_applicable' },
    harmony_frame: { component: 'branch', sizes: [3], transformation: 'not_assessed' },
    half_frame: { component: 'branch', sizes: [2], half: true, transformation: 'not_assessed' },
    directional_combination: { component: 'branch', sizes: [3], transformation: 'not_assessed' },
    punishment: { component: 'branch', sizes: [2, 3], transformation: 'not_applicable' },
    half_punishment: { component: 'branch', sizes: [2], half: true, transformation: 'not_applicable' },
    self_punishment: { component: 'branch', sizes: [2], transformation: 'not_applicable' },
    harm: { component: 'branch', sizes: [2], transformation: 'not_applicable' },
  };
  // The shared families each keep an arc of their own, as they always have.
  const OWN_ARC = ['stem_combination', 'branch_combination', 'branch_clash', 'harmony_frame'];
  // The arcs' rows hold four levels, and an arc at most three strands. No combination of
  // stems or branches needs more (tests/test_api_interactions.py walks every one with
  // this layout).
  const ARC_LEVELS = 4;
  const ARC_STRANDS = 3;

  // Each arc spans its members' columns. A relationship of the families the canon adds
  // to the shared ones joins an arc that already spans the same columns, as a strand
  // inside it; where none does, it has an arc of its own. An arc rises one level for
  // each column it spans, and higher still to stand above every arc it spans or crosses:
  // narrow arcs are placed first, each at least one level above the highest it
  // overlaps. Arcs that only meet at a card may share a level.
  const arcLayout = (relationships) => {
    const slots = [];
    const strands = relationships.map((relationship) => {
      const columns = relationship.members.map((member) => DISPLAY_ORDER.indexOf(member.pillar)).sort((a, b) => a - b);
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
    if (slots.some((slot) => slot.strands.length > ARC_STRANDS)) {
      throw new Error(`A relationship arc needs more than ${ARC_STRANDS} strands.`);
    }
    const byWidth = [...slots].sort((a, b) => (a.to - a.from) - (b.to - b.from) || a.from - b.from);
    byWidth.forEach((slot, index) => {
      const overlapped = byWidth.slice(0, index)
        .filter((other) => Math.max(slot.from, other.from) < Math.min(slot.to, other.to));
      slot.level = Math.max(slot.to - slot.from, 1 + Math.max(0, ...overlapped.map((other) => other.level)));
    });
    if (slots.some((slot) => slot.level > ARC_LEVELS)) {
      throw new Error(`Relationship arcs need more than ${ARC_LEVELS} levels.`);
    }
    // A strand stands a little inside the one before it: lower, and narrower.
    const height = (strand) => strand.slot.level - strand.strand / ARC_STRANDS;
    // The feet on one card, left to right: arcs from the left, lowest first; a triple's
    // middle member; arcs to the right, highest first. No arc's foot then crosses
    // another arc that ends on the same card. Separate arcs' feet stand a spread apart,
    // the strands of one arc half a spread.
    DISPLAY_ORDER.forEach((_, column) => {
      const feet = [
        ...strands.filter((s) => s.to === column).sort((a, b) => height(a) - height(b)).map((s) => [s, 'to']),
        ...strands.filter((s) => s.columns.length === 3 && s.columns[1] === column).map((s) => [s, 'middle']),
        ...strands.filter((s) => s.from === column).sort((a, b) => height(b) - height(a)).map((s) => [s, 'from']),
      ];
      const at = [];
      feet.forEach(([strand], index) => {
        at.push(index === 0 ? 0 : at[index - 1] + (feet[index - 1][0].slot === strand.slot ? 0.5 : 1));
      });
      const middle = at.length ? at[at.length - 1] / 2 : 0;
      feet.forEach(([strand, end], index) => { strand.feet[end] = at[index] - middle; });
    });
    strands.forEach((strand) => { strand.level = strand.slot.level; });
    return strands;
  };

  const NOTE_KEY = {
    stem_combination: 'relationship_combination_note',
    branch_combination: 'relationship_combination_note',
    branch_clash: 'relationship_clash_note',
    harmony_frame: 'relationship_frame_note',
    half_frame: 'relationship_half_frame_note',
    directional_combination: 'relationship_directional_note',
    punishment: 'relationship_punishment_note',
    half_punishment: 'relationship_punishment_note',
    self_punishment: 'relationship_punishment_note',
    harm: 'relationship_harm_note',
  };

  const create = ({ root, translate: t, escape: esc, spot, canon, beforeSelect }) => {
    const list = root.querySelector('#relationship-list');
    const empty = root.querySelector('#relationship-empty');
    const about = root.querySelector('#relationship-about');
    const detail = root.querySelector('#relationship-detail');
    const status = root.querySelector('#relationship-status');
    const pillars = root.querySelector('#pillars');
    if (!list || !empty || !about || !detail || !status || !pillars || !spot || !canon) {
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

    // A member points at its card; a branch's roles, each at its hidden stem.
    const memberMarkup = (relationship, member) => {
      const chart = chartByPillar[member.pillar];
      const data = tenGods[member.pillar];
      const component = chart[relationship.component];
      const identity = `${member.pinyin} ${member.char}`;
      const elementLabel = relationship.component === 'stem' ? component.label : component.element_label;
      const stem = relationship.component === 'stem';
      const roles = stem ? [data.stem] : data.hidden_stems;
      const card = `${relationship.component}:${member.pillar}`;
      return `
        <div class="relationship-member"${spot.attr([card])}>
          <div class="relationship-position">${esc(t('pillar_' + member.pillar))}</div>
          <div class="relationship-identity">${esc(identity)}</div>
          <div class="relationship-element">${esc(elementLabel)}</div>
          <div class="relationship-roles">${roles.map((role) => `
            <div class="hidden-stem-item"${spot.attr([stem ? card : `hidden:${member.pillar}:${role.char}`])}>
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
      const noteKey = NOTE_KEY[relationship.kind];
      const displayMembers = [...relationship.members].sort(
        (a, b) => DISPLAY_ORDER.indexOf(a.pillar) - DISPLAY_ORDER.indexOf(b.pillar)
      );
      // What the canon says of it sits under its finding, before its members.
      detail.innerHTML = `
        <div class="relationship-detail-heading">
          <h3 id="relationship-detail-title">${esc(labelFor(relationship))}</h3>
        </div>
        <p class="relationship-meta">${esc(meta.join(' · '))}</p>
        ${canon.relationship(relationship.id)}
        <div class="relationship-members" style="--member-count: ${relationship.members.length}">
          ${displayMembers.map((member) => memberMarkup(relationship, member)).join('')}
        </div>
        <p class="relationship-note">${esc([t(noteKey), canon.note()].filter(Boolean).join(' '))}</p>`;
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
        `--strand: ${arc.strand}`, `--foot-from: ${arc.feet.from}`, `--foot-to: ${arc.feet.to}`,
      ].join('; ');
      // A triple's middle member stands under the arc where it is (at) of the way
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
        const rule = KIND_RULES[relationship.kind];
        const size = Array.isArray(relationship.members) ? relationship.members.length : 0;
        if (!rule || typeof relationship.id !== 'string' || ids.has(relationship.id)
          || relationship.component !== rule.component || !rule.sizes.includes(size)
          || new Set(relationship.members.map((member) => member.pillar)).size !== size
          || typeof relationship.adjacent !== 'boolean'
          || relationship.completeness !== (rule.half ? 'half' : size === 3 ? 'complete' : 'pair')
          || relationship.transformation !== rule.transformation) {
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
      // Each entry points at its cards and its arc.
      list.innerHTML = relationships.map((relationship, index) => `
        <button type="button" class="relationship-chip" data-kind="${esc(relationship.kind)}"
          data-relationship-index="${index}" data-relationship="${esc(relationship.id)}"${spot.attr([
            ...relationship.members.map((member) => `${relationship.component}:${member.pillar}`), `arc:${relationship.id}`])}
          aria-expanded="false" aria-controls="relationship-detail">
          <span class="relationship-mark" aria-hidden="true"></span>
          <span>${esc(labelFor(relationship))}</span>${canon.chipLine(relationship.id)}
        </button>`).join('');
      empty.classList.toggle('hidden', relationships.length !== 0);
      about.innerHTML = canon.relationshipsAbout();
    };

    // A relationship's name as the list names it, for the pages that link to it.
    const labelOf = (id) => {
      const relationship = entries.find((entry) => entry.id === id);
      if (!relationship) throw new Error(`Unknown relationship ${id}.`);
      return labelFor(relationship);
    };
    return { render, clear, labelOf };
  };

  window.EC_RELATIONSHIPS = { create };
})();
