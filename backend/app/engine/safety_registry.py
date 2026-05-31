"""Registry of safety modifiers.

Modifiers register themselves here (via ``register``) when their module is imported.
``all_modifiers`` returns them in registration order — that order is the per-drug
application order and the patient-advisory merge order, so it is deterministic and
documented in ``app/safety/__init__.py``.
"""
from __future__ import annotations

from typing import List

from app.engine.safety_base import SafetyModifier

_MODIFIERS: List[SafetyModifier] = []


def register(modifier: SafetyModifier) -> SafetyModifier:
    if any(existing.key == modifier.key for existing in _MODIFIERS):
        raise ValueError(f"Duplicate safety modifier registered for '{modifier.key}'.")
    _MODIFIERS.append(modifier)
    return modifier


def all_modifiers() -> List[SafetyModifier]:
    return list(_MODIFIERS)
