(function () {
  'use strict';

  const ELEMENT_COLORS = {
    Wood: '#7A9E72',
    Fire: '#C4857A',
    Earth: '#BBA862',
    Metal: '#C8C2B8',
    Water: '#7A8FA0',
  };

  const TEN_GOD_GROUP_COLORS = {
    Self: '#8B7DC4',
    Output: '#C48855',
    Wealth: '#B8A24E',
    Authority: '#B87070',
    Resource: '#4E9888',
    None: '#9A9389',
  };

  const RELATION_COLORS = {
    production: '#6B946B',
    control: '#B87070',
    drain: '#6878B0',
  };

  const MOTIF_COLORS = {
    chain: '#C4A04E',
    loop: '#9070B0',
    cascade: '#B06880',
    bottleneck: '#B86060',
    pulse: '#4898A8',
  };

  const ELEMENT_ORDER = ['Wood', 'Fire', 'Earth', 'Metal', 'Water'];
  const RESOURCE_BY_ELEMENT = [4, 0, 1, 2, 3];
  const GOVERNOR_BY_ELEMENT = [3, 4, 0, 1, 2];
  const BASIN_SEGMENT_COLORS = [
    '#7A8FA0',
    '#BBA862',
    '#8B7DC4',
    '#B87070',
    '#7A9E72',
    '#C48855',
  ];

  const STEM_INFO = {
    'Wood|Yang': { char: '甲', roman: 'Jia', archetype: 'Pioneer' },
    'Wood|Yin': { char: '乙', roman: 'Yi', archetype: 'Cultivator' },
    'Fire|Yang': { char: '丙', roman: 'Bing', archetype: 'Sun' },
    'Fire|Yin': { char: '丁', roman: 'Ding', archetype: 'Lamp' },
    'Earth|Yang': { char: '戊', roman: 'Wu', archetype: 'Mountain' },
    'Earth|Yin': { char: '己', roman: 'Ji', archetype: 'Field' },
    'Metal|Yang': { char: '庚', roman: 'Geng', archetype: 'Blade' },
    'Metal|Yin': { char: '辛', roman: 'Xin', archetype: 'Jewel' },
    'Water|Yang': { char: '壬', roman: 'Ren', archetype: 'Ocean' },
    'Water|Yin': { char: '癸', roman: 'Gui', archetype: 'Rain' },
  };

  const BRANCH_INFO = {
    1: { char: '子', roman: 'Zi', animal: 'Rat' },
    2: { char: '丑', roman: 'Chou', animal: 'Ox' },
    3: { char: '寅', roman: 'Yin', animal: 'Tiger' },
    4: { char: '卯', roman: 'Mao', animal: 'Rabbit' },
    5: { char: '辰', roman: 'Chen', animal: 'Dragon' },
    6: { char: '巳', roman: 'Si', animal: 'Snake' },
    7: { char: '午', roman: 'Wu', animal: 'Horse' },
    8: { char: '未', roman: 'Wei', animal: 'Goat' },
    9: { char: '申', roman: 'Shen', animal: 'Monkey' },
    10: { char: '酉', roman: 'You', animal: 'Rooster' },
    11: { char: '戌', roman: 'Xu', animal: 'Dog' },
    12: { char: '亥', roman: 'Hai', animal: 'Pig' },
  };

  const LIFE_STAGE_INFO = {
    1: 'Chang Sheng (Birth)',
    2: 'Mu Yu (Bath)',
    3: 'Guan Dai (Crowning)',
    4: 'Lin Guan (Office)',
    5: 'Di Wang (Prosperity)',
    6: 'Shuai (Decline)',
    7: 'Bing (Sickness)',
    8: 'Si (Death)',
    9: 'Mu (Tomb)',
    10: 'Jue (Extinction)',
    11: 'Tai (Gestation)',
    12: 'Yang (Nourishment)',
  };

  const PILLAR_DOMAIN = {
    Year: 'Ancestry',
    Month: 'Career',
    Day: 'Self',
    Hour: 'Inner World',
  };

  const state = {
    basinViews: [],
    basinDistribution: [],
    activeBasinIndex: 0,
    nodes: [],
    edges: [],
    ghostEdges: [],
    nodeById: new Map(),
    motifs: {
      chains: [],
      loops: [],
      cascades: [],
      bottlenecks: [],
      pulses: [],
      absences: [],
    },
    topologyModifiers: [],
    branchIds: [],
    meta: {},
    views: {
      graph: true,
      pillar: true,
    },
    relationFilters: new Set(['production', 'control', 'drain']),
    motifToggles: {
      chains: true,
      loops: true,
      cascades: true,
      bottlenecks: true,
      pulses: true,
      ghosts: true,
    },
    searchQuery: '',
    minFlux: 0.0,
    maxFlux: 0.0,
    selectedNodeId: null,
  };

  let svg;
  let rootGroup;
  let axisGroup;
  let edgesGroup;
  let ghostEdgesGroup;
  let motifsGroup;
  let nodesGroup;
  let pressureGroup;
  let pulseGroup;
  let edgeSel;
  let ghostEdgeSel;
  let motifSel;
  let nodeSel;
  let pressureSel;
  let pulseSel;
  let simulation;
  let zoomBehavior;
  let fluxScale;
  let width = 0;
  let height = 0;
  let boundsForce;
  let neighborMap = new Map();

  const tooltip = document.getElementById("tooltip");

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function nodeRef(endpoint) {
    if (typeof endpoint === 'object' && endpoint && endpoint.id) return endpoint;
    return state.nodeById.get(endpoint) || null;
  }

  function relationColor(relation) {
    return RELATION_COLORS[relation] || '#9A9389';
  }

  function elementColor(name) {
    return ELEMENT_COLORS[name] || '#9A9389';
  }

  function groupColor(name) {
    return TEN_GOD_GROUP_COLORS[name] || TEN_GOD_GROUP_COLORS.None;
  }

  function queryInputPayload() {
    const params = new URLSearchParams(window.location.search);
    const date = (params.get('date') || '').trim();
    const time = (params.get('time') || '').trim();
    const city = (params.get('city') || '').trim();
    const country = (params.get('country') || '').trim();
    if (!date || !time || !city || !country) {
      return null;
    }
    return { date, time, city, country };
  }

  async function loadGraphData(queryPayload) {
    const response = await fetch('/api/evolution_explorer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(queryPayload),
    });
    const payload = await response.json();
    if (!response.ok) {
      const detail = payload && payload.detail ? String(payload.detail) : 'Evolution load failed.';
      throw new Error(detail);
    }
    if (!payload || !payload.graph_data) {
      throw new Error('Evolution load returned no graph_data.');
    }
    return payload.graph_data;
  }

  function normalizeDistribution(input, basinViews) {
    const fromInput = asArray(input)
      .map((item, index) => {
        const basinId = Number(item?.basin_id ?? index);
        const basinIndex = basinViews.findIndex(
          (view, viewIndex) => Number(view.meta?.basin_id ?? viewIndex) === basinId
        );
        return {
          basin_id: basinId,
          basin_index: basinIndex >= 0 ? basinIndex : index,
          mass: Math.max(0, Number(item?.mass ?? 0)),
          mode: String(item?.mode || 'Unknown'),
        };
      })
      .filter((item) => Number.isFinite(item.mass));
    if (fromInput.length) {
      return fromInput;
    }
    return basinViews.map((view, index) => ({
      basin_id: Number(view.meta?.basin_id ?? index),
      basin_index: index,
      mass: Math.max(0, Number(view.meta?.basin_mass ?? 0)),
      mode: String(view.meta?.mode || 'Unknown'),
    }));
  }

  function findBasinIndexById(basinId) {
    const target = Number(basinId);
    if (!Number.isFinite(target)) return -1;
    return state.basinViews.findIndex(
      (view, index) => Number(view.meta?.basin_id ?? index) === target
    );
  }

  function applyBasinView(view) {
    state.nodes = asArray(view.nodes).map((node) => ({ ...node }));
    state.edges = asArray(view.edges).map((edge) => ({ ...edge }));
    state.ghostEdges = asArray(view.ghost_edges).map((edge) => ({ ...edge }));
    state.motifs = {
      chains: asArray(view.motifs?.chains),
      loops: asArray(view.motifs?.loops),
      cascades: asArray(view.motifs?.cascades),
      bottlenecks: asArray(view.motifs?.bottlenecks),
      pulses: asArray(view.motifs?.pulses),
      absences: asArray(view.motifs?.absences),
    };
    state.topologyModifiers = asArray(view.topology_modifiers).map((modifier) => ({
      ...modifier,
      pillar_indices: asArray(modifier.pillar_indices).map((value) => Number(value)),
    }));
    state.branchIds = asArray(view.meta?.branch_ids).map((value) => Number(value));
    state.meta = {
      ...(view.meta || {}),
      basin_mass_distribution: state.basinDistribution,
      active_basin_index: state.activeBasinIndex,
      basin_count: state.basinViews.length,
    };

    state.nodeById = new Map();
    state.nodes.forEach((node) => {
      const vitality = Number(node.dynamic_vitality || 0);
      node.radius = node.is_ghost ? 12 : 7 + vitality * 17;
      node.anchorX = 0;
      node.anchorY = 0;
      state.nodeById.set(node.id, node);
    });

    state.maxFlux = Math.max(
      0,
      ...state.edges.map((edge) => Number(edge.abs_flux || 0))
    );
    const domainMax = state.maxFlux > 0 ? state.maxFlux : 1;
    fluxScale = d3.scaleSqrt().domain([0, domainMax]).range([0.7, 5]);
  }

  function parseData(raw) {
    const candidates =
      raw && Array.isArray(raw.basin_views) && raw.basin_views.length
        ? raw.basin_views
        : [raw];
    state.basinViews = candidates
      .filter(
        (view) =>
          view &&
          Array.isArray(view.nodes) &&
          Array.isArray(view.edges)
      )
      .map((view, index) => ({
        ...view,
        meta: {
          ...(view.meta || {}),
          basin_id: Number(view.meta?.basin_id ?? index),
        },
      }));
    if (!state.basinViews.length) {
      throw new Error('GRAPH_DATA must include nodes and edges arrays.');
    }

    const requestedIndex = Number(
      raw?.active_basin_index ?? raw?.meta?.active_basin_index ?? 0
    );
    state.activeBasinIndex = Number.isFinite(requestedIndex)
      ? Math.max(0, Math.min(state.basinViews.length - 1, Math.trunc(requestedIndex)))
      : 0;

    state.basinDistribution = normalizeDistribution(
      raw?.meta?.basin_mass_distribution,
      state.basinViews
    );
    applyBasinView(state.basinViews[state.activeBasinIndex]);
  }

  function writeMetaLine() {
    const mass = Number(state.meta.basin_mass || 0) * 100;
    const basinCount = Math.max(1, state.basinViews.length);
    const text = [
      `Basin ${state.activeBasinIndex + 1}/${basinCount} (id ${state.meta.basin_id ?? 0})`,
      `Mass ${mass.toFixed(1)}%`,
      `Mode ${state.meta.mode || 'Unknown'}`,
      `Chart T ${Number(state.meta.chart_temperature || 0).toFixed(3)}`,
      `Chart S ${Number(state.meta.chart_saturation || 0).toFixed(3)}`,
    ].join(' \u2022 ');
    document.getElementById('metaLine').textContent = text;
  }

  function clamp01(value) {
    return Math.max(0, Math.min(1, value));
  }

  function normalizeSigned(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return 0.5;
    return clamp01((number + 1) / 2);
  }

  function basinSegmentColor(index) {
    return BASIN_SEGMENT_COLORS[index % BASIN_SEGMENT_COLORS.length];
  }

  function motifCountsFromView(view) {
    const motifs = view?.motifs || {};
    return {
      chains: asArray(motifs.chains).length,
      loops: asArray(motifs.loops).length,
      cascades: asArray(motifs.cascades).length,
      bottlenecks: asArray(motifs.bottlenecks).length,
      pulses: asArray(motifs.pulses).length,
    };
  }

  function dominantBasinIndex() {
    if (!state.basinDistribution.length) return 0;
    let best = state.basinDistribution[0];
    state.basinDistribution.forEach((item) => {
      if (Number(item.mass || 0) > Number(best.mass || 0)) {
        best = item;
      }
    });
    const byDistribution = Number(best.basin_index);
    if (Number.isFinite(byDistribution) && byDistribution >= 0) {
      return Math.min(state.basinViews.length - 1, Math.trunc(byDistribution));
    }
    const byId = findBasinIndexById(best.basin_id);
    return byId >= 0 ? byId : 0;
  }

  function updateFluxControls() {
    const slider = document.getElementById('fluxThreshold');
    const output = document.getElementById('fluxThresholdValue');
    const maxFlux = Math.max(0, Number(state.maxFlux || 0));
    if (maxFlux <= 0) {
      state.minFlux = 0;
      slider.value = '0';
      output.textContent = '0.00';
      return;
    }
    state.minFlux = Math.max(0, Math.min(state.minFlux, maxFlux));
    const ratio = clamp01(state.minFlux / maxFlux);
    slider.value = `${Math.round(ratio * 100)}`;
    output.textContent = state.minFlux.toFixed(2);
  }

  function renderBasinTabs() {
    const tabs = document.getElementById('basinTabs');
    if (!tabs) return;
    if (state.basinViews.length <= 1) {
      tabs.innerHTML = '';
      return;
    }

    const totalMass = state.basinDistribution.reduce(
      (sum, item) => sum + Math.max(0, Number(item.mass || 0)),
      0
    );
    const rows = state.basinDistribution.map((item, index) => {
      const basinIndex = Number.isFinite(Number(item.basin_index))
        ? Number(item.basin_index)
        : findBasinIndexById(item.basin_id);
      const resolvedIndex =
        basinIndex >= 0 && basinIndex < state.basinViews.length ? basinIndex : index;
      const percent = totalMass > 0 ? (Number(item.mass || 0) / totalMass) * 100 : 0;
      const mode = String(
        item.mode || state.basinViews[resolvedIndex]?.meta?.mode || 'Unknown'
      );
      const activeClass = resolvedIndex === state.activeBasinIndex ? ' active' : '';
      return `
        <button class="basin-tab${activeClass}" data-basin-index="${resolvedIndex}" title="Switch to basin ${resolvedIndex + 1}">
          B${resolvedIndex + 1} · ${percent.toFixed(1)}% · ${mode}
        </button>
      `;
    });
    tabs.innerHTML = rows.join('');
    tabs.querySelectorAll('.basin-tab').forEach((button) => {
      button.addEventListener('click', () => {
        const index = Number(button.getAttribute('data-basin-index'));
        if (Number.isFinite(index)) {
          setActiveBasin(index);
        }
      });
    });
  }

  function renderBasinMetadata() {
    const panel = document.getElementById('basinMetaPanel');
    const mode = String(state.meta.mode || 'Unknown');
    const chartTemperature = Number(state.meta.chart_temperature || 0);
    const chartSaturation = Number(state.meta.chart_saturation || 0);
    const dotX = normalizeSigned(chartTemperature) * 100;
    const dotY = (1 - normalizeSigned(chartSaturation)) * 100;

    const distribution = state.basinDistribution.length
      ? state.basinDistribution
      : [
        {
          basin_id: Number(state.meta.basin_id ?? state.activeBasinIndex),
          basin_index: state.activeBasinIndex,
          mass: Math.max(0, Number(state.meta.basin_mass || 0)),
          mode,
        },
      ];
    const totalMass = distribution.reduce(
      (sum, basin) => sum + Math.max(0, Number(basin.mass || 0)),
      0
    );
    const dominantIndex = dominantBasinIndex();
    const referenceView =
      state.basinViews[dominantIndex] || state.basinViews[state.activeBasinIndex];
    const referenceCounts = motifCountsFromView(referenceView);

    let cumulative = 0;
    const segmentsHtml = distribution
      .map((basin, index) => {
        const mass = Math.max(0, Number(basin.mass || 0));
        const width = totalMass > 0 ? (mass / totalMass) * 100 : 0;
        const left = cumulative;
        cumulative += width;
        const color = basinSegmentColor(index);
        const basinIndex = Number.isFinite(Number(basin.basin_index))
          ? Number(basin.basin_index)
          : findBasinIndexById(basin.basin_id);
        const activeClass =
          basinIndex === state.activeBasinIndex ? ' probability-segment-active' : '';
        return `
          <div
            class="probability-segment${activeClass}"
            data-basin-index="${basinIndex}"
            style="left:${left}%; width:${width}%; background:${color};"
            title="Basin ${basinIndex + 1} — ${(width || 0).toFixed(1)}%"
          ></div>
        `;
      })
      .join('');

    const probabilityLegend = distribution
      .map((basin, index) => {
        const mass = Math.max(0, Number(basin.mass || 0));
        const percent = totalMass > 0 ? (mass / totalMass) * 100 : 0;
        const basinIndex = Number.isFinite(Number(basin.basin_index))
          ? Number(basin.basin_index)
          : findBasinIndexById(basin.basin_id);
        const activeClass = basinIndex === state.activeBasinIndex ? ' active' : '';
        return `
          <div class="probability-row${activeClass}" data-basin-index="${basinIndex}">
            <div class="left">
              <span class="probability-swatch" style="background:${basinSegmentColor(index)}"></span>
              <span>Basin ${basinIndex + 1} · ${String(basin.mode || 'Unknown')}</span>
            </div>
            <span>${percent.toFixed(1)}%</span>
          </div>
        `;
      })
      .join('');

    const motifRows = [
      {
        key: 'chains',
        colorKey: 'chain',
        label: 'Chains',
        count: asArray(state.motifs.chains).length,
      },
      {
        key: 'loops',
        colorKey: 'loop',
        label: 'Loops',
        count: asArray(state.motifs.loops).length,
      },
      {
        key: 'cascades',
        colorKey: 'cascade',
        label: 'Cascades',
        count: asArray(state.motifs.cascades).length,
      },
      {
        key: 'bottlenecks',
        colorKey: 'bottleneck',
        label: 'Bottlenecks',
        count: asArray(state.motifs.bottlenecks).length,
      },
      {
        key: 'pulses',
        colorKey: 'pulse',
        label: 'Pulses',
        count: asArray(state.motifs.pulses).length,
      },
    ];
    const motifHtml = motifRows
      .map(
        (row) => {
          const referenceCount = Number(referenceCounts[row.key] || 0);
          const delta = row.count - referenceCount;
          const deltaText = delta === 0 ? '\u00b10' : `${delta > 0 ? '+' : ''}${delta}`;
          return `
          <div class="motif-row">
            <div class="motif-left">
              <span class="line-swatch" style="background:${MOTIF_COLORS[row.colorKey] || '#9A9389'}"></span>
              <span>${row.label}</span>
            </div>
            <span class="motif-count">${row.count} <span class="k">(${deltaText})</span></span>
          </div>
        `;
        }
      )
      .join('');

    const switchRows = asArray(state.topologyModifiers)
      .map((modifier) => ({
        rule_index: Number(modifier.rule_index ?? 0),
        label: String(modifier.label || `r${modifier.rule_index ?? '?'}`),
        switch_state: Number(modifier.switch_state ?? 0),
        omega: Number(modifier.omega ?? 0),
      }))
      .sort((left, right) => left.rule_index - right.rule_index);
    const transformationRows = switchRows.filter((row) => row.switch_state > 1);
    const switchListHtml = switchRows.length
      ? switchRows
        .map(
          (row) => `
            <div class="switch-row">
              <span class="switch-label">r${row.rule_index} · ${row.label}</span>
              <span>s=${row.switch_state}, \u03c9=${row.omega.toFixed(2)}</span>
            </div>
          `
        )
        .join('')
      : '<div class="absence-item">No topology switches active in this basin.</div>';

    const transformListHtml = transformationRows.length
      ? transformationRows
        .map(
          (row) => `
            <div class="switch-row">
              <span class="switch-label">r${row.rule_index} · ${row.label}</span>
              <span>state ${row.switch_state}</span>
            </div>
          `
        )
        .join('')
      : '<div class="absence-item">No full-state transformations firing.</div>';

    const referenceSwitchSet = new Set(
      asArray(referenceView?.topology_modifiers).map((modifier) =>
        Number(modifier.rule_index ?? -1)
      )
    );
    const currentSwitchSet = new Set(
      asArray(state.topologyModifiers).map((modifier) =>
        Number(modifier.rule_index ?? -1)
      )
    );
    const flippedOn = [...currentSwitchSet]
      .filter((ruleIndex) => !referenceSwitchSet.has(ruleIndex))
      .sort((a, b) => a - b);
    const flippedOff = [...referenceSwitchSet]
      .filter((ruleIndex) => !currentSwitchSet.has(ruleIndex))
      .sort((a, b) => a - b);
    const switchDeltaText = [
      flippedOn.length ? `ON: ${flippedOn.map((rule) => `r${rule}`).join(', ')}` : 'ON: none',
      flippedOff.length ? `OFF: ${flippedOff.map((rule) => `r${rule}`).join(', ')}` : 'OFF: none',
    ].join(' \u2022 ');

    const dayMasterNode = state.nodes.find(
      (node) => !node.is_ghost && Boolean(node.is_day_master)
    );
    const dayMasterElementIndex = Number(dayMasterNode?.effective_element_index ?? -1);
    const absences = asArray(state.motifs.absences)
      .map((value) => Number(value))
      .filter((value) => Number.isFinite(value) && value >= 0 && value < ELEMENT_ORDER.length);

    let absenceHtml = '<div class="absence-item">No elemental absence in this basin.</div>';
    if (absences.length) {
      absenceHtml = absences
        .map((missingElementIndex) => {
          const roles = [];
          if (
            dayMasterElementIndex >= 0 &&
            missingElementIndex === RESOURCE_BY_ELEMENT[dayMasterElementIndex]
          ) {
            roles.push('Resource');
          }
          if (
            dayMasterElementIndex >= 0 &&
            missingElementIndex === GOVERNOR_BY_ELEMENT[dayMasterElementIndex]
          ) {
            roles.push('Governor');
          }
          const roleText = roles.length
            ? roles.join(', ')
            : 'No direct Resource/Governor role for current Day Master';
          return `
            <div class="absence-item">
              <strong>${ELEMENT_ORDER[missingElementIndex]}</strong>
              <div>${roleText}</div>
            </div>
          `;
        })
        .join('');
    }

    panel.innerHTML = `
      <div class="meta-card">
        <div class="meta-card-title">Global Mode</div>
        <span class="mode-label">${mode}</span>
      </div>
      <div class="meta-card">
        <div class="meta-card-title">Climate Quadrant</div>
        <div class="climate-quadrant">
          <div class="climate-midline-x"></div>
          <div class="climate-midline-y"></div>
          <div class="climate-dot" style="left:${dotX}%; top:${dotY}%"></div>
          <div class="climate-axis-label top">Cold · Wet</div>
          <div class="climate-axis-label right">Hot · Wet</div>
          <div class="climate-axis-label bottom">Cold · Dry</div>
          <div class="climate-axis-label left">Hot · Dry</div>
        </div>
      </div>
      <div class="meta-card">
        <div class="meta-card-title">Basin Mass</div>
        <div class="probability-bar">${segmentsHtml}</div>
        <div class="probability-legend">${probabilityLegend}</div>
      </div>
      <div class="meta-card">
        <div class="meta-card-title">Switchboard Delta vs Basin ${dominantIndex + 1}</div>
        <div class="switch-row">
          <span class="switch-label">Active switches</span>
          <span>${switchRows.length}</span>
        </div>
        <div class="switch-row">
          <span class="switch-label">Transformations firing</span>
          <span>${transformationRows.length}</span>
        </div>
        <div class="absence-item">${switchDeltaText}</div>
      </div>
      <div class="meta-card">
        <div class="meta-card-title">Active Topology Switches</div>
        <div class="switch-grid">${switchListHtml}</div>
      </div>
      <div class="meta-card">
        <div class="meta-card-title">Firing Transformations</div>
        <div class="switch-grid">${transformListHtml}</div>
      </div>
      <div class="meta-card">
        <div class="meta-card-title">Motif Inventory (vs Basin ${dominantIndex + 1})</div>
        <div class="motif-inventory">${motifHtml}</div>
      </div>
      <div class="absence-callout">
        <div class="absence-title">Absence Callout · Missing Element Roles</div>
        ${absenceHtml}
      </div>
    `;

    panel.querySelectorAll('[data-basin-index]').forEach((node) => {
      node.addEventListener('click', () => {
        const basinIndex = Number(node.getAttribute('data-basin-index'));
        if (Number.isFinite(basinIndex)) {
          setActiveBasin(basinIndex);
        }
      });
    });
  }

  function applyViewVisibility() {
    const graphView = document.getElementById('graphView');
    const pillarView = document.getElementById('pillarView');
    graphView.style.display = state.views.graph ? '' : 'none';
    pillarView.style.display = state.views.pillar ? '' : 'none';
    document.getElementById('fitButton').disabled = !state.views.graph;
  }

  function stemInfoFromNode(node) {
    if (!node || node.is_ghost) {
      return { char: '—', roman: 'Unknown', archetype: 'Unknown' };
    }
    const key = `${node.effective_element}|${node.polarity}`;
    return STEM_INFO[key] || { char: '—', roman: 'Unknown', archetype: 'Unknown' };
  }

  function branchInfoByPillar(pillarIndex) {
    const branchId = state.branchIds[pillarIndex - 1];
    return BRANCH_INFO[branchId] || { char: '—', roman: 'Unknown', animal: 'Unknown' };
  }

  function renderPillarStrip() {
    const strip = document.getElementById('pillarStrip');
    const bands = document.getElementById('modifierBands');
    const displayPillars = [
      { name: 'Hour', index: 4 },
      { name: 'Day', index: 3 },
      { name: 'Month', index: 2 },
      { name: 'Year', index: 1 },
    ];
    const displayPositionByPillar = new Map(
      displayPillars.map((pillar, position) => [pillar.index, position])
    );

    const cardHtml = displayPillars
      .map((pillar) => {
        const pillarName = pillar.name;
        const pillarIndex = pillar.index;
        const stemNode = state.nodes.find(
          (node) =>
            !node.is_ghost &&
            Number(node.pillar_index) === pillarIndex &&
            Number(node.hierarchy_index) === 4
        );
        const stemInfo = stemInfoFromNode(stemNode);
        const branchInfo = branchInfoByPillar(pillarIndex);
        const lifeStageNumber = Number(stemNode?.vitality_stage || 0);
        const lifeStageLabel = LIFE_STAGE_INFO[lifeStageNumber] || 'Unknown';
        const tenGod = stemNode?.ten_god || 'Unknown';
        const domain = PILLAR_DOMAIN[pillarName] || 'Domain';

        return `
          <article class="pillar-card" data-pillar-index="${pillarIndex}">
            <div class="pillar-card-head">
              <div class="pillar-name">${pillarName}</div>
              <div class="pillar-domain">${domain}</div>
            </div>
            <div class="pillar-row">
              <span class="label">Stem</span>
              <span class="value">${stemInfo.char} ${stemInfo.roman} · ${stemInfo.archetype}</span>
            </div>
            <div class="pillar-row">
              <span class="label">Branch</span>
              <span class="value">${branchInfo.char} ${branchInfo.roman} · ${branchInfo.animal}</span>
            </div>
            <div class="pillar-row">
              <span class="label">Life Stage</span>
              <span class="value">${lifeStageNumber || '—'} · ${lifeStageLabel}</span>
            </div>
            <div class="pillar-row">
              <span class="label">Ten God</span>
              <span class="value">${tenGod}</span>
            </div>
          </article>
        `;
      })
      .join('');

    strip.innerHTML = cardHtml;

    const activeBands = state.topologyModifiers.filter(
      (modifier) =>
        Array.isArray(modifier.pillar_indices) &&
        modifier.pillar_indices.length >= 2
    );

    if (!activeBands.length) {
      bands.style.height = '22px';
      bands.innerHTML = '<div class="modifier-band empty">No active topology modifiers.</div>';
      return;
    }

    const stripRect = strip.getBoundingClientRect();
    const spanByPillar = new Map();
    Array.from(strip.querySelectorAll('.pillar-card')).forEach((card) => {
      const pillarIndex = Number(card.dataset.pillarIndex || 0);
      if (pillarIndex < 1 || pillarIndex > 4) return;
      const rect = card.getBoundingClientRect();
      spanByPillar.set(pillarIndex, {
        left: rect.left - stripRect.left,
        right: rect.right - stripRect.left,
      });
    });

    const positionedBands = activeBands
      .map((modifier) => {
        const pillarIndices = modifier.pillar_indices
          .map((value) => Number(value))
          .filter((value) => value >= 1 && value <= 4)
          .sort(
            (left, right) =>
              (displayPositionByPillar.get(left) ?? 99) -
              (displayPositionByPillar.get(right) ?? 99)
          );
        if (pillarIndices.length < 2) return null;
        const startSpan = spanByPillar.get(pillarIndices[0]);
        const endSpan = spanByPillar.get(pillarIndices[pillarIndices.length - 1]);
        if (!startSpan || !endSpan) return null;
        const left = startSpan.left + 6;
        const right = endSpan.right - 6;
        const width = Math.max(34, right - left);
        const connectedPillars = pillarIndices.map((pillarIndex) => {
          const displayPillar = displayPillars.find((item) => item.index === pillarIndex);
          return displayPillar ? displayPillar.name : `P${pillarIndex}`;
        });
        return {
          kind: modifier.kind || 'harmony',
          label: modifier.label || 'Modifier',
          connector: connectedPillars.join(' ↔ '),
          left,
          right,
          width,
        };
      })
      .filter(Boolean)
      .sort((a, b) => a.left - b.left || a.right - b.right);

    if (!positionedBands.length) {
      bands.style.height = '22px';
      bands.innerHTML =
        '<div class="modifier-band empty">No active topology modifiers.</div>';
      return;
    }

    const rowGap = 6;
    const bandHeight = 20;
    const rowLastRight = [];
    positionedBands.forEach((band) => {
      let rowIndex = rowLastRight.findIndex(
        (lastRight) => band.left > lastRight + rowGap
      );
      if (rowIndex < 0) {
        rowIndex = rowLastRight.length;
        rowLastRight.push(band.right);
      } else {
        rowLastRight[rowIndex] = band.right;
      }
      band.rowIndex = rowIndex;
    });

    const rowCount = Math.max(1, rowLastRight.length);
    const totalHeight = rowCount * bandHeight + (rowCount - 1) * rowGap;
    bands.style.height = `${totalHeight}px`;

    const bandHtml = positionedBands
      .map((band) => {
        const top = band.rowIndex * (bandHeight + rowGap);
        return `
          <div
            class="modifier-band ${band.kind}"
            style="left:${band.left}px; width:${band.width}px; top:${top}px;"
            title="${band.connector} · ${band.label}"
          >
            ${band.label}
          </div>
        `;
      })
      .join('');

    bands.innerHTML = bandHtml;
  }

  function setupControls() {
    const searchInput = document.getElementById('searchInput');
    const fluxSlider = document.getElementById('fluxThreshold');
    const fluxOutput = document.getElementById('fluxThresholdValue');

    searchInput.addEventListener('input', () => {
      state.searchQuery = searchInput.value.trim().toLowerCase();
      applyFilters();
    });

    fluxSlider.addEventListener('input', () => {
      const ratio = Number(fluxSlider.value) / 100;
      state.minFlux = ratio * Math.max(0, Number(state.maxFlux || 0));
      fluxOutput.textContent = state.minFlux.toFixed(2);
      applyFilters();
    });
    updateFluxControls();

    document.querySelectorAll('#relationFilters .toggle-btn').forEach((button) => {
      button.addEventListener('click', () => {
        const relation = button.dataset.relation;
        if (!relation) return;
        if (state.relationFilters.has(relation)) {
          state.relationFilters.delete(relation);
          button.classList.remove('active');
        } else {
          state.relationFilters.add(relation);
          button.classList.add('active');
        }
        applyFilters();
      });
    });

    const checkboxMap = {
      toggleChains: 'chains',
      toggleLoops: 'loops',
      toggleCascades: 'cascades',
      toggleBottlenecks: 'bottlenecks',
      togglePulses: 'pulses',
      toggleGhosts: 'ghosts',
    };
    Object.entries(checkboxMap).forEach(([id, key]) => {
      const input = document.getElementById(id);
      input.addEventListener('change', () => {
        state.motifToggles[key] = input.checked;
        applyFilters();
      });
    });

    document.querySelectorAll('#viewMenu .view-tab').forEach((button) => {
      button.addEventListener('click', () => {
        const viewKey = button.dataset.view;
        if (viewKey !== 'graph' && viewKey !== 'pillar') return;
        const nextValue = !state.views[viewKey];
        const enabledCount =
          Number(state.views.graph) + Number(state.views.pillar);
        if (!nextValue && enabledCount <= 1) return;
        state.views[viewKey] = nextValue;
        button.classList.toggle('active', nextValue);
        applyViewVisibility();
        if (viewKey === 'graph' && nextValue) {
          canvasSize();
          svg.attr('viewBox', `0 0 ${width} ${height}`);
          boundsForce?.setSize(width, height);
          simulation.alpha(0.24).restart();
          fitToView();
        }
        if (viewKey === 'pillar' && nextValue) {
          requestAnimationFrame(() => {
            renderPillarStrip();
          });
        }
      });
    });

    document.getElementById('fitButton').addEventListener('click', fitToView);
    document.getElementById('resetButton').addEventListener('click', () => {
      state.searchQuery = '';
      searchInput.value = '';
      state.minFlux = 0.0;
      updateFluxControls();
      state.relationFilters = new Set(['production', 'control', 'drain']);
      document.querySelectorAll('#relationFilters .toggle-btn').forEach((button) => {
        button.classList.add('active');
      });
      state.motifToggles = {
        chains: true,
        loops: true,
        cascades: true,
        bottlenecks: true,
        pulses: true,
        ghosts: true,
      };
      Object.keys(checkboxMap).forEach((id) => {
        const input = document.getElementById(id);
        input.checked = true;
      });
      applyFilters();
      fitToView();
    });
  }

  function renderLegend() {
    const legendPanel = document.getElementById('legendPanel');

    const elementHtml = Object.entries(ELEMENT_COLORS)
      .map(
        ([name, color]) =>
          `<div class="legend-item"><span class="swatch" style="background:${color}"></span>${name}</div>`
      )
      .join('');

    const groupHtml = Object.entries(TEN_GOD_GROUP_COLORS)
      .map(
        ([name, color]) =>
          `<div class="legend-item"><span class="swatch" style="background:${color}"></span>${name}</div>`
      )
      .join('');

    const relationHtml = Object.entries(RELATION_COLORS)
      .map(
        ([name, color]) =>
          `<div class="legend-item"><span class="line-swatch" style="background:${color}"></span>${name}</div>`
      )
      .join('');

    const motifHtml = Object.entries(MOTIF_COLORS)
      .map(
        ([name, color]) =>
          `<div class="legend-item"><span class="line-swatch" style="background:${color}"></span>${name}</div>`
      )
      .join('');

    legendPanel.innerHTML = `
      <h2>Legend</h2>
      <div class="legend-group">
        <div class="legend-label">Element</div>
        ${elementHtml}
      </div>
      <div class="legend-group">
        <div class="legend-label">Ten God Group</div>
        ${groupHtml}
      </div>
      <div class="legend-group">
        <div class="legend-label">Flux Relation</div>
        ${relationHtml}
      </div>
      <div class="legend-group">
        <div class="legend-label">Motif Overlay</div>
        ${motifHtml}
        <div class="legend-item"><span class="swatch" style="background:transparent;border:1px dashed rgba(42,37,32,0.2)"></span>absent ghost</div>
      </div>
    `;
  }

  function canvasSize() {
    const box = document.querySelector('.canvas-wrap').getBoundingClientRect();
    width = Math.max(100, box.width);
    height = Math.max(100, box.height);
  }

  function setAnchors() {
    const margin = { left: 90, right: 90, top: 90, bottom: 90 };
    const usableWidth = Math.max(120, width - margin.left - margin.right);
    const usableHeight = Math.max(120, height - margin.top - margin.bottom);

    const rowByHierarchy = { 4: 0, 3: 1, 2: 2, 1: 3 };
    state.nodes.forEach((node) => {
      if (node.is_ghost) {
        const side = Number(node.ghost_slot || 0) % 2 === 0 ? -1 : 1;
        node.anchorX = side < 0 ? margin.left - 70 : width - margin.right + 70;
        node.anchorY = margin.top + (Number(node.effective_element_index || 0) / 4) * usableHeight;
        return;
      }
      const pillarIndex = Math.max(1, Math.min(4, Number(node.pillar_index || 1)));
      const hierarchyIndex = Math.max(1, Math.min(4, Number(node.hierarchy_index || 1)));
      const row = rowByHierarchy[hierarchyIndex] ?? 3;
      node.anchorX = margin.left + ((pillarIndex - 1) / 3) * usableWidth;
      node.anchorY = margin.top + (row / 3) * usableHeight;
    });

    drawAxisGuides(margin, usableWidth, usableHeight);
  }

  function buildNeighborMap() {
    neighborMap = new Map();
    state.nodes.forEach((node) => {
      neighborMap.set(node.id, new Set());
    });
    const allEdges = [...state.edges, ...state.ghostEdges];
    allEdges.forEach((edge) => {
      const source = nodeRef(edge.source);
      const target = nodeRef(edge.target);
      if (!source || !target) return;
      neighborMap.get(source.id)?.add(target);
      neighborMap.get(target.id)?.add(source);
    });
  }

  function drawAxisGuides(margin, usableWidth, usableHeight) {
    const pillars = ['Year', 'Month', 'Day', 'Hour'];
    const hierarchy = ['Stem', 'Principal', 'Secondary', 'Residual'];

    const pillarData = pillars.map((label, index) => ({
      label,
      x: margin.left + (index / 3) * usableWidth,
      y: 30,
    }));
    const hierarchyData = hierarchy.map((label, index) => ({
      label,
      x: 12,
      y: margin.top + (index / 3) * usableHeight + 4,
    }));

    axisGroup.selectAll('*').remove();
    axisGroup
      .selectAll('text.pillar')
      .data(pillarData)
      .join('text')
      .attr('class', 'axis-guide')
      .attr('x', (d) => d.x)
      .attr('y', (d) => d.y)
      .attr('text-anchor', 'middle')
      .text((d) => d.label);

    axisGroup
      .selectAll('text.hierarchy')
      .data(hierarchyData)
      .join('text')
      .attr('class', 'axis-guide')
      .attr('x', (d) => d.x)
      .attr('y', (d) => d.y)
      .attr('text-anchor', 'start')
      .text((d) => d.label);
  }

  function createSvg() {
    svg = d3.select('#graph');
    svg.selectAll('*').remove();
    svg.attr('viewBox', `0 0 ${width} ${height}`);

    const defs = svg.append('defs');
    Object.entries(RELATION_COLORS).forEach(([relation, color]) => {
      defs
        .append('marker')
        .attr('id', `arrow-${relation}`)
        .attr('viewBox', '0 0 10 10')
        .attr('refX', 9)
        .attr('refY', 5)
        .attr('markerWidth', 7)
        .attr('markerHeight', 7)
        .attr('orient', 'auto-start-reverse')
        .append('path')
        .attr('d', 'M 0 0 L 10 5 L 0 10 z')
        .attr('fill', color);
    });
    defs
      .append('marker')
      .attr('id', 'arrow-cascade')
      .attr('viewBox', '0 0 10 10')
      .attr('refX', 9)
      .attr('refY', 5)
      .attr('markerWidth', 8)
      .attr('markerHeight', 8)
      .attr('orient', 'auto-start-reverse')
      .append('path')
      .attr('d', 'M 0 0 L 10 5 L 0 10 z')
      .attr('fill', MOTIF_COLORS.cascade);

    rootGroup = svg.append('g');
    axisGroup = rootGroup.append('g');
    edgesGroup = rootGroup.append('g');
    ghostEdgesGroup = rootGroup.append('g');
    motifsGroup = rootGroup.append('g');
    pressureGroup = rootGroup.append('g');
    pulseGroup = rootGroup.append('g');
    nodesGroup = rootGroup.append('g');

    zoomBehavior = d3
      .zoom()
      .scaleExtent([0.2, 5])
      .on('zoom', (event) => {
        rootGroup.attr('transform', event.transform);
      });
    svg.call(zoomBehavior);
  }

  function buildMotifSegments() {
    const segments = [];

    function addPathSegments(paths, kind, closeLoop) {
      paths.forEach((path, pathIndex) => {
        if (!Array.isArray(path) || path.length < 2) return;
        const pathNodes = path.slice();
        for (let i = 0; i < path.length - 1; i += 1) {
          segments.push({
            id: `${kind}_${pathIndex}_${i}`,
            source: path[i],
            target: path[i + 1],
            kind,
            path_nodes: pathNodes,
            path_index: pathIndex,
          });
        }
        if (closeLoop && path.length >= 2) {
          segments.push({
            id: `${kind}_${pathIndex}_close`,
            source: path[path.length - 1],
            target: path[0],
            kind,
            path_nodes: pathNodes,
            path_index: pathIndex,
          });
        }
      });
    }

    addPathSegments(state.motifs.chains, 'chain', false);
    addPathSegments(state.motifs.loops, 'loop', true);
    addPathSegments(state.motifs.cascades, 'cascade', false);

    return segments;
  }

  function createGraphLayers() {
    edgeSel = edgesGroup
      .selectAll('line.edge')
      .data(state.edges, (edge) => edge.id)
      .join('line')
      .attr('class', (edge) => `edge ${edge.relation}`)
      .attr('stroke-width', (edge) => fluxScale(Number(edge.abs_flux || 0)))
      .attr('marker-end', (edge) => `url(#arrow-${edge.relation})`);

    ghostEdgeSel = ghostEdgesGroup
      .selectAll('line.edge.ghost-edge')
      .data(state.ghostEdges, (edge) => edge.id)
      .join('line')
      .attr('class', (edge) => `edge ghost-edge ${edge.relation}`)
      .attr('stroke-width', 1.3)
      .attr('marker-end', (edge) => `url(#arrow-${edge.relation})`);

    motifSel = motifsGroup
      .selectAll('line.motif-edge')
      .data(buildMotifSegments(), (segment) => segment.id)
      .join('line')
      .attr('class', (segment) => `motif-edge ${segment.kind}`)
      .attr('stroke', (segment) => MOTIF_COLORS[segment.kind] || '#9A9389')
      .attr('marker-end', (segment) =>
        segment.kind === 'cascade' ? 'url(#arrow-cascade)' : null
      );

    nodeSel = nodesGroup
      .selectAll('g.node-shell')
      .data(state.nodes, (node) => node.id)
      .join((enter) => {
        const group = enter.append('g').attr('class', 'node-shell');
        group.append('circle').attr('class', 'node-core');
        group.append('text').attr('class', 'node-label');
        group.append('text').attr('class', 'node-sub');
        return group;
      });

    nodeSel
      .select('circle.node-core')
      .attr('class', (node) => {
        let css = 'node-core';
        if (node.is_day_master) css += ' day-master';
        if (node.is_ghost) css += ' ghost';
        return css;
      })
      .attr('r', (node) => node.radius)
      .attr('fill', (node) => elementColor(node.effective_element))
      .attr('stroke', 'none')
      .attr('opacity', (node) => (node.is_ghost ? 0.58 : 1));

    nodeSel
      .select('text.node-label')
      .attr('y', (node) => node.radius + 14)
      .text((node) => node.label);

    nodeSel
      .select('text.node-sub')
      .attr('y', (node) => node.radius + 27)
      .text((node) => {
        if (node.is_ghost) return node.effective_element;
        return `${node.effective_element} \u2022 ${node.ten_god}`;
      });

    pressureSel = pressureGroup
      .selectAll('path.pressure-mark')
      .data(
        state.motifs.bottlenecks
          .map((nodeId) => state.nodeById.get(nodeId))
          .filter(Boolean),
        (node) => node.id
      )
      .join('path')
      .attr('class', 'pressure-mark')
      .attr('d', d3.symbol().type(d3.symbolTriangle).size(75));

    pulseSel = pulseGroup
      .selectAll('circle.pulse-ring')
      .data(
        state.motifs.pulses
          .map((nodeId) => state.nodeById.get(nodeId))
          .filter(Boolean),
        (node) => node.id
      )
      .join('circle')
      .attr('class', 'pulse-ring')
      .attr('r', (node) => node.radius + 6);

    setupNodeInteractions();
    setupDrag();
  }

  function linkDistance(edge) {
    if (edge.is_ghost) return 110;
    const maxFlux = Math.max(1e-6, Number(state.meta.max_abs_flux || 0.0001));
    const norm = Math.min(1, Number(edge.abs_flux || 0) / maxFlux);
    return 190 - norm * 120;
  }

  function linkStrength(edge) {
    if (edge.is_ghost) return 0.22;
    const maxFlux = Math.max(1e-6, Number(state.meta.max_abs_flux || 0.0001));
    const norm = Math.min(1, Number(edge.abs_flux || 0) / maxFlux);
    return 0.08 + norm * 0.42;
  }

  function createWanderForce() {
    let nodes = [];
    return Object.assign(
      function force(alpha) {
        const t = performance.now() * 0.0011;
        for (const node of nodes) {
          if (node.fx != null || node.fy != null) continue;
          if (node._phaseA == null) {
            node._phaseA = Math.random() * Math.PI * 2;
            node._phaseB = Math.random() * Math.PI * 2;
          }
          node.vx += Math.sin(t + node._phaseA) * 0.005 * (0.6 + alpha);
          node.vy += Math.cos(t * 0.9 + node._phaseB) * 0.005 * (0.6 + alpha);
        }
      },
      {
        initialize(initNodes) {
          nodes = initNodes;
        },
      }
    );
  }

  function createBoundsForce(canvasWidth, canvasHeight) {
    let nodes = [];
    let w = canvasWidth;
    let h = canvasHeight;
    const pad = 20;
    const strength = 0.09;
    const force = function apply(alpha) {
      for (const node of nodes) {
        if (node.x < pad) node.vx += (pad - node.x) * strength * alpha;
        if (node.x > w - pad) node.vx -= (node.x - (w - pad)) * strength * alpha;
        if (node.y < pad) node.vy += (pad - node.y) * strength * alpha;
        if (node.y > h - pad) node.vy -= (node.y - (h - pad)) * strength * alpha;
      }
    };
    force.initialize = function initialize(initNodes) {
      nodes = initNodes;
    };
    force.setSize = function setSize(nextWidth, nextHeight) {
      w = nextWidth;
      h = nextHeight;
    };
    return force;
  }

  function setupSimulation() {
    const allLinks = [...state.edges, ...state.ghostEdges];
    state.nodes.forEach((node) => {
      if (typeof node.x !== 'number') {
        node.x = node.anchorX + (Math.random() - 0.5) * 28;
      }
      if (typeof node.y !== 'number') {
        node.y = node.anchorY + (Math.random() - 0.5) * 28;
      }
      node.vx = (node.vx || 0) + (Math.random() - 0.5) * 0.08;
      node.vy = (node.vy || 0) + (Math.random() - 0.5) * 0.08;
    });
    boundsForce = createBoundsForce(width, height);
    simulation = d3
      .forceSimulation(state.nodes)
      .force(
        'link',
        d3.forceLink(allLinks).id((node) => node.id).distance(linkDistance).strength(linkStrength)
      )
      .force(
        'charge',
        d3.forceManyBody().strength((node) => (node.is_ghost ? -34 : -95))
      )
      .force('collision', d3.forceCollide().radius((node) => node.radius + 6))
      .force(
        'x',
        d3
          .forceX((node) => node.anchorX)
          .strength((node) => (node.is_ghost ? 0.03 : 0.014))
      )
      .force(
        'y',
        d3
          .forceY((node) => node.anchorY)
          .strength((node) => (node.is_ghost ? 0.03 : 0.014))
      )
      .force('wander', createWanderForce())
      .force('bounds', boundsForce)
      .alpha(0.78)
      .alphaMin(0.003)
      .alphaDecay(0.013)
      .velocityDecay(0.28)
      .alphaTarget(0.02)
      .on('tick', ticked);
  }

  function edgeCoordinates(edge) {
    const source = nodeRef(edge.source);
    const target = nodeRef(edge.target);
    if (!source || !target) return null;

    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const offsetX = (dx / dist) * (target.radius + 2);
    const offsetY = (dy / dist) * (target.radius + 2);

    return {
      x1: source.x,
      y1: source.y,
      x2: target.x - offsetX,
      y2: target.y - offsetY,
    };
  }

  function ticked() {
    edgeSel
      .attr('x1', (edge) => edgeCoordinates(edge)?.x1 || 0)
      .attr('y1', (edge) => edgeCoordinates(edge)?.y1 || 0)
      .attr('x2', (edge) => edgeCoordinates(edge)?.x2 || 0)
      .attr('y2', (edge) => edgeCoordinates(edge)?.y2 || 0);

    ghostEdgeSel
      .attr('x1', (edge) => edgeCoordinates(edge)?.x1 || 0)
      .attr('y1', (edge) => edgeCoordinates(edge)?.y1 || 0)
      .attr('x2', (edge) => edgeCoordinates(edge)?.x2 || 0)
      .attr('y2', (edge) => edgeCoordinates(edge)?.y2 || 0);

    motifSel
      .attr('x1', (segment) => nodeRef(segment.source)?.x || 0)
      .attr('y1', (segment) => nodeRef(segment.source)?.y || 0)
      .attr('x2', (segment) => nodeRef(segment.target)?.x || 0)
      .attr('y2', (segment) => nodeRef(segment.target)?.y || 0);

    nodeSel.attr('transform', (node) => `translate(${node.x},${node.y})`);

    pressureSel.attr(
      'transform',
      (node) => `translate(${node.x + node.radius + 8},${node.y - node.radius - 7})`
    );

    pulseSel.attr('cx', (node) => node.x).attr('cy', (node) => node.y);
  }

  function nodeMatchesSearch(node) {
    if (!state.searchQuery) return true;
    const query = state.searchQuery;
    const stack = [
      node.id,
      node.label,
      node.pillar,
      node.hierarchy,
      node.effective_element,
      node.ten_god,
      node.ten_god_group,
      node.polarity,
    ]
      .join(' ')
      .toLowerCase();
    return stack.includes(query);
  }

  function edgeVisible(edge, isGhost) {
    if (!state.relationFilters.has(edge.relation)) return false;
    if (!isGhost && Number(edge.abs_flux || 0) < state.minFlux) return false;
    if (isGhost && !state.motifToggles.ghosts) return false;
    const source = nodeRef(edge.source);
    const target = nodeRef(edge.target);
    if (!source || !target) return false;
    if (state.searchQuery) {
      return nodeMatchesSearch(source) || nodeMatchesSearch(target);
    }
    return true;
  }

  function motifVisible(segment) {
    const toggleKey =
      segment.kind === 'chain'
        ? 'chains'
        : segment.kind === 'loop'
          ? 'loops'
          : 'cascades';
    if (!state.motifToggles[toggleKey]) return false;

    const source = nodeRef(segment.source);
    const target = nodeRef(segment.target);
    if (!source || !target) return false;
    if (!state.motifToggles.ghosts && (source.is_ghost || target.is_ghost)) return false;
    if (state.searchQuery) {
      return nodeMatchesSearch(source) || nodeMatchesSearch(target);
    }
    return true;
  }

  function visibleEdgeNodeSet() {
    const set = new Set();
    state.edges.forEach((edge) => {
      if (!edgeVisible(edge, false)) return;
      const source = nodeRef(edge.source);
      const target = nodeRef(edge.target);
      if (!source || !target) return;
      set.add(source.id);
      set.add(target.id);
    });
    if (state.motifToggles.ghosts) {
      state.ghostEdges.forEach((edge) => {
        if (!edgeVisible(edge, true)) return;
        const source = nodeRef(edge.source);
        const target = nodeRef(edge.target);
        if (!source || !target) return;
        set.add(source.id);
        set.add(target.id);
      });
    }
    return set;
  }

  function nodeVisible(node, visibleEdgeNodes) {
    if (node.is_ghost && !state.motifToggles.ghosts) return false;
    if (!state.searchQuery) return true;
    return nodeMatchesSearch(node) || visibleEdgeNodes.has(node.id);
  }

  function applyFilters() {
    const visibleEdgeNodes = visibleEdgeNodeSet();

    edgeSel.classed('hidden', (edge) => !edgeVisible(edge, false));
    ghostEdgeSel.classed('hidden', (edge) => !edgeVisible(edge, true));
    motifSel.classed('hidden', (segment) => !motifVisible(segment));

    nodeSel
      .classed('node-faded', (node) => !nodeVisible(node, visibleEdgeNodes))
      .style('pointer-events', (node) =>
        nodeVisible(node, visibleEdgeNodes) ? 'all' : 'none'
      );

    pressureSel.style('display', state.motifToggles.bottlenecks ? null : 'none');
    pulseSel.style('display', state.motifToggles.pulses ? null : 'none');

    if (state.selectedNodeId && !state.nodeById.has(state.selectedNodeId)) {
      state.selectedNodeId = null;
    }
    if (state.selectedNodeId) {
      renderDetail({ type: 'node', payload: state.nodeById.get(state.selectedNodeId) });
    }

    updateStatus();
  }

  function connectedNodeIds(nodeId) {
    const ids = new Set([nodeId]);
    const all = [...state.edges, ...state.ghostEdges];
    all.forEach((edge) => {
      const source = nodeRef(edge.source);
      const target = nodeRef(edge.target);
      if (!source || !target) return;
      if (source.id === nodeId) ids.add(target.id);
      if (target.id === nodeId) ids.add(source.id);
    });
    return ids;
  }

  function highlightNode(nodeId) {
    const connected = connectedNodeIds(nodeId);
    nodeSel
      .classed('node-highlight', (node) => connected.has(node.id))
      .classed('node-faded', (node) => !connected.has(node.id));

    edgeSel.classed('hidden', (edge) => {
      const source = nodeRef(edge.source);
      const target = nodeRef(edge.target);
      if (!source || !target) return true;
      const linked = source.id === nodeId || target.id === nodeId;
      return !linked || !edgeVisible(edge, false);
    });
    ghostEdgeSel.classed('hidden', (edge) => {
      const source = nodeRef(edge.source);
      const target = nodeRef(edge.target);
      if (!source || !target) return true;
      const linked = source.id === nodeId || target.id === nodeId;
      return !linked || !edgeVisible(edge, true);
    });
  }

  function clearHighlight() {
    nodeSel.classed('node-highlight', false);
    applyFilters();
  }

  function showTooltip(html, x, y) {
    tooltip.innerHTML = html;
    tooltip.style.left = `${x + 14}px`;
    tooltip.style.top = `${y + 14}px`;
    tooltip.classList.add('visible');
  }

  function hideTooltip() {
    tooltip.classList.remove('visible');
  }

  function formatNumber(value, digits = 3) {
    const number = Number(value);
    if (!Number.isFinite(number)) return '—';
    return number.toFixed(digits);
  }

  function nodeCaption(nodeId) {
    const node = state.nodeById.get(nodeId);
    if (!node) return nodeId;
    return `${node.id} (${node.pillar} ${node.hierarchy})`;
  }

  function edgeBetween(sourceId, targetId) {
    return state.edges.find((edge) => {
      const source = nodeRef(edge.source);
      const target = nodeRef(edge.target);
      if (!source || !target) return false;
      return source.id === sourceId && target.id === targetId;
    });
  }

  function motifNarrative(kind, pathNodes) {
    const captions = pathNodes.map((nodeId) => nodeCaption(String(nodeId)));
    if (kind === 'chain') {
      return `Chain flow: ${captions.join(' → ')}. Energy is handed forward step by step across the topology.`;
    }
    if (kind === 'loop') {
      return `Loop circulation: ${captions.join(' → ')} → ${captions[0]}. Current feeds back into its origin, creating a self-reinforcing circuit.`;
    }
    return `Cascade amplification: ${captions.join(' → ')}. Upstream flux propagates downstream and tends to magnify pressure at the tail.`;
  }

  function renderEdgeDetail(edge) {
    const panel = document.getElementById('detailPanel');
    const source = nodeRef(edge.source);
    const target = nodeRef(edge.target);
    if (!source || !target) {
      panel.innerHTML = 'Edge data unavailable.';
      return;
    }
    panel.innerHTML = `
      <div><strong>Flux Edge</strong> ${source.id} → ${target.id}</div>
      <div class="k">${source.label} → ${target.label}</div>
      <hr>
      <div class="detail-row"><span>Flux F(i→j)</span><span>${formatNumber(edge.flux)}</span></div>
      <div class="detail-row"><span>|Flux|</span><span>${formatNumber(edge.abs_flux)}</span></div>
      <div class="detail-row"><span>Elemental relationship</span><span>${edge.elemental_relationship || edge.relation || '—'}</span></div>
      <div class="detail-row"><span>Elemental interaction</span><span>${formatNumber(edge.elemental_interaction)}</span></div>
      <div class="detail-row"><span>Polarity modifier</span><span>${formatNumber(edge.polarity_modifier)}</span></div>
      <div class="detail-row"><span>Vitality differential</span><span>${formatNumber(edge.vitality_differential)}</span></div>
      <div class="detail-row"><span>Proximity weight</span><span>${formatNumber(edge.proximity_weight)}</span></div>
      <div class="detail-row"><span>Hierarchy coupling</span><span>${formatNumber(edge.hierarchy_coupling, 2)}</span></div>
      <div class="detail-row"><span>Transport capacity term</span><span>${formatNumber(edge.transport_capacity_component)}</span></div>
    `;
  }

  function renderMotifDetail(segment) {
    const panel = document.getElementById('detailPanel');
    const pathNodes = asArray(segment.path_nodes).map((nodeId) => String(nodeId));
    if (pathNodes.length < 2) {
      panel.innerHTML = 'Motif path unavailable.';
      return;
    }

    const stepRows = [];
    for (let index = 0; index < pathNodes.length - 1; index += 1) {
      const sourceId = pathNodes[index];
      const targetId = pathNodes[index + 1];
      const edge = edgeBetween(sourceId, targetId);
      stepRows.push(`
        <div class="detail-row">
          <span>${nodeCaption(sourceId)} → ${nodeCaption(targetId)}</span>
          <span>${edge ? formatNumber(edge.flux) : 'n/a'}</span>
        </div>
      `);
    }
    if (segment.kind === 'loop') {
      const sourceId = pathNodes[pathNodes.length - 1];
      const targetId = pathNodes[0];
      const edge = edgeBetween(sourceId, targetId);
      stepRows.push(`
        <div class="detail-row">
          <span>${nodeCaption(sourceId)} → ${nodeCaption(targetId)}</span>
          <span>${edge ? formatNumber(edge.flux) : 'n/a'}</span>
        </div>
      `);
    }

    panel.innerHTML = `
      <div><strong>Motif Highlight</strong> · ${String(segment.kind || 'motif').toUpperCase()}</div>
      <div class="k">${motifNarrative(segment.kind, pathNodes)}</div>
      <hr>
      <div><strong>Path Flux Steps</strong></div>
      ${stepRows.join('')}
    `;
  }

  function renderGhostDetail(node) {
    const panel = document.getElementById('detailPanel');
    const connectsFrom = asArray(node.connects_from).map((nodeId) => String(nodeId));
    const connectsTo = asArray(node.connects_to).map((nodeId) => String(nodeId));
    const fromCaption = connectsFrom.length
      ? connectsFrom.map((nodeId) => nodeCaption(nodeId)).join(', ')
      : 'none';
    const toCaption = connectsTo.length
      ? connectsTo.map((nodeId) => nodeCaption(nodeId)).join(', ')
      : 'none';

    const dayMaster = state.nodes.find(
      (candidate) => !candidate.is_ghost && Boolean(candidate.is_day_master)
    );
    const missingElementIndex = Number(node.effective_element_index ?? -1);
    const roles = [];
    if (
      dayMaster &&
      missingElementIndex >= 0 &&
      missingElementIndex === RESOURCE_BY_ELEMENT[Number(dayMaster.effective_element_index)]
    ) {
      roles.push('Resource');
    }
    if (
      dayMaster &&
      missingElementIndex >= 0 &&
      missingElementIndex === GOVERNOR_BY_ELEMENT[Number(dayMaster.effective_element_index)]
    ) {
      roles.push('Governor');
    }
    const roleText = roles.length ? roles.join(' + ') : 'supporting role';
    const loopHint =
      state.motifs.loops.length > 0
        ? 'It may rebalance existing loops by adding a missing transfer branch.'
        : 'It may close open chains into loops if the new branch completes a return path.';
    const bottleneckHint =
      state.motifs.bottlenecks.length > 0
        ? 'It is likely to relieve pressure around bottleneck nodes by adding alternate routes.'
        : 'It would still add optional bypass routes for future bottlenecks.';

    panel.innerHTML = `
      <div><strong>Absence Ghost</strong> · ${node.effective_element || 'Unknown'}</div>
      <div class="k">This node is not active in the current basin but shown as a structural gap.</div>
      <hr>
      <div class="detail-row"><span>Would receive from</span><span>${fromCaption}</span></div>
      <div class="detail-row"><span>Would feed into</span><span>${toCaption}</span></div>
      <div class="detail-row"><span>Role if present</span><span>${roleText}</span></div>
      <hr>
      <div><strong>Motif Impact (What-if)</strong></div>
      <div class="k">If present, this missing element would introduce new production bridges from upstream sources to downstream targets.</div>
      <div class="k">${loopHint}</div>
      <div class="k">${bottleneckHint}</div>
    `;
  }

  function topFluxRows(edges, direction, limit) {
    return edges
      .slice()
      .sort((a, b) => Number(b.abs_flux || 0) - Number(a.abs_flux || 0))
      .slice(0, limit)
      .map((edge) => {
        const source = nodeRef(edge.source);
        const target = nodeRef(edge.target);
        if (!source || !target) return '';
        const label = direction === 'out' ? target.id : source.id;
        return `
          <div class="detail-row">
            <span>${label}</span>
            <span>${formatNumber(edge.flux)}</span>
          </div>
        `;
      })
      .join('');
  }

  function renderNodeDetail(node) {
    const panel = document.getElementById('detailPanel');
    const inEdges = state.edges.filter((edge) => nodeRef(edge.target)?.id === node.id);
    const outEdges = state.edges.filter((edge) => nodeRef(edge.source)?.id === node.id);
    const absIn = inEdges.reduce((sum, edge) => sum + Number(edge.abs_flux || 0), 0);
    const absOut = outEdges.reduce((sum, edge) => sum + Number(edge.abs_flux || 0), 0);

    panel.innerHTML = `
      <div><strong>${node.id}</strong> — ${node.label}</div>
      <div class="k">${node.pillar} / ${node.hierarchy} / ${node.polarity}</div>
      <hr>
      <div class="detail-row"><span>Element</span><span>${node.effective_element}</span></div>
      <div class="detail-row"><span>Ten God</span><span>${node.ten_god} (${node.ten_god_group})</span></div>
      <div class="detail-row"><span>Life Stage</span><span>${node.vitality_stage}</span></div>
      <div class="detail-row"><span>Vitality</span><span>${formatNumber(node.dynamic_vitality)}</span></div>
      <div class="detail-row"><span>Climate T contribution</span><span>${formatNumber(node.climate_temperature_component, 2)} (weighted ${formatNumber(node.climate_temperature_weighted, 2)})</span></div>
      <div class="detail-row"><span>Climate S contribution</span><span>${formatNumber(node.climate_moisture_component, 2)} (weighted ${formatNumber(node.climate_moisture_weighted, 2)})</span></div>
      <hr>
      <div class="detail-row"><span>Total |in flux|</span><span>${formatNumber(absIn)}</span></div>
      <div class="detail-row"><span>Total |out flux|</span><span>${formatNumber(absOut)}</span></div>
      <hr>
      <div><strong>Top Outgoing</strong></div>
      ${topFluxRows(outEdges, 'out', 5) || '<div class="k">none</div>'}
      <hr>
      <div><strong>Top Incoming</strong></div>
      ${topFluxRows(inEdges, 'in', 5) || '<div class="k">none</div>'}
    `;
  }

  function renderDetail(item) {
    const panel = document.getElementById('detailPanel');
    if (!item) {
      panel.innerHTML = 'Tap a node, edge, motif, or absence ghost to inspect flow details.';
      return;
    }
    if (item.type === 'edge') {
      renderEdgeDetail(item.payload);
      return;
    }
    if (item.type === 'motif') {
      renderMotifDetail(item.payload);
      return;
    }
    if (item.type === 'node') {
      if (item.payload?.is_ghost) {
        renderGhostDetail(item.payload);
        return;
      }
      renderNodeDetail(item.payload);
    }
  }

  function setupNodeInteractions() {
    nodeSel
      .on('mouseenter', (event, node) => {
        highlightNode(node.id);
        showTooltip(
          `
            <div><strong>${node.id}</strong> \u2014 ${node.label}</div>
            <div>${node.effective_element} | ${node.ten_god_group}</div>
            <div>Vitality A: ${Number(node.dynamic_vitality || 0).toFixed(3)}</div>
          `,
          event.clientX,
          event.clientY
        );
      })
      .on('mousemove', (event) => {
        tooltip.style.left = `${event.clientX + 14}px`;
        tooltip.style.top = `${event.clientY + 14}px`;
      })
      .on('mouseleave', () => {
        hideTooltip();
        clearHighlight();
      })
      .on('click', (event, node) => {
        event.stopPropagation();
        state.selectedNodeId = node.id;
        renderDetail({ type: 'node', payload: node });
      })
      .on('dblclick', (event, node) => {
        event.stopPropagation();
        node.fx = null;
        node.fy = null;
        simulation.alphaTarget(0.08).restart();
      });

    edgeSel
      .on('mouseenter', (event, edge) => {
        const source = nodeRef(edge.source);
        const target = nodeRef(edge.target);
        if (!source || !target) return;
        showTooltip(
          `
            <div><strong>${source.id} \u2192 ${target.id}</strong></div>
            <div>F(i\u2192j) = ${Number(edge.flux || 0).toFixed(3)}</div>
            <div>|F| = ${Number(edge.abs_flux || 0).toFixed(3)} (${edge.relation})</div>
          `,
          event.clientX,
          event.clientY
        );
      })
      .on('mousemove', (event) => {
        tooltip.style.left = `${event.clientX + 14}px`;
        tooltip.style.top = `${event.clientY + 14}px`;
      })
      .on('mouseleave', hideTooltip)
      .on('click', (event, edge) => {
        event.stopPropagation();
        state.selectedNodeId = null;
        renderDetail({ type: 'edge', payload: edge });
      });

    motifSel
      .on('mouseenter', (event, segment) => {
        showTooltip(
          `
            <div><strong>${String(segment.kind || 'motif').toUpperCase()}</strong></div>
            <div>${motifNarrative(segment.kind, asArray(segment.path_nodes).map((nodeId) => String(nodeId)))}</div>
          `,
          event.clientX,
          event.clientY
        );
      })
      .on('mousemove', (event) => {
        tooltip.style.left = `${event.clientX + 14}px`;
        tooltip.style.top = `${event.clientY + 14}px`;
      })
      .on('mouseleave', hideTooltip)
      .on('click', (event, segment) => {
        event.stopPropagation();
        state.selectedNodeId = null;
        renderDetail({ type: 'motif', payload: segment });
      });

    svg.on('click', () => {
      state.selectedNodeId = null;
      renderDetail(null);
      clearHighlight();
    });
  }

  function nudgeConnectedNeighbors(node, targetX, targetY) {
    const neighbors = neighborMap.get(node.id);
    if (!neighbors) return;
    neighbors.forEach((other) => {
      if (!other || other.id === node.id) return;
      if (other.fx != null || other.fy != null) return;
      const ox = typeof other.x === 'number' ? other.x : targetX;
      const oy = typeof other.y === 'number' ? other.y : targetY;
      const dx = targetX - ox;
      const dy = targetY - oy;
      other.vx = (other.vx || 0) + dx * 0.0026;
      other.vy = (other.vy || 0) + dy * 0.0026;
    });
  }

  function setupDrag() {
    const dragBehavior = d3
      .drag()
      .on('start', (event, node) => {
        event.sourceEvent?.stopPropagation();
        if (!event.active) {
          simulation.alphaTarget(0.16).restart();
        }
        node.fx = node.x;
        node.fy = node.y;
      })
      .on('drag', (event, node) => {
        node.fx = event.x;
        node.fy = event.y;
        nudgeConnectedNeighbors(node, event.x, event.y);
        simulation.alphaTarget(0.22).restart();
      })
      .on('end', (event, node) => {
        node.fx = event.x;
        node.fy = event.y;
        if (!event.active) {
          simulation.alphaTarget(0.03);
        }
      });

    nodeSel.call(dragBehavior);
  }


  function updateStatus() {
    const visibleNodes = state.nodes.filter((node) => !nodeSel.filter((d) => d.id === node.id).classed('node-faded')).length;
    const visibleEdges =
      state.edges.filter((edge) => edgeVisible(edge, false)).length +
      state.ghostEdges.filter((edge) => edgeVisible(edge, true)).length;
    const motifSegmentsVisible = buildMotifSegments().filter((segment) => motifVisible(segment)).length;
    const activeModifiers = state.topologyModifiers.length;

    document.getElementById('statusBar').textContent =
      `${visibleNodes} nodes visible \u2022 ${visibleEdges} directed edges visible \u2022 ${motifSegmentsVisible} motif segments \u2022 ${activeModifiers} topology modifiers`;
  }

  function fitToView() {
    if (!state.views.graph) return;
    const visibleNodes = state.nodes.filter((node) => {
      if (node.is_ghost && !state.motifToggles.ghosts) return false;
      return true;
    });
    if (!visibleNodes.length) return;

    const minX = d3.min(visibleNodes, (node) => node.x ?? node.anchorX);
    const maxX = d3.max(visibleNodes, (node) => node.x ?? node.anchorX);
    const minY = d3.min(visibleNodes, (node) => node.y ?? node.anchorY);
    const maxY = d3.max(visibleNodes, (node) => node.y ?? node.anchorY);
    if (minX == null || maxX == null || minY == null || maxY == null) return;

    const dx = Math.max(1, maxX - minX + 80);
    const dy = Math.max(1, maxY - minY + 80);
    const scale = Math.min(width / dx, height / dy, 1.6);
    const tx = width / 2 - (minX + maxX) / 2 * scale;
    const ty = height / 2 - (minY + maxY) / 2 * scale;
    const transform = d3.zoomIdentity.translate(tx, ty).scale(scale);

    svg.transition().duration(420).call(zoomBehavior.transform, transform);
  }

  function rebuildGraph(shouldFit = true) {
    if (simulation) {
      simulation.stop();
    }
    canvasSize();
    createSvg();
    setAnchors();
    buildNeighborMap();
    createGraphLayers();
    setupSimulation();
    applyFilters();
    renderDetail(null);

    setTimeout(() => {
      if (!simulation) return;
      for (let i = 0; i < 160; i += 1) simulation.tick();
      ticked();
      if (shouldFit) {
        fitToView();
      }
    }, 0);
  }

  function setActiveBasin(index) {
    if (!state.basinViews.length) return;
    const nextIndex = Math.max(
      0,
      Math.min(state.basinViews.length - 1, Math.trunc(Number(index) || 0))
    );
    state.activeBasinIndex = nextIndex;
    applyBasinView(state.basinViews[nextIndex]);
    writeMetaLine();
    renderBasinTabs();
    renderBasinMetadata();
    renderPillarStrip();
    updateFluxControls();
    rebuildGraph(true);
  }

  async function boot() {
    const queryPayload = queryInputPayload();
    let graphData = GRAPH_DATA;
    if (queryPayload) {
      try {
        graphData = await loadGraphData(queryPayload);
      } catch (error) {
        console.error(error);
        const statusBar = document.getElementById('statusBar');
        if (statusBar) {
          statusBar.textContent = `Failed to load evolution data: ${error?.message || 'unknown error'}`;
        }
        return;
      }
    }
    parseData(graphData);
    setupControls();
    applyViewVisibility();
    renderLegend();
    renderBasinTabs();
    writeMetaLine();
    renderBasinMetadata();
    renderPillarStrip();
    updateFluxControls();
    rebuildGraph(true);

    let resizeTimer;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        renderPillarStrip();
        canvasSize();
        svg.attr('viewBox', `0 0 ${width} ${height}`);
        setAnchors();
        boundsForce?.setSize(width, height);
        simulation.alpha(0.45).restart();
        fitToView();
      }, 120);
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    void boot();
  });
})();
