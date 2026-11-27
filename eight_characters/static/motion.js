// Natural flow: the Tactile spring selected in the interactive motion study.
// Every channel keeps its position and velocity when its destination changes.
(() => {
  'use strict';
  const model = Object.freeze({ stiffness: 180, damping: 20, mass: 1, travel: 20, feedback: 100 });
  const preference = matchMedia('(prefers-reduced-motion: reduce)');
  const channels = new WeakMap();
  const panelStates = new WeakMap();
  const disclosureStyles = new WeakMap();
  const moving = new Set();
  const frameListeners = new Set();
  let frame = 0;
  let previousTime = 0;
  const clamp = (value) => Math.max(0, Math.min(1, value));

  const mark = (owner) => {
    const active = [...channels.get(owner).values()].some((channel) => channel.active);
    owner.toggleAttribute('data-motion-running', active);
  };
  const complete = (channel) => {
    channel.active = false;
    moving.delete(channel);
    channel.write({ ...channel.value });
    mark(channel.owner);
    channel.complete?.();
  };
  const refreshTarget = (channel, now) => {
    if (!channel.resolveTarget) return;
    const next = channel.resolveTarget(now);
    for (const key of Object.keys(next)) {
      if (!Number.isFinite(next[key]) || !Number.isFinite(channel.value[key])) {
        throw new Error(`Natural flow received a non-finite ${channel.name}.${key}.`);
      }
      channel.range[key] = Math.max(channel.range[key], Math.abs(next[key] - channel.value[key]), 1);
    }
    channel.target = { ...next };
  };
  const tick = (now) => {
    const elapsed = Math.min((now - previousTime) / 1000, .032);
    previousTime = now;
    const steps = Math.max(1, Math.ceil(elapsed / .008));
    const dt = elapsed / steps;
    for (const channel of moving) {
      if (!channel.owner.isConnected) {
        channel.active = false;
        moving.delete(channel);
        mark(channel.owner);
        continue;
      }
      if (!channel.owner.getClientRects().length) {
        if (channel.name === 'scroll') cancel(channel.owner, 'scroll');
        else {
          Object.assign(channel.value, channel.target);
          Object.keys(channel.velocity).forEach((key) => { channel.velocity[key] = 0; });
          complete(channel);
        }
        continue;
      }
      if (now < channel.start) continue;
      refreshTarget(channel, now);
      let resting = true;
      for (const key of Object.keys(channel.target)) {
        for (let step = 0; step < steps; step++) {
          channel.velocity[key] += (-model.stiffness * (channel.value[key] - channel.target[key])
            - model.damping * channel.velocity[key]) / model.mass * dt;
          channel.value[key] += channel.velocity[key] * dt;
        }
        const range = channel.range[key];
        if (Math.abs(channel.value[key] - channel.target[key]) > range * .0008
          || Math.abs(channel.velocity[key]) > range * .008) resting = false;
      }
      if (resting && channel.canComplete()) {
        Object.assign(channel.value, channel.target);
        Object.keys(channel.velocity).forEach((key) => { channel.velocity[key] = 0; });
        complete(channel);
      } else channel.write({ ...channel.value });
    }
    frameListeners.forEach((listener) => listener());
    frame = moving.size ? requestAnimationFrame(tick) : 0;
  };

  const spring = (owner, name, { from, to, write, complete: done, delay = 0, rebase = false, canComplete = () => true }) => {
    const target = typeof to === 'function' ? to() : to;
    let own = channels.get(owner);
    if (!own) { own = new Map(); channels.set(owner, own); }
    let channel = own.get(name);
    if (!channel) {
      channel = { owner, name, value: { ...from }, velocity: {}, range: {}, active: false };
      own.set(name, channel);
    } else if (!channel.active) {
      channel.value = { ...from };
      channel.velocity = {};
    } else if (rebase) Object.assign(channel.value, from);
    for (const key of Object.keys(target)) {
      if (!Number.isFinite(target[key]) || !Number.isFinite(channel.value[key])) {
        throw new Error(`Natural flow received a non-finite ${name}.${key}.`);
      }
      channel.velocity[key] ??= 0;
      channel.range[key] = Math.max(1, Math.abs(target[key] - channel.value[key]));
    }
    channel.target = { ...target };
    channel.resolveTarget = typeof to === 'function' ? to : null;
    channel.canComplete = canComplete;
    channel.write = write;
    channel.complete = done;
    channel.start = performance.now() + delay;
    channel.active = true;
    if (preference.matches) {
      Object.assign(channel.value, target);
      Object.keys(channel.velocity).forEach((key) => { channel.velocity[key] = 0; });
      complete(channel);
      return;
    }
    moving.add(channel);
    mark(owner);
    write({ ...channel.value });
    if (!frame) { previousTime = performance.now(); frame = requestAnimationFrame(tick); }
  };
  const value = (owner, name) => {
    const channel = channels.get(owner)?.get(name);
    return channel?.active ? { ...channel.value } : null;
  };
  const cancel = (owner, name) => {
    const channel = channels.get(owner)?.get(name);
    if (!channel) return;
    channel.active = false;
    moving.delete(channel);
    channels.get(owner).delete(name);
    mark(owner);
  };
  const finish = () => {
    // Scroll destinations depend on the final sizes of their disclosures and panels.
    const ordered = [...moving].sort((a, b) => Number(a.name === 'scroll') - Number(b.name === 'scroll'));
    for (const channel of ordered) {
      if (channel.owner.getClientRects().length) refreshTarget(channel);
      else if (channel.name === 'scroll') { cancel(channel.owner, 'scroll'); continue; }
      Object.assign(channel.value, channel.target);
      Object.keys(channel.velocity).forEach((key) => { channel.velocity[key] = 0; });
      complete(channel);
    }
  };

  const disclose = (element, open, animate = true, after = null) => {
    const layoutHeight = () => {
      const style = getComputedStyle(element);
      let height = Number.parseFloat(style.height);
      if (style.boxSizing !== 'border-box') {
        for (const key of ['paddingTop', 'paddingBottom', 'borderTopWidth', 'borderBottomWidth']) height += Number.parseFloat(style[key]);
      }
      return height;
    };
    if (!disclosureStyles.has(element)) disclosureStyles.set(element, {
      paddingTop: element.style.paddingTop, paddingBottom: element.style.paddingBottom,
    });
    const original = disclosureStyles.get(element);
    const from = { height: element.hidden ? 0 : layoutHeight(),
      opacity: element.hidden ? 0 : Number(getComputedStyle(element).opacity),
      paddingTop: element.hidden ? 0 : Number.parseFloat(getComputedStyle(element).paddingTop),
      padding: element.hidden ? 0 : Number.parseFloat(getComputedStyle(element).paddingBottom) };
    if (open) element.hidden = false;
    element.style.paddingTop = original.paddingTop;
    element.style.paddingBottom = original.paddingBottom;
    element.style.height = 'auto';
    const natural = { height: layoutHeight(),
      paddingTop: Number.parseFloat(getComputedStyle(element).paddingTop),
      padding: Number.parseFloat(getComputedStyle(element).paddingBottom) };
    element.setAttribute('data-flow-disclosure', '');
    element.inert = !open;
    if (!animate) {
      cancel(element, 'disclosure');
      element.style.height = open ? 'auto' : '0px';
      element.style.opacity = open ? '1' : '0';
      element.removeAttribute('data-flow-disclosure');
      after?.();
      return;
    }
    spring(element, 'disclosure', {
      from,
      to: { height: open ? natural.height : 0, opacity: open ? 1 : 0,
        paddingTop: open ? natural.paddingTop : 0, padding: open ? natural.padding : 0 },
      write: ({ height, opacity, paddingTop, padding }) => {
        element.style.height = `${Math.max(0, height)}px`;
        element.style.paddingTop = `${Math.max(0, paddingTop)}px`;
        element.style.paddingBottom = `${Math.max(0, padding)}px`;
        element.style.opacity = String(clamp(opacity));
      },
      complete: () => { element.style.height = open ? 'auto' : '0px';
        element.style.paddingTop = original.paddingTop; element.style.paddingBottom = original.paddingBottom;
        element.removeAttribute('data-flow-disclosure'); after?.(); },
    });
  };
  const reveal = (element, { distance = model.travel, delay = 0 } = {}) => {
    spring(element, 'reveal', {
      from: { progress: 0 }, to: { progress: 1 }, delay,
      write: ({ progress }) => {
        element.style.opacity = String(clamp(progress));
        element.style.setProperty('--flow-enter-y', `${(1 - progress) * distance}px`);
        element.setAttribute('data-flow-enter', '');
      },
      complete: () => { element.style.opacity = ''; element.style.removeProperty('--flow-enter-y');
        element.removeAttribute('data-flow-enter'); cancel(element, 'reveal'); },
    });
  };

  const layout = (root, change, selector = ':scope > *') => {
    const elements = [...root.querySelectorAll(selector)];
    const identity = (element) => element.dataset.flowKey ?? element;
    const before = new Map(elements.map((element) => [identity(element), { element, box: element.getBoundingClientRect() }]));
    const result = change();
    for (const element of root.querySelectorAll(selector)) {
      const previous = before.get(identity(element));
      if (!previous || !previous.box.width || !previous.box.height) continue;
      const old = previous.box;
      // A replaced actor keeps its identity's live momentum (comparison frames
      // reload when reordered, so moving the old DOM node is not an option).
      const channel = channels.get(previous.element)?.get('layout');
      if (previous.element !== element && channel?.active) {
        channels.get(previous.element).delete('layout');
        mark(previous.element);
        let own = channels.get(element);
        if (!own) { own = new Map(); channels.set(element, own); }
        channel.owner = element;
        own.set('layout', channel);
      }
      element.removeAttribute('data-flow-layout');
      ['x', 'y', 'sx', 'sy'].forEach((key) => element.style.removeProperty(`--flow-layout-${key}`));
      element.setAttribute('data-flow-layout', '');
      const next = element.getBoundingClientRect();
      if (!next.width || !next.height) { element.removeAttribute('data-flow-layout'); continue; }
      const from = { x: old.left - next.left, y: old.top - next.top,
        sx: old.width / next.width, sy: old.height / next.height };
      const transform = getComputedStyle(element).transform;
      if (transform !== 'none') {
        const native = new DOMMatrix(transform);
        // Individual scale precedes the actor's native transform. Its translation
        // is scaled too, so the inverse must remove that additional displacement.
        from.x -= native.e * (from.sx - 1);
        from.y -= native.f * (from.sy - 1);
      }
      if (Math.abs(from.x) < .5 && Math.abs(from.y) < .5
        && Math.abs(from.sx - 1) < .001 && Math.abs(from.sy - 1) < .001
        && !channels.get(element)?.get('layout')?.active) { element.removeAttribute('data-flow-layout'); continue; }
      spring(element, 'layout', { from, to: { x: 0, y: 0, sx: 1, sy: 1 }, rebase: true,
        write: ({ x, y, sx, sy }) => {
          element.style.setProperty('--flow-layout-x', `${x}px`); element.style.setProperty('--flow-layout-y', `${y}px`);
          element.style.setProperty('--flow-layout-sx', String(sx)); element.style.setProperty('--flow-layout-sy', String(sy));
        },
        complete: () => {
          element.removeAttribute('data-flow-layout');
          ['x', 'y', 'sx', 'sy'].forEach((key) => element.style.removeProperty(`--flow-layout-${key}`));
          cancel(element, 'layout');
        },
      });
    }
    return result;
  };
  const scroll = (element, left, top = element.scrollTop, { pending = () => false } = {}) => {
    const bounded = (value, maximum) => Math.max(0, Math.min(maximum, value));
    const bounds = () => ({ left: Math.max(0, element.scrollWidth - element.clientWidth),
      top: Math.max(0, element.scrollHeight - element.clientHeight) });
    spring(element, 'scroll', {
      from: { left: element.scrollLeft, top: element.scrollTop }, rebase: true,
      to: () => {
        const maximum = bounds();
        const requestedTop = typeof top === 'function' ? top() : top;
        if (!Number.isFinite(left) || !Number.isFinite(requestedTop)) throw new Error('Natural flow received a non-finite scroll destination.');
        return { left: bounded(left, maximum.left), top: bounded(requestedTop, maximum.top) };
      },
      canComplete: () => !pending(),
      write: (next) => {
        const maximum = bounds();
        const channel = channels.get(element).get('scroll');
        for (const key of ['left', 'top']) {
          const position = bounded(next[key], maximum[key]);
          if (position !== next[key]) { channel.value[key] = position; channel.velocity[key] = 0; }
          element[key === 'left' ? 'scrollLeft' : 'scrollTop'] = position;
        }
      },
      complete: () => cancel(element, 'scroll'),
    });
  };
  const interruptScroll = (event) => {
    if (event.type === 'keydown' && !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event.key)) return;
    for (const channel of [...moving]) {
      if (channels.get(channel.owner)?.get('scroll') === channel && channel.owner.contains(event.target)) {
        cancel(channel.owner, 'scroll');
      }
    }
  };
  ['wheel', 'pointerdown', 'touchstart'].forEach((type) => document.addEventListener(type, interruptScroll, { capture: true, passive: true }));
  document.addEventListener('keydown', interruptScroll, true);

  const retire = (element) => {
    queueMicrotask(() => {
      if (!element.classList.contains('hidden')) return;
      const parent = element.closest('.chart-panel');
      if (!parent || !parent.hasAttribute('data-flow-leaving') || element.closest('.chart-container.hidden')) {
        element.replaceChildren(); return;
      }
      element.setAttribute('data-flow-retain', '');
      panelStates.get(parent).retired.add(element);
    });
  };
  const panel = (element, open) => {
    const body = element.querySelector(':scope > .chart-panel-body');
    if (!body) throw new Error('Natural flow panel content is missing.');
    let state = panelStates.get(element);
    if (!state) {
      state = { open: false, box: null, retired: new Set(), saved: null, originalHeight: element.style.height };
      panelStates.set(element, state);
      new ResizeObserver(() => {
        if (state.open && !element.closest('.hidden')) state.box = element.getBoundingClientRect();
      }).observe(element);
    }
    const resize = (fromHeight) => {
      if (!element.getClientRects().length) {
        cancel(element, 'panel-size'); element.style.height = state.originalHeight; state.box = null; return;
      }
      const destination = () => {
        const style = getComputedStyle(element);
        const edges = ['paddingTop', 'paddingBottom', 'borderTopWidth', 'borderBottomWidth']
          .reduce((height, key) => height + Number.parseFloat(style[key]), 0);
        const height = Number.parseFloat(getComputedStyle(body).height) + edges;
        return { height: Math.max(edges, Math.min(height, style.maxHeight === 'none' ? Infinity : Number.parseFloat(style.maxHeight))) };
      };
      const targetHeight = destination().height;
      if (Math.abs(targetHeight - fromHeight) > .5 || value(element, 'panel-size') !== null) {
        spring(element, 'panel-size', {
          from: { height: fromHeight },
          to: destination,
          canComplete: () => !element.querySelector('[data-flow-disclosure]'),
          write: ({ height }) => { element.style.height = `${Math.max(0, height)}px`; },
          complete: () => { element.style.height = state.originalHeight;
            state.box = element.getClientRects().length ? element.getBoundingClientRect() : null; cancel(element, 'panel-size'); },
        });
      }
    };
    if (state.open === open) {
      if (open && state.box !== null) resize(value(element, 'panel-size')?.height ?? state.box.height);
      return;
    }
    const reopeningHeight = open && state.saved ? element.getBoundingClientRect().height : null;
    const sizing = value(element, 'panel-size');
    const heldHeight = sizing === null ? null : element.getBoundingClientRect().height;
    cancel(element, 'panel-size');
    element.style.height = state.originalHeight;
    state.open = open;
    element.inert = !open;
    if (!open) cancel(element, 'scroll');
    if (open) {
      for (const child of state.retired) {
        child.removeAttribute('data-flow-retain');
        if (child.classList.contains('hidden')) child.replaceChildren();
      }
      state.retired.clear();
      if (state.saved) { Object.assign(element.style, state.saved); state.saved = null; }
      element.removeAttribute('data-flow-leaving'); element.classList.remove('hidden');
      if (reopeningHeight !== null) resize(reopeningHeight);
      state.box = element.getBoundingClientRect();
    } else {
      const current = element.getBoundingClientRect();
      const height = heldHeight ?? (state.box === null ? current.height : state.box.height);
      const y = Number.parseFloat(element.style.getPropertyValue('--flow-enter-y') || '0');
      const box = { left: current.left - Number.parseFloat(element.style.getPropertyValue('--flow-enter-x') || '0'),
        top: (window.innerWidth < 1200 ? current.bottom - height : current.top) - y,
        width: current.width, height };
      state.saved ??= Object.fromEntries(['position', 'left', 'top', 'right', 'bottom', 'width', 'height', 'margin']
        .map((key) => [key, element.style[key]]));
      element.setAttribute('data-flow-leaving', '');
      Object.assign(element.style, { position: 'fixed', left: `${box.left}px`, top: `${box.top}px`,
        right: 'auto', bottom: 'auto', width: `${box.width}px`, height: `${box.height}px`, margin: '0' });
      element.classList.add('hidden');
    }
    spring(element, 'panel', {
      from: { progress: open ? 0 : 1 }, to: { progress: open ? 1 : 0 },
      write: ({ progress }) => {
        element.style.opacity = String(clamp(progress));
        const horizontal = window.innerWidth >= 1200;
        element.style.setProperty('--flow-enter-x', `${horizontal ? (1 - progress) * model.travel : 0}px`);
        element.style.setProperty('--flow-enter-y', `${horizontal ? 0 : (1 - progress) * model.travel}px`);
        element.setAttribute('data-flow-enter', '');
      },
      complete: () => {
        element.style.opacity = ''; element.style.removeProperty('--flow-enter-y'); element.style.removeProperty('--flow-enter-x'); element.removeAttribute('data-flow-enter');
        if (!open) {
          element.removeAttribute('data-flow-leaving'); Object.assign(element.style, state.saved); state.saved = null;
          for (const child of state.retired) { child.removeAttribute('data-flow-retain'); child.replaceChildren(); }
          state.retired.clear();
        }
      },
    });
  };

  // Semantic surfaces enter as one unit. Updating a reading does not replay a
  // chart's entrance, and focus/selection changes never trigger decorative motion.
  document.addEventListener('DOMContentLoaded', () => {
    const scenes = '#input-view, #chart-view, #today-view, #today-body, #settings-view, #compare-view, '
      + '#account-start, #account-code-step, #account-menu, .life, .luck-ribbon, '
      + '#location-suggestions, #settings-location-suggestions';
    const contents = '#context-detail, #pillar-detail, #luck-detail, #relationship-detail, '
      + '#today-detail, #today-scale, #today-pillars, #today-couple, #today-in-chart, #today-hours, '
      + '#settings-charts-body, #library-list, '
      + '#parameterPane, #legendPanel, #detailPanel, #basinMetaPanel, #pillarStrip, #modifierBands';
    const previous = new WeakMap();
    document.querySelectorAll(contents).forEach((element) => previous.set(element, element.innerHTML));
    const observer = new MutationObserver((records) => {
      const changed = new Set();
      const scenesSeen = new Set();
      for (const record of records) {
        const element = record.target;
        if (!(element instanceof Element)) continue;
        if (record.type === 'attributes' && element.matches(scenes) && !scenesSeen.has(element)) {
          scenesSeen.add(element);
          const wasHidden = (record.oldValue || '').split(/\s+/).includes('hidden');
          if (wasHidden && !element.classList.contains('hidden')
            && !(element.id === 'chart-view' && document.documentElement.classList.contains('is-embedded'))) {
            const surface = ['chart-view', 'today-view'].includes(element.id)
              ? element.querySelector(':scope > .chart-column') : element;
            if (!surface) throw new Error(`Natural flow has no surface for ${element.id}.`);
            reveal(surface);
          }
        }
        if (record.type === 'childList') {
          for (const node of record.addedNodes) {
            if (node instanceof Element && node.matches('.relationship-arcs, .luck-arcs') && node.getClientRects().length) {
              reveal(node, { distance: 0, delay: Number.parseFloat(css.getPropertyValue('--flow-settle')) / 3 });
            }
          }
          const surface = element.closest(contents);
          if (surface) changed.add(surface);
        }
      }
      for (const element of changed) {
        const html = element.innerHTML;
        if (previous.get(element) === html) continue;
        previous.set(element, html);
        if (element.getClientRects().length && !element.closest('.hidden')) reveal(element, { distance: 8 });
      }
    });
    observer.observe(document.body, { subtree: true, childList: true, attributes: true,
      attributeFilter: ['class'], attributeOldValue: true });
  });

  // CSS-only feedback samples this same spring; spatial transitions use the live
  // integrator so a reversal preserves velocity instead of restarting an easing.
  let position = 0, velocity = 0;
  const samples = [0];
  do {
    velocity += (-model.stiffness * (position - 1) - model.damping * velocity) * .008;
    position += velocity * .008;
    samples.push(position);
  } while (Math.abs(position - 1) > .0008 || Math.abs(velocity) > .008);
  samples[samples.length - 1] = 1;
  const css = document.documentElement.style;
  css.setProperty('--flow-settle', `${(samples.length - 1) * 8}ms`);
  css.setProperty('--flow-spring', `linear(${samples.map((sample) => sample.toFixed(5)).join(',')})`);
  css.setProperty('--flow-feedback', `${model.feedback}ms`);
  preference.addEventListener('change', () => { if (preference.matches) finish(); });
  window.addEventListener('beforeprint', finish);
  // Direct viewport resizing takes over from animation. Old coordinate offsets
  // must not survive into a different responsive layout or constrain its sizes.
  window.addEventListener('resize', finish);
  window.EC_MOTION = Object.freeze({ model, spring, value, cancel, disclose, reveal, layout, scroll, panel, retire, finish,
    onFrame: (listener) => { frameListeners.add(listener); return () => frameListeners.delete(listener); },
    reduced: () => preference.matches, active: () => moving.size > 0 });
})();
