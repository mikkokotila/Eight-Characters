// The two profiles every suite runs in: a desktop and a touch-enabled phone. EC_PROFILE,
// when set, names the one to run: tests/run_checks.py runs each profile of a suite in a
// process of its own, beside the others. Unset, a suite runs both, one after the other.
import assert from 'node:assert/strict';
import { describe } from 'node:test';

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
