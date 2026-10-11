# EUVD Mapper

Look up [ENISA EUVD](https://euvd.enisa.europa.eu/) records for an open source component and version.

**GitHub Pages:** https://rkosinski941.github.io/euvd-mapper/

This is a shared workspace for two agents:

- **Grok Build (Enjoy)** on the Windows machine
- **10thman-oss** Grok Bot

10thman-oss: clone this repo and push matching logic, fixtures, and lookup work here. See [AGENTS.md](AGENTS.md).

## What this is

A public lookup surface: product + optional vendor + optional version → related EUVDs.

The ENISA API (`https://euvdservices.enisa.europa.eu/api/search`) does not allow browser CORS, so the GitHub Page reads committed snapshots under `data/`. Live fetches run from PowerShell or the Lookup EUVD Action.

## What this is not

This is not the local 10th-man SCA kit (inventory, installer, confirming-source pipeline, reachability). That kit stays off GitHub.

## Quick lookup (Windows)

```powershell
.\scripts\lookup.ps1 -Product "Apache Tomcat" -Version "9.0.20"
```

Write a snapshot the page can load:

```powershell
.\scripts\lookup.ps1 -Product "Apache Tomcat" -Vendor "Apache Software Foundation" -Out "data\products\apache-tomcat.json"
```

Then update `data/catalog.json` so the page lists the product.

## GitHub Action

Actions → **Lookup EUVD** → Run workflow. Inputs: `product`, optional `vendor` and `slug`. It writes `data/products/<slug>.json` and refreshes `data/catalog.json`.

## Data

| Path | Role |
| --- | --- |
| `data/catalog.json` | Products the page can search |
| `data/products/*.json` | Raw EUVD `/api/search` responses |

Seed snapshot: Apache Tomcat (first 100 of the API's matches). Version filtering is a first-cut range/substring check in `index.html`; replace it with real matching when that work lands.
