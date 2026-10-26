"""Black Duck project-report layout: EUVD sheets beside Vulnerabilities.

The workbook is a template-6.1.0 style export when it has a Bill of Materials
sheet and a Vulnerabilities sheet with the headers below. Matching is:

- every NVD CVE on the Vulnerabilities sheet is looked up on EUVD ``/api/enisaid``
- each other BOM component is searched on EUVD ``/api/search`` by product name

A product-search row is written only when the BOM version falls inside a
parsed EUVD range. Out-of-range hits and ranges that do not parse are listed
on the run summary. A missing row is not a finding that no vulnerability exists.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from openpyxl.workbook.workbook import Workbook

from euvd_mapper.euvd import lookup_alias, search_product
from euvd_mapper.http import CacheMiss, HttpError
from euvd_mapper.versionrange import evaluate_product_version

BOM_SHEET = "Bill of Materials"
VULN_SHEET = "Vulnerabilities"
EUVD_SHEET = "EUVD Vulnerabilities"
SUMMARY_SHEET = "EUVD Run Summary"

BOM_HEADERS = (
    "Component",
    "Version",
    "License",
    "Usage",
    "License Status",
    "Security Status",
    "Home Page",
    "Ship Status",
    "Code Match",
    "Depends",
    "Search",
    "Multi-Licensing",
    "Comment",
)

VULN_HEADERS = (
    "Severity",
    "Component",
    "Version",
    "NVD CVE",
    "Related BDSA",
    "NVD Overall (Base)",
    "NVD Exploitability",
    "NVD Impact",
    "NVD CVSS",
    "NVD Description",
    "NVD Published",
    "NVD Updated",
    "NVD CWE",
    "Patch Reference",
    "Suggested Version Upgrade",
    "Workaround",
    "Short-term Version Upgrade",
    "Long-term Version Upgrade",
    "BDSA Severity",
    "BDSA  Overall (Temporal)",
    "BDSA Base",
    "BDSA Exploitability",
    "BDSA Impact",
    "BDSA CVSS",
    "BDSA CWE",
    "BDSA Description",
    "BDSA Published",
    "BDSA Updated",
    "CISA KEV Vuln Id",
    "CISA KEV Vuln Name",
    "CISA KEV Date Added",
    "CISA KEV Required Action",
    "From Transitive Dependency?",
)

EUVD_HEADERS = (
    "Severity",
    "Component",
    "Version",
    "EUVD ID",
    "NVD CVE",
    "Related BDSA",
    "EUVD Aliases (CVE/GHSA)",
    "EUVD Base Score",
    "EUVD CVSS Version",
    "EUVD CVSS Vector",
    "EUVD EPSS",
    "EUVD Published",
    "EUVD Updated",
    "EUVD Description",
    "EUVD Link",
    "Affected-Version Verdict",
    "Match Basis",
    "Notes",
)

CVE_BASIS = "CVE alias (from Vulnerabilities tab)"
CVE_NOTE = "Also listed in Black Duck Vulnerabilities tab"
SEARCH_NOTE = "Not in Black Duck Vulnerabilities tab; review"
LINK_PREFIX = "https://euvd.enisa.europa.eu/vulnerability/"
_ZONE = ZoneInfo("America/New_York")

_SIMPLE_RANGE = re.compile(r"^(?:([\d.]+)|0|unspecified|\*)?\s*(<|≤)(=?)\s*([\d.]+)$")
_PRIOR_RANGE = re.compile(
    r"^(?:apache cxf\s*)?(?:versions?\s*)?(?:(\d+\.\d+)\.x\s*)?(?:prior to|before|<)\s*([\d.]+)$",
    re.I,
)
@dataclass
class BomComponent:
    component: str
    version: str
    usage: str


@dataclass
class VulnRow:
    component: str
    version: str
    cve: str
    bdsa: str


@dataclass
class ReportBuild:
    banner: str
    euvd_rows: list[list]
    summary_rows: list[list]
    stdout: list[str]
    checked: list[BomComponent] = field(default_factory=list)


def is_blackduck_project_report(workbook: Workbook) -> bool:
    if BOM_SHEET not in workbook.sheetnames or VULN_SHEET not in workbook.sheetnames:
        return False
    bom = _headers(workbook[BOM_SHEET])
    vuln = _headers(workbook[VULN_SHEET])
    return bom == list(BOM_HEADERS) and vuln == list(VULN_HEADERS)


def read_bom(workbook: Workbook) -> list[BomComponent]:
    sheet = workbook[BOM_SHEET]
    rows = []
    for row in range(3, (sheet.max_row or 2) + 1):
        component = _text(sheet.cell(row, 1).value)
        version = _text(sheet.cell(row, 2).value)
        usage = _text(sheet.cell(row, 4).value)
        if not component and not version:
            continue
        rows.append(BomComponent(component, version, usage))
    return rows


def read_vulnerabilities(workbook: Workbook) -> list[VulnRow]:
    sheet = workbook[VULN_SHEET]
    rows = []
    for row in range(3, (sheet.max_row or 2) + 1):
        cve = _text(sheet.cell(row, 4).value)
        component = _text(sheet.cell(row, 2).value)
        version = _text(sheet.cell(row, 3).value)
        bdsa = _text(sheet.cell(row, 5).value)
        if not cve and not component and not version:
            continue
        if not cve:
            continue
        rows.append(VulnRow(component, version, cve, bdsa))
    return rows


def components_to_search(rows: list[BomComponent]) -> list[BomComponent]:
    """BOM rows whose usage is not the project's own original code."""
    return [row for row in rows if row.component and row.usage != "Original Code"]


def severity_from_score(score) -> str:
    """EUVD base score bands. A missing score is Not Yet Rated."""
    if score is None or score == "":
        return "Not Yet Rated"
    try:
        number = float(score)
    except (TypeError, ValueError):
        return "Not Yet Rated"
    if number >= 9:
        return "Critical"
    if number >= 7:
        return "High"
    if number >= 4:
        return "Medium"
    return "Low"


def search_query(component: str) -> str:
    """Drop Black Duck qualifiers so the EUVD product query is the product name."""
    return re.sub(r"\s*::.*|\(.*?\)", "", component).strip()


def version_verdict(version: str, ranges: list[str]) -> tuple[str, str]:
    """Return ``(label, kind)`` with kind affected, not_affected, or unknown.

    A range is applied only when the whole string is a single bound, an exact
    version, or a 'prior to' / 'before' line, and the shared range parser agrees.
    Anything else stays unknown. An unparsed string is not treated as a match
    and is not treated as proof that the version is outside the affected set.
    """
    cleaned = [(item or "").strip() for item in ranges]
    if not any(cleaned):
        return "unknown (no product version data)", "unknown"
    current = _digits(version)
    hits: list[str] = []
    unknown: list[str] = []
    for text in cleaned:
        if not text:
            unknown.append(text)
            continue
        bound = _simple_bound(text)
        if bound is not None:
            lower, upper, inclusive = bound
            inside = lower <= current and (current <= upper if inclusive else current < upper)
            if inside:
                checked = evaluate_product_version(text, version).verdict
                if checked == "affected":
                    hits.append(text)
                elif checked == "unknown":
                    unknown.append(text)
            continue
        if re.fullmatch(r"[\d.]+", text):
            if _digits(text) == current:
                checked = evaluate_product_version(text, version).verdict
                if checked == "affected":
                    hits.append(text)
                elif checked == "unknown":
                    unknown.append(text)
            continue
        unknown.append(text)
    if hits:
        return "affected (in range " + "; ".join(hits) + ")", "affected"
    if unknown:
        shown = "; ".join(item for item in unknown[:4] if item) or "empty product_version"
        return "unknown (unparsed ranges: " + shown + ")", "unknown"
    return "not in listed ranges", "not_affected"


def build_report(http, vulnerabilities: list[VulnRow], bom: list[BomComponent], now: datetime | None = None) -> ReportBuild:
    stamp = _stamp(now)
    checked = components_to_search(bom)
    rows: list[list] = []
    alias_ids: set[str] = set()
    unmatched: list[tuple[str, str]] = []
    errors: list[str] = []

    for item in vulnerabilities:
        print(f"lookup {item.cve}", file=sys.stderr)
        record, problem = _lookup(http, item.cve)
        if problem:
            if problem.startswith("API error") or problem.startswith("offline"):
                errors.append(problem)
            unmatched.append((item.cve, problem))
            rows.append(_cve_gap(item, problem))
            continue
        alias_ids.add(str(record["id"]))
        rows.append(_cve_row(item, record))

    errors = _unique(errors)

    excluded: list[tuple[str, str, str]] = []
    stats: dict[tuple[str, str], str] = {}
    seen: set[tuple[str, str, str]] = set()
    for component in checked:
        query = search_query(component.component)
        print(f"search {query}", file=sys.stderr)
        try:
            found_items, _total = search_product(http, query)
        except CacheMiss as exc:
            message = f"offline cache miss for product search {query!r}; not a statement that no EUVD record exists ({exc.key})"
            errors.append(message)
            stats[(component.component, component.version)] = "product search not run (offline cache miss)"
            continue
        except HttpError as exc:
            message = f"API error for product search {query!r}: {exc}"
            errors.append(message)
            stats[(component.component, component.version)] = "API error"
            continue
        found = 0
        for record in found_items:
            eid = str(record.get("id") or "")
            if not eid or eid in alias_ids:
                continue
            matched, fuzzy = _match_products(component.component, query, _products(record))
            if not matched:
                continue
            marker = (component.component, component.version, eid)
            if marker in seen:
                continue
            label, kind = version_verdict(component.version, [version for _name, version in matched])
            if kind != "affected":
                excluded.append((component.component, eid, _range_text(matched)))
                continue
            seen.add(marker)
            found += 1
            rows.append(_search_row(component, record, matched, fuzzy, query, label))
        if found:
            stats[(component.component, component.version)] = f"{found} additional via product search"
        else:
            stats[(component.component, component.version)] = (
                "no additional EUVD match (product search, exact/fuzzy name + version range)"
            )

    product_rows = sum(1 for row in rows if str(row[16]).startswith("product search"))
    banner = (
        "This tab shows vulnerabilities from the ENISA EU Vulnerability Database (EUVD) "
        "associated with the components found during the audit. Entries were matched via "
        "CVE aliases from the Vulnerabilities tab and via EUVD product search, using the "
        f"public EUVD API on {stamp}. Affected-version verdicts come from EUVD product "
        "ranges and need review."
    )
    summary = _summary(
        stamp,
        checked,
        vulnerabilities,
        rows,
        unmatched,
        product_rows,
        excluded,
        errors,
        stats,
    )
    stdout = [
        "layout blackduck-project-report",
        (
            f"euvd_rows {len(rows)} cve_rows {len(vulnerabilities)} "
            f"cve_without_euvd {len(unmatched)} product_search_rows {product_rows} "
            f"excluded {len(excluded)} api_errors {len(errors)}"
        ),
    ]
    return ReportBuild(banner=banner, euvd_rows=rows, summary_rows=summary, stdout=stdout, checked=checked)


def _lookup(http, cve: str) -> tuple[dict | None, str | None]:
    try:
        record = lookup_alias(http, cve)
    except CacheMiss as exc:
        return None, (
            "offline cache miss; not a statement that this CVE has no EUVD record "
            f"({exc.key})"
        )
    except HttpError as exc:
        return None, f"API error: {exc}"
    if not record or not record.get("id"):
        return None, "no EUVD record aliasing this CVE"
    return record, None


def _cve_gap(item: VulnRow, reason: str) -> list:
    return [
        "Not Yet Rated",
        item.component,
        item.version,
        "no EUVD match",
        item.cve,
        item.bdsa,
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        CVE_BASIS,
        reason,
    ]


def _cve_row(item: VulnRow, record: dict) -> list:
    matched, _fuzzy = _match_products(item.component, search_query(item.component), _products(record))
    ranges = [version for _name, version in matched] if matched else [
        version for name, version in _products(record) if item.component and item.component.casefold() in name.casefold()
    ]
    label, _kind = version_verdict(item.version, ranges)
    return _record_row(
        component=item.component,
        version=item.version,
        record=record,
        cve=item.cve,
        bdsa=item.bdsa,
        verdict=label,
        basis=CVE_BASIS,
        notes=CVE_NOTE,
    )


def _search_row(component: BomComponent, record: dict, matched, fuzzy: bool, query: str, verdict: str) -> list:
    product = matched[0][0]
    if fuzzy:
        basis = f'product search ("{query}", fuzzy name match to EUVD product "{product}")'
    else:
        basis = f'product search ("{query}", exact product-name match)'
    return _record_row(
        component=component.component,
        version=component.version,
        record=record,
        cve="",
        bdsa="",
        verdict=verdict,
        basis=basis,
        notes=SEARCH_NOTE,
    )


def _record_row(component, version, record, cve, bdsa, verdict, basis, notes) -> list:
    score = record.get("baseScore")
    if score == "":
        score = None
    epss = record.get("epss")
    if epss == "":
        epss = None
    return [
        severity_from_score(score),
        component,
        version,
        str(record.get("id") or ""),
        cve,
        bdsa,
        _aliases(record.get("aliases")),
        score if isinstance(score, (int, float)) and not isinstance(score, bool) else "",
        _text(record.get("baseScoreVersion")),
        _text(record.get("baseScoreVector")),
        epss if isinstance(epss, (int, float)) and not isinstance(epss, bool) else "",
        _text(record.get("datePublished")),
        _text(record.get("dateUpdated")),
        record.get("description") or "",
        LINK_PREFIX + str(record.get("id") or ""),
        verdict,
        basis,
        notes,
    ]


def _summary(stamp, checked, vulnerabilities, rows, unmatched, product_rows, excluded, errors, stats) -> list[list]:
    mapped = len(vulnerabilities) - len(unmatched)
    table = [
        ["EUVD Run Summary", ""],
        ["Item", "Value"],
        ["Run date", f"{stamp} (America/New_York)"],
        ["Source", "Public ENISA EUVD API, https://euvdservices.enisa.europa.eu/api/ (no login)"],
        ["BOM components checked (excluding Original Code)", len(checked)],
        ["Vulnerabilities tab rows (CVEs)", len(vulnerabilities)],
        ["CVEs mapped to an EUVD ID", mapped],
        ["CVEs with no EUVD entry", len(unmatched)],
        ["Additional EUVD entries via product search (not in Vulnerabilities tab)", product_rows],
        ["Total rows on EUVD Vulnerabilities tab", len(rows)],
        [
            "Product-search hits excluded (version outside EUVD ranges, or fuzzy name without in-range version)",
            len(excluded),
        ],
        ["API errors", len(errors)],
        ["", ""],
        ["Component", "Version / product-search result"],
    ]
    for component in checked:
        detail = stats.get(
            (component.component, component.version),
            "no additional EUVD match (product search, exact/fuzzy name + version range)",
        )
        table.append([component.component, f"{component.version}: {detail}"])
    table.append(["", ""])
    table.append(["Excluded EUVD ID (component)", "EUVD product version ranges"])
    for component, eid, ranges in excluded:
        table.append([f"{eid} ({component})", ranges])
    for cve, reason in unmatched:
        table.append([cve, reason])
    for message in errors:
        table.append(["API error", message])
    table.append(
        [
            "How to read this sheet",
            "Rows are EUVD matches to review. A component or CVE with no row on EUVD Vulnerabilities "
            "still needs review; this alias and product-name search does not cover every advisory.",
        ]
    )
    return table


def _headers(worksheet) -> list[str]:
    last = worksheet.max_column or 1
    values = []
    for col in range(1, last + 1):
        values.append(_text(worksheet.cell(2, col).value))
    while values and values[-1] == "":
        values.pop()
    return values


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return format(value, "g")
    return str(value).strip()


def _digits(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", value or ""))


def _simple_bound(text: str) -> tuple[tuple[int, ...], tuple[int, ...], bool] | None:
    match = _SIMPLE_RANGE.match(text)
    if match:
        lower = _digits(match.group(1)) if match.group(1) else ()
        inclusive = match.group(2) == "≤" or match.group(3) == "="
        return lower, _digits(match.group(4)), inclusive
    match = _PRIOR_RANGE.match(text)
    if match:
        lower = _digits(match.group(1)) if match.group(1) else ()
        return lower, _digits(match.group(2)), False
    return None


def _products(record: dict) -> list[tuple[str, str]]:
    found = []
    for entry in record.get("enisaIdProduct") or []:
        product = (entry.get("product") or {}).get("name") or ""
        if not product:
            continue
        found.append((str(product), str(entry.get("product_version") or "")))
    return found


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def _match_products(component: str, query: str, products: list[tuple[str, str]]) -> tuple[list[tuple[str, str]], bool]:
    exact = [
        item
        for item in products
        if item[0].casefold() == component.casefold() or item[0].casefold() == query.casefold()
    ]
    if exact:
        return exact, False
    query_tokens = _tokens(query)
    fuzzy = [item for item in products if query_tokens and query_tokens <= _tokens(item[0])]
    return fuzzy, bool(fuzzy)


def _aliases(raw) -> str:
    parts = [part.strip() for part in str(raw or "").replace("\n", ";").split(";")]
    found = []
    for part in parts:
        if part and part not in found:
            found.append(part)
    return "; ".join(found)


def _range_text(matched: list[tuple[str, str]]) -> str:
    return "; ".join(version for _name, version in matched)[:120]


def _stamp(now: datetime | None) -> str:
    if now is None:
        current = datetime.now(_ZONE)
    elif now.tzinfo is None:
        current = now.replace(tzinfo=_ZONE)
    else:
        current = now.astimezone(_ZONE)
    return f"{current.strftime('%b')} {current.day} {current.year}"


def _unique(items: list[str]) -> list[str]:
    found = []
    for item in items:
        if item not in found:
            found.append(item)
    return found
