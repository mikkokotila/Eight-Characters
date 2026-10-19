// Settings: what the account keeps (docs/Standard-Settings.md): its saved charts, which
// of them is the person's own, the couples they form, where you are, and the schools
// the day follows. What they hold comes from the API (GET /api/account/settings, GET
// /api/schools). Every change names the account by its key and the settings it was
// made from by their `updated_at`, so a change made in another tab is refused (412)
// rather than silently undone.
(() => {
  const SETTINGS = ['favourable', 'season', 'transits'];
  const PILLARS = ['hour', 'day', 'month', 'year'];

  // A request the API refused, with its status and its own words.
  class Refused extends Error {
    constructor(status, message) {
      super(message);
      this.status = status;
    }
  }

  const create = ({ view, translate: t, escape: esc, format, language, account, onOpenChart, onAddBirth, onClose, onChanged, toast }) => {
    if (!window.EC_LIBRARY) throw new Error('Settings need the library.');
    const library = window.EC_LIBRARY;
    const statusLine = view.querySelector('#settings-status');
    const mineBody = view.querySelector('#settings-mine-body');
    const couplesBody = view.querySelector('#settings-couples-body');
    const chartsBody = view.querySelector('#settings-charts-body');
    const placeNow = view.querySelector('#settings-place-now');
    const placeForm = view.querySelector('#settings-place-form');
    const placeInput = view.querySelector('#settings-location');
    const suggestionList = view.querySelector('#settings-location-suggestions');
    const placeStatus = view.querySelector('#settings-location-status');
    const placeSave = view.querySelector('#settings-place-save');
    const placeRemove = view.querySelector('#settings-place-remove');
    const schoolsBody = view.querySelector('#settings-schools-body');
    const toolbarChoice = view.querySelector('#settings-toolbar-choice');
    const closeButton = view.querySelector('#settings-close');
    if (!statusLine || !mineBody || !couplesBody || !chartsBody || !placeNow || !placeForm || !placeInput || !suggestionList || !placeStatus
      || !placeSave || !placeRemove || !schoolsBody || !toolbarChoice || !closeButton) throw new Error('Settings view is incomplete.');
    if (!window.EC_TOOLBAR) throw new Error('Settings need the toolbar.');

    // The settings as the API last gave them, and the schools it lists.
    let settings = null;
    let catalog = null;
    // Reads and changes run one at a time, in the order they were made: a change waits
    // for the ones made before it and is made from the settings they left, so changes in
    // quick succession (arrowing through a school's presets) follow one another.
    let queue = Promise.resolve();
    const inTurn = (task) => {
      const turn = queue.then(task);
      queue = turn.catch(() => {});
      return turn;
    };
    // A change is made from the settings on screen. Once they are replaced by settings
    // this page did not make (changed elsewhere, another account's, a sign-in), the
    // changes still waiting were made from the old ones, and are not made: `basis`
    // counts the replacements, and `replaced` says why the last one happened. A sign-out,
    // or another account taken, starts a new `generation`: a read or a change answered
    // after it is not taken, and `ended` says why.
    let basis = 0;
    let replaced = '';
    let generation = 0;
    let ended = '';
    // The basis of the settings last drawn here: a change from this page's controls is
    // made from them, so settings read meanwhile by Today or the library (a chart saved
    // elsewhere, say) replace them, and the change is not made.
    let drawnBasis = -1;
    // The settings last drawn here, which this page's controls show.
    let drawn = null;
    // Changes still waiting: the page is drawn once the last of them has its answer.
    let waiting = 0;

    const call = async (method, path, body) => {
      const response = await fetch(path, {
        method,
        headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      let value = null;
      try {
        value = await response.json();
      } catch (err) {
        throw new Error(t('settings_answer_error', { status: response.status }), { cause: err });
      }
      if (!response.ok) {
        const detail = value && typeof value.detail === 'string' ? value.detail : t('settings_answer_error', { status: response.status });
        throw new Refused(response.status, detail);
      }
      return value;
    };
    // The answer must be the settings: a malformed one is said, never drawn. Every
    // reference names a saved chart.
    const isId = (value) => typeof value === 'string' && /^[0-9a-f]{32}$/.test(value);
    const checked = (value) => {
      const charts = Array.isArray(value?.charts) ? value.charts : null;
      const ids = new Set(charts?.map((chart) => chart?.id));
      const ok = value && typeof value === 'object' && typeof value.key === 'string'
        && (value.updated_at === null || typeof value.updated_at === 'string')
        && SETTINGS.every((name) => typeof value.schools?.[name] === 'string' && Object.hasOwn(value.chosen ?? {}, name))
        && charts !== null && charts.every((chart) => isId(chart?.id) && typeof chart.date === 'string'
          && typeof chart.time === 'string' && typeof chart.place === 'object' && chart.place !== null
          && (chart.pillars === null ? typeof chart.problem === 'string' : typeof chart.pillars === 'object'))
        && ids.size === charts.length
        && (value.my_chart === null || ids.has(value.my_chart))
        && (value.pending_partner === null || ids.has(value.pending_partner))
        && Array.isArray(value.couples) && value.couples.every((couple) => isId(couple?.id)
          && Array.isArray(couple.charts) && couple.charts.length === 2 && couple.charts.every((id) => ids.has(id))
          && couple.charts[0] !== couple.charts[1])
        // A chart can be in any number of couples (#98), each pair once.
        && new Set(value.couples.map((couple) => [...couple.charts].sort().join(' '))).size === value.couples.length
        // A future unlimited allowance is null; an omitted or malformed limit is not.
        && (value.chart_limit === null || (Number.isInteger(value.chart_limit) && value.chart_limit > 0))
        // How many couples one chart may be in on the account's plan; null for no cap.
        && (value.couples_per_chart === null || (Number.isInteger(value.couples_per_chart) && value.couples_per_chart > 0))
        && (value.place === null || typeof value.place === 'object');
      if (!ok) throw new Error(t('settings_answer_error', { status: 200 }));
      return value;
    };

    // The settings, read from the API. Settings other than those on screen replace the
    // basis of the changes still waiting, for the reason given.
    const read = async (why = t('settings_changed_elsewhere')) => {
      const at = generation;
      const value = checked(await call('GET', '/api/account/settings'));
      if (at !== generation) throw new Error(ended);
      if (settings === null || value.key !== settings.key || value.updated_at !== settings.updated_at) {
        basis += 1;
        replaced = why;
      }
      settings = value;
      return value;
    };
    // The settings, read anew in their turn. A session that ended meanwhile asks for a
    // sign-in first, while `wanted` holds: the page may still hold the account whose
    // session ended, so the server is asked before the sign-in is. The settings are
    // then those of the account signed in.
    const load = (wanted = () => true) => inTurn(async () => {
      try {
        return await read();
      } catch (err) {
        if (!(err instanceof Refused) || err.status !== 401 || !wanted()) throw err;
        if (!(await account.recheck(wanted))) {
          if (!wanted()) throw err;
          await account.signIn();
        }
        return read(t('settings_signed_in_again'));
      }
    });
    const loadCatalog = async () => {
      if (catalog === null) {
        const value = await call('GET', '/api/schools');
        if (!Array.isArray(value?.settings) || value.settings.map((s) => s.id).join() !== SETTINGS.join()) {
          throw new Error(t('settings_answer_error', { status: 200 }));
        }
        catalog = value;
      }
      return catalog;
    };

    const say = (text, isError = false) => {
      statusLine.textContent = text;
      statusLine.classList.toggle('is-error', isError);
      statusLine.classList.toggle('hidden', text === '');
    };

    // Refused for settings it was not made from: the settings are read again and shown,
    // and the changes still waiting, made from the old ones, are not made either.
    const reread = async (why) => {
      basis += 1;
      replaced = why;
      await read(why);
      onChanged(settings);
      return why;
    };
    // A change, made from the settings of basis `from`: null once the API has made it, or
    // why it was not made. Refused because the settings changed elsewhere, because the
    // session ended or because another account is signed in now, the settings are read
    // again and drawn, and the change is not repeated: the reader decides again.
    // `made`, given the settings the change was made from and the ones it left, once
    // the API has made it: in turn, before any later change.
    const write = (method, path, body, from, made = null) => {
      waiting += 1;
      return inTurn(async () => {
        // A sign-out while the change is on its way: its answer is the account's before,
        // and is neither taken nor drawn, and a refusal asks for no sign-in.
        const at = generation;
        try {
          // No settings read and drawn, none shown: nothing is changed from controls left
          // over, nor from a page that could not read them.
          if (settings === null || from < 0) return t('settings_load_error');
          if (from !== basis) return replaced;
          const was = settings;
          const value = checked(await call(method, path, { ...body, key: settings.key, updated_at: settings.updated_at }));
          if (at !== generation) return ended;
          settings = value;
          onChanged(settings);
          made?.(was, value);
          return null;
        } catch (err) {
          if (at !== generation) return ended;
          // A change not made, for whatever reason, stops the changes waiting behind it:
          // they were made from the settings it was to leave.
          basis += 1;
          replaced = err.message || t('settings_load_error');
          if (!(err instanceof Refused)) throw err;
          // Awaited here, so that the drawing below shows the settings read again.
          if (err.status === 412) return await reread(t('settings_changed_elsewhere'));
          if (err.status === 401) {
            // Signed out elsewhere: the server is asked first, since the page may still
            // hold the account; then a sign-in, and the settings of the account signed in.
            replaced = t('account_session_ended');
            if (!(await account.recheck(() => true))) await account.signIn();
            return await reread(t('settings_signed_in_again'));
          }
          if (err.status === 409) {
            // Another account is signed in in this browser now: its settings are shown.
            await account.stillSignedIn(() => true);
            await reread(err.message);
          }
          return err.message;
        } finally {
          waiting -= 1;
          if (waiting === 0 && at === generation) draw();
        }
      });
    };
    // A change from this page: done, it is said briefly (`done`, or what it says of the
    // settings it left and the ones it was made from, which changes made before it may
    // have changed since it was asked for); refused, its reason stays here.
    const change = async (method, path, body, done) => {
      let problem;
      let said = typeof done === 'function' ? null : done;
      try {
        problem = await write(method, path, body, drawnBasis, (was, now) => {
          if (typeof done === 'function') said = done(now, was);
        });
      } catch (err) {
        console.error(err);
        problem = err.message || t('settings_load_error');
      }
      if (problem === null) {
        say('');
        toast(said, false);
        return true;
      }
      say(problem, true);
      return false;
    };

    // ── Your chart, your couples and your saved charts ──
    const birthHeading = (birth) => {
      const reading = format.parseWallClock(`${birth.date}T${birth.time}`);
      if (!reading) throw new Error(t('settings_answer_error', { status: 200 }));
      return [format.date(reading), format.time(reading, birth.time.length > 5), birth.place.city].join(' · ');
    };
    const chartName = (chart) => chart.name ?? t('library_unnamed');
    // A chart's partners as one list, in the order formed, past three "and N more"; an
    // unnamed one by its birth date.
    const listName = (chart) => chart.name ?? t('library_unnamed_born', {
      date: format.date(format.parseWallClock(`${chart.date}T${chart.time}`)),
    });
    const names = (charts) => library.partnerList(charts, {
      lang: language(), nameOf: listName, more: (count) => t('names_more', { count }),
    });
    // A saved chart as a card: its name, its marks, its birth and its pillars.
    const card = (kept, chart, actions) => {
      const partners = library.partnersOf(kept, chart.id);
      const marks = [
        chart.id === kept.my_chart ? `<span class="saved-mark is-mine">${esc(t('library_mine'))}</span>` : '',
        partners.length === 0 ? '' : `<span class="saved-mark">${esc(t('library_with', { names: names(partners) }))}</span>`,
        chart.id === kept.pending_partner ? `<span class="saved-mark">${esc(t('settings_waiting'))}</span>` : '',
      ].join('');
      return `<li class="saved-card" data-chart="${esc(chart.id)}">
          <p class="saved-head"><span class="saved-name">${esc(chartName(chart))}</span>${marks}</p>
          <p class="saved-birth">${esc(birthHeading(chart))}</p>
          ${library.strip(chart, { escape: esc, translate: t })}
          <div class="settings-actions">${actions}</div>
        </li>`;
    };
    const action = (name, chart, label, extra = '') => `<button type="button" class="bar-action" data-settings-action="${name}"
        ${chart === null ? '' : `data-chart="${esc(chart.id)}"`} ${extra}>${esc(label)}</button>`;
    const options = (charts, chosen = null) => charts.map((chart) => `<option value="${esc(chart.id)}"${chart.id === chosen ? ' selected' : ''}>${esc(
      `${chartName(chart)} · ${birthHeading(chart)}`,
    )}</option>`).join('');

    const drawMine = () => {
      const mine = settings.my_chart === null ? null : library.chartWith(settings, settings.my_chart);
      const others = settings.charts.filter((chart) => chart.id !== settings.my_chart);
      const choose = others.length === 0 ? '' : `
        <div class="settings-choose">
          <span class="settings-pick"><label for="settings-mine-choice">${esc(t(mine === null ? 'settings_mine_choose' : 'settings_mine_change'))}</label>
          <select id="settings-mine-choice">${options(others)}</select></span>
          ${action('mark', null, t('settings_mine_mark'))}
        </div>`;
      mineBody.innerHTML = `${mine === null
        ? `<p class="settings-note">${esc(t('settings_mine_none'))}</p>`
        : `<ul class="saved-cards">${card(settings, mine, `${action('open', mine, t('settings_chart_open'))}${action('unmark', mine, t('settings_mine_clear'))}`)}</ul>`}
        ${choose}
        <div class="settings-actions">${action('add-mine', null, t('settings_new_birth'))}</div>`;
    };

    // A chart can take one more couple: any chart, as many as the account's plan allows
    // (couples_per_chart, null for no cap).
    const underCap = (kept, chart) => kept.couples_per_chart === null
      || library.couplesOf(kept, chart.id).length < kept.couples_per_chart;
    // The charts a chart can pair with now: under the cap, neither itself nor one of its
    // partners.
    const pairable = (kept, chart) => kept.charts.filter((other) => other.id !== chart.id
      && underCap(kept, other) && library.coupleBetween(kept, chart.id, other.id) === null);
    // The second list follows the first: the charts the first can pair with.
    const drawPairSecond = () => {
      const first = view.querySelector('#settings-pair-first');
      const second = view.querySelector('#settings-pair-second');
      if (!first || !second) return;
      const chart = library.chartWith(settings, first.value);
      const choices = chart === null ? [] : pairable(settings, chart);
      second.innerHTML = options(choices, choices[0]?.id ?? null);
    };
    const drawCouples = () => {
      // Pair offers each chart that can take one more couple and is not yet paired with
      // every chart it could be; a new birth can be the partner of any chart under the
      // cap, even one paired with every other.
      const firsts = settings.charts.filter((chart) => underCap(settings, chart) && pairable(settings, chart).length > 0);
      const open = settings.charts.filter((chart) => underCap(settings, chart));
      const couples = settings.couples.map((couple) => {
        const [first, second] = couple.charts.map((id) => library.chartWith(settings, id));
        return `<li class="couple-card" data-couple="${esc(couple.id)}">
            <p class="couple-names"><span class="saved-name">${esc(chartName(first))}</span>
              <span class="couple-and" aria-hidden="true">＆</span><span class="sr-only">${esc(t('couple_and'))}</span>
              <span class="saved-name">${esc(chartName(second))}</span></p>
            <div class="couple-strips">${library.strip(first, { escape: esc, translate: t })}${library.strip(second, { escape: esc, translate: t })}</div>
            <div class="settings-actions">
              <button type="button" class="bar-action" data-settings-action="end" data-couple="${esc(couple.id)}">${esc(t('settings_couple_end'))}</button>
            </div>
          </li>`;
      }).join('');
      const pending = settings.pending_partner === null ? null : library.chartWith(settings, settings.pending_partner);
      // Each list starts at my chart, else at its first chart.
      const first = firsts.find((chart) => chart.id === settings.my_chart) ?? firsts[0] ?? null;
      const partnerOf = open.find((chart) => chart.id === settings.my_chart) ?? open[0] ?? null;
      // Under a plan's cap, a chart in as many couples as it allows is not offered: the
      // page says why.
      const capped = settings.couples_per_chart !== null && open.length < settings.charts.length;
      const cap = () => (settings.couples_per_chart === 1 ? t('settings_couple_cap_one')
        : t('settings_couple_cap', { count: settings.couples_per_chart }));
      couplesBody.innerHTML = `
        ${couples === '' ? `<p class="settings-note">${esc(t('settings_couples_none'))}</p>` : `<ul class="couple-cards">${couples}</ul>`}
        ${pending === null ? '' : `<p class="settings-note">${esc(t('settings_pending', { name: chartName(pending) }))}</p>`}
        ${capped ? `<p class="settings-note">${esc(cap())}</p>` : ''}
        ${first !== null ? `
          <div class="settings-choose settings-pair">
            <span class="settings-pick"><label for="settings-pair-first">${esc(t('settings_pair_first'))}</label>
            <select id="settings-pair-first">${options(firsts, first.id)}</select></span>
            <span class="settings-pick"><label for="settings-pair-second">${esc(t('settings_pair_second'))}</label>
            <select id="settings-pair-second"></select></span>
            ${action('pair', null, t('settings_pair'))}
          </div>` : settings.charts.length < 2 ? '' : `<p class="settings-note">${esc(t('settings_pair_none'))}</p>`}
        ${partnerOf === null ? '' : `
          <div class="settings-choose">
            <span class="settings-pick"><label for="settings-partner-of">${esc(t('settings_partner_of'))}</label>
            <select id="settings-partner-of">${options(open, partnerOf.id)}</select></span>
            ${action('add-partner', null, t('settings_partner_new_birth'))}
          </div>`}`;
      drawPairSecond();
    };

    // A rename is asked for in place, on the chart's card.
    let renaming = null;
    const drawCharts = () => {
      chartsBody.innerHTML = settings.charts.length === 0
        ? `<p class="settings-note">${esc(t('settings_charts_none'))}</p>`
        : `<ul class="saved-cards">${settings.charts.map((chart) => card(settings, chart, renaming === chart.id
          ? `<form class="settings-rename" data-chart="${esc(chart.id)}" novalidate>
              <label for="settings-rename-${esc(chart.id)}">${esc(t('settings_rename_label'))}</label>
              <input type="text" id="settings-rename-${esc(chart.id)}" maxlength="80" autocomplete="off" spellcheck="false">
              <button type="submit" class="bar-action" data-settings-action="rename-save" data-chart="${esc(chart.id)}">${esc(t('settings_rename_save'))}</button>
              <button type="button" class="bar-action" data-settings-action="rename-cancel" data-chart="${esc(chart.id)}">${esc(t('cancel'))}</button>
            </form>`
          : `${chart.pillars === null ? '' : action('open', chart, t('settings_chart_open'))}${action('rename', chart, t('settings_chart_rename'))}${action('correct', chart, t('settings_chart_correct'))}${action('remove', chart, t('settings_chart_remove'))}`)).join('')}</ul>`;
      // The name being changed goes in as the field's value, never into the markup: a
      // name is text, quotes and all.
      if (renaming !== null) {
        const field = chartsBody.querySelector(`#settings-rename-${CSS.escape(renaming)}`);
        const chart = library.chartWith(settings, renaming);
        if (field && chart) field.value = chart.name ?? '';
      }
      chartsBody.insertAdjacentHTML('beforeend', `<p class="settings-note">${esc(t('settings_consent'))}</p>`);
    };

    // What a change from these parts asks the API, made from the settings drawn here.
    const chosenIn = (selector) => view.querySelector(selector)?.value ?? null;
    // A full library takes no new birth: said here, in the page's language.
    const full = () => {
      if (drawn.chart_limit === null || drawn.charts.length < drawn.chart_limit) return false;
      say(t('library_full', { limit: drawn.chart_limit }), true);
      return true;
    };
    // A change asked for again, with nothing asked for since, while it is on its way is
    // not asked for twice: a second press on Pair, say, adds nothing to the first. Asked
    // for again after another change (Mark, Unmark, Mark), it is asked for in its turn.
    let latest = null;
    const once = async (what, run) => {
      if (latest !== null && latest.what === what) return;
      const mine = { what };
      latest = mine;
      try {
        await run();
      } finally {
        if (latest === mine) latest = null;
      }
    };
    // Removing a chart says first what else it ends: being your chart, each of its
    // couples, or its wait to pair with your chart.
    const removing = (chart) => {
      const name = chartName(chart);
      const partners = library.partnersOf(drawn, chart.id);
      const ends = partners.length === 0 ? null
        : partners.length === 1 ? { key: 'couple', vars: { partner: chartName(partners[0]) } }
          : { key: 'couples', vars: { partners: names(partners) } };
      if (chart.id === drawn.my_chart) {
        return ends === null
          ? t('settings_chart_remove_confirm_mine', { name })
          : t(`settings_chart_remove_confirm_mine_${ends.key}`, { name, ...ends.vars });
      }
      if (ends !== null) return t(`settings_chart_remove_confirm_${ends.key}`, { name, ...ends.vars });
      if (chart.id === drawn.pending_partner) return t('settings_chart_remove_confirm_pending', { name });
      return t('settings_chart_remove_confirm', { name });
    };
    const onLibrary = async (event) => {
      const button = event.target.closest('[data-settings-action]');
      if (!button || drawn === null) return;
      const id = button.dataset.chart ?? null;
      const chart = id === null ? null : library.chartWith(drawn, id);
      switch (button.dataset.settingsAction) {
        case 'open':
          if (chart !== null) onOpenChart(library.chartParams(chart, language()));
          break;
        case 'mark': {
          const chosen = chosenIn('#settings-mine-choice');
          if (chosen === null) break;
          // A partner kept from before charts pairs with the chart marked: said, by name.
          // When the chart is at its plan's cap the partner does not, waits no longer, and
          // the page says why. Both are read from the settings the mark was made from,
          // not those drawn when it was asked for: changes before it may have paired the
          // partner already.
          const marked = (now, was) => {
            const partner = library.pairedSince(was, now, chosen);
            if (partner !== null) return t('settings_mine_marked_paired', { name: chartName(partner) });
            const waiting = was.pending_partner === null || was.pending_partner === chosen ? null : library.chartWith(now, was.pending_partner);
            const atCap = now.couples_per_chart !== null && library.couplesOf(now, chosen).length >= now.couples_per_chart;
            return waiting !== null && atCap && now.pending_partner === null
              ? t('settings_mine_marked_unpaired', { name: chartName(waiting) })
              : t('settings_mine_marked');
          };
          await once(`mark ${chosen}`, () => change('PUT', '/api/account/my-chart', { chart: chosen }, marked));
          break;
        }
        case 'unmark':
          await once('unmark', () => change('DELETE', '/api/account/my-chart', {}, t('settings_mine_cleared')));
          break;
        case 'add-mine':
          if (full()) break;
          onAddBirth({ as: 'mine' });
          break;
        case 'pair': {
          const first = chosenIn('#settings-pair-first');
          const second = chosenIn('#settings-pair-second');
          if (first === null || second === null) break;
          if (first === second) {
            say(t('settings_pair_same'), true);
            break;
          }
          if (library.coupleBetween(drawn, first, second) !== null) {
            say(t('settings_pair_twice'), true);
            break;
          }
          // A couple is the same whichever chart is chosen first.
          await once(`pair ${[first, second].sort().join(' ')}`, () => change('POST', '/api/account/couples', { charts: [first, second] }, t('settings_paired')));
          break;
        }
        case 'add-partner': {
          const of = chosenIn('#settings-partner-of');
          if (of !== null && !full()) onAddBirth({ as: 'partner', with: of });
          break;
        }
        case 'end': {
          const couple = button.dataset.couple;
          await once(`end ${couple}`, () => change('DELETE', `/api/account/couples/${encodeURIComponent(couple)}`, {}, t('settings_couple_ended')));
          break;
        }
        case 'rename':
          renaming = id;
          draw();
          view.querySelector(`#settings-rename-${CSS.escape(id)}`)?.focus();
          break;
        case 'rename-cancel':
          renaming = null;
          draw();
          view.querySelector(`[data-settings-action="rename"][data-chart="${CSS.escape(id)}"]`)?.focus();
          break;
        case 'correct':
          if (chart !== null) onAddBirth({ as: 'correct', chart: chart.id });
          break;
        case 'remove':
          if (chart === null) break;
          // Asked once more on the button itself: a second press removes.
          if (button.dataset.confirming !== 'true') {
            button.dataset.confirming = 'true';
            button.textContent = removing(chart);
            break;
          }
          await once(`remove ${chart.id}`, () => change('DELETE', `/api/account/charts/${encodeURIComponent(chart.id)}`, {}, t('settings_chart_removed')));
          break;
        default:
          break;
      }
    };
    [mineBody, couplesBody, chartsBody].forEach((part) => part.addEventListener('click', (event) => {
      if (event.target.closest('button[type="submit"]')) return;
      onLibrary(event).catch((err) => {
        console.error(err);
        say(err.message || t('settings_load_error'), true);
      });
    }));
    couplesBody.addEventListener('change', (event) => {
      if (event.target.id === 'settings-pair-first') drawPairSecond();
    });
    chartsBody.addEventListener('submit', async (event) => {
      event.preventDefault();
      const formNode = event.target.closest('.settings-rename');
      if (!formNode) return;
      const id = formNode.dataset.chart;
      const name = formNode.querySelector('input').value.trim();
      // A name is one line of printable text, up to 80 characters, or none.
      if (name.length > 80 || /\p{Cc}/u.test(name)) {
        say(t('save_chart_name_error'), true);
        return;
      }
      if (await change('PUT', `/api/account/charts/${encodeURIComponent(id)}/name`, { name: name === '' ? null : name }, t('settings_chart_renamed'))) {
        renaming = null;
        draw();
        view.querySelector(`[data-settings-action="rename"][data-chart="${CSS.escape(id)}"]`)?.focus();
      }
    });

    // ── Where you are: the place search, as the form's, here on its own ──
    let picked = null;
    const search = window.EC_PLACE_SEARCH.create({
      input: placeInput, list: suggestionList, status: placeStatus, optionId: 'settings-location-option',
      translate: t, escape: esc, format,
      onType: () => {
        picked = null;
        placeSave.disabled = true;
      },
      onPick: (place) => {
        picked = place;
        placeSave.disabled = false;
      },
    });
    const drawPlace = () => {
      const place = settings.place;
      placeNow.textContent = place === null
        ? t('settings_place_none')
        : t('settings_place_now', { place: place.name, where: search.coordinates(place) });
      placeRemove.classList.toggle('hidden', place === null);
    };
    placeForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (picked === null) return;
      const saving = picked;
      const place = {
        name: saving.display,
        city: saving.city,
        timezone: saving.timezone,
        latitude: saving.latitude,
        longitude: saving.longitude,
      };
      // Saved, the search is cleared, unless another place was picked or typed meanwhile;
      // Save, then unavailable, hands its focus to the search.
      if (await change('PUT', '/api/account/place', { place }, t('settings_place_saved')) && picked === saving) {
        const focused = document.activeElement === placeSave;
        picked = null;
        placeInput.value = '';
        placeSave.disabled = true;
        search.setStatus('');
        if (focused) placeInput.focus();
      }
    });
    placeRemove.addEventListener('click', async () => {
      await change('DELETE', '/api/account/place', {}, t('settings_place_removed'));
    });

    // ── The schools: each setting's presets, the default marked in words ──
    const text = (pair) => pair[language()];
    const drawSchools = () => {
      schoolsBody.innerHTML = catalog.settings.map((setting) => {
        const chosen = settings.schools[setting.id];
        return `
          <fieldset class="settings-school" data-setting="${esc(setting.id)}">
            <legend class="settings-school-name">${esc(text(setting.name))}</legend>
            <p class="settings-note">${esc(text(setting.question))}</p>
            ${setting.presets.map((preset) => {
              const id = `settings-${setting.id}-${preset.id}`;
              const han = preset.han === null ? '' : ` <span class="settings-han"><span lang="zh-Hant">${esc(preset.han.chinese)}</span> ${esc(preset.han.pinyin)}</span>`;
              return `
                <div class="settings-preset">
                  <input type="radio" id="${id}" name="settings-${esc(setting.id)}" value="${esc(preset.id)}"${preset.id === chosen ? ' checked' : ''}
                    data-default="${preset.default}" aria-describedby="${id}-summary">
                  <label for="${id}"><span class="settings-preset-name">${esc(text(preset.name))}</span>${han}${preset.default ? ` <span class="settings-default">${esc(t('settings_school_default'))}</span>` : ''}</label>
                  <p class="settings-summary" id="${id}-summary">${esc(text(preset.summary))}</p>
                  <p class="settings-sources">${esc(t('settings_sources', { sources: preset.sources.join('; ') }))}</p>
                </div>`;
            }).join('')}
          </fieldset>`;
      }).join('') + (language() === 'fi' && catalog.finnish_provisional ? `<p class="settings-note">${esc(t('settings_finnish_provisional'))}</p>` : '');
    };
    // ── The toolbar: this browser's own, taken at once (toolbar.js) ──
    const drawToolbar = () => {
      toolbarChoice.querySelectorAll('input[name="settings-toolbar"]').forEach((radio) => {
        radio.checked = radio.value === window.EC_TOOLBAR.way();
      });
    };
    toolbarChoice.addEventListener('change', (event) => {
      const radio = event.target.closest('input[name="settings-toolbar"]');
      if (radio?.checked) window.EC_TOOLBAR.choose(radio.value);
    });
    // Chosen in another tab meanwhile: the choice shown follows, so either can be chosen.
    window.EC_TOOLBAR.watch(drawToolbar);
    schoolsBody.addEventListener('change', async (event) => {
      const radio = event.target.closest('input[type="radio"]');
      if (!radio) return;
      const setting = radio.closest('[data-setting]').dataset.setting;
      // The default is followed, not chosen, so a later change of default applies too.
      const choice = radio.dataset.default === 'true' ? null : radio.value;
      await change('PATCH', '/api/account/schools', { [setting]: choice }, t('settings_school_saved'));
    });

    // Drawing replaces the controls: the one that had focus hands it to its counterpart
    // (the same preset or action), or, gone, to the first control of its part, so the
    // keyboard stays where it was. A control hidden or disabled has lost focus too.
    const focusable = (node) => node.isConnected && !node.closest('.hidden') && !node.disabled;
    const draw = () => {
      if (settings === null) return;
      const focused = view.contains(document.activeElement) ? document.activeElement : null;
      const part = focused?.closest('#settings-mine-body, #settings-couples-body, #settings-charts-body, #settings-schools-body') ?? null;
      let counterpart = null;
      if (focused?.id) counterpart = `#${CSS.escape(focused.id)}`;
      else if (focused?.dataset.settingsAction) {
        counterpart = `[data-settings-action="${CSS.escape(focused.dataset.settingsAction)}"]`
          + (focused.dataset.chart ? `[data-chart="${CSS.escape(focused.dataset.chart)}"]` : '')
          + (focused.dataset.couple ? `[data-couple="${CSS.escape(focused.dataset.couple)}"]` : '');
      }
      // A chart renamed or removed elsewhere ends its rename here.
      if (renaming !== null && library.chartWith(settings, renaming) === null) renaming = null;
      drawMine();
      drawCouples();
      drawCharts();
      drawPlace();
      if (catalog !== null) drawSchools();
      drawn = settings;
      drawnBasis = basis;
      if (focused === null || focusable(focused)) return;
      const found = counterpart === null ? null : view.querySelector(counterpart);
      const next = found !== null && focusable(found) ? found : [...(part?.querySelectorAll('button, input, select') ?? [])].find(focusable);
      // The place's Remove, gone with the place, hands focus to the place's search.
      (next ?? placeInput).focus();
    };

    // Shows the settings, read anew: whatever another tab changed meanwhile is shown,
    // and `note` says why they are shown again, if they are. Each showing is numbered:
    // only the latest draws or says anything, so one that ends late changes nothing of a
    // later one, its failure included.
    let showing = 0;
    const show = async (note = '') => {
      const mine = ++showing;
      say('');
      drawToolbar();
      view.classList.remove('hidden');
      view.setAttribute('aria-busy', 'true');
      try {
        await Promise.all([load(() => mine === showing), loadCatalog()]);
        if (mine !== showing) return;
        draw();
        say(note);
      } catch (err) {
        if (mine !== showing) return;
        console.error(err);
        say(err.message || t('settings_load_error'), true);
      } finally {
        if (mine === showing) view.removeAttribute('aria-busy');
      }
    };
    const hide = () => {
      showing += 1;
      view.classList.add('hidden');
      view.removeAttribute('aria-busy');
      search.close();
    };
    closeButton.addEventListener('click', () => onClose());

    // Keeps a birth in the library, as the library's Save and the form's save mode ask
    // (app.js): null once kept, or why not. `mine` and `couple_with` mark it as the
    // person's own, or pair it, in the same write. Each change is made from the settings
    // its dialog or form read, by the basis they had then (basis()).
    const saveChart = async (birth, { mine = false, coupleWith = null } = {}, from) => write(
      'POST', '/api/account/charts', { ...birth, mine, ...(coupleWith === null ? {} : { couple_with: coupleWith }) }, from,
    );
    // Corrects a saved chart's birth: it keeps its id, its mark and its couple.
    const correctChart = async (id, birth, from) => write('PUT', `/api/account/charts/${encodeURIComponent(id)}`, birth, from);
    // Sets where you are, as Today asks for it when none is set (today.js), from the
    // settings it read: null once set, or why not.
    const setPlace = async (place, from) => write('PUT', '/api/account/place', { place }, from);

    return {
      show,
      hide,
      load,
      current: () => settings,
      basis: () => basis,
      saveChart,
      correctChart,
      setPlace,
      chartName,
      // A sign-out, or another account taken (`why` says which), forgets what was read for
      // the account and leaves nothing of it on the page, and the changes still waiting
      // are not made.
      forget: (why = t('account_session_ended')) => {
        settings = null;
        drawn = null;
        generation += 1;
        basis += 1;
        replaced = why;
        ended = why;
        latest = null;
        renaming = null;
        mineBody.innerHTML = '';
        couplesBody.innerHTML = '';
        chartsBody.innerHTML = '';
        placeNow.textContent = '';
        placeRemove.classList.add('hidden');
        schoolsBody.innerHTML = '';
        search.reset();
        picked = null;
        placeSave.disabled = true;
        say('');
      },
      // The page's language changed: the schools are written in it.
      redraw: () => {
        if (!view.classList.contains('hidden')) draw();
      },
    };
  };
  window.EC_SETTINGS = { create, Refused };
})();
