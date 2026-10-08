// The canon's taxonomy, read in the pages the chart already has. Each reading is one
// line, its passage's own first sentence, and the rest opens beneath it. The words are
// the canon's, as the API gives them: the engine chose them for this chart, and nothing
// here writes, shortens or rephrases them. The canon speaks English, so readings show
// only when the chart's language is English; otherwise every part of this is empty.
// The cards stay as they are.
(() => {
  const ORDER = ['year', 'month', 'day', 'hour'];
  const DISPLAY = ['hour', 'day', 'month', 'year'];
  const PLAIN = { year: 'Year', month: 'Month', day: 'Day', hour: 'Hour' };
  const ELEMENT = { wood: 'Wood', fire: 'Fire', earth: 'Earth', metal: 'Metal', water: 'Water' };
  const ANIMAL = {
    子: 'Rat', 丑: 'Ox', 寅: 'Tiger', 卯: 'Rabbit', 辰: 'Dragon', 巳: 'Snake',
    午: 'Horse', 未: 'Goat', 申: 'Monkey', 酉: 'Rooster', 戌: 'Dog', 亥: 'Pig',
  };
  // Each kind of relationship by its family in the canon, whose introduction says what
  // the kind is. The list's 'About' lines go by family, in the canon's sections' order;
  // each keeps the name its first kind gave it.
  const FAMILY_OF = {
    stem_combination: 'stem_combinations', branch_combination: 'six_harmonies', branch_clash: 'clashes',
    harmony_frame: 'three_harmonies', half_frame: 'three_harmonies', directional_combination: 'directional',
    punishment: 'punishments', half_punishment: 'punishments', self_punishment: 'punishments', harm: 'harms',
  };
  const ABOUT_FAMILY = [
    ['stem_combinations', 'about-stem_combination', 'About stem combinations'],
    ['six_harmonies', 'about-branch_combination', 'About the six harmonies'],
    ['clashes', 'about-branch_clash', 'About clashes'],
    ['three_harmonies', 'about-harmony_frame', 'About the three harmonies'],
    ['directional', 'about-directional_combination', 'About the directional combinations'],
    ['punishments', 'about-punishment', 'About punishments'],
    ['harms', 'about-harm', 'About harms'],
  ];
  // The chevron the branches use for their hidden stems.
  const CHEVRON = '<svg class="canon-line-chevron" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>';
  const NOTE = 'Readings quote the canon’s Taxonomy, after San Ming Tong Hui 三命通会. The chart chooses which apply; nothing in them assesses strength or predicts.';
  // The canon reads no luck position: a luck pillar reads as its stem and its branch do.
  const LUCK_NOTE = 'The canon has no passages for the luck position. These are its passages for this stem and this branch, read from the Day Master’s seat.';

  const create = ({ root, escape: esc, spot, roleName, go }) => {
    const panel = root.querySelector('#chart-panel');
    if (!panel || !spot || typeof roleName !== 'function' || typeof go !== 'function') {
      throw new Error('Readings view is incomplete.');
    }
    let reading = null;
    // The luck pillars' readings, decade by decade (luck_reading), or null.
    let luckReading = null;
    let chart = {};
    let serial = 0;
    // The kinds of reading that are open: they stay open on the next page that has them.
    const open = new Set();
    const fail = (what) => { throw new Error(`The chart's reading is incomplete: ${what}.`); };

    // The canon's arrow is drawn, as the page's other arrows are: the page fonts have
    // none. The words beside it say what it means, so assistive technology skips it.
    const arrows = (html) => html.replaceAll('→', '<span class="canon-arrow" aria-hidden="true"></span>');
    // The canon keeps two inline marks, emphasis and strong; everything else is text.
    const marks = (text) => arrows(esc(text)
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>'));
    // A sentence ends at its stop, or just after the closing quote that follows it.
    const sentences = (text) => text.split(/(?<=[.!?]["”]?)\s+/);
    const paragraphMarkup = (p) => `<p class="canon-text">${p.label === null ? '' : `<strong>${arrows(esc(p.label))}:</strong>${p.text ? ' ' : ''}`}${marks(p.text)}</p>`;
    // A link names its page in the app's words; `quote`, the canon's words there, follows.
    const link = (label, target, tokens = [], quote = null) => `<button type="button" class="canon-link" data-canon-go="${esc(target)}"${spot.attr(tokens)}>${esc(label)}${quote === null ? '' : `<span class="canon-link-quote">${marks(quote)}</span>`}</button>`;

    // A line: a key that names what it is, the passage's first sentence, and the rest of
    // the passage beneath, open while its kind is open. A single labelled paragraph gives
    // its label to the key.
    const line = ({ part, key, paragraphs, tokens = [], links = [], head = null, before = '' }) => {
      if (!paragraphs?.length) fail(part);
      const [first, ...others] = paragraphs;
      const labelled = first.label !== null;
      if (labelled && others.length) fail(`${part}: a labelled paragraph that does not stand alone`);
      if (!labelled && !key) fail(`${part}: its key`);
      const [lead, ...rest] = sentences(first.text);
      if (head === null && !lead) fail(`${part}: its first sentence`);
      const remainder = [...(rest.length ? [{ label: null, text: rest.join(' ') }] : []), ...others];
      serial += 1;
      const id = `canon-passage-${serial}`;
      const isOpen = open.has(part);
      return `
        <div class="canon-line" data-canon-part="${esc(part)}"${spot.attr(tokens)}>
          <button type="button" class="canon-line-toggle" aria-expanded="${isOpen}" aria-controls="${id}">
            <span class="canon-line-key">${arrows(esc(labelled ? first.label : key))}</span>
            <span class="canon-line-head">${head === null ? marks(lead) : arrows(esc(head))}</span>
            ${CHEVRON}
          </button>
          <div class="canon-line-passage" id="${id}"${isOpen ? '' : ' hidden'}>
            ${before}${(head === null ? remainder : paragraphs).map(paragraphMarkup).join('')}
            ${links.length ? `<p class="canon-links">${links.join('')}</p>` : ''}
          </div>
        </div>`;
    };
    const lines = (markup) => (markup ? `<div class="canon-lines">${markup}</div>` : '');
    // A relationship's name as the list names it (relationships.js).
    let relationshipLabel = null;
    const role = (name) => roleName(name);
    const element = () => ELEMENT[chart.day.stem.element];
    // The Day Master on a pillar's branch, each named with its character: 'Ren 壬 on Chen 辰'.
    const onBranch = (name) => `${chart.day.stem.pinyin} ${chart.day.stem.char} on ${chart[name].branch.pinyin} ${chart[name].branch.char}`;

    // ── What each page reads ──
    const pillar = (name) => {
      if (!reading) return '';
      const r = reading.pillars[name];
      const el = element();
      const stem = r.stem_reading;
      const touching = Object.entries(reading.relationships)
        .filter(([id]) => id.split(':')[2].split('-').includes(name));
      return lines([
        line({ part: 'lens', key: `Your ${el} in the ${PLAIN[name]}`, paragraphs: r.lens, tokens: [`stem:${name}`, `branch:${name}`] }),
        stem.kind === 'day_master'
          ? line({ part: 'stem', key: 'Who stands here · the Day Master', paragraphs: stem.paragraphs, tokens: ['stem:day'],
            links: [link(roleName('day_master'), 'day-master', ['stem:day'])] })
          : line({ part: 'stem', key: `Who stands here · ${role(stem.ten_god)}`, paragraphs: stem.paragraphs, tokens: [`stem:${name}`],
            links: [link(role(stem.ten_god), `roles/${stem.ten_god}`, [`stem:${name}`])] }),
        r.own_stage
          ? line({ part: 'own-stage', key: `${role(stem.ten_god)}’s own stage here · ${r.own_stage.name} ${r.own_stage.chinese}`,
            paragraphs: r.own_stage.paragraphs, tokens: [`stem:${name}`, `branch:${name}`] })
          : '',
        line({ part: 'ground', key: `The ground · ${ANIMAL[r.branch]}`, paragraphs: r.ground, tokens: [`branch:${name}`],
          links: (chart.gods[name]?.hidden_stems || []).map((h) => link(`${h.char} ${role(h.ten_god)}`, `roles/${h.ten_god}`, [`hidden:${name}:${h.char}`])) }),
        line({ part: 'ground-about', key: `About the ${ANIMAL[r.branch]}`, paragraphs: r.ground_about, tokens: [`branch:${name}`] }),
        line({ part: 'meets', key: name === 'day' ? `Your seat · ${onBranch(name)}` : `Your ${el} on this ground · ${onBranch(name)}`,
          paragraphs: r.meets, tokens: [`branch:${name}`] }),
        line({ part: 'stage', key: `Your ${el}’s stage here · ${r.stage.name} ${r.stage.chinese}`, paragraphs: r.stage.paragraphs, tokens: [`branch:${name}`],
          links: [link('The whole cycle', 'day-master#dm-cycle')] }),
        touching.length
          ? `<div class="canon-here"><p class="canon-line-key">Relationships here</p><p class="canon-links">${touching.map(([id, rel]) => link(
            relationshipLabel(id), `relationships/${id}`, [`arc:${id}`], rel.line)).join('')}</p></div>`
          : '',
        line({ part: 'about-pillar', key: 'About these readings', paragraphs: [...reading.branches_introduction, ...reading.day_master.grounds_introduction] }),
      ].join(''));
    };

    const relationship = (id) => {
      if (!reading) return '';
      const r = reading.relationships[id];
      if (!r) fail(`relationship ${id}`);
      return relationshipMarkup(id, r);
    };
    const relationshipMarkup = (id, r) => {
      const condition = r.condition
        ? `<p class="canon-condition">In this chart: born in the ${esc(chart.month.branch.pinyin)} month, in ${esc(r.condition.season)}. The entry reads <q>${marks(r.condition.sentence)}</q></p>`
        : '';
      // An entry's title is its characters, then its name: '子午冲 — Zi-Wu Clash (…)'.
      const parts = r.entry.title.split(' — ');
      if (parts.length !== 2) fail(`the title of ${id}`);
      const [title, subtitle] = parts;
      return lines([
        r.pairing ? line({ part: 'pairing', key: r.pairing.label, paragraphs: [{ label: null, text: r.pairing.text }], tokens: [`arc:${id}`] }) : '',
        r.with_day_master ? line({ part: 'with-day-master', paragraphs: [r.with_day_master], tokens: ['stem:day'] }) : '',
        r.neither_day_master ? line({ part: 'neither-day-master', paragraphs: [r.neither_day_master], tokens: [`arc:${id}`] }) : '',
        line({ part: 'entry', key: `${title} · ${subtitle}`, paragraphs: r.entry.paragraphs, tokens: [`arc:${id}`], before: condition }),
        r.dynamic ? line({ part: 'dynamic', paragraphs: [r.dynamic], tokens: [`arc:${id}`] }) : '',
        r.mechanics.length ? line({ part: 'mechanics', key: 'When a combination transforms', paragraphs: r.mechanics, tokens: [`arc:${id}`] }) : '',
      ].join(''));
    };
    // The meaning under a relationship's name in the list: the canon's sentence about its
    // own form, which the reading chooses (a pairing's first sentence, a half's own pair).
    const chipLine = (id) => {
      if (!reading) return '';
      const r = reading.relationships[id];
      if (!r) fail(`relationship ${id}`);
      if (typeof r.line !== 'string' || !r.line) fail(`the line of ${id}`);
      return `<span class="canon-chip-line">${marks(r.line)}</span>`;
    };
    // What each family of relationship in the list is.
    const relationshipsAbout = () => {
      if (!reading) return '';
      const found = Object.values(reading.relationships);
      found.forEach((r) => { if (!Object.hasOwn(FAMILY_OF, r.kind)) fail(`the kind ${r.kind}`); });
      return lines(ABOUT_FAMILY.filter(([family]) => found.some((r) => FAMILY_OF[r.kind] === family))
        .map(([family, part, key]) => line({
          part, key, paragraphs: found.find((r) => FAMILY_OF[r.kind] === family).introduction,
        })).join(''));
    };

    const rolesAbout = () => (reading
      ? lines(line({ part: 'about-roles', key: 'About the roles', paragraphs: reading.roles_introduction })) : '');
    const roleCore = (name) => {
      if (!reading) return '';
      const r = reading.roles[name];
      if (!r) fail(`the ${name} role`);
      // The app names the role; the canon's own name for it stays in its passages.
      return lines(line({ part: 'role-core', key: `What it is · ${r.relation}`, paragraphs: r.core }));
    };
    const roleStem = (name, pillarName) => {
      if (!reading) return '';
      // A role stands on the Year, Month or Hour stem; the canon reads it on each.
      const paragraphs = reading.roles[name]?.stems[pillarName];
      if (!paragraphs) fail(`the ${name} role on the ${pillarName} stem`);
      return lines(line({ part: 'role-stem', key: `On the ${PLAIN[pillarName]} stem`, paragraphs, tokens: [`stem:${pillarName}`] }));
    };
    const rootGround = (pillarName) => {
      if (!reading) return '';
      const r = reading.pillars[pillarName];
      return lines(line({ part: 'meets', key: pillarName === 'day' ? `Your seat · ${onBranch(pillarName)}` : `Your ${element()} on this ground · ${onBranch(pillarName)}`,
        paragraphs: r.meets, tokens: [`branch:${pillarName}`] }));
    };
    const season = () => {
      if (!reading) return '';
      const r = reading.pillars.month;
      return lines([
        line({ part: 'ground', key: `The ground · ${ANIMAL[r.branch]} in the Month`, paragraphs: r.ground, tokens: ['branch:month'] }),
        line({ part: 'ground-about', key: `About the ${ANIMAL[r.branch]}`, paragraphs: r.ground_about, tokens: ['branch:month'] }),
      ].join(''));
    };

    // The cycle: the Day Master's stage on each branch as one sentence, and the twelve
    // stages as a ring with this chart's branches on it.
    const ring = () => {
      const cycle = reading.day_master.cycle;
      const width = 360; const cx = width / 2; const cy = 0; const r = 96;
      const at = {};
      ORDER.forEach((name) => { const n = cycle.stages[name]; at[n] = [...(at[n] || []), name]; });
      const fixed = (value) => value.toFixed(1);
      // Each point's label reads away from the ring: its stage, its branch's pinyin and
      // character, and the pillars on it, one to a line. The measures suit the ring's
      // type, --text-1: a line's box runs `up` above its baseline and `down` below it.
      const line = 17; const up = 12; const down = 5; const gap = 4;
      // A label stands `off` from the centre: above its point at the top of the ring,
      // below it at the bottom, level with it on the sides.
      const off = r + 12;
      const labels = cycle.ring.map((stage) => {
        const angle = (-90 + (stage.stage - 1) * 30) * Math.PI / 180;
        const cos = Math.cos(angle); const sin = Math.sin(angle);
        const on = at[stage.stage] || [];
        const name = stage.name.replace("Emperor's ", '').replace('Approaching ', '');
        const lines = [
          { kind: `canon-ring-stage${on.length ? ' is-on' : ''}`, markup: esc(name) },
          { kind: `canon-ring-branch${on.length ? ' is-on' : ''}`, markup: `<tspan class="canon-ring-pinyin">${esc(stage.pinyin)}</tspan> <tspan class="canon-ring-char">${esc(stage.branch)}</tspan>` },
          ...on.map((p) => ({ kind: 'canon-ring-pillar', markup: esc(PLAIN[p].toUpperCase()) })),
        ];
        const height = line * (lines.length - 1) + up + down;
        const ideal = cy + off * sin - height * (1 - sin) / 2;
        return { cos, sin, on, lines, height, ideal, top: ideal, side: cos > 0.3 ? 'right' : cos < -0.3 ? 'left' : 'middle' };
      });
      // The labels down each side settle without overlapping, in the ring's order: each as
      // near its ideal as its neighbours allow. Labels that would overlap stack as a run,
      // touching, centred on their ideals.
      const stack = (run) => {
        const offsets = run.map((l, i) => run.slice(0, i).reduce((sum, above) => sum + above.height + gap, 0));
        const top = run.reduce((sum, l, i) => sum + l.ideal - offsets[i], 0) / run.length;
        run.forEach((l, i) => { l.top = top + offsets[i]; });
        return run;
      };
      const settle = (side) => {
        const runs = [];
        side.sort((a, b) => a.sin - b.sin).forEach((label) => {
          let run = [label];
          while (runs.length && runs.at(-1).at(-1).top + runs.at(-1).at(-1).height + gap > run[0].top) {
            run = stack([...runs.pop(), ...run]);
          }
          runs.push(run);
        });
      };
      settle(labels.filter((l) => l.side === 'right'));
      settle(labels.filter((l) => l.side === 'left'));
      // A label on a side keeps its nearest corner `off` from the centre, and keeps clear
      // of the labels at the top and the bottom of the ring.
      const aside = 36;
      const reach = (l) => {
        const near = Math.max(0, l.top - cy, cy - l.top - l.height);
        return Math.max(aside, Math.sqrt(Math.max(0, off ** 2 - near ** 2)));
      };
      const marksOnRing = labels.map((l) => {
        const x = { middle: cx, right: cx + reach(l), left: cx - reach(l) }[l.side];
        const anchor = { middle: 'middle', right: 'start', left: 'end' }[l.side];
        return `<g class="canon-ring-point"><circle cx="${fixed(cx + r * l.cos)}" cy="${fixed(cy + r * l.sin)}" r="${l.on.length ? 7 : 3.5}" class="${l.on.length ? 'canon-ring-on' : 'canon-ring-off'}"/>
          ${l.lines.map((ln, i) => `<text class="${ln.kind}" x="${fixed(x)}" y="${fixed(l.top + up + line * i)}" text-anchor="${anchor}">${ln.markup}</text>`).join('')}</g>`;
      }).join('');
      // As tall as its labels need.
      const top = Math.min(...labels.map((l) => l.top)) - gap;
      const bottom = Math.max(...labels.map((l) => l.top + l.height)) + gap;
      // The Day Master in the centre: its character over its pinyin, as a pillar is named.
      return `<svg class="canon-ring" viewBox="0 ${fixed(top)} ${width} ${fixed(bottom - top)}" role="img" aria-label="${esc(`The twelve stages of ${element()}, with this chart's branches on them`)}">
        <circle cx="${cx}" cy="${cy}" r="${r}" class="canon-ring-track"/>
        <text class="canon-ring-center" x="${cx}" y="${cy + 3}" text-anchor="middle"><tspan class="canon-ring-char">${esc(reading.day_master.stem)}</tspan><tspan class="canon-ring-pinyin" x="${cx}" dy="22">${esc(chart.day.stem.pinyin)}</tspan></text>${marksOnRing}</svg>`;
    };
    const dayMaster = () => {
      if (!reading) return '';
      const dm = reading.day_master;
      const el = element();
      const cycle = dm.cycle;
      const sentence = ORDER.map((name) => {
        const text = sentences(reading.pillars[name].stage.paragraphs[0].text)[0];
        return `<button type="button" class="canon-clause" data-canon-go="pillar/${name}#stage"${spot.attr([`branch:${name}`])}>${marks(text)}</button>`;
      }).join(' ');
      return lines([
        line({ part: 'dm-core', key: `What your ${el} is`, paragraphs: dm.core, tokens: ['stem:day'] }),
        line({ part: 'dm-grounds', key: `How your ${el} meets any ground`, paragraphs: dm.grounds, tokens: ['stem:day'] }),
        ...DISPLAY.map((name) => line({
          part: `dm-lens-${name}`, key: `${PLAIN[name]} · ${chart[name].stem.pinyin} ${chart[name].branch.pinyin} ${reading.pillars[name].stem}${reading.pillars[name].branch}`,
          paragraphs: reading.pillars[name].lens, tokens: [`stem:${name}`, `branch:${name}`],
          links: [link(`The ${PLAIN[name]} pillar`, `pillar/${name}#lens`, [`stem:${name}`, `branch:${name}`])],
        })),
        line({
          part: 'dm-cycle', key: `Where your ${el} is in its cycle`, head: ORDER.map((name) => reading.pillars[name].stage.name).join(' · '),
          paragraphs: cycle.narrative, before: `<p class="canon-sentence">${sentence}</p>${ring()}`,
        }),
        line({ part: 'dm-stages', key: 'The twelve stages', paragraphs: [...cycle.introduction, ...cycle.mapping_introduction] }),
        line({ part: 'dm-reconception', key: 'The pattern of reconception', paragraphs: cycle.reconception }),
        line({ part: 'about-lens', key: 'About these readings', paragraphs: dm.introduction }),
      ].join(''));
    };

    // ── The luck pillars (luck_reading) ──
    // A decade's reading: its stem's role, its branch, the Day Master on it and its stage
    // there, from the Day Master's seat. `branch` is the luck branch, char and pinyin.
    const luckDecade = (sequence) => {
      const decade = luckReading.decades.find((d) => d.sequence === sequence);
      if (!decade) fail(`luck pillar ${sequence}`);
      return decade;
    };
    const luckPage = (sequence, branch) => {
      if (!luckReading) return '';
      const d = luckDecade(sequence);
      const el = element();
      const dm = chart.day.stem;
      return lines([
        line({ part: 'luck-stem', key: `Its stem · ${role(d.stem.ten_god)}`, paragraphs: d.stem.core, tokens: ['stem:luck'] }),
        line({ part: 'luck-ground-about', key: `About the ${ANIMAL[branch.char]}`, paragraphs: d.branch.about, tokens: ['branch:luck'] }),
        line({ part: 'luck-meets', key: `Your ${el} on this ground · ${dm.pinyin} ${dm.char} on ${branch.pinyin} ${branch.char}`,
          paragraphs: d.branch.meets, tokens: ['branch:luck'] }),
        line({ part: 'luck-stage', key: `Your ${el}’s stage here · ${d.branch.stage.name} ${d.branch.stage.chinese}`,
          paragraphs: d.branch.stage.paragraphs, tokens: ['branch:luck'] }),
      ].join(''));
    };
    // What the canon waits for that this luck pillar brings: what waits in the natal chart,
    // and the canon's sentence. `labelOf` names a relationship, natal or the luck pillar's.
    const luckSettles = (sequence, labelOf) => {
      if (!luckReading) return '';
      return luckDecade(sequence).settles.map((s) => {
        const tokens = [...(s.natal === null ? [] : [`arc:${s.natal}`]), ...s.by.map((id) => `arc:${id}`)];
        const what = s.natal === null
          ? `This luck pillar brings the Peak the natal Birth and Storage wait for: ${s.by.map(labelOf).join(', ')}.`
          : `This luck pillar brings what the natal ${labelOf(s.natal)} waits for.`;
        return `<p class="canon-condition luck-settles" data-settles="${esc(s.source)}"${spot.attr(tokens)}>${esc(what)} The canon reads <q>${marks(s.sentence)}</q></p>`;
      }).join('');
    };
    // A relationship the luck pillar forms, read as its entry reads: no pairing, which the
    // canon gives for the natal positions only.
    const luckRelationshipOf = (sequence, id) => {
      const r = luckDecade(sequence).relationships[id];
      if (!r) fail(`luck relationship ${id}`);
      return r;
    };
    const luckLine = (sequence, id) => {
      if (!luckReading) return '';
      const r = luckRelationshipOf(sequence, id);
      if (typeof r.line !== 'string' || !r.line) fail(`the line of ${id}`);
      return `<span class="canon-chip-line">${marks(r.line)}</span>`;
    };
    const luckRelationship = (sequence, id) => (luckReading ? relationshipMarkup(id, luckRelationshipOf(sequence, id)) : '');

    // ── Opening, following, arriving ──
    const toggle = (button, force) => {
      const next = force ?? button.getAttribute('aria-expanded') !== 'true';
      button.setAttribute('aria-expanded', String(next));
      const passage = root.querySelector(`#${button.getAttribute('aria-controls')}`);
      if (!passage) fail('a passage');
      passage.hidden = !next;
      const part = button.closest('.canon-line').dataset.canonPart;
      if (next) open.add(part); else open.delete(part);
    };
    const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    // Brings a page's line into view and marks it a moment; `openIt` opens it too.
    const arrive = (section, part, openIt = false) => {
      const target = section.querySelector(`.canon-line[data-canon-part="${part}"]`);
      if (!target) return null;
      if (openIt) toggle(target.querySelector('.canon-line-toggle'), true);
      const top = target.getBoundingClientRect().top - panel.getBoundingClientRect().top + panel.scrollTop;
      panel.scrollTo({ top: Math.max(0, top - panel.clientHeight / 8), behavior: reduced() ? 'auto' : 'smooth' });
      root.querySelectorAll('.canon-line.is-arrived').forEach((node) => node.classList.remove('is-arrived'));
      void target.offsetWidth;
      target.classList.add('is-arrived');
      return target;
    };
    panel.addEventListener('click', (event) => {
      const button = event.target.closest('.canon-line-toggle');
      if (button) {
        toggle(button);
        return;
      }
      const target = event.target.closest('[data-canon-go]');
      if (!target) return;
      const [path, part] = target.dataset.canonGo.split('#');
      go(path, part || null);
    });

    const validate = (data, chartData, gods) => {
      if (!data || data.policy !== 'canon_taxonomy_v1' || data.language !== 'en') fail('its policy');
      if (!ORDER.every((name) => data.pillars?.[name])) fail('its pillars');
      // The ring names each of the twelve branches by its pinyin, as the chart names its own.
      const ring = data.day_master?.cycle?.ring;
      if (!Array.isArray(ring) || ring.length !== 12 || !ring.every((s, i) => s.stage === i + 1
        && typeof s.branch === 'string' && s.branch && typeof s.pinyin === 'string' && s.pinyin)) {
        fail('the ring');
      }
      DISPLAY.forEach((name, index) => {
        const p = chartData.pillars[index];
        const r = data.pillars[name];
        if (r.stem !== p.stem.char || r.branch !== p.branch.char) fail(`the ${name} pillar`);
        if (name !== 'day' && r.stem_reading.ten_god !== gods[name].stem.ten_god) fail(`the ${name} stem's role`);
        if (ring.find((s) => s.branch === p.branch.char)?.pinyin !== p.branch.pinyin) fail('the ring');
      });
      if (data.day_master.stem !== chartData.pillars[1].stem.char) fail('the Day Master');
    };
    // `data` is the API's reading, or null where none was asked for (Finnish); `luck` is
    // its luck pillars' reading, or null for a chart without them.
    const render = (data, chartData, gods, labelFor, luck = null) => {
      reading = null;
      luckReading = null;
      chart = {};
      relationshipLabel = labelFor;
      if (data === null) {
        if (luck !== null) fail('its luck pillars, without the chart\'s own');
        return;
      }
      validate(data, chartData, gods);
      reading = data;
      chart = Object.fromEntries(DISPLAY.map((name, index) => [name, chartData.pillars[index]]));
      chart.gods = gods;
      if (luck === null) return;
      if (luck.policy !== 'canon_taxonomy_v1' || luck.language !== 'en' || !Array.isArray(luck.decades)
        || !luck.decades.every((d, index) => d.sequence === index + 1 && d.stem && d.branch && d.relationships && Array.isArray(d.settles))) {
        fail('its luck pillars');
      }
      luckReading = luck;
    };

    return {
      render,
      has: () => reading !== null,
      note: () => (reading ? NOTE : ''),
      // The canon's own heading for the Day Master, e.g. '壬 Ren — Yang Water'.
      dayMasterTitle: () => (reading ? reading.day_master.title : ''),
      pillar,
      relationship,
      chipLine,
      luckPage,
      luckNote: () => (luckReading ? LUCK_NOTE : ''),
      luckSettles,
      luckLine,
      luckRelationship,
      relationshipsAbout,
      rolesAbout,
      roleCore,
      roleStem,
      rootGround,
      season,
      dayMaster,
      arrive,
    };
  };
  window.EC_READINGS = { create };
})();
