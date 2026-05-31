"""Rule module for post-traumatic stress disorder (PTSD)."""
from typing import List

from app.diagnoses._anxiety_common import AnxietySpectrumModule
from app.engine.context import PatientContext
from app.engine.registry import register


class PTSDModule(AnxietySpectrumModule):
    def diagnosis_notes(self, ctx: PatientContext) -> List[str]:
        if not ctx.extended_rules:
            return []
        return [
            "PTSD: trauma-focused psychotherapy is a first-line treatment; SSRIs are an "
            "evidence-based pharmacological option and may be used alongside it."
        ]


    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        recs = super().non_pharmacological(ctx)
        recs.append("Trauma-focused psychotherapy (e.g. trauma-focused CBT or EMDR) is first-line for PTSD.")
        return recs

MODULE = register(PTSDModule(diagnosis="ptsd", display_name="Post-traumatic stress disorder"))
