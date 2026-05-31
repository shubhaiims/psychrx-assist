"""Small, pure helper functions shared across the rule engine.

These were previously top-level functions inside the monolithic engine. They are
deliberately dependency-free and deterministic.
"""
from __future__ import annotations

from typing import Iterable


def normalise(text: str) -> str:
    """Lower-case, trim, and convert spaces/hyphens to underscores.

    Used so that free-text fields (comorbidities, family history, drug names)
    can be matched against keyword lists regardless of casing/spacing.
    """
    return text.strip().lower().replace(" ", "_").replace("-", "_")


def enum_value(value) -> str:
    """Return ``value.value`` for an Enum, otherwise ``str(value)``.

    Pydantic may hand us either an Enum member or a plain string depending on how
    the model was constructed, so we normalise to a plain string once, here.
    """
    return value.value if hasattr(value, "value") else str(value)


def has_any(items: Iterable[str], keywords: Iterable[str]) -> bool:
    """True if any keyword appears (normalised) inside the joined items."""
    haystack = " ".join(normalise(x) for x in items)
    return any(normalise(k) in haystack for k in keywords)
