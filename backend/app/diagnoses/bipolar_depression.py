"""Rule module for bipolar depression.

Adds the antidepressant-monotherapy caution on top of the shared bipolar base. This
rule was previously a hard-coded ``if diagnosis == "bipolar_depression"`` branch in
the monolithic engine; it now lives with the diagnosis it concerns.
"""
from app.diagnoses._bipolar_common import BipolarModule
from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.registry import register


class BipolarDepressionModule(BipolarModule):
    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        # First apply the shared bipolar rule(s) (lithium family-history, etc.)
        super().diagnosis_specific_rules(ctx, drug, card)
        # Then the bipolar-depression-specific antidepressant-monotherapy caution.
        if drug.get("class_name") in ("SSRI", "SNRI"):
            card.add_caution(
                "BIP-AD-MONOTX",
                "Bipolar depression: antidepressant monotherapy should not be treated as a "
                "default option; check mood stabilizer/antimanic cover.",
                delta=-25,
                references=cite("BIP-AD-MONOTX"),
            )
        # Extended rule: lamotrigine is a first-line option for the depressive pole.
        if ctx.extended_rules and drug.get("name", "").strip().lower() == "lamotrigine":
            card.add_reason(
                "BIP-LAMOTRIGINE",
                "Lamotrigine is a first-line option for bipolar depression.",
                delta=8,
                references=cite("BIP-LAMOTRIGINE"),
            )


MODULE = register(
    BipolarDepressionModule(
        diagnosis="bipolar_depression",
        display_name="Bipolar disorder — depressive episode",
    )
)
