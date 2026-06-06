"""Book-derived PTSD nodes reconciled with current VA/DoD safety guidance."""
from __future__ import annotations

from app.diagnoses._anxiety_common import (
    AnxietySpectrumModule,
    adequate_trials,
    drug_name,
)
from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.registry import register


PTSD_FIRST_LINE = {"sertraline", "paroxetine", "venlafaxine_xr"}
PTSD_BOOK_ALTERNATIVES = {"mirtazapine", "trazodone", "prazosin"}
PTSD_TRIAL_NAMES = PTSD_FIRST_LINE | PTSD_BOOK_ALTERNATIVES


class PTSDModule(AnxietySpectrumModule):
    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        super().diagnosis_specific_rules(ctx, drug, card)
        if not ctx.extended_rules:
            return

        name = drug_name(drug)
        failures = adequate_trials(
            ctx, PTSD_TRIAL_NAMES, responses={"none", "intolerable"}
        )

        if name in PTSD_FIRST_LINE:
            card.add_reason(
                "PTSD-MED-FIRSTLINE",
                "When medication is chosen for global PTSD symptoms, sertraline, paroxetine, or venlafaxine has the strongest current support.",
                delta=12,
                references=cite("PTSD-MED-FIRSTLINE"),
            )
            if failures and ctx.previous_response_for(drug.get("name", "")) is None:
                card.add_reason(
                    "PTSD-NEXT-TRIAL",
                    "After an adequate nonresponse, try an untried supported SSRI/SNRI before experimental augmentation.",
                    delta=7,
                    references=cite("PTSD-NEXT-TRIAL"),
                )

        if name == "paroxetine":
            card.add_caution(
                "PTSD-PAROXETINE-BURDEN",
                "Paroxetine has substantial withdrawal, interaction, weight, sedation, sexual, and pregnancy-related concerns despite efficacy.",
                delta=-5,
                references=cite("PTSD-PAROXETINE-BURDEN"),
            )

        if name == "prazosin":
            if ctx.profile.symptoms.nightmares:
                card.add_reason(
                    "PTSD-PRAZOSIN-NIGHTMARES",
                    "Prazosin may be considered specifically for PTSD-associated nightmares after blood-pressure and orthostasis review.",
                    delta=12,
                    references=cite("PTSD-PRAZOSIN-NIGHTMARES"),
                )
                card.add_monitoring(
                    "Monitor seated/standing blood pressure, dizziness, syncope, falls, and nightmare response during cautious titration."
                )
            else:
                card.add_caution(
                    "PTSD-PRAZOSIN-NOT-GLOBAL",
                    "Prazosin should not be promoted for global PTSD symptoms when trauma-related nightmares are not the treatment target.",
                    delta=-40,
                    references=cite("PTSD-PRAZOSIN-NOT-GLOBAL"),
                )

        if name == "trazodone":
            if ctx.profile.symptoms.insomnia:
                card.add_reason(
                    "PTSD-TRAZODONE-SLEEP",
                    "The book considers trazodone for persistent sleep-onset insomnia after other causes are assessed.",
                    delta=4,
                    references=cite("PTSD-TRAZODONE-SLEEP"),
                )
            card.add_caution(
                "PTSD-TRAZODONE-LIMITED",
                "Trazodone evidence in PTSD sleep disturbance is limited; monitor sedation, orthostasis, syncope, and priapism risk.",
                delta=-5,
                references=cite("PTSD-TRAZODONE-LIMITED"),
            )

        if name == "mirtazapine":
            card.add_caution(
                "PTSD-MIRTAZAPINE-UNCERTAIN",
                "The book lists mirtazapine as an alternative, but current PTSD guidance finds evidence insufficient; weigh sedation and weight gain carefully.",
                delta=-8,
                references=cite("PTSD-MIRTAZAPINE-UNCERTAIN"),
            )

        if failures and len(failures) >= 2:
            card.add_monitoring(
                "Before calling PTSD medication resistant, verify trauma-focused psychotherapy access, diagnosis, adherence, dose, duration, sleep disorders, substance use, and comorbid depression/bipolar disorder."
            )

    def extra_missing_info(self, ctx: PatientContext) -> list[str]:
        if not ctx.extended_rules:
            return []
        missing = [
            "PTSD assessment: trauma exposure, intrusion, avoidance, negative mood/cognition, arousal/reactivity, duration, impairment, dissociation, substance use, and suicide risk."
        ]
        if ctx.profile.symptoms.insomnia or ctx.profile.symptoms.nightmares:
            missing.append(
                "Sleep assessment: sleep apnoea, restless legs/limb movements, pain, nocturia, caffeine/nicotine, withdrawal, sleep schedule, and medication-induced insomnia."
            )
        if ctx.profile.symptoms.psychotic:
            missing.append(
                "Psychosis differential: distinguish flashbacks/dissociation and PTSD-related phenomena from primary psychosis, mood disorder, substance effects, delirium, or another medical cause."
            )
        return missing

    def extra_red_flags(self, ctx: PatientContext) -> list[str]:
        if not ctx.extended_rules:
            return []
        if ctx.profile.symptoms.psychotic and (
            ctx.severity == "emergency"
            or ctx.profile.suicide_risk
            or ctx.profile.symptoms.aggression_risk
        ):
            return [
                "PTSD with psychosis plus acute safety risk requires urgent specialist assessment; do not rely on the routine outpatient PTSD pathway."
            ]
        return []

    def diagnosis_notes(self, ctx: PatientContext) -> list[str]:
        if not ctx.extended_rules:
            return []
        notes = [
            "Current safety update: trauma-focused psychotherapy is preferred over medication for PTSD; use medication when therapy is unavailable, infeasible, declined, or when a supported comorbidity also requires it.",
            "Book sleep node retained with safeguards: assess sleep at every step; use CBT-I first for chronic insomnia, and consider prazosin only for a defined nightmare target, not global PTSD symptoms.",
            "Do not use benzodiazepines for PTSD treatment. Avoid routine antipsychotic augmentation; current evidence recommends against risperidone for PTSD and does not support medication stacking.",
        ]
        if len(adequate_trials(ctx, PTSD_TRIAL_NAMES, responses={"none", "intolerable"})) >= 2:
            notes.append(
                "After two supported medication failures, obtain specialist review rather than automatically progressing through the book's older experimental anticonvulsant and antipsychotic options."
            )
        return notes

    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        recs = super().non_pharmacological(ctx)
        recs += [
            "Offer individual trauma-focused psychotherapy, especially prolonged exposure, cognitive processing therapy, or EMDR.",
            "For chronic insomnia, offer CBT-I; consider nightmare-focused psychological work when appropriate.",
            "Address substance use, smoking, anger/impulsivity, pain, and social safety without delaying evidence-based PTSD treatment.",
        ]
        return recs


MODULE = register(
    PTSDModule(
        diagnosis="ptsd",
        display_name="Post-traumatic stress disorder",
    )
)
