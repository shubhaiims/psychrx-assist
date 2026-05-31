"""cardiac_qtc_safety — QT-interval and cardiac-illness screening.

Baseline (unconditional): the per-drug QTc modifier migrated verbatim.
Extended: cardiac illness raises the bar for QT-prolonging agents (baseline ECG/QTc and
cardiology input), and flags a baseline ECG when none is on file.
"""
from __future__ import annotations

from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.safety_base import SafetyModifier
from app.engine.safety_registry import register
from app.engine.scoring import ScoreCard


class CardiacQtcSafety(SafetyModifier):
    key = "cardiac_qtc"
    display_name = "Cardiac / QTc safety"

    def applies(self, ctx: PatientContext, drug: dict) -> bool:
        return ctx.profile.labs.qtc_ms is not None or ctx.cardiac_disease

    def apply(self, ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
        qtc = ctx.profile.labs.qtc_ms
        qt_risk = drug.get("qt_risk")
        # ----- baseline: measured QTc -----
        if qtc is not None:
            if qtc >= 500 and qt_risk in ("moderate", "high"):
                card.add_caution("QTC-HIGH-500", "QTc >= 500 ms and this drug has QT concern in the rule entry.", delta=-70, references=cite("QTC-HIGH-500"))
            elif qtc >= 470 and qt_risk == "high":
                card.add_caution("QTC-HIGH-470", "Borderline/prolonged QTc with high QT-risk drug entry.", delta=-35, references=cite("QTC-HIGH-470"))

        if not ctx.extended_rules:
            return

        # ----- extended: cardiac illness -----
        if ctx.cardiac_disease and qt_risk in ("moderate", "high"):
            card.add_caution("CARDIAC-QT-ILLNESS", "Cardiac illness with a QT-prolonging agent: obtain baseline ECG/QTc, correct electrolytes, and involve cardiology where appropriate.", delta=-15, references=cite("CARDIAC-QT-ILLNESS"))
            card.add_monitoring("ECG/QTc monitoring with QT-prolonging agents in cardiac illness.")
            if qtc is None:
                card.add_investigation("Baseline ECG/QTc before a QT-prolonging agent in cardiac illness.")


MODIFIER = register(CardiacQtcSafety())
