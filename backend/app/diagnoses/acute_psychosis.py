"""Rule module for acute psychosis.

Uses the shared psychosis logic plus an acute-presentation advisory to exclude
organic/substance-induced causes before committing to a maintenance plan.
"""
from typing import List

from app.diagnoses._psychosis_common import PsychosisModule
from app.engine.context import PatientContext
from app.engine.registry import register


class AcutePsychosisModule(PsychosisModule):
    def diagnosis_notes(self, ctx: PatientContext) -> List[str]:
        notes = super().diagnosis_notes(ctx)
        if ctx.extended_rules:
            notes.append(
                "Acute psychosis: exclude organic and substance-induced causes and delirium "
                "before committing to a long-term antipsychotic plan."
            )
        return notes


MODULE = register(
    AcutePsychosisModule(
        diagnosis="acute_psychosis",
        display_name="Acute psychosis",
    )
)
