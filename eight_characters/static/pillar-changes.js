// When each pillar last changed before the birth and when it next changes. A pillar
// close to a change is marked; every pillar's exact changes open on demand.
(() => {
  const ORDER = ['hour', 'day', 'month', 'year'];
  // A pillar at most this far from a change is marked (decided for #17).
  const MARK_WINDOW_SECONDS = 30 * 60;
  const STEMS = '甲乙丙丁戊己庚辛壬癸';
  const BRANCHES = '子丑寅卯辰巳午未申酉戌亥';
  // The engine names a change's far-side pillar by its characters. These are their
  // names, as in eight_characters/data.py; a unit test keeps the two the same.
  const PINYIN = {
    甲: 'Jia', 乙: 'Yi', 丙: 'Bing', 丁: 'Ding', 戊: 'Wu', 己: 'Ji', 庚: 'Geng', 辛: 'Xin', 壬: 'Ren', 癸: 'Gui',
    子: 'Zi', 丑: 'Chou', 寅: 'Yin', 卯: 'Mao', 辰: 'Chen', 巳: 'Si', 午: 'Wu', 未: 'Wei', 申: 'Shen', 酉: 'You',
    戌: 'Xu', 亥: 'Hai',
  };
  const TERMS = {
    lichun_315: 'Lichun', jingzhe_345: 'Jingzhe', qingming_15: 'Qingming', lixia_45: 'Lixia',
    mangzhong_75: 'Mangzhong', xiaoshu_105: 'Xiaoshu', liqiu_135: 'Liqiu', bailu_165: 'Bailu',
    hanlu_195: 'Hanlu', lidong_225: 'Lidong', daxue_255: 'Daxue', xiaohan_285: 'Xiaohan',
  };
  const CLOCKS = ['true_solar', 'civil'];

  const create = ({ root, translate: t, escape: esc, format, beforeSelect }) => {
    const detail = root.querySelector('#pillar-detail');
    const status = root.querySelector('#pillar-status');
    if (!detail || !status) throw new Error('Pillar change view is incomplete.');
    let entries = {};
    let readings = {};
    let selected = null;

    const fail = () => { throw new Error(t('changes_error')); };

    const readPillar = (pillar) => {
      const stem = pillar?.stem?.chinese;
      const branch = pillar?.branch?.chinese;
      if (typeof stem !== 'string' || typeof branch !== 'string' || stem.length !== 1 || branch.length !== 1
        || !STEMS.includes(stem) || !BRANCHES.includes(branch)) fail();
      return { chars: stem + branch, names: `${PINYIN[stem]} ${PINYIN[branch]}` };
    };

    const readChange = (name, change) => {
      if (!change || typeof change.seconds !== 'number' || !Number.isFinite(change.seconds) || change.seconds < 0) fail();
      const far = readPillar(change.pillar);
      if (name === 'year' || name === 'month') {
        if (!Object.hasOwn(TERMS, change.term) || 'clock' in change || 'clock_time' in change) fail();
        return { seconds: change.seconds, far, term: TERMS[change.term] };
      }
      const reading = typeof change.clock_time === 'string' ? format.parseWallClock(change.clock_time) : null;
      if (!CLOCKS.includes(change.clock) || !reading || 'term' in change) fail();
      return { seconds: change.seconds, far, clock: change.clock, reading };
    };

    // True solar time runs within a minute a day of real time, so a change on it must
    // lie where its reading says.
    const consistent = (entry, birthTrueSolar) => ['previous', 'next'].every((side) => {
      const change = entry[side];
      if (change.clock !== 'true_solar') return true;
      const elapsed = (change.reading - birthTrueSolar) / 1000;
      return Math.abs(elapsed - (side === 'previous' ? -change.seconds : change.seconds)) < 120;
    });

    const identity = (pillar) => `${pillar.chars} ${pillar.names}`;

    const whereText = (change) => {
      if (change.term) return t('pillar_change_term', { term: change.term });
      const time = format.time(change.reading, change.reading.getUTCSeconds() !== 0);
      const sameDay = change.reading.toISOString().slice(0, 10) === readings[change.clock].toISOString().slice(0, 10);
      const when = sameDay ? t('at_time', { time }) : t('date_and_time', { date: format.date(change.reading), time });
      return t(change.clock === 'true_solar' ? 'pillar_change_clock_true_solar' : 'pillar_change_clock_civil', { when });
    };

    const sideMarkup = (entry, side) => {
      const change = entry[side];
      const [before, after] = side === 'previous' ? [change.far, entry.natal] : [entry.natal, change.far];
      // The arrow is drawn: the page fonts have no arrow glyphs.
      const pillars = `<span>${esc(identity(before))}</span> <span class="pillar-change-arrow">`
        + `<span class="sr-only">${esc(t('pillar_change_then'))}</span></span> <span>${esc(identity(after))}</span>`;
      const distance = t(side === 'previous' ? 'pillar_change_ago' : 'pillar_change_in',
        { duration: format.duration(change.seconds, true) });
      return `
        <div class="pillar-change">
          <div class="pillar-change-side">${esc(t(side === 'previous' ? 'pillar_change_previous' : 'pillar_change_next'))}</div>
          <div class="pillar-change-distance">${esc(distance)}</div>
          <div class="pillar-change-where">${esc(whereText(change))}</div>
          <div class="pillar-change-pillars">${pillars}</div>
        </div>`;
    };

    const titleFor = (name) => t('pillar_changes_title', { pillar: entries[name].label, identity: identity(entries[name].natal) });

    const buttonFor = (name) => root.querySelector(`.pillar-identity[data-pillar="${name}"]`);

    const clear = () => {
      selected = null;
      root.querySelectorAll('.pillar-identity').forEach((button) => button.setAttribute('aria-expanded', 'false'));
      detail.classList.add('hidden');
      detail.innerHTML = '';
      status.textContent = '';
    };

    const select = (name) => {
      const wasSelected = selected === name;
      clear();
      if (wasSelected) return;
      beforeSelect();
      selected = name;
      const entry = entries[name];
      buttonFor(name).setAttribute('aria-expanded', 'true');
      const notes = [t('pillar_changes_note')];
      if (name === 'year' || name === 'month') notes.push(t('pillar_changes_term_note'));
      detail.innerHTML = `
        <div class="relationship-detail-heading">
          <h3 id="pillar-detail-title">${esc(titleFor(name))}</h3>
          <button type="button" class="reading-toggle" data-clear-pillar>${esc(t('pillar_changes_close'))}</button>
        </div>
        <div class="pillar-change-sides">
          ${sideMarkup(entry, 'previous')}
          ${sideMarkup(entry, 'next')}
        </div>
        <p class="relationship-note">${esc(notes.join(' '))}</p>`;
      detail.classList.remove('hidden');
      status.textContent = t('pillar_changes_selected', { pillar: titleFor(name) });
    };

    root.addEventListener('click', (event) => {
      const button = event.target.closest('.pillar-identity');
      if (!button) return;
      if (!Object.hasOwn(entries, button.dataset.pillar)) throw new Error('Unknown pillar selection.');
      select(button.dataset.pillar);
    });
    const clearAndReturnFocus = () => {
      const button = selected ? buttonFor(selected) : null;
      clear();
      if (button) button.focus();
    };
    detail.addEventListener('click', (event) => {
      if (event.target.closest('[data-clear-pillar]')) clearAndReturnFocus();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && selected !== null) {
        event.preventDefault();
        clearAndReturnFocus();
      }
    });

    // `birthReadings` holds the birth on each clock: `civil` as entered, `true_solar` as computed.
    const render = (fourPillars, chartData, birthReadings) => {
      clear();
      entries = {};
      if (!fourPillars || !Array.isArray(chartData.pillars) || chartData.pillars.length !== ORDER.length) fail();
      const next = {};
      ORDER.forEach((name, index) => {
        const chartPillar = chartData.pillars[index];
        const natal = readPillar(fourPillars[name]);
        // The chart's characters and names must be the engine's own.
        if (`${chartPillar.stem.char}${chartPillar.branch.char}` !== natal.chars
          || `${chartPillar.stem.pinyin} ${chartPillar.branch.pinyin}` !== natal.names) fail();
        const changes = fourPillars[name].changes;
        const entry = {
          label: chartPillar.label,
          natal,
          previous: readChange(name, changes?.previous),
          next: readChange(name, changes?.next),
        };
        if (entry.previous.far.chars === natal.chars || entry.next.far.chars === natal.chars
          || !consistent(entry, birthReadings.true_solar)) fail();
        next[name] = entry;
      });
      entries = next;
      readings = birthReadings;
      ORDER.forEach((name) => {
        const pillar = root.querySelector(`.pillar[data-pillar="${name}"]`);
        const mark = pillar?.querySelector('.pillar-mark');
        if (!mark || !buttonFor(name)) throw new Error('Pillar change view is incomplete.');
        const entry = entries[name];
        const near = ['previous', 'next']
          .filter((side) => entry[side].seconds <= MARK_WINDOW_SECONDS)
          .sort((a, b) => entry[a].seconds - entry[b].seconds)[0];
        mark.textContent = near
          ? t(near === 'previous' ? 'pillar_mark_previous' : 'pillar_mark_next',
            { duration: format.duration(entry[near].seconds) })
          : '';
        pillar.classList.toggle('is-near-change', Boolean(near));
      });
    };

    return { render, clear };
  };

  window.EC_PILLAR_CHANGES = { create };
})();
