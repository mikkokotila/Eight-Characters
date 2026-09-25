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
- cross-verification report artifacts

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
