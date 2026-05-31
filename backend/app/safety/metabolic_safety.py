"""metabolic_safety — metabolic-risk screening.

Baseline (unconditional): the per-drug metabolic modifiers migrated verbatim.
Extended: routine metabolic monitoring for second-generation antipsychotics.
"""
from __future__ import annotations

from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.safety_base import SafetyModifier
from app.engine.safety_registry import register
from app.engine.scoring import ScoreCard


class MetabolicSafety(SafetyModifier):
    key = "metabolic"
    display_name = "Metabolic safety"

    def apply(self, ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
        high_metabolic = drug.get("metabolic_risk") == "high"
        # ----- baseline -----
        if ctx.bmi is not None and ctx.bmi >= 30 and high_metabolic:
            card.add_caution("METAB-BMI", "BMI is high and this drug is high metabolic-risk in the rule entry.", delta=-30, references=cite("METAB-BMI"))
        if ctx.has_metabolic_comorbidity and high_metabolic:
            card.add_caution("METAB-COMORBID", "Metabolic comorbidity present; this drug is high metabolic-risk in the rule entry.", delta=-30, references=cite("METAB-COMORBID"))

        if not ctx.extended_rules:
            return

        # ----- extended: SGA metabolic monitoring (any patient) -----
        if drug.get("class_name") == "Second-generation antipsychotic":
            card.add_monitoring("Baseline and periodic metabolic monitoring (weight/BMI, fasting glucose/HbA1c, lipids) for second-generation antipsychotics.")


MODIFIER = register(MetabolicSafety())
