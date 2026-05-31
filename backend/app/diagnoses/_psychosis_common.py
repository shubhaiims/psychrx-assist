"""Shared logic for psychotic disorders (schizophrenia, acute psychosis).

Encodes widely-accepted antipsychotic prescribing principles:

* clozapine is reserved for treatment-resistant illness and requires mandatory
  blood-count (ANC) monitoring, so it is down-ranked as a default choice; and
* second-generation antipsychotics require metabolic monitoring.

Extended-rule-set logic (runs only when ``ctx.extended_rules`` is on); each
reason/caution carries a placeholder citation pending psychiatrist sign-off.
"""
from __future__ import annotations

from typing import List

from app.engine.base import DiagnosisRuleModule
from app.engine.context import PatientContext
from app.engine.references import cite


class PsychosisModule(DiagnosisRuleModule):
    """Common behaviour for psychotic-disorder modules."""

    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        if not ctx.extended_rules:
            return
        name = drug.get("name", "").strip().lower()

        if name == "clozapine":
            card.add_caution(
                "PSY-CLOZAPINE-TRD",
                "Clozapine is reserved for treatment-resistant schizophrenia (typically after "
                "two adequate antipsychotic trials) and requires mandatory blood-count (ANC) "
                "monitoring for agranulocytosis; it is not a first-line choice.",
                delta=-25,
                references=cite("PSY-CLOZAPINE-TRD"),
            )
        # NOTE: routine metabolic monitoring for second-generation antipsychotics is
        # applied by metabolic_safety (cross-cutting), so it is not repeated here.

    def diagnosis_notes(self, ctx: PatientContext) -> List[str]:
        if not ctx.extended_rules:
            return []
        return [
            "Antipsychotic choice should weigh efficacy with metabolic, extrapyramidal, "
            "prolactin and sedation profiles and patient preference, alongside psychosocial "
            "interventions."
        ]

    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        recs = super().non_pharmacological(ctx)
        recs += [
            "Family psychoeducation and support.",
            "Cognitive behavioural therapy for psychosis (CBTp) where available.",
            "Supported employment/education and recovery-oriented rehabilitation.",
        ]
        return recs
