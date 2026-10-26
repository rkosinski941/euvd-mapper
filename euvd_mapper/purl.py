"""Minimal package-URL parsing for the ecosystems this tool queries."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote


class PurlError(ValueError):
    pass


@dataclass(frozen=True)
class PackageURL:
    type: str
    namespace: str | None
    name: str
    version: str | None
    raw: str

    def unversioned(self) -> str:
        parts = [f"pkg:{self.type}/"]
        if self.namespace:
            parts.append(self.namespace + "/")
        parts.append(self.name)
        return "".join(parts)

    def osv_query(self, version: str | None = None) -> dict:
        """OSV /v1/query body. Version is sent once, not also inside the purl."""
        chosen = version if version is not None else self.version
        body: dict = {"package": {"purl": self.unversioned()}}
        if chosen:
            body["version"] = chosen
        return body


def parse_purl(value: str | None) -> PackageURL | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if not raw.lower().startswith("pkg:"):
        return None
    body = raw[4:]
    body = body.split("?", 1)[0].split("#", 1)[0]
    if "/" not in body:
        raise PurlError(f"purl is missing a name: {raw}")
    type_name, remainder = body.split("/", 1)
    version = None
    if "@" in remainder:
        remainder, version = remainder.rsplit("@", 1)
        version = unquote(version) or None
    remainder = unquote(remainder)
    if "/" in remainder:
        namespace, name = remainder.rsplit("/", 1)
        namespace = namespace or None
    else:
        namespace, name = None, remainder
    if not type_name or not name:
        raise PurlError(f"purl is missing a type or name: {raw}")
    return PackageURL(
        type=unquote(type_name).lower(),
        namespace=namespace,
        name=name,
        version=version,
        raw=raw,
    )
