"""Safety-modifier framework.

A ``SafetyModifier`` is a self-contained module that screens a single drug for a
single safety dimension (pregnancy, renal, hepatic, cardiac/QTc, metabolic, seizure,
elderly, child/adolescent, suicide/overdose, adherence, interactions). Each one can:

* up-rank a drug          -> ``card.add_reason(..., delta=+N)``
* down-rank a drug        -> ``card.add_caution(..., delta=-N)``
* move to "use with caution"        -> ``card.add_caution(...)`` (any caution does this)
* move to "relatively unsuitable"   -> ``card.mark_unsuitable(...)`` (forces the bucket)
* add a missing investigation       -> ``card.add_investigation(...)``
* add a monitoring requirement       -> ``card.add_monitoring(...)``
* add explanation text               -> the ``detail`` passed to the above
* add citation placeholders          -> ``references=cite(rule_id)``

It can also contribute *patient-level* advisories (missing investigations, red flags,
notes) via ``patient_advisories``.

Design rules for every modifier:
- The behaviour-preserving baseline portion (where one exists) is applied
  unconditionally; the richer, clinician-authored logic is guarded by
  ``ctx.extended_rules`` so the engine can reproduce the original output exactly.
- No unsupported medical claims. Encode widely-accepted, structural logic and key it
  on fields that actually exist in the knowledge base; everything carries a
  placeholder citation for a clinician to confirm.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from app.engine.context import PatientContext
from app.engine.scoring import ScoreCard


@dataclass
class PatientAdvisory:
    """Patient-level (not per-drug) output a safety modifier can contribute."""
    missing_information: List[str] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


class SafetyModifier:
    """Base class for a single-dimension safety screen."""

    key: str = "safety"
    display_name: str = "Safety"

    def applies(self, ctx: PatientContext, drug: dict) -> bool:
        """Cheap pre-check so the engine can skip irrelevant modifiers. Default True;
        modules still guard internally, so this is an optimisation, not the contract."""
        return True

    def apply(self, ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
        """Adjust one drug's score/reasons/cautions/investigations/monitoring."""
        return None

    def patient_advisories(self, ctx: PatientContext) -> PatientAdvisory:
        """Patient-level missing investigations / red flags / notes for this dimension."""
        return PatientAdvisory()
