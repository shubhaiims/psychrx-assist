"""Rule module for panic disorder."""
from typing import List

from app.diagnoses._anxiety_common import AnxietySpectrumModule
from app.engine.context import PatientContext
from app.engine.registry import register


class PanicDisorderModule(AnxietySpectrumModule):
    def diagnosis_notes(self, ctx: PatientContext) -> List[str]:
        if not ctx.extended_rules:
            return []
        return [
            "Panic disorder: start SSRIs at a low dose to limit initial activation/jitteriness, "
            "then titrate; cognitive behavioural therapy is first-line."
        ]


MODULE = register(
    PanicDisorderModule(diagnosis="panic_disorder", display_name="Panic disorder")
)
