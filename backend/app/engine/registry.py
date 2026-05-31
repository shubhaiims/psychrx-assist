"""Diagnosis-module registry and dispatcher.

Each diagnosis module registers itself here (via ``register``). ``get_module``
dispatches a diagnosis string to its module. ``assert_registry_complete`` is a
startup integrity guard: if someone adds a value to the ``Diagnosis`` enum but
forgets to write/register a module for it (or registers one for a diagnosis that
doesn't exist), the application refuses to start with a clear error rather than
silently mis-routing a patient to a generic fallback.
"""
from __future__ import annotations

from typing import Dict

from app.engine.base import DiagnosisRuleModule

_REGISTRY: Dict[str, DiagnosisRuleModule] = {}


def register(module: DiagnosisRuleModule) -> DiagnosisRuleModule:
    if module.diagnosis in _REGISTRY:
        raise ValueError(f"Duplicate diagnosis module registered for '{module.diagnosis}'.")
    _REGISTRY[module.diagnosis] = module
    return module


def get_module(diagnosis: str) -> DiagnosisRuleModule:
    """Return the module for a diagnosis, or a safe generic fallback."""
    module = _REGISTRY.get(diagnosis)
    if module is None:
        # Defensive only: assert_registry_complete() should prevent reaching here.
        return DiagnosisRuleModule(diagnosis, diagnosis.replace("_", " ").title())
    return module


def all_modules() -> Dict[str, DiagnosisRuleModule]:
    return dict(_REGISTRY)


def assert_registry_complete() -> None:
    """Verify the registry covers exactly the Diagnosis enum (no gaps, no extras)."""
    from app.models import Diagnosis

    enum_values = {d.value for d in Diagnosis}
    registered = set(_REGISTRY)
    missing = enum_values - registered
    extra = registered - enum_values
    problems = []
    if missing:
        problems.append(f"diagnoses with no registered module: {sorted(missing)}")
    if extra:
        problems.append(f"registered modules for unknown diagnoses: {sorted(extra)}")
    if problems:
        raise RuntimeError("Diagnosis registry is inconsistent — " + "; ".join(problems))
