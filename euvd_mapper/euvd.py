"""ENISA EUVD search and id/alias lookup.

Paging was checked against the live /api/search endpoint: page is 0-based,
size max is 100, and a short or empty page ends the walk. Callers dedupe
by EUVD id because a repeated page must not be treated as new records.
"""

from __future__ import annotations

import urllib.parse

from euvd_mapper.http import HttpError

SEARCH_URL = "https://euvdservices.enisa.europa.eu/api/search"
ID_URL = "https://euvdservices.enisa.europa.eu/api/enisaid"
PAGE_SIZE = 100


def search_product(http, product: str, vendor: str = "", max_pages: int = 20) -> tuple[list[dict], int | None]:
    items: list[dict] = []
    seen: set[str] = set()
    total: int | None = None
    for page in range(max_pages):
        query = {"product": product, "size": PAGE_SIZE, "page": page}
        if vendor:
            query["vendor"] = vendor
        url = SEARCH_URL + "?" + urllib.parse.urlencode(query)
        try:
            payload = http.get_json(url)
        except HttpError as exc:
            if exc.status == 404:
                break
            raise
        if total is None and payload.get("total") is not None:
            total = int(payload["total"])
        batch = payload.get("items") or []
        added = 0
        for item in batch:
            eid = str(item.get("id") or "")
            if not eid or eid in seen:
                continue
            seen.add(eid)
            items.append(item)
            added += 1
        if not batch or added == 0:
            break
        if total is not None and len(items) >= total:
            break
    return items, total


def lookup_alias(http, alias: str) -> dict | None:
    """GET /api/enisaid. The id parameter accepts an EUVD id, CVE, or GHSA."""
    url = ID_URL + "?" + urllib.parse.urlencode({"id": alias})
    try:
        payload = http.get_json(url)
    except HttpError as exc:
        if exc.status == 404:
            return None
        raise
    if not payload or not payload.get("id"):
        return None
    return payload
