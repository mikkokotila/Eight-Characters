// The classic view's controls: local icons, preserved labels, and one accessible tooltip.
// In the toolbar's words (toolbar.js) a control marked data-control-words shows its words
// too: a switch its label alone, an action its icon and label, a topic its title.
(() => {
  if (!window.EC_ICONS || !window.EC_I18N) throw new Error('Control resources are missing.');
  const { markup } = window.EC_ICONS;
  const selectors = [
    '#display-switch button', '#luck-switch button',
    '#chart-language button', '#compare-language button', '.lang-btn',
    '#copy-link-btn', '#copy-text-btn', '#back-btn', '#new-chart-btn', '#compare-btn',
    '#relationships-topic', '#context-controls button', '.canon-day-master-line',
    '.panel-close', '.pillar-identity', '#pillars .card.branch',
    '.role-choice', '[data-root-pillar]', '[data-role-back]', '.relationship-chip',
    '.canon-line-toggle', '.canon-link', '.canon-clause', '.luck-step', '.luck-today',
    '.luck-chip', '.luck-phase', '.luck-identity', '[data-zi-convention]',
    '#compare-sides button', '#compare-swap', '#compare-copy-link', '#compare-close',
    '#compare-cancel', '#create-chart-btn', '.gender-option',
    '#page-switch button', '#today-page-switch button', '#library-btn', '#save-cancel', '#settings-close',
    '#today-language button', '.today-step', '.today-now', '#today-copy-link', '#today-copy-text',
    '#today-print', '#today-settings',
  ].join(',');
  const text = (key, vars = {}) => {
    const lang = document.documentElement.lang;
    const value = window.EC_I18N.dictionaries[lang]?.[key];
    if (typeof value !== 'string') throw new Error(`Missing control translation: ${lang}/${key}.`);
    return value.replace(/\{(\w+)\}/g, (_, token) => String(vars[token] ?? ''));
  };
  const labelOf = (node) => (node.querySelector('.control-label')?.textContent ?? node.textContent).trim();
  // While the luck pillar shows, a topic's badge adds what it brings (luck.js, through
  // app.js and day-master-context.js): Relationships 3+2, Roots 3+1, Roles +2.
  const withLuck = (node, count) => (node.dataset.controlLuck ? `${count ?? ''}${node.dataset.controlLuck}` : null);
  const firstWords = (label) => label.split(' · ')[0].trim().split(/\s+/).slice(0, 2).join(' ');
  // What the toolbar's words show of a control: a switch its label (`label`), an action
  // its icon and label (`icon-label`), a topic its title between its icon and its count
  // (`title`). Navigation keeps its icons: the steps, Today's dates, Close on a panel.
  const ACTIONS = ['copy-link-btn', 'copy-text-btn', 'back-btn', 'new-chart-btn', 'compare-btn', 'today-copy-link',
    'today-copy-text', 'today-print', 'today-settings', 'compare-swap', 'compare-copy-link', 'compare-close'];
  const fixed = {
    'copy-link-btn': ['link-2', 'link'], 'copy-text-btn': ['clipboard-list', 'copy'],
    'back-btn': ['pencil', 'edit'], 'new-chart-btn': ['square-plus', 'new'],
    'compare-btn': ['columns-2', 'compare'], 'compare-swap': ['arrow-left-right', 'swap'],
    'compare-copy-link': ['link-2', 'link'], 'compare-close': ['x', 'comparison_close'],
    'settings-close': ['x', 'settings_close'],
    'today-copy-link': ['link-2', 'link'], 'today-copy-text': ['clipboard-list', 'copy_day'],
    'today-print': ['printer', 'print'], 'today-settings': ['settings', 'settings'],
  };
  const info = (node) => {
    let label = labelOf(node);
    let icon = null; let key = null; let only = false; let count = null; let caption = null;
    let place = node; let words = null; let title = null;
    if (fixed[node.id]) { [icon, key] = fixed[node.id]; only = true; if (ACTIONS.includes(node.id)) words = 'icon-label'; }
    else if (node.matches('#display-switch button')) {
      [icon, key] = { characters: ['languages', 'characters'], 'ten-gods': ['orbit', 'gods'], 'hidden-stems': ['layers-2', 'hidden'] }[node.dataset.display];
      only = true; words = 'label';
    } else if (node.matches('#luck-switch button')) {
      [icon, key] = node.dataset.luckShow === 'off' ? ['circle-dot', 'natal'] : ['calendar-range', 'with_luck']; only = true; words = 'label';
    } else if (node.matches('#page-switch button, #today-page-switch button')) {
      [icon, key] = node.dataset.page === 'chart' ? ['columns-4', 'page_chart'] : ['sun', 'page_today']; only = true; words = 'label';
    } else if (node.matches('#chart-language button, #compare-language button, #today-language button, .lang-btn')) {
      key = (node.dataset.chartLang ?? node.dataset.compareLang ?? node.dataset.todayLang ?? node.dataset.lang) === 'fi' ? 'finnish' : 'english';
    } else if (node.id === 'relationships-topic') {
      icon = 'waypoints'; key = 'relationships'; only = true; count = node.dataset.controlCount; caption = withLuck(node, count);
      label = text('relationships'); words = 'title'; title = label;
    } else if (node.matches('[data-context]')) {
      const context = node.dataset.context;
      [icon, key] = { season: ['sun-snow', 'season'], roots: ['sprout', 'roots'], roles: ['users-round', 'roles'], 'day-master': ['chevron-down', 'master'] }[context];
      if (context === 'roots') {
        count = node.dataset.controlCount; only = Number(count) > 0; caption = withLuck(node, count);
        label = text('context_roots');
        if (only) { words = 'title'; title = node.dataset.title; }
      } else if (context === 'roles') { only = true; caption = withLuck(node, null); words = 'title'; title = node.dataset.title; }
      else if (context === 'day-master') label = text('ten_god_day_master');
    } else if (node.matches('.panel-close')) { icon = 'x'; key = 'close'; only = true; }
    else if (node.matches('.pillar-identity, .luck-identity')) {
      icon = 'chevron-down'; key = 'pillar'; label = node.querySelector('.pillar-pinyin')?.textContent.trim() ?? label;
    } else if (node.matches('.card.branch')) {
      key = node.getAttribute('aria-expanded') === 'true' ? 'hidden_close' : 'hidden_open';
      label = node.querySelector('.animal-name')?.textContent.trim() ?? text('display_hidden_stems');
    } else if (node.matches('.role-choice')) {
      icon = 'chevron-right'; key = 'role'; place = node.querySelector('.role-choice-name'); label = place.textContent.trim();
    } else if (node.matches('[data-root-pillar]')) {
      icon = 'sprout'; key = 'inspect_roots'; label = text('tip_inspect_roots_label');
    } else if (node.matches('[data-role-back]')) { icon = 'arrow-left'; key = 'back'; }
    else if (node.matches('.relationship-chip')) {
      icon = 'chevron-right'; key = 'relationship'; label = node.querySelector('.relationship-chip-label')?.textContent.trim() ?? label;
    } else if (node.matches('.canon-line-toggle')) {
      key = node.getAttribute('aria-expanded') === 'true' ? 'collapse' : 'expand'; label = node.querySelector('.canon-line-key').textContent.trim();
    } else if (node.matches('.canon-link, .canon-clause')) { icon = 'arrow-up-right'; key = 'reading'; }
    else if (node.matches('.luck-step')) {
      [icon, key] = node.dataset.luckStep === '-1' ? ['chevron-left', 'previous'] : ['chevron-right', 'next']; label = node.getAttribute('aria-label'); only = true;
    } else if (node.matches('.luck-today')) { icon = 'calendar-check'; key = 'today'; only = true; }
    else if (node.matches('.today-step')) {
      [icon, key] = node.dataset.todayStep === '-1' ? ['chevron-left', 'day_previous'] : ['chevron-right', 'day_next']; only = true;
    } else if (node.matches('.today-now')) { icon = 'calendar-check'; key = 'day_today'; only = true; }
    else if (node.matches('.luck-chip')) {
      key = node.dataset.luck === 'before' ? 'before' : 'decade';
      label = node.dataset.luck === 'before' ? text('luck_before') : node.querySelector('.luck-chip-names').textContent.trim();
    } else if (node.matches('.luck-phase')) {
      [icon, key] = node.dataset.luckPhase === 'stem' ? ['panel-top', 'stem_phase'] : ['panel-bottom', 'branch_phase'];
      place = node.querySelector('.luck-phase-name'); label = place.textContent.trim();
    } else if (node.matches('[data-zi-convention]')) {
      const midnight = node.dataset.ziConvention === 'split_midnight';
      [icon, key, caption] = midnight ? ['clock-12', 'midnight', '00:00'] : ['clock-11', 'zi', '23:00']; only = true;
    } else if (node.matches('#compare-sides button')) {
      [icon, key] = node.dataset.compareSide === 'a' ? ['panel-left', 'first'] : ['panel-right', 'second'];
    } else if (node.id === 'compare-cancel' || node.id === 'save-cancel') { icon = 'x'; key = 'cancel'; }
    else if (node.id === 'library-btn') {
      icon = 'library'; key = 'library'; label = node.querySelector('.library-label').textContent.trim();
    } else if (node.id === 'create-chart-btn') {
      [icon, key] = {
        compare_create: ['columns-2', 'compare_create'], save_create: ['bookmark-plus', 'save_create'],
      }[node.dataset.i18n] ?? ['square-plus', 'create'];
    } else if (node.matches('.gender-option')) {
      key = { '': 'gender_none', female: 'gender_female', male: 'gender_male' }[node.querySelector('input').value];
    }
    if (!key || !place) throw new Error('Unknown classic control.');
    if (key === 'copy') label = text('tip_copy_label');
    return { icon, key, label, prefix: firstWords(label), description: text('tip_' + key), only, count, caption, place, words, title };
  };
  const decorate = (node) => {
    const spec = info(node);
    if (spec.icon && !spec.place.querySelector(':scope > [data-control-icon]')) {
      if (node.matches('.luck-step')) node.replaceChildren();
      if (spec.only && !node.querySelector('.control-label')) {
        const label = document.createElement('span'); label.className = 'control-label sr-only';
        label.append(...node.childNodes); node.append(label);
      }
      spec.place.insertAdjacentHTML('afterbegin', markup(spec.icon));
      node.classList.add('has-control-icon');
    }
    if (spec.only) {
      node.classList.add('icon-control');
      if (!node.querySelector('.control-label') && node.textContent.trim()) {
        const label = document.createElement('span'); label.className = 'control-label sr-only';
        Array.from(node.childNodes).filter(child => !(child instanceof Element && child.matches('[data-control-icon], .control-caption'))).forEach(child => label.append(child));
        node.append(label);
      }
      if (spec.count !== null || spec.caption !== null) {
        let badge = node.querySelector('.control-caption');
        if (!badge) { badge = document.createElement('span'); badge.className = 'control-caption'; badge.setAttribute('aria-hidden', 'true'); node.append(badge); }
        const value = spec.caption ?? spec.count;
        if (badge.dataset.caption !== value) badge.dataset.caption = value;
      } else node.querySelector('.control-caption')?.remove();
    }
    // The page's original text stays in the DOM, including its full accessible name.
    node.dataset.controlTip = spec.key;
    if (spec.words) {
      if (node.dataset.controlWords !== spec.words) node.dataset.controlWords = spec.words;
    } else if (node.dataset.controlWords) delete node.dataset.controlWords;
    // A topic's title, shown in words between its icon and its count; its full name is
    // its label's, for a screen reader, as in icons. Drawn from its attribute, as the
    // count is, it adds nothing to the button's text, which the commands read.
    let title = node.querySelector(':scope > .control-title');
    if (spec.words === 'title') {
      if (!title) {
        title = document.createElement('span');
        title.className = 'control-title';
        title.setAttribute('aria-hidden', 'true');
        const icon = node.querySelector(':scope > [data-control-icon]');
        if (icon) icon.after(title);
        else node.prepend(title);
      }
      if (title.dataset.title !== spec.title) title.dataset.title = spec.title;
    } else title?.remove();
  };
  window.EC_CONTROLS = { label: labelOf, icon: (node) => info(node).icon };

  document.addEventListener('DOMContentLoaded', () => {
    const tip = document.createElement('div');
    tip.id = 'control-tooltip'; tip.className = 'control-tooltip'; tip.setAttribute('role', 'tooltip'); tip.setAttribute('popover', 'manual');
    const heading = document.createElement('strong'); const purpose = document.createElement('span'); tip.append(heading, purpose); document.body.append(tip);
    let active = null; let pending = null; let hoverTimer = null; let exitTimer = null; let fadeTimer = null;
    let keyboard = false; let escapeKeyDown = false; let dismissed = null; let touch = null; let suppressedClick = null; let hoveringTip = false;
    let touchInput = false;
    // From a key press until the mouse moves, layout passing controls below a still
    // pointer is not hover: it must not take the tip from the control in focus. Its place,
    // not its movement, says it moved: WebKit can report none for a real move.
    let pointerAt = null; let stillAt = null;
    const moved = (event) => {
      pointerAt = { x: event.clientX, y: event.clientY };
      if (stillAt && (stillAt.x !== pointerAt.x || stillAt.y !== pointerAt.y)) stillAt = null;
      return stillAt === null;
    };
    // In the toolbar's words a menu's items say what they do, and need no tooltip.
    const trigger = (target) => {
      const node = target instanceof Element ? target.closest(selectors) : null;
      return node && document.documentElement.dataset.toolbar === 'words' && node.closest('.bar-menu-items') ? null : node;
    };
    const cancelHover = () => { clearTimeout(hoverTimer); hoverTimer = null; pending = null; };
    const describe = (node, add) => {
      const target = node.matches('.gender-option') ? node.querySelector('input') : node;
      const ids = new Set((target.getAttribute('aria-describedby') ?? '').split(/\s+/).filter(Boolean));
      if (add) ids.add(tip.id); else ids.delete(tip.id);
      if (ids.size) target.setAttribute('aria-describedby', [...ids].join(' ')); else target.removeAttribute('aria-describedby');
    };
    const hide = () => {
      cancelHover(); clearTimeout(exitTimer); clearTimeout(fadeTimer);
      if (active) describe(active, false);
      active = null; hoveringTip = false; tip.classList.remove('is-visible');
      fadeTimer = setTimeout(() => { if (tip.matches(':popover-open')) tip.hidePopover(); }, 90);
    };
    const position = () => {
      if (!active) return;
      const rect = active.getBoundingClientRect();
      if (!active.checkVisibility() || rect.bottom < 0 || rect.top > innerHeight || rect.right < 0 || rect.left > innerWidth) { hide(); return; }
      const bounds = tip.getBoundingClientRect();
      const x = Math.max(8, Math.min(rect.left + (rect.width - bounds.width) / 2, innerWidth - bounds.width - 8));
      const cardHint = active.matches('.card.branch') ? document.querySelector('.card-hint:not(.hidden)') : null;
      const edge = cardHint?.checkVisibility() ? cardHint.getBoundingClientRect().top : rect.top;
      const above = edge - bounds.height - 8;
      tip.style.left = `${x}px`; tip.style.top = `${above >= 8 ? above : Math.min(innerHeight - bounds.height - 8, rect.bottom + 8)}px`;
    };
    window.EC_MOTION.onFrame(position);
    const show = (node) => {
      if (!node.isConnected || node.matches(':disabled') || node === dismissed) return;
      cancelHover(); clearTimeout(exitTimer); clearTimeout(fadeTimer);
      if (active && active !== node) describe(active, false);
      const spec = info(node);
      heading.textContent = spec.prefix; purpose.textContent = ` · ${spec.description}`;
      active = node; describe(node, true);
      if (!tip.matches(':popover-open')) tip.showPopover();
      position();
      requestAnimationFrame(() => { if (active === node) tip.classList.add('is-visible'); });
    };
    const schedule = (node) => {
      if (active === node) { clearTimeout(exitTimer); return; }
      if (pending === node || node === dismissed || node.matches(':disabled')) return;
      if (active) hide();
      cancelHover(); clearTimeout(exitTimer);
      pending = node;
      hoverTimer = setTimeout(() => show(node), 500);
    };
    const refresh = () => {
      document.querySelectorAll(selectors).forEach(decorate);
      if (active && (!active.isConnected || !active.checkVisibility() || active.matches(':disabled'))) hide();
      else if (active) {
        const spec = info(active); heading.textContent = spec.prefix; purpose.textContent = ` · ${spec.description}`; position();
      }
    };
    refresh();
    // Existing renderers replace labels and entire panels; decorate only those mutations.
    const observer = new MutationObserver(records => {
      if (records.some(record => !tip.contains(record.target) && (record.type !== 'attributes' || record.target === document.documentElement || record.target.matches(selectors)))) {
        observer.disconnect(); refresh(); observe();
      }
    });
    const observe = () => observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['aria-expanded', 'aria-pressed', 'data-control-count', 'data-control-luck'] });
    observe();
    new MutationObserver(() => refresh()).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    // Static tooltip text never blocks the controls below it. Pointer coordinates
    // keep its content hoverable even though its surface passes clicks through.
    const overTip = (event) => {
      if (!active || !tip.classList.contains('is-visible')) return false;
      const box = tip.getBoundingClientRect();
      return event.clientX >= box.left && event.clientX <= box.right && event.clientY >= box.top && event.clientY <= box.bottom;
    };
    document.addEventListener('pointerover', event => {
      if (event.pointerType === 'touch' || touchInput || !moved(event)) return;
      if (overTip(event)) { hoveringTip = true; cancelHover(); clearTimeout(exitTimer); return; }
      const node = trigger(event.target);
      if (node && !node.contains(event.relatedTarget)) schedule(node);
    });
    document.addEventListener('pointerout', event => {
      if (event.pointerType === 'touch' || touchInput || !moved(event)) return;
      const node = trigger(event.target);
      if (node?.contains(event.relatedTarget) || overTip(event)) return;
      if (node && pending === node) cancelHover();
      if (node && active === node) exitTimer = setTimeout(() => {
        if (!(keyboard && active?.contains(document.activeElement))) hide();
      }, 100);
      if (dismissed === node) dismissed = null;
    });
    document.addEventListener('focusin', event => {
      const node = trigger(event.target);
      if (node && escapeKeyDown) dismissed = node;
      else if (node && keyboard) show(node); else if (active && active !== node) hide();
    });
    document.addEventListener('focusout', event => {
      if (active?.contains(event.target) && !active.contains(event.relatedTarget)) hide();
      if (dismissed?.contains(event.target)) dismissed = null;
    });
    document.addEventListener('keydown', event => {
      keyboard = true; stillAt = pointerAt;
      if (pending) cancelHover();
      if (event.key === 'Escape') { escapeKeyDown = true; dismissed = active ?? pending; hide(); }
    }, true);
    document.addEventListener('keyup', event => { if (event.key === 'Escape') escapeKeyDown = false; }, true);
    document.addEventListener('pointerdown', event => {
      keyboard = false; stillAt = null; if (event.pointerType !== 'touch') pointerAt = { x: event.clientX, y: event.clientY };
      dismissed = null; touchInput = event.pointerType === 'touch';
      const node = trigger(event.target);
      if (active && active !== node && !tip.contains(event.target)) hide();
      if (event.pointerType !== 'touch' || !node || !info(node).only || node.matches(':disabled')) return;
      cancelHover(); clearTimeout(exitTimer); touch = { node, id: event.pointerId, x: event.clientX, y: event.clientY, shown: false };
      hoverTimer = setTimeout(() => { if (touch) { touch.shown = true; show(touch.node); } }, 500);
    }, true);
    // A hold is its finger's alone: another pointer's events leave it, such as the mouse
    // pointer WebKit moves back to the last tap's place after a scroll.
    document.addEventListener('pointermove', event => {
      if (touch?.id === event.pointerId && Math.hypot(event.clientX - touch.x, event.clientY - touch.y) > 10) { cancelHover(); if (touch.shown) hide(); touch = null; }
      if (event.pointerType === 'touch') return;
      if (!moved(event)) return;
      if (touchInput) {
        if (touch !== null || (event.movementX === 0 && event.movementY === 0)) return;
        // Layout can dispatch mouse enter/leave events below a stationary
        // compatibility pointer after a tap. Only mouse movement restores hover.
        touchInput = false;
        const node = trigger(event.target);
        if (node) schedule(node);
      }
      const inside = overTip(event);
      if (inside) { cancelHover(); clearTimeout(exitTimer); }
      else if (hoveringTip) {
        const node = trigger(event.target);
        if (node) schedule(node);
        else exitTimer = setTimeout(() => { if (!(keyboard && active?.contains(document.activeElement))) hide(); }, 100);
      }
      hoveringTip = inside;
    });
    document.addEventListener('pointerup', event => {
      if (touch?.id !== event.pointerId) return;
      cancelHover();
      if (touch.shown) suppressedClick = { node: touch.node, until: performance.now() + 600 };
      touch = null;
    }, true);
    document.addEventListener('pointercancel', event => { if (touch && touch.id !== event.pointerId) return; cancelHover(); touch = null; hide(); });
    document.addEventListener('click', event => {
      if (suppressedClick && performance.now() < suppressedClick.until && suppressedClick.node.contains(event.target)) {
        event.preventDefault(); event.stopImmediatePropagation(); suppressedClick = null;
      } else if (!tip.contains(event.target)) hide();
    }, true);
    document.addEventListener('contextmenu', event => { if (touch?.shown || active && info(active).only && event.pointerType === 'touch') event.preventDefault(); });
    document.addEventListener('scroll', () => { if (touch) { cancelHover(); touch = null; } position(); }, true);
    window.addEventListener('resize', position);
    document.addEventListener('visibilitychange', () => { if (document.hidden) hide(); });
    window.addEventListener('pagehide', hide);
  });
})();
