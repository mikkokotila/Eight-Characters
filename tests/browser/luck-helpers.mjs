// The luck pillars' sample chart, its link and its clock, for the suites that use them
// (luck.test.mjs, life.test.mjs).
import { engineName, openChart, settled, HELSINKI } from './chart-helpers.mjs';

// The design's sample: 14 August 1975, 07:45, Helsinki, female. Its luck pillars run
// forward from 乙酉 Yi You, the first at age 8. On 7 October 2026 the fifth, 己丑 Ji Chou,
// is in its stem phase, from 18 December 2023 to 18 December 2028.
const SAMPLE = { date: '1975-08-14', time: '07:45', place: HELSINKI, gender: 'female' };
const TODAY = new Date('2026-10-07T12:00:00Z');
// Characters, names, first and last year, and the age each starts at.
const DECADES = [
  ['乙酉', 'Yi You', 1983, 1993, 8], ['丙戌', 'Bing Xu', 1993, 2003, 18], ['丁亥', 'Ding Hai', 2003, 2013, 28],
  ['戊子', 'Wu Zi', 2013, 2023, 38], ['己丑', 'Ji Chou', 2023, 2033, 48], ['庚寅', 'Geng Yin', 2033, 2043, 58],
  ['辛卯', 'Xin Mao', 2043, 2053, 68], ['壬辰', 'Ren Chen', 2053, 2063, 78], ['癸巳', 'Gui Si', 2063, 2073, 88],
  ['甲午', 'Jia Wu', 2073, 2083, 98],
];
const sampleLink = (parts = {}) => `/#chart?${new URLSearchParams({
  date: SAMPLE.date, time: SAMPLE.time, place: HELSINKI.display, city: HELSINKI.city,
  latitude: String(HELSINKI.latitude), longitude: String(HELSINKI.longitude), timezone: HELSINKI.timezone,
  lang: 'en', gender: 'female', ...parts,
})}`;
// Safari moves Tab only between text fields and tab-indexed elements unless Full Keyboard
// Access is on; Option+Tab reaches every control (keyboard.test.mjs).
const TAB = engineName === 'webkit' ? 'Alt+Tab' : 'Tab';

async function openSample(page, options = {}, now = TODAY) {
  await page.clock.setFixedTime(now);
  return openChart(page, { ...SAMPLE, ...options });
}

// A part of the address, as the app wrote it: the topic open, or the gender.
function linkPart(page, name) {
  return page.evaluate((name) => new URLSearchParams(location.hash.split('?')[1] ?? '').get(name), name);
}

async function click(page, selector) {
  await page.locator(selector).click();
  await settled(page);
}

// The switch's With luck: the luck pillar shows, at the period chosen, with its ribbon
// and its life grid. A chart with a gender opens natal, without them.
async function showLuck(page) {
  await click(page, '#luck-switch [data-luck-show="on"]');
}

export { SAMPLE, TODAY, DECADES, sampleLink, TAB, openSample, linkPart, click, showLuck };
