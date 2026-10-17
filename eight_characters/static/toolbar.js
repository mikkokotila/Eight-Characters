// The toolbar's two ways (docs/Standard-Toolbar.md). In words, the default, every switch
// says what it does and the actions gather in one menu; in icons, every switch and
// action is an icon, its words in a tooltip, one press away. The page carries the way as
// <html data-toolbar>, which the stylesheet reads; each browser keeps its own.
(() => {
  const KEY = 'eight_characters_toolbar';
  const WAYS = ['words', 'icons'];
  const root = document.documentElement;
  const kept = localStorage.getItem(KEY);
  if (kept !== null && !WAYS.includes(kept)) throw new Error(`This browser keeps an unknown toolbar: ${kept}.`);

  // Each menu's parts: in words a menu button and its menu of items, in icons nothing but
  // the buttons themselves, standing in the bar.
  const menus = [];
  // In a comparison's frame (app.js says so) the bar keeps only Copy as text: no menu.
  let embedded = false;
  const roles = (menu, words) => {
    const { button, list } = menu;
    button.hidden = !words;
    if (words) list.setAttribute('role', 'menu');
    else list.removeAttribute('role');
    list.querySelectorAll(':scope > button').forEach((item) => {
      if (words) {
        item.setAttribute('role', 'menuitem');
        item.tabIndex = -1;
      } else {
        item.removeAttribute('role');
        item.removeAttribute('tabindex');
      }
    });
    list.querySelectorAll(':scope > .bar-menu-rule').forEach((rule) => {
      if (words) rule.setAttribute('role', 'separator');
      else rule.removeAttribute('role');
    });
  };
  const way = () => root.dataset.toolbar;
  const take = (next) => {
    if (!WAYS.includes(next)) throw new Error(`Unknown toolbar: ${next}.`);
    root.dataset.toolbar = next;
    menus.forEach((menu) => {
      menu.close(false);
      roles(menu, next === 'words' && !embedded);
    });
  };
  take(kept ?? 'words');

  // An item can be chosen while it is shown: the comparison's frames leave some out.
  const shown = (item) => item.getClientRects().length > 0;
  const setUp = (holder) => {
    const button = holder.querySelector(':scope > .bar-menu-button');
    const list = holder.querySelector(':scope > .bar-menu-items');
    if (!button || !list) throw new Error('A bar menu needs its button and its items.');
    const items = () => [...list.querySelectorAll(':scope > button')].filter(shown);
    const isOpen = () => list.classList.contains('is-open');
    const menu = { button, list };
    // Opens the menu with an item focused: the first, or the last.
    const open = (at) => {
      list.classList.add('is-open');
      button.setAttribute('aria-expanded', 'true');
      const all = items();
      all[at === 'last' ? all.length - 1 : 0]?.focus();
    };
    // Closes it; `back` hands the focus to the menu button, as when an item was chosen
    // or Escape pressed, unless the item chosen sent it elsewhere.
    menu.close = (back) => {
      if (!isOpen()) return;
      list.classList.remove('is-open');
      button.setAttribute('aria-expanded', 'false');
      if (back && (list.contains(document.activeElement) || document.activeElement === document.body)) button.focus();
    };
    button.addEventListener('click', () => {
      if (isOpen()) menu.close(true);
      else open('first');
    });
    button.addEventListener('keydown', (event) => {
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
      event.preventDefault();
      event.stopPropagation();
      open(event.key === 'ArrowUp' ? 'last' : 'first');
    });
    list.addEventListener('keydown', (event) => {
      if (!isOpen()) return;
      if (event.key === 'Tab') {
        menu.close(false);
        return;
      }
      // The page's own keys rest while a menu is open.
      event.stopPropagation();
      const all = items();
      const at = all.indexOf(document.activeElement);
      const go = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: all.length - 1 }[event.key];
      if (go !== undefined) {
        event.preventDefault();
        all[(go + all.length) % all.length].focus();
      } else if (event.key === 'Escape') {
        event.preventDefault();
        menu.close(true);
      }
    });
    // An item chosen does what it does, as its button would, and the menu closes. One
    // that is unavailable now (the day's Copy before its answer) leaves it open.
    list.addEventListener('click', (event) => {
      const item = event.target.closest('button');
      if (!isOpen() || !item || item.getAttribute('aria-disabled') === 'true') return;
      menu.close(true);
    });
    holder.addEventListener('focusout', (event) => {
      if (isOpen() && !holder.contains(event.relatedTarget) && event.relatedTarget !== null) menu.close(false);
    });
    document.addEventListener('pointerdown', (event) => {
      if (isOpen() && !holder.contains(event.target)) menu.close(false);
    }, true);
    menus.push(menu);
    roles(menu, way() === 'words' && !embedded);
  };
  document.querySelectorAll('[data-bar-menu]').forEach(setUp);

  // Chosen in another of this browser's tabs: this one follows at once.
  window.addEventListener('storage', (event) => {
    if (event.key === KEY && event.newValue !== null) take(event.newValue);
  });

  window.EC_TOOLBAR = {
    WAYS,
    way,
    // Chosen in Settings: the page takes it at once, and this browser keeps it.
    choose: (next) => {
      take(next);
      localStorage.setItem(KEY, next);
    },
    // A comparison's frame: its bar's buttons stand in the bar, in either way.
    embed: () => {
      embedded = true;
      take(way());
    },
  };
})();
