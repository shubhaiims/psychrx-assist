"""Rule module for bipolar depression.

Adds the antidepressant-monotherapy caution on top of the shared bipolar base. This
rule was previously a hard-coded ``if diagnosis == "bipolar_depression"`` branch in
the monolithic engine; it now lives with the diagnosis it concerns.
"""
from app.diagnoses._bipolar_common import BipolarModule
from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.registry import register
from app.engine.utils import has_any, normalise


PREFERRED_BIPOLAR_DEPRESSION_OPTIONS = {
    "lithium": "Lithium is an early bipolar-depression option, especially when suicide prevention or maintenance benefit matters.",
    "quetiapine": "Quetiapine is a first-line bipolar-depression option with acute antidepressant evidence.",
    "lamotrigine": "Lamotrigine is a first-line bipolar-depression option and is useful for depressive-pole maintenance.",
    "lurasidone": "Lurasidone is a first-line bipolar-depression option with relatively low metabolic burden.",
    "cariprazine": "Cariprazine is a first-line bipolar-depression option, including where bipolar depression and activation/mixed features need careful review.",
}


def _is_mixed_or_rapid(ctx: PatientContext) -> bool:
    subtype = ctx.profile.diagnosis_subtype or ""
    return (
        has_any([subtype], ["mixed", "rapid_cycling", "rapid cycling", "antidepressant_induced", "switch"])
        or (ctx.profile.symptoms.depressive and ctx.profile.symptoms.manic)
    )


class BipolarDepressionModule(BipolarModule):
    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        # First apply the shared bipolar rule(s) (lithium family-history, etc.)
        super().diagnosis_specific_rules(ctx, drug, card)
        # Then the bipolar-depression-specific antidepressant-monotherapy caution.
        class_name = drug.get("class_name")
        name = normalise(drug.get("name", ""))
        is_antidepressant = class_name in ("SSRI", "SNRI") or (
            ctx.extended_rules and name == "bupropion"
        )
        if is_antidepressant:
            if ctx.extended_rules and _is_mixed_or_rapid(ctx):
                card.add_caution(
                    "BIP-DEP-AD-RISK",
                    "Bipolar depression with mixed features, rapid cycling, or antidepressant activation history: avoid antidepressant monotherapy and review mood-stabilising cover before considering any antidepressant.",
                    delta=-45,
                    references=cite("BIP-DEP-AD-RISK"),
                )
            card.add_caution(
                "BIP-AD-MONOTX",
                "Bipolar depression: antidepressant monotherapy should not be treated as a "
                "default option; check mood stabilizer/antimanic cover.",
                delta=-25,
                references=cite("BIP-AD-MONOTX"),
            )
        if not ctx.extended_rules:
            return
        if name in PREFERRED_BIPOLAR_DEPRESSION_OPTIONS:
            card.add_reason(
                "BIP-DEP-PREFERRED",
                PREFERRED_BIPOLAR_DEPRESSION_OPTIONS[name],
                delta=10,
                references=cite("BIP-DEP-PREFERRED"),
            )
        # Keep the older rule id for compatibility and test readability.
        if name == "lamotrigine":
            card.add_reason(
                "BIP-LAMOTRIGINE",
                "Lamotrigine is a first-line option for bipolar depression.",
                delta=8,
                references=cite("BIP-LAMOTRIGINE"),
            )

    def diagnosis_notes(self, ctx: PatientContext) -> list[str]:
        notes = super().diagnosis_notes(ctx)
        if not ctx.extended_rules:
            return notes
        notes.append(
            "Bipolar depression protocol: start with lithium, quetiapine, lamotrigine, lurasidone, or cariprazine; delay antidepressants unless mixed/rapid-cycling risk is excluded and antimanic cover is in place."
        )
        if _is_mixed_or_rapid(ctx):
            notes.append(
                "Mixed features or rapid cycling documented: antidepressants should be avoided or used only with specialist justification and mood-stabilising cover."
            )
        return notes


MODULE = register(
    BipolarDepressionModule(
        diagnosis="bipolar_depression",
        display_name="Bipolar disorder — depressive episode",
    )
)
