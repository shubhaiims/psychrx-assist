"""Rule module for behavioural symptoms in dementia.

The key population-specific safety rule for this diagnosis — antipsychotics carry a
boxed warning for increased mortality and cerebrovascular events in elderly patients
with dementia — is implemented by the elderly safety modifier
(``safety/elderly_safety.py``, rule ``GERI-ANTIPSYCHOTIC-DEMENTIA``), which strongly
down-ranks second-generation antipsychotics for an elderly dementia patient and records
the risk-benefit caution in ``rule_trace``. It is part of the extended rule set and
carries a placeholder citation pending psychiatrist sign-off.

This module therefore keeps only diagnosis-level defaults. A reviewer could add
dementia-specific ranking here (e.g. preferring particular agents for specific
behavioural targets) with citations.
"""
from app.engine.base import DiagnosisRuleModule
from app.engine.context import PatientContext
from app.engine.registry import register


class DementiaModule(DiagnosisRuleModule):
    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        recs = super().non_pharmacological(ctx)
        recs += [
            "Non-pharmacological behavioural management is FIRST-LINE for behavioural and "
            "psychological symptoms of dementia: identify and treat triggers (pain, infection, "
            "constipation, sensory or environmental factors) before considering medication.",
            "Caregiver education and support; structured activities and environmental adaptation.",
        ]
        return recs


MODULE = register(
    DementiaModule(
        diagnosis="dementia_related_behavioural_symptoms",
        display_name="Behavioural symptoms in dementia",
    )
)
