"""Install vendored wheels with the pip wheel on sys.path. No PyPI."""

import sys
from pathlib import Path

wheels = Path(sys.argv[1])
matches = sorted(wheels.glob("pip-*.whl"))
if len(matches) != 1:
    names = ", ".join(path.name for path in matches)
    raise SystemExit("expected exactly one pip wheel, found: " + names)
sys.path.insert(0, str(matches[0]))
from pip._internal.cli.main import main

code = main(
    [
        "install",
        "--no-index",
        "--find-links",
        str(wheels),
        "--disable-pip-version-check",
        "pip",
        "setuptools",
        "wheel",
        "openpyxl==3.1.5",
        "tzdata==2026.5",
        "euvd-mapper==0.2.0",
    ]
)
raise SystemExit(code)
