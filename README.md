# EUVD Mapper

Map an open source component to the [ENISA EUVD](https://euvd.enisa.europa.eu/) records that affect it.

Give it a package URL (or a name, plus an optional version). It asks [OSV](https://osv.dev/) which advisories affect that package version, looks those CVE and GHSA aliases up in EUVD, and also searches EUVD by product name and parses `product_version`. When both paths run, agreement and disagreement are both reported. A version is never marked affected without a version basis. Unknown stays unknown.

**GitHub Pages** (snapshot viewer): https://rkosinski941.github.io/euvd-mapper/

This repo is shared by Grok Build (Enjoy), which owns the Pages shell and `scripts/lookup.ps1`, and 10thman-oss, which owns the matcher, aliases, fixtures, and the workbook enricher. See [AGENTS.md](AGENTS.md).

## Two-minute demo

The demo reads recorded public API responses, so it does not call the network. From the repo root, with Python 3 and `openpyxl` (`pip install -e .`):

```bash
python -m euvd_mapper enrich-xlsx examples/black-duck-sample.xlsx -o /tmp/black-duck-sample-euvd.xlsx --offline --cache-dir tests/fixtures/cache
```

PowerShell:

```powershell
.\scripts\enrich.ps1 -InputPath .\examples\black-duck-sample.xlsx -Out \tmp\black-duck-sample-euvd.xlsx -CacheDir .\tests\fixtures\cache -Offline
```

The command writes a new workbook. It does not modify the input. Stdout is:

```text
components 8 affected 7 not_affected 0 unknown 1 disagree 0
records affected 190 not_affected 168 unknown 147 disagree 76
tomcat-catalina	9.0.20	affected	euvd-range, osv-range	EUVD-2019-0787 EUVD-2019-0793 EUVD-2020-0311 EUVD-2020-0404 EUVD-2021-0677 EUVD-2021-0906 EUVD-2021-1340 EUVD-2021-1533 EUVD-2021-1563 EUVD-2021-1985 EUVD-2022-0828 EUVD-2022-0967 EUVD-2022-1098 EUVD-2022-1201 EUVD-2022-1215 EUVD-2022-4051 EUVD-2022-5128 EUVD-2022-6865 EUVD-2022-7390 EUVD-2023-0720 EUVD-2023-0829 EUVD-2023-2335 EUVD-2023-2737 EUVD-2023-2799 EUVD-2023-2957 EUVD-2024-0340 EUVD-2024-0863 EUVD-2024-1010 EUVD-2024-2438 EUVD-2024-3211 EUVD-2024-3331 EUVD-2024-3537 EUVD-2024-3539 EUVD-2024-3542 EUVD-2025-13626 EUVD-2025-16411 EUVD-2025-18406 EUVD-2025-18409 EUVD-2025-207697 EUVD-2025-21032 EUVD-2025-21044 EUVD-2025-21045 EUVD-2025-24559 EUVD-2025-24574 EUVD-2025-36223 EUVD-2025-36224 EUVD-2025-6498 EUVD-2026-21006 EUVD-2026-21008 EUVD-2026-21012 EUVD-2026-21057 EUVD-2026-29513 EUVD-2026-29514 EUVD-2026-29515 EUVD-2026-29516 EUVD-2026-29517 EUVD-2026-29518 EUVD-2026-29519 EUVD-2026-40226 EUVD-2026-40227 EUVD-2026-40230 EUVD-2026-40231 EUVD-2026-40232 EUVD-2026-40233 EUVD-2026-43638 EUVD-2026-43640 EUVD-2026-66124 EUVD-2026-66128 EUVD-2026-66130 EUVD-2026-66132 EUVD-2026-66135 EUVD-2026-66192 EUVD-2026-7831 EUVD-2026-85222 EUVD-2026-85224 EUVD-2026-85225 EUVD-2026-85230 EUVD-2026-85232 EUVD-2026-85236
log4j-core	2.14.1	affected	osv-range	EUVD-2021-2559 EUVD-2021-34768 EUVD-2021-34769 EUVD-2022-0516 EUVD-2025-204312 EUVD-2026-21407 EUVD-2026-21410
lodash	4.17.15	affected	osv-range	EUVD-2020-0567 EUVD-2021-0912 EUVD-2022-0424 EUVD-2025-206319 EUVD-2026-17591 EUVD-2026-17610
jackson-databind	2.9.10	affected	osv-range, euvd-range	EUVD-2019-0709 EUVD-2019-0747 EUVD-2019-0750 EUVD-2020-0328 EUVD-2020-0346 EUVD-2020-0366 EUVD-2020-0370 EUVD-2020-0375 EUVD-2020-0384 EUVD-2020-0399 EUVD-2020-0417 EUVD-2020-0423 EUVD-2020-0433 EUVD-2020-0438 EUVD-2020-0443 EUVD-2020-0444 EUVD-2020-0460 EUVD-2020-0477 EUVD-2020-0478 EUVD-2020-0495 EUVD-2020-0497 EUVD-2021-0490 EUVD-2021-0525 EUVD-2021-2393 EUVD-2021-2450 EUVD-2021-2481 EUVD-2021-2482 EUVD-2021-2486 EUVD-2021-2495 EUVD-2021-2497 EUVD-2021-2504 EUVD-2021-2511 EUVD-2021-2527 EUVD-2021-2550 EUVD-2021-2570 EUVD-2021-2576 EUVD-2021-2578 EUVD-2021-2592 EUVD-2021-2603 EUVD-2022-1319 EUVD-2022-6411 EUVD-2022-7117 EUVD-2022-7159 EUVD-2026-38589 EUVD-2026-38590 EUVD-2026-38591 EUVD-2026-38592 EUVD-2026-38593 EUVD-2026-38595 EUVD-2026-38597 EUVD-2026-38629 EUVD-2026-43957 EUVD-2026-44506 EUVD-2026-65088 EUVD-2026-68961 EUVD-2026-76142 EUVD-2026-85002 EUVD-2026-85003
Django	3.2.0	affected	osv-range	EUVD-2021-0061 EUVD-2021-0062 EUVD-2021-0064 EUVD-2021-0065 EUVD-2021-0067 EUVD-2021-0068 EUVD-2022-0085 EUVD-2022-0086 EUVD-2022-0087 EUVD-2022-0088 EUVD-2022-0089 EUVD-2022-0090 EUVD-2022-0091 EUVD-2022-0092 EUVD-2022-0093 EUVD-2022-0094 EUVD-2023-0065 EUVD-2023-0066 EUVD-2023-0067 EUVD-2023-0068 EUVD-2023-0069 EUVD-2023-0070 EUVD-2023-0071 EUVD-2024-0038 EUVD-2024-0039 EUVD-2024-3135 EUVD-2025-16951 EUVD-2025-26641 EUVD-2025-37763 EUVD-2025-37765 EUVD-2026-34086 EUVD-2026-34088 EUVD-2026-34090 EUVD-2026-42043 EUVD-2026-42044 EUVD-2026-42045 EUVD-2026-52747 EUVD-2026-52749
Apache Tomcat	9.0.21	affected	euvd-range	EUVD-2019-0787 EUVD-2019-0793 EUVD-2020-0311 EUVD-2020-0404 EUVD-2021-0677 EUVD-2021-0906 EUVD-2021-1340 EUVD-2021-1533 EUVD-2021-1563 EUVD-2021-1985 EUVD-2022-0828 EUVD-2022-0967 EUVD-2022-1098 EUVD-2022-1201 EUVD-2022-1215 EUVD-2022-5128 EUVD-2022-6865 EUVD-2022-7390 EUVD-2023-0720 EUVD-2023-0829 EUVD-2023-2335 EUVD-2023-2737 EUVD-2023-2799 EUVD-2023-2957 EUVD-2024-0340 EUVD-2024-0863 EUVD-2024-1010 EUVD-2024-2438 EUVD-2024-3211 EUVD-2024-3331 EUVD-2024-3537 EUVD-2024-3539 EUVD-2024-3542 EUVD-2025-13626 EUVD-2025-16411 EUVD-2025-18406 EUVD-2025-18409 EUVD-2025-207697 EUVD-2025-21032 EUVD-2025-21044 EUVD-2025-21045 EUVD-2025-24559 EUVD-2025-24574 EUVD-2025-36223 EUVD-2025-36224 EUVD-2025-6498 EUVD-2026-21006 EUVD-2026-21008 EUVD-2026-21012 EUVD-2026-21057 EUVD-2026-29513 EUVD-2026-29514 EUVD-2026-29515 EUVD-2026-29516 EUVD-2026-29517 EUVD-2026-29518 EUVD-2026-29519 EUVD-2026-40226 EUVD-2026-40227 EUVD-2026-40230 EUVD-2026-40231 EUVD-2026-40232 EUVD-2026-40233 EUVD-2026-43638 EUVD-2026-43640 EUVD-2026-66124 EUVD-2026-66128 EUVD-2026-66130 EUVD-2026-66132 EUVD-2026-66135 EUVD-2026-66192 EUVD-2026-7831 EUVD-2026-85222 EUVD-2026-85224 EUVD-2026-85225 EUVD-2026-85230 EUVD-2026-85232 EUVD-2026-85236
Apache Tomcat	latest	unknown	name-only	
wrote /tmp/black-duck-sample-euvd.xlsx
```

Progress lines (`lookup pkg:...`) go to stderr and are not part of that summary. The same text is frozen in `tests/fixtures/demo-stdout.txt`.

Open the workbook. The BOM sheet keeps its original columns and gains, at the end: EUVD IDs, CVE/GHSA aliases, Max severity/score, Version verdict, Match basis, Evidence/notes. **EUVD Detail** has one row per component and EUVD record, with links to `euvd.enisa.europa.eu`. **EUVD Run** has the timestamp, tool version, API sources, and verdict counts.

Rows worth showing a reviewer:

| Component | Version | Verdict | Basis | What to open on EUVD Detail |
| --- | --- | --- | --- | --- |
| tomcat-catalina | 9.0.20 | affected (component) | euvd-range and osv-range | `EUVD-2022-4051` / CVE-2022-25762 is **disagree**: the EUVD range `9.0.0.M1 to 9.0.20` includes 9.0.20, and the OSV query for this purl did not list it |
| log4j-core | 2.14.1 | affected | osv-range | `EUVD-2021-34768` / CVE-2021-44228 (Log4Shell). The EUVD `product_version` is malformed, so it is not used as a range |
| lodash | 4.17.15 | affected | osv-range | `EUVD-2021-0912` / CVE-2021-23337. OSV and the EUVD range `prior to 4.17.21` agree |
| jackson-databind | 2.9.10 | affected | osv-range | `EUVD-2020-0440` is **unknown**: `product_version` lists 2.9.10, and the description says "before" 2.9.10 |
| Django | 3.2.0 | affected | osv-range | `EUVD-2021-0067` / CVE-2021-33203. EUVD has no product version for this record |
| Apache Tomcat | 9.0.21 | affected for other records | euvd-range | `EUVD-2022-4051` is **not_affected** (the range ends at 9.0.20) |
| Apache Tomcat | latest | unknown | name-only | not marked affected |

`examples/cyclonedx-sample.xlsx` is the same public components on a Name / Version / PURL sheet.

Live lookups use the same command without `--offline`. Responses are cached under `--cache-dir` (default `.cache/euvd-mapper`) and retried with backoff.

One component, without a workbook:

```bash
python -m euvd_mapper lookup --purl "pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1" --offline --cache-dir tests/fixtures/cache
```

## Workbook columns

The enricher detects the header row and the sheet. It understands Black Duck style names (`Component name`, `Component version name`, `Version`, `Package URL`, `Origin id`) and CycloneDX style names (`Name`, `Version`, `PURL`). Override them with `--sheet`, `--name-column`, `--version-column`, and `--purl-column`. An origin id is used as a purl only when it starts with `pkg:`. Without a purl, the matcher uses name and version and says so in the basis.

Identical purls, or identical name and version, are queried once. `--offline` reads only the cache. A cache miss is reported on EUVD Run and is not marked affected.

## Pages

The page reads `data/catalog.json` and `data/products/*.json`. It does not call OSV or EUVD. Verdict and basis columns use `js/versionrange.js`, the same range rules as the CLI, so a Tomcat 9.0.20 lookup shows `EUVD-2022-4051` as affected on `euvd-range`, and 9.0.21 shows that same record as not_affected. A non-comparable version such as `latest` stays unknown and name-only. Apache Tomcat Native is not treated as Apache Tomcat. A direct link: `index.html?product=Apache%20Tomcat&version=9.0.20`.

The Apache Tomcat snapshot is the full search result, 165 of 165. `/api/search` paging is 0-based, `size` max is 100, and the second page is required. `scripts/lookup.ps1` and the Lookup EUVD Action both follow that.

```powershell
.\scripts\lookup.ps1 -Product "Apache Tomcat" -Out "data\products\apache-tomcat.json"
```

```bash
python -m euvd_mapper snapshot --product "Apache Tomcat" --slug apache-tomcat
```

Actions → **Lookup EUVD** runs that snapshot command and commits `data/`.

## Tests

```bash
python -m unittest discover -s tests
node --test js/versionrange.test.js
```

GitHub Actions workflow **Tests** runs both. The golden tests replay `tests/fixtures/cache`, which is recorded OSV and EUVD JSON trimmed to the fields the matcher reads (advisory bodies are not stored).

## Limitations

- EUVD product data has gaps. Django records such as `EUVD-2021-0067` (CVE-2021-33203) have no product or version, so only the OSV alias path can call them affected, and the basis stays `osv-range`.
- Some `product_version` strings are not ranges. Log4Shell's EUVD record stores `2.0-beta9 <log4j-core*`. That stays unknown. The affected verdict for log4j-core 2.14.1 comes from OSV, not from a guessed parse.
- `EUVD-2020-0440` lists exact versions `2.9.10` and `2.10.0` while the description says the flaw is in versions before those. Those two signals are not merged into affected.
- OSV and EUVD disagree on Tomcat 9.0.20 / CVE-2022-25762 (`EUVD-2022-4051`). The Apache advisory and the EUVD range include 9.0.0.M1 through 9.0.20 (fixed in 9.0.21). OSV does not return that CVE for `pkg:maven/org.apache.tomcat/tomcat-catalina@9.0.20`; the GHSA is filed on `org.apache.tomcat:tomcat` with `fixed: 9.0.20`, which excludes 9.0.20. The row is `disagree`.
- EUVD search is product-scoped and OSV is artifact-scoped. A Tomcat module purl will not line up with every Apache Tomcat product record. Those conflicts stay visible. There were 76 disagreeing records on the sample BOM.
- Product-name matching is exact, plus a small alias table (`tomcat-catalina` → Apache Tomcat, `log4j-core` → Apache Log4j2). It does not treat "Apache Tomcat Native" as Apache Tomcat, or "lodash.template" as lodash.
- A missing or non-comparable version (`latest`) is `unknown` and `name-only`. It is not affected.
- The clients send a User-Agent, sleep between calls, back off on HTTP 429 and 5xx, and cache responses. EUVD search pages are at most 100 rows. Offline mode never fills a miss by calling the network.
- This is not a reachability or exploitability judgment, and it is not a complete substitute for the NVD or for OSV.

## What this is not

This is not the local 10th-man SCA kit. No customer SBOMs, scan output, or installer bits belong in this repo. The workbooks under `examples/` are public sample components only.
