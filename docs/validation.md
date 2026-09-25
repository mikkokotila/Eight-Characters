# Validation and Quality

## Automated Tests

Run all tests:

```bash
source venv/bin/activate
python -m unittest discover -s tests -p 'test_*.py'
```

Current coverage includes:
- policy and architecture contracts
- time normalization and DST handling
- astronomy kernel and solar position
- boundary solving and pillar assignment
- integrity and deterministic output
- API endpoint behavior
- external verification fixtures and cross-check reports

## Verification Fixtures

Stored under `tests/fixtures/`, including:
- regression snapshots
- HKO solar term fixture set
- IMCCE's VSOP87D check values for the Earth
- cross-verification report artifacts

## Astronomical Accuracy

The models are described in `conventions-and-output.md`. Each check below runs in
the test suite (`test_phase3_astronomical_kernel`,
`test_tkt023_hko_solar_term_verification`):

- **VSOP87D**: IMCCE's own check values for the Earth (`vsop87.chk`, ten dates a
  century apart, 1100 to 2000) are reproduced to 1e-10 rad and au; the largest
  difference is 5e-11.
- **Nutation**: Meeus's Example 22.a (1987 April 10). His values come from the
  IAU 1980 series; IAU 2000A (R06) differs from them by 0.007″ in longitude and
  0.002″ in obliquity, and the test allows 0.01″.
- **IAU 2006 precession and obliquity**: ERFA's own test values for `eraP06e`,
  to 1e-14 rad.
- **Apparent longitude**: Meeus's Example 25.b (1992 October 13.0 TD) to 0.0012″,
  and its radius vector to 1e-8 au, on the VSOP87D terms he prints (his
  Appendix III) and in his IAU 1976 equinox of date. The full series puts the
  Sun 0.27″ west of his abridged one.
- **Hong Kong Observatory**, 2019-2028 (240 solar terms, published to the
  minute): every instant is within 30.9 s of the published minute. Rounded,
  238 give that minute. The other two lie 0.2 s and 0.9 s past a half minute.
  Moving all 240 by one constant amount cannot reproduce every minute. The
  best such shift, 0.855 s earlier, still leaves two instants 0.012 s past a
  half minute. In other words, the engine's instants lie about 0.85 s after
  the Observatory's.
- **`lunar-python`**, every jie 1950-2100 (1,812 instants, compared in TT so that
  the two libraries' conversions to civil time do not enter): largest difference
  2.7 s, median 0.6 s. `lunar-python` evaluates an abridged series with its own
  corrections.

### Known residual

The engine ties VSOP87's J2000 equinox to FK5 (Meeus eq. 32.3). The IAU 2006
framework refers instead to the inertial dynamical mean equinox of J2000 (IERS
Conventions 2010, section 5.5.4), in the ICRS. VSOP87 refers to that same kind
of equinox, but as realised with the DE200 ephemeris (Bretagnon & Francou 1988).
The constant 0.85 s against the Hong Kong Observatory, about 0.035″ in longitude,
is of the order of the difference between these realisations; that remains to be
shown with the published rotations. Part of it may come from the Observatory's
own conversion to civil time. It is not yet resolved (#26).
`flags.model_uncertainty_seconds` (0.5 s from 1972, 1.5 s before) is a declared
allowance, and after 1972 it is smaller than this offset.

## Timezone Data

Civil birth times are converted with the IANA tz database from the `tzdata`
package, pinned to an exact version in `pyproject.toml`. Zones are loaded only
from that package, never from the host's system database, so the same input
gives the same output on every machine, and `engine.tzdb_version` reports the
data that was actually used.

To update the tz database:

1. Bump the `tzdata==` pin in `pyproject.toml` and reinstall.
2. Review which zones and dates change between the two releases.
3. Update `engine.tzdb_version` in
   `tests/fixtures/phase5-regression-1988-02-04.json` to the new version.
4. Run the full test suite; `test_phase5_verification_harness` fails until the
   pin, the installed package and the fixture agree.

## Cross-Verification

`lunar-python` is used for comparison suites in validation workflows.

## Interpreting Accuracy Metrics

- Solar-term comparison metrics in the audit are based on available HKO XML years.
- Cross-verification mismatch reports are generated and preserved for review.
- Deterministic serialization checks confirm stable output for fixed inputs.

## Related Reports

- `../artefacts/phase5-integrity-output-verification.md`
- `../artefacts/tkt030-release-readiness-audit.md`
