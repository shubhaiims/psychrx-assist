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
from app.engine.core_rules import trial_adequacy
from app.engine.references import cite
from app.engine.registry import register
from app.engine.utils import has_any, normalise


ANTIDEPRESSANT_NAMES = {
    "sertraline",
    "escitalopram",
    "fluoxetine",
    "bupropion",
    "venlafaxine",
    "venlafaxine_xr",
    "duloxetine",
    "mirtazapine",
}

PSYCHOTIC_DEPRESSION_ANTIPSYCHOTICS = {
    "olanzapine",
    "quetiapine",
    "aripiprazole",
    "ziprasidone",
}

MELANCHOLIC_OR_INPATIENT_KEYWORDS = [
    "melancholic",
    "inpatient",
    "hospital",
    "refusal_of_food",
    "poor_intake",
    "psychomotor",
    "catatonia",
]

TRD_KEYWORDS = ["treatment_resistant", "trd", "refractory"]


def _drug_name(drug: dict) -> str:
    return normalise(drug.get("name", ""))


def _case_has(ctx: PatientContext, keywords: list[str]) -> bool:
    items = [ctx.profile.diagnosis_subtype or ""] + list(ctx.profile.comorbidities)
    return has_any(items, keywords)


def _is_psychotic_depression(ctx: PatientContext) -> bool:
    return ctx.severity == "severe_with_psychotic_features" or ctx.profile.symptoms.psychotic


def _matches_name(recorded: str, options: set[str]) -> bool:
    observed = normalise(recorded)
    return any(observed == option or option in observed or observed in option for option in options)


def _adequate_failed_antidepressant_trials(ctx: PatientContext) -> int:
    failed = 0
    for trial in ctx.profile.previous_drug_responses:
        if not _matches_name(trial.drug, ANTIDEPRESSANT_NAMES):
            continue
        if normalise(trial.response) not in {"none", "intolerable"}:
            continue
        if trial_adequacy(ctx, trial) == "adequate":
            failed += 1
    return failed


class MajorDepressiveDisorderModule(DiagnosisRuleModule):
    def candidate_drugs(self, ctx: PatientContext, all_drugs: list[dict]) -> list[dict]:
        candidates = super().candidate_drugs(ctx, all_drugs)
        if not ctx.extended_rules:
            return candidates
        needs_augmentation = (
            _case_has(ctx, TRD_KEYWORDS)
            or _adequate_failed_antidepressant_trials(ctx) >= 2
        )
        if needs_augmentation:
            candidates += [d for d in all_drugs if _drug_name(d) == "lithium"]

        seen: set[str] = set()
        unique: list[dict] = []
        for drug in candidates:
            name = _drug_name(drug)
            if name not in seen:
                unique.append(drug)
                seen.add(name)
        return unique

    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        if not ctx.extended_rules:
            return
        class_name = drug.get("class_name", "")
        name = _drug_name(drug)
        psychotic_depression = _is_psychotic_depression(ctx)
        adequate_failed_ads = _adequate_failed_antidepressant_trials(ctx)
        trd = _case_has(ctx, TRD_KEYWORDS) or adequate_failed_ads >= 2
        melancholic_or_inpatient = _case_has(ctx, MELANCHOLIC_OR_INPATIENT_KEYWORDS)

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

        if name == "bupropion":
            card.add_reason(
                "MDD-BUPROPION-FIRSTLINE",
                "Bupropion is a routine first-line antidepressant option for nonpsychotic unipolar depression.",
                delta=10,
                references=cite("MDD-BUPROPION-FIRSTLINE"),
            )
            if ctx.has_preference("avoid_sexual_side_effects") or ctx.has_preference("avoid_weight_gain"):
                card.add_reason(
                    "MDD-BUPROPION-PREFERENCE",
                    "Bupropion is often useful when avoiding sexual adverse effects or weight gain is a priority.",
                    delta=6,
                    references=cite("MDD-BUPROPION-PREFERENCE"),
                )

        if name == "venlafaxine_xr":
            if psychotic_depression:
                card.add_reason(
                    "MDD-PSYCHOTIC-VENLAFAXINE",
                    "Psychotic depression pharmacotherapy favors an antidepressant plus an antipsychotic; venlafaxine XR is the preferred antidepressant component in the loaded algorithm.",
                    delta=12,
                    references=cite("MDD-PSYCHOTIC-VENLAFAXINE"),
                )
            elif melancholic_or_inpatient or trd:
                card.add_reason(
                    "MDD-SEVERE-MELANCHOLIC-STEPUP",
                    "Severe melancholic, inpatient, or treatment-resistant depression can justify moving beyond routine SSRI-first sequencing.",
                    delta=6,
                    references=cite("MDD-SEVERE-MELANCHOLIC-STEPUP"),
                )

        if name == "mirtazapine" and (melancholic_or_inpatient or trd):
            card.add_reason(
                "MDD-SEVERE-MELANCHOLIC-STEPUP",
                "Mirtazapine is a step-up antidepressant option when severe depression, sleep/appetite burden, or treatment resistance is documented.",
                delta=6,
                references=cite("MDD-SEVERE-MELANCHOLIC-STEPUP"),
            )

        if name == "lithium" and trd:
            card.add_reason(
                "MDD-TRD-LITHIUM-AUGMENT",
                "Two adequate antidepressant nonresponses or treatment-resistant depression is recorded; lithium augmentation can be considered with level/renal/thyroid monitoring.",
                delta=8,
                references=cite("MDD-TRD-LITHIUM-AUGMENT"),
            )
            card.add_monitoring("Serum lithium level, renal function, TSH, calcium, and toxicity symptoms if lithium augmentation is used.")

        if class_name == "Second-generation antipsychotic":
            if ctx.severity == "severe_with_psychotic_features":
                card.add_reason(
                    "MDD-PSYCHOTIC-AUGMENT",
                    "Depression with psychotic features: an antipsychotic (with an "
                    "antidepressant) or ECT is appropriate rather than antidepressant monotherapy.",
                    delta=8,
                    references=cite("MDD-PSYCHOTIC-AUGMENT"),
                )
                if name in PSYCHOTIC_DEPRESSION_ANTIPSYCHOTICS:
                    card.add_reason(
                        "MDD-PSYCHOTIC-SGA-EVIDENCE",
                        "Psychotic depression medication treatment should pair an antidepressant with an antipsychotic; olanzapine and quetiapine have the strongest support, while aripiprazole/ziprasidone are lower-metabolic alternatives with weaker evidence.",
                        delta=8 if name in {"olanzapine", "quetiapine"} else 3,
                        references=cite("MDD-PSYCHOTIC-SGA-EVIDENCE"),
                    )
            else:
                card.add_caution(
                    "MDD-SGA-ADJUNCT",
                    "In unipolar depression, antipsychotics are augmentation/adjunct options "
                    "(or for psychotic features), not first-line monotherapy.",
                    delta=-12,
                    references=cite("MDD-SGA-ADJUNCT"),
                )

        if psychotic_depression and name in {"bupropion", "mirtazapine"}:
            card.add_caution(
                "MDD-PSYCHOTIC-AD-NOTFAVORED",
                "Psychotic depression should not be treated like routine nonpsychotic depression; bupropion or mirtazapine are not preferred antidepressant components for the initial combination strategy.",
                delta=-18,
                references=cite("MDD-PSYCHOTIC-AD-NOTFAVORED"),
            )

        if adequate_failed_ads >= 2:
            card.add_monitoring(
                "Before labelling treatment-resistant depression, confirm adherence, dose, duration, diagnosis, substance/medical contributors, and psychotherapy access."
            )

    def extra_missing_info(self, ctx: PatientContext) -> list[str]:
        if not ctx.extended_rules:
            return []
        missing: list[str] = []
        if _is_psychotic_depression(ctx):
            missing.append(
                "Psychotic depression differential review: bipolar disorder, schizoaffective disorder, primary psychosis, substance-induced and medical causes."
            )
        if _case_has(ctx, TRD_KEYWORDS) or _adequate_failed_antidepressant_trials(ctx) >= 2:
            missing.append(
                "Treatment-resistance review: document adequate dose, adequate duration, adherence, tolerability, comorbidities, and psychosocial drivers for each prior trial."
            )
        return missing

    def extra_red_flags(self, ctx: PatientContext) -> list[str]:
        if not ctx.extended_rules:
            return []
        if _is_psychotic_depression(ctx) and (
            ctx.severity == "emergency"
            or ctx.profile.suicide_risk
            or ctx.profile.symptoms.catatonia
            or _case_has(ctx, ["poor_intake", "refusal_of_food"])
        ):
            return [
                "Severe psychotic depression with high-risk features: urgent specialist/hospital review and ECT consideration are required."
            ]
        return []

    def diagnosis_notes(self, ctx: PatientContext):
        if not ctx.extended_rules:
            return []
        notes = [
            "For mild major depressive disorder, evidence-based psychotherapy may be offered "
            "before or alongside pharmacotherapy."
        ]
        if _is_psychotic_depression(ctx):
            notes.append(
                "Psychotic depression pathway: if ECT is not used, use an antidepressant plus an antipsychotic rather than antidepressant monotherapy, and continue an effective acute regimen for at least 4 months after response."
            )
        if _case_has(ctx, TRD_KEYWORDS) or _adequate_failed_antidepressant_trials(ctx) >= 2:
            notes.append(
                "Treatment-resistant depression pathway: after two adequate antidepressant failures, reassess diagnosis and contributors before switching, augmentation, rTMS/ECT, or later specialist options."
            )
        return notes


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
