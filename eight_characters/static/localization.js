(() => {
  const dictionaries = {
    fi: {
      relationships: 'Yhteydet',
      show_ten_gods: 'Näytä kymmenen jumalaa',
      hide_ten_gods: 'Näytä merkit',
      interactions_error: 'Kartan yhteyksien lukeminen epäonnistui.',
      pillar_year: 'Vuosi',
      pillar_month: 'Kuukausi',
      pillar_day: 'Päivä',
      pillar_hour: 'Tunti',
      relationship_stem_combination: 'Runkojen yhdistelmä',
      relationship_branch_combination: 'Haarojen yhdistelmä',
      relationship_branch_clash: 'Haarojen törmäys',
      relationship_harmony_frame: 'Kolmen haaran harmonia',
      relationship_empty: 'Ei yhdistelmiä, törmäyksiä tai täysiä kolmen haaran harmonioita.',
      relationship_adjacent: 'Vierekkäiset pilarit',
      relationship_non_adjacent: 'Pilarit eivät ole vierekkäin',
      relationship_potential_element: 'Mahdollinen elementti: {element}',
      relationship_clear: 'Poista valinta',
      relationship_selected: 'Korostettu: {relationship}.',
      relationship_combination_note: 'Yhdistelmä havaittu. Muuntumista ei ole arvioitu.',
      relationship_frame_note: 'Täysi kolmen haaran harmonia havaittu. Muuntumista ei ole arvioitu.',
      relationship_clash_note: 'Törmäyspari havaittu. Voimakkuutta tai vaikutuksia ei ole arvioitu.',
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
      ten_gods_error: 'Kymmenen jumalan laskenta epäonnistui.',
      element_wood: 'Puu',
      element_fire: 'Tuli',
      element_earth: 'Maa',
      element_metal: 'Metalli',
      element_water: 'Vesi',
      qi_main: 'Pää',
      qi_middle: 'Keski',
      qi_residual: 'Jäännös',
      ten_god_friend: 'Ystävä',
      ten_god_rob_wealth: 'Rikkauden ryöstäjä',
      ten_god_eating_god: 'Ruokajumala',
      ten_god_hurting_officer: 'Loukkaava virkamies',
      ten_god_indirect_wealth: 'Epäsuora rikkaus',
      ten_god_direct_wealth: 'Suora rikkaus',
      ten_god_seven_killings: 'Seitsemän surmaa',
      ten_god_direct_officer: 'Suora virkamies',
      ten_god_indirect_resource: 'Epäsuora voimavara',
      ten_god_direct_resource: 'Suora voimavara',
      ten_god_day_master: 'Päivän mestari',
      lang_fi: 'FI',
      lang_en: 'EN',
    },
    en: {
      relationships: 'Relationships',
      show_ten_gods: 'Show Ten Gods',
      hide_ten_gods: 'Show characters',
      interactions_error: 'Could not read chart relationships.',
      pillar_year: 'Year',
      pillar_month: 'Month',
      pillar_day: 'Day',
      pillar_hour: 'Hour',
      relationship_stem_combination: 'Stem combination',
      relationship_branch_combination: 'Branch combination',
      relationship_branch_clash: 'Branch clash',
      relationship_harmony_frame: 'Three-harmony frame',
      relationship_empty: 'No combinations, clashes or complete harmony frames.',
      relationship_adjacent: 'Adjacent pillars',
      relationship_non_adjacent: 'Non-adjacent pillars',
      relationship_potential_element: 'Potential element: {element}',
      relationship_clear: 'Clear',
      relationship_selected: 'Highlighted: {relationship}.',
      relationship_combination_note: 'Combination present. Transformation has not been assessed.',
      relationship_frame_note: 'Complete frame present. Transformation has not been assessed.',
      relationship_clash_note: 'Clash pair present. Strength and effects have not been assessed.',
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
      ten_gods_error: 'Ten gods calculation failed.',
      element_wood: 'Wood',
      element_fire: 'Fire',
      element_earth: 'Earth',
      element_metal: 'Metal',
      element_water: 'Water',
      qi_main: 'Main',
      qi_middle: 'Mid',
      qi_residual: 'Residual',
      ten_god_friend: 'Friend',
      ten_god_rob_wealth: 'Rob Wealth',
      ten_god_eating_god: 'Eating God',
      ten_god_hurting_officer: 'Hurting Officer',
      ten_god_indirect_wealth: 'Indirect Wealth',
      ten_god_direct_wealth: 'Direct Wealth',
      ten_god_seven_killings: 'Seven Killings',
      ten_god_direct_officer: 'Direct Officer',
      ten_god_indirect_resource: 'Indirect Resource',
      ten_god_direct_resource: 'Direct Resource',
      ten_god_day_master: 'Day Master',
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
