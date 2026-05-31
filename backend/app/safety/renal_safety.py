"""renal_safety — renal-function screening.

Baseline (unconditional): the per-drug renal modifier migrated verbatim.
Extended: an extra caution for severe impairment (eGFR < 30) on renally-cleared agents.
"""
from __future__ import annotations

from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.safety_base import SafetyModifier
from app.engine.safety_registry import register
from app.engine.scoring import ScoreCard


class RenalSafety(SafetyModifier):
    key = "renal"
    display_name = "Renal safety"

    def applies(self, ctx: PatientContext, drug: dict) -> bool:
        return ctx.renal_impaired

    def apply(self, ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
        rule = drug.get("renal", "standard")
        if rule == "avoid_severe_or_specialist":
            card.add_caution("RENAL-AVOID", "Renal impairment/eGFR concern: specialist dosing or alternative required.", delta=-45, references=cite("RENAL-AVOID"))
        elif rule == "dose_adjust":
            card.add_caution("RENAL-DOSEADJ", "Renal impairment: dose adjustment and monitoring required.", delta=-20, references=cite("RENAL-DOSEADJ"))
        # NOTE: a "specialist_review" renal value is intentionally NOT down-ranked
        # (legacy behaviour). Flagged for clinical review; left unchanged for parity.

        if not ctx.extended_rules:
            return

        # Extended: severe impairment on a renally-cleared/contraindicated agent.
        if ctx.egfr is not None and ctx.egfr < 30 and rule == "avoid_severe_or_specialist":
            card.add_caution("RENAL-SEVERE", "Severe renal impairment (eGFR < 30): specialist input and a renally safer alternative are usually preferred for this agent.", delta=-15, references=cite("RENAL-SEVERE"))
            card.add_investigation("Specialist renal-dosing review (eGFR < 30) before this agent.")


MODIFIER = register(RenalSafety())
