// The library: the charts the account keeps (docs/Standard-Settings.md). A chart link
// holds a birth, never an id, so the chart on screen is the saved chart drawn from the
// same birth: the API saves each birth once (records.Birth.chart_key). This module
// matches births to saved charts, draws a saved chart for Settings and for the
// classic view, and runs the classic view's library, opened from the chart's heading.
(() => {
  // The chart's own order, hour to year, as every view of a chart reads.
  const PILLARS = ['hour', 'day', 'month', 'year'];

  // A birth's chart, as the API tells births apart: the day, the time to the second,
  // the pass, the place on the globe and its zone, the gender and the Zi-hour
  // convention. Names and place labels are no part of it.
  const keyOf = (birth) => JSON.stringify([
    birth.date,
    birth.time.length === 5 ? `${birth.time}:00` : birth.time,
    birth.fold ?? null,
    birth.place.timezone,
    birth.place.latitude,
    birth.place.longitude,
    birth.gender ?? null,
    birth.zi,
  ]);
  // The saved chart drawn from a birth, or null.
  const savedOf = (kept, birth) => kept.charts.find((chart) => keyOf(chart) === keyOf(birth)) ?? null;
  const chartWith = (kept, id) => kept.charts.find((chart) => chart.id === id) ?? null;
  // The couples a saved chart is in, in the order they were formed: any number of
  // them (#98).
  const couplesOf = (kept, id) => kept.couples.filter((couple) => couple.charts.includes(id));
  // The other chart of each of a saved chart's couples, in the order they were formed.
  const partnersOf = (kept, id) => couplesOf(kept, id).map((couple) => chartWith(kept, couple.charts.find((other) => other !== id)));
  // The couple two saved charts form, in either order, or null.
  const coupleBetween = (kept, first, second) => kept.couples
    .find((couple) => couple.charts.includes(first) && couple.charts.includes(second)) ?? null;
  // Names as one list in the page's language: "A, B and C".
  const listOf = (names, lang) => new Intl.ListFormat(lang, { style: 'long', type: 'conjunction' }).format(names);
  // A chart's partners as one list, in the order their couples were formed: "A, B and
  // C", and past three "A, B, C and N more" (#98). `nameOf` names an unnamed partner by
  // its birth date, so two can be told apart.
  const partnerList = (partners, { lang, nameOf, more }) => {
    const names = partners.map(nameOf);
    return listOf(names.length > 3 ? [...names.slice(0, 3), more(names.length - 3)] : names, lang);
  };
  // The chart a write paired with chart `id`, by the settings before it and after: a
  // partner kept from before charts pairs with the chart marked as yours. Null when the
  // write formed no couple for it.
  const pairedSince = (before, after, id) => {
    const formed = after.couples.find((couple) => couple.charts.includes(id) && !before.couples.some((old) => old.id === couple.id));
    return formed === undefined ? null : chartWith(after, formed.charts.find((other) => other !== id));
  };
  // A saved chart's own link, as the chart's bar writes one.
  const chartParams = (birth, lang) => {
    const params = new URLSearchParams({
      date: birth.date,
      time: birth.time,
      place: birth.place.name,
      city: birth.place.city,
      latitude: String(birth.place.latitude),
      longitude: String(birth.place.longitude),
      timezone: birth.place.timezone,
      lang,
    });
    params.set('gender', birth.gender);
    if (birth.zi !== 'split_midnight') params.set('zi', birth.zi);
    // A time the place's clocks repeat names its pass, as the saved birth does.
    if (birth.fold !== null) params.set('fold', String(birth.fold));
    return params.toString();
  };

  // A saved chart's four pillars, hour first, as the chart lays them out: each a stem
  // over its branch in their elements' colours, with their pinyin, as the classic view
  // draws them. A chart the engine no longer charts says why instead.
  const strip = (chart, { escape: esc, translate: t }) => {
    if (chart.pillars === null) {
      return `<p class="saved-problem">${esc(t('saved_problem', { problem: chart.problem }))}</p>`;
    }
    const tile = (part, glyph) => `<span class="saved-glyph ${part} ${esc(glyph.element)}">
        <span class="saved-char glyph" lang="zh-Hant">${esc(glyph.chinese)}</span>
        <span class="saved-pinyin card-pinyin">${esc(glyph.pinyin)}</span>
      </span>`;
    return `<ol class="saved-strip">${PILLARS.map((name) => {
      const { stem, branch } = chart.pillars[name];
      return `<li class="saved-pillar"><span class="sr-only">${esc(t('pillar_' + name))}</span>${tile('stem', stem)}${tile('branch', branch)}</li>`;
    }).join('')}</ol>`;
  };

  // A saved chart as every list of them shows it (the library, the start page): its
  // name, its marks (your chart; its partners, unless `withPartners` is false, as on the
  // saved charts' page, which lists each couple under the chart; waiting to pair with
  // your chart when `waiting`; on screen when `here`), its birth and its pillars.
  // `tools` are the page's: translate, escape, format and language.
  const row = (kept, chart, {
    here = false, waiting = false, withPartners = true, translate: t, escape: esc, format, language,
  }) => {
    const reading = format.parseWallClock(`${chart.date}T${chart.time}`);
    if (!reading) throw new Error(t('settings_answer_error', { status: 200 }));
    const birthLine = [format.date(reading), format.time(reading, chart.time.length > 5), chart.place.city].join(' · ');
    // A partner named in a list: an unnamed one by its birth date.
    const listName = (partner) => partner.name ?? t('library_unnamed_born', {
      date: format.date(format.parseWallClock(`${partner.date}T${partner.time}`)),
    });
    const partners = partnersOf(kept, chart.id);
    const marks = [
      chart.id === kept.my_chart ? `<span class="saved-mark is-mine">${esc(t('library_mine'))}</span>` : '',
      !withPartners || partners.length === 0 ? '' : `<span class="saved-mark">${esc(t('library_with', {
        names: partnerList(partners, { lang: language(), nameOf: listName, more: (count) => t('names_more', { count }) }),
      }))}</span>`,
      waiting ? `<span class="saved-mark">${esc(t('settings_waiting'))}</span>` : '',
      here ? `<span class="saved-mark is-here">${esc(t('library_here'))}</span>` : '',
    ].join('');
    return `<span class="saved-head"><span class="saved-name">${esc(chart.name ?? t('library_unnamed'))}</span>${marks}</span>
                <span class="saved-birth">${esc(birthLine)}</span>
                ${strip(chart, { escape: esc, translate: t })}`;
  };

  // The classic view's library: the saved charts, the one on screen marked, each opening
  // its chart; "Save the chart on screen" while it is unsaved; and Manage, their page. It opens
  // from the heading of each page that shows a chart (`pages`: the chart's, the day's),
  // each button naming the chart on that page; a chart chosen opens on the page the
  // library was opened from, so the day's library opens the chosen chart's day.
  const create = ({ dialog, pages, translate: t, escape: esc, format, settings, language, onOpen, onSave, onManage }) => {
    const need = (selector) => {
      const node = dialog.querySelector(selector);
      if (!node) throw new Error(`The library is incomplete: ${selector}.`);
      return node;
    };
    const list = need('#library-list');
    const status = need('#library-status');
    const saveButton = need('#library-save');
    const manageButton = need('#library-manage');
    const closeButton = need('#library-close');
    if (!Array.isArray(pages) || pages.length === 0) throw new Error('The library opens from no page.');
    const triggers = pages.map(({ page, button, screenBirth, canSave }) => {
      const label = button.querySelector('.library-label');
      if (!label) throw new Error('The library button is incomplete.');
      return { page, button, label, screenBirth, canSave };
    });
    const pageOf = (name) => {
      const found = triggers.find((trigger) => trigger.page === name);
      if (!found) throw new Error(`The library opens from no ${name} page.`);
      return found;
    };
    // The page the library was last opened from.
    let from = triggers[0];

    const nameOf = (chart) => chart.name ?? t('library_unnamed');
    // The saved chart on a page's screen, by the settings last read: null when the chart
    // is not saved, undefined while no settings have been read or no chart is shown.
    const onScreen = (name = triggers[0].page) => {
      const kept = settings.current();
      const birth = pageOf(name).screenBirth();
      if (kept === null || birth === null) return undefined;
      return savedOf(kept, birth);
    };
    // Each button names its page's chart: its saved name, or that it is not saved.
    const sayName = () => triggers.forEach(({ page, button, label }) => {
      const saved = onScreen(page);
      const text = saved === undefined ? t('library_open') : saved === null ? t('library_unsaved') : nameOf(saved);
      // Rewritten only when it changes: WebKit drops a click whose label is replaced
      // between the press and the release.
      if (label.textContent !== text) label.textContent = text;
      const state = saved === undefined ? 'unknown' : String(saved !== null);
      if (button.dataset.saved !== state) button.dataset.saved = state;
    });

    const draw = (kept) => {
      const saved = savedOf(kept, from.screenBirth());
      list.innerHTML = kept.charts.length === 0
        ? `<li class="library-empty">${esc(t('library_empty'))}</li>`
        : kept.charts.map((chart) => {
          const here = chart.id === saved?.id;
          return `<li>
              <button type="button" class="library-chart${here ? ' is-here' : ''}" data-library-chart="${esc(chart.id)}"
                ${here ? 'aria-current="true"' : ''}>
                ${row(kept, chart, { here, translate: t, escape: esc, format, language })}
              </button>
            </li>`;
        }).join('');
      // A page that cannot save its chart (the day's) offers no save.
      saveButton.classList.toggle('hidden', saved !== null || !from.canSave);
    };

    const say = (text, isError = false) => {
      status.textContent = text;
      status.classList.toggle('is-error', isError);
      status.classList.toggle('hidden', text === '');
    };

    // Opens with the settings read anew, so the list is the account's as it is now: from
    // the page named (the chart's when none is), while it shows a chart.
    let opening = 0;
    const open = async (name = triggers[0].page) => {
      const trigger = pageOf(name);
      if (dialog.open || trigger.screenBirth() === null) return;
      from = trigger;
      const mine = ++opening;
      say('');
      list.innerHTML = '';
      saveButton.classList.add('hidden');
      dialog.setAttribute('aria-busy', 'true');
      dialog.showModal();
      try {
        const kept = await settings.load(() => mine === opening && dialog.open);
        if (mine !== opening || !dialog.open) return;
        draw(kept);
        sayName();
        (list.querySelector('[aria-current="true"]') ?? list.querySelector('button') ?? (saveButton.classList.contains('hidden') ? manageButton : saveButton)).focus();
      } catch (err) {
        if (mine !== opening || !dialog.open) return;
        console.error(err);
        say(err.message || t('settings_load_error'), true);
      } finally {
        if (mine === opening) dialog.removeAttribute('aria-busy');
      }
    };
    dialog.addEventListener('close', () => {
      opening += 1;
      dialog.removeAttribute('aria-busy');
      from.button.focus();
    });
    triggers.forEach(({ page, button }) => button.addEventListener('click', () => open(page)));
    closeButton.addEventListener('click', () => dialog.close());
    list.addEventListener('click', (event) => {
      const chosen = event.target.closest('[data-library-chart]');
      if (!chosen) return;
      const kept = settings.current();
      const chart = kept === null ? null : chartWith(kept, chosen.dataset.libraryChart);
      if (chart === null) return;
      const page = from.page;
      dialog.close();
      onOpen(chartParams(chart, language()), page);
    });
    saveButton.addEventListener('click', () => {
      dialog.close();
      onSave();
    });
    manageButton.addEventListener('click', () => {
      dialog.close();
      onManage();
    });

    return {
      open,
      sayName,
      onScreen,
      // A sign-out leaves nothing of the account's library on the page.
      forget: () => {
        if (dialog.open) dialog.close();
        list.innerHTML = '';
        say('');
        sayName();
      },
    };
  };

  window.EC_LIBRARY = { create, keyOf, savedOf, chartWith, couplesOf, partnersOf, coupleBetween, listOf, partnerList, pairedSince, chartParams, strip, row };
})();
