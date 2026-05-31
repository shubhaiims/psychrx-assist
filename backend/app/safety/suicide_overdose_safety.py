"""suicide_overdose_safety — overdose-toxicity screening under suicide risk.

Baseline (unconditional): the per-drug suicide/overdose overlay migrated verbatim
(keys on the ``suicide_risk`` boolean).

Extended: graded ``suicidality`` (plan or recent attempt) extends caution to
moderate-overdose-toxicity agents and adds safety-planning/limited-dispensing advice,
plus a patient-level red flag.
"""
from __future__ import annotations

from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.safety_base import PatientAdvisory, SafetyModifier
from app.engine.safety_registry import register
from app.engine.scoring import ScoreCard

_HIGH_RISK_SUICIDALITY = ("ideation_with_plan", "recent_attempt")


class SuicideOverdoseSafety(SafetyModifier):
    key = "suicide_overdose"
    display_name = "Suicide / overdose safety"

    def apply(self, ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
        # ----- baseline -----
        if ctx.profile.suicide_risk and drug.get("overdose_toxicity") == "high":
            card.add_caution("SUICIDE-OD", "Suicide risk present; drug has high overdose-toxicity entry.", delta=-35, references=cite("SUICIDE-OD"))

        if not ctx.extended_rules:
            return

        # ----- extended: graded suicidality -----
        if ctx.suicidality in _HIGH_RISK_SUICIDALITY:
            toxicity = drug.get("overdose_toxicity")
            if toxicity == "moderate":
                card.add_caution("SUICIDE-OD-GRADED", "Active suicidality (plan/recent attempt): even moderate overdose-toxicity agents warrant limited dispensing and a safety plan.", delta=-15, references=cite("SUICIDE-OD-GRADED"))
            if toxicity in ("moderate", "high"):
                card.add_monitoring("Limited-quantity dispensing and documented safety plan while suicidality is active.")

    def patient_advisories(self, ctx: PatientContext) -> PatientAdvisory:
        if not ctx.extended_rules:
            return PatientAdvisory()
        if ctx.suicidality in _HIGH_RISK_SUICIDALITY:
            return PatientAdvisory(red_flags=[
                "Active suicidality (plan or recent attempt): ensure urgent risk assessment, safety planning, and means restriction."
            ])
        return PatientAdvisory()


MODIFIER = register(SuicideOverdoseSafety())
