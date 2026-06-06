"""Schizophrenia-specific branches layered on the shared psychosis sequence."""
from app.diagnoses._psychosis_common import (
    PsychosisModule,
    has_primary_negative_symptoms,
    previous_clozapine_trial,
)
from app.engine.context import PatientContext
from app.engine.core_rules import trial_adequacy
from app.engine.references import cite
from app.engine.registry import register
from app.engine.utils import normalise


class SchizophreniaModule(PsychosisModule):
    def candidate_drugs(self, ctx: PatientContext, all_drugs: list[dict]) -> list[dict]:
        candidates = super().candidate_drugs(ctx, all_drugs)
        if not ctx.extended_rules:
            return candidates

        extra_names: set[str] = set()
        if has_primary_negative_symptoms(ctx):
            extra_names.add("mirtazapine")

        clozapine_trial = previous_clozapine_trial(ctx)
        if (
            clozapine_trial is not None
            and trial_adequacy(ctx, clozapine_trial) == "adequate"
            and normalise(clozapine_trial.response) in {"partial", "none"}
        ):
            extra_names.add("lamotrigine")

        candidates += [
            drug
            for drug in all_drugs
            if normalise(drug.get("name", "")) in extra_names
        ]

        seen: set[str] = set()
        unique: list[dict] = []
        for drug in candidates:
            name = normalise(drug.get("name", ""))
            if name not in seen:
                unique.append(drug)
                seen.add(name)
        return unique

    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        super().diagnosis_specific_rules(ctx, drug, card)
        if not ctx.extended_rules:
            return

        name = normalise(drug.get("name", ""))
        if has_primary_negative_symptoms(ctx):
            if name == "cariprazine":
                card.add_reason(
                    "PSY-NEGATIVE-CARIPRAZINE",
                    "After secondary causes are addressed, cariprazine can be considered for persistent predominant negative symptoms.",
                    delta=10,
                    references=cite("PSY-NEGATIVE-CARIPRAZINE"),
                )
            elif name == "mirtazapine":
                card.add_reason(
                    "PSY-NEGATIVE-MIRTAZAPINE",
                    "Mirtazapine may be considered as antidepressant augmentation for persistent negative symptoms after depression, EPS, sedation, and active positive symptoms are reviewed.",
                    delta=4,
                    references=cite("PSY-NEGATIVE-MIRTAZAPINE"),
                )
                card.add_caution(
                    "PSY-NEGATIVE-MIRTAZAPINE-ADJUNCT",
                    "Mirtazapine is an adjunct for a selected negative-symptom pathway, not antipsychotic monotherapy for schizophrenia.",
                    delta=0,
                    references=cite("PSY-NEGATIVE-MIRTAZAPINE-ADJUNCT"),
                )

        clozapine_trial = previous_clozapine_trial(ctx)
        clozapine_inadequate = (
            clozapine_trial is not None
            and trial_adequacy(ctx, clozapine_trial) == "adequate"
            and normalise(clozapine_trial.response) in {"partial", "none"}
        )
        if clozapine_inadequate and name in {"risperidone", "lamotrigine"}:
            card.add_reason(
                "PSY-CLOZAPINE-AUGMENT",
                "After clozapine optimization, risperidone or lamotrigine augmentation may be considered in selected partial/nonresponders.",
                delta=4,
                references=cite("PSY-CLOZAPINE-AUGMENT"),
            )
            card.add_caution(
                "PSY-CLOZAPINE-AUGMENT-WEAK",
                "Evidence for clozapine pharmacological augmentation is weak or modest; use specialist review, a defined target, and a time-limited monitored trial.",
                delta=0,
                references=cite("PSY-CLOZAPINE-AUGMENT-WEAK"),
            )

        if name == "ziprasidone":
            card.add_monitoring(
                "Confirm every oral ziprasidone dose is taken with an adequate meal before calling the trial ineffective."
            )
        if name == "lurasidone":
            card.add_monitoring(
                "Confirm lurasidone is taken with the required meal and review CYP3A4 interactions before calling the trial ineffective."
            )

    def diagnosis_notes(self, ctx: PatientContext) -> list[str]:
        notes = super().diagnosis_notes(ctx)
        if not ctx.extended_rules:
            return notes
        if has_primary_negative_symptoms(ctx):
            notes.append(
                "Negative-symptom pathway: first correct secondary causes such as depression, persistent positive symptoms, EPS/parkinsonism, sedation, and medication burden; primary negative symptoms respond only modestly to medicines."
            )
        clozapine_trial = previous_clozapine_trial(ctx)
        if (
            clozapine_trial is not None
            and trial_adequacy(ctx, clozapine_trial) == "adequate"
            and normalise(clozapine_trial.response) in {"partial", "none"}
        ):
            notes.append(
                "After optimized clozapine remains inadequate, ECT augmentation or a carefully monitored risperidone/lamotrigine augmentation trial may be considered, but evidence is limited."
            )
        return notes

    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        recs = super().non_pharmacological(ctx)
        recs.append(
            "Cognitive remediation/rehabilitation and social-skills support for cognitive and functional impairment."
        )
        return recs


MODULE = register(
    SchizophreniaModule(
        diagnosis="schizophrenia",
        display_name="Schizophrenia",
    )
)
