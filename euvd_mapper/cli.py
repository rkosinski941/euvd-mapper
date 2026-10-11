"""Command line for lookup and BOM enrichment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from euvd_mapper.enrich import WorkbookError, enrich_workbook
from euvd_mapper.http import HttpCache
from euvd_mapper.match import match_component, rollup_basis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="euvd_mapper")
    sub = parser.add_subparsers(dest="command", required=True)

    look = sub.add_parser("lookup", help="Map one component to EUVD records")
    look.add_argument("--purl", default="")
    look.add_argument("--name", default="")
    look.add_argument("--vendor", default="")
    look.add_argument("--version", default="")
    _cache_args(look)

    enrich = sub.add_parser("enrich-xlsx", help="Append EUVD columns to a BOM workbook")
    enrich.add_argument("input")
    enrich.add_argument("-o", "--output", default="")
    enrich.add_argument("--sheet", default="")
    enrich.add_argument("--name-column", default="")
    enrich.add_argument("--version-column", default="")
    enrich.add_argument("--purl-column", default="")
    _cache_args(enrich)

    snap = sub.add_parser("snapshot", help="Refresh a committed EUVD product snapshot")
    snap.add_argument("--product", required=True)
    snap.add_argument("--vendor", default="")
    snap.add_argument("--slug", default="")
    snap.add_argument("--out", default="")
    _cache_args(snap)

    args = parser.parse_args(argv)
    try:
        if args.command == "lookup":
            return _lookup(args)
        if args.command == "enrich-xlsx":
            return _enrich(args)
        return _snapshot(args)
    except (WorkbookError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _cache_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cache-dir", default=".cache/euvd-mapper")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--interval", type=float, default=0.35)


def _http(args) -> HttpCache:
    return HttpCache(args.cache_dir, offline=args.offline, min_interval=0 if args.offline else args.interval)


def _lookup(args) -> int:
    result = match_component(
        _http(args),
        name=args.name or None,
        version=args.version or None,
        purl=args.purl or None,
        vendor=args.vendor or None,
    )
    if result.error:
        print(result.error, file=sys.stderr)
        return 2
    ids = " ".join(item.euvd_id for item in result.notable)
    print(
        "\t".join(
            [
                result.name,
                result.version or "",
                result.verdict,
                rollup_basis(result.records, result.version),
                ids,
            ]
        )
    )
    for item in result.records:
        if item.verdict == "not_affected":
            continue
        alias = " ".join(alias for alias in item.aliases if alias.startswith(("CVE-", "GHSA-")))
        print(
            f"  {item.euvd_id}\t{item.verdict}\t{item.match_basis}\t{item.cross_check}\t{alias}\t{item.evidence}"
        )
    return 0


def _enrich(args) -> int:
    source = Path(args.input)
    output = args.output
    if not output:
        output = str(source.with_name(source.stem + "-euvd.xlsx"))
    lines = enrich_workbook(
        source,
        output,
        _http(args),
        sheet=args.sheet or None,
        name_column=args.name_column or None,
        version_column=args.version_column or None,
        purl_column=args.purl_column or None,
    )
    print("\n".join(lines))
    return 0


def _snapshot(args) -> int:
    from euvd_mapper.snapshot import write_snapshot

    destination = args.out
    if not destination:
        slug = args.slug or _slug(args.product)
        destination = str(Path("data/products") / f"{slug}.json")
    count, total = write_snapshot(
        _http(args),
        args.product,
        args.vendor,
        destination,
        slug=args.slug,
    )
    print(f"Wrote {destination} ({count} of {total})")
    return 0


def _slug(product: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", product.lower()).strip("-")
