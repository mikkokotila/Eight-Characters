// The parameter pane: the run settings, conventions and model parameters a reader can
// change, as GET /api/evolution_controls lists them, and Recompute, which asks
// POST /api/evolution_explorer for the chart again with them.
//
// What the graph was computed with comes back as graph_data.parameters. An edit is a
// draft until a recompute applies it, and a recompute sends every value that differs
// from its default, so what was applied before stays applied.
(function () {
  'use strict';

  const SECTIONS = ['run', 'conventions', 'model'];
  const CLUSTER_WEIGHTS = ['CLUSTER_ALPHA', 'CLUSTER_BETA', 'CLUSTER_GAMMA'];
  const OPEN_GROUPS = new Set(['Run']);
  const SEED_RANGE = 2147483648;

  const layout = document.querySelector('.layout');
  const toggle = document.getElementById('parameterToggle');
  const pane = document.getElementById('parameterPane');
  const closeButton = document.getElementById('parameterClose');
  const statusLine = document.getElementById('parameterStatus');
  const controlsRoot = document.getElementById('parameterControls');
  const recomputeButton = document.getElementById('parameterRecompute');
  const discardButton = document.getElementById('parameterDiscard');
  const resetButton = document.getElementById('parameterReset');
  if (
    !layout || !toggle || !pane || !closeButton || !statusLine || !controlsRoot ||
    !recomputeButton || !discardButton || !resetButton
  ) {
    throw new Error('The parameter pane is incomplete.');
  }

  let explorer = window.EC_EXPLORER || null;
  let catalogue = null;
  let catalogueRequest = null;
  let catalogueError = null;
  let applied = explorer ? explorer.parameters : null;
  // 'section.id' to a value that differs from the applied one.
  const drafts = new Map();
  // 'section.id' to what is wrong with the entry typed into it.
  const invalid = new Map();
  let inFlight = null;
  let outcome = null;
  let newSeedEachRun = false;

  const keyOf = (section, id) => `${section}.${id}`;
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const escapeHtml = (value) =>
    String(value).replace(/[&<>"']/g, (char) => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]
    ));
  const decimals = (step) => (Number.isInteger(step) ? 0 : String(step).split('.')[1].length);

  function controlOf(key) {
    const [section, id] = key.split('.');
    const control = catalogue[section].find((item) => item.id === id);
    if (!control) throw new Error(`No control ${key}.`);
    return control;
  }

  function appliedValue(key) {
    const [section, id] = key.split('.');
    if (!applied || !(id in applied[section])) {
      throw new Error(`The graph does not say what ${key} it was computed with.`);
    }
    return applied[section][id];
  }

  const currentValue = (key) => (drafts.has(key) ? drafts.get(key) : appliedValue(key));

  // What an entry is called: a control, or one cell of a table ('model.ID[row,column]').
  function entryLabel(entry) {
    const [, key, index] = entry.match(/^([^[]+)(?:\[(.+)\])?$/);
    const control = controlOf(key);
    if (index === undefined) return control.label;
    const [row, column] = index.split(',').map(Number);
    const cell = column === undefined
      ? control.columns[row]
      : `${control.rows[row]} to ${control.columns[column]}`;
    return `${control.label}, ${cell}`;
  }

  // An edit that matches what the chart was computed with changes nothing. While a
  // recompute runs, the chart may yet take other values, so every edit is kept until
  // the answer lands; pruneDrafts then drops those that match it.
  function setDraft(key, value) {
    if (!inFlight && same(value, appliedValue(key))) drafts.delete(key);
    else drafts.set(key, value);
  }

  function pruneDrafts() {
    [...drafts.entries()].forEach(([key, value]) => {
      if (same(value, appliedValue(key))) drafts.delete(key);
    });
  }

  const usable = () => Boolean(explorer && explorer.birth && catalogue && applied);

  // ── Status ──

  function changedFromDefaults(values) {
    let count = 0;
    SECTIONS.forEach((section) => {
      catalogue[section].forEach((control) => {
        if (!same(values(keyOf(section, control.id)), control.default)) count += 1;
      });
    });
    return count;
  }

  function describeValues(count) {
    if (count === 0) return 'the defaults';
    return count === 1 ? '1 value changed from its default' : `${count} values changed from their defaults`;
  }

  function statusText() {
    if (!explorer) return 'The chart has not been drawn, so there is nothing to recompute yet.';
    if (!explorer.birth) {
      return 'This is the bundled sample chart. Open the explorer from a chart to change its parameters.';
    }
    if (catalogueError) return `Could not load the parameters: ${catalogueError}`;
    if (!catalogue) return 'Loading the parameters…';
    if (inFlight) return 'Recomputing…';
    const parts = [];
    if (outcome) parts.push(outcome.text);
    parts.push(`Computed with ${describeValues(changedFromDefaults(appliedValue))}.`);
    if (invalid.size) {
      const [entry, message] = invalid.entries().next().value;
      parts.push(`Fix ${entryLabel(entry)} before recomputing: ${message}`);
    } else if (drafts.size) {
      parts.push(drafts.size === 1 ? '1 change to apply.' : `${drafts.size} changes to apply.`);
    } else if (newSeedEachRun) {
      parts.push('Each recompute draws a new seed.');
    }
    return parts.join(' ');
  }

  function refresh() {
    statusLine.textContent = statusText();
    statusLine.classList.toggle('is-error', Boolean(catalogueError || (outcome && outcome.error)));
    const ready = usable();
    recomputeButton.disabled = !ready || Boolean(inFlight) || invalid.size > 0 ||
      (drafts.size === 0 && !newSeedEachRun);
    // A click that blurs an edited field refreshes between its press and release.
    // Rewriting the same label then replaces the text being pressed, and WebKit
    // drops the click.
    const label = inFlight ? 'Recomputing…' : 'Recompute';
    if (recomputeButton.textContent !== label) recomputeButton.textContent = label;
    pane.setAttribute('aria-busy', String(Boolean(inFlight)));
    discardButton.disabled = !ready || (drafts.size === 0 && invalid.size === 0);
    resetButton.disabled = !ready || (changedFromDefaults(currentValue) === 0 && invalid.size === 0);
    controlsRoot.querySelectorAll('input, button').forEach((element) => {
      element.disabled = !ready || (element.dataset.seedInput === 'true' && newSeedEachRun);
    });
    if (!ready) return;
    controlsRoot.querySelectorAll('input[data-key]').forEach((input) => {
      input.setAttribute('aria-invalid', String(invalid.has(entryKey(input))));
    });
    controlsRoot.querySelectorAll('.param[data-key]').forEach((element) => {
      const key = element.dataset.key;
      element.classList.toggle('is-draft', drafts.has(key));
      element.classList.toggle('is-changed', !same(currentValue(key), controlOf(key).default));
      element.classList.toggle('is-invalid', [...invalid.keys()].some((item) => item === key || item.startsWith(`${key}[`)));
    });
  }

  // ── Controls ──

  function rangeAttributes(control) {
    return `min="${control.min}" max="${control.max}" step="${control.step}"`;
  }

  function numberControl(section, control) {
    const key = keyOf(section, control.id);
    const id = `param-${section}-${control.id}`;
    const seed = section === 'run' && control.id === 'seed';
    const slider = seed
      ? ''
      : `<input type="range" class="param-range" data-key="${key}" ${rangeAttributes(control)} aria-label="${escapeHtml(control.label)}">`;
    const seedChoice = seed
      ? `<label class="param-check"><input type="checkbox" data-seed-each-run="true"> New seed each run</label>`
      : '';
    return `
      <div class="param" data-key="${key}">
        <label class="param-label" for="${id}">${escapeHtml(control.label)}</label>
        <div class="param-inputs${seed ? ' is-seed' : ''}">
          ${slider}
          <input type="number" class="param-number" id="${id}" data-key="${key}" ${seed ? 'data-seed-input="true"' : ''}
            ${rangeAttributes(control)} inputmode="${control.kind === 'integer' ? 'numeric' : 'decimal'}">
        </div>
        ${seedChoice}
        <p class="param-help">${escapeHtml(control.description)} Default ${escapeHtml(control.default)}.</p>
      </div>`;
  }

  function choiceControl(section, control) {
    const key = keyOf(section, control.id);
    const options = control.options
      .map(
        (option) => `
          <label class="param-option">
            <input type="radio" name="param-${section}-${control.id}" data-key="${key}" value="${escapeHtml(option.value)}">
            ${escapeHtml(option.label)}
          </label>`
      )
      .join('');
    return `
      <fieldset class="param param-choice" data-key="${key}">
        <legend class="param-label">${escapeHtml(control.label)}</legend>
        ${options}
        <p class="param-help">${escapeHtml(control.description)}</p>
      </fieldset>`;
  }

  function vectorControl(section, control) {
    const key = keyOf(section, control.id);
    const rows = control.columns
      .map(
        (label, index) => `
          <div class="param-vector-row">
            <label class="param-vector-label" for="param-${control.id}-${index}">${escapeHtml(label)}</label>
            <span class="param-bar" aria-hidden="true"><span class="param-bar-fill" data-bar="${key}[${index}]"></span></span>
            <input type="number" class="param-entry" id="param-${control.id}-${index}" data-key="${key}" data-index="${index}" ${rangeAttributes(control)} inputmode="decimal">
          </div>`
      )
      .join('');
    return `
      <div class="param param-table" data-key="${key}">
        <div class="param-label">${escapeHtml(control.label)}</div>
        <div class="param-vector">${rows}</div>
        <p class="param-help">${escapeHtml(control.description)} Each from ${control.min} to ${control.max}.</p>
      </div>`;
  }

  function matrixControl(section, control) {
    const key = keyOf(section, control.id);
    const head = control.columns.map((label) => `<th scope="col">${escapeHtml(label)}</th>`).join('');
    const body = control.rows
      .map((row, rowIndex) => {
        const cells = control.columns
          .map(
            (column, columnIndex) => `
              <td><input type="number" class="param-entry" data-key="${key}" data-index="${rowIndex},${columnIndex}"
                ${rangeAttributes(control)} inputmode="decimal" aria-label="${escapeHtml(`${row} to ${column}`)}"></td>`
          )
          .join('');
        return `<tr><th scope="row">${escapeHtml(row)}</th>${cells}</tr>`;
      })
      .join('');
    return `
      <div class="param param-table" data-key="${key}">
        <div class="param-label">${escapeHtml(control.label)}</div>
        <table class="param-matrix"><thead><tr><td></td>${head}</tr></thead><tbody>${body}</tbody></table>
        <p class="param-help">${escapeHtml(control.description)} Each from ${control.min} to ${control.max}.</p>
      </div>`;
  }

  const BUILDERS = {
    integer: numberControl,
    number: numberControl,
    choice: choiceControl,
    vector: vectorControl,
    matrix: matrixControl,
  };

  function renderControls() {
    const groups = new Map();
    SECTIONS.forEach((section) => {
      catalogue[section].forEach((control) => {
        if (!groups.has(control.group)) groups.set(control.group, []);
        groups.get(control.group).push(BUILDERS[control.kind](section, control));
      });
    });
    controlsRoot.innerHTML = [...groups.entries()]
      .map(
        ([group, controls]) => `
          <details class="parameter-group"${OPEN_GROUPS.has(group) ? ' open' : ''}>
            <summary>${escapeHtml(group)}</summary>
            ${controls.join('')}
          </details>`
      )
      .join('');
    renderValues();
  }

  // Puts the current values into the inputs, except into one being typed in.
  function renderValues(except = null) {
    controlsRoot.querySelectorAll('[data-key]').forEach((input) => {
      if (input === except || !(input instanceof HTMLInputElement)) return;
      const key = input.dataset.key;
      if (invalid.has(entryKey(input))) return;
      const value = currentValue(key);
      if (input.type === 'radio') {
        input.checked = input.value === value;
      } else if (input.dataset.index !== undefined) {
        input.value = String(entryOf(value, input.dataset.index));
      } else {
        input.value = String(value);
      }
    });
    controlsRoot.querySelectorAll('[data-seed-each-run]').forEach((box) => {
      box.checked = newSeedEachRun;
    });
    renderBars();
  }

  // Every bar of a vector is measured against its largest entry, so one edit can
  // rescale them all.
  function renderBars() {
    catalogue.model
      .filter((control) => control.kind === 'vector')
      .forEach((control) => {
        const key = keyOf('model', control.id);
        const values = currentValue(key);
        const largest = Math.max(...values.map((value) => Math.abs(value)));
        values.forEach((value, index) => {
          const bar = controlsRoot.querySelector(`[data-bar="${key}[${index}]"]`);
          bar.style.width = `${largest > 0 ? (Math.abs(value) / largest) * 100 : 0}%`;
        });
      });
  }

  function entryOf(value, index) {
    const [row, column] = index.split(',').map(Number);
    return column === undefined ? value[row] : value[row][column];
  }

  const entryKey = (input) =>
    input.dataset.index === undefined ? input.dataset.key : `${input.dataset.key}[${input.dataset.index}]`;

  function withEntry(value, index, entry) {
    const [row, column] = index.split(',').map(Number);
    const next = value.map((item) => (Array.isArray(item) ? [...item] : item));
    if (column === undefined) next[row] = entry;
    else next[row][column] = entry;
    return next;
  }

  // A typed entry is a number within the control's range; an emptied field is no entry
  // at all, never zero.
  function parseEntry(input, control) {
    const text = input.value.trim();
    if (text === '') return { error: 'it needs a number.' };
    const value = Number(text);
    if (!Number.isFinite(value)) return { error: `${text} is no number.` };
    if (control.kind === 'integer' && !Number.isInteger(value)) {
      return { error: 'it needs a whole number.' };
    }
    if (value < control.min || value > control.max) {
      return { error: `it must be from ${control.min} to ${control.max}.` };
    }
    return { value };
  }

  function roundTo(value, step) {
    return Number(value.toFixed(decimals(step)));
  }

  // The three clustering weights stay shares of one: the other two take up what one
  // gives or takes, in proportion.
  function setClusterWeight(id, weight) {
    const others = CLUSTER_WEIGHTS.filter((item) => item !== id);
    const control = controlOf(keyOf('model', id));
    const rest = 1 - weight;
    const current = others.map((item) => currentValue(keyOf('model', item)));
    const total = current[0] + current[1];
    const first = roundTo(total > 0 ? (rest * current[0]) / total : rest / 2, control.step);
    setDraft(keyOf('model', id), weight);
    setDraft(keyOf('model', others[0]), first);
    setDraft(keyOf('model', others[1]), roundTo(rest - first, control.step));
  }

  function onInput(event) {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || !input.dataset.key || !usable()) return;
    const key = input.dataset.key;
    const control = controlOf(key);
    if (input.type === 'radio') {
      setDraft(key, input.value);
    } else {
      const parsed = parseEntry(input, control);
      if (parsed.error) {
        invalid.set(entryKey(input), parsed.error);
        refresh();
        return;
      }
      invalid.delete(entryKey(input));
      const [, id] = key.split('.');
      if (input.dataset.index !== undefined) {
        setDraft(key, withEntry(currentValue(key), input.dataset.index, parsed.value));
      } else if (CLUSTER_WEIGHTS.includes(id)) {
        setClusterWeight(id, parsed.value);
      } else {
        setDraft(key, parsed.value);
      }
    }
    outcome = null;
    renderValues(input);
    refresh();
  }

  // ── Recompute ──

  function requestBody() {
    const body = { ...explorer.birth, basin_index: explorer.activeBasinIndex() };
    SECTIONS.forEach((section) => {
      const changed = {};
      catalogue[section].forEach((control) => {
        const value = currentValue(keyOf(section, control.id));
        if (!same(value, control.default)) changed[control.id] = value;
      });
      if (section === 'run' && newSeedEachRun) {
        changed.seed = crypto.getRandomValues(new Uint32Array(1))[0] % SEED_RANGE;
      }
      if (Object.keys(changed).length) body[section] = changed;
    });
    return body;
  }

  async function answerOf(response) {
    const text = await response.text();
    let payload;
    try {
      payload = JSON.parse(text);
    } catch (error) {
      throw new Error(`The server answered ${response.status} without JSON.`, { cause: error });
    }
    if (!response.ok) {
      throw new Error(payload && payload.detail ? String(payload.detail) : `The server answered ${response.status}.`);
    }
    if (!payload || !payload.graph_data || !payload.graph_data.parameters) {
      throw new Error('The answer had no graph and parameters.');
    }
    return payload.graph_data;
  }

  async function recompute() {
    if (inFlight) inFlight.abort();
    const controller = new AbortController();
    inFlight = controller;
    outcome = null;
    refresh();
    try {
      const response = await fetch('/api/evolution_explorer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody()),
        signal: controller.signal,
      });
      const graphData = await answerOf(response);
      if (inFlight !== controller) return;
      explorer.redraw(graphData);
      applied = graphData.parameters;
      outcome = { text: 'Recomputed.', error: false };
    } catch (error) {
      // An abort means a later recompute or a reset took over, and says so itself.
      if (error.name === 'AbortError' || inFlight !== controller) return;
      outcome = { text: `Recompute failed: ${error.message} The chart is unchanged.`, error: true };
    } finally {
      if (inFlight === controller) {
        inFlight = null;
        pruneDrafts();
        renderValues();
        refresh();
      }
    }
  }

  function discard() {
    drafts.clear();
    invalid.clear();
    outcome = null;
    renderValues();
    refresh();
  }

  function resetToDefaults() {
    if (inFlight) {
      inFlight.abort();
      inFlight = null;
    }
    drafts.clear();
    invalid.clear();
    newSeedEachRun = false;
    SECTIONS.forEach((section) => {
      catalogue[section].forEach((control) => setDraft(keyOf(section, control.id), control.default));
    });
    outcome = null;
    renderValues();
    refresh();
  }

  // ── Opening ──

  async function loadCatalogue() {
    catalogueRequest = fetch('/api/evolution_controls');
    refresh();
    try {
      const response = await catalogueRequest;
      if (!response.ok) throw new Error(`the server answered ${response.status}.`);
      catalogue = await response.json();
      catalogueError = null;
      renderControls();
    } catch (error) {
      catalogueError = error.message;
      catalogueRequest = null;
    }
    refresh();
  }

  // The controls are asked for once the pane is open on a chart drawn for a birth; the
  // bundled sample chart has none to recompute.
  function loadCatalogueWhenNeeded() {
    if (!pane.hidden && explorer && explorer.birth && !catalogue && !catalogueRequest) {
      void loadCatalogue();
    }
  }

  function setOpen(open) {
    pane.hidden = !open;
    layout.classList.toggle('parameters-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.classList.toggle('active', open);
    loadCatalogueWhenNeeded();
    refresh();
  }

  toggle.addEventListener('click', () => setOpen(pane.hidden));
  closeButton.addEventListener('click', () => {
    setOpen(false);
    toggle.focus();
  });
  pane.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    setOpen(false);
    toggle.focus();
  });
  controlsRoot.addEventListener('input', onInput);
  controlsRoot.addEventListener('change', (event) => {
    if (event.target instanceof HTMLInputElement && event.target.dataset.seedEachRun) {
      newSeedEachRun = event.target.checked;
      // Each recompute then draws its own seed, so a typed one has nothing to apply.
      if (newSeedEachRun) {
        drafts.delete('run.seed');
        invalid.delete('run.seed');
      }
      outcome = null;
      renderValues();
      refresh();
      return;
    }
    onInput(event);
  });
  recomputeButton.addEventListener('click', () => void recompute());
  discardButton.addEventListener('click', discard);
  resetButton.addEventListener('click', resetToDefaults);
  document.addEventListener('explorer:ready', () => {
    explorer = window.EC_EXPLORER;
    applied = explorer.parameters;
    loadCatalogueWhenNeeded();
    refresh();
  });
  refresh();
})();
