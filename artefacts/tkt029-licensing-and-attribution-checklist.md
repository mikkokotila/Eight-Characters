# TKT-029 - Licensing and Attribution Checklist

Distribution checklist for embedded models and data sources.

## Source Checklist

- VSOP87D coefficients
  - license: public domain
  - attribution required: Bretagnon and Francou 1988
  - status: included in documentation checklist
- IAU 2000A nutation
  - license: public domain standard
  - attribution required: Mathews, Herring and Buffett 2002
  - status: included in documentation checklist
- IAU 2006 precession and obliquity
  - license: public domain standard
  - attribution required: Capitaine, Wallace and Chapront 2003
  - status: included in documentation checklist
- Espenak-Meeus delta-T polynomials
  - license: public domain
  - attribution required: NASA Eclipse site
  - status: included in documentation checklist
- IANA tzdata and leap second list
  - license: public domain
  - attribution required: IANA
  - status: included in documentation checklist
- GeoNames dataset (if distributed with geocoding bundle)
  - license: CC-BY-4.0
  - attribution required: mandatory
  - status: policy requires attribution in docs and UI where geocoding data is shipped

## Dependency License Review

- runtime dependencies used:
  - `fastapi`
  - `uvicorn`
  - `jinja2`
  - `pydantic`
  - `tzdata`
  - `httpx`
  - `lunar-python` (verification/comparison tooling)

No copyleft runtime dependency has been introduced for the core calculation path.

## Compliance Status

- attribution checklist document: complete
- release-time action: include this checklist in packaging/release notes
- blocker status: clear
