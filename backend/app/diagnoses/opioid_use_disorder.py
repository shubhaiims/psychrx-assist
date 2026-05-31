"""Rule module for opioid use disorder."""
from typing import List

from app.diagnoses._substance_common import SubstanceUseModule
from app.engine.context import PatientContext
from app.engine.registry import register


class OpioidUseDisorderModule(SubstanceUseModule):
    def diagnosis_notes(self, ctx: PatientContext) -> List[str]:
        if not ctx.extended_rules:
            return []
        return [
            "Opioid use disorder: first-line maintenance is usually an opioid agonist/partial "
            "agonist (e.g. methadone or buprenorphine); these are not yet in this rule set and "
            "should be added with citations. Naltrexone is an option after detoxification."
        ]


MODULE = register(
    OpioidUseDisorderModule(
        diagnosis="opioid_use_disorder",
        display_name="Opioid use disorder",
    )
)
