(() => {
  const dictionaries = {
    fi: {
      heading: 'Neljä pilaria',
      title: 'Kahdeksan merkkiä',
      label_date: 'Syntymäpäivä',
      label_time: 'Kellonaika',
      label_location: 'Syntymäpaikka',
      placeholder_city: 'Kaupunki',
      create_chart: 'Luo kartta',
      back: '← Takaisin',
      pick_city: 'Valitse kaupunki listasta.',
      selected_city: '{city} ({timezone}) valittu',
      need_location: 'Valitse ensin kaupunki listasta.',
      suggest_error: 'Sijainnin haku epaonnistui.',
      pillars_error: 'Pilarien laskenta epaonnistui.',
      chart_error: 'Kartan renderointi epaonnistui.',
      chart_create_error: 'Virhe kartan luomisessa.',
      element_wood: 'Puu',
      element_fire: 'Tuli',
      element_earth: 'Maa',
      element_metal: 'Metalli',
      element_water: 'Vesi',
      qi_main: 'Pää',
      qi_middle: 'Keski',
      qi_residual: 'Jäännös',
      lang_fi: 'FI',
      lang_en: 'EN',
    },
    en: {
      heading: 'Four pillars',
      title: 'Eight characters',
      label_date: 'Birth date',
      label_time: 'Time',
      label_location: 'Birth place',
      placeholder_city: 'City',
      create_chart: 'Create chart',
      back: '← Back',
      pick_city: 'Select a city from the list.',
      selected_city: '{city} ({timezone}) selected',
      need_location: 'Select a city from the list first.',
      suggest_error: 'Location search failed.',
      pillars_error: 'Pillar calculation failed.',
      chart_error: 'Chart rendering failed.',
      chart_create_error: 'Failed to create chart.',
      element_wood: 'Wood',
      element_fire: 'Fire',
      element_earth: 'Earth',
      element_metal: 'Metal',
      element_water: 'Water',
      qi_main: 'Main',
      qi_middle: 'Mid',
      qi_residual: 'Residual',
      lang_fi: 'FI',
      lang_en: 'EN',
    },
  };

  const fallback = 'fi';

  const normalizeLanguage = (value) => (value === 'en' ? 'en' : 'fi');

  const getLanguage = () => {
    const saved = localStorage.getItem('eight_characters_lang');
    if (saved) {
      return normalizeLanguage(saved);
    }
    const browser = (navigator.language || '').toLowerCase();
    return browser.startsWith('en') ? 'en' : fallback;
  };

  const setLanguage = (lang) => {
    const normalized = normalizeLanguage(lang);
    localStorage.setItem('eight_characters_lang', normalized);
    return normalized;
  };

  const t = (key, vars = {}, lang = getLanguage()) => {
    const activeLang = normalizeLanguage(lang);
    const source = dictionaries[activeLang] || dictionaries[fallback];
    const template = source[key] || dictionaries[fallback][key] || key;
    return template.replace(/\{(\w+)\}/g, (_, token) => String(vars[token] ?? ''));
  };

  window.EC_I18N = {
    dictionaries,
    getLanguage,
    setLanguage,
    t,
  };
})();
