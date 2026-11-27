// The first chart (docs/Standard-First-Chart.md): what a birth settles without an
// account, or without its time, from POST /api/first_chart (first_chart.py). Its
// pillars as the chart lays them out, hour to year, each a stem card over its branch
// card as the day's cards are drawn; the hour left open without a time, and said so;
// each pillar that changes during a day whose time is unknown, with both its sides and
// when; and the Day Master, with the canon's core passage. A visitor is offered the
// whole chart with a free account.
(() => {
  const ORDER = ['hour', 'day', 'month', 'year'];
  const ELEMENTS = ['wood', 'fire', 'earth', 'metal', 'water'];
  const POLARITIES = ['Yang', 'Yin'];
  const SIGNS = ['Rat', 'Ox', 'Tiger', 'Rabbit', 'Dragon', 'Snake', 'Horse', 'Goat', 'Monkey', 'Rooster', 'Dog', 'Pig'];
  // A change's moment on the place's clock, to the second, with its offset from UTC.
  const AT = /^(\d{2}:\d{2}:\d{2})([+-]\d{2}:\d{2})$/;

  const create = ({ view, translate: t, escape: esc, onEdit, onNew, onAccount }) => {
    const heading = view.querySelector('#first-birth');
    const lead = view.querySelector('#first-lead');
    const pillars = view.querySelector('#first-pillars');
    const changes = view.querySelector('#first-changes');
    const master = view.querySelector('#first-day-master');
    const masterTitle = view.querySelector('#first-day-master-title');
    const masterNote = view.querySelector('#first-day-master-note');
    const passage = view.querySelector('#first-passage');
    const offer = view.querySelector('#first-offer');
    const offerText = view.querySelector('#first-offer-text');
    const editButton = view.querySelector('#first-edit');
    const newButton = view.querySelector('#first-new');
    const accountButton = view.querySelector('#first-account');
    if (![heading, lead, pillars, changes, master, masterTitle, masterNote, passage, offer, offerText, editButton, newButton, accountButton]
      .every(Boolean) || typeof onEdit !== 'function' || typeof onNew !== 'function' || typeof onAccount !== 'function') {
      throw new Error('The first chart is incomplete.');
    }
    const canon = window.EC_READINGS.reader({ panel: passage, escape: esc, subject: 'The first chart’s' });

    // ── The answer, read whole: a part missing or unknown fails, never half a chart ──
    const fail = (what) => { throw new Error(`The first chart’s answer has no valid ${what}.`); };
    const glyph = (value, part, where) => {
      if (typeof value?.chinese !== 'string' || !value.chinese || typeof value.pinyin !== 'string' || !value.pinyin
        || !ELEMENTS.includes(value.element) || !POLARITIES.includes(value.polarity)
        || (part === 'branch' && !SIGNS.includes(value.sign))) fail(`${where} ${part}`);
      return value;
    };
    const pillarOf = (value, where) => ({ stem: glyph(value?.stem, 'stem', where), branch: glyph(value?.branch, 'branch', where) });
    const read = (payload, timed) => {
      const names = timed ? ORDER : ORDER.filter((name) => name !== 'hour');
      if (typeof payload?.pillars !== 'object' || payload.pillars === null) fail('pillars');
      const unknown = Object.keys(payload.pillars).filter((name) => !names.includes(name));
      if (unknown.length) fail(`pillar ${unknown[0]}`);
      const chart = Object.fromEntries(names.map((name) => [name, pillarOf(payload.pillars[name], name)]));
      if (!Array.isArray(payload.changes) || (timed && payload.changes.length)) fail('changes');
      const moved = payload.changes.map((change, index) => {
        if (!names.includes(change?.pillar) || !AT.test(change.at ?? '')) fail(`change ${index}`);
        return { pillar: change.pillar, at: change.at, before: pillarOf(change.before, `change ${index}`), after: pillarOf(change.after, `change ${index}`) };
      });
      const dm = payload.day_master;
      if (!dm || dm.stem !== chart.day.stem.chinese || dm.pinyin !== chart.day.stem.pinyin || !ELEMENTS.includes(dm.element)
        || !POLARITIES.includes(dm.polarity) || typeof dm.title !== 'string' || !dm.title
        || !Array.isArray(dm.passage) || !dm.passage.length || dm.passage.some((text) => typeof text !== 'string' || !text)) {
        fail('Day Master');
      }
      return { chart, changes: moved, dayMaster: dm };
    };

    // ── Drawing ──
    const elementOf = (value) => `${value.polarity} ${t('element_' + value.element)}`;
    // A pillar by its characters, each with its pinyin: 壬辰 Ren Chen.
    const named = (pillar) => `${pillar.stem.chinese}${pillar.branch.chinese} ${pillar.stem.pinyin} ${pillar.branch.pinyin}`;
    const card = (part, value) => `<span class="today-card is-${part} ${esc(value.element)}">
        <span class="today-card-glyph glyph" lang="zh-Hant">${esc(value.chinese)}</span>
        <span class="today-card-pinyin card-pinyin">${esc(value.pinyin)}</span>
        ${part === 'stem'
          ? `<span class="element-name">${esc(elementOf(value))}</span>`
          : `<span class="animal-name">${esc(t('animal_' + value.sign.toLowerCase()))}</span><span class="animal-element">${esc(elementOf(value))}</span>`}
      </span>`;
    const column = (name, pillar, changing) => (pillar === null
      ? `<div class="first-pillar is-open" data-pillar="hour">
          <p class="first-pillar-name">${esc(t('pillar_hour'))}</p>
          <p class="first-pillar-chars">${esc(t('first_hour_open'))}</p>
          <span class="today-cards is-large is-pending" aria-hidden="true"><span class="today-card is-stem"></span><span class="today-card is-branch"></span></span>
          <p class="first-pillar-note">${esc(t('first_hour_note'))}</p>
        </div>`
      : `<div class="first-pillar" data-pillar="${name}">
          <p class="first-pillar-name">${esc(t('pillar_' + name))}</p>
          <p class="first-pillar-chars"><span lang="zh-Hant">${esc(pillar.stem.chinese + pillar.branch.chinese)}</span> ${esc(`${pillar.stem.pinyin} ${pillar.branch.pinyin}`)}</p>
          <span class="today-cards is-large">${card('stem', pillar.stem)}${card('branch', pillar.branch)}</span>
          ${changing ? `<p class="first-pillar-note">${esc(t('first_pillar_changes'))}</p>` : ''}
        </div>`);
    // A change on the place's clock: its time, with its offset when the clocks may repeat it.
    const clock = (at) => {
      const [, time, offset] = at.match(AT);
      return t('first_change_at', { time, offset });
    };
    const changeLine = (change, shown) => t('first_change', {
      pillar: t('pillar_' + change.pillar),
      at: clock(change.at),
      before: named(change.before),
      after: named(change.after),
      shown: named(shown),
    });

    let asking = 0;
    let visitorShown = false;
    // Shows the first chart of `link` (a chart link's birth: date, time or 'unknown',
    // place) under `title`; `visitor` offers the whole chart with an account. Resolves
    // once it is drawn, or when a later showing took its place; rejects with the API's
    // reason, or the page's, when the birth cannot be charted.
    const show = async (link, { title, visitor }) => {
      const mine = ++asking;
      const timed = link.time !== 'unknown';
      view.classList.remove('hidden');
      view.setAttribute('aria-busy', 'true');
      try {
        const where = { timezone: link.place.timezone, latitude: link.place.latitude, longitude: link.place.longitude };
        if (timed && link.fold !== null) where.fold = link.fold;
        // The link's Zi-hour convention decides when its day changes at night, as on the
        // whole chart.
        const conventions = link.zi === 'split_midnight' ? {} : { conventions: { zi_convention: link.zi } };
        const response = await fetch('/api/first_chart', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ date: link.date, ...(timed ? { time: link.time } : {}), location: where, ...conventions }),
        });
        const payload = await response.json();
        if (mine !== asking) return;
        if (!response.ok) throw new Error(typeof payload?.detail === 'string' ? payload.detail : t('first_error'));
        const { chart, changes: moved, dayMaster } = read(payload, timed);
        visitorShown = visitor;
        heading.textContent = title;
        lead.textContent = t(visitor ? (timed ? 'first_lead_visitor' : 'first_lead_visitor_unknown') : 'first_lead_unknown');
        pillars.innerHTML = ORDER.map((name) => column(name, chart[name] ?? null, moved.some((change) => change.pillar === name))).join('');
        changes.innerHTML = moved.map((change) => `<li>${esc(changeLine(change, chart[change.pillar]))}</li>`).join('');
        changes.classList.toggle('hidden', moved.length === 0);
        masterTitle.textContent = `${t('ten_god_day_master')} · ${dayMaster.pinyin} — ${elementOf(dayMaster)}`;
        // The Day Master is the day pillar's stem: when the day changes during an
        // unknown time, it holds from the change, and the other side's is named.
        const dayChange = moved.find((change) => change.pillar === 'day');
        if (dayChange) {
          const other = dayChange.after.stem.chinese === dayMaster.stem ? dayChange.before : dayChange.after;
          const holds = dayChange.after.stem.chinese === dayMaster.stem ? 'first_day_master_from' : 'first_day_master_before';
          masterNote.textContent = t(holds, {
            at: clock(dayChange.at), other: `${other.stem.pinyin} ${other.stem.chinese} — ${elementOf(other.stem)}`,
          });
        } else masterNote.textContent = '';
        masterNote.classList.toggle('hidden', !dayChange);
        passage.innerHTML = canon.lines(canon.line({
          part: 'first-core', key: dayMaster.title, paragraphs: dayMaster.passage.map((text) => ({ label: null, text })),
        }));
        // The core reads in full, as it does without an account on eightchord.com.
        const core = passage.querySelector('.canon-line-toggle');
        if (core.getAttribute('aria-expanded') !== 'true') canon.toggle(core, true);
        // Without the time, the account alone opens no more: the offer says so.
        offerText.textContent = t(timed ? 'first_offer' : 'first_offer_unknown');
        offer.classList.toggle('hidden', !visitor);
      } finally {
        if (mine === asking) view.removeAttribute('aria-busy');
      }
    };
    const hide = () => {
      asking += 1;
      visitorShown = false;
      view.classList.add('hidden');
      view.removeAttribute('aria-busy');
    };

    editButton.addEventListener('click', () => onEdit());
    newButton.addEventListener('click', () => onNew());
    accountButton.addEventListener('click', () => onAccount());

    return {
      show,
      hide,
      isShown: () => !view.classList.contains('hidden'),
      // Whether it offers the whole chart: shown to a visitor without an account.
      forVisitor: () => !view.classList.contains('hidden') && visitorShown,
    };
  };
  window.EC_FIRST = { create };
})();
