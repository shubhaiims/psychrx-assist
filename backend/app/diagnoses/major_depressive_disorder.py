"""Rule module for major depressive disorder (MDD).

Encodes a small set of widely-accepted, explainable MDD prescribing principles:

* SSRIs are a first-line pharmacotherapy and are up-ranked;
* second-generation antipsychotics in unipolar depression are augmentation/adjunct
  options (or for psychotic features), not first-line monotherapy, and are mildly
  down-ranked; with psychotic-features severity they are instead noted as appropriate
  augmentation;
* a monitoring reminder for emergent suicidality early in antidepressant treatment;
* an advisory that psychotherapy is a first-line option for milder MDD.

All rules below are part of the *extended* rule set: they run only when
``ctx.extended_rules`` is on, and each carries a placeholder citation in
references.json that a psychiatrist must confirm before clinical use.
"""
from app.engine.base import DiagnosisRuleModule
from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.registry import register


class MajorDepressiveDisorderModule(DiagnosisRuleModule):
    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        if not ctx.extended_rules:
            return
        class_name = drug.get("class_name", "")

        if class_name == "SSRI":
            card.add_reason(
                "MDD-SSRI-FIRSTLINE",
                "SSRIs are a recommended first-line pharmacotherapy for major depressive disorder.",
                delta=10,
                references=cite("MDD-SSRI-FIRSTLINE"),
            )
            card.add_monitoring(
                "Monitor for emergent suicidality/agitation early in treatment and after dose changes."
            )

        if class_name == "Second-generation antipsychotic":
            if ctx.severity == "severe_with_psychotic_features":
                card.add_reason(
                    "MDD-PSYCHOTIC-AUGMENT",
                    "Depression with psychotic features: an antipsychotic (with an "
                    "antidepressant) or ECT is appropriate rather than antidepressant monotherapy.",
                    delta=8,
                    references=cite("MDD-PSYCHOTIC-AUGMENT"),
                )
            else:
                card.add_caution(
                    "MDD-SGA-ADJUNCT",
                    "In unipolar depression, antipsychotics are augmentation/adjunct options "
                    "(or for psychotic features), not first-line monotherapy.",
                    delta=-12,
                    references=cite("MDD-SGA-ADJUNCT"),
                )

    def diagnosis_notes(self, ctx: PatientContext):
        if not ctx.extended_rules:
            return []
        return [
            "For mild major depressive disorder, evidence-based psychotherapy may be offered "
            "before or alongside pharmacotherapy."
        ]


    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        recs = super().non_pharmacological(ctx)
        recs += [
            "Structured psychotherapy (e.g. CBT, behavioural activation, or IPT).",
            "Behavioural activation, exercise, and sleep/routine support.",
        ]
        return recs

MODULE = register(
    MajorDepressiveDisorderModule(
        diagnosis="major_depressive_disorder",
        display_name="Major depressive disorder",
    )
)
