# Astronomical model data

These files are the published model tables, unmodified. The loaders check each file's
SHA-256 at startup, so a changed file stops the app instead of changing results.

| File | Model | Source | SHA-256 |
|---|---|---|---|
| `VSOP87D.ear` | VSOP87 version D, Earth: heliocentric L, B, R referred to the ecliptic and equinox of date (Bretagnon & Francou 1988) | IMCCE, `https://ftp.imcce.fr/pub/ephem/planets/vsop87/VSOP87D.ear` | `8b160c859136d467f2be7fc29efa8a9652e95516dfbde00e4c739d7ddc90ca91` |
| `tab5.3a.txt` | Nutation in longitude, IAU 2000A with the IAU 2006 adjustments (IAU 2000_R06), IERS Conventions 2010, Table 5.3a | IERS, `https://iers-conventions.obspm.fr/content/chapter5/additional_info/tab5.3a.txt` | `6da73bfe10873ac815520d00fffd67114d647a34afebc5946cfc275e73693f32` |
| `tab5.3b.txt` | Nutation in obliquity, same model, Table 5.3b | IERS, `https://iers-conventions.obspm.fr/content/chapter5/additional_info/tab5.3b.txt` | `f0dff02c78809b629cc64e2a9fbeffaea5ae20f67e1a62a0ed966f8624807557` |

Retrieved 2026-09-25. The IMCCE check values used by the tests come from
`vsop87.chk` in the same IMCCE directory
(`f8fa52449262be05a22a96840c1acbad0b35c8999e00b5c0477ba8a91a67a51a`).
