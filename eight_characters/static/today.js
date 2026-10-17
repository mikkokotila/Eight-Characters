// Today: what a day, its month, its year and the luck pillar in force bring to the chart
// on screen, and to its partner's (docs/Standard-Today.md). The API reckons all of it
// (POST /api/today), with the place and the schools the account keeps (settings.js) and,
// when the chart on screen is a saved chart in a couple, the other chart of the couple
// (library.js). This page draws its answer and computes nothing: the only thing it
// reads itself is the date on the clock at where you are.
(() => {
  const LAYERS = ['day', 'month', 'year', 'luck'];
  const BANDS = ['strongly_supportive', 'supportive', 'mixed', 'draining', 'strongly_draining'];
  // The fifth places the day's pillars stand in, as the relationships name them.
  const FIFTH = { daily: 'day', monthly: 'month', annual: 'year', luck: 'luck' };
  const TOPIC_PATH = /^(marriage|work|health|day|pillar\/(day|month|year|luck))$/;
  const DAY_PATH = /^\d{4}-\d{2}-\d{2}$/;
  const ELEMENTS = ['wood', 'fire', 'earth', 'metal', 'water'];
  const NATAL = ['year', 'month', 'day', 'hour'];
  // The five gods, from the useful to the unfavourable (docs/Today.md).
  const GODS = ['useful', 'favourable', 'idle', 'enemy', 'unfavourable'];
  // The pull's scale, the same for every layer and day: the rules' largest pull is 3.28
  // (test_schools.py holds every pull inside it).
  const SCALE = 3.5;
  // A drag moves the days once it has gone this far across.
  const DRAG = 40;

  // ── The address: the chart's link parts, then the day, whose day, the partner in view
  // and the topic ──
  // The chart's own link, in the language the day is shown in.
  const chartLink = (state) => {
    const params = new URLSearchParams(state.chartParams);
    params.set('lang', state.lang);
    return params.toString();
  };
  const address = (state) => {
    const params = new URLSearchParams(chartLink(state));
    params.set('day', state.day);
    if (state.who === 'partner') params.set('who', 'partner');
    if (state.partner !== null) params.set('partner', state.partner);
    if (state.topic !== null) params.set('topic', state.topic);
    return `#today?${params}`;
  };
  // What a day is read for, its day and topic apart: the chart, in its language, whose
  // day it is, and the partner in view.
  const reading = (state) => `${chartLink(state)} ${state.who} ${state.partner ?? ''}`;

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
    const partnerChoice = need('#today-partner-choice');
    const partnerSelect = need('#today-partner');
    const languageSwitch = need('#today-language');
    const copyLink = need('#today-copy-link');
    const copyText = need('#today-copy-text');
    const printButton = need('#today-print');
    const settingsButton = need('#today-settings');
    const notice = need('#today-notice');
    const body = need('#today-body');
    const pullLine = need('#today-pull-line');
    const topics = need('#today-topics');
    const days = need('#today-days');
    const daysTrack = need('.today-days-track');
    const run = need('#today-run');
    const scale = need('#today-scale');
    const pillarsNote = need('#today-pillars-label');
    const pillars = need('#today-pillars');
    const couple = need('#today-couple');
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
    // The run the days and their steps go by: the answer drawn last's, while what is shown
    // is still read as it was (`daysReading`). None while no day is drawn, and none from
    // when another chart, language or person is shown, or Today is left (its settings may
    // change meanwhile), until the next answer is drawn.
    let daysRun = null;
    let daysReading = null;
    // The press on the days being followed, if any (the gestures are below).
    let drag = null;
    const dropDrag = () => {
      if (drag?.moving) releaseDays();
      drag = null;
      days.classList.remove('is-dragging');
      days.style.removeProperty('--drag');
    };
    // The run a press drags by is discarded (another reading shown, the day refused,
    // Today left): the press is still followed to its release, for its click, but moves
    // nothing, though another run is drawn before it ends.
    const cancelDrag = () => {
      if (drag === null) return;
      if (drag.moving) releaseDays();
      drag.drags = false;
      drag.moving = false;
      days.classList.remove('is-dragging');
      days.style.removeProperty('--drag');
    };
    // The clock as the page last drew it: today where you are, and the hour of the day
    // shown that it is in.
    let clockDrawn = null;

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
    const weekdayOf = (day) => new Intl.DateTimeFormat(locale(), { weekday: 'long', timeZone: 'UTC' }).format(calendar(day));
    const dayMonthOf = (day) => new Intl.DateTimeFormat(locale(), { day: 'numeric', month: 'long', timeZone: 'UTC' }).format(calendar(day));
    const dayOfMonth = (day) => new Intl.DateTimeFormat(locale(), { day: 'numeric', timeZone: 'UTC' }).format(calendar(day));
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
    // "Useful: Wood": one of the five gods and its element.
    const godLine = (god, element) => t('today_god_element', { god: t('today_god_' + god), element: t('element_' + element) });

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
    // A step from the day shown, through the run drawn: as many of its days on as asked,
    // so a date the place's clocks skipped is passed over; whatever goes past the run's
    // end is counted in calendar days from that end. With no run drawn (a day the API
    // refused, or another reading on its way), every step is a calendar day.
    const stepped = (by) => {
      const at = daysRun === null ? -1 : daysRun.findIndex((day) => day.date === state.day);
      if (at < 0) return stepDay(state.day, by);
      const end = Math.min(Math.max(at + by, 0), daysRun.length - 1);
      return stepDay(daysRun[end].date, at + by - end);
    };

    // Moves to another state: the address follows, replacing the entry for a step and
    // adding one for a topic, and the page is drawn for it.
    const move = (changes, method = 'replaceState') => {
      const next = { ...state, ...changes };
      go(address(next), method);
      // Topics select material already in this day's answer; they are not inputs to
      // /api/today. An answer on its way draws the latest topic when it arrives.
      if (Object.keys(changes).every((key) => key === 'topic')) {
        state = next;
        if (answer !== null) keepingFocus(() => { drawTopics(); drawPanel(); });
        else if (next.topic === null) drawPanel();
        return;
      }
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
      ...(chart.fold === null ? {} : { fold: chart.fold }),
      gender: chart.gender,
      zi: chart.zi,
    });
    // The partners of the chart on screen, as saved, in the order its couples were
    // formed: none when the chart is not saved or in no couple. A chart can be in any
    // number of couples (#98).
    const partnersOf = (kept) => {
      const saved = window.EC_LIBRARY.savedOf(kept, chartBirth(state.chart));
      return saved === null ? [] : window.EC_LIBRARY.partnersOf(kept, saved.id);
    };
    // The partner in view: the one the address names, when it is one of the chart's
    // partners in this account (show() writes the first couple's partner in when the
    // address names none); null otherwise.
    const partnerInView = (kept) => (state.partner === null ? null
      : partnersOf(kept).find((chart) => chart.id === state.partner) ?? null);
    // The partner in view, when its chart can be read.
    const partnerOf = (kept) => {
      const other = partnerInView(kept);
      return other === null || other.problem !== null ? null : other;
    };
    // The partner in view's id, as the settings last read name it: null for none.
    const shownPartnerId = () => (shownSettings === null ? null : partnerInView(shownSettings)?.id ?? null);
    // Why no partner is read: the chart is in no couple, the chart named is not one of
    // its partners in this account, or the partner's chart no longer charts.
    const partnerGone = (kept) => {
      if (partnerInView(kept) !== null) return t('today_partner_problem');
      return t(partnersOf(kept).length === 0 ? 'today_partner_gone' : 'today_partner_unpaired');
    };
    // What the API takes of a saved chart: its birth, without the library's id or the
    // drawn pillars.
    const partnerBirth = (partner) => {
      const { id, pillars: drawn, problem, ...birth } = partner;
      if (typeof id !== 'string' || problem !== null || drawn === null) throw new Error(t('today_answer_error'));
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
      else if (action === 'edit') onEdit(chartLink(state));
      else if (action === 'retry') show(state);
      // This chart's own day, with the first couple's partner in view again.
      else if (action === 'self') move({ who: 'self', partner: null, topic: null });
    });

    // ── The bar ──
    // The choice of partners as last drawn.
    let partnerChoices = '';
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
      // With the chart in several couples, or one named that is not its partner, the
      // partner in view is chosen here: an unnamed one by its birth, one that no longer
      // charts shown but not chosen.
      const partners = shownSettings === null ? [] : partnersOf(shownSettings);
      const inView = shownSettings === null ? null : partnerInView(shownSettings);
      const choosing = partners.length > 1 || (partners.length > 0 && inView === null && state.partner !== null);
      partnerChoice.classList.toggle('hidden', !choosing);
      const choiceLabel = (chart) => [
        chart.name ?? `${t('library_unnamed')} · ${chartHeading(chart)}`,
        chart.problem === null ? '' : ` ${t('today_partner_cannot')}`,
      ].join('');
      // Hidden, it keeps no names.
      const choices = choosing ? [
        inView === null ? `<option value="" selected disabled>${esc(t('today_partner'))}</option>` : '',
        ...partners.map((chart) => `<option value="${esc(chart.id)}"${chart.id === inView?.id ? ' selected' : ''}${chart.problem === null ? '' : ' disabled'}>${esc(choiceLabel(chart))}</option>`),
      ].join('') : '';
      // Drawn again only when it changes: an open choice is left alone.
      if (choices !== partnerChoices) {
        partnerSelect.innerHTML = choices;
        partnerChoices = choices;
      }
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
      // Every pillar is drawn as the chart's cards and every pull on the scale: an answer
      // without a pillar's lines, or with a pull past the scale's ends, is refused, never
      // drawn clipped.
      const lines = (found, count) => Array.isArray(found) && found.length === count && found.every((line) => line === 'L' || line === 'B');
      const drawable = (pillar) => Boolean(pillar?.stem && pillar.branch && lines(pillar.stem.lines, 3) && lines(pillar.branch.lines, 6)
        && ELEMENTS.includes(pillar.stem.element) && ELEMENTS.includes(pillar.branch.element));
      const onScale = (found) => Number.isFinite(found) && Math.abs(found) <= SCALE;
      const whole = ok && value.natal && NATAL.every((name) => drawable(value.natal[name]))
        && LAYERS.every((layer) => value.layers[layer] === null
          || (drawable(value.layers[layer].pillar) && onScale(value.layers[layer].pull.score)))
        && value.run.every((day) => drawable(day.pillar) && onScale(day.score))
        && GODS.every((god) => ELEMENTS.includes(value.favourable.gods?.[god]))
        && value.hours.every((hour) => ELEMENTS.includes(hour.element))
        && (value.marriage === null || onScale(value.marriage?.partner?.pull?.score));
      if (!whole) throw new Error(t('today_answer_error'));
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
    // ── The chart's cards, as Standard mode draws a pillar: a stem card over its branch
    // card, each in its own element's colours, its character with its pinyin. Large, a
    // card also draws its lines (the stem's trigram, the branch's hexagram, as the answer
    // gives them) and its name: the stem's polarity and element, the branch's animal. A
    // relationship's member is outlined on its card. ──
    const gua = (lines) => `<span class="today-gua" aria-hidden="true">${lines.map((line) => `<i class="today-line is-${line === 'L' ? 'whole' : 'broken'}"></i>`).join('')}</span>`;
    const card = (part, glyph, large, member) => `<span class="today-card is-${part} ${esc(glyph.element)}${member ? ' is-member' : ''}">
        <span class="today-card-glyph" lang="zh-Hant">${esc(glyph.chinese)}</span>
        <span class="today-card-pinyin">${esc(glyph.pinyin)}</span>
        ${large ? `${gua(glyph.lines)}<span class="today-card-name">${esc(part === 'stem'
          ? `${glyph.polarity} ${t('element_' + glyph.element)}`
          : t('animal_' + glyph.sign.toLowerCase()))}</span>` : ''}
      </span>`;
    const cards = (pillar, size, member = null) => `<span class="today-cards is-${size}">${card('stem', pillar.stem, size === 'large', member === pillar.stem.chinese)}${card('branch', pillar.branch, size === 'large', member === pillar.branch.chinese)}</span>`;

    // ── The pull's scale: one domain, -3.5 to +3.5, for every layer and day; ticks at the
    // bands' edges; the score's marker. Its halves take the useful and the unfavourable
    // element's colours; the words beside it say what the colours do. ──
    const TICKS = [-1.5, -0.5, 0, 0.5, 1.5];
    const scaleAt = (value) => `${(50 + (value / SCALE) * 50).toFixed(2)}%`;
    const track = (markers, gods = null, size = '') => `<span class="today-scale-track${gods === null ? ' is-neutral' : ''}${size ? ` is-${size}` : ''}"${gods === null ? ''
      : ` style="--for: var(--${gods.useful}-bg); --against: var(--${gods.unfavourable}-bg)"`}>
        ${TICKS.map((tick) => `<i class="today-scale-tick${tick === 0 ? ' is-zero' : ''}" style="--at: ${scaleAt(tick)}"></i>`).join('')}
        ${markers.map(([value, kind]) => `<i class="today-scale-marker is-${kind}" style="--at: ${scaleAt(value)}"></i>`).join('')}
      </span>`;
    const drawScale = () => {
      const gods = answer.favourable.gods;
      scale.innerHTML = `<div class="today-scale-figure" aria-hidden="true">
          <span class="today-scale-end is-against">− ${esc(godLine('unfavourable', gods.unfavourable))}</span>
          ${track([[answer.layers.day.pull.score, 'day']], gods)}
          <span class="today-scale-end is-for">+ ${esc(godLine('useful', gods.useful))}</span>
        </div>
        <p class="today-five-gods">${GODS.map((god) => `<span class="today-god"><i class="today-god-chip ${esc(gods[god])}" aria-hidden="true"></i>${esc(godLine(god, gods[god]))}</span>`).join('')}</p>`;
    };

    // ── The days: the chosen one in the middle as the chart's cards, its neighbours in the
    // run on either side, smaller. A day's node stays while it is near the middle, so a
    // step moves the days rather than drawing them anew; one coming into view enters
    // from a step beyond. ──
    const dayNodes = new Map();
    const placeDay = (node, place) => {
      if (!node.getClientRects().length) {
        node.dataset.place = place;
        node.style.removeProperty('--flow-day-x'); node.style.removeProperty('--flow-day-scale');
        return;
      }
      const transform = getComputedStyle(node).transform;
      const before = transform === 'none' ? new DOMMatrix() : new DOMMatrix(transform);
      node.style.removeProperty('--flow-day-x'); node.style.removeProperty('--flow-day-scale');
      node.dataset.place = place;
      const targetTransform = getComputedStyle(node).transform;
      const target = targetTransform === 'none' ? new DOMMatrix() : new DOMMatrix(targetTransform);
      window.EC_MOTION.spring(node, 'day', {
        from: { x: before.e, scale: before.a }, to: { x: target.e, scale: target.a }, rebase: true,
        write: ({ x, scale }) => {
          node.style.setProperty('--flow-day-x', `${x}px`); node.style.setProperty('--flow-day-scale', String(scale));
        },
        complete: () => { node.style.removeProperty('--flow-day-x'); node.style.removeProperty('--flow-day-scale'); },
      });
    };
    const releaseDays = () => {
      const poses = [...dayNodes.values()].filter((node) => node.getClientRects().length)
        .map((node) => [node, new DOMMatrix(getComputedStyle(node).transform)]);
      days.style.removeProperty('--drag');
      for (const [node, pose] of poses) {
        node.style.setProperty('--flow-day-x', `${pose.e}px`); node.style.setProperty('--flow-day-scale', String(pose.a));
        placeDay(node, node.dataset.place);
      }
    };
    const dayMarkup = (day) => `${cards(day.pillar, 'large')}
      <span class="today-day-when"><span class="today-day-weekday">${esc(weekdayOf(day.date))}</span>
        <span class="today-day-date">${esc(dayMonthOf(day.date))}</span></span>
      <span class="today-day-pull band-${esc(day.band)}"><span class="today-band-mark" aria-hidden="true"></span>${esc(pull(day))}</span>`;
    const placeOf = (offset) => (offset < -2 ? 'before' : offset > 2 ? 'after' : String(offset));
    const clearDays = () => {
      dayNodes.forEach((node) => node.remove());
      dayNodes.clear();
    };
    // Lays the days out around `centre`, from the run drawn; `moved` is the step's way
    // (1 later, -1 earlier, 0 none). False when the run does not hold the day.
    const layDays = (centre, moved) => {
      const at = daysRun === null ? -1 : daysRun.findIndex((day) => day.date === centre);
      if (at < 0) return false;
      const near = new Map();
      for (let offset = -3; offset <= 3; offset += 1) {
        const day = daysRun[at + offset];
        if (day) near.set(day.date, { day, offset });
      }
      dayNodes.forEach((node, date) => {
        if (near.has(date)) return;
        node.remove();
        dayNodes.delete(date);
      });
      let entering = false;
      near.forEach(({ day, offset }, date) => {
        let node = dayNodes.get(date);
        if (!node) {
          node = document.createElement('div');
          node.className = 'today-day';
          node.dataset.todayPick = date;
          node.dataset.place = placeOf(offset + moved);
          daysTrack.append(node);
          dayNodes.set(date, node);
          entering = true;
        }
        node.innerHTML = dayMarkup(day);
        node.classList.toggle('is-centre', offset === 0);
        node.setAttribute('aria-hidden', String(offset !== 0));
      });
      // Laid out where they enter from, then moved: the days slide in.
      if (entering && moved !== 0) void daysTrack.offsetWidth;
      near.forEach(({ offset }, date) => {
        placeDay(dayNodes.get(date), placeOf(offset));
      });
      return true;
    };
    // The run marks the day chosen at once too.
    const markRun = (day) => {
      run.querySelectorAll('[data-today-day]').forEach((button) => {
        const chosen = button.dataset.todayDay === day;
        button.classList.toggle('is-selected', chosen);
        if (chosen) button.setAttribute('aria-current', 'date');
        else button.removeAttribute('aria-current');
      });
    };
    const drawDays = () => {
      daysRun = answer.run;
      daysReading = reading(state);
      layDays(state.day, 0);
    };

    // ── The run: the 22 days as a strip, each a bar around a zero line, up for a positive
    // pull and down for a negative one, its length on the pull's scale. Each day's text
    // (date, pillar, score, band) is in its button, for the reader and for print. ──
    const drawRun = () => {
      const gods = answer.favourable.gods;
      const { today } = clockDrawn;
      run.innerHTML = `
        <span id="today-run-label" class="today-run-label">${esc(t('today_run_label'))}</span>
        <div class="today-run-track" style="--for: var(--${gods.useful}-bg); --against: var(--${gods.unfavourable}-bg)">${answer.run.map((day) => `
          <button type="button" class="today-run-day band-${esc(day.band)}${day.date === state.day ? ' is-selected' : ''}${day.date === today ? ' is-today' : ''}" data-today-day="${esc(day.date)}"
            ${day.date === state.day ? 'aria-current="date"' : ''} aria-label="${esc(t('today_run_day', { day: shortDate(day.date), pillar: `${day.pillar.stem.pinyin} ${day.pillar.branch.pinyin}`, pull: pull(day) }))}">
            <span class="today-run-bar ${day.score < 0 ? 'is-against' : 'is-for'}" style="--size: ${Math.min(Math.abs(day.score) / SCALE, 1).toFixed(3)}" aria-hidden="true"></span>
            <span class="today-run-number" aria-hidden="true">${esc(dayOfMonth(day.date))}</span>
            <span class="today-run-text" aria-hidden="true">
              <span class="today-run-date">${esc(shortDate(day.date))}</span>
              <span class="today-run-chars" lang="zh-Hant">${esc(day.pillar.stem.chinese + day.pillar.branch.chinese)}</span>
              <span class="today-run-pinyin">${esc(`${day.pillar.stem.pinyin} ${day.pillar.branch.pinyin}`)}</span>
              <span class="today-run-mark"></span>
              <span class="today-run-score">${esc(score(day.score))}</span>
              <span class="today-run-band">${esc(bandName(day.band))}</span>
            </span>
          </button>`).join('')}</div>`;
    };

    // ── The four pillars, at noon where you are, each as the chart's cards ──
    const tenGodOf = (layer) => layer.ten_gods.find((god) => god.role === 'stem');
    const luckYears = (span) => `${span.start_utc.slice(0, 4)}–${span.end_utc.slice(0, 4)}`;
    const drawPillars = () => {
      pillarsNote.textContent = t('today_pillars_at_noon', { place: answer.place.city });
      pillars.innerHTML = LAYERS.map((name) => {
        const layer = answer.layers[name];
        if (layer === null) {
          return `<article class="today-pillar is-empty" data-layer="${name}">
            <h3 class="today-pillar-name">${esc(layerName(name))}</h3>
            <p class="today-pillar-none">${esc(t('today_no_luck'))}</p>
          </article>`;
        }
        const god = tenGodOf(layer);
        // By phase, a luck pillar's stem rests in its branch phase, as the chart draws it.
        const resting = name === 'luck' && answer.schools.transits === 'phases' && layer.luck?.phase === 'branch';
        const luck = layer.luck === null ? ''
          : `<p class="today-pillar-luck">${esc(t('today_luck_span', { years: luckYears(layer.luck), phase: t('today_phase_' + layer.luck.phase) }))}</p>`;
        return `<article class="today-pillar" data-layer="${name}">
          <h3 class="today-pillar-name">${esc(layerName(name))}</h3>
          <button type="button" class="today-pillar-open${resting ? ' is-stem-resting' : ''}" data-today-topic="pillar/${name}" aria-expanded="${state.topic === `pillar/${name}`}" aria-controls="today-panel">
            ${cards(layer.pillar, 'small')}
          </button>
          <p class="today-pillar-god">${esc(god ? t('ten_god_' + god.ten_god) : '')}</p>
          <p class="today-pillar-pull band-${esc(layer.pull.band)}"><span class="today-band-mark" aria-hidden="true"></span>${esc(pull(layer.pull))}</p>
          <span class="today-pillar-scale" aria-hidden="true">${track([[layer.pull.score, 'layer']], answer.favourable.gods, 'mini')}</span>
          ${luck}
        </article>`;
      }).join('');
    };

    // ── The couple: both sides' pulls on the same day, on one neutral scale (each chart's
    // own elements differ), and whether the day pulls them apart, as the API says ──
    const drawCouple = () => {
      const m = answer.marriage;
      couple.classList.toggle('hidden', m === null);
      if (m === null) {
        couple.replaceChildren();
        return;
      }
      const partner = shownSettings === null ? null : partnerOf(shownSettings);
      if (partner === null) throw new Error(t('today_answer_error'));
      const sides = state.who === 'partner'
        ? [[partnerName(partner), answer.layers.day.pull], [t('today_self'), m.partner.pull]]
        : [[t('today_self'), answer.layers.day.pull], [partnerName(partner), m.partner.pull]];
      couple.innerHTML = `<h3 id="today-couple-title" class="today-section-title">${esc(t('today_couple'))}</h3>
        <div class="today-couple-day">${cards(answer.layers.day.pillar, 'small')}</div>
        <ul class="today-couple-sides">${sides.map(([name, value], index) => `<li class="today-couple-side is-${index === 0 ? 'first' : 'second'}">
            <span class="today-couple-key" aria-hidden="true"></span>
            <span class="today-couple-name">${esc(name)}</span>
            <span class="today-pillar-pull band-${esc(value.band)}"><span class="today-band-mark" aria-hidden="true"></span>${esc(pull(value))}</span>
          </li>`).join('')}</ul>
        <span class="today-couple-scale" aria-hidden="true">${track([[sides[0][1].score, 'first'], [sides[1][1].score, 'second']])}</span>
        <p class="today-couple-apart">${esc(t(m.pull_apart ? 'today_pull_apart' : 'today_pull_not_apart'))}</p>`;
    };

    // ── In your chart: each relationship, and on the main page the pillars it joins: the
    // day's own for its member of this day, month, year or luck pillar, the chart's own
    // (answer.natal) for its members in the chart, each member outlined on its card ──
    const memberPillar = (member) => {
      const pillar = FIFTH[member.pillar] ? answer.layers[FIFTH[member.pillar]]?.pillar : answer.natal[member.pillar];
      if (!pillar) throw new Error(t('today_answer_error'));
      return pillar;
    };
    const relationshipFigure = (r) => `<span class="today-relationship-figure" aria-hidden="true">${r.members.map((member) => `<span class="today-member-pillar">
        <span class="today-member-place">${esc(placeName(member.pillar))}</span>${cards(memberPillar(member), 'tiny', member.char)}
      </span>`).join('<span class="today-relationship-link"></span>')}</span>`;
    const relationshipItem = (r, figure = false) => `<li class="today-relationship" data-relationship="${esc(r.id)}">
        <span class="today-relationship-kind">${esc(relationshipName(r.kind))}</span>
        <span class="today-relationship-members">${r.members.map((m) => `<span class="today-member"><span lang="zh-Hant">${esc(m.char)}</span> ${esc(m.pinyin)} · ${esc(placeName(m.pillar))}</span>`).join('')}</span>
        ${figure ? relationshipFigure(r) : ''}
        ${r.line ? `<span class="today-relationship-line">${esc(r.line)}</span>` : ''}
      </li>`;
    const drawInChart = () => {
      const all = LAYERS.flatMap((name) => (answer.layers[name]?.relationships ?? []));
      const partner = shownSettings === null ? null : partnerOf(shownSettings);
      const title = state.who === 'partner' && partner !== null
        ? t('today_in_chart_of', { name: partnerName(partner) }) : t('today_in_chart');
      inChart.innerHTML = `<h3 id="today-in-chart-title" class="today-section-title">${esc(title)}</h3>
        ${all.length ? `<ul class="today-relationships">${all.map((r) => relationshipItem(r, true)).join('')}</ul>`
          : `<p class="settings-note">${esc(t('today_in_chart_none'))}</p>`}`;
    };

    // ── The hours: a dial of the twelve double hours, by branch (Zi at the top, clockwise),
    // in their elements' colours, each with its call's mark; and the table, which says it
    // all (the dial is a picture of it). The hour the clock is in now, on today, is
    // outlined on the dial, and named "now" in its table row, the current time. ──
    const DIAL = 240;
    const dial = () => {
      const centre = DIAL / 2;
      const outer = 116;
      const inner = 58;
      const point = (degrees, radius) => {
        const angle = (degrees * Math.PI) / 180;
        return [centre + radius * Math.cos(angle), centre + radius * Math.sin(angle)].map((v) => v.toFixed(2)).join(' ');
      };
      const isNow = (hour) => answer.hours.indexOf(hour) === clockDrawn.hour;
      const mark = (call, x, y) => {
        if (call === 'protect') return `<circle class="today-dial-call" cx="${x}" cy="${y}" r="4"/>`;
        if (call === 'mixed') return `<rect class="today-dial-call" x="${(x - 5).toFixed(2)}" y="${(y - 1).toFixed(2)}" width="10" height="2"/>`;
        if (call === 'avoid') return `<rect class="today-dial-call" x="${(x - 4).toFixed(2)}" y="${(y - 4).toFixed(2)}" width="8" height="8"/>`;
        return '';
      };
      const wedges = answer.hours.map((hour, index) => {
        const middle = index * 30 - 90;
        const [from, to] = [middle - 14.4, middle + 14.4];
        const at = (radius) => point(middle, radius).split(' ').map(Number);
        // The branch over its pinyin, upright, in the wedge's outer part; the call's mark
        // nearer the middle.
        const [lx, ly] = at(92);
        const [cx, cy] = at(67);
        return `<g class="today-dial-hour ${esc(hour.element)}${isNow(hour) ? ' is-now' : ''}">
          <path d="M ${point(from, outer)} A ${outer} ${outer} 0 0 1 ${point(to, outer)} L ${point(to, inner)} A ${inner} ${inner} 0 0 0 ${point(from, inner)} Z"/>
          <text class="today-dial-glyph" x="${lx.toFixed(2)}" y="${(ly - 7).toFixed(2)}" lang="zh-Hant">${esc(hour.branch)}</text>
          <text class="today-dial-pinyin" x="${lx.toFixed(2)}" y="${(ly + 10).toFixed(2)}">${esc(hour.pinyin)}</text>
          ${mark(hour.call, Number(cx.toFixed(2)), Number(cy.toFixed(2)))}
        </g>`;
      }).join('');
      const current = answer.hours.find(isNow);
      return `<svg class="today-dial" viewBox="0 0 ${DIAL} ${DIAL}" aria-hidden="true">${wedges}
        ${current ? `<g class="today-dial-now"><text class="today-dial-now-label" x="${centre}" y="${centre - 6}">${esc(t('today_hour_now'))}</text>
          <text class="today-dial-now-hour" x="${centre}" y="${centre + 14}"><tspan lang="zh-Hant">${esc(current.branch)}</tspan> ${esc(current.pinyin)}</text></g>` : ''}
      </svg>`;
    };
    const drawHours = () => {
      hours.innerHTML = `<h3 id="today-hours-title" class="today-section-title">${esc(t('today_hours'))}</h3>
        <p class="settings-note">${esc(t('today_hours_note', { place: answer.place.city }))}</p>
        <div class="today-hours-body">
          ${dial()}
          <table class="today-hours">
            <thead><tr>
              <th scope="col">${esc(t('today_hour'))}</th>
              <th scope="col">${esc(t('today_hour_time'))}</th>
              <th scope="col">${esc(t('today_hour_ties'))}</th>
              <th scope="col">${esc(t('today_hour_call'))}</th>
            </tr></thead>
            <tbody>${answer.hours.map((hour, index) => `<tr class="${hour.call === null ? '' : `call-${esc(hour.call)}`}"${index === clockDrawn.hour ? ' aria-current="time"' : ''}>
              <th scope="row"><span lang="zh-Hant">${esc(hour.branch)}</span> ${esc(hour.pinyin)} · ${esc(t('animal_' + hour.sign.toLowerCase()))}${index === clockDrawn.hour ? ` <span class="today-hour-now">· ${esc(t('today_hour_now'))}</span>` : ''}</th>
              <td>${hour.spans.map((span) => `${esc(clock(span.start))}–${esc(clock(span.end))}`).join('<br>')}</td>
              <td>${esc(hour.ties.map(tieName).join(', ') || '—')}</td>
              <td>${hour.call === null ? '—' : `<span class="today-call-mark" aria-hidden="true"></span>${esc(t('today_call_' + hour.call))}`}</td>
            </tr>`).join('')}</tbody>
          </table>
        </div>`;
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
        ${layer.relationships.length ? `<ul class="today-relationships">${layer.relationships.map((r) => relationshipItem(r)).join('')}</ul>` : ''}
        ${readingOf(name, layer)}
      </section>`;
    };
    const palace = (title, place) => `<h4 class="today-detail-subtitle">${esc(title)} · <span lang="zh-Hant">${esc(place.branch)}</span> ${esc(place.pinyin)}</h4>
      ${place.relationships.length ? `<ul class="today-relationships">${place.relationships.map((r) => relationshipItem(r)).join('')}</ul>`
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
          ${m.partner_chart.length ? `<ul class="today-relationships">${m.partner_chart.map((r) => relationshipItem(r)).join('')}</ul>`
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
    const drawPanel = () => window.EC_MOTION.layout(view, () => {
      const open = state.topic !== null;
      detail.classList.toggle('hidden', !open);
      if (open) detail.innerHTML = topicMarkup(state.topic);
      if (open) view.classList.add('has-panel');
      window.EC_MOTION.panel(panel, open);
      if (!open) view.classList.remove('has-panel');
      if (!open) window.EC_MOTION.retire(detail);
    }, ':scope > .chart-column');
    panel.addEventListener('click', (event) => {
      if (event.target.closest('[data-close-today-panel]')) closeTopic();
    });
    const closeTopic = () => {
      if (state === null || state.topic === null) return;
      const opener = view.querySelector(`[data-today-topic="${state.topic}"]`);
      move({ topic: null }, 'pushState');
      opener?.focus();
    };

    // ── The clock: today where you are, and the hour of the day shown that it is in, on
    // today alone (-1 for none). While a day is drawn, what the page says of them follows
    // the clock past midnight and each hour's end (the bar's Today, the run's dot, the
    // dial's "now"), looked at every half minute and when the page is seen again. ──
    const clockAt = () => {
      const today = todayAt(answer.place.timezone);
      const time = Date.now();
      const hour = answer.date !== today ? -1
        : answer.hours.findIndex((h) => h.spans.some((span) => Date.parse(span.start) <= time && time < Date.parse(span.end)));
      return { today, hour };
    };
    const followClock = () => {
      if (answer === null) return;
      const now = clockAt();
      if (now.today === clockDrawn.today && now.hour === clockDrawn.hour) return;
      clockDrawn = now;
      keepingFocus(() => {
        drawBar();
        run.querySelectorAll('[data-today-day]').forEach((button) => button.classList.toggle('is-today', button.dataset.todayDay === now.today));
        drawHours();
      });
    };
    window.setInterval(followClock, 30 * 1000);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') followClock();
    });

    const draw = () => {
      clockDrawn = clockAt();
      drawBar();
      drawTopics();
      drawDays();
      drawRun();
      drawScale();
      drawPillars();
      drawCouple();
      drawInChart();
      drawHours();
      drawPanel();
      body.classList.remove('hidden');
    };
    // Drawing replaces the page's buttons: the one that had focus hands it to its
    // counterpart in the new markup (the same topic, day or action), or, gone, to the
    // day's heading, so that focus stays on the page and its keys keep working.
    const COUNTERPARTS = [['todayTopic', 'data-today-topic'], ['todayDay', 'data-today-day'], ['todayAction', 'data-today-action']];
    // A control can take focus while it is in the page, shown and enabled.
    const focusable = (node) => node.isConnected && !node.closest('.hidden') && !node.disabled;
    const keepingFocus = (change) => {
      const focused = view.contains(document.activeElement) ? document.activeElement : null;
      change();
      if (focused === null || (document.activeElement === focused && focusable(focused))) return;
      const pair = COUNTERPARTS.find(([key]) => focused.dataset?.[key] !== undefined);
      const counterpart = pair ? view.querySelector(`[${pair[1]}="${CSS.escape(focused.dataset[pair[0]])}"]`) : null;
      (counterpart !== null && focusable(counterpart) ? counterpart : dateHeading).focus();
    };
    // The day is copied as text and printed only once its own answer is drawn. Until
    // then the two say they are unavailable, and keep their focus.
    const ready = (yes) => {
      for (const button of [copyText, printButton]) button.setAttribute('aria-disabled', String(!yes));
    };
    // Says what the page shows instead of the day, with what can be done: the day before
    // it, and its open topic, are no longer shown.
    const instead = (text, actions) => keepingFocus(() => {
      // An answer that could not be drawn is neither copied as text nor printed.
      answer = null;
      body.classList.add('hidden');
      // No run is drawn: steps are calendar days again.
      daysRun = null;
      cancelDrag();
      clearDays();
      panel.classList.add('hidden');
      view.classList.remove('has-panel');
      detail.innerHTML = '';
      sayNotice(text, actions);
    });

    // Shows the day a state names: the settings are read again, then the API asked. Until
    // its answer is drawn, the day is neither copied as text nor printed.
    const show = async (next) => {
      if (!DAY_PATH.test(next.day) || (next.topic !== null && !TOPIC_PATH.test(next.topic))) throw new Error(t('today_answer_error'));
      const before = state?.day ?? null;
      // A drag under way began on the day shown: another day shown (by a key or a pick)
      // cancels it, so the old gesture never moves the new day.
      if (before !== next.day) cancelDrag();
      state = next;
      answer = null;
      // The run drawn stands for its own reading alone: for another chart, language or
      // person, the days wait for its own answer, and steps until then are calendar days.
      if (daysRun !== null && daysReading !== reading(next)) {
        daysRun = null;
        cancelDrag();
      }
      // The days move at once, from the run drawn; the rest waits, dimmed, for the day's
      // own answer.
      if (before !== null && before !== next.day && layDays(next.day, next.day > before ? 1 : -1)) markRun(next.day);
      ready(false);
      const mine = ++asked;
      view.classList.remove('hidden');
      view.setAttribute('aria-busy', 'true');
      keepingFocus(() => {
        clearNotice();
        drawBar();
      });
      try {
        const kept = await settings.load(() => mine === asked);
        if (mine !== asked) return;
        shownSettings = kept;
        keepingFocus(drawBar);
        if (!state.chart.gender) {
          instead(t('today_needs_gender'), [['edit', t('edit_chart')]]);
          return;
        }
        if (kept.place === null) {
          instead(t('today_needs_place'), [['settings', t('settings_open')]]);
          return;
        }
        // The partner in view (#98): the one the address names, else the first couple's
        // partner, written into the address. A chart named that is not one of this
        // chart's partners in this account, or no longer charts, is never swapped for
        // another.
        const partners = partnersOf(kept);
        if (state.partner === null && partners.length > 0) {
          state = { ...state, partner: partners[0].id };
          go(address(state), 'replaceState');
          keepingFocus(drawBar);
        }
        const partner = partnerOf(kept);
        let gone = null;
        if (partner === null && (state.who === 'partner' || state.partner !== null)) {
          if (state.who === 'partner') {
            instead(partnerGone(kept), [['self', t('today_self')], ['settings', t('settings_open')]]);
            return;
          }
          // On this chart's own day the day is read without a couple, and the page says
          // why; With offers its partners.
          gone = partnerGone(kept);
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
          instead(typeof value?.detail === 'string' ? value.detail : t('today_answer_error'), [['retry', t('today_retry')]]);
          return;
        }
        const reply = checked(value);
        // Marriage is read exactly when a partner's chart is sent with the day.
        if ((partner === null) !== (reply.marriage === null)) throw new Error(t('today_answer_error'));
        if (state.topic === 'marriage' && reply.marriage === null) {
          // The partner's chart was removed, or no longer charts, since Marriage was
          // opened: it is no longer one of the day's topics, and the page says why.
          state = { ...state, topic: null };
          go(address(state), 'replaceState');
          gone = gone ?? partnerGone(kept);
        }
        answer = reply;
        keepingFocus(draw);
        ready(true);
        if (state.who === 'partner') sayNotice(t('today_partner_note', { name: partnerName(partner), place: kept.place.city }));
        else if (gone !== null) sayNotice(gone);
        status.textContent = t('today_status', { day: longDate(state.day), pull: pull(answer.layers.day.pull) });
      } catch (err) {
        if (mine !== asked) return;
        console.error(err);
        instead(err.message || t('today_answer_error'), [['retry', t('today_retry')]]);
      } finally {
        if (mine === asked) view.removeAttribute('aria-busy');
      }
    };
    const hide = () => {
      asked += 1;
      state = null;
      answer = null;
      // The settings may change meanwhile: the run drawn with them no longer leads steps.
      daysRun = null;
      cancelDrag();
      view.classList.add('hidden');
      view.removeAttribute('aria-busy');
    };
    // Nothing of the settings read for the account, nor of the day drawn with them, is
    // left on the page.
    const clear = () => {
      shownSettings = null;
      answer = null;
      ready(false);
      dateHeading.textContent = '';
      chartLine.textContent = '';
      partnerLabel.textContent = '';
      whoSwitch.classList.add('hidden');
      partnerChoice.classList.add('hidden');
      partnerSelect.replaceChildren();
      partnerChoices = '';
      clearNotice();
      body.classList.add('hidden');
      for (const part of [pullLine, topics, run, scale, pillarsNote, pillars, couple, inChart, hours]) part.replaceChildren();
      couple.classList.add('hidden');
      daysRun = null;
      cancelDrag();
      clearDays();
      panel.classList.add('hidden');
      view.classList.remove('has-panel');
      detail.replaceChildren();
      status.textContent = '';
    };

    // ── The controls ──
    steps.addEventListener('click', (event) => {
      if (state === null) return;
      const step = event.target.closest('[data-today-step]');
      if (step) move({ day: stepped(Number(step.dataset.todayStep)) });
      else if (event.target.closest('[data-today-now]') && shownSettings?.place) move({ day: todayAt(shownSettings.place.timezone) });
    });
    // The days: a press on a neighbour picks it; Left and Right step, Home and End go to
    // the run's first and last day, while the days have focus (a held key steps once).
    daysTrack.addEventListener('click', (event) => {
      const chosen = event.target.closest('[data-today-pick]');
      if (chosen && state !== null && chosen.dataset.todayPick !== state.day) move({ day: chosen.dataset.todayPick });
    });
    days.addEventListener('keydown', (event) => {
      if (state === null || event.metaKey || event.ctrlKey || event.altKey || event.repeat) return;
      let day = null;
      if (event.key === 'ArrowLeft') day = stepped(-1);
      else if (event.key === 'ArrowRight') day = stepped(1);
      else if (event.key === 'Home' && daysRun !== null) day = daysRun[0].date;
      else if (event.key === 'End' && daysRun !== null) day = daysRun.at(-1).date;
      else return;
      event.preventDefault();
      if (day !== state.day) move({ day });
    });
    // A swipe or drag on the days moves them with the pointer that started it, once it
    // has gone 40px across (more than a touch hold's 10px), and not from the screen's left
    // edge, which is iOS's Back. Let go, the day steps by as many days as it went, one at
    // least; let go within 40px of where it started, it moves nothing. Vertical scrolling
    // stays the page's (touch-action: pan-y). A cancel or a lost capture moves nothing. A
    // press that went more than 10px, a drag's or not, opens nothing when let go. Another
    // pointer pressed with it, of any kind (a touch during a mouse's drag too), spoils
    // it: nothing moves, and no click opens a day until a press starts alone.
    //
    // The pointers pressed on the days and not yet let go, with their kinds. A primary
    // pointer is the only one of its kind down: another of its kind still kept was let go
    // where its release was not seen.
    const down = new Map();
    // Whether a click on the days opens nothing: from the release of a press that went
    // more than 10px, or from a second pointer pressed, until the next press starts alone.
    // A press's click comes after its release, in the same task or (a touch's tap) later.
    let swallowing = false;
    daysTrack.addEventListener('pointerdown', (event) => {
      if (event.isPrimary) {
        for (const [id, kind] of down) if (kind === event.pointerType) down.delete(id);
      }
      down.set(event.pointerId, event.pointerType);
      if (down.size > 1) {
        dropDrag();
        swallowing = true;
        return;
      }
      swallowing = false;
      dropDrag();
      if (event.button !== 0) return;
      // Every press is followed, so that one that went more than 10px opens nothing; it
      // drags only while a run is drawn (not while another reading's is on its way), and
      // not from the screen's left edge. A day is as wide as its box is laid out, before
      // the scale of a neighbour or of a slide under way.
      const width = daysTrack.querySelector('.today-day')?.offsetWidth ?? 0;
      drag = {
        id: event.pointerId, x: event.clientX, y: event.clientY, moving: false, still: true, vertical: false,
        width, drags: state !== null && daysRun !== null && width > 0 && event.clientX >= 24,
      };
    });
    // Followed wherever it goes, off the days too: a press that went out more than 10px
    // and came back is no press either.
    window.addEventListener('pointermove', (event) => {
      if (drag === null || event.pointerId !== drag.id || drag.vertical) return;
      const dx = event.clientX - drag.x;
      if (!drag.moving) {
        const dy = event.clientY - drag.y;
        if (Math.max(Math.abs(dx), Math.abs(dy)) > 10) drag.still = false;
        // Up or down first: the page scrolls, and this is no drag.
        if (Math.abs(dy) > Math.max(Math.abs(dx), 10)) {
          drag.vertical = true;
          return;
        }
        if (!drag.drags || Math.abs(dx) < DRAG) return;
        drag.moving = true;
        dayNodes.forEach((node) => window.EC_MOTION.cancel(node, 'day'));
        daysTrack.setPointerCapture(drag.id);
        days.classList.add('is-dragging');
      }
      days.style.setProperty('--drag', `${dx}px`);
    });
    daysTrack.addEventListener('pointerup', (event) => {
      if (drag === null || event.pointerId !== drag.id) return;
      const { moving, still, width } = drag;
      const dx = event.clientX - drag.x;
      dropDrag();
      if (!still) swallowing = true;
      if (!moving || Math.abs(dx) < DRAG || state === null) return;
      const by = Math.max(1, Math.round(Math.abs(dx) / width)) * (dx < 0 ? 1 : -1);
      const day = stepped(by);
      if (day !== state.day) move({ day });
    });
    for (const type of ['pointercancel', 'lostpointercapture']) {
      daysTrack.addEventListener(type, (event) => {
        if (drag === null || event.pointerId !== drag.id) return;
        if (!drag.still) swallowing = true;
        dropDrag();
      });
    }
    // A pointer let go anywhere is no longer down; let go off the days (a mouse beside
    // them, before its drag began), its press ends there.
    for (const type of ['pointerup', 'pointercancel']) {
      window.addEventListener(type, (event) => {
        down.delete(event.pointerId);
        if (drag !== null && event.pointerId === drag.id) dropDrag();
      });
    }
    daysTrack.addEventListener('click', (event) => {
      if (swallowing) event.stopImmediatePropagation();
    }, true);
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
    // Another partner chosen: its couple is the one read, from the side shown, with the
    // topic left open.
    partnerSelect.addEventListener('change', () => {
      const chosen = partnerSelect.value;
      if (state !== null && chosen !== '' && chosen !== shownPartnerId()) move({ partner: chosen });
    });
    languageSwitch.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-today-lang]');
      if (!button || state === null || button.dataset.todayLang === state.lang) return;
      onLanguage(button.dataset.todayLang);
      move({ lang: button.dataset.todayLang });
    });
    pageSwitch.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-page="chart"]');
      if (button && state !== null) onChart(chartLink(state));
    });
    settingsButton.addEventListener('click', () => onSettings());
    printButton.addEventListener('click', () => {
      if (answer !== null) window.print();
    });
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
      const partner = shownSettings === null ? null : partnerOf(shownSettings);
      const other = state.who === 'partner' ? t('today_self') : (partner === null ? null : partnerName(partner));
      const lines = [
        `${longDate(state.day)} · ${chartLine.textContent}`,
        t('today_schools_used', { schools: Object.values(answer.schools).join(', ') }),
        t('today_pull_line', { pull: pull(answer.layers.day.pull) }),
        GODS.map((god) => godLine(god, answer.favourable.gods[god])).join(' · '),
        ...LAYERS.map((name) => {
          const layer = answer.layers[name];
          if (layer === null) return `${layerName(name)}: ${t('today_no_luck')}`;
          const { stem, branch } = layer.pillar;
          return `${layerName(name)}: ${stem.chinese}${branch.chinese} ${stem.pinyin} ${branch.pinyin} · ${pull(layer.pull)}`;
        }),
        ...(answer.marriage === null ? [] : [
          `${other}: ${pull(answer.marriage.partner.pull)} · ${t(answer.marriage.pull_apart ? 'today_pull_apart' : 'today_pull_not_apart')}`,
        ]),
        `${t('today_run_label')}:`,
        ...answer.run.map((day) => `  ${shortDate(day.date)} ${day.pillar.stem.chinese}${day.pillar.branch.chinese} · ${pull(day)}`),
        `${t('today_hours')}:`,
        ...answer.hours.map((hour) => `  ${hour.branch} ${hour.pinyin} ${hour.spans.map((s) => `${clock(s.start)}–${clock(s.end)}`).join(', ')}${hour.call === null ? '' : ` · ${t('today_call_' + hour.call)}`}`),
      ];
      return lines.join('\n');
    };
    copyText.addEventListener('click', async () => {
      if (answer === null) return;
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
      if (state === null || event.metaKey || (event.ctrlKey && !event.altKey) || event.repeat) return false;
      const plain = !event.ctrlKey && !event.altKey;
      if (event.key === '[') move({ day: stepped(-1) });
      else if (event.key === ']') move({ day: stepped(1) });
      else if (plain && event.key.toLowerCase() === 'n' && shownSettings?.place) move({ day: todayAt(shownSettings.place.timezone) });
      else if (event.key === 'Escape' && state.topic !== null) closeTopic();
      else return false;
      return true;
    };
    // What Today offers to the commands (⌘K), as its controls name them.
    const commands = () => {
      if (state === null) return [];
      const list = [
        { label: t('today_previous'), run: () => move({ day: stepped(-1) }), icon: 'chevron-left' },
        { label: t('today_next'), run: () => move({ day: stepped(1) }), icon: 'chevron-right' },
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
        { label: t('page_chart'), run: () => onChart(chartLink(state)), icon: 'columns-4' },
        { label: t('copy_link'), run: () => copyLink.click(), icon: 'link-2' },
      );
      // The day as text and on paper, once its answer is drawn.
      if (answer !== null) {
        list.push(
          { label: t('copy_text'), run: () => copyText.click(), icon: 'clipboard-list' },
          { label: t('print'), run: () => window.print(), icon: 'printer' },
        );
      }
      list.push({ label: t('settings_open'), run: () => onSettings(), icon: 'settings' });
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
      // A sign-out forgets the settings read for the account and leaves nothing of its day
      // on the page.
      forget: () => {
        hide();
        clear();
      },
      // Another account taken in this browser: the day drawn with the settings of the one
      // before (its place, its schools, its couple) goes, shown or hidden, so that Today
      // opened again draws nothing of it; shown, the day is asked for again with this
      // account's. The partner in view was the account before's: it goes from the address,
      // and this account's first couple's partner is written in instead.
      renew: () => {
        const next = state === null ? null : { ...state, partner: null };
        keepingFocus(clear);
        if (next !== null) {
          go(address(next), 'replaceState');
          show(next);
        }
      },
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
  window.EC_TODAY = { create, address, TOPIC_PATH, DAY_PATH };
})();
