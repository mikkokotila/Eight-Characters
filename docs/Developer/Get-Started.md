# Get Started

This guide is the practical entry point for running and working with
`eight_characters`.

## Prerequisites

- Python 3.11: the version the production image runs and every CI gate tests
  (`requires-python = '>=3.11'`). On a newer Python, code that 3.11 cannot run
  passes locally and then fails in CI.
- `pip`
- Git (the account backup and its tests use it)
- Optional: Docker

## Local Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run the API

The app needs its account settings and database to start, even on a laptop: see
[Accounts, on a laptop](Accounts.md#on-a-laptop). Then:

```bash
uvicorn eight_characters.main:app --reload
```

Open `http://127.0.0.1:8000`. Charts need an account; codes arrive as files in the
mail folder the settings name.

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
