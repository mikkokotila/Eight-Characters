// A place search: a field whose suggestions hang from it as a listbox, looked up as the
// reader types (POST /api/location_suggest) and chosen by a press, or by the arrow keys
// and Enter. Settings' place uses it, and so does Today's question for where you are.
// Only the lookup for the text in the field is shown; a failed one says why, under it.
(() => {
  const create = ({ input, list, status, optionId, translate: t, escape: esc, format, onType, onPick }) => {
    if (!input || !list || !status) throw new Error('A place search needs its field, its list and its status.');
    let found = [];
    let active = -1;
    let lookup = null;
    let debounce = null;
    // A place's coordinates and time zone, as its suggestion and Settings write them.
    const coordinates = (place) => `${format.coordinates(place.latitude, place.longitude)} · ${place.timezone}`;
    const closeList = () => {
      found = [];
      active = -1;
      list.innerHTML = '';
      list.classList.add('hidden');
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
    };
    const setStatus = (text, kind = '') => {
      status.textContent = text;
      status.className = `field-status${kind ? ` ${kind}` : ''}`;
    };
    const pick = (place) => {
      clearTimeout(debounce);
      lookup?.abort();
      input.value = place.display;
      closeList();
      setStatus(t('selected_city', { city: place.city, coordinates: format.coordinates(place.latitude, place.longitude), timezone: place.timezone }), 'is-found');
      onPick(place);
    };
    const showList = (items) => {
      found = items;
      active = -1;
      if (!items.length) {
        closeList();
        return;
      }
      list.innerHTML = items.map((item, index) => `
        <div role="option" id="${optionId}-${index}" class="location-suggestion" aria-selected="false" data-index="${index}">
          <span class="location-suggestion-city">${esc(item.display)}</span>
          <span class="location-suggestion-meta">${esc(coordinates(item))}</span>
        </div>`).join('');
      list.classList.remove('hidden');
      input.setAttribute('aria-expanded', 'true');
    };
    const activate = (index) => {
      const options = [...list.querySelectorAll('.location-suggestion')];
      if (!options.length) return;
      active = (index + options.length) % options.length;
      options.forEach((option, i) => {
        option.classList.toggle('is-active', i === active);
        option.setAttribute('aria-selected', String(i === active));
      });
      input.setAttribute('aria-activedescendant', options[active].id);
      options[active].scrollIntoView({ block: 'nearest' });
    };
    input.addEventListener('input', () => {
      onType();
      clearTimeout(debounce);
      lookup?.abort();
      closeList();
      const query = input.value.trim();
      setStatus('');
      if (!query) return;
      debounce = setTimeout(async () => {
        const request = new AbortController();
        lookup = request;
        // Only the lookup for the text in the field may be shown.
        const stale = () => request.signal.aborted || input.value.trim() !== query;
        try {
          const response = await fetch('/api/location_suggest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, limit: 8 }),
            signal: request.signal,
          });
          const data = await response.json();
          if (stale()) return;
          if (!response.ok) throw new Error(data.detail || t('suggest_error'));
          if (!Array.isArray(data.suggestions)) throw new Error(t('suggest_error'));
          showList(data.suggestions);
          setStatus(t(data.suggestions.length ? 'pick_city' : 'no_places'));
        } catch (err) {
          if (stale()) return;
          closeList();
          setStatus(err.message || t('suggest_error'), 'is-error');
        }
      }, 180);
    });
    input.addEventListener('keydown', (event) => {
      if (list.classList.contains('hidden')) return;
      if (event.key === 'ArrowDown') activate(active + 1);
      else if (event.key === 'ArrowUp') activate(active - 1);
      else if (event.key === 'Enter') pick(found[active >= 0 ? active : 0]);
      else if (event.key === 'Escape') closeList();
      else return;
      event.preventDefault();
    });
    list.addEventListener('mousedown', (event) => event.preventDefault());
    list.addEventListener('click', (event) => {
      const option = event.target.closest('.location-suggestion');
      if (option) pick(found[Number(option.dataset.index)]);
    });
    input.addEventListener('blur', () => closeList());
    // Any lookup on its way is dropped, and the field, its list and its status emptied.
    const reset = () => {
      clearTimeout(debounce);
      lookup?.abort();
      input.value = '';
      setStatus('');
      closeList();
    };
    return { coordinates, setStatus, close: closeList, reset };
  };

  window.EC_PLACE_SEARCH = { create };
})();
