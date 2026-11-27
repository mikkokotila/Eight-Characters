// The two profiles every suite runs in: a desktop and a touch-enabled phone. EC_PROFILE,
// when set, names the one to run: tests/run_checks.py runs each profile of a suite in a
// process of its own, beside the others. Unset, a suite runs both, one after the other.
// EC_PART, as k/n, runs the k-th of every n tests: the runner runs the profiles of its
// longest suites in parts, beside each other. Unset, every test runs.
import assert from 'node:assert/strict';
import { describe, it as test } from 'node:test';

const ALL = [
  { name: 'desktop', viewport: { width: 1440, height: 1000 }, hasTouch: false, isMobile: false },
  { name: 'mobile', viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true },
];
const only = process.env.EC_PROFILE;
assert.ok(only === undefined || ALL.some((profile) => profile.name === only),
  `EC_PROFILE names a profile (${ALL.map((profile) => profile.name).join(' or ')}), or is not set.`);

export const profiles = only === undefined ? ALL : ALL.filter((profile) => profile.name === only);

// The desktop profile: the tests outside a suite's profiles run in it, once (describeOnce).
export const desktop = ALL[0];

// A describe outside the profiles: it runs once, in the desktop profile, so in the
// desktop profile's process when the profiles run apart.
export function describeOnce(name, options, run) {
  if (only === undefined || only === desktop.name) describe(name, options, run);
}

const part = /^([1-9]\d*)\/([1-9]\d*)$/.exec(process.env.EC_PART ?? '1/1');
assert.ok(part && Number(part[1]) <= Number(part[2]), 'EC_PART is k/n, with k from 1 to n, or is not set.');
const [k, n] = [Number(part[1]), Number(part[2])];
let registered = 0;

// node:test's it, for the tests of this part: of every n the suite registers, in order,
// the k-th.
export function it(...args) {
  registered += 1;
  if ((registered - 1) % n === k - 1) test(...args);
}
