"""Combine the OSV package query with EUVD product ranges.

Both paths are kept visible. A record is affected only when a version
basis says so and the other path does not contradict it. A malformed
product_version stays unknown. An exact product_version that the
description calls a "before" bound stays unknown rather than being
treated as the affected set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from euvd_mapper.aliases import names_match, normalize_name, product_names_for
from euvd_mapper.euvd import lookup_alias, search_product
from euvd_mapper.osv import query_affecting
from euvd_mapper.purl import parse_purl
from euvd_mapper.versionrange import (
    Version,
    evaluate_product_version,
    parse_constraints,
    parse_user_version,
)

_BEFORE_WINDOW = re.compile(r"(?i)\b(?:before|prior\s+to|earlier\s+than)\b(.{0,80})")
_VERSION_TOKEN = re.compile(
    r"(?i)(?<![A-Za-z0-9])(\d+(?:\.\d+)*[.\-](?:alpha|beta|milestone|rc|cr|preview|pre|snapshot|m)\d*|\d+(?:\.\d+)+|\d+)(?![A-Za-z0-9])"
)


@dataclass
class RecordHit:
    euvd_id: str
    aliases: list[str]
    score: float | None
    severity: str | None
    verdict: str
    match_basis: str
    evidence: str
    cross_check: str
    osv_verdict: str | None = None
    euvd_verdict: str | None = None


@dataclass
class ComponentResult:
    name: str
    version: str | None
    purl: str | None
    vendor: str | None
    records: list[RecordHit] = field(default_factory=list)
    error: str | None = None

    @property
    def verdict(self) -> str:
        return rollup_verdict(self.records, self.version)

    @property
    def notable(self) -> list[RecordHit]:
        """Records a reviewer should read: affected or disagree."""
        return [item for item in self.records if item.verdict in {"affected", "disagree"}]


def match_component(
    http,
    name: str | None = None,
    version: str | None = None,
    purl: str | None = None,
    vendor: str | None = None,
) -> ComponentResult:
    parsed = parse_purl(purl) if purl else None
    component_name = (name or "").strip() or (parsed.name if parsed else "")
    component_version = (version or "").strip() or (parsed.version if parsed else None)
    if component_version == "":
        component_version = None
    result = ComponentResult(
        name=component_name,
        version=component_version,
        purl=parsed.raw if parsed else (purl or None),
        vendor=(vendor or "").strip() or None,
    )
    if not component_name and parsed is None:
        result.error = "no component name or purl"
        return result

    osv_ids: set[str] = set()
    by_id: dict[str, dict] = {}
    ran_osv = False
    if parsed is not None and component_version and parse_user_version(component_version) is not None:
        ran_osv = True
        for vuln in query_affecting(http, parsed.raw, component_version):
            osv_ids.update(vuln["aliases"])
            record = _first_euvd(http, vuln["aliases"])
            if record is not None:
                by_id[str(record["id"])] = record

    if component_name:
        for product in product_names_for(component_name):
            items, _total = search_product(http, product)
            for item in items:
                eid = str(item.get("id") or "")
                if eid and eid not in by_id:
                    by_id[eid] = item

    hits: list[RecordHit] = []
    for eid in sorted(by_id):
        hit = _judge(
            by_id[eid],
            component_name,
            component_version,
            parsed.raw if parsed else None,
            osv_ids,
            ran_osv,
            result.vendor,
        )
        if hit is not None:
            hits.append(hit)
    result.records = hits
    return result


def rollup_verdict(records: list[RecordHit], version: str | None) -> str:
    verdicts = {item.verdict for item in records}
    if "affected" in verdicts:
        return "affected"
    if "disagree" in verdicts:
        return "disagree"
    if not version or parse_user_version(version) is None:
        return "unknown"
    if not records:
        return "unknown"
    if verdicts <= {"not_affected"}:
        return "not_affected"
    return "unknown"


def rollup_basis(records: list[RecordHit], version: str | None) -> str:
    notable = [item for item in records if item.verdict in {"affected", "disagree"}]
    chosen = notable or records
    bases = []
    for item in chosen:
        for part in item.match_basis.split(","):
            part = part.strip()
            if part and part not in bases:
                bases.append(part)
    if bases:
        return ", ".join(bases)
    if not version or parse_user_version(version) is None:
        return "name-only"
    return "euvd-range"


def severity_for(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 9:
        return "critical"
    if score >= 7:
        return "high"
    if score >= 4:
        return "medium"
    if score > 0:
        return "low"
    return None


def format_score(score: float | None) -> str:
    if score is None:
        return ""
    label = severity_for(score)
    text = f"{score:g}"
    if label:
        return f"{label} {text}"
    return text


def _first_euvd(http, aliases: list[str]) -> dict | None:
    for alias in _lookup_order(aliases):
        record = lookup_alias(http, alias)
        if record is not None:
            return record
    return None


def _lookup_order(aliases: list[str]) -> list[str]:
    def rank(alias: str) -> tuple[int, str]:
        if alias.startswith("CVE-"):
            group = 0
        elif alias.startswith("GHSA-"):
            group = 1
        elif alias.startswith("PYSEC-"):
            group = 2
        elif alias.startswith("EUVD-"):
            group = 3
        else:
            group = 4
        return group, alias

    unique = []
    for alias in aliases:
        if alias and alias not in unique:
            unique.append(alias)
    return sorted(unique, key=rank)


def _judge(
    record: dict,
    component_name: str,
    version: str | None,
    purl: str | None,
    osv_ids: set[str],
    ran_osv: bool,
    vendor: str | None,
) -> RecordHit | None:
    aliases = aliases_of(record)
    identity = set(aliases)
    identity.add(str(record.get("id") or ""))
    osv_affected = bool(identity & osv_ids)
    ranges = _matching_ranges(record, component_name, vendor)
    product_matched = ranges is not None
    if not product_matched and not osv_affected:
        return None

    euvd_verdict, euvd_evidence = _euvd_side(ranges or [], record.get("description") or "", version)
    osv_verdict = None
    if ran_osv:
        osv_verdict = "affected" if osv_affected else "not_affected"

    verdict, basis, cross = _combine(osv_verdict, euvd_verdict, ran_osv, product_matched, version)
    evidence = _evidence(osv_verdict, euvd_evidence, purl, version, aliases, ran_osv)
    score = score_of(record)
    return RecordHit(
        euvd_id=str(record.get("id") or ""),
        aliases=aliases,
        score=score,
        severity=severity_for(score),
        verdict=verdict,
        match_basis=basis,
        evidence=evidence,
        cross_check=cross,
        osv_verdict=osv_verdict,
        euvd_verdict=euvd_verdict,
    )


def _combine(
    osv_verdict: str | None,
    euvd_verdict: str,
    ran_osv: bool,
    product_matched: bool,
    version: str | None,
) -> tuple[str, str, str]:
    comparable = bool(version) and parse_user_version(version) is not None
    if not ran_osv:
        if not comparable:
            return "unknown", "name-only", "not_run"
        if not product_matched:
            return "unknown", "name-only", "not_run"
        basis = "euvd-range" if euvd_verdict != "unknown" else "euvd-range"
        return euvd_verdict, basis, "not_run"

    if osv_verdict == "affected" and euvd_verdict == "affected":
        return "affected", "osv-range", "agree"
    if osv_verdict == "affected" and euvd_verdict == "not_affected":
        return "disagree", "osv-range", "disagree"
    if osv_verdict == "affected" and euvd_verdict == "unknown":
        return "affected", "osv-range", "osv_only"
    if osv_verdict == "not_affected" and euvd_verdict == "affected":
        return "disagree", "euvd-range", "disagree"
    if osv_verdict == "not_affected" and euvd_verdict == "not_affected":
        return "not_affected", "euvd-range", "agree"
    if not comparable:
        return "unknown", "name-only", "not_run"
    return "unknown", "euvd-range", "unconfirmed"


def _evidence(
    osv_verdict: str | None,
    euvd_evidence: str,
    purl: str | None,
    version: str | None,
    aliases: list[str],
    ran_osv: bool,
) -> str:
    parts = []
    if ran_osv:
        shown = ", ".join(alias for alias in aliases if alias.startswith(("CVE-", "GHSA-", "PYSEC-")))
        target = purl or "this purl"
        if version and purl and "@" not in purl:
            target = f"{purl}@{version}"
        if osv_verdict == "affected":
            parts.append(f"OSV lists {shown or 'this id'} for {target}")
        else:
            parts.append(f"OSV query for {target} did not list {shown or 'this id'}")
    if euvd_evidence:
        parts.append(euvd_evidence)
    return "; ".join(parts)


def _euvd_side(version_strings: list[str], description: str, version: str | None) -> tuple[str, str]:
    if not version or not str(version).strip():
        return "unknown", "no version supplied; not marked affected"
    if parse_user_version(version) is None:
        return "unknown", f"version '{version}' is not a comparable version"
    if not version_strings:
        return "unknown", "EUVD record has no product_version for this component"
    usable = []
    contradicted = []
    for text in version_strings:
        constraints = parse_constraints(text)
        if (
            constraints
            and all(item.exact is not None for item in constraints)
            and _description_contradicts(description, [item.exact for item in constraints if item.exact])
        ):
            contradicted.append(text)
            continue
        usable.append(evaluate_product_version(text, version))
    if not usable and contradicted:
        shown = _clip(contradicted[0])
        return (
            "unknown",
            f"product_version '{shown}' contradicts the description (before/prior); left unknown",
        )
    if any(item.verdict == "affected" for item in usable):
        return "affected", next(item.evidence for item in usable if item.verdict == "affected")
    if any(item.verdict == "unknown" for item in usable):
        return "unknown", next(item.evidence for item in usable if item.verdict == "unknown")
    if usable:
        return "not_affected", usable[0].evidence
    return "unknown", "EUVD product_version is not a parseable range"


def _description_contradicts(description: str, pins: list[Version]) -> bool:
    if not description or not pins:
        return False
    pin_keys = {_version_key(item) for item in pins}
    mentioned: set[tuple] = set()
    for match in _BEFORE_WINDOW.finditer(description):
        for token in _VERSION_TOKEN.findall(match.group(1)):
            parsed = parse_user_version(token)
            if parsed is not None:
                mentioned.add(_version_key(parsed))
    return bool(pin_keys & mentioned)


def _version_key(version: Version) -> tuple:
    return (version.numbers, version.pre_rank, version.pre_num)


def _matching_ranges(record: dict, component_name: str, vendor: str | None) -> list[str] | None:
    matched = False
    ranges: list[str] = []
    for entry in record.get("enisaIdProduct") or []:
        product = ((entry.get("product") or {}).get("name")) or ""
        if not names_match(component_name, product):
            continue
        vend = (((entry.get("product") or {}).get("vendor") or {}).get("name")) or ""
        if vendor and not _vendor_ok(vendor, vend):
            continue
        matched = True
        ranges.append(entry.get("product_version") or "")
    if not matched:
        return None
    return ranges


def _vendor_ok(wanted: str, found: str) -> bool:
    left = normalize_name(wanted)
    right = normalize_name(found)
    if not right or right in {"n/a", "na", "unknown"}:
        return True
    if not left:
        return True
    return left == right or left in right or right in left


def aliases_of(record: dict) -> list[str]:
    raw = record.get("aliases") or ""
    found = []
    for part in re.split(r"[\s,;]+", str(raw).strip()):
        if part and part not in found:
            found.append(part)
    return found


def score_of(record: dict) -> float | None:
    value = record.get("baseScore")
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _clip(text: str, limit: int = 180) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."
