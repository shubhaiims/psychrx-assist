"""Shared logic for the three bipolar phases (mania, depression, maintenance).

These rules were previously hard-coded inside the monolithic engine. They are
genuinely diagnosis-specific, so they belong here rather than in the shared bundle:

* a TSH baseline is flagged as missing before lithium / mood-stabiliser planning;
* a documented family history of lithium response up-ranks lithium.

The bipolar-depression module adds one more rule on top of this base (see that file).
"""
from __future__ import annotations

from typing import List

from app.engine.base import DiagnosisRuleModule
from app.engine.context import PatientContext
from app.engine.references import cite


class BipolarModule(DiagnosisRuleModule):
    """Common behaviour for all bipolar phases."""

    def extra_missing_info(self, ctx: PatientContext) -> List[str]:
        # TSH baseline is bipolar-specific work-up (lithium / mood stabiliser planning).
        if ctx.profile.labs.tsh is None:
            return ["TSH before lithium or mood-stabilizer planning"]
        return []

    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        # Family-history-guided lithium selection.
        if drug["name"].lower() == "lithium" and ctx.family_history_has(
            ["good lithium response", "lithium responder"]
        ):
            card.add_reason(
                "BIP-LITHIUM-FHX",
                "Family history suggests lithium response.",
                delta=10,
                references=cite("BIP-LITHIUM-FHX"),
            )

    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        recs = super().non_pharmacological(ctx)
        recs += [
            "Psychoeducation on relapse signatures and a written relapse-prevention plan.",
            "Stabilise sleep and daily routines; reduce alcohol/substances.",
        ]
        return recs
