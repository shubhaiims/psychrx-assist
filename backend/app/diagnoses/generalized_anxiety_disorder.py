"""Book-derived, safety-updated treatment sequence for generalized anxiety disorder."""
from __future__ import annotations

from app.diagnoses._anxiety_common import (
    AnxietySpectrumModule,
    adequate_trials,
    drug_name,
    unique_candidates,
)
from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.registry import register
from app.engine.utils import normalise


SSRI_NAMES = {"sertraline", "escitalopram", "paroxetine"}
SNRI_NAMES = {"duloxetine", "venlafaxine_xr"}
EARLY_ALTERNATIVES = {"buspirone", "hydroxyzine", "pregabalin", "bupropion"}
GAD_TRIAL_NAMES = SSRI_NAMES | SNRI_NAMES | EARLY_ALTERNATIVES | {"clonazepam"}
LATE_SGA_NAMES = {"quetiapine", "risperidone", "aripiprazole"}


class GeneralizedAnxietyDisorderModule(AnxietySpectrumModule):
    def candidate_drugs(self, ctx: PatientContext, all_drugs: list[dict]) -> list[dict]:
        candidates = super().candidate_drugs(ctx, all_drugs)
        if not ctx.extended_rules:
            return candidates

        failures = adequate_trials(
            ctx, GAD_TRIAL_NAMES, responses={"none", "intolerable"}
        )
        extra_names = {"bupropion"}
        if len(failures) >= 3:
            extra_names |= LATE_SGA_NAMES
        candidates += [
            drug for drug in all_drugs if drug_name(drug) in extra_names
        ]
        return unique_candidates(candidates)

    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        super().diagnosis_specific_rules(ctx, drug, card)
        if not ctx.extended_rules:
            return

        name = drug_name(drug)
        failures = adequate_trials(
            ctx, GAD_TRIAL_NAMES, responses={"none", "intolerable"}
        )
        partials = adequate_trials(ctx, GAD_TRIAL_NAMES, responses={"partial"})
        failed_count = len(failures)

        if failed_count == 0:
            if name == "sertraline":
                card.add_reason(
                    "GAD-FIRST-SERTRALINE",
                    "Sertraline is the preferred first SSRI in the safety-updated GAD sequence.",
                    delta=14,
                    references=cite("GAD-FIRST-SERTRALINE"),
                )
            elif name in {"escitalopram", "duloxetine"}:
                card.add_reason(
                    "GAD-FIRST-ALTERNATIVE",
                    "Escitalopram or duloxetine is an evidence-supported early medication option when its adverse-effect profile fits the patient.",
                    delta=8,
                    references=cite("GAD-FIRST-ALTERNATIVE"),
                )
            elif name in EARLY_ALTERNATIVES:
                card.add_reason(
                    "GAD-EARLY-ALTERNATIVE",
                    "The book algorithm lists this as an early alternative when an SSRI is unsuitable or unacceptable.",
                    delta=2,
                    references=cite("GAD-EARLY-ALTERNATIVE"),
                )

        if failed_count >= 1 and name in SSRI_NAMES | {"duloxetine"}:
            if ctx.previous_response_for(drug.get("name", "")) is None:
                card.add_reason(
                    "GAD-SECOND-TRIAL",
                    "After one adequate nonresponse, try a different SSRI or duloxetine before moving to higher-risk strategies.",
                    delta=10,
                    references=cite("GAD-SECOND-TRIAL"),
                )

        if failed_count >= 2 and name in SNRI_NAMES:
            if ctx.previous_response_for(drug.get("name", "")) is None:
                card.add_reason(
                    "GAD-SNRI-STEP",
                    "After two adequate early trials, an untried SNRI is the next medication step in the book sequence.",
                    delta=10,
                    references=cite("GAD-SNRI-STEP"),
                )

        if failed_count >= 2 and name == "pregabalin":
            card.add_reason(
                "GAD-PREGABALIN-LATER",
                "Pregabalin is a later alternative when SSRI/SNRI treatment is ineffective or not tolerated.",
                delta=6,
                references=cite("GAD-PREGABALIN-LATER"),
            )

        if partials and name in {"pregabalin", "hydroxyzine", "buspirone"}:
            card.add_reason(
                "GAD-PARTIAL-AUGMENT",
                "A genuine partial response can justify a carefully monitored augmentation discussion.",
                delta=3,
                references=cite("GAD-PARTIAL-AUGMENT"),
            )
            card.add_caution(
                "GAD-PARTIAL-AUGMENT-WEAK",
                "Medication augmentation evidence is limited; confirm adherence, adequate exposure, comorbidity, and a medication-attributable partial response first.",
                delta=0,
                references=cite("GAD-PARTIAL-AUGMENT-WEAK"),
            )

        if name == "paroxetine":
            card.add_caution(
                "GAD-PAROXETINE-BURDEN",
                "Paroxetine is effective but has greater withdrawal, interaction, weight, sedation, sexual, and pregnancy-related concerns than several alternatives.",
                delta=-5,
                references=cite("GAD-PAROXETINE-BURDEN"),
            )

        if name == "venlafaxine_xr":
            card.add_caution(
                "GAD-VENLAFAXINE-BURDEN",
                "Venlafaxine is effective but usually follows better-tolerated options because of withdrawal, blood-pressure, and overdose-toxicity concerns.",
                delta=-4,
                references=cite("GAD-VENLAFAXINE-BURDEN"),
            )

        if name == "bupropion":
            card.add_caution(
                "GAD-BUPROPION-LIMITED",
                "Bupropion was an early alternative in the book based on limited evidence; it is not a routine guideline-preferred GAD treatment.",
                delta=-8,
                references=cite("GAD-BUPROPION-LIMITED"),
            )

        if name == "clonazepam":
            card.add_caution(
                "GAD-BENZO-CRISIS-ONLY",
                "Do not use a benzodiazepine as routine GAD maintenance treatment; reserve only for a short, clearly defined crisis plan because of dependence, cognitive, sedation, and withdrawal risks.",
                delta=-35,
                references=cite("GAD-BENZO-CRISIS-ONLY"),
            )
            if ctx.profile.substance_use:
                card.mark_unsuitable(
                    "GAD-BENZO-SUBSTANCE",
                    "Substance use is recorded; benzodiazepine misuse and dependence risk make clonazepam unsuitable without specialist justification.",
                    delta=-20,
                    references=cite("GAD-BENZO-SUBSTANCE"),
                )

        if name in LATE_SGA_NAMES:
            card.add_reason(
                "GAD-SGA-REFRACTORY",
                "The book considers selected antipsychotics only after multiple adequate treatment failures.",
                delta=2,
                references=cite("GAD-SGA-REFRACTORY"),
            )
            card.add_caution(
                "GAD-SGA-SPECIALIST",
                "Antipsychotics are not routine GAD treatment; use only after specialist review of metabolic, neurologic, cardiac, and long-term risks.",
                delta=-18,
                references=cite("GAD-SGA-SPECIALIST"),
            )

    def extra_missing_info(self, ctx: PatientContext) -> list[str]:
        if not ctx.extended_rules:
            return []
        missing = [
            "Confirm worry is broad, persistent, difficult to control, impairing, and not better explained by another anxiety disorder, substance, medication, or medical condition."
        ]
        if adequate_trials(ctx, GAD_TRIAL_NAMES, responses={"none", "partial"}):
            missing.append(
                "Before advancing the GAD sequence, document adherence, adequate dose, at least 8 weeks of treatment, tolerability, and concurrent psychological treatment."
            )
        return missing

    def diagnosis_notes(self, ctx: PatientContext) -> list[str]:
        if not ctx.extended_rules:
            return []
        notes = [
            "GAD sequence: education/active monitoring and CBT or applied relaxation; if medication is chosen, start with sertraline, then another SSRI or SNRI, and use pregabalin when SSRI/SNRI treatment is not tolerated.",
            "Review benefit and adverse effects every 2 to 4 weeks early in treatment; if effective, continuation for at least 12 months reduces relapse risk.",
            "Complex treatment-refractory GAD, self-neglect, marked impairment, substance misuse, or self-harm risk requires specialist step-4 care rather than indefinite medication stacking.",
        ]
        if any(normalise(x) in {"alcohol", "opioids", "benzodiazepines"} for x in ctx.profile.substance_use):
            notes.append(
                "Substance use can mimic or worsen anxiety and changes the risk-benefit balance of sedatives; treat both conditions explicitly."
            )
        return notes

    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        recs = super().non_pharmacological(ctx)
        recs += [
            "Offer stepped-care psychological treatment: guided self-help/psychoeducation, then high-intensity CBT or applied relaxation when impairment persists.",
            "Review caffeine, alcohol, other substances, sleep, and medical contributors to autonomic anxiety symptoms.",
        ]
        return recs


MODULE = register(
    GeneralizedAnxietyDisorderModule(
        diagnosis="generalized_anxiety_disorder",
        display_name="Generalized anxiety disorder",
    )
)
