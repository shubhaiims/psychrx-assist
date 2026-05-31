"""Rule module for generalized anxiety disorder (GAD)."""
from typing import List

from app.diagnoses._anxiety_common import AnxietySpectrumModule
from app.engine.context import PatientContext
from app.engine.registry import register


class GeneralizedAnxietyDisorderModule(AnxietySpectrumModule):
    def diagnosis_notes(self, ctx: PatientContext) -> List[str]:
        if not ctx.extended_rules:
            return []
        return [
            "Generalized anxiety disorder: SSRIs/SNRIs are first-line; cognitive behavioural "
            "therapy is an effective first-line alternative or adjunct."
        ]


MODULE = register(
    GeneralizedAnxietyDisorderModule(
        diagnosis="generalized_anxiety_disorder",
        display_name="Generalized anxiety disorder",
    )
)
