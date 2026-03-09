(function () {
  'use strict';

  const ELEMENT_COLORS = {
    Wood: '#57a773',
    Fire: '#e4572e',
    Earth: '#caa76b',
    Metal: '#95a3b3',
    Water: '#4a90e2',
  };

  const TEN_GOD_GROUP_COLORS = {
    Self: '#8b5cf6',
    Output: '#f97316',
    Wealth: '#eab308',
    Authority: '#ef4444',
    Resource: '#14b8a6',
    None: '#6b7280',
  };

  const RELATION_COLORS = {
    production: '#22c55e',
    control: '#ef4444',
    drain: '#3b82f6',
  };

  const MOTIF_COLORS = {
    chain: '#f59e0b',
    loop: '#a855f7',
    cascade: '#ec4899',
  };

  const state = {
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
    meta: {},
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

  const tooltip = document.getElementById("tooltip");

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function nodeRef(endpoint) {
    if (typeof endpoint === 'object' && endpoint && endpoint.id) return endpoint;
    return state.nodeById.get(endpoint) || null;
  }

  function relationColor(relation) {
    return RELATION_COLORS[relation] || '#9ca3af';
  }

  function elementColor(name) {
    return ELEMENT_COLORS[name] || '#8b93a9';
  }

  function groupColor(name) {
    return TEN_GOD_GROUP_COLORS[name] || TEN_GOD_GROUP_COLORS.None;
  }

  function parseData(raw) {
    if (!raw || !Array.isArray(raw.nodes) || !Array.isArray(raw.edges)) {
      throw new Error('GRAPH_DATA must include nodes and edges arrays.');
    }

    state.nodes = raw.nodes.map((node) => ({ ...node }));
    state.edges = raw.edges.map((edge) => ({ ...edge }));
    state.ghostEdges = asArray(raw.ghost_edges).map((edge) => ({ ...edge }));
    state.motifs = {
      chains: asArray(raw.motifs?.chains),
      loops: asArray(raw.motifs?.loops),
      cascades: asArray(raw.motifs?.cascades),
      bottlenecks: asArray(raw.motifs?.bottlenecks),
      pulses: asArray(raw.motifs?.pulses),
      absences: asArray(raw.motifs?.absences),
    };
    state.meta = raw.meta || {};

    state.nodeById = new Map();
    state.nodes.forEach((node) => {
      const vitality = Number(node.dynamic_vitality || 0);
      node.radius = node.is_ghost ? 12 : 7 + vitality * 17;
      node.anchorX = 0;
      node.anchorY = 0;
      state.nodeById.set(node.id, node);
    });

    const maxAbsFlux = Math.max(
      0,
      ...state.edges.map((edge) => Number(edge.abs_flux || 0))
    );
    const domainMax = maxAbsFlux > 0 ? maxAbsFlux : 1;
    fluxScale = d3.scaleSqrt().domain([0, domainMax]).range([0.7, 5]);
  }

  function writeMetaLine() {
    const mass = Number(state.meta.basin_mass || 0) * 100;
    const text = [
      `Basin ${state.meta.basin_id ?? 0}`,
      `Mass ${mass.toFixed(1)}%`,
      `Mode ${state.meta.mode || 'Unknown'}`,
      `Chart T ${Number(state.meta.chart_temperature || 0).toFixed(3)}`,
      `Chart S ${Number(state.meta.chart_saturation || 0).toFixed(3)}`,
    ].join(' \u2022 ');
    document.getElementById('metaLine').textContent = text;
  }

  function setupControls() {
    const searchInput = document.getElementById('searchInput');
    const fluxSlider = document.getElementById('fluxThreshold');
    const fluxOutput = document.getElementById('fluxThresholdValue');
    const maxFlux = Math.max(0, ...state.edges.map((edge) => Number(edge.abs_flux || 0)));

    searchInput.addEventListener('input', () => {
      state.searchQuery = searchInput.value.trim().toLowerCase();
      applyFilters();
    });

    fluxSlider.addEventListener('input', () => {
      const ratio = Number(fluxSlider.value) / 100;
      state.minFlux = ratio * maxFlux;
      fluxOutput.textContent = state.minFlux.toFixed(2);
      applyFilters();
    });
    fluxOutput.textContent = '0.00';

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

    document.getElementById('fitButton').addEventListener('click', fitToView);
    document.getElementById('resetButton').addEventListener('click', () => {
      state.searchQuery = '';
      searchInput.value = '';
      state.minFlux = 0.0;
      fluxSlider.value = '0';
      fluxOutput.textContent = '0.00';
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
      <div class="legend-item"><span class="k">Node fill</span></div>
      ${elementHtml}
      <div style="height:8px"></div>
      <div class="legend-item"><span class="k">Node border (Ten God group)</span></div>
      ${groupHtml}
      <div style="height:8px"></div>
      <div class="legend-item"><span class="k">Flux edge relation</span></div>
      ${relationHtml}
      <div style="height:8px"></div>
      <div class="legend-item"><span class="k">Motif overlays</span></div>
      ${motifHtml}
      <div class="legend-item"><span class="swatch" style="background:transparent;border:1px dashed #9ca3af"></span>absent element ghost</div>
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
        for (let i = 0; i < path.length - 1; i += 1) {
          segments.push({
            id: `${kind}_${pathIndex}_${i}`,
            source: path[i],
            target: path[i + 1],
            kind,
          });
        }
        if (closeLoop && path.length >= 2) {
          segments.push({
            id: `${kind}_${pathIndex}_close`,
            source: path[path.length - 1],
            target: path[0],
            kind,
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
      .attr('stroke', (segment) => MOTIF_COLORS[segment.kind] || '#f8fafc')
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
      .attr('stroke', (node) => groupColor(node.ten_god_group))
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

  function setupSimulation() {
    const allLinks = [...state.edges, ...state.ghostEdges];
    simulation = d3
      .forceSimulation(state.nodes)
      .force(
        'link',
        d3.forceLink(allLinks).id((node) => node.id).distance(linkDistance).strength(linkStrength)
      )
      .force(
        'charge',
        d3.forceManyBody().strength((node) => (node.is_ghost ? -80 : -210))
      )
      .force('collision', d3.forceCollide().radius((node) => node.radius + 8))
      .force('x', d3.forceX((node) => node.anchorX).strength((node) => (node.is_ghost ? 0.62 : 0.4)))
      .force('y', d3.forceY((node) => node.anchorY).strength((node) => (node.is_ghost ? 0.62 : 0.4)))
      .alpha(0.95)
      .alphaDecay(0.07)
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
      renderDetail(state.nodeById.get(state.selectedNodeId));
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
        renderDetail(node);
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
      .on('mouseleave', hideTooltip);

    svg.on('click', () => {
      state.selectedNodeId = null;
      renderDetail(null);
      clearHighlight();
    });
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
            <span>${Number(edge.flux || 0).toFixed(3)}</span>
          </div>
        `;
      })
      .join('');
  }

  function renderDetail(node) {
    const panel = document.getElementById('detailPanel');
    if (!node) {
      panel.innerHTML = 'Select a node to inspect flux details.';
      return;
    }

    const inEdges = state.edges.filter((edge) => nodeRef(edge.target)?.id === node.id);
    const outEdges = state.edges.filter((edge) => nodeRef(edge.source)?.id === node.id);
    const absIn = inEdges.reduce((sum, edge) => sum + Number(edge.abs_flux || 0), 0);
    const absOut = outEdges.reduce((sum, edge) => sum + Number(edge.abs_flux || 0), 0);

    panel.innerHTML = `
      <div><strong>${node.id}</strong> \u2014 ${node.label}</div>
      <div class="k">${node.pillar} / ${node.hierarchy} / ${node.polarity}</div>
      <div class="k">${node.effective_element} \u2022 ${node.ten_god} (${node.ten_god_group})</div>
      <div class="k">Vitality amplitude A = ${Number(node.dynamic_vitality || 0).toFixed(3)}</div>
      <hr>
      <div class="detail-row"><span>Total |in flux|</span><span>${absIn.toFixed(3)}</span></div>
      <div class="detail-row"><span>Total |out flux|</span><span>${absOut.toFixed(3)}</span></div>
      <hr>
      <div><strong>Top Outgoing</strong></div>
      ${topFluxRows(outEdges, 'out', 5) || '<div class="k">none</div>'}
      <hr>
      <div><strong>Top Incoming</strong></div>
      ${topFluxRows(inEdges, 'in', 5) || '<div class="k">none</div>'}
    `;
  }

  function updateStatus() {
    const visibleNodes = state.nodes.filter((node) => !nodeSel.filter((d) => d.id === node.id).classed('node-faded')).length;
    const visibleEdges =
      state.edges.filter((edge) => edgeVisible(edge, false)).length +
      state.ghostEdges.filter((edge) => edgeVisible(edge, true)).length;
    const motifSegmentsVisible = buildMotifSegments().filter((segment) => motifVisible(segment)).length;

    document.getElementById('statusBar').textContent =
      `${visibleNodes} nodes visible \u2022 ${visibleEdges} directed edges visible \u2022 ${motifSegmentsVisible} motif segments`;
  }

  function fitToView() {
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

  function boot() {
    parseData(GRAPH_DATA);
    writeMetaLine();
    setupControls();
    renderLegend();
    canvasSize();
    createSvg();
    setAnchors();
    createGraphLayers();
    setupSimulation();
    applyFilters();
    renderDetail(null);

    setTimeout(() => {
      for (let i = 0; i < 160; i += 1) simulation.tick();
      ticked();
      fitToView();
    }, 0);

    let resizeTimer;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        canvasSize();
        svg.attr('viewBox', `0 0 ${width} ${height}`);
        setAnchors();
        simulation.alpha(0.45).restart();
        fitToView();
      }, 120);
    });
  }

  document.addEventListener('DOMContentLoaded', boot);
})();
