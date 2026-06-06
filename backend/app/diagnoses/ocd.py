"""Book-derived treatment sequence for obsessive-compulsive disorder."""
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


PREFERRED_SSRI_NAMES = {"sertraline", "fluoxetine", "fluvoxamine"}
OTHER_SSRI_NAMES = {"escitalopram", "paroxetine"}
OCD_FIRST_LINE_NAMES = PREFERRED_SSRI_NAMES | OTHER_SSRI_NAMES
OCD_TRIAL_NAMES = OCD_FIRST_LINE_NAMES | {"clomipramine"}
AUGMENTATION_NAMES = {"aripiprazole", "risperidone"}
EXPERIMENTAL_NAMES = {"memantine", "lamotrigine", "topiramate"}


class OCDModule(AnxietySpectrumModule):
    def candidate_drugs(self, ctx: PatientContext, all_drugs: list[dict]) -> list[dict]:
        candidates = super().candidate_drugs(ctx, all_drugs)
        if not ctx.extended_rules:
            return candidates

        failures = adequate_trials(
            ctx, OCD_TRIAL_NAMES, responses={"none", "intolerable"}
        )
        extra_names: set[str] = set()
        if len(failures) >= 2:
            extra_names |= AUGMENTATION_NAMES
        if len(failures) >= 3:
            extra_names |= EXPERIMENTAL_NAMES
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
            ctx, OCD_TRIAL_NAMES, responses={"none", "intolerable"}
        )
        partials = adequate_trials(ctx, OCD_TRIAL_NAMES, responses={"partial"})
        failed_count = len(failures)

        if failed_count == 0 and name in PREFERRED_SSRI_NAMES:
            card.add_reason(
                "OCD-PREFERRED-SSRI",
                "Sertraline, fluoxetine, or fluvoxamine is a preferred first medication option for OCD.",
                delta=14,
                references=cite("OCD-PREFERRED-SSRI"),
            )

        if failed_count >= 1 and name in OCD_FIRST_LINE_NAMES:
            if ctx.previous_response_for(drug.get("name", "")) is None:
                card.add_reason(
                    "OCD-SECOND-SSRI",
                    "After one adequate SSRI nonresponse or intolerance, an untried SSRI is an appropriate next step.",
                    delta=10,
                    references=cite("OCD-SECOND-SSRI"),
                )

        if name == "clomipramine":
            if failed_count >= 1:
                card.add_reason(
                    "OCD-CLOMIPRAMINE-LATER",
                    "Clomipramine is a later medication option after an adequate SSRI trial.",
                    delta=8,
                    references=cite("OCD-CLOMIPRAMINE-LATER"),
                )
            card.add_caution(
                "OCD-CLOMIPRAMINE-SAFETY",
                "Clomipramine has greater anticholinergic, cardiac, interaction, seizure, and overdose toxicity than SSRIs; review ECG/QTc and overdose risk.",
                delta=-8,
                references=cite("OCD-CLOMIPRAMINE-SAFETY"),
            )

        if name == "paroxetine":
            card.add_caution(
                "OCD-PAROXETINE-BURDEN",
                "Paroxetine is effective but has greater withdrawal, interaction, weight, sedation, sexual, and pregnancy-related concerns than preferred SSRIs.",
                delta=-5,
                references=cite("OCD-PAROXETINE-BURDEN"),
            )

        if name == "escitalopram":
            card.add_caution(
                "OCD-ESCITALOPRAM-QT",
                "OCD may require higher antidepressant exposure, but escitalopram has dose-related QT concerns; do not exceed locally approved limits and review ECG risk.",
                delta=-2,
                references=cite("OCD-ESCITALOPRAM-QT"),
            )

        if failures or partials:
            card.add_investigation(
                "Before declaring OCD medication failure: verify adherence, dose, at least 12 weeks of treatment, drug interactions, tolerability, and ERP participation."
            )
            card.add_monitoring(
                "Use a structured OCD severity measure such as Y-BOCS to document target symptoms and response."
            )

        if failed_count >= 2 and name in AUGMENTATION_NAMES:
            card.add_reason(
                "OCD-ANTIPSYCHOTIC-AUGMENT",
                "After at least two adequate SRI trials, low-dose aripiprazole or risperidone augmentation can be considered for persistent OCD.",
                delta=7,
                references=cite("OCD-ANTIPSYCHOTIC-AUGMENT"),
            )
            card.add_caution(
                "OCD-ANTIPSYCHOTIC-TRIAL",
                "Use only as augmentation with a defined target and time-limited specialist trial; monitor metabolic effects, EPS/akathisia, and prolactin as appropriate.",
                delta=-5,
                references=cite("OCD-ANTIPSYCHOTIC-TRIAL"),
            )

        if failed_count >= 3 and name in EXPERIMENTAL_NAMES:
            card.add_reason(
                "OCD-EXPERIMENTAL-LATER",
                "The book discusses this only after multiple adequate medication failures.",
                delta=2,
                references=cite("OCD-EXPERIMENTAL-LATER"),
            )
            card.add_caution(
                "OCD-EXPERIMENTAL-WEAK",
                "Evidence is limited and this is not routine OCD treatment; use only after specialist review and optimized ERP/SRI treatment.",
                delta=-18,
                references=cite("OCD-EXPERIMENTAL-WEAK"),
            )

    def extra_missing_info(self, ctx: PatientContext) -> list[str]:
        if not ctx.extended_rules:
            return []
        missing = [
            "OCD severity and impairment using a structured measure such as Y-BOCS, including time occupied, distress, avoidance, insight, and functional effects.",
            "Screen for bipolar disorder, psychosis, tic disorder, substance effects, and medical/neurological mimics before escalating antidepressant treatment.",
            "Access to therapist-delivered exposure and response prevention (ERP).",
        ]
        if adequate_trials(ctx, OCD_TRIAL_NAMES, responses={"none", "partial"}):
            missing.append(
                "Confirm adherence and adequate SRI exposure before declaring failure; plasma concentration can help when adherence, absorption, metabolism, or interactions are uncertain."
            )
        return missing

    def diagnosis_notes(self, ctx: PatientContext) -> list[str]:
        if not ctx.extended_rules:
            return []
        return [
            "OCD medication sequence: combine ERP with an SSRI, assess over a full 12-week trial, switch to another SSRI or clomipramine after nonresponse, and consider low-dose aripiprazole/risperidone augmentation only after multiple adequate trials.",
            "Do not judge an SSRI ineffective too early: allow several weeks at a tolerated therapeutic dose, and document dose, duration, adherence, and Y-BOCS change before advancing.",
            "For severe treatment-refractory OCD, specialist services may consider evidence-based rTMS targets or, rarely, neurosurgical/deep-brain-stimulation pathways after exhaustive multidisciplinary review.",
        ]

    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        recs = super().non_pharmacological(ctx)
        recs += [
            "Offer therapist-delivered exposure and response prevention (ERP), with family involvement when accommodation maintains compulsions.",
            "Identify avoidance, reassurance seeking, family accommodation, and covert rituals and include them in the exposure hierarchy.",
        ]
        return recs


MODULE = register(
    OCDModule(
        diagnosis="ocd",
        display_name="Obsessive-compulsive disorder",
    )
)
