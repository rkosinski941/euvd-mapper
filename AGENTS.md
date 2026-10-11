# Agent notes

Shared repo for **Grok Build (Enjoy)** and **10thman-oss**.

## Scope

Input: open source component name, optional vendor, optional version.
Output: EUVD records related to that component, with version relevance when a version is given.

Source of truth for records: ENISA EUVD API, `GET https://euvdservices.enisa.europa.eu/api/search`.

## Who does what

| Agent | Owns |
| --- | --- |
| 10thman-oss | Matching logic, version-range parsing, component aliases, fixtures, existing lookup work to land here |
| Grok Build | GitHub Pages UI, Windows `scripts/lookup.ps1`, repo plumbing, browser checks |

Do not copy the local 10th-man SCA kit into this repo.

## Where to put work

- `index.html` — Pages UI and the current version filter
- `scripts/lookup.ps1` — live API client (no CORS)
- `data/catalog.json` + `data/products/` — snapshots the page reads
- `.github/workflows/lookup.yml` — on-demand snapshot refresh (Actions → Lookup EUVD)

## Conventions

- Public data only. No customer SBOMs, no internal scan output, no installer bits.
- Prefer PowerShell on Windows. No Makefiles.
- Keep the page usable from GitHub Pages with committed JSON; do not depend on a CORS proxy.
- When replacing the version filter, keep the function name `versionMightMatch` or update the one call site in `index.html`.
