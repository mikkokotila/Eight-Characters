// What a line in the panel names, pointed out on the chart. Resting the pointer on a line
// for half a second rings the cards, hidden-stem rows and arcs it names; while a ring
// shows, the next line rings at once. Keyboard focus on a control in the panel rings at
// once. A click or tap on a line that leads nowhere else keeps its ring until it is
// clicked again. Nothing on the chart moves, opens, turns or changes colour.
(() => {
  const DWELL_MS = 500;
  // Between one line and the next: the ring holds, and the next follows at once.
  const GRACE_MS = 200;
  const create = ({ root, escape: esc }) => {
    const panel = root.querySelector('#chart-panel');
    const pillars = root.querySelector('#pillars');
    if (!panel || !pillars) throw new Error('Spotlight view is incomplete.');

    // A line names what it points at as tokens: stem:<pillar>, branch:<pillar>,
    // hidden:<pillar>:<stem> (its branch card, and its row on the card's back and in
    // the opened hidden stems) and arc:<relationship id>.
    const card = (component, pillar) => pillars.querySelector(`.card.${component}[data-pillar="${pillar}"]`);
    const resolve = (token) => {
      const at = token.indexOf(':');
      const kind = token.slice(0, at);
      const value = token.slice(at + 1);
      if (kind === 'stem' || kind === 'branch') return [card(kind, value)].filter(Boolean);
      if (kind === 'hidden') {
        const [pillar, char] = value.split(':');
        const rows = [...pillars.querySelectorAll(`.pillar[data-pillar="${pillar}"] [data-hidden-stem="${char}"]`)];
        return card('branch', pillar) && rows.length === 2 ? [card('branch', pillar), ...rows] : [];
      }
      if (kind === 'arc') return [...pillars.querySelectorAll('.relationship-arc')].filter((arc) => arc.dataset.relationshipId === value);
      return [];
    };
    const of = (e) => (e.component === 'stem' ? `stem:${e.pillar}` : `hidden:${e.pillar}:${e.char}`);
    // Checked as a page is built: a line names only what the chart shows. A line that
    // names nothing (an absent role) points at nothing.
    const attr = (tokens) => {
      const unique = [...new Set(tokens)];
      unique.forEach((token) => {
        if (!resolve(token).length) throw new Error(`The chart shows nothing for ${token}.`);
      });
      return unique.length ? ` data-spot="${esc(unique.join(' '))}"` : '';
    };

    let shown = null; // { item, targets }: the line whose targets are ringed
    let hovered = null; // the line under the pointer
    let pinned = null; // the line a click keeps
    let engaged = false; // a ring showed a moment ago: the next follows at once
    let dwell = 0;
    let grace = 0;
    let last = null; // where the pointer last moved

    const ring = (item) => {
      if (shown?.item === item) return;
      if (shown) {
        shown.targets.forEach((node) => node.classList.remove('is-spotlit'));
        shown.item.classList.remove('is-spot-source');
        delete pillars.dataset.spotlight;
        shown = null;
      }
      if (!item) return;
      const targets = item.dataset.spot.split(' ').flatMap(resolve);
      if (!targets.length) throw new Error(`The chart shows nothing for ${item.dataset.spot}.`);
      targets.forEach((node) => node.classList.add('is-spotlit'));
      item.classList.add('is-spot-source');
      pillars.dataset.spotlight = '';
      shown = { item, targets };
    };
    const itemOf = (node) => (node instanceof Element ? node.closest('[data-spot]') : null);

    const hover = (item) => {
      if (item === hovered) return;
      hovered = item;
      clearTimeout(dwell);
      clearTimeout(grace);
      if (item && engaged) ring(item);
      else if (item) dwell = setTimeout(() => { engaged = true; ring(item); }, DWELL_MS);
      else grace = setTimeout(() => { engaged = false; ring(pinned); }, GRACE_MS);
    };
    panel.addEventListener('pointermove', (event) => {
      if (event.pointerType === 'touch') return;
      // The pointer's own movement counts, not a page redrawn under a pointer at rest.
      if (last && last.x === event.clientX && last.y === event.clientY) return;
      last = { x: event.clientX, y: event.clientY };
      hover(itemOf(event.target));
    });
    panel.addEventListener('pointerleave', (event) => {
      if (event.pointerType === 'touch') return;
      last = null;
      hover(null);
    });
    // A press acts on the line; its ring waits until the pointer moves again.
    panel.addEventListener('pointerdown', () => {
      clearTimeout(dwell);
      clearTimeout(grace);
      hovered = null;
      engaged = false;
      ring(pinned);
    });
    // A control keeps its own action; a line that leads nowhere else keeps its ring.
    panel.addEventListener('click', (event) => {
      const item = itemOf(event.target);
      if (!item || event.target.closest('button')) return;
      pinned?.classList.remove('is-spot-pinned');
      pinned = pinned === item ? null : item;
      pinned?.classList.add('is-spot-pinned');
      ring(pinned);
    });
    panel.addEventListener('focusin', (event) => {
      const item = itemOf(event.target);
      if (item && event.target.matches(':focus-visible')) ring(item);
    });
    panel.addEventListener('focusout', (event) => {
      if (shown && shown.item === itemOf(event.target) && shown.item !== pinned) ring(pinned);
    });

    // A page redrawn or closed takes its lines with it, and their rings.
    const gone = (node) => node !== null && (!node.isConnected || !node.checkVisibility());
    new MutationObserver(() => {
      if (gone(hovered)) {
        hovered = null;
        clearTimeout(dwell);
      }
      if (gone(pinned)) pinned = null;
      if (shown && gone(shown.item)) {
        engaged = false;
        ring(pinned);
      }
    }).observe(panel, { subtree: true, childList: true, attributes: true, attributeFilter: ['class'] });

    return { of, attr };
  };
  window.EC_SPOTLIGHT = { create };
})();
