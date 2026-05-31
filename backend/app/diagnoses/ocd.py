"""Rule module for obsessive-compulsive disorder (OCD)."""
from typing import List

from app.diagnoses._anxiety_common import AnxietySpectrumModule
from app.engine.context import PatientContext
from app.engine.registry import register


class OCDModule(AnxietySpectrumModule):
    def diagnosis_notes(self, ctx: PatientContext) -> List[str]:
        if not ctx.extended_rules:
            return []
        return [
            "OCD often requires higher SSRI doses and longer trials than depression before "
            "judging response; combine with exposure and response prevention (ERP) where available."
        ]


    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        recs = super().non_pharmacological(ctx)
        recs.append("Exposure and response prevention (ERP) is the first-line psychotherapy for OCD.")
        return recs

MODULE = register(OCDModule(diagnosis="ocd", display_name="Obsessive-compulsive disorder"))
