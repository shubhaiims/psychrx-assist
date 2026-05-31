"""adherence_safety — adherence screening.

Baseline (unconditional): the LAI up-rank migrated verbatim (non-adherence risk + an
available long-acting injectable).

Extended: when no LAI exists, add adherence-support monitoring instead.
"""
from __future__ import annotations

from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.safety_base import SafetyModifier
from app.engine.safety_registry import register
from app.engine.scoring import ScoreCard


class AdherenceSafety(SafetyModifier):
    key = "adherence"
    display_name = "Adherence safety"

    def applies(self, ctx: PatientContext, drug: dict) -> bool:
        return ctx.profile.non_adherence_risk

    def apply(self, ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
        if not ctx.profile.non_adherence_risk:
            return
        # ----- baseline -----
        if drug.get("lai_available"):
            card.add_reason("ADHERENCE-LAI", "Non-adherence risk present and a long-acting injectable option exists for this drug/class.", delta=12, references=cite("ADHERENCE-LAI"))
            return

        if not ctx.extended_rules:
            return

        # ----- extended: no LAI available -----
        card.add_monitoring("Adherence support (psychoeducation, reminders, simplified once-daily regimen, follow-up) given non-adherence risk.")


MODIFIER = register(AdherenceSafety())
