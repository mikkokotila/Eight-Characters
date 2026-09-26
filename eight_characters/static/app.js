// ═══════════════════════════════════════════════════════
// Eight Characters — Client-side logic
// ═══════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  const i18n = window.EC_I18N;
  if (!i18n) {
    return;
  }
  const inputView = document.getElementById('input-view');
  const chartView = document.getElementById('chart-view');
  const form = document.getElementById('chart-form');
  const backBtn = document.getElementById('back-btn');
  const createChartBtn = document.getElementById('create-chart-btn');
  const dateInput = document.getElementById('date');
  const dateStatus = document.getElementById('date-status');
  const timeInput = document.getElementById('time');
  const timeStatus = document.getElementById('time-status');
  const locationInput = document.getElementById('location');
  const locationSuggestions = document.getElementById('location-suggestions');
  const locationStatus = document.getElementById('location-status');
  const formError = document.getElementById('form-error');
  const languageButtons = [...document.querySelectorAll('.lang-btn')];
  if (
    !inputView ||
    !chartView ||
    !form ||
    !backBtn ||
    !createChartBtn ||
    !dateInput ||
    !dateStatus ||
    !timeInput ||
    !timeStatus ||
    !locationInput ||
    !locationSuggestions ||
    !locationStatus ||
    !formError
  ) {
    return;
  }
  // The engine's supported years, rendered from its policy into the date field's bounds.
  const supportedYears = [dateInput.min, dateInput.max].map((bound) => Number(bound.slice(0, 4)));
  if (!supportedYears.every((year) => Number.isInteger(year) && year > 0)) {
    throw new Error('The birth date field has no supported range.');
  }

  // The chart's characters have a small font of their own. Fetch it now, before the
  // first chart needs it; a failure rejects, and shows in the console.
  document.fonts.load("500 1em 'Noto Serif TC'", '甲');

  let resolvedLocation = null;
  let suggestDebounce = null;
  let suggestRequest = null;
  let latestSuggestions = [];
  let activeSuggestionIndex = -1;
  let currentLanguage = i18n.getLanguage();
  const t = (key, vars = {}) => i18n.t(key, vars, currentLanguage);

  // ── The chart header: the birth moment as entered, and the true solar time ──
  const chartDate = document.getElementById('chart-date');
  const chartSolarTime = document.getElementById('chart-solar-time');
  const displaySwitch = document.getElementById('display-switch');
  const viewSwitch = document.getElementById('view-switch');
  const chartLanguage = document.getElementById('chart-language');
  const newChartBtn = document.getElementById('new-chart-btn');
  const relationshipsTopic = document.getElementById('relationships-topic');
  const relationshipsSection = document.getElementById('relationships-panel');
  const chartPanel = document.getElementById('chart-panel');
  if (!chartDate || !chartSolarTime || !displaySwitch || !viewSwitch || !chartLanguage || !newChartBtn
    || !relationshipsTopic || !relationshipsSection || !chartPanel) throw new Error('Chart view is incomplete.');
  const locale = () => (currentLanguage === 'en' ? 'en' : 'fi');
  // A clock reading, held as a UTC date so that formatting never moves it into the
  // viewer's own time zone. Readings no calendar has, such as 24:10, give null.
  const parseWallClock = (text) => {
    const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(text);
    if (!match) return null;
    const [year, month, day, hour, minute, second] = match.slice(1).map((part) => Number(part || 0));
    const reading = new Date(Date.UTC(year, month - 1, day, hour, minute, second));
    const exact = reading.getUTCFullYear() === year && reading.getUTCMonth() === month - 1
      && reading.getUTCDate() === day && reading.getUTCHours() === hour
      && reading.getUTCMinutes() === minute && reading.getUTCSeconds() === second;
    return exact ? reading : null;
  };
  const formatDate = (reading) => new Intl.DateTimeFormat(locale(), { dateStyle: 'long', timeZone: 'UTC' })
    .format(reading);
  // Finnish writes 16.30, English 16:30; both on a 24-hour clock.
  const formatTime = (reading, withSeconds) => new Intl.DateTimeFormat(locale(), {
    timeStyle: withSeconds ? 'medium' : 'short', hourCycle: 'h23', timeZone: 'UTC',
  }).format(reading);
  // Whole seconds, or with `tenths` to a tenth of a second (the exact values on demand).
  const formatDuration = (totalSeconds, tenths = false) => {
    const scale = tenths ? 10 : 1;
    let remaining = Math.round(totalSeconds * scale);
    const parts = [];
    for (const [size, unit] of [[86400, 'unit_days'], [3600, 'unit_hours'], [60, 'unit_minutes']]) {
      const amount = Math.floor(remaining / (size * scale));
      remaining -= amount * size * scale;
      if (amount) parts.push(`${amount} ${requiredTranslation(unit)}`);
    }
    if (remaining || tenths || !parts.length) {
      const digits = tenths ? 1 : 0;
      const seconds = new Intl.NumberFormat(locale(), { minimumFractionDigits: digits, maximumFractionDigits: digits })
        .format(remaining / scale);
      parts.push(`${seconds} ${requiredTranslation('unit_seconds')}`);
    }
    return parts.join(' ');
  };
  // True solar time, and how far it lies from the clock the birth was recorded on.
  const describeSolarTime = (solarTime, birth) => {
    const reading = solarTime && typeof solarTime.true_solar_time === 'string'
      ? parseWallClock(solarTime.true_solar_time) : null;
    if (!reading) throw new Error(requiredTranslation('solar_time_error'));
    const time = formatTime(reading, true);
    const sameDay = reading.toISOString().slice(0, 10) === birth.toISOString().slice(0, 10);
    const shown = sameDay ? time : requiredTranslation('date_and_time', { date: formatDate(reading), time });
    const offset = Math.round((reading - birth) / 1000);
    const difference = offset === 0
      ? requiredTranslation('clock_offset_none')
      : requiredTranslation(offset < 0 ? 'clock_offset_behind' : 'clock_offset_ahead',
        { duration: formatDuration(Math.abs(offset)) });
    return { reading, text: `${requiredTranslation('true_solar_time', { time: shown })} · ${difference}` };
  };

  // ── The chart's flags: the Zi-hour alternative, and notices ──
  const chartNotices = document.getElementById('chart-notices');
  const ziSwitch = document.getElementById('zi-switch');
  if (!chartNotices || !ziSwitch) throw new Error('Chart header is incomplete.');
  const ZI_CONVENTIONS = ['split_midnight', 'whole_zi_23'];
  // Reads the flags, checking them against the pillars; inconsistent flags stop the chart.
  const readFlags = (flags, fourPillars, request) => {
    const fail = () => { throw new Error(requiredTranslation('flags_error')); };
    if (!flags || typeof flags.zi_hour_window !== 'boolean' || typeof flags.solar_term_ambiguous !== 'boolean'
      || typeof flags.high_latitude_warning !== 'boolean' || typeof flags.model_uncertainty_seconds !== 'number'
      || !(flags.model_uncertainty_seconds > 0)) fail();
    const pillarText = (pillar) => `${pillar?.stem?.chinese}${pillar?.branch?.chinese}`;
    const current = request.conventions?.zi_convention ?? ZI_CONVENTIONS[0];
    const alternative = flags.alternative_pillars;
    // The engine gives the other convention's pillars exactly when the birth is in the Zi hour.
    if (flags.zi_hour_window !== (alternative !== null && alternative !== undefined)) fail();
    let zi = null;
    if (flags.zi_hour_window) {
      const other = alternative.conventions?.zi_convention;
      if (!ZI_CONVENTIONS.includes(other) || other === current) fail();
      // Offered only where the other convention gives other pillars.
      if (pillarText(alternative.day) !== pillarText(fourPillars.day)
        || pillarText(alternative.hour) !== pillarText(fourPillars.hour)) zi = { current, other };
    }
    const notices = [];
    // The month changes at the jie on either side of the birth; the nearer decides the flag.
    const { previous, next } = fourPillars.month.changes;
    const nearest = previous.seconds <= next.seconds ? previous : next;
    const within = nearest.seconds < flags.model_uncertainty_seconds;
    // A millisecond either way: the engine and this check round differently.
    if (flags.solar_term_ambiguous !== within
      && Math.abs(nearest.seconds - flags.model_uncertainty_seconds) > 0.001) fail();
    if (flags.solar_term_ambiguous) {
      const seconds = new Intl.NumberFormat(locale(), { maximumFractionDigits: 1 }).format(flags.model_uncertainty_seconds);
      notices.push(requiredTranslation(
        nearest.term === 'lichun_315' ? 'notice_term_ambiguous_year' : 'notice_term_ambiguous_month', { seconds }));
    }
    if (flags.high_latitude_warning) notices.push(requiredTranslation('notice_high_latitude'));
    return { zi, notices };
  };
  const renderFlags = ({ zi, notices }) => {
    chartNotices.innerHTML = notices.map((notice) => `<li>${esc(notice)}</li>`).join('');
    chartNotices.classList.toggle('hidden', notices.length === 0);
    ziSwitch.classList.toggle('hidden', zi === null);
    ziSwitch.innerHTML = zi === null ? '' : `
      <p class="zi-switch-note" id="zi-switch-note">${esc(requiredTranslation('zi_switch_note'))}</p>
      <div class="zi-switch-options">${ZI_CONVENTIONS.map((convention) => `
        <button type="button" data-zi-convention="${convention}" aria-pressed="${convention === zi.current}">${
          esc(requiredTranslation(`zi_${convention}`))}</button>`).join('')}
      </div>`;
  };

  const setFieldStatus = (status, text, state) => {
    status.textContent = text || '';
    status.classList.remove('is-found', 'is-error');
    if (state) {
      status.classList.add(state);
    }
  };

  const setLocationStatus = (text, state) => setFieldStatus(locationStatus, text, state);

  // A field's error is written beneath it and marks the field invalid; an empty text clears both.
  const setFieldError = (input, status, text) => {
    setFieldStatus(status, text, text ? 'is-error' : '');
    if (text) {
      input.setAttribute('aria-invalid', 'true');
    } else {
      input.removeAttribute('aria-invalid');
    }
  };

  // Returns the first field needing a fix, after writing every message.
  const checkBirthMoment = () => {
    let firstInvalid = null;
    const flag = (input, status, text) => {
      setFieldError(input, status, text);
      if (text && !firstInvalid) firstInvalid = input;
    };
    const year = Number(dateInput.value.split('-')[0]);
    flag(dateInput, dateStatus, !dateInput.value ? t('need_date')
      : year < supportedYears[0] || year > supportedYears[1]
        ? t('date_out_of_range', { min: supportedYears[0], max: supportedYears[1] })
        : '');
    flag(timeInput, timeStatus, timeInput.value ? '' : t('need_time'));
    return firstInvalid;
  };

  dateInput.addEventListener('input', () => setFieldError(dateInput, dateStatus, ''));
  timeInput.addEventListener('input', () => setFieldError(timeInput, timeStatus, ''));

  // Failures that belong to no single field: the chart request itself, or its evidence.
  const setFormError = (text) => {
    formError.textContent = text || '';
    formError.classList.toggle('hidden', !text);
  };
  // The message describes the last attempt; any edit starts a new one.
  form.addEventListener('input', () => setFormError(''));

  // While a chart is being created the button says so and takes no second submit.
  let pending = false;
  const setPending = (value) => {
    pending = value;
    if (value) {
      form.setAttribute('aria-busy', 'true');
    } else {
      form.removeAttribute('aria-busy');
    }
    createChartBtn.classList.toggle('is-pending', value);
    createChartBtn.textContent = t(value ? 'creating_chart' : 'create_chart');
    createChartBtn.disabled = value || !resolvedLocation;
  };

  const applyLanguage = () => {
    document.documentElement.lang = currentLanguage;
    const textNodes = document.querySelectorAll('[data-i18n]');
    textNodes.forEach((node) => {
      const key = node.getAttribute('data-i18n');
      if (key) {
        node.textContent = t(key);
      }
    });
    if (pending) {
      createChartBtn.textContent = t('creating_chart');
    }
    const placeholderNodes = document.querySelectorAll('[data-i18n-placeholder]');
    placeholderNodes.forEach((node) => {
      const key = node.getAttribute('data-i18n-placeholder');
      if (key) {
        node.setAttribute('placeholder', t(key));
      }
    });
    languageButtons.forEach((button) => {
      button.classList.toggle('is-active', button.dataset.lang === currentLanguage);
    });
    chartLanguage.querySelectorAll('button[data-chart-lang]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.chartLang === currentLanguage));
    });
    if (!resolvedLocation && !locationStatus.textContent) {
      setLocationStatus('', '');
    }
  };

  // The field is a combobox: focus stays in it and the active option is announced from it.
  const hideSuggestions = () => {
    latestSuggestions = [];
    activeSuggestionIndex = -1;
    locationSuggestions.innerHTML = '';
    locationSuggestions.classList.add('hidden');
    locationInput.setAttribute('aria-expanded', 'false');
    locationInput.removeAttribute('aria-activedescendant');
  };

  const showSuggestions = (suggestions) => {
    latestSuggestions = suggestions;
    activeSuggestionIndex = -1;
    if (!suggestions.length) {
      hideSuggestions();
      return;
    }
    locationSuggestions.innerHTML = suggestions
      .map(
        (item, index) => `
        <div
          role='option'
          id='location-option-${index}'
          class='location-suggestion'
          aria-selected='false'
          data-index='${index}'
        >
          <span class='location-suggestion-city'>${esc(item.display)}</span>
          <span class='location-suggestion-meta'>${esc(
            `${formatCoordinates(item.latitude, item.longitude)} · ${item.timezone}`
          )}</span>
        </div>
      `
      )
      .join('');
    locationSuggestions.classList.remove('hidden');
    locationInput.setAttribute('aria-expanded', 'true');
  };

  const updateActiveSuggestion = (nextIndex) => {
    const options = [...locationSuggestions.querySelectorAll('.location-suggestion')];
    if (!options.length) {
      activeSuggestionIndex = -1;
      return;
    }
    const max = options.length - 1;
    if (nextIndex < 0) {
      activeSuggestionIndex = max;
    } else if (nextIndex > max) {
      activeSuggestionIndex = 0;
    } else {
      activeSuggestionIndex = nextIndex;
    }
    options.forEach((option, index) => {
      const active = index === activeSuggestionIndex;
      option.classList.toggle('is-active', active);
      option.setAttribute('aria-selected', String(active));
    });
    const activeOption = options[activeSuggestionIndex];
    locationInput.setAttribute('aria-activedescendant', activeOption.id);
    activeOption.scrollIntoView({ block: 'nearest' });
  };

  const cancelSuggestionLookup = () => {
    clearTimeout(suggestDebounce);
    suggestDebounce = null;
    if (suggestRequest) {
      suggestRequest.abort();
      suggestRequest = null;
    }
  };

  // A place picked from the list, or named by a chart's link.
  const pickPlace = (place) => {
    // A lookup still pending must not reopen the list or replace the chosen city's status.
    cancelSuggestionLookup();
    // Kept whole: the chart is computed for these coordinates, since names repeat.
    resolvedLocation = place;
    locationInput.value = place.display;
    createChartBtn.disabled = pending;
    hideSuggestions();
    setLocationStatus(
      t('selected_city', {
        city: place.city,
        coordinates: formatCoordinates(place.latitude, place.longitude),
        timezone: place.timezone,
      }),
      'is-found'
    );
  };

  const applySuggestionAtIndex = (indexValue) => {
    const selected = latestSuggestions[indexValue];
    if (!selected) {
      return;
    }
    pickPlace(selected);
  };

  const clearResolvedLocation = () => {
    resolvedLocation = null;
    createChartBtn.disabled = true;
    hideSuggestions();
    setLocationStatus('', '');
  };

  const lookUpSuggestions = async (cityQuery) => {
    const request = new AbortController();
    suggestRequest = request;
    // Responses can arrive out of order; only the lookup for the current input may be shown.
    const isStale = () => request.signal.aborted || locationInput.value.trim() !== cityQuery;
    try {
      const res = await fetch('/api/location_suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: cityQuery, limit: 8 }),
        signal: request.signal,
      });
      const data = await res.json();
      if (isStale()) {
        return;
      }
      if (!res.ok) {
        throw new Error(data.detail || t('suggest_error'));
      }
      if (!Array.isArray(data.suggestions)) {
        throw new Error(t('suggest_error'));
      }
      showSuggestions(data.suggestions);
      setLocationStatus(t(data.suggestions.length ? 'pick_city' : 'no_places'), '');
    } catch (err) {
      // A cancelled lookup rejects with an AbortError; only the current lookup's failures show.
      if (isStale()) {
        return;
      }
      hideSuggestions();
      setLocationStatus(err.message || t('suggest_error'), 'is-error');
    }
  };

  locationInput.addEventListener('input', () => {
    // The text no longer names the picked place, so a new pick is needed to create a chart.
    if (resolvedLocation) {
      clearResolvedLocation();
    }
    // The listed cities, and any lookup under way, belong to an earlier query.
    cancelSuggestionLookup();
    hideSuggestions();
    const cityQuery = locationInput.value.trim();
    if (!cityQuery) {
      setLocationStatus('', '');
      return;
    }
    suggestDebounce = setTimeout(() => lookUpSuggestions(cityQuery), 180);
  });

  locationInput.addEventListener('keydown', (event) => {
    const hasSuggestions =
      !locationSuggestions.classList.contains('hidden') &&
      locationSuggestions.querySelectorAll('.location-suggestion').length > 0;
    if (!hasSuggestions) {
      return;
    }

    const key = event.key;
    const keyCode = event.keyCode;
    const isArrowDown = key === 'ArrowDown' || key === 'Down' || keyCode === 40;
    const isArrowUp = key === 'ArrowUp' || key === 'Up' || keyCode === 38;
    const isEnter = key === 'Enter' || keyCode === 13;
    const isEscape = key === 'Escape' || key === 'Esc' || keyCode === 27;

    if (isArrowDown) {
      event.preventDefault();
      updateActiveSuggestion(activeSuggestionIndex + 1);
      return;
    }
    if (isArrowUp) {
      event.preventDefault();
      updateActiveSuggestion(activeSuggestionIndex - 1);
      return;
    }
    if (isEnter) {
      event.preventDefault();
      const chosenIndex = activeSuggestionIndex >= 0 ? activeSuggestionIndex : 0;
      applySuggestionAtIndex(chosenIndex);
      return;
    }
    if (isEscape) {
      event.preventDefault();
      hideSuggestions();
    }
  });

  // A pointer pick, like a keyboard pick, leaves focus in the field.
  locationSuggestions.addEventListener('mousedown', (event) => event.preventDefault());

  locationSuggestions.addEventListener('click', (event) => {
    const button = event.target.closest('.location-suggestion');
    if (!button) {
      return;
    }
    const indexValue = Number(button.dataset.index);
    applySuggestionAtIndex(indexValue);
  });

  document.addEventListener('click', (event) => {
    const clickedInside = event.target.closest('.location-group');
    if (!clickedInside) {
      hideSuggestions();
    }
  });

  // The chart on screen: the request that made it, its place and its heading, so that it
  // can be asked for again (in the other language, or under the other Zi-hour
  // convention) and named in the address.
  let shown = null;
  // Only the chart asked for last is drawn: an earlier answer that arrives later is
  // dropped. Leaving the chart drops any answer still on its way.
  let drawing = 0;

  // A chart for a birth at a picked place: its coordinates, not its name, which would
  // resolve to the first place so named.
  const chartRequest = ({ date, time, place, lang, zi }) => ({
    date,
    time,
    location: { timezone: place.timezone, latitude: place.latitude, longitude: place.longitude },
    include_chart: true,
    include_hidden_stems: true,
    include_ten_gods: true,
    include_interactions: true,
    include_day_master_context: true,
    include_role_profile: true,
    lang,
    ...(zi === ZI_CONVENTIONS[0] ? {} : { conventions: { zi_convention: zi } }),
  });

  // Requests a chart and draws it, and says whether it did: a later request supersedes
  // it. Anything missing or inconsistent throws before the chart view is shown.
  const showChart = async (request, place) => {
    const serial = ++drawing;
    const pillarsRes = await fetch('/api/four_pillars', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    const pillarsData = await pillarsRes.json();
    if (serial !== drawing) return false;
    if (!pillarsRes.ok) {
      throw new Error(pillarsData.detail || t('pillars_error'));
    }

    const chartData = pillarsData.chart;
    if (!chartData) {
      throw new Error(t('chart_error'));
    }
    const tenGodsData = pillarsData.ten_gods;
    if (!tenGodsData) {
      throw new Error(t('ten_gods_error'));
    }

    // The header shows the birth as it was entered; the API's header text is not used.
    const birth = parseWallClock(`${request.date}T${request.time}`);
    if (!birth) throw new Error(t('chart_error'));
    const heading = [
      formatDate(birth), formatTime(birth, request.time.length > 5), place.city,
    ].join(' · ');
    const solarTime = describeSolarTime(pillarsData.solar_time, birth);

    renderChart(chartData, Object.fromEntries(
      ['hour', 'day', 'month', 'year'].map((name) => [name, requiredTranslation('pillar_' + name)])));
    setKeyCard(cardAt(keyCard));
    chartDate.textContent = heading;
    chartSolarTime.textContent = solarTime.text;
    pillarChanges.render(pillarsData.four_pillars, chartData, { civil: birth, true_solar: solarTime.reading });
    // Read after the pillar changes are checked: the month's changes decide the term notice.
    renderFlags(readFlags(pillarsData.flags, pillarsData.four_pillars, request));
    populateTenGods(tenGodsData);
    if (!pillarsData.hidden_stems) throw new Error(t('context_error'));
    populateHiddenStems(pillarsData.hidden_stems);
    relationships.render(pillarsData.interactions, chartData, tenGodsData);
    relationshipsTopic.textContent = requiredTranslation('relationships_topic', { count: pillarsData.interactions.length });
    dayMasterContext.render(pillarsData.day_master_context, chartData, tenGodsData, pillarsData.hidden_stems, pillarsData.role_profile);
    closePanel();
    applyDisplay(false);
    shown = { request, place, heading };
    revealChart();
    return true;
  };
  // Open charts are told apart by their tab.
  const revealChart = () => {
    document.title = t('chart_page_title', { chart: shown.heading });
    inputView.classList.add('hidden');
    chartView.classList.remove('hidden');
  };

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (pending) {
      return;
    }

    setFormError('');
    const invalidField = checkBirthMoment();
    if (!resolvedLocation) {
      setLocationStatus(t('need_location'), 'is-error');
      createChartBtn.disabled = true;
    }
    if (invalidField || !resolvedLocation) {
      (invalidField || locationInput).focus();
      return;
    }

    const request = chartRequest({
      date: form.date.value, time: form.time.value, place: resolvedLocation, lang: currentLanguage, zi: ZI_CONVENTIONS[0],
    });

    setPending(true);
    try {
      if (await showChart(request, resolvedLocation)) addressChart('pushState');
    } catch (err) {
      console.error(err);
      setFormError(err.message || t('chart_create_error'));
    } finally {
      setPending(false);
    }
  });

  // The next chart starts as a new one: nothing open, characters on every card.
  const leaveChart = () => {
    drawing += 1;
    closePanel();
    displayMode = 'characters';
    keyCard = { pillar: 'hour', component: 'stem' };
    chartView.classList.add('hidden');
    inputView.classList.remove('hidden');
    document.title = t('page_title');
  };

  // The shown chart, asked for again with one thing changed. A chart that then fails
  // is not left half drawn: the form comes back with the reason. Focus returns to
  // the control that asked, found again in the redrawn chart.
  const reshow = async (changes, focusSelector) => {
    chartView.setAttribute('aria-busy', 'true');
    try {
      if (!(await showChart({ ...shown.request, ...changes }, shown.place))) return;
      addressChart('replaceState');
      chartView.querySelector(focusSelector).focus();
    } catch (err) {
      console.error(err);
      leaveChart();
      setFormError(err.message || t('chart_create_error'));
      addressForm('replaceState');
    } finally {
      chartView.removeAttribute('aria-busy');
    }
  };

  // Meanwhile the chart takes no clicks: they would act on a chart about to be
  // replaced, or leave it only for the new one to open over the form.
  chartView.addEventListener('click', (event) => {
    if (chartView.getAttribute('aria-busy') !== 'true') return;
    event.preventDefault();
    event.stopImmediatePropagation();
  }, { capture: true });

  // The other Zi-hour convention, for this chart only.
  ziSwitch.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-zi-convention]');
    if (!button || button.getAttribute('aria-pressed') === 'true') return;
    const convention = button.dataset.ziConvention;
    reshow({ conventions: { zi_convention: convention } }, `button[data-zi-convention="${convention}"]`);
  });

  // The chart's own words come from the API in the chart's language, so a new
  // language asks for the chart again.
  chartLanguage.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-chart-lang]');
    if (!button || button.getAttribute('aria-pressed') === 'true') return;
    currentLanguage = i18n.setLanguage(button.dataset.chartLang === 'en' ? 'en' : 'fi');
    applyLanguage();
    reshow({ lang: currentLanguage }, `button[data-chart-lang="${currentLanguage}"]`);
  });

  // The same birth in the Evolution explorer.
  viewSwitch.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-view="evolution"]');
    if (!button) return;
    const { request } = shown;
    const query = new URLSearchParams({
      date: request.date,
      time: request.time,
      latitude: String(request.location.latitude),
      longitude: String(request.location.longitude),
      timezone: request.location.timezone,
      lang: currentLanguage,
    });
    window.location.assign(`/explorer/?${query.toString()}`);
  });

  // Edit keeps the birth, so another chart for it only needs what changed. Both steps
  // back to the form are history entries: Back returns to the chart.
  backBtn.addEventListener('click', () => {
    leaveChart();
    addressForm('pushState');
  });

  newChartBtn.addEventListener('click', () => {
    leaveChart();
    addressForm('pushState');
    form.reset();
    clearResolvedLocation();
    setFieldError(dateInput, dateStatus, '');
    setFieldError(timeInput, timeStatus, '');
    dateInput.focus();
  });

  // ── Hidden stems: populate, expand, collapse ──

  const populateHiddenStems = (data) => {
    const panels = document.querySelectorAll('.hidden-stems-panel');
    panels.forEach((panel) => {
      const pillarName = panel.dataset.pillar;
      const pillarData = data[pillarName];
      if (!pillarData) return;

      const list = panel.querySelector('.hidden-stems-list');
      if (!list) return;

      list.innerHTML = pillarData.hidden_stems
        .map((hs) => {
          const elementName = t('element_' + hs.element);
          const qiLabel = t('qi_' + hs.qi_type);
          return `
            <div class='hidden-stem-item' data-hidden-stem='${esc(hs.char)}'>
              <span class='hidden-stem-dot ${esc(hs.element)}'></span>
              <span class='hidden-stem-label'>${esc(hs.polarity)} ${esc(elementName)}</span>
              <span class='hidden-stem-type'>${esc(qiLabel)}</span>
            </div>`;
        })
        .join('');
    });
  };

  // ── Ten gods: populate card backs ──

  const requiredTranslation = (key, vars = {}) => {
    if (!Object.prototype.hasOwnProperty.call(i18n.dictionaries[currentLanguage], key)) {
      throw new Error(`Missing ${currentLanguage} translation: ${key}`);
    }
    return t(key, vars);
  };

  // One topic is open at a time, in the panel: a relationship (or their list), the
  // Day Master context, or a pillar's changes.
  const setRelationshipsOpen = (open) => {
    relationshipsSection.classList.toggle('hidden', !open);
    relationshipsTopic.setAttribute('aria-expanded', String(open));
  };
  const relationships = window.EC_RELATIONSHIPS.create({
    root: chartView, translate: requiredTranslation, escape: esc,
    beforeSelect: () => { dayMasterContext.clear(); pillarChanges.clear(); },
  });
  const dayMasterContext = window.EC_DAY_MASTER_CONTEXT.create({
    root: chartView, translate: requiredTranslation, escape: esc,
    beforeSelect: () => { relationships.clear(); pillarChanges.clear(); setRelationshipsOpen(false); },
  });
  const pillarChanges = window.EC_PILLAR_CHANGES.create({
    root: chartView, translate: requiredTranslation, escape: esc,
    format: { parseWallClock, date: formatDate, time: formatTime, duration: formatDuration },
    beforeSelect: () => { relationships.clear(); dayMasterContext.clear(); setRelationshipsOpen(false); },
  });
  const closePanel = () => {
    relationships.clear();
    dayMasterContext.clear();
    pillarChanges.clear();
    setRelationshipsOpen(false);
  };
  relationshipsTopic.addEventListener('click', () => {
    const open = relationshipsTopic.getAttribute('aria-expanded') !== 'true';
    closePanel();
    setRelationshipsOpen(open);
  });

  // The panel is open while any of its sections is: the modules show and hide their
  // own sections, and the panel follows them.
  const panelSections = [...chartPanel.querySelectorAll(':scope > section')];
  const syncPanel = () => {
    const open = panelSections.some((section) => !section.classList.contains('hidden'));
    chartPanel.classList.toggle('hidden', !open);
    chartView.classList.toggle('has-panel', open);
  };
  const panelObserver = new MutationObserver(syncPanel);
  panelSections.forEach((section) => panelObserver.observe(section, { attributes: true, attributeFilter: ['class'] }));

  // Closing returns focus to the chart control whose topic was open.
  const closePanelAndReturnFocus = () => {
    const opener = chartView.querySelector('.chart-column [aria-expanded="true"]');
    closePanel();
    if (opener) opener.focus();
  };
  chartPanel.addEventListener('click', (event) => {
    if (event.target.closest('[data-close-panel]')) closePanelAndReturnFocus();
  });
  // A module closes its own selection on Escape first; an open list closes on the next.
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || event.defaultPrevented) return;
    if (relationshipsTopic.getAttribute('aria-expanded') !== 'true') return;
    event.preventDefault();
    closePanelAndReturnFocus();
  });

  // ── Display: every card at once shows its character, its ten gods, or its hidden stems ──
  let displayMode = 'characters';
  const hiddenStemsOf = (branchCard) => branchCard.closest('.pillar-cards').querySelector('.hidden-stems-panel');
  const showsHiddenStems = (panel) => displayMode === 'hidden-stems'
    && panel.querySelector('.hidden-stems-list').children.length > 0;
  // A long press or a tap changes one card; the choice then reads 'mixed', and
  // pressing it again shows it on every card.
  const syncDisplaySwitch = () => {
    const mixed = [...pillarsContainer.querySelectorAll('.card')].some((card) =>
      card.classList.contains('is-flipped') !== (displayMode === 'ten-gods')
      || (card.classList.contains('branch')
        && hiddenStemsOf(card).classList.contains('is-expanded') !== showsHiddenStems(hiddenStemsOf(card))));
    displaySwitch.querySelectorAll('button[data-display]').forEach((button) => {
      const chosen = button.dataset.display === displayMode;
      button.setAttribute('aria-pressed', chosen ? (mixed ? 'mixed' : 'true') : 'false');
    });
  };
  const applyDisplay = (animate) => {
    pillarsContainer.querySelectorAll('.card').forEach((card) => {
      const flip = displayMode === 'ten-gods';
      if (card.classList.contains('is-flipped') === flip) return;
      if (animate) flipCard(card);
      else {
        card.classList.toggle('is-flipped', flip);
        labelCard(card);
      }
    });
    pillarsContainer.querySelectorAll('.card.branch').forEach((branchCard) => {
      const panel = hiddenStemsOf(branchCard);
      const expand = showsHiddenStems(panel);
      if (panel.classList.contains('is-expanded') === expand) return;
      if (expand) expandPanel(panel, branchCard, animate);
      else collapsePanel(panel, branchCard);
    });
    syncDisplaySwitch();
  };
  displaySwitch.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-display]');
    if (!button || button.getAttribute('aria-pressed') === 'true') return;
    displayMode = button.dataset.display;
    applyDisplay(!reducedMotion.matches);
  });

  const populateTenGods = (data) => {
    document.querySelectorAll('#pillars .card').forEach((card) => {
      const pillarName = card.dataset.pillar;
      const pillarData = data[pillarName];
      if (!pillarData) {
        throw new Error(`Ten gods missing for the ${pillarName} pillar.`);
      }
      const back = card.querySelector('.card-back');

      if (card.classList.contains('stem')) {
        if (pillarData.stem.char !== card.dataset.char) {
          throw new Error(`Ten gods do not match the ${pillarName} stem.`);
        }
        back.querySelector('.ten-god-name').textContent = requiredTranslation(
          'ten_god_' + pillarData.stem.ten_god
        );
        return;
      }

      if (pillarData.branch !== card.dataset.char) {
        throw new Error(`Ten gods do not match the ${pillarName} branch.`);
      }
      back.querySelector('.ten-god-list').innerHTML = pillarData.hidden_stems
        .map((hs) => {
          const tenGodName = requiredTranslation('ten_god_' + hs.ten_god);
          const qiLabel = requiredTranslation('qi_' + hs.qi_type);
          return `
            <div class='hidden-stem-item' data-hidden-stem='${esc(hs.char)}'>
              <span class='hidden-stem-dot ${esc(hs.element)}'></span>
              <span class='hidden-stem-label'>${esc(tenGodName)}</span>
              <span class='hidden-stem-type'>${esc(qiLabel)}</span>
            </div>`;
        })
        .join('');
    });
  };

  const expandPanel = (panel, branchCard, animate = true) => {
    branchCard.classList.add('is-expanded');
    branchCard.setAttribute('aria-expanded', 'true');
    panel.classList.add('is-expanded');
    if (!animate) {
      panel.style.height = 'auto';
      return;
    }
    panel.style.height = panel.scrollHeight + 'px';
    panel.addEventListener('transitionend', (event) => {
      if (event.propertyName === 'height' && panel.classList.contains('is-expanded')) panel.style.height = 'auto';
    }, { once: true });
  };

  const collapsePanel = (panel, branchCard) => {
    panel.style.height = panel.scrollHeight + 'px';
    panel.offsetHeight; // force reflow
    panel.classList.remove('is-expanded');
    branchCard.classList.remove('is-expanded');
    branchCard.setAttribute('aria-expanded', 'false');
    panel.style.height = '0';
  };

  // ── Cards: long press flips to ten gods, quick click toggles hidden stems ──

  const pillarsContainer = document.getElementById('pillars');
  const LONG_PRESS_MS = 500;
  const LONG_PRESS_MOVE_TOLERANCE_PX = 10;
  // A press lasts until its pointer is released; its timer is null once the card flipped.
  let activePress = null;
  let suppressNextClick = false;

  const cancelPress = () => {
    if (!activePress) return;
    clearTimeout(activePress.timer);
    activePress = null;
  };

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  // Nothing else shows that a card turns over, so a hint says so, above the card
  // under the mouse. It stays there while the page scrolls.
  const cardHint = document.createElement('div');
  cardHint.className = 'card-hint hidden';
  cardHint.setAttribute('aria-hidden', 'true');
  chartView.append(cardHint);
  let hintedCard = null;
  const placeCardHint = () => {
    const box = hintedCard.getBoundingClientRect();
    cardHint.style.left = `${box.left + box.width / 2}px`;
    cardHint.style.top = `${box.top}px`;
  };
  const hideCardHint = () => {
    hintedCard = null;
    cardHint.classList.add('hidden');
  };
  pillarsContainer.addEventListener('pointerover', (event) => {
    const card = event.target.closest('.card');
    if (!card || event.pointerType !== 'mouse' || activePress) return;
    hintedCard = card;
    cardHint.textContent = requiredTranslation('long_press_hint');
    placeCardHint();
    cardHint.classList.remove('hidden');
  });
  pillarsContainer.addEventListener('pointerout', (event) => {
    if (!event.relatedTarget || !event.target.closest('.card')?.contains(event.relatedTarget)) hideCardHint();
  });
  window.addEventListener('scroll', () => { if (hintedCard) placeCardHint(); }, { passive: true });

  // A card is named by its pillar and the side it shows.
  const labelCard = (card) => {
    const component = card.classList.contains('stem') ? 'stem' : 'branch';
    const side = card.classList.contains('is-flipped') ? 'back' : 'front';
    card.setAttribute('aria-labelledby', `pillar-name-${card.dataset.pillar} card-${card.dataset.pillar}-${component}-${side}`);
  };

  // The facing side sizes the card, so a taller back grows the card as it turns.
  const flipCard = (card) => {
    const inner = card.querySelector('.card-inner');
    inner.getAnimations().forEach((animation) => animation.cancel());
    card.classList.remove('is-turning');
    const fromHeight = inner.getBoundingClientRect().height;
    const flipped = card.classList.toggle('is-flipped');
    labelCard(card);
    if (reducedMotion.matches) return;
    const toHeight = inner.getBoundingClientRect().height;
    card.classList.add('is-turning');
    const turn = inner.animate(
      [
        { height: `${fromHeight}px`, transform: `rotateY(${flipped ? 0 : 180}deg)` },
        { height: `${toHeight}px`, transform: `rotateY(${flipped ? 180 : 360}deg)` },
      ],
      { duration: 600, easing: 'cubic-bezier(0.4, 0, 0.2, 1)', fill: 'forwards' }
    );
    turn.onfinish = () => {
      card.classList.remove('is-turning');
      turn.cancel();
    };
  };

  pillarsContainer.addEventListener('pointerdown', (e) => {
    cancelPress();
    suppressNextClick = false;
    if (!e.isPrimary || e.button !== 0) return;
    const card = e.target.closest('.card');
    if (!card) return;
    hideCardHint();
    const press = {
      pointerId: e.pointerId,
      pointerType: e.pointerType,
      startX: e.clientX,
      startY: e.clientY,
      timer: null,
    };
    press.timer = setTimeout(() => {
      press.timer = null;
      // The release that ends this press must not also toggle hidden stems.
      suppressNextClick = true;
      flipCard(card);
      syncDisplaySwitch();
    }, LONG_PRESS_MS);
    activePress = press;
  });

  document.addEventListener('pointermove', (e) => {
    if (!activePress || !activePress.timer || e.pointerId !== activePress.pointerId) return;
    const moved = Math.hypot(e.clientX - activePress.startX, e.clientY - activePress.startY);
    // A drag, or another button pressed during the hold, is not a long press.
    if (moved > LONG_PRESS_MOVE_TOLERANCE_PX || e.button !== -1) {
      cancelPress();
    }
  });

  ['pointerup', 'pointercancel'].forEach((type) => {
    document.addEventListener(type, (e) => {
      if (activePress && e.pointerId === activePress.pointerId) {
        cancelPress();
      }
    });
  });

  window.addEventListener('blur', cancelPress);

  pillarsContainer.addEventListener('contextmenu', (e) => {
    if (!activePress) return;
    // A mouse context menu (right click, ctrl+click) is its own gesture: let it open.
    if (activePress.pointerType === 'mouse') {
      cancelPress();
      return;
    }
    // Touch and pen open a context menu on long press; this hold belongs to the card.
    e.preventDefault();
  });

  pillarsContainer.addEventListener('click', (e) => {
    if (suppressNextClick) {
      suppressNextClick = false;
      return;
    }

    const branchCard = e.target.closest('.card.branch');
    if (!branchCard) return;

    const pillarCards = branchCard.closest('.pillar-cards');
    if (!pillarCards) return;

    const panel = pillarCards.querySelector('.hidden-stems-panel');
    if (!panel) return;

    const list = panel.querySelector('.hidden-stems-list');
    if (!list || !list.children.length) return;

    if (panel.classList.contains('is-expanded')) {
      collapsePanel(panel, branchCard);
    } else {
      expandPanel(panel, branchCard);
    }
    syncDisplaySwitch();
  });

  // ── The cards by keyboard ──
  // The eight cards take one tab stop, the card last focused (the hour stem to begin
  // with), and arrows move between them: left and right along the pillars, up and down
  // between stem and branch. Enter or Space opens a branch's hidden stems, as a click
  // does; T turns the card with focus, as a long press does. A hint above the card
  // says so when it has keyboard focus.
  const PILLAR_ORDER = ['hour', 'day', 'month', 'year'];
  let keyCard = { pillar: 'hour', component: 'stem' };
  const cardAt = ({ pillar, component }) => pillarsContainer.querySelector(`.card.${component}[data-pillar="${pillar}"]`);
  const setKeyCard = (card) => {
    keyCard = { pillar: card.dataset.pillar, component: card.classList.contains('stem') ? 'stem' : 'branch' };
    pillarsContainer.querySelectorAll('.card').forEach((node) => node.setAttribute('tabindex', node === card ? '0' : '-1'));
  };
  pillarsContainer.addEventListener('focusin', (event) => {
    const card = event.target;
    if (!card.matches('.card')) return;
    setKeyCard(card);
    if (!card.matches(':focus-visible')) return;
    hintedCard = card;
    cardHint.textContent = requiredTranslation(card.classList.contains('branch') ? 'key_hint_branch' : 'key_hint_stem');
    placeCardHint();
    cardHint.classList.remove('hidden');
  });
  pillarsContainer.addEventListener('focusout', (event) => {
    if (event.target === hintedCard) hideCardHint();
  });
  pillarsContainer.addEventListener('keydown', (event) => {
    const card = event.target;
    if (!card.matches('.card') || event.altKey || event.ctrlKey || event.metaKey) return;
    const pillar = card.dataset.pillar;
    const component = card.classList.contains('stem') ? 'stem' : 'branch';
    const at = PILLAR_ORDER.indexOf(pillar);
    const moves = {
      ArrowLeft: at > 0 ? { pillar: PILLAR_ORDER[at - 1], component } : null,
      ArrowRight: at < PILLAR_ORDER.length - 1 ? { pillar: PILLAR_ORDER[at + 1], component } : null,
      ArrowUp: component === 'branch' ? { pillar, component: 'stem' } : null,
      ArrowDown: component === 'stem' ? { pillar, component: 'branch' } : null,
    };
    if (Object.hasOwn(moves, event.key)) {
      // The page does not scroll under the cards.
      event.preventDefault();
      if (moves[event.key]) cardAt(moves[event.key]).focus();
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (component === 'branch' && !event.repeat) card.click();
      return;
    }
    if ((event.key === 't' || event.key === 'T') && !event.repeat) {
      event.preventDefault();
      flipCard(card);
      syncDisplaySwitch();
    }
  });

  languageButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const selectedLang = button.dataset.lang === 'en' ? 'en' : 'fi';
      currentLanguage = i18n.setLanguage(selectedLang);
      applyLanguage();
    });
  });

  // ── The address: the chart on screen and its open topic ──
  // A chart lives in the address's fragment, which browsers never send to the server:
  // #chart?date=…&time=…&place=…&city=…&latitude=…&longitude=…&timezone=…&lang=…, then
  // zi, display and topic where they differ from a new chart's. A new chart, another
  // topic, Edit and New chart add history entries; the language, the Zi-hour convention
  // and the display replace the current one. The address never names a chart that is
  // not on screen.
  const CHART_ROUTE = '#chart?';
  const LINK_PARTS = ['date', 'time', 'place', 'city', 'latitude', 'longitude', 'timezone', 'lang', 'zi', 'display', 'topic'];
  const DISPLAYS = ['characters', 'ten-gods', 'hidden-stems'];
  // The pages a topic can show. Whether this chart has the one named is known once it is drawn.
  const TOPIC_PATH = /^(season|roots|roles(\/[a-z_]+)?(\/stem\/(hour|day|month|year))?|relationships(\/[a-z_]+:\d+:[a-z-]+)?|pillar\/(hour|day|month|year))$/;
  const linkError = (part) => new Error(t('link_error', { part }));
  const formAddress = () => `${location.pathname}${location.search}`;

  // The topic open in the panel, as the address names it, or null.
  const contextDetail = document.getElementById('context-detail');
  const currentTopic = () => {
    if (!contextDetail.classList.contains('hidden')) return contextDetail.dataset.topic;
    if (relationshipsTopic.getAttribute('aria-expanded') === 'true') {
      const chosen = relationshipsSection.querySelector('.relationship-chip.is-active');
      return chosen ? `relationships/${chosen.dataset.relationship}` : 'relationships';
    }
    const pillar = chartView.querySelector('.pillar-identity[aria-expanded="true"]');
    return pillar ? `pillar/${pillar.dataset.pillar}` : null;
  };

  const chartAddress = () => {
    const { request, place } = shown;
    const params = new URLSearchParams({
      date: request.date,
      time: request.time,
      place: place.display,
      city: place.city,
      latitude: String(request.location.latitude),
      longitude: String(request.location.longitude),
      timezone: request.location.timezone,
      lang: request.lang,
    });
    const zi = request.conventions?.zi_convention ?? ZI_CONVENTIONS[0];
    if (zi !== ZI_CONVENTIONS[0]) params.set('zi', zi);
    if (displayMode !== 'characters') params.set('display', displayMode);
    const topic = currentTopic();
    if (topic !== null) params.set('topic', topic);
    return `${formAddress()}${CHART_ROUTE}${params}`;
  };

  // What the address holds: null for the form, or the chart's open topic and display.
  let addressed = null;
  const addressChart = (method) => {
    history[method](null, '', chartAddress());
    addressed = { topic: currentTopic(), display: displayMode };
  };
  const addressForm = (method) => {
    history[method](null, '', formAddress());
    addressed = null;
  };

  // After a reader's click or key on the chart, the address follows what is open.
  const followView = () => {
    if (addressed === null || chartView.getAttribute('aria-busy') === 'true') return;
    const topic = currentTopic();
    if (topic !== addressed.topic) addressChart('pushState');
    else if (displayMode !== addressed.display) addressChart('replaceState');
  };
  chartView.addEventListener('click', followView);
  document.addEventListener('keydown', followView);

  // The chart a link describes, or null when it describes none. A link that describes
  // no chart throws, naming the part that is missing or wrong.
  const readChartLink = (hash) => {
    if (hash === '' || hash === '#') return null;
    if (!hash.startsWith(CHART_ROUTE)) throw linkError('chart');
    const params = new URLSearchParams(hash.slice(CHART_ROUTE.length));
    for (const key of new Set(params.keys())) {
      if (!LINK_PARTS.includes(key) || params.getAll(key).length > 1) throw linkError(key);
    }
    const text = (key) => {
      const value = params.get(key);
      if (value === null || value.trim() === '') throw linkError(key);
      return value;
    };
    const optional = (key, valid) => {
      const value = params.get(key);
      if (value !== null && !valid(value)) throw linkError(key);
      return value;
    };
    const coordinate = (key, limit) => {
      const value = Number(text(key));
      if (!Number.isFinite(value) || Math.abs(value) > limit) throw linkError(key);
      return value;
    };
    const date = text('date');
    const year = Number(date.slice(0, 4));
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !parseWallClock(`${date}T00:00`)
      || year < supportedYears[0] || year > supportedYears[1]) throw linkError('date');
    const time = text('time');
    if (!/^\d{2}:\d{2}(:\d{2})?$/.test(time) || !parseWallClock(`${date}T${time}`)) throw linkError('time');
    const lang = text('lang');
    if (!['fi', 'en'].includes(lang)) throw linkError('lang');
    return {
      date,
      time,
      place: {
        display: text('place'),
        city: text('city'),
        latitude: coordinate('latitude', 90),
        longitude: coordinate('longitude', 180),
        timezone: text('timezone'),
      },
      lang,
      zi: optional('zi', (value) => ZI_CONVENTIONS.includes(value)) ?? ZI_CONVENTIONS[0],
      display: optional('display', (value) => DISPLAYS.includes(value)) ?? 'characters',
      topic: optional('topic', (value) => TOPIC_PATH.test(value)),
    };
  };

  const sameChart = (link) => {
    if (shown === null) return false;
    const { request, place } = shown;
    return place.display === link.place.display && place.city === link.place.city
      && request.date === link.date && request.time === link.time && request.lang === link.lang
      && request.location.latitude === link.place.latitude && request.location.longitude === link.place.longitude
      && request.location.timezone === link.place.timezone
      && (request.conventions?.zi_convention ?? ZI_CONVENTIONS[0]) === link.zi;
  };

  // Opens the topic a link names, as a reader would, and checks that it is the one open.
  const openTopic = (topic) => {
    const need = (element) => {
      if (!element) throw linkError('topic');
      return element;
    };
    const [first, ...rest] = topic.split('/');
    if (first === 'relationships') {
      relationshipsTopic.click();
      if (rest.length) {
        need([...relationshipsSection.querySelectorAll('.relationship-chip')]
          .find((chip) => chip.dataset.relationship === rest[0])).click();
      }
    } else if (first === 'pillar') {
      need(chartView.querySelector(`.pillar-identity[data-pillar="${rest[0]}"]`)).click();
    } else {
      need(chartView.querySelector(`#context-controls button[data-context="${first}"]`)).click();
      // roles/<role>, roles/stem/<pillar>, or roles/<role>/stem/<pillar>
      const role = rest[0] === 'stem' ? '' : rest.shift();
      if (role) need(contextDetail.querySelector(`button[data-role="${role}"]`)).click();
      if (rest[0] === 'stem') {
        need(contextDetail.querySelector(`button[data-root-pillar="${rest[1]}"][data-from-role="${role}"]`)).click();
      }
    }
    if (currentTopic() !== topic) throw linkError('topic');
  };

  // Shows what the address names, the form or a chart with its topic and display,
  // without adding to the history. The birth goes into the form, for Edit. An address
  // that names no chart gives way to the form's, with the reason.
  let arrivals = 0;
  const followAddress = async () => {
    const arrival = ++arrivals;
    // Until the address is followed, opening its topic is not a reader's step.
    addressed = null;
    // An earlier arrival or a creation still under way is superseded, and so is its wait.
    chartView.removeAttribute('aria-busy');
    setPending(false);
    setFormError('');
    let link;
    try {
      link = readChartLink(location.hash);
    } catch (err) {
      console.error(err);
      leaveChart();
      setFormError(err.message);
      addressForm('replaceState');
      return;
    }
    if (link === null) {
      leaveChart();
      return;
    }
    if (link.lang !== currentLanguage) {
      currentLanguage = i18n.setLanguage(link.lang);
      applyLanguage();
    }
    dateInput.value = link.date;
    timeInput.value = link.time;
    setFieldError(dateInput, dateStatus, '');
    setFieldError(timeInput, timeStatus, '');
    pickPlace(link.place);
    // Meanwhile a chart on screen takes no clicks, and the form says it is creating one.
    const onChart = !chartView.classList.contains('hidden');
    try {
      if (sameChart(link)) {
        closePanel();
        displayMode = link.display;
        applyDisplay(false);
        revealChart();
      } else {
        if (onChart) chartView.setAttribute('aria-busy', 'true');
        else setPending(true);
        displayMode = link.display;
        const drawn = await showChart(chartRequest(link), link.place)
          .finally(() => {
            if (arrival !== arrivals) return;
            chartView.removeAttribute('aria-busy');
            setPending(false);
          });
        if (!drawn) return;
      }
      if (link.topic !== null) openTopic(link.topic);
      addressChart('replaceState');
    } catch (err) {
      console.error(err);
      leaveChart();
      setFormError(err.message || t('chart_create_error'));
      addressForm('replaceState');
    }
  };
  window.addEventListener('popstate', followAddress);

  // ── Copy link: the address names this chart and its open topic ──
  const copyLinkBtn = document.getElementById('copy-link-btn');
  if (!copyLinkBtn) throw new Error('Chart bar is incomplete.');
  // What a bar action did, said briefly over the foot of the page and read out.
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.setAttribute('role', 'status');
  chartView.append(toast);
  let toastTimer = null;
  const showToast = (text, isError) => {
    clearTimeout(toastTimer);
    toast.textContent = text;
    toast.classList.toggle('is-error', isError);
    toast.classList.add('is-shown');
    toastTimer = setTimeout(() => {
      toast.classList.remove('is-shown');
      toast.textContent = '';
    }, isError ? 6000 : 3000);
  };
  copyLinkBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(location.href);
      showToast(requiredTranslation('link_copied'), false);
    } catch (err) {
      console.error(err);
      showToast(requiredTranslation('link_copy_error'), true);
    }
  });

  // ── The keys, and the commands ──
  // ? lists the keys while the chart has focus: a character key acts only then (WCAG
  // 2.1.4). ⌘K or Ctrl+K opens the commands wherever focus is, while a chart is shown.
  const keysDialog = document.getElementById('keys-dialog');
  const paletteDialog = document.getElementById('command-palette');
  if (!keysDialog || !paletteDialog) throw new Error('Chart dialogs are incomplete.');
  const palette = window.EC_PALETTE.create({ dialog: paletteDialog, escape: esc });
  // Escape in a dialog closes it and nothing else: an open topic stays open.
  [keysDialog, paletteDialog].forEach((dialog) => dialog.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') event.stopPropagation();
  }));
  let keysOpener = null;
  const openKeys = () => {
    keysOpener = document.activeElement;
    keysDialog.showModal();
  };
  keysDialog.addEventListener('click', (event) => {
    if (event.target.closest('[data-close-dialog]')) keysDialog.close();
  });
  keysDialog.addEventListener('close', () => {
    if (keysOpener) keysOpener.focus();
  });

  // A topic from the palette opens as a link's does, in one step of the history.
  const goToTopic = (path) => {
    if (currentTopic() === path) return;
    const before = addressed;
    addressed = null;
    try {
      closePanel();
      openTopic(path);
    } finally {
      addressed = before;
    }
    followView();
  };
  const ROLES = ['friend', 'rob_wealth', 'eating_god', 'hurting_officer', 'indirect_wealth', 'direct_wealth',
    'seven_killings', 'direct_officer', 'indirect_resource', 'direct_resource'];
  // What the chart offers now, named as its controls name it.
  const chartCommands = () => {
    const commands = [];
    const add = (group, label, run) => commands.push({ group, label: label.replace(/\s+/g, ' ').trim(), run });
    const topics = requiredTranslation('palette_topics');
    chartView.querySelectorAll('#context-controls button[data-context]').forEach((button) => {
      add(topics, button.textContent, () => goToTopic(button.dataset.context));
    });
    add(topics, relationshipsTopic.textContent, () => goToTopic('relationships'));
    relationshipsSection.querySelectorAll('.relationship-chip').forEach((chip) => {
      add(requiredTranslation('relationships'), chip.textContent, () => goToTopic(`relationships/${chip.dataset.relationship}`));
    });
    ROLES.forEach((role) => {
      add(requiredTranslation('roles_title'), requiredTranslation('ten_god_' + role), () => goToTopic(`roles/${role}`));
    });
    chartView.querySelectorAll('.pillar-identity').forEach((button) => {
      add(requiredTranslation('palette_pillars'),
        `${requiredTranslation('pillar_' + button.dataset.pillar)} · ${button.textContent}`,
        () => goToTopic(`pillar/${button.dataset.pillar}`));
    });
    displaySwitch.querySelectorAll('button[data-display]').forEach((button) => {
      add(requiredTranslation('display_label'), button.textContent, () => button.click());
    });
    chartLanguage.querySelectorAll('button[data-chart-lang][aria-pressed="false"]').forEach((button) => {
      add(requiredTranslation('language_label'), button.textContent, () => button.click());
    });
    const evolution = viewSwitch.querySelector('button[data-view="evolution"]');
    add(requiredTranslation('view_label'), evolution.textContent, () => evolution.click());
    const chart = requiredTranslation('palette_chart');
    [copyLinkBtn, backBtn, newChartBtn].forEach((button) => add(chart, button.textContent, () => button.click()));
    if (currentTopic() !== null) add(chart, requiredTranslation('panel_close'), closePanelAndReturnFocus);
    add(chart, requiredTranslation('keys_title'), openKeys);
    return commands;
  };

  document.addEventListener('keydown', (event) => {
    if (event.defaultPrevented || chartView.classList.contains('hidden') || keysDialog.open || paletteDialog.open) return;
    if (event.key.toLowerCase() === 'k' && (event.metaKey || event.ctrlKey) && !event.altKey && !event.shiftKey) {
      event.preventDefault();
      palette.open(chartCommands());
      return;
    }
    const focus = document.activeElement;
    if (event.key === '?' && !event.ctrlKey && !event.metaKey && !event.altKey
      && chartView.contains(focus) && !focus.closest('input, textarea, select, [contenteditable="true"]')) {
      event.preventDefault();
      openKeys();
    }
  });

  applyLanguage();
  if (location.hash) followAddress();
});


// `plainNames` are the pillars' plain names in the page language; the chart's own
// labels are their poetic names.
function renderChart(data, plainNames) {
  const container = document.getElementById('pillars');
  container.innerHTML = '';

  const pillarKeys = ['hour', 'day', 'month', 'year'];
  const expandHint = `<svg class='branch-expand-hint' aria-hidden='true' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>`;

  data.pillars.forEach((p, i) => {
    const pillar = document.createElement('div');
    pillar.className = 'pillar';
    pillar.dataset.pillar = pillarKeys[i];
    pillar.style.animationDelay = [0.5, 0.35, 0.2, 0.05][i] + 's';

    // Each card is named by its pillar and its facing side (see labelCard). A branch is
    // a button: it opens its hidden stems.
    const key = pillarKeys[i];
    pillar.innerHTML = `
      <div class='pillar-header'>
        <div class='pillar-label'>
          <span class='pillar-plain' id='pillar-name-${key}'>${esc(plainNames[pillarKeys[i]])}</span>
          <span class='pillar-poetic'>${esc(p.label)}</span>
        </div>
        <button type='button' class='pillar-identity' data-pillar='${pillarKeys[i]}'
          aria-expanded='false' aria-controls='pillar-detail'>
          <span class='pillar-chars' lang='zh-Hant'>${esc(p.stem.char + p.branch.char)}</span>
          <span class='pillar-pinyin'>${esc(`${p.stem.pinyin} ${p.branch.pinyin}`)}</span>
        </button>
        <p class='pillar-mark'></p>
      </div>
      <div class='pillar-cards'>
        <div class='card ${p.stem.element} stem' data-pillar='${pillarKeys[i]}' data-char='${esc(p.stem.char)}'
          role='group' tabindex='-1' aria-keyshortcuts='T' aria-labelledby='pillar-name-${key} card-${key}-stem-front'>
          <div class='card-inner'>
            <div class='card-face card-front' id='card-${key}-stem-front'>
              <div class='glyph' lang='zh-Hant'>${esc(p.stem.char)}</div>
              <div class='gua'>${renderLines(p.stem.lines)}</div>
              <div class='element-name'>${esc(p.stem.label)}</div>
            </div>
            <div class='card-face card-back' id='card-${key}-stem-back'>
              <div class='ten-god-name'></div>
            </div>
          </div>
        </div>
        <div class='card ${p.branch.element} branch' data-pillar='${pillarKeys[i]}' data-char='${esc(p.branch.char)}'
          role='button' tabindex='-1' aria-expanded='false' aria-controls='hidden-stems-${key}' aria-keyshortcuts='Enter Space T'
          aria-labelledby='pillar-name-${key} card-${key}-branch-front'>
          <div class='card-inner'>
            <div class='card-face card-front' id='card-${key}-branch-front'>
              <div class='glyph' lang='zh-Hant'>${esc(p.branch.char)}</div>
              <div class='gua'>${renderLines(p.branch.lines)}</div>
              <div class='animal-name'>${esc(p.branch.animal_fi)}</div>
              <div class='animal-element'>${esc(p.branch.element_label)}</div>
              ${expandHint}
            </div>
            <div class='card-face card-back' id='card-${key}-branch-back'>
              <div class='ten-god-list'></div>
              ${expandHint}
            </div>
          </div>
        </div>
        <div class='hidden-stems-panel ${p.branch.element}' data-pillar='${pillarKeys[i]}' id='hidden-stems-${key}'>
          <div class='hidden-stems-list'></div>
        </div>
      </div>
    `;

    container.appendChild(pillar);
  });
}


function renderLines(lines) {
  return lines.map((lineCode) => `<div class='${lineCode}'></div>`).join('');
}


function esc(str) {
  const el = document.createElement('span');
  el.textContent = String(str ?? '');
  return el.innerHTML;
}


// Two decimals is about a kilometre, or under 3 seconds of solar time.
function formatCoordinates(latitude, longitude) {
  const latitudeText = `${Math.abs(latitude).toFixed(2)}° ${latitude < 0 ? 'S' : 'N'}`;
  const longitudeText = `${Math.abs(longitude).toFixed(2)}° ${longitude < 0 ? 'W' : 'E'}`;
  return `${latitudeText}, ${longitudeText}`;
}
