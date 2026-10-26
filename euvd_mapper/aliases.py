"""Component name aliases for EUVD product names.

EUVD product search is product-scoped. Maven artifacts such as
tomcat-catalina are not EUVD product names. Substring matching is not
used: "Apache Tomcat" does not match "Apache Tomcat Native", and
"lodash" does not match "lodash.template".
"""

from __future__ import annotations

import re


def normalize_name(name: str | None) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().casefold())


# Keys are normalized package or product names.
_ALIASES: dict[str, tuple[str, ...]] = {
    "tomcat": ("Apache Tomcat",),
    "tomcat-catalina": ("Apache Tomcat",),
    "tomcat-embed-core": ("Apache Tomcat",),
    "tomcat-embed-websocket": ("Apache Tomcat",),
    "tomcat-coyote": ("Apache Tomcat",),
    "tomcat-jasper": ("Apache Tomcat",),
    "tomcat-jdbc": ("Apache Tomcat",),
    "tomcat-jni": ("Apache Tomcat",),
    "tomcat-api": ("Apache Tomcat",),
    "tomcat-util": ("Apache Tomcat",),
    "apache tomcat": ("Apache Tomcat",),
    "apache-tomcat": ("Apache Tomcat",),
    "log4j-core": ("Apache Log4j2",),
    "log4j-api": ("Apache Log4j API",),
    "apache log4j2": ("Apache Log4j2",),
    "apache log4j": ("Apache Log4j",),
    "lodash": ("lodash",),
    "jackson-databind": ("jackson-databind",),
    "fasterxml jackson-databind": ("jackson-databind",),
    "django": ("Django",),
}


def product_names_for(name: str | None) -> tuple[str, ...]:
    """EUVD product names to search for a component name."""
    key = normalize_name(name)
    if not key:
        return ()
    if key in _ALIASES:
        return _ALIASES[key]
    return (re.sub(r"\s+", " ", (name or "").strip()),)


def names_match(query_name: str | None, product_name: str | None) -> bool:
    """True when product_name is an exact alias target (or the query itself)."""
    product = normalize_name(product_name)
    if not product:
        return False
    targets = {normalize_name(item) for item in product_names_for(query_name)}
    targets.add(normalize_name(query_name))
    targets.discard("")
    return product in targets
