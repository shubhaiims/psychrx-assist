"""Shared logic for anxiety-spectrum and obsessive-compulsive disorders
(OCD, generalized anxiety disorder, panic disorder, PTSD).

Common principle encoded: SSRIs are a first-line pharmacotherapy across this group,
so they are up-ranked. Per-disorder modules add their own advisories (e.g. OCD dosing,
PTSD psychotherapy).

Extended-rule-set logic (runs only when ``ctx.extended_rules`` is on); the SSRI
first-line reason carries a placeholder citation pending psychiatrist sign-off.

Note on benzodiazepines/antipsychotics: cautions for those classes in primary anxiety
would be appropriate, but no benzodiazepine is present in the current knowledge base
and no antipsychotic is indicated for these diagnoses there, so such rules are left as
documented extension points rather than dead code.
"""
from __future__ import annotations

from app.engine.base import DiagnosisRuleModule
from app.engine.context import PatientContext
from app.engine.references import cite


class AnxietySpectrumModule(DiagnosisRuleModule):
    """Common behaviour for anxiety-spectrum / OCD modules."""

    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        if not ctx.extended_rules:
            return
        if drug.get("class_name") == "SSRI":
            card.add_reason(
                "ANX-SSRI-FIRSTLINE",
                "SSRIs are a recommended first-line pharmacotherapy for this "
                "anxiety/obsessive-compulsive disorder.",
                delta=10,
                references=cite("ANX-SSRI-FIRSTLINE"),
            )

    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        recs = super().non_pharmacological(ctx)
        recs.append("Cognitive behavioural therapy (CBT) is an effective first-line option for anxiety/OCD-spectrum disorders.")
        return recs
