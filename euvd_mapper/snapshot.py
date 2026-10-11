"""Write the product snapshots the GitHub Page reads."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from euvd_mapper.euvd import SEARCH_URL, search_product


def write_snapshot(http, product: str, vendor: str, out_path: str | Path, slug: str = "") -> tuple[int, int | None]:
    items, total = search_product(http, product, vendor=vendor)
    destination = Path(out_path)
    payload = {
        "queriedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "product": product,
        "vendor": vendor,
        "source": SEARCH_URL,
        "totalReported": total,
        "itemCount": len(items),
        "items": items,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _update_catalog(destination, product, vendor, slug or _slug(product), len(items), total)
    return len(items), total


def _update_catalog(destination: Path, product: str, vendor: str, slug: str, count: int, total: int | None) -> None:
    catalog_path = destination.parent.parent / "catalog.json"
    if destination.parent.name != "products" or not catalog_path.exists():
        return
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    entry = {
        "id": slug,
        "name": product,
        "vendor": vendor,
        "file": f"products/{destination.name}",
        "queryProduct": product,
        "itemCount": count,
        "total": total,
    }
    products = [item for item in catalog.get("products", []) if item.get("id") != slug]
    products.append(entry)
    products.sort(key=lambda item: item.get("name", "").lower())
    catalog["products"] = products
    catalog["generated"] = datetime.now(timezone.utc).date().isoformat()
    catalog_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")


def _slug(product: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", product.lower()).strip("-")
