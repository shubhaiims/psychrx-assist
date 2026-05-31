"""Rule module for bipolar maintenance.

Extends the shared bipolar base with maintenance-phase first-line logic:

* lithium is up-ranked as a first-line maintenance option; and
* lamotrigine is up-ranked for maintenance (particularly for the depressive pole).

Extended-rule-set additions (run only when ``ctx.extended_rules`` is on); each
carries a placeholder citation pending psychiatrist sign-off. The
valproate-in-childbearing caution is handled by the pregnancy/lactation population
layer, so it is not duplicated here.
"""
from app.diagnoses._bipolar_common import BipolarModule
from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.registry import register


class BipolarMaintenanceModule(BipolarModule):
    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        super().diagnosis_specific_rules(ctx, drug, card)
        if not ctx.extended_rules:
            return
        name = drug.get("name", "").strip().lower()
        if name == "lithium":
            card.add_reason(
                "BIP-LITHIUM-FIRSTLINE",
                "Lithium is a first-line maintenance option in bipolar disorder and has "
                "anti-suicidal benefit.",
                delta=8,
                references=cite("BIP-LITHIUM-FIRSTLINE"),
            )
        if name == "lamotrigine":
            card.add_reason(
                "BIP-LAMOTRIGINE",
                "Lamotrigine is effective for maintenance in bipolar disorder, particularly "
                "for preventing depressive episodes.",
                delta=6,
                references=cite("BIP-LAMOTRIGINE"),
            )


MODULE = register(
    BipolarMaintenanceModule(
        diagnosis="bipolar_maintenance",
        display_name="Bipolar disorder — maintenance",
    )
)
