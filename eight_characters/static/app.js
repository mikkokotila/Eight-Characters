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
  const modeButtons = [...document.querySelectorAll('.mode-btn')];
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

  let resolvedLocation = null;
  let suggestDebounce = null;
  let suggestRequest = null;
  let latestSuggestions = [];
  let activeSuggestionIndex = -1;
  let currentLanguage = i18n.getLanguage();
  let selectedMode = 'standard';
  const t = (key, vars = {}) => i18n.t(key, vars, currentLanguage);

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
    if (!resolvedLocation && !locationStatus.textContent) {
      setLocationStatus('', '');
    }
  };

  const applyModeSelection = () => {
    modeButtons.forEach((button) => {
      button.classList.toggle('is-active', button.dataset.mode === selectedMode);
    });
  };

  const hideSuggestions = () => {
    latestSuggestions = [];
    activeSuggestionIndex = -1;
    locationSuggestions.innerHTML = '';
    locationSuggestions.classList.add('hidden');
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
        <button
          type='button'
          class='location-suggestion ${index === activeSuggestionIndex ? 'is-active' : ''}'
          data-index='${index}'
        >
          <span class='location-suggestion-city'>${esc(item.display)}</span>
          <span class='location-suggestion-meta'>${esc(
            `${formatCoordinates(item.latitude, item.longitude)} · ${item.timezone}`
          )}</span>
        </button>
      `
      )
      .join('');
    locationSuggestions.classList.remove('hidden');
  };

  const updateActiveSuggestion = (nextIndex) => {
    const suggestionButtons = [...locationSuggestions.querySelectorAll('.location-suggestion')];
    if (!suggestionButtons.length) {
      activeSuggestionIndex = -1;
      return;
    }
    const max = suggestionButtons.length - 1;
    if (nextIndex < 0) {
      activeSuggestionIndex = max;
    } else if (nextIndex > max) {
      activeSuggestionIndex = 0;
    } else {
      activeSuggestionIndex = nextIndex;
    }
    suggestionButtons.forEach((button) => button.classList.remove('is-active'));
    const activeButton = suggestionButtons[activeSuggestionIndex];
    if (activeButton) {
      activeButton.classList.add('is-active');
      activeButton.scrollIntoView({ block: 'nearest' });
    }
  };

  const cancelSuggestionLookup = () => {
    clearTimeout(suggestDebounce);
    suggestDebounce = null;
    if (suggestRequest) {
      suggestRequest.abort();
      suggestRequest = null;
    }
  };

  const applySuggestionAtIndex = (indexValue) => {
    const selected = latestSuggestions[indexValue];
    if (!selected) {
      return;
    }
    // A lookup still pending must not reopen the list or replace the chosen city's status.
    cancelSuggestionLookup();
    // Kept whole: the chart is computed for these coordinates, since names repeat.
    resolvedLocation = selected;
    locationInput.value = selected.display;
    createChartBtn.disabled = false;
    hideSuggestions();
    setLocationStatus(
      t('selected_city', {
        city: selected.city,
        coordinates: formatCoordinates(selected.latitude, selected.longitude),
        timezone: selected.timezone,
      }),
      'is-found'
    );
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
      showSuggestions(data.suggestions || []);
      setLocationStatus(t('pick_city'), '');
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

    const fourPillarsPayload = {
      date: form.date.value,
      time: form.time.value,
      // The picked place itself: sending its name would resolve to the first place so named.
      location: {
        timezone: resolvedLocation.timezone,
        latitude: resolvedLocation.latitude,
        longitude: resolvedLocation.longitude,
      },
      include_chart: true,
      include_hidden_stems: true,
      include_ten_gods: true,
      include_interactions: true,
      include_day_master_context: true,
      include_role_profile: true,
      lang: currentLanguage,
    };

    if (selectedMode === 'evolution') {
      const query = new URLSearchParams({
        date: String(fourPillarsPayload.date || ''),
        time: String(fourPillarsPayload.time || ''),
        latitude: String(resolvedLocation.latitude),
        longitude: String(resolvedLocation.longitude),
        timezone: resolvedLocation.timezone,
        lang: currentLanguage,
      });
      window.location.assign(`/explorer/?${query.toString()}`);
      return;
    }

    setPending(true);
    try {
      const pillarsRes = await fetch('/api/four_pillars', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fourPillarsPayload),
      });
      const pillarsData = await pillarsRes.json();
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

      chartData.header = `${chartData.header} · ${resolvedLocation.city}`;

      renderChart(chartData);
      populateTenGods(tenGodsData);
      if (!pillarsData.hidden_stems) throw new Error(t('context_error'));
      populateHiddenStems(pillarsData.hidden_stems);
      relationships.render(pillarsData.interactions, chartData, tenGodsData);
      dayMasterContext.render(pillarsData.day_master_context, chartData, tenGodsData, pillarsData.hidden_stems, pillarsData.role_profile);
      syncTenGodsToggle();
      inputView.classList.add('hidden');
      chartView.classList.remove('hidden');
    } catch (err) {
      console.error(err);
      setFormError(err.message || t('chart_create_error'));
    } finally {
      setPending(false);
    }
  });

  // The picked place is kept, so another chart for it only needs a new date or time.
  backBtn.addEventListener('click', () => {
    relationships.clear();
    dayMasterContext.clear();
    chartView.classList.add('hidden');
    inputView.classList.remove('hidden');
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

  const relationships = window.EC_RELATIONSHIPS.create({
    root: chartView, translate: requiredTranslation, escape: esc,
    beforeSelect: () => dayMasterContext.clear(),
  });
  const dayMasterContext = window.EC_DAY_MASTER_CONTEXT.create({
    root: chartView, translate: requiredTranslation, escape: esc,
    beforeSelect: () => relationships.clear(),
  });
  const tenGodsToggle = document.getElementById('ten-gods-toggle');
  const syncTenGodsToggle = () => {
    const cards = [...document.querySelectorAll('#pillars .card')];
    const flippedCount = cards.filter((card) => card.classList.contains('is-flipped')).length;
    const allFlipped = cards.length > 0 && flippedCount === cards.length;
    tenGodsToggle.setAttribute('aria-pressed', allFlipped ? 'true' : flippedCount ? 'mixed' : 'false');
    tenGodsToggle.textContent = requiredTranslation(allFlipped ? 'hide_ten_gods' : 'show_ten_gods');
  };
  tenGodsToggle.addEventListener('click', () => {
    const cards = [...document.querySelectorAll('#pillars .card')];
    const show = !cards.every((card) => card.classList.contains('is-flipped'));
    cards.forEach((card) => {
      if (card.classList.contains('is-flipped') !== show) flipCard(card);
    });
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

  const expandPanel = (panel, branchCard) => {
    branchCard.classList.add('is-expanded');
    panel.classList.add('is-expanded');
    panel.style.height = panel.scrollHeight + 'px';
  };

  const collapsePanel = (panel, branchCard) => {
    panel.style.height = panel.scrollHeight + 'px';
    panel.offsetHeight; // force reflow
    panel.classList.remove('is-expanded');
    branchCard.classList.remove('is-expanded');
    panel.style.height = '0';
  };

  // ── Cards: long press flips to ten gods, quick click toggles hidden stems ──

  const pillarsContainer = document.getElementById('pillars');
  const LONG_PRESS_MS = 1000;
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

  // The facing side sizes the card, so a taller back grows the card as it turns.
  const flipCard = (card) => {
    const inner = card.querySelector('.card-inner');
    inner.getAnimations().forEach((animation) => animation.cancel());
    card.classList.remove('is-turning');
    const fromHeight = inner.getBoundingClientRect().height;
    const flipped = card.classList.toggle('is-flipped');
    syncTenGodsToggle();
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
  });

  languageButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const selectedLang = button.dataset.lang === 'en' ? 'en' : 'fi';
      currentLanguage = i18n.setLanguage(selectedLang);
      applyLanguage();
    });
  });

  modeButtons.forEach((button) => {
    button.addEventListener('click', () => {
      selectedMode = button.dataset.mode === 'evolution' ? 'evolution' : 'standard';
      applyModeSelection();
    });
  });

  applyLanguage();
  applyModeSelection();
});


function renderChart(data) {
  // Header
  document.getElementById('chart-date').textContent = data.header;

  // Pillars
  const container = document.getElementById('pillars');
  container.innerHTML = '';

  const pillarKeys = ['hour', 'day', 'month', 'year'];
  const expandHint = `<svg class='branch-expand-hint' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'></polyline></svg>`;

  data.pillars.forEach((p, i) => {
    const pillar = document.createElement('div');
    pillar.className = 'pillar';
    pillar.style.animationDelay = [0.5, 0.35, 0.2, 0.05][i] + 's';

    pillar.innerHTML = `
      <div class='pillar-header'>
        <div class='pillar-label'>${esc(p.label)}</div>
        <div class='pillar-value'>${esc(p.value)}</div>
      </div>
      <div class='pillar-cards'>
        <div class='card ${p.stem.element} stem' data-pillar='${pillarKeys[i]}' data-char='${esc(p.stem.char)}'>
          <div class='card-inner'>
            <div class='card-face card-front'>
              <div class='gua'>${renderLines(p.stem.lines)}</div>
              <div class='element-name'>${esc(p.stem.label)}</div>
            </div>
            <div class='card-face card-back'>
              <div class='ten-god-name'></div>
            </div>
          </div>
        </div>
        <div class='card ${p.branch.element} branch' data-pillar='${pillarKeys[i]}' data-char='${esc(p.branch.char)}'>
          <div class='card-inner'>
            <div class='card-face card-front'>
              <div class='gua'>${renderLines(p.branch.lines)}</div>
              <div class='animal-name'>${esc(p.branch.animal_fi)}</div>
              <div class='animal-element'>${esc(p.branch.element_label)}</div>
              ${expandHint}
            </div>
            <div class='card-face card-back'>
              <div class='ten-god-list'></div>
              ${expandHint}
            </div>
          </div>
        </div>
        <div class='hidden-stems-panel ${p.branch.element}' data-pillar='${pillarKeys[i]}'>
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
