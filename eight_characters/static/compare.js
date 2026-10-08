// Two charts side by side. Each is the chart view itself, embedded in a frame of its own
// (?embed=1) with its own topics and panel; this page holds the pair: its address, its
// language, which side is which and, on a narrow screen, which of the two is shown.
(() => {
  const SIDES = ['a', 'b'];
  const create = ({ view, translate: t, heading, onAddress, onLanguage, onClose, toast, ready }) => {
    const charts = view.querySelector('#compare-charts');
    const shownSwitch = view.querySelector('#compare-sides');
    const languageSwitch = view.querySelector('#compare-language');
    const swapButton = view.querySelector('#compare-swap');
    const copyButton = view.querySelector('#compare-copy-link');
    const closeButton = view.querySelector('#compare-close');
    if (!charts || !shownSwitch || !languageSwitch || !swapButton || !copyButton || !closeButton) {
      throw new Error('Comparison view is incomplete.');
    }
    if (typeof ready !== 'function') throw new Error('The comparison needs the page to make sure of the session.');
    // Each side's chart link (its fragment's parameters), its frame, and the language.
    let pair = null;
    let language = null;
    const frames = {};
    // The check of the session under way before the frames ask for their charts again,
    // or null.
    let checking = null;

    const address = () => `#compare?${new URLSearchParams({ a: pair.a, b: pair.b })}`;
    // A chart's link in another language.
    const inLanguage = (params, lang) => {
      const next = new URLSearchParams(params);
      next.set('lang', lang);
      return next.toString();
    };
    const title = () => {
      SIDES.forEach((side, index) => {
        frames[side].title = t('compare_frame', { n: index + 1, chart: heading(pair[side]) });
      });
      document.title = t('compare_page_title', { first: heading(pair.a), second: heading(pair.b) });
    };
    const showSide = (side) => {
      charts.dataset.shown = side;
      shownSwitch.querySelectorAll('button[data-compare-side]').forEach((button) => {
        button.setAttribute('aria-pressed', String(button.dataset.compareSide === side));
      });
    };
    const pressLanguage = (lang) => {
      languageSwitch.querySelectorAll('button[data-compare-lang]').forEach((button) => {
        button.setAttribute('aria-pressed', String(button.dataset.compareLang === lang));
      });
    };
    const setChecking = (check) => {
      checking = check;
      if (check === null) view.removeAttribute('aria-busy');
      else view.setAttribute('aria-busy', 'true');
    };

    // A new frame for each chart: a frame's first page replaces its blank one, so it adds
    // nothing to the history.
    const show = (a, b, lang) => {
      hide();
      pair = { a, b };
      language = lang;
      SIDES.forEach((side) => {
        const frame = document.createElement('iframe');
        frame.className = 'compare-frame';
        frame.dataset.side = side;
        frame.src = `${location.pathname}?embed=1#chart?${pair[side]}`;
        charts.append(frame);
        frames[side] = frame;
      });
      title();
      showSide('a');
      pressLanguage(lang);
      view.classList.remove('hidden');
    };
    const hide = () => {
      SIDES.forEach((side) => {
        frames[side]?.remove();
        delete frames[side];
      });
      pair = null;
      language = null;
      setChecking(null);
      view.classList.add('hidden');
    };
    // Before the frames ask for their charts again (in another language, or with the
    // sides swapped), the page makes sure of the session (`ready`): the frames cannot ask
    // for a sign-in themselves. Meanwhile the comparison is busy, and its language and
    // sides take no clicks, so one change is made at a time, to the comparison as it then
    // stands. Answers with the page's language, which a sign-in may have set, or null:
    // without a session, or with the comparison left or shown anew meanwhile, nothing
    // changes.
    const whenReady = async () => {
      if (checking !== null) return null;
      const asked = pair;
      const check = {};
      setChecking(check);
      try {
        const lang = await ready();
        return pair === asked ? lang : null;
      } finally {
        if (checking === check) setChecking(null);
      }
    };

    // Each chart tells its new address (another topic, display, convention or language).
    window.addEventListener('message', (event) => {
      if (pair === null || event.origin !== location.origin || event.data?.type !== 'ec-chart') return;
      const side = SIDES.find((key) => frames[key].contentWindow === event.source);
      if (!side) return;
      if (!event.data.hash.startsWith('#chart?')) throw new Error(`A compared chart told no chart: ${event.data.hash}`);
      pair[side] = event.data.hash.slice('#chart?'.length);
      title();
      onAddress(address());
    });

    shownSwitch.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-compare-side]');
      if (button) showSide(button.dataset.compareSide);
    });
    // Both charts are asked for again in the language, once the session is made sure of;
    // each tells its new address.
    languageSwitch.addEventListener('click', async (event) => {
      const button = event.target.closest('button[data-compare-lang]');
      if (!button || button.getAttribute('aria-pressed') === 'true') return;
      if ((await whenReady()) === null) return;
      const lang = button.dataset.compareLang;
      language = lang;
      onLanguage(lang);
      pressLanguage(lang);
      SIDES.forEach((side) => frames[side].contentWindow.postMessage({ type: 'ec-language', lang }, location.origin));
    });
    // The charts change sides. A frame moved in the page would load again from its first
    // link, so both are drawn anew from their links as they stand, with what is open in
    // them; the order they are read in stays the order they are seen in. The session is
    // made sure of first, as for the language; a sign-in asked for then sets the page's
    // language, which both charts take.
    swapButton.addEventListener('click', async () => {
      const lang = await whenReady();
      if (lang === null) return;
      const shown = charts.dataset.shown === 'a' ? 'b' : 'a';
      const [a, b] = lang === language ? [pair.b, pair.a] : [inLanguage(pair.b, lang), inLanguage(pair.a, lang)];
      show(a, b, lang);
      showSide(shown);
      onAddress(address());
    });
    copyButton.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(location.href);
        toast(t('compare_link_copied'), false);
      } catch (err) {
        console.error(err);
        toast(t('link_copy_error'), true);
      }
    });
    closeButton.addEventListener('click', () => onClose(pair.a));

    return { show, hide };
  };
  window.EC_COMPARE = { create };
})();
