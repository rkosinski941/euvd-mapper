"""Parse EUVD product_version strings and compare component versions.

Handles the shapes ENISA actually stores, including:

- ``9.0.0.M1 to 9.0.20`` and ``8.5.0 to 8.5.75``
- ``8.5.85 <= 8.5.93`` (the source text uses U+2264)
- ``Apache Tomcat 9 <9.0.42`` and ``Apache Tomcat 8.5 <8.5.62``
- ``prior to`` / ``before`` / ``and earlier``
- comma-separated lists of ranges
- milestone, alpha, beta, and RC ordering (``9.0.0.M1 < 9.0.0``)

A string that contains a range operator but no complete range is unknown.
That includes malformed values such as ``2.0-beta9 <log4j-core*``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_QUAL_RANK = {
    "alpha": 0,
    "beta": 1,
    "milestone": 2,
    "m": 2,
    "rc": 3,
    "cr": 3,
    "preview": 3,
    "pre": 3,
    "snapshot": 4,
}

# Release sorts above every prerelease tag.
_RELEASE_RANK = 100

_TOKEN_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])("
    r"\d+(?:\.\d+)*\.[x*]"
    r"|\d+(?:\.\d+)*[.\-](?:alpha|beta|milestone|rc|cr|preview|pre|snapshot|m)\d*"
    r"|\d+(?:\.\d+)+"
    r"|\d+"
    r")(?![A-Za-z0-9])"
)

_BEFORE_RE = re.compile(r"(?i)\b(?:prior\s+to|earlier\s+than|before)\b")
_EARLIER_RE = re.compile(r"(?i)\band\s+earlier\b")
_BETWEEN_RE = re.compile(r"(?i)\bbetween\b")
_AND_RE = re.compile(r"(?i)\band\b")
_TO_RE = re.compile(r"(?i)\bto\b")


@dataclass(frozen=True)
class Version:
    numbers: tuple[int, ...]
    pre_rank: int | None = None
    pre_num: int = 0
    wildcard: bool = False

    def label(self) -> str:
        base = ".".join(str(n) for n in self.numbers)
        if self.wildcard:
            return base + ".x"
        if self.pre_rank is None:
            return base
        name = next(k for k, v in _QUAL_RANK.items() if v == self.pre_rank and len(k) > 1)
        return f"{base}-{name}{self.pre_num}"


@dataclass(frozen=True)
class _Token:
    start: int
    end: int
    text: str
    version: Version


@dataclass(frozen=True)
class Constraint:
    lower: Version | None = None
    lower_inclusive: bool = True
    upper: Version | None = None
    upper_inclusive: bool = True
    exact: Version | None = None
    prefix: tuple[int, ...] | None = None
    branch: tuple[int, ...] | None = None


@dataclass(frozen=True)
class RangeResult:
    verdict: str
    evidence: str


def cmp_version(left: Version, right: Version) -> int:
    """Return -1, 0, or 1. Prereleases sort before the matching release."""
    if left.wildcard or right.wildcard:
        raise ValueError("wildcard versions are prefixes, not points")
    length = max(len(left.numbers), len(right.numbers))
    for i in range(length):
        av = left.numbers[i] if i < len(left.numbers) else 0
        bv = right.numbers[i] if i < len(right.numbers) else 0
        if av != bv:
            return -1 if av < bv else 1
    ar = _RELEASE_RANK if left.pre_rank is None else left.pre_rank
    br = _RELEASE_RANK if right.pre_rank is None else right.pre_rank
    if ar != br:
        return -1 if ar < br else 1
    if left.pre_num != right.pre_num:
        return -1 if left.pre_num < right.pre_num else 1
    return 0


def parse_user_version(text: str | None) -> Version | None:
    """Parse a single component version. Extra words make it unknown."""
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    raw = re.sub(r"(?i)^v(?=\d)", "", raw)
    tokens = _tokens(raw)
    if len(tokens) != 1:
        return None
    if tokens[0].text.lower() != raw.lower():
        return None
    if tokens[0].version.wildcard:
        return None
    return tokens[0].version


def parse_constraints(text: str | None) -> list[Constraint] | None:
    """Return constraints, or None when the text is not a usable range.

    None means unknown. It is not an empty affected-set.
    """
    if text is None:
        return None
    raw = str(text).strip()
    if not raw or raw.casefold() in {"n/a", "na", "none", "unknown", "unspecified", "-"}:
        return None
    cleaned = re.sub(r"\[[^\]]*\]", " ", raw)
    cleaned = cleaned.replace("\u2264", " <= ").replace("\u2265", " >= ").replace("\u2266", " <= ")
    clauses = [part.strip() for part in cleaned.split(",") if part.strip()]
    parsed: list[Constraint] = []
    for clause in clauses:
        piece = _parse_clause(clause)
        if piece is None:
            return None
        parsed.extend(piece)
    if not parsed:
        return None
    return parsed


def evaluate_product_version(range_text: str | None, version: str | None) -> RangeResult:
    """Compare one product_version string to one component version."""
    shown = _clip(range_text)
    if version is None or not str(version).strip():
        return RangeResult("unknown", "no version supplied")
    version_text = str(version).strip()
    target = parse_user_version(version_text)
    if target is None:
        return RangeResult(
            "unknown",
            f"version '{version_text}' is not a comparable version",
        )
    constraints = parse_constraints(range_text)
    if constraints is None:
        return RangeResult(
            "unknown",
            f"EUVD product_version '{shown}' is not a parseable range",
        )
    if any(_contains(item, target) for item in constraints):
        return RangeResult("affected", f"EUVD range '{shown}' includes {version_text}")
    return RangeResult("not_affected", f"EUVD range '{shown}' excludes {version_text}")


def version_might_match(range_text: str | None, version: str | None) -> bool:
    """True only when the range parses and includes the version."""
    return evaluate_product_version(range_text, version).verdict == "affected"


def _clip(text: str | None, limit: int = 180) -> str:
    raw = "" if text is None else str(text).strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 1] + "..."


def _tokens(text: str) -> list[_Token]:
    found: list[_Token] = []
    for match in _TOKEN_RE.finditer(text):
        token = match.group(1)
        found.append(
            _Token(match.start(1), match.end(1), token, _parse_token(token))
        )
    return found


def _parse_token(token: str) -> Version:
    wildcard = re.fullmatch(r"(?i)\d+(?:\.\d+)*\.[x*]", token)
    if wildcard:
        parts = token.split(".")
        numbers = tuple(int(part) for part in parts[:-1])
        return Version(numbers=numbers, wildcard=True)
    pre = re.fullmatch(
        r"(?i)(\d+(?:\.\d+)*)[.\-](alpha|beta|milestone|rc|cr|preview|pre|snapshot|m)(\d*)",
        token,
    )
    if pre:
        numbers = tuple(int(part) for part in pre.group(1).split("."))
        qual = pre.group(2).lower()
        pre_num = int(pre.group(3) or "0")
        return Version(numbers=numbers, pre_rank=_QUAL_RANK[qual], pre_num=pre_num)
    numbers = tuple(int(part) for part in token.split("."))
    return Version(numbers=numbers)


def _parse_clause(clause: str) -> list[Constraint] | None:
    between = _BETWEEN_RE.search(clause)
    if between:
        rest = clause[between.end() :]
        conjunction = _AND_RE.search(rest)
        if conjunction is None:
            return None
        left = _first(rest[: conjunction.start()])
        right = _first(rest[conjunction.end() :])
        if left is None or right is None or left.version.wildcard or right.version.wildcard:
            return None
        return [
            Constraint(
                lower=left.version,
                lower_inclusive=True,
                upper=right.version,
                upper_inclusive=True,
            )
        ]

    earlier = _EARLIER_RE.search(clause)
    if earlier:
        left = _last(clause[: earlier.start()])
        if left is None or left.version.wildcard:
            return None
        return [
            Constraint(
                upper=left.version,
                upper_inclusive=True,
                branch=_branch(clause[: left.start], left.version),
            )
        ]

    before = _BEFORE_RE.search(clause)
    if before:
        right = _first(clause[before.end() :])
        if right is None or right.version.wildcard:
            return None
        return [
            Constraint(
                upper=right.version,
                upper_inclusive=False,
                branch=_branch(clause[: before.end()], right.version),
            )
        ]

    word_to = _TO_RE.search(clause)
    if word_to:
        left = _last(clause[: word_to.start()])
        right = _first(clause[word_to.end() :])
        if left is None or right is None or left.version.wildcard or right.version.wildcard:
            return None
        return [
            Constraint(
                lower=left.version,
                lower_inclusive=True,
                upper=right.version,
                upper_inclusive=True,
            )
        ]

    ops = _cmp_ops(clause)
    if ops:
        op, index = ops[0]
        left = _last(clause[:index])
        right = _first(clause[index + len(op) :])
        if right is None or right.version.wildcard:
            return None
        if op in {"<=", ">="} and left is not None and left.version.wildcard:
            return None
        if op == "<=" and left is not None and not _is_line_label(left.version, right.version):
            return [
                Constraint(
                    lower=left.version,
                    lower_inclusive=True,
                    upper=right.version,
                    upper_inclusive=True,
                )
            ]
        if op == "<=":
            return [
                Constraint(
                    upper=right.version,
                    upper_inclusive=True,
                    branch=_branch(clause[:index], right.version),
                )
            ]
        if op == "<" and left is not None and not _is_line_label(left.version, right.version):
            if left.version.wildcard:
                return None
            return [
                Constraint(
                    lower=left.version,
                    lower_inclusive=True,
                    upper=right.version,
                    upper_inclusive=False,
                )
            ]
        if op == "<":
            return [
                Constraint(
                    upper=right.version,
                    upper_inclusive=False,
                    branch=_branch(clause[:index], right.version),
                )
            ]
        if op == ">=" and left is None:
            return [Constraint(lower=right.version, lower_inclusive=True)]
        if op == ">" and left is None:
            return [Constraint(lower=right.version, lower_inclusive=False)]
        return None

    tokens = _tokens(clause)
    if not tokens:
        return []
    specific = max(tokens, key=lambda item: (len(item.version.numbers), item.start))
    if specific.version.wildcard:
        return [Constraint(prefix=specific.version.numbers)]
    return [Constraint(exact=specific.version)]


def _cmp_ops(clause: str) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    index = 0
    while index < len(clause):
        if clause.startswith("<=", index) or clause.startswith(">=", index):
            found.append((clause[index : index + 2], index))
            index += 2
        elif clause[index] in "<>":
            found.append((clause[index], index))
            index += 1
        else:
            index += 1
    return found


def _first(text: str) -> _Token | None:
    tokens = _tokens(text)
    return tokens[0] if tokens else None


def _last(text: str) -> _Token | None:
    tokens = _tokens(text)
    return tokens[-1] if tokens else None


def _is_line_label(left: Version, upper: Version) -> bool:
    """True when left is a short product line such as '9' or '8.5', not a bound."""
    if left.wildcard or left.pre_rank is not None:
        return False
    numbers = left.numbers
    return len(numbers) < len(upper.numbers) and upper.numbers[: len(numbers)] == numbers


def _branch(prefix: str, upper: Version) -> tuple[int, ...] | None:
    """A leading line label such as '8.5' or '9' in front of an upper bound."""
    for token in reversed(_tokens(prefix)):
        numbers = token.version.numbers
        if token.version.wildcard or token.version.pre_rank is not None:
            continue
        if len(numbers) < len(upper.numbers) and upper.numbers[: len(numbers)] == numbers:
            return numbers
    return None


def _shares(version: Version, prefix: tuple[int, ...]) -> bool:
    padded = version.numbers
    if len(padded) < len(prefix):
        padded = padded + (0,) * (len(prefix) - len(padded))
    return padded[: len(prefix)] == prefix


def _contains(constraint: Constraint, version: Version) -> bool:
    if constraint.exact is not None:
        return cmp_version(version, constraint.exact) == 0
    if constraint.prefix is not None:
        return _shares(version, constraint.prefix)
    if constraint.branch is not None and not _shares(version, constraint.branch):
        return False
    if constraint.lower is not None:
        order = cmp_version(version, constraint.lower)
        if constraint.lower_inclusive:
            if order < 0:
                return False
        elif order <= 0:
            return False
    if constraint.upper is not None:
        order = cmp_version(version, constraint.upper)
        if constraint.upper_inclusive:
            if order > 0:
                return False
        elif order >= 0:
            return False
    return constraint.lower is not None or constraint.upper is not None
