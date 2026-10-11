"""Disk cache and polite HTTP for the public OSV and EUVD APIs."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from euvd_mapper import __version__

USER_AGENT = f"euvd-mapper/{__version__} (https://github.com/rkosinski941/euvd-mapper)"


class CacheMiss(LookupError):
    def __init__(self, key: str):
        super().__init__(f"offline cache miss: {key}")
        self.key = key


class HttpError(RuntimeError):
    def __init__(self, status: int, url: str, detail: str = ""):
        super().__init__(f"HTTP {status} for {url} {detail}".strip())
        self.status = status
        self.url = url


class HttpCache:
    """Resumable JSON cache. Failed 429/5xx responses are not stored."""

    def __init__(
        self,
        cache_dir: str | Path,
        offline: bool = False,
        min_interval: float = 0.35,
        opener=None,
    ):
        self.cache_dir = Path(cache_dir)
        self.offline = offline
        self.min_interval = min_interval
        self._opener = opener
        self._last_network = 0.0

    def get_json(self, url: str) -> dict:
        status, payload = self._request("GET", url, None)
        if status == 404:
            raise HttpError(404, url)
        return payload

    def post_json(self, url: str, body: dict) -> dict:
        status, payload = self._request("POST", url, body)
        if status == 404:
            raise HttpError(404, url)
        return payload

    def _request(self, method: str, url: str, body: dict | None) -> tuple[int, dict]:
        digest = _digest(method, url, body)
        cached = self._read(digest)
        if cached is not None:
            return cached["status"], cached["payload"]
        if self.offline:
            raise CacheMiss(url)
        status, payload = self._fetch(method, url, body)
        if status == 200 or status == 404:
            stored = payload
            if "api.osv.dev" in url and isinstance(payload, dict):
                stored = trim_osv_response(payload)
            self._write(digest, {"status": status, "url": url, "method": method, "payload": stored})
            if "api.osv.dev" in url:
                payload = stored
        return status, payload

    def _read(self, digest: str) -> dict | None:
        path = self._path(digest)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, digest: str, envelope: dict) -> None:
        path = self._path(digest)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")

    def _path(self, digest: str) -> Path:
        return self.cache_dir / digest[:2] / f"{digest}.json"

    def _fetch(self, method: str, url: str, body: dict | None) -> tuple[int, dict]:
        delay = 1.0
        last_error: Exception | None = None
        for _attempt in range(4):
            self._pause()
            try:
                status, payload = self._once(method, url, body)
            except HttpError as exc:
                last_error = exc
                if exc.status == 429 or exc.status >= 500:
                    time.sleep(delay)
                    delay = min(delay * 2, 16)
                    continue
                raise
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                time.sleep(delay)
                delay = min(delay * 2, 16)
                continue
            if status == 429 or status >= 500:
                time.sleep(delay)
                delay = min(delay * 2, 16)
                last_error = HttpError(status, url)
                continue
            return status, payload
        if isinstance(last_error, Exception):
            raise last_error
        raise HttpError(0, url, "request failed")

    def _pause(self) -> None:
        if self.min_interval <= 0:
            return
        wait = self.min_interval - (time.monotonic() - self._last_network)
        if wait > 0:
            time.sleep(wait)
        self._last_network = time.monotonic()

    def _once(self, method: str, url: str, body: dict | None) -> tuple[int, dict]:
        data = None
        headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        opener = self._opener or urllib.request.urlopen
        try:
            with opener(request, timeout=90) as response:
                raw = response.read()
                status = getattr(response, "status", 200)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            if exc.code == 404:
                return 404, {}
            raise HttpError(exc.code, url, detail) from exc
        if not raw:
            return status, {}
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise HttpError(status, url, "response was not JSON") from exc
        if not isinstance(payload, dict):
            raise HttpError(status, url, "response was not a JSON object")
        return status, payload


def trim_osv_response(payload: dict) -> dict:
    """Keep the fields the matcher reads. Drop version lists and prose."""
    vulns = []
    for vuln in payload.get("vulns") or []:
        affected = []
        for item in vuln.get("affected") or []:
            ranges = []
            for rng in item.get("ranges") or []:
                ranges.append({"type": rng.get("type"), "events": rng.get("events") or []})
            affected.append({"package": item.get("package"), "ranges": ranges})
        vulns.append(
            {
                "id": vuln.get("id"),
                "aliases": vuln.get("aliases") or [],
                "summary": vuln.get("summary"),
                "affected": affected,
            }
        )
    trimmed = {"vulns": vulns}
    if payload.get("next_page_token"):
        trimmed["next_page_token"] = payload["next_page_token"]
    return trimmed


def _digest(method: str, url: str, body: dict | None) -> str:
    blob = json.dumps(
        {"method": method, "url": url, "body": body},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
