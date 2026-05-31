"""seizure_safety — seizure-threshold screening (neurological illness).

Extended only (no baseline). Clozapine lowers the seizure threshold in a dose-dependent
way (already reflected in its monitoring), so in a patient with a seizure disorder it is
down-ranked with added monitoring. Restricted to clozapine because that is the agent
with a clear, well-established effect in the current knowledge base; per-drug
seizure-threshold data would be needed to extend this safely to other agents.
"""
from __future__ import annotations

from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.safety_base import PatientAdvisory, SafetyModifier
from app.engine.safety_registry import register
from app.engine.scoring import ScoreCard


class SeizureSafety(SafetyModifier):
    key = "seizure"
    display_name = "Seizure-threshold safety"

    def applies(self, ctx: PatientContext, drug: dict) -> bool:
        return ctx.seizure_disorder

    def apply(self, ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
        if not ctx.extended_rules:
            return
        if not ctx.seizure_disorder:
            return
        if drug.get("name", "").strip().lower() == "clozapine":
            card.add_caution("SEIZURE-CLOZAPINE", "Clozapine lowers the seizure threshold (dose-dependent); in a seizure disorder use cautiously, titrate slowly, and consider anticonvulsant cover and EEG.", delta=-20, references=cite("SEIZURE-CLOZAPINE"))
            card.add_monitoring("Seizure monitoring (and EEG where indicated) with clozapine in a seizure disorder.")

    def patient_advisories(self, ctx: PatientContext) -> PatientAdvisory:
        if not ctx.extended_rules or not ctx.seizure_disorder:
            return PatientAdvisory()
        return PatientAdvisory(notes=[
            "Seizure disorder: review the seizure-threshold effect and anticonvulsant interactions of any psychotropic, and coordinate with neurology."
        ])


MODIFIER = register(SeizureSafety())
