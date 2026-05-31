"""hepatic_safety — hepatic-function screening.

Baseline (unconditional): the per-drug hepatic modifier migrated verbatim.
Extended: a valproate hepatotoxicity caution in hepatic impairment.
"""
from __future__ import annotations

from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.safety_base import SafetyModifier
from app.engine.safety_registry import register
from app.engine.scoring import ScoreCard


class HepaticSafety(SafetyModifier):
    key = "hepatic"
    display_name = "Hepatic safety"

    def applies(self, ctx: PatientContext, drug: dict) -> bool:
        return ctx.hepatic_impaired

    def apply(self, ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
        rule = drug.get("hepatic", "standard")
        if rule == "avoid_severe_or_specialist":
            card.add_caution("HEPATIC-AVOID", "Hepatic impairment: avoid or use only with specialist review according to rule entry.", delta=-45, references=cite("HEPATIC-AVOID"))
        elif rule == "start_low_go_slow":
            card.add_caution("HEPATIC-SLOWLOW", "Hepatic impairment: start low, go slow, and monitor LFT/clinical toxicity.", delta=-15, references=cite("HEPATIC-SLOWLOW"))

        if not ctx.extended_rules:
            return

        # Extended: valproate is hepatotoxic — caution in hepatic impairment.
        if drug.get("name", "").strip().lower() == "valproate":
            card.add_caution("HEPATIC-VALPROATE", "Valproate is hepatotoxic; avoid or use only with specialist review and close LFT monitoring in hepatic impairment.", delta=-20, references=cite("HEPATIC-VALPROATE"))
            card.add_monitoring("Liver function tests before and during valproate in hepatic impairment.")


MODIFIER = register(HepaticSafety())
