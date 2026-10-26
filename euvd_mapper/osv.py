"""OSV.dev query by package URL and version."""

from __future__ import annotations

from euvd_mapper.purl import parse_purl

OSV_QUERY = "https://api.osv.dev/v1/query"


def query_affecting(http, purl: str, version: str | None) -> list[dict]:
    """Vulns OSV says affect this purl and version. Each item has id and aliases."""
    parsed = parse_purl(purl)
    if parsed is None:
        return []
    body = parsed.osv_query(version)
    found: list[dict] = []
    seen: set[str] = set()
    seen_tokens: set[str] = set()
    token = None
    while True:
        if token:
            if token in seen_tokens:
                break
            seen_tokens.add(token)
        page = dict(body)
        if token:
            page["page_token"] = token
        payload = http.post_json(OSV_QUERY, page)
        for vuln in payload.get("vulns") or []:
            aliases = []
            for value in [vuln.get("id"), *(vuln.get("aliases") or [])]:
                if value and value not in aliases:
                    aliases.append(value)
            key = aliases[0] if aliases else ""
            if not key or key in seen:
                continue
            seen.add(key)
            found.append({"id": vuln.get("id"), "aliases": aliases, "summary": vuln.get("summary") or ""})
        token = payload.get("next_page_token")
        if not token:
            break
    return found
