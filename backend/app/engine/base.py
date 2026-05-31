"""The contract every diagnosis module implements.

A diagnosis module owns the prescribing logic for ONE diagnosis. The base class
provides sensible, behaviour-preserving defaults (candidate selection by indication,
the standard shared safety bundle) so a generic diagnosis "just works", and exposes
override hooks where a diagnosis genuinely differs:

    candidate_drugs(ctx, all_drugs)      which drugs are even considered
    diagnosis_specific_rules(ctx, d, c)  ranking logic unique to this diagnosis
    extra_missing_info(ctx)              extra work-up to flag for this diagnosis
    extra_red_flags(ctx)                 extra urgent flags for this diagnosis
    diagnosis_notes(ctx)                 extra footnotes for this diagnosis

Adding a new diagnosis is therefore: subclass this (or instantiate it for a generic
one), implement only the hooks that differ, and register it. The core engine never
changes.
"""
from __future__ import annotations

from typing import List

from app.engine.context import PatientContext
from app.engine.core_rules import apply_age_fit, apply_patient_preference, apply_previous_response
from app.engine.references import cite
from app.engine.scoring import new_scorecard
from app.models import RecommendationItem


class DiagnosisRuleModule:
    """Base class / generic module for a single diagnosis."""

    def __init__(self, diagnosis: str, display_name: str, notes: List[str] | None = None):
        self.diagnosis = diagnosis
        self.display_name = display_name
        self._notes = list(notes or [])

    # ----- candidate selection --------------------------------------------

    def candidate_drugs(self, ctx: PatientContext, all_drugs: List[dict]) -> List[dict]:
        """Default: every drug whose knowledge-base entry lists this diagnosis."""
        return [d for d in all_drugs if self.diagnosis in d.get("diagnoses", [])]

    # ----- override hooks (no-ops by default) -----------------------------

    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        """Ranking logic unique to this diagnosis. Override in subclasses."""
        return None

    def extra_missing_info(self, ctx: PatientContext) -> List[str]:
        return []

    def extra_red_flags(self, ctx: PatientContext) -> List[str]:
        return []

    def diagnosis_notes(self, ctx: PatientContext) -> List[str]:
        return list(self._notes)

    def non_pharmacological(self, ctx: PatientContext) -> List[str]:
        """Non-drug recommendations for this diagnosis. The generic default is broadly
        applicable; diagnosis modules extend it (e.g. ERP for OCD, trauma-focused therapy
        for PTSD). These are conservative, widely-accepted options and editable
        placeholders — confirm and tailor against local guidelines before use."""
        return [
            "Psychoeducation for the patient and, where appropriate, family/carers.",
            "Offer an evidence-based psychological therapy where indicated and available.",
            "Address sleep, substance use, and physical health alongside any medication.",
            "Agree follow-up and a safety plan; involve the multidisciplinary team as needed.",
        ]

    # ----- evaluation -----------------------------------------------------
    # Pipeline order:
    #   DX-MATCH -> core rules (age fit, preference, prior response)
    #            -> diagnosis-specific rules
    #            -> safety modifiers (one per safety dimension, registration order)
    # The safety modifiers are passed in by the orchestrator. Each modifier applies
    # its baseline portion unconditionally and its extended portion only when
    # ctx.extended_rules is on, so with extended rules off this reproduces the
    # original engine's scores and categories (the parity test guards this).

    def evaluate(self, ctx: PatientContext, drug: dict, safety_modifiers=()) -> RecommendationItem:
        card = new_scorecard(drug)
        card.add_reason(
            "DX-MATCH",
            f"Matches selected diagnosis pathway: {ctx.diagnosis.replace('_', ' ')}.",
            delta=0,
            references=cite("DX-MATCH"),
        )
        apply_age_fit(ctx, drug, card)
        apply_patient_preference(ctx, drug, card)
        apply_previous_response(ctx, drug, card)
        self.diagnosis_specific_rules(ctx, drug, card)
        for modifier in safety_modifiers:
            if modifier.applies(ctx, drug):
                modifier.apply(ctx, drug, card)
        return card.to_item()
