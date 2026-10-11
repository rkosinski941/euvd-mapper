"""Map an open source component to ENISA EUVD records.

Version verdicts are affected, not_affected, unknown, or disagree.
Unknown stays unknown: a version is never marked affected without a
version basis, and a product_version string that does not parse is not
turned into a guessed range.
"""

__version__ = "0.2.0"
