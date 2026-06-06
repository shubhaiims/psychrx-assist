"""Treatment sequence for generalized social anxiety disorder."""
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


FIRST_SSRI_NAMES = {"sertraline", "escitalopram"}
ALTERNATIVE_NAMES = {"fluvoxamine", "paroxetine", "venlafaxine_xr"}
MAOI_NAMES = {"phenelzine"}
EXPERIMENTAL_NAMES = {"pregabalin", "gabapentin", "mirtazapine", "clonazepam"}
SAD_TRIAL_NAMES = FIRST_SSRI_NAMES | ALTERNATIVE_NAMES | MAOI_NAMES | EXPERIMENTAL_NAMES


class SocialAnxietyDisorderModule(AnxietySpectrumModule):
    def candidate_drugs(self, ctx: PatientContext, all_drugs: list[dict]) -> list[dict]:
        candidates = super().candidate_drugs(ctx, all_drugs)
        if not ctx.extended_rules:
            return candidates

        partials = adequate_trials(ctx, SAD_TRIAL_NAMES, responses={"partial"})
        if partials:
            candidates += [
                drug for drug in all_drugs if drug_name(drug) == "buspirone"
            ]
        return unique_candidates(candidates)

    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        super().diagnosis_specific_rules(ctx, drug, card)
        if not ctx.extended_rules:
            return

        name = drug_name(drug)
        failures = adequate_trials(
            ctx, SAD_TRIAL_NAMES, responses={"none", "intolerable"}
        )
        partials = adequate_trials(ctx, SAD_TRIAL_NAMES, responses={"partial"})
        failed_count = len(failures)

        if failed_count == 0 and name in FIRST_SSRI_NAMES:
            card.add_reason(
                "SAD-FIRST-SSRI",
                "Sertraline or escitalopram is the preferred medication when an adult with social anxiety chooses pharmacotherapy.",
                delta=14,
                references=cite("SAD-FIRST-SSRI"),
            )

        if failed_count >= 1 and name in ALTERNATIVE_NAMES:
            if ctx.previous_response_for(drug.get("name", "")) is None:
                card.add_reason(
                    "SAD-SECOND-MEDICATION",
                    "After an adequate sertraline/escitalopram nonresponse or intolerance, try fluvoxamine, paroxetine, or venlafaxine.",
                    delta=10,
                    references=cite("SAD-SECOND-MEDICATION"),
                )

        if failed_count >= 2 and name in MAOI_NAMES:
            card.add_reason(
                "SAD-MAOI-LATER",
                "Phenelzine is a later specialist option after adequate SSRI/SNRI trials have failed.",
                delta=8,
                references=cite("SAD-MAOI-LATER"),
            )
            card.add_caution(
                "SAD-MAOI-SAFETY",
                "MAOI treatment requires specialist supervision, interaction washouts, dietary counselling, and hypertensive-crisis/serotonin-toxicity precautions.",
                delta=-8,
                references=cite("SAD-MAOI-SAFETY"),
            )

        if name in {"paroxetine", "venlafaxine_xr"}:
            card.add_caution(
                "SAD-WITHDRAWAL-BURDEN",
                "This option has a greater tendency to produce discontinuation symptoms; discuss adherence and tapering before treatment.",
                delta=-4,
                references=cite("SAD-WITHDRAWAL-BURDEN"),
            )

        if name == "fluvoxamine":
            card.add_caution(
                "SAD-FLUVOXAMINE-INTERACTIONS",
                "Fluvoxamine can cause clinically important CYP-mediated interactions; complete a full medication review.",
                delta=-3,
                references=cite("SAD-FLUVOXAMINE-INTERACTIONS"),
            )

        if partials and name == "buspirone":
            card.add_reason(
                "SAD-BUSPIRONE-AUGMENT",
                "The book describes buspirone augmentation after a medication-attributable partial SSRI response.",
                delta=2,
                references=cite("SAD-BUSPIRONE-AUGMENT"),
            )
            card.add_caution(
                "SAD-BUSPIRONE-WEAK",
                "Evidence is limited; current guidance prefers adding individual CBT after a partial SSRI response.",
                delta=-5,
                references=cite("SAD-BUSPIRONE-WEAK"),
            )

        if name in EXPERIMENTAL_NAMES:
            card.add_caution(
                "SAD-NONROUTINE",
                "This is a historical or experimental book option and is not routinely recommended for social anxiety; prefer disorder-specific CBT and established SSRI/SNRI steps.",
                delta=-22,
                references=cite("SAD-NONROUTINE"),
            )

        if name == "clonazepam" and ctx.profile.substance_use:
            card.mark_unsuitable(
                "SAD-BENZO-SUBSTANCE",
                "Substance use is recorded; clonazepam misuse, dependence, cognitive, and coordination risks make it unsuitable without specialist justification.",
                delta=-20,
                references=cite("SAD-BENZO-SUBSTANCE"),
            )

    def extra_missing_info(self, ctx: PatientContext) -> list[str]:
        if not ctx.extended_rules:
            return []
        missing = [
            "Confirm persistent fear of scrutiny/negative evaluation, avoidance, functional impairment, and whether anxiety is limited to performance situations."
        ]
        if adequate_trials(ctx, SAD_TRIAL_NAMES, responses={"none", "partial"}):
            missing.append(
                "Before advancing treatment, document a 10 to 12 week adequate medication trial, adherence, adverse effects, and access to disorder-specific individual CBT."
            )
        return missing

    def diagnosis_notes(self, ctx: PatientContext) -> list[str]:
        if not ctx.extended_rules:
            return []
        return [
            "Social anxiety sequence: individual disorder-specific CBT is preferred; if medication is chosen, start sertraline or escitalopram, then fluvoxamine/paroxetine/venlafaxine, then specialist MAOI review.",
            "For partial SSRI response after 10 to 12 weeks, add individual CBT rather than automatically stacking medication.",
            "Support graduated exposure to feared or avoided social situations and review early activation, suicidality, withdrawal risk, sexual effects, and adherence.",
        ]

    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        recs = super().non_pharmacological(ctx)
        recs += [
            "Offer individual CBT specifically developed for social anxiety, using the Clark and Wells or Heimberg model.",
            "Build a graded exposure plan for feared social situations and address safety behaviours and post-event rumination.",
        ]
        return recs


MODULE = register(
    SocialAnxietyDisorderModule(
        diagnosis="social_anxiety_disorder",
        display_name="Social anxiety disorder",
    )
)
