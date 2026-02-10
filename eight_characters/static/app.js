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
  const locationInput = document.getElementById('location');
  const locationSuggestions = document.getElementById('location-suggestions');
  const locationStatus = document.getElementById('location-status');
  const languageButtons = [...document.querySelectorAll('.lang-btn')];
  if (
    !inputView ||
    !chartView ||
    !form ||
    !backBtn ||
    !createChartBtn ||
    !locationInput ||
    !locationSuggestions ||
    !locationStatus
  ) {
    return;
  }

  let resolvedLocation = null;
  let suggestDebounce = null;
  let latestSuggestions = [];
  let activeSuggestionIndex = -1;
  let currentLanguage = i18n.getLanguage();
  const t = (key, vars = {}) => i18n.t(key, vars, currentLanguage);

  const setLocationStatus = (text, state) => {
    locationStatus.textContent = text || '';
    locationStatus.classList.remove('is-found', 'is-error');
    if (state) {
      locationStatus.classList.add(state);
    }
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
          <span class='location-suggestion-meta'>${esc(item.timezone)}</span>
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

  const applySuggestionAtIndex = (indexValue) => {
    const selected = latestSuggestions[indexValue];
    if (!selected) {
      return;
    }
    resolvedLocation = {
      city: selected.city || '',
      country: selected.country || '',
      timezone: selected.timezone || '',
    };
    locationInput.value = selected.display || `${resolvedLocation.city}, ${resolvedLocation.country}`;
    locationInput.readOnly = true;
    locationInput.classList.add('location-locked');
    createChartBtn.disabled = false;
    hideSuggestions();
    setLocationStatus(
      t('selected_city', { city: resolvedLocation.city, timezone: resolvedLocation.timezone }),
      'is-found'
    );
  };

  const clearResolvedLocation = () => {
    resolvedLocation = null;
    createChartBtn.disabled = true;
    locationInput.readOnly = false;
    locationInput.classList.remove('location-locked');
    hideSuggestions();
    setLocationStatus('', '');
  };

  locationInput.addEventListener('input', async () => {
    if (resolvedLocation) {
      clearResolvedLocation();
    }
    const cityQuery = locationInput.value.trim();
    if (!cityQuery) {
      hideSuggestions();
      setLocationStatus('', '');
      return;
    }
    if (suggestDebounce) {
      clearTimeout(suggestDebounce);
    }
    suggestDebounce = setTimeout(async () => {
      try {
        const res = await fetch('/api/location_suggest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: cityQuery, limit: 8 }),
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || t('suggest_error'));
        }
        showSuggestions(data.suggestions || []);
        setLocationStatus(t('pick_city'), '');
      } catch (err) {
        hideSuggestions();
        setLocationStatus(err.message || t('suggest_error'), 'is-error');
      }
    }, 180);
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

    if (!resolvedLocation) {
      setLocationStatus(t('need_location'), 'is-error');
      createChartBtn.disabled = true;
      return;
    }

    const fourPillarsPayload = {
      date: form.date.value,
      time: form.time.value,
      city: `${resolvedLocation.city}, ${resolvedLocation.country}`,
    };

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

      const pillars = pillarsData.four_pillars;
      const chartPayload = {
        date: form.date.value,
        time: form.time.value,
        hour_stem: pillars.hour.stem.chinese,
        hour_branch: pillars.hour.branch.chinese,
        day_stem: pillars.day.stem.chinese,
        day_branch: pillars.day.branch.chinese,
        month_stem: pillars.month.stem.chinese,
        month_branch: pillars.month.branch.chinese,
        year_stem: pillars.year.stem.chinese,
        year_branch: pillars.year.branch.chinese,
        lang: currentLanguage,
      };

      const chartRes = await fetch('/api/chart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(chartPayload),
      });
      const chartData = await chartRes.json();
      if (!chartRes.ok || chartData.error) {
        throw new Error(chartData.error || t('chart_error'));
      }

      if (pillarsData.resolved_location) {
        chartData.header = `${chartData.header} · ${pillarsData.resolved_location.city}`;
      }

      renderChart(chartData);
      inputView.classList.add('hidden');
      chartView.classList.remove('hidden');
    } catch (err) {
      console.error(err);
      setLocationStatus(err.message || t('chart_create_error'), 'is-error');
    }
  });

  backBtn.addEventListener('click', () => {
    clearResolvedLocation();
    chartView.classList.add('hidden');
    inputView.classList.remove('hidden');
  });

  languageButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const selectedLang = button.dataset.lang === 'en' ? 'en' : 'fi';
      currentLanguage = i18n.setLanguage(selectedLang);
      applyLanguage();
    });
  });

  applyLanguage();
});


function renderChart(data) {
  // Header
  document.getElementById('chart-date').textContent = data.header;

  // Pillars
  const container = document.getElementById('pillars');
  container.innerHTML = '';

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
        <div class='card ${p.stem.element} stem'>
          <div class='gua'>${renderLines(p.stem.lines)}</div>
          <div class='element-name'>${esc(p.stem.label)}</div>
        </div>
        <div class='card ${p.branch.element} branch'>
          <div class='gua'>${renderLines(p.branch.lines)}</div>
          <div class='animal-name'>${esc(p.branch.animal_fi)}</div>
          <div class='animal-element'>${esc(p.branch.element_label)}</div>
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
