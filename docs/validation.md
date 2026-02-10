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

## Cross-Verification

`lunar-python` is used for comparison suites in validation workflows.

## Interpreting Accuracy Metrics

- Solar-term comparison metrics in the audit are based on available HKO XML years.
- Cross-verification mismatch reports are generated and preserved for review.
- Deterministic serialization checks confirm stable output for fixed inputs.

## Related Reports

- `phase5-integrity-output-verification.md`
- `tkt030-release-readiness-audit.md`
