"""Shared logic for anxiety-spectrum and obsessive-compulsive disorders
(OCD, generalized anxiety disorder, panic disorder, PTSD).

Common principle encoded: SSRIs are a first-line pharmacotherapy across this group,
so they are up-ranked. Per-disorder modules add their own advisories (e.g. OCD dosing,
PTSD psychotherapy).

Extended-rule-set logic (runs only when ``ctx.extended_rules`` is on); the SSRI
first-line reason carries a placeholder citation pending psychiatrist sign-off.

Diagnosis modules add condition-specific safeguards for benzodiazepines,
antipsychotics, and other later-line options rather than treating them as shared
first-line anxiety medicines.
"""
from __future__ import annotations

from app.engine.base import DiagnosisRuleModule
from app.engine.context import PatientContext
from app.engine.core_rules import trial_adequacy
from app.engine.references import cite
from app.engine.utils import normalise


def drug_name(drug: dict) -> str:
    return normalise(drug.get("name", ""))


def trial_matches(trial_name: str, names: set[str]) -> bool:
    observed = normalise(trial_name)
    return any(observed == name or observed in name or name in observed for name in names)


def adequate_trials(
    ctx: PatientContext,
    names: set[str],
    *,
    responses: set[str] | None = None,
) -> list:
    matched = []
    for trial in ctx.profile.previous_drug_responses:
        if not trial_matches(trial.drug, names):
            continue
        if responses is not None and normalise(trial.response) not in responses:
            continue
        if trial_adequacy(ctx, trial) == "adequate":
            matched.append(trial)
    return matched


def unique_candidates(candidates: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for drug in candidates:
        name = drug_name(drug)
        if name not in seen:
            unique.append(drug)
            seen.add(name)
    return unique


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
