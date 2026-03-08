<h3 align="center">Eight Characters is a deterministic Four Pillars engine and API.</h3>
<p align="center">
<a href="#value-proposition">Value Proposition</a> •
<a href="#quick-start">Quick Start</a> •
<a href="#contributing">Contributing</a> •
<a href="#license">License</a>
</p>
<hr>

# Value Proposition

Eight Characters computes true solar time and Four Pillars (year, month, day, hour)
with rigorous deterministic conventions and explicit ambiguity flags. It is designed as a
reliable backend/API foundation for Ba Zi (Four Pillars) applications, integrations, and testing.

# Quick Start

If your environment is already configured, use these three examples:

1) Running the app

```bash
uvicorn eight_characters.main:app --reload
```

2) Checking the service

```bash
curl http://127.0.0.1:8000/
```

3) Calling the Four Pillars API

```bash
curl -X POST 'http://127.0.0.1:8000/api/four_pillars' \
  -H 'Content-Type: application/json' \
  -d '{
    "date": "1988-02-04",
    "time": "16:30:00",
    "city": "Chengdu",
    "country": "China"
  }'
```

For complete setup, configuration, and deployment instructions, see
[Get Started](docs/Developer/Get-Started.md).

# Contributing

The simplest way to contribute is by joining open discussions or picking up an issue:

- [Open discussions](https://github.com/mikkokotila/Eight-Characters/discussions)
- [Open issues](https://github.com/mikkokotila/Eight-Characters/issues)

Before contributing, start with [Get Started](docs/Developer/Get-Started.md).

# Vulnerabilities

Report vulnerabilities privately through
[GitHub Security Advisories](https://github.com/mikkokotila/Eight-Characters/security/advisories/new).

# Citations

If you use Eight Characters for published work, please cite:

Eight Characters [Computer software]. (2026). Retrieved from
https://github.com/mikkokotila/Eight-Characters.

# License

[MIT License](LICENSE.md).
