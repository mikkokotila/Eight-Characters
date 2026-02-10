# Troubleshooting

## `400` on `/api/bazi`

Common causes:
- invalid `date` format (must be `YYYY-MM-DD`)
- invalid `time` format (must be `HH:MM` or `HH:MM:SS`)
- invalid timezone id
- DST fall-back ambiguous local time without `fold`
- DST spring-forward nonexistent local time
- invalid latitude/longitude ranges

## DST ambiguity

For fall-back local times, set:
- `location.fold = 0` for first occurrence
- `location.fold = 1` for second occurrence

## High-latitude warning

`high_latitude_warning` may be true above `66` or below `-66`.
This is advisory behavior and not a hard error.

## Reproducibility checks

If output seems inconsistent:
- confirm same engine version
- confirm same timezone data version
- rerun regression tests:

```bash
source venv/bin/activate
python -m unittest discover -s tests -p 'test_*.py'
```

## Dependency issues

If API tests fail due to missing client libs:

```bash
source venv/bin/activate
pip install -r requirements.txt
```
