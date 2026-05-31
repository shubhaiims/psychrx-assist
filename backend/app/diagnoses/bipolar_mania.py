"""Rule module for bipolar mania.

Extends the shared bipolar base (lithium family-history, TSH work-up) with
phase-specific first-line logic for acute mania:

* lithium is up-ranked as a first-line antimanic option; and
* second-generation antipsychotics are up-ranked as first-line antimanic agents.

These are extended-rule-set additions (run only when ``ctx.extended_rules`` is on);
each carries a placeholder citation in references.json pending psychiatrist sign-off.
The valproate-in-childbearing caution is handled by the pregnancy/lactation
population layer, so it is not duplicated here.
"""
from app.diagnoses._bipolar_common import BipolarModule
from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.registry import register


class BipolarManiaModule(BipolarModule):
    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        # Shared bipolar rules first (lithium family-history, etc.).
        super().diagnosis_specific_rules(ctx, drug, card)
        if not ctx.extended_rules:
            return
        if drug.get("name", "").strip().lower() == "lithium":
            card.add_reason(
                "BIP-LITHIUM-FIRSTLINE",
                "Lithium is a first-line option for bipolar disorder (acute mania and "
                "maintenance) and has anti-suicidal benefit.",
                delta=8,
                references=cite("BIP-LITHIUM-FIRSTLINE"),
            )
        if drug.get("class_name") == "Second-generation antipsychotic":
            card.add_reason(
                "BIP-MANIA-ANTIPSYCHOTIC",
                "Second-generation antipsychotics are first-line agents for acute mania.",
                delta=6,
                references=cite("BIP-MANIA-ANTIPSYCHOTIC"),
            )


MODULE = register(
    BipolarManiaModule(
        diagnosis="bipolar_mania",
        display_name="Bipolar disorder — acute mania",
    )
)
