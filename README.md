# Eight Characters

Deterministic Ba Zi backend engine and API for computing:
- true solar time
- Four Pillars (year, month, day, hour)

The project includes an implementation roadmap, validation suites, and a production API endpoint.

## Quick Start

### 1) Install and run

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
uvicorn eight_characters.main:app --reload
```

Open `http://127.0.0.1:8000`.

### 1b) Run with Docker

Build and run directly:

```bash
docker build -t eight-characters:latest .
docker run --rm -p 8000:8000 eight-characters:latest
```

Or with compose:

```bash
docker compose up --build
```

### 2) Call the Ba Zi API

`POST /api/bazi`

Example payload:

```json
{
  "date": "1988-02-04",
  "time": "16:30:00",
  "location": {
    "timezone": "Asia/Shanghai",
    "longitude": 104.066,
    "latitude": 30.658
  },
  "conventions": {
    "zi_convention": "split_midnight",
    "hour_basis": "true_solar",
    "day_boundary_basis": "true_solar"
  }
}
```

Returns:
- solar-time fields (`utc_time`, `local_mean_solar_time`, `true_solar_time`)
- four pillars
- ambiguity and warning flags

### 3) Run validation suite

```bash
source venv/bin/activate
python -m unittest discover -s tests -p 'test_*.py'
```

## Project Docs

- User docs index: `docs/README.md`
- API usage: `docs/api.md`
- Conventions and outputs: `docs/conventions-and-output.md`
- Validation and quality: `docs/validation.md`
- Troubleshooting: `docs/troubleshooting.md`

## Engineering and Audit Artifacts

- Main product spec: `astrometrics-spec.md`
- Task board: `backend-task-tree.md`
- Execution workboard: `backend-implementation-workboard.md`
- Phase reports:
  - `phase1-governance-architecture-baseline.md`
  - `phase2-time-normalization-core.md`
  - `phase3-astronomical-computation-kernel.md`
  - `phase4-boundary-solving-and-pillar-assignment.md`
  - `phase5-integrity-output-verification.md`
- Final closeout:
  - `tkt028-limitations-and-warning-behavior.md`
  - `tkt029-licensing-and-attribution-checklist.md`
  - `tkt030-release-readiness-audit.md`

## License and Data

See `tkt029-licensing-and-attribution-checklist.md` for attribution and data-source compliance requirements.
