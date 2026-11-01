"""Check the embeddable zip against its SPDX file checksums."""

import hashlib
import json
import sys
import zipfile
from pathlib import Path

REQUIRED = ("python.exe", "python313.dll", "python313.zip", "python313._pth")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_sha256(document, filename):
    for package in document.get("packages") or []:
        if package.get("packageFileName") != filename:
            continue
        for entry in package.get("checksums") or []:
            algorithm = (entry.get("algorithm") or "").upper().replace("-", "")
            if algorithm == "SHA256":
                return entry.get("checksumValue", "").lower()
    return ""


def member_name(archive, wanted):
    for info in archive.infolist():
        if info.filename.replace("\\", "/").lower() == wanted:
            return info.filename
    return ""


def check_pth(archive):
    member = member_name(archive, "python313._pth")
    if not member:
        raise SystemExit("missing in zip: python313._pth")
    text = archive.read(member).decode("ascii")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or lines[0] != "python313.zip":
        raise SystemExit("python313._pth does not name python313.zip")
    if "#import site" not in text:
        raise SystemExit("python313._pth is missing the commented import site line")


def main():
    zip_path = Path(sys.argv[1])
    spdx_path = Path(sys.argv[2])
    document = json.loads(spdx_path.read_text(encoding="utf-8"))
    expected = package_sha256(document, zip_path.name)
    if not expected:
        raise SystemExit("SPDX has no SHA256 for " + zip_path.name)
    actual = sha256_file(zip_path)
    if actual != expected:
        raise SystemExit("zip sha256 mismatch: " + actual)
    with zipfile.ZipFile(zip_path) as archive:
        names = {info.filename.replace("\\", "/").lower() for info in archive.infolist()}
        for required in REQUIRED:
            if required not in names:
                raise SystemExit("missing in zip: " + required)
        check_pth(archive)
    print("zip-sha256 " + actual)
    print("pth python313.zip commented-import-site")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
