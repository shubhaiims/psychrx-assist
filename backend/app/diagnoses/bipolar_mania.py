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
from app.engine.utils import has_any, normalise


ANTIDEPRESSANT_KEYWORDS = [
    "sertraline",
    "escitalopram",
    "fluoxetine",
    "paroxetine",
    "venlafaxine",
    "duloxetine",
    "bupropion",
    "mirtazapine",
    "ssri",
    "snri",
    "antidepressant",
]


def _is_mixed_mania(ctx: PatientContext) -> bool:
    subtype = ctx.profile.diagnosis_subtype or ""
    return has_any([subtype], ["mixed", "dysphoric"]) or (
        ctx.profile.symptoms.manic and ctx.profile.symptoms.depressive
    )


class BipolarManiaModule(BipolarModule):
    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        # Shared bipolar rules first (lithium family-history, etc.).
        super().diagnosis_specific_rules(ctx, drug, card)
        if not ctx.extended_rules:
            return
        name = normalise(drug.get("name", ""))
        mixed = _is_mixed_mania(ctx)
        if name == "lithium":
            card.add_reason(
                "BIP-LITHIUM-FIRSTLINE",
                "Lithium is a first-line option for bipolar disorder (acute mania and "
                "maintenance) and has anti-suicidal benefit.",
                delta=8,
                references=cite("BIP-LITHIUM-FIRSTLINE"),
            )
            if mixed:
                card.add_caution(
                    "BIP-MANIA-MIXED-LITHIUM-SEQUENCE",
                    "Mixed manic presentations usually start with quetiapine or another antipsychotic; lithium may be sequenced after inadequate response or used with specialist rationale.",
                    delta=-8,
                    references=cite("BIP-MANIA-MIXED-LITHIUM-SEQUENCE"),
                )
        if drug.get("class_name") == "Second-generation antipsychotic":
            card.add_reason(
                "BIP-MANIA-ANTIPSYCHOTIC",
                "Second-generation antipsychotics are first-line agents for acute mania.",
                delta=6,
                references=cite("BIP-MANIA-ANTIPSYCHOTIC"),
            )
            if mixed:
                card.add_reason(
                    "BIP-MANIA-MIXED-SGA",
                    "Mixed mania protocol favors quetiapine or another second-generation antipsychotic before adding valproate or lithium.",
                    delta=8,
                    references=cite("BIP-MANIA-MIXED-SGA"),
                )
        if name == "valproate" and mixed:
            card.add_reason(
                "BIP-MANIA-MIXED-VALPROATE",
                "For mixed mania with inadequate antipsychotic response, valproate is a common next-step add-on when pregnancy/childbearing safety does not prohibit it.",
                delta=5,
                references=cite("BIP-MANIA-MIXED-VALPROATE"),
            )

    def diagnosis_notes(self, ctx: PatientContext) -> list[str]:
        notes = super().diagnosis_notes(ctx)
        if not ctx.extended_rules:
            return notes
        if has_any(ctx.profile.current_medications, ANTIDEPRESSANT_KEYWORDS):
            notes.append(
                "Acute mania protocol: stop or hold antidepressants unless a specialist documents a clear reason to continue."
            )
        if _is_mixed_mania(ctx):
            notes.append(
                "Mixed mania protocol: start with quetiapine or another second-generation antipsychotic, add valproate if needed, and avoid routine dual-antipsychotic combinations except cross-tapering."
            )
        else:
            notes.append(
                "Nonmixed acute mania protocol: lithium is a core first-line option; add or switch to an antipsychotic if response is inadequate, and consider ECT for urgent, delirious, catatonic, or refractory mania."
            )
        return notes


MODULE = register(
    BipolarManiaModule(
        diagnosis="bipolar_mania",
        display_name="Bipolar disorder — acute mania",
    )
)
