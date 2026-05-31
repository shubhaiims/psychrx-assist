"""Shared logic for substance use disorders (alcohol, opioid).

Common safety principle encoded: naltrexone is an opioid antagonist, so an opioid-free
interval must be confirmed before starting it to avoid precipitated withdrawal. This is
recorded as a caution plus a required investigation.

Extended-rule-set logic (runs only when ``ctx.extended_rules`` is on); the caution
carries a placeholder citation pending psychiatrist sign-off.
"""
from __future__ import annotations

from app.engine.base import DiagnosisRuleModule
from app.engine.context import PatientContext
from app.engine.references import cite


class SubstanceUseModule(DiagnosisRuleModule):
    """Common behaviour for substance-use-disorder modules."""

    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        if not ctx.extended_rules:
            return
        if drug.get("name", "").strip().lower() == "naltrexone":
            card.add_caution(
                "SUD-NALTREXONE-OPIOID-FREE",
                "Naltrexone is an opioid antagonist: confirm an adequate opioid-free interval "
                "(and follow local naloxone-challenge protocol) before starting, to avoid "
                "precipitated withdrawal; not for actively opioid-dependent patients without "
                "prior detoxification.",
                delta=-15,
                references=cite("SUD-NALTREXONE-OPIOID-FREE"),
            )
            card.add_investigation(
                "Confirm opioid-free interval / withdrawal status before naltrexone initiation."
            )

    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        recs = super().non_pharmacological(ctx)
        recs += [
            "Psychosocial treatment (e.g. motivational interviewing, relapse-prevention CBT).",
            "Mutual-help groups and recovery support; harm-reduction advice where appropriate.",
        ]
        return recs
