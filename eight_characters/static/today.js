// Today: what a day, its month, its year and the luck pillar in force bring to the chart
// on screen, and to a partner's (docs/Standard-Today.md). The API reckons all of it
// (POST /api/today), with the partner's chart, the place and the schools the account
// keeps (settings.js). This page draws its answer and computes nothing: the only thing
// it reads itself is the date on the clock at where you are.
(() => {
  const LAYERS = ['day', 'month', 'year', 'luck'];
  const BANDS = ['strongly_supportive', 'supportive', 'mixed', 'draining', 'strongly_draining'];
  // The fifth places the day's pillars stand in, as the relationships name them.
  const FIFTH = { daily: 'day', monthly: 'month', annual: 'year', luck: 'luck' };
  const TOPIC_PATH = /^(marriage|work|health|day|pillar\/(day|month|year|luck))$/;
  const DAY_PATH = /^\d{4}-\d{2}-\d{2}$/;
  const ELEMENTS = ['wood', 'fire', 'earth', 'metal', 'water'];

  const create = ({ view, translate: t, escape: esc, locale, settings, format, account, go, onChart, onSettings, onEdit, onLanguage, toast }) => {
    const need = (selector) => {
      const node = view.querySelector(selector);
      if (!node) throw new Error(`Today is incomplete: ${selector}.`);
      return node;
    };
    const dateHeading = need('#today-date');
    const chartLine = need('#today-chart');
    const pageSwitch = need('#today-page-switch');
    const steps = need('#today-steps');
    const nowButton = need('[data-today-now]');
    const whoSwitch = need('#today-who');
    const partnerLabel = need('.today-who-name');
    const languageSwitch = need('#today-language');
    const copyLink = need('#today-copy-link');
    const copyText = need('#today-copy-text');
    const printButton = need('#today-print');
    const settingsButton = need('#today-settings');
    const notice = need('#today-notice');
    const body = need('#today-body');
    const pullLine = need('#today-pull-line');
    const topics = need('#today-topics');
    const run = need('#today-run');
    const pillars = need('#today-pillars');
    const inChart = need('#today-in-chart');
    const hours = need('#today-hours');
    const panel = need('#today-panel');
    const detail = need('#today-detail');
    const status = need('#today-status');

    // What is shown: the chart, the day, whose day and the open topic (the address), the
    // settings it was asked with, and the API's answer. Each request is numbered: only
    // the answer to the latest is drawn.
    let state = null;
    let shownSettings = null;
    let answer = null;
    let asked = 0;

    // ── Words and numbers in the page's language ──
    const lang = () => state?.lang ?? 'fi';
    const score = (value) => new Intl.NumberFormat(locale(), {
      minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: 'exceptZero',
    }).format(value);
    const number = (value, digits = 1) => new Intl.NumberFormat(locale(), {
      minimumFractionDigits: digits, maximumFractionDigits: digits,
    }).format(value);
    const bandName = (band) => {
      if (!BANDS.includes(band)) throw new Error(t('today_answer_error'));
      return t('today_band_' + band);
    };
    const pull = (value) => `${bandName(value.band)} (${score(value.score)})`;
    // A calendar date, held as UTC midnight so that formatting never moves it.
    const calendar = (day) => new Date(`${day}T00:00:00Z`);
    const longDate = (day) => new Intl.DateTimeFormat(locale(), {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC',
    }).format(calendar(day));
    const shortDate = (day) => new Intl.DateTimeFormat(locale(), {
      weekday: 'short', day: 'numeric', month: 'numeric', timeZone: 'UTC',
    }).format(calendar(day));
    // A clock time the API gives with its offset, read as the place's clock shows it.
    const clock = (text) => {
      const match = /T(\d{2}):(\d{2})/.exec(text);
      if (!match) throw new Error(t('today_answer_error'));
      return format.time(new Date(Date.UTC(2000, 0, 1, Number(match[1]), Number(match[2]))), false);
    };
    const characters = (stem, branch) => `<span class="today-chars" lang="zh-Hant">${esc(stem.chinese + branch.chinese)}</span>`
      + `<span class="today-pinyin">${esc(`${stem.pinyin} ${branch.pinyin}`)}</span>`;
    const layerName = (layer) => t('today_layer_' + layer);
    // A natal pillar by its name; a pillar of the day as this day's, month's or year's.
    const placeName = (pillar) => (FIFTH[pillar] ? t('today_member_' + FIFTH[pillar]) : t('pillar_' + pillar));
    const relationshipName = (kind) => t('relationship_' + kind);
    const tieName = (tie) => (tie === 'repeat' ? t('today_tie_repeat') : relationshipName(tie));

    // ── The date on the clock at where you are, and calendar steps ──
    const todayAt = (timezone) => new Intl.DateTimeFormat('en-CA', {
      timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit',
    }).format(new Date());
    // A calendar step: a day before or after, not 86,400 seconds of some clock.
    const stepDay = (day, by) => {
      const next = calendar(day);
      next.setUTCDate(next.getUTCDate() + by);
      return next.toISOString().slice(0, 10);
    };

    // ── The address: the chart's link parts, then the day, whose day, and the topic ──
    const address = (next) => {
      const params = new URLSearchParams(next.chartParams);
      params.set('lang', next.lang);
      params.set('day', next.day);
      if (next.who === 'partner') params.set('who', 'partner');
      if (next.topic !== null) params.set('topic', next.topic);
      return `#today?${params}`;
    };
    // Moves to another state: the address follows, replacing the entry for a step and
    // adding one for a topic, and the page is drawn for it.
    const move = (changes, method = 'replaceState') => {
      const next = { ...state, ...changes };
      go(address(next), method);
      show(next);
    };

    // ── The request: the chart on screen, with what the account keeps ──
    const chartBirth = (chart) => ({
      date: chart.date,
      time: chart.time,
      place: {
        name: chart.place.display,
        city: chart.place.city,
        timezone: chart.place.timezone,
        latitude: chart.place.latitude,
        longitude: chart.place.longitude,
      },
      gender: chart.gender,
      zi: chart.zi,
    });
    const partnerOf = (kept) => (kept.partner === null || kept.partner.problem !== null ? null : kept.partner);
    const partnerBirth = (partner) => {
      const { pillars: drawn, problem, ...birth } = partner;
      if (problem !== null || drawn === null) throw new Error(t('today_answer_error'));
      return birth;
    };
    const partnerName = (partner) => partner.name ?? t('today_partner');

    // ── What the page says instead of the day, with what can be done ──
    const sayNotice = (text, actions = []) => {
      notice.innerHTML = `<p>${esc(text)}</p>${actions.length ? `<div class="settings-actions">${actions.map(
        ([action, label]) => `<button type="button" class="bar-action" data-today-action="${esc(action)}">${esc(label)}</button>`,
      ).join('')}</div>` : ''}`;
      notice.classList.remove('hidden');
    };
    const clearNotice = () => {
      notice.innerHTML = '';
      notice.classList.add('hidden');
    };
    notice.addEventListener('click', (event) => {
      const action = event.target.closest('[data-today-action]')?.dataset.todayAction;
      if (action === 'settings') onSettings();
      else if (action === 'edit') onEdit(state.chartParams);
      else if (action === 'retry') show(state);
      else if (action === 'self') move({ who: 'self', topic: null });
    });

    // ── The bar ──
    const chartHeading = (chart) => {
      const reading = format.parseWallClock(`${chart.date}T${chart.time}`);
      return [format.date(reading), format.time(reading, chart.time.length > 5), chart.place.city].join(' · ');
    };
    const drawBar = () => {
      dateHeading.textContent = longDate(state.day);
      const partner = shownSettings === null ? null : partnerOf(shownSettings);
      const whose = state.who === 'partner' && partner !== null
        ? t('today_partner_chart', { name: partnerName(partner) })
        : chartHeading(state.chart);
      const place = shownSettings?.place;
      chartLine.textContent = place ? `${whose} · ${t('today_at', { place: place.city })}` : whose;
      whoSwitch.classList.toggle('hidden', partner === null);
      partnerLabel.textContent = partner === null ? '' : partnerName(partner);
      whoSwitch.querySelectorAll('button[data-who]').forEach((button) => {
        button.setAttribute('aria-pressed', String(button.dataset.who === state.who));
      });
      languageSwitch.querySelectorAll('button[data-today-lang]').forEach((button) => {
        button.setAttribute('aria-pressed', String(button.dataset.todayLang === state.lang));
      });
      pageSwitch.querySelectorAll('button[data-page]').forEach((button) => {
        button.setAttribute('aria-pressed', String(button.dataset.page === 'today'));
      });
      nowButton.disabled = !place || state.day === todayAt(place.timezone);
      document.title = t('today_page_title', { day: longDate(state.day) });
    };

    // ── The answer, drawn ──
    const checked = (value) => {
      const ok = value && value.policy === 'today_v1' && value.date === state.day && value.chart === state.who
        && LAYERS.every((layer) => Object.hasOwn(value.layers ?? {}, layer))
        && value.layers.day && value.layers.month && value.layers.year
        && Array.isArray(value.run) && value.run.length > 0 && Array.isArray(value.hours) && value.hours.length === 12
        && value.favourable && value.work && value.health && Array.isArray(value.health.elements);
      if (!ok) throw new Error(t('today_answer_error'));
      return value;
    };
    const topicButton = (path, label) => `<button type="button" class="topic-button" data-today-topic="${esc(path)}"
      aria-expanded="${state.topic === path}" aria-controls="today-panel">${esc(label)}</button>`;
    const drawTopics = () => {
      const day = answer.layers.day;
      pullLine.textContent = t('today_pull_line', { pull: pull(day.pull) });
      topics.innerHTML = [
        topicButton('day', t('today_topic_day')),
        answer.marriage === null ? '' : topicButton('marriage', t('today_topic_marriage')),
        topicButton('work', t('today_topic_work')),
        topicButton('health', t('today_topic_health')),
      ].join('');
    };
    const drawRun = () => {
      run.innerHTML = `
        <span id="today-run-label" class="luck-ribbon-label">${esc(t('today_run_label'))}</span>
        <div class="today-run-track">${answer.run.map((day) => `
          <button type="button" class="today-run-day band-${esc(day.band)}${day.date === state.day ? ' is-selected' : ''}" data-today-day="${esc(day.date)}"
            ${day.date === state.day ? 'aria-current="date"' : ''} aria-label="${esc(t('today_run_day', { day: shortDate(day.date), pull: pull(day) }))}">
            <span class="today-run-date" aria-hidden="true">${esc(shortDate(day.date))}</span>
            <span class="today-run-chars" lang="zh-Hant" aria-hidden="true">${esc(day.pillar.stem.chinese + day.pillar.branch.chinese)}</span>
            <span class="today-run-mark" aria-hidden="true"></span>
            <span class="today-run-score" aria-hidden="true">${esc(score(day.score))}</span>
            <span class="today-run-band" aria-hidden="true">${esc(bandName(day.band))}</span>
          </button>`).join('')}</div>`;
      run.querySelector('.today-run-day.is-selected')?.scrollIntoView({ block: 'nearest', inline: 'center' });
    };
    const tenGodOf = (layer) => layer.ten_gods.find((god) => god.role === 'stem');
    const luckYears = (span) => `${span.start_utc.slice(0, 4)}–${span.end_utc.slice(0, 4)}`;
    const drawPillars = () => {
      pillars.innerHTML = LAYERS.map((name) => {
        const layer = answer.layers[name];
        if (layer === null) {
          return `<article class="today-pillar is-empty" data-layer="${name}">
            <h3 class="today-pillar-name">${esc(layerName(name))}</h3>
            <p class="today-pillar-none">${esc(t('today_no_luck'))}</p>
          </article>`;
        }
        const { stem, branch } = layer.pillar;
        const god = tenGodOf(layer);
        const luck = layer.luck === null ? ''
          : `<p class="today-pillar-luck">${esc(t('today_luck_span', { years: luckYears(layer.luck), phase: t('today_phase_' + layer.luck.phase) }))}</p>`;
        return `<article class="today-pillar ${esc(stem.element)}" data-layer="${name}">
          <h3 class="today-pillar-name">${esc(layerName(name))}</h3>
          <button type="button" class="today-pillar-open" data-today-topic="pillar/${name}" aria-expanded="${state.topic === `pillar/${name}`}" aria-controls="today-panel">
            ${characters(stem, branch)}
          </button>
          <p class="today-pillar-god">${esc(god ? t('ten_god_' + god.ten_god) : '')}</p>
          <p class="today-pillar-pull band-${esc(layer.pull.band)}"><span class="today-band-mark" aria-hidden="true"></span>${esc(pull(layer.pull))}</p>
          ${luck}
        </article>`;
      }).join('');
    };
    const relationshipItem = (r) => `<li class="today-relationship" data-relationship="${esc(r.id)}">
        <span class="today-relationship-kind">${esc(relationshipName(r.kind))}</span>
        <span class="today-relationship-members">${r.members.map((m) => `<span class="today-member"><span lang="zh-Hant">${esc(m.char)}</span> ${esc(m.pinyin)} · ${esc(placeName(m.pillar))}</span>`).join('')}</span>
        ${r.line ? `<span class="today-relationship-line">${esc(r.line)}</span>` : ''}
      </li>`;
    const drawInChart = () => {
      const all = LAYERS.flatMap((name) => (answer.layers[name]?.relationships ?? []));
      const partner = shownSettings === null ? null : partnerOf(shownSettings);
      const title = state.who === 'partner' && partner !== null
        ? t('today_in_chart_of', { name: partnerName(partner) }) : t('today_in_chart');
      inChart.innerHTML = `<h3 id="today-in-chart-title" class="today-section-title">${esc(title)}</h3>
        ${all.length ? `<ul class="today-relationships">${all.map(relationshipItem).join('')}</ul>`
          : `<p class="settings-note">${esc(t('today_in_chart_none'))}</p>`}`;
    };
    const drawHours = () => {
      hours.innerHTML = `<h3 id="today-hours-title" class="today-section-title">${esc(t('today_hours'))}</h3>
        <p class="settings-note">${esc(t('today_hours_note', { place: answer.place.city }))}</p>
        <table class="today-hours">
          <thead><tr>
            <th scope="col">${esc(t('today_hour'))}</th>
            <th scope="col">${esc(t('today_hour_time'))}</th>
            <th scope="col">${esc(t('today_hour_ties'))}</th>
            <th scope="col">${esc(t('today_hour_call'))}</th>
          </tr></thead>
          <tbody>${answer.hours.map((hour) => `<tr class="${hour.call === null ? '' : `call-${esc(hour.call)}`}">
            <th scope="row"><span lang="zh-Hant">${esc(hour.branch)}</span> ${esc(hour.pinyin)} · ${esc(t('animal_' + hour.sign.toLowerCase()))}</th>
            <td>${hour.spans.map((span) => `${esc(clock(span.start))}–${esc(clock(span.end))}`).join('<br>')}</td>
            <td>${esc(hour.ties.map(tieName).join(', ') || '—')}</td>
            <td>${hour.call === null ? '—' : `<span class="today-call-mark" aria-hidden="true"></span>${esc(t('today_call_' + hour.call))}`}</td>
          </tr>`).join('')}</tbody>
        </table>`;
    };

    // ── The panel's topics ──
    const partsTable = (layer) => `<table class="today-parts">
        <thead><tr>
          <th scope="col">${esc(t('today_part'))}</th>
          <th scope="col">${esc(t('today_part_element'))}</th>
          <th scope="col">${esc(t('today_part_weight'))}</th>
          <th scope="col">${esc(t('today_part_counts'))}</th>
          <th scope="col">${esc(t('today_part_value'))}</th>
        </tr></thead>
        <tbody>${layer.pull.parts.map((part) => `<tr>
          <th scope="row"><span lang="zh-Hant">${esc(part.char)}</span> ${esc(part.pinyin)} · ${esc(t('today_role_' + part.role))}</th>
          <td>${esc(t('element_' + part.element))}</td>
          <td>${esc(score(part.weight))}</td>
          <td>${esc(number(part.factor, 2))}</td>
          <td>${esc(score(part.value))}</td>
        </tr>`).join('')}</tbody>
      </table>`;
    // The canon's readings for a pillar of the day, as the decade page reads a luck
    // pillar (English only).
    const passage = (key, paragraphs) => (paragraphs?.length ? `<details class="today-reading">
        <summary><span class="canon-line-key">${esc(key)}</span></summary>
        ${paragraphs.map((p) => `<p class="canon-text">${p.label === null ? '' : `<strong>${esc(p.label)}:</strong> `}${esc(p.text)}</p>`).join('')}
      </details>` : '');
    const readingOf = (name, layer) => {
      const reading = answer.readings?.[name];
      if (!reading) return '';
      const stage = reading.branch.stage;
      return `<div class="today-readings">
        ${passage(`Its stem · ${reading.stem.name}`, reading.stem.core)}
        ${passage(`About the ${layer.pillar.branch.sign}`, reading.branch.about)}
        ${passage('On this ground', reading.branch.meets)}
        ${passage(`The stage here · ${stage.name} ${stage.chinese}`, stage.paragraphs)}
        ${Object.values(reading.relationships).map((r) => passage(`${r.entry.title}${r.line ? ` · ${r.line}` : ''}`, [...(r.introduction ?? []), ...r.entry.paragraphs])).join('')}
        ${reading.settles.map((s) => `<p class="canon-condition">${esc(s.sentence)}</p>`).join('')}
      </div>`;
    };
    const pillarSection = (name) => {
      const layer = answer.layers[name];
      if (layer === null) return `<p class="settings-note">${esc(t('today_no_luck'))}</p>`;
      const { stem, branch } = layer.pillar;
      return `<section class="today-detail-pillar">
        <h4 class="today-detail-subtitle">${esc(layerName(name))} · ${characters(stem, branch)}</h4>
        <p>${esc(t('today_layer_pull', { pull: pull(layer.pull) }))}</p>
        ${partsTable(layer)}
        ${layer.relationships.length ? `<ul class="today-relationships">${layer.relationships.map(relationshipItem).join('')}</ul>` : ''}
        ${readingOf(name, layer)}
      </section>`;
    };
    const palace = (title, place) => `<h4 class="today-detail-subtitle">${esc(title)} · <span lang="zh-Hant">${esc(place.branch)}</span> ${esc(place.pinyin)}</h4>
      ${place.relationships.length ? `<ul class="today-relationships">${place.relationships.map(relationshipItem).join('')}</ul>`
        : `<p class="settings-note">${esc(t('today_palace_quiet'))}</p>`}`;
    const topicMarkup = (topic) => {
      if (topic === 'day') {
        const season = answer.season;
        return `<h3 id="today-detail-title" class="panel-heading">${esc(t('today_topic_day'))}</h3>
          <p class="settings-note">${esc(t('today_season', { element: t('element_' + season.ruler), school: season.school }))}</p>
          <p class="settings-note">${esc(t('today_schools_used', { schools: Object.values(answer.schools).join(', ') }))}</p>
          ${LAYERS.map(pillarSection).join('')}
          ${lang() === 'fi' ? `<p class="settings-note">${esc(t('today_readings_english'))}</p>` : ''}`;
      }
      if (topic.startsWith('pillar/')) {
        const name = topic.slice('pillar/'.length);
        return `<h3 id="today-detail-title" class="panel-heading">${esc(layerName(name))}</h3>${pillarSection(name)}`;
      }
      if (topic === 'marriage') {
        const m = answer.marriage;
        if (m === null) throw new Error(t('today_answer_error'));
        const partner = shownSettings === null ? null : partnerOf(shownSettings);
        const other = state.who === 'partner' ? t('today_self') : partnerName(partner);
        return `<h3 id="today-detail-title" class="panel-heading">${esc(t('today_topic_marriage'))}</h3>
          <p>${esc(t('today_their_pull', { name: other, pull: pull(m.partner.pull) }))}</p>
          <p>${esc(t(m.pull_apart ? 'today_pull_apart' : 'today_pull_not_apart'))}</p>
          ${m.partner.luck === null ? '' : `<p>${esc(t('today_their_luck', { name: other, pull: pull(m.partner.luck.pull) }))} ${characters(m.partner.luck.pillar.stem, m.partner.luck.pillar.branch)}</p>`}
          ${palace(t('today_spouse_palace'), m.spouse_palace)}
          <h4 class="today-detail-subtitle">${esc(t('today_with_their_chart', { name: other }))}</h4>
          ${m.partner_chart.length ? `<ul class="today-relationships">${m.partner_chart.map(relationshipItem).join('')}</ul>`
            : `<p class="settings-note">${esc(t('today_palace_quiet'))}</p>`}`;
      }
      if (topic === 'work') {
        const w = answer.work;
        return `<h3 id="today-detail-title" class="panel-heading">${esc(t('today_topic_work'))}</h3>
          ${palace(t('today_career_house'), w.career_house)}
          <h4 class="today-detail-subtitle">${esc(t('today_gods_in_play'))}</h4>
          <ul class="today-gods">${w.ten_gods.map((god) => `<li><span lang="zh-Hant">${esc(god.char)}</span> ${esc(god.pinyin)} · ${esc(t('ten_god_' + god.ten_god))}${lang() === 'en' && god.relation ? ` · ${esc(god.relation)}` : ''}</li>`).join('')}</ul>`;
      }
      const h = answer.health;
      return `<h3 id="today-detail-title" class="panel-heading">${esc(t('today_topic_health'))}</h3>
        <p class="settings-note">${esc(t('today_health_note'))}</p>
        <table class="today-health">
          <thead><tr>
            <th scope="col">${esc(t('today_part_element'))}</th>
            <th scope="col">${esc(t('today_health_today'))}</th>
            <th scope="col">${esc(t('today_health_chart'))}</th>
            <th scope="col">${esc(t('today_health_organs'))}</th>
          </tr></thead>
          <tbody>${ELEMENTS.map((element) => {
            const e = h.elements.find((item) => item.element === element);
            if (!e) throw new Error(t('today_answer_error'));
            return `<tr><th scope="row">${esc(t('element_' + element))}</th><td>${esc(number(e.today, 2))}</td><td>${esc(number(e.chart_share))} %</td><td>${esc(e.organs)}</td></tr>`;
          }).join('')}</tbody>
        </table>`;
    };
    const drawPanel = () => {
      if (state.topic === null) {
        panel.classList.add('hidden');
        view.classList.remove('has-panel');
        detail.innerHTML = '';
        return;
      }
      detail.innerHTML = topicMarkup(state.topic);
      panel.classList.remove('hidden');
      view.classList.add('has-panel');
    };
    panel.addEventListener('click', (event) => {
      if (event.target.closest('[data-close-today-panel]')) closeTopic();
    });
    const closeTopic = () => {
      if (state === null || state.topic === null) return;
      const opener = view.querySelector(`[data-today-topic="${state.topic}"]`);
      move({ topic: null }, 'pushState');
      opener?.focus();
    };

    const draw = () => {
      drawBar();
      drawTopics();
      drawRun();
      drawPillars();
      drawInChart();
      drawHours();
      drawPanel();
      body.classList.remove('hidden');
    };

    // Shows the day a state names: the settings are read again, then the API asked.
    const show = async (next) => {
      if (!DAY_PATH.test(next.day) || (next.topic !== null && !TOPIC_PATH.test(next.topic))) throw new Error(t('today_answer_error'));
      state = next;
      const mine = ++asked;
      view.classList.remove('hidden');
      view.setAttribute('aria-busy', 'true');
      clearNotice();
      drawBar();
      try {
        const kept = await settings.load();
        if (mine !== asked) return;
        shownSettings = kept;
        drawBar();
        if (!state.chart.gender) {
          body.classList.add('hidden');
          sayNotice(t('today_needs_gender'), [['edit', t('edit_chart')]]);
          return;
        }
        if (kept.place === null) {
          body.classList.add('hidden');
          sayNotice(t('today_needs_place'), [['settings', t('settings_open')]]);
          return;
        }
        const partner = partnerOf(kept);
        if (state.who === 'partner' && partner === null) {
          body.classList.add('hidden');
          sayNotice(t(kept.partner === null ? 'today_partner_gone' : 'today_partner_problem'), [['self', t('today_self')], ['settings', t('settings_open')]]);
          return;
        }
        const response = await fetch('/api/today', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            date: state.day,
            lang: state.lang,
            place: kept.place,
            charts: { self: chartBirth(state.chart), ...(partner === null ? {} : { partner: partnerBirth(partner) }) },
            chart: state.who,
            schools: kept.chosen,
          }),
        });
        if (mine !== asked) return;
        if (response.status === 401) {
          // Signed out meanwhile: a sign-in, then the day again.
          if (!(await account.recheck(() => mine === asked))) await account.signIn();
          if (mine === asked) await show(state);
          return;
        }
        let value;
        try {
          value = await response.json();
        } catch (err) {
          throw new Error(t('today_answer_error'), { cause: err });
        }
        if (mine !== asked) return;
        if (!response.ok) {
          body.classList.add('hidden');
          sayNotice(typeof value?.detail === 'string' ? value.detail : t('today_answer_error'), [['retry', t('today_retry')]]);
          return;
        }
        answer = checked(value);
        draw();
        if (state.who === 'partner') sayNotice(t('today_partner_note', { name: partnerName(partner), place: kept.place.city }));
        status.textContent = t('today_status', { day: longDate(state.day), pull: pull(answer.layers.day.pull) });
      } catch (err) {
        if (mine !== asked) return;
        console.error(err);
        body.classList.add('hidden');
        sayNotice(err.message || t('today_answer_error'), [['retry', t('today_retry')]]);
      } finally {
        if (mine === asked) view.removeAttribute('aria-busy');
      }
    };
    const hide = () => {
      asked += 1;
      state = null;
      answer = null;
      view.classList.add('hidden');
      view.removeAttribute('aria-busy');
    };

    // ── The controls ──
    steps.addEventListener('click', (event) => {
      if (state === null) return;
      const step = event.target.closest('[data-today-step]');
      if (step) move({ day: stepDay(state.day, Number(step.dataset.todayStep)) });
      else if (event.target.closest('[data-today-now]') && shownSettings?.place) move({ day: todayAt(shownSettings.place.timezone) });
    });
    run.addEventListener('click', (event) => {
      const chosen = event.target.closest('[data-today-day]');
      if (chosen && state !== null && chosen.dataset.todayDay !== state.day) move({ day: chosen.dataset.todayDay });
    });
    view.addEventListener('click', (event) => {
      const opener = event.target.closest('[data-today-topic]');
      if (!opener || state === null) return;
      const topic = opener.dataset.todayTopic;
      move({ topic: state.topic === topic ? null : topic }, 'pushState');
    });
    whoSwitch.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-who]');
      if (button && state !== null && button.dataset.who !== state.who) move({ who: button.dataset.who, topic: null });
    });
    languageSwitch.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-today-lang]');
      if (!button || state === null || button.dataset.todayLang === state.lang) return;
      onLanguage(button.dataset.todayLang);
      move({ lang: button.dataset.todayLang });
    });
    pageSwitch.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-page="chart"]');
      if (button && state !== null) onChart(state.chartParams);
    });
    settingsButton.addEventListener('click', () => onSettings());
    printButton.addEventListener('click', () => window.print());
    copyLink.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(location.href);
        toast(t('link_copied'), false);
      } catch (err) {
        console.error(err);
        toast(t('link_copy_error'), true);
      }
    });
    // The day as text, for notes and messages: the same numbers as the page.
    const text = () => {
      if (answer === null) return '';
      const lines = [
        `${longDate(state.day)} · ${chartLine.textContent}`,
        t('today_schools_used', { schools: Object.values(answer.schools).join(', ') }),
        t('today_pull_line', { pull: pull(answer.layers.day.pull) }),
        ...LAYERS.map((name) => {
          const layer = answer.layers[name];
          if (layer === null) return `${layerName(name)}: ${t('today_no_luck')}`;
          const { stem, branch } = layer.pillar;
          return `${layerName(name)}: ${stem.chinese}${branch.chinese} ${stem.pinyin} ${branch.pinyin} · ${pull(layer.pull)}`;
        }),
        `${t('today_run_label')}:`,
        ...answer.run.map((day) => `  ${shortDate(day.date)} ${day.pillar.stem.chinese}${day.pillar.branch.chinese} · ${pull(day)}`),
        `${t('today_hours')}:`,
        ...answer.hours.map((hour) => `  ${hour.branch} ${hour.pinyin} ${hour.spans.map((s) => `${clock(s.start)}–${clock(s.end)}`).join(', ')}${hour.call === null ? '' : ` · ${t('today_call_' + hour.call)}`}`),
      ];
      return lines.join('\n');
    };
    copyText.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(text());
        toast(t('text_copied'), false);
      } catch (err) {
        console.error(err);
        toast(t('text_copy_error'), true);
      }
    });

    // The keys, while the page has focus and no field does: [ and ] step a day, N goes
    // to today, Escape closes a topic. Brackets are typed with Alt or AltGr on many
    // keyboards; a held key steps once.
    const keydown = (event) => {
      if (state === null || answer === null || event.metaKey || (event.ctrlKey && !event.altKey) || event.repeat) return false;
      const plain = !event.ctrlKey && !event.altKey;
      if (event.key === '[') move({ day: stepDay(state.day, -1) });
      else if (event.key === ']') move({ day: stepDay(state.day, 1) });
      else if (plain && event.key.toLowerCase() === 'n' && shownSettings?.place) move({ day: todayAt(shownSettings.place.timezone) });
      else if (event.key === 'Escape' && state.topic !== null) closeTopic();
      else return false;
      return true;
    };
    // What Today offers to the commands (⌘K), as its controls name them.
    const commands = () => {
      if (state === null) return [];
      const list = [
        { label: t('today_previous'), run: () => move({ day: stepDay(state.day, -1) }), icon: 'chevron-left' },
        { label: t('today_next'), run: () => move({ day: stepDay(state.day, 1) }), icon: 'chevron-right' },
      ];
      if (shownSettings?.place) list.push({ label: t('today_now'), run: () => move({ day: todayAt(shownSettings.place.timezone) }), icon: 'calendar-check' });
      const partner = shownSettings === null ? null : partnerOf(shownSettings);
      if (partner !== null) {
        list.push(state.who === 'partner'
          ? { label: t('today_self'), run: () => move({ who: 'self', topic: null }), icon: null }
          : { label: partnerName(partner), run: () => move({ who: 'partner', topic: null }), icon: 'users-round' });
      }
      view.querySelectorAll('#today-topics [data-today-topic]').forEach((button) => {
        list.push({ label: button.textContent.trim(), run: () => move({ topic: button.dataset.todayTopic }, 'pushState'), icon: 'chevron-right' });
      });
      list.push(
        { label: t('page_chart'), run: () => onChart(state.chartParams), icon: 'columns-4' },
        { label: t('copy_link'), run: () => copyLink.click(), icon: 'link-2' },
        { label: t('copy_text'), run: () => copyText.click(), icon: 'clipboard-list' },
        { label: t('print'), run: () => window.print(), icon: 'printer' },
        { label: t('settings_open'), run: () => onSettings(), icon: 'settings' },
      );
      return list;
    };

    return {
      show,
      hide,
      keydown,
      commands,
      text,
      isShown: () => state !== null,
      // The current state, for the address: null while Today is not shown.
      state: () => state,
      // Settings changed: the day is asked for again with them.
      refresh: () => {
        if (state !== null) show(state);
      },
      // The page's language set from outside (the account): the day follows it.
      setLanguage: (next) => {
        if (state !== null && state.lang !== next) move({ lang: next });
      },
    };
  };
  window.EC_TODAY = { create, TOPIC_PATH, DAY_PATH };
})();
