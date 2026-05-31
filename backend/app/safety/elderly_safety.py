"""elderly_safety — older-adult screening (geriatric psychiatry).

Extended only. Implements the antipsychotic-in-dementia boxed-warning caution, a general
antipsychotic caution in older adults, a sedation/fall-risk caution (using the drug's
``sedation`` field as a proxy), and a 'start low, go slow' advisory.
"""
from __future__ import annotations

from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.safety_base import PatientAdvisory, SafetyModifier
from app.engine.safety_registry import register
from app.engine.scoring import ScoreCard

_DEMENTIA = "dementia_related_behavioural_symptoms"


class ElderlySafety(SafetyModifier):
    key = "elderly"
    display_name = "Elderly safety"

    def applies(self, ctx: PatientContext, drug: dict) -> bool:
        return ctx.age_group == "elderly"

    def apply(self, ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
        if not ctx.extended_rules or ctx.age_group != "elderly":
            return
        is_antipsychotic = drug.get("class_name") == "Second-generation antipsychotic"

        if is_antipsychotic and ctx.diagnosis == _DEMENTIA:
            card.add_caution("GERI-ANTIPSYCHOTIC-DEMENTIA", "Antipsychotics increase mortality and cerebrovascular events in elderly patients with dementia (boxed warning); reserve for severe risk/distress after non-pharmacological measures, use the lowest dose for the shortest time, and document consent and regular review.", delta=-35, references=cite("GERI-ANTIPSYCHOTIC-DEMENTIA"))
        elif is_antipsychotic:
            card.add_caution("GERI-ANTIPSYCHOTIC-ELDERLY", "Use antipsychotics cautiously in older adults (sedation, falls, cerebrovascular, metabolic and anticholinergic burden); start low and review regularly.", delta=-10, references=cite("GERI-ANTIPSYCHOTIC-ELDERLY"))

        if drug.get("sedation") == "high":
            card.add_caution("GERI-SEDATION-FALLS", "Highly sedating agent in an older adult: increased fall and cognitive-impairment risk; consider a lower-sedation alternative.", delta=-12, references=cite("GERI-SEDATION-FALLS"))

    def patient_advisories(self, ctx: PatientContext) -> PatientAdvisory:
        if not ctx.extended_rules or ctx.age_group != "elderly":
            return PatientAdvisory()
        return PatientAdvisory(notes=[
            "Older adults: 'start low, go slow', minimise polypharmacy and anticholinergic burden, check renal function for renally-cleared drugs, and review regularly (a structured Beers/STOPP review is recommended once per-drug burden data is added)."
        ])


MODIFIER = register(ElderlySafety())
