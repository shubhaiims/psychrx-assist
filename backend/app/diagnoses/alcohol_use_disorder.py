"""Rule module for alcohol use disorder."""
from typing import List

from app.diagnoses._substance_common import SubstanceUseModule
from app.engine.context import PatientContext
from app.engine.registry import register


class AlcoholUseDisorderModule(SubstanceUseModule):
    def diagnosis_notes(self, ctx: PatientContext) -> List[str]:
        if not ctx.extended_rules:
            return []
        return [
            "Alcohol use disorder: naltrexone and acamprosate are evidence-based for relapse "
            "prevention (disulfiram in selected patients); acamprosate/disulfiram are not yet "
            "represented in this rule set and should be added with citations. Combine with "
            "psychosocial treatment."
        ]


MODULE = register(
    AlcoholUseDisorderModule(
        diagnosis="alcohol_use_disorder",
        display_name="Alcohol use disorder",
    )
)
