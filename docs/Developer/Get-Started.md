# Get Started

This guide is the practical entry point for running and working with
`eight_characters`.

## Prerequisites

- Python 3.12 preferred (project requires Python 3.9+)
- `pip`
- Optional: Docker

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run the API

```bash
uvicorn eight_characters.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Run Tests

```bash
python -m unittest discover -s tests
```

## Run Quality Gates Locally

```bash
ruff check .
ruff format --check .
pyright
```

## Browser Regression Tests

See [browser regression tests](../../tests/browser/README.md) for the explicit
server/module settings and desktop/mobile Chromium and WebKit checks. These use
existing browser tooling and do not add production dependencies.

## Key Docs

- User docs index: `../README.md`
- API reference: `../api.md`
- Developer API internals: `API.md`
- Troubleshooting: `../troubleshooting.md`
