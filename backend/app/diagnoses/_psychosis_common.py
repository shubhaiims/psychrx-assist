"""Shared logic for psychotic disorders (schizophrenia, acute psychosis).

Encodes widely-accepted antipsychotic prescribing principles:

* clozapine is reserved for treatment-resistant illness and requires mandatory
  blood-count (ANC) monitoring, so it is down-ranked as a default choice; and
* second-generation antipsychotics require metabolic monitoring.

Extended-rule-set logic (runs only when ``ctx.extended_rules`` is on); each
reason/caution carries a placeholder citation pending psychiatrist sign-off.
"""
from __future__ import annotations

from typing import List

from app.engine.base import DiagnosisRuleModule
from app.engine.context import PatientContext
from app.engine.core_rules import trial_adequacy
from app.engine.references import cite
from app.engine.utils import has_any, normalise


ANTIPSYCHOTIC_TRIAL_NAMES = {
    "amisulpride",
    "aripiprazole",
    "asenapine",
    "haloperidol",
    "lurasidone",
    "olanzapine",
    "paliperidone",
    "quetiapine",
    "risperidone",
    "ziprasidone",
}

FIRST_EPISODE_PREFERRED = {
    "amisulpride",
    "aripiprazole",
    "lurasidone",
    "risperidone",
    "ziprasidone",
}

SECOND_TRIAL_PREFERRED = {
    "haloperidol",
    "olanzapine",
    "risperidone",
}

CLOZAPINE_EFFICACY_GATE_TRIALS = {
    "haloperidol",
    "olanzapine",
    "perphenazine",
    "risperidone",
}

FGA_NAMES = {
    "chlorpromazine",
    "fluphenazine",
    "haloperidol",
    "loxapine",
    "perphenazine",
}


def _recorded_trial_name(recorded: str) -> str | None:
    observed = normalise(recorded)
    for name in ANTIPSYCHOTIC_TRIAL_NAMES | {"clozapine", "perphenazine"}:
        if observed == name or name in observed:
            return name
    return None


def adequate_failed_antipsychotic_names(ctx: PatientContext) -> set[str]:
    failed: set[str] = set()
    for trial in ctx.profile.previous_drug_responses:
        name = _recorded_trial_name(trial.drug)
        if name not in ANTIPSYCHOTIC_TRIAL_NAMES:
            continue
        if trial_adequacy(ctx, trial) != "adequate":
            continue
        if normalise(trial.response) in {"none", "intolerable"}:
            failed.add(name)
    return failed


def adequate_failed_antipsychotic_trials(ctx: PatientContext) -> int:
    return len(adequate_failed_antipsychotic_names(ctx))


def previous_clozapine_trial(ctx: PatientContext):
    for trial in ctx.profile.previous_drug_responses:
        if _recorded_trial_name(trial.drug) == "clozapine":
            return trial
    return None


def is_first_episode(ctx: PatientContext) -> bool:
    return has_any(
        [ctx.profile.diagnosis_subtype or ""],
        ["first_episode", "first episode", "new_onset", "new onset", "antipsychotic_naive"],
    )


def has_primary_negative_symptoms(ctx: PatientContext) -> bool:
    return ctx.profile.symptoms.negative or has_any(
        [ctx.profile.diagnosis_subtype or ""],
        ["predominant_negative", "primary_negative", "deficit_syndrome", "negative symptoms"],
    )


def _active_suicidality(ctx: PatientContext) -> bool:
    return ctx.profile.suicide_risk or ctx.suicidality in {
        "ideation",
        "ideation_with_plan",
        "recent_attempt",
    }


def _needs_trial_adequacy_review(ctx: PatientContext) -> bool:
    for trial in ctx.profile.previous_drug_responses:
        if _recorded_trial_name(trial.drug) not in ANTIPSYCHOTIC_TRIAL_NAMES:
            continue
        if normalise(trial.response) in {"none", "partial", "unknown"} and trial_adequacy(ctx, trial) != "adequate":
            return True
    return False


class PsychosisModule(DiagnosisRuleModule):
    """Common behaviour for psychotic-disorder modules."""

    def diagnosis_specific_rules(self, ctx: PatientContext, drug: dict, card) -> None:
        if not ctx.extended_rules:
            return
        name = normalise(drug.get("name", ""))
        failed_names = adequate_failed_antipsychotic_names(ctx)
        failed_trials = len(failed_names)

        if is_first_episode(ctx):
            if name in FIRST_EPISODE_PREFERRED:
                card.add_reason(
                    "PSY-FIRST-EPISODE-PREFERRED",
                    "First-episode schizophrenia: this is one of the preferred initial antipsychotics balancing efficacy with long-term tolerability.",
                    delta=12,
                    references=cite("PSY-FIRST-EPISODE-PREFERRED"),
                )
            elif name == "olanzapine":
                card.add_caution(
                    "PSY-FIRST-EPISODE-OLANZAPINE",
                    "Olanzapine is effective but is not preferred for a first antipsychotic trial because of substantial early weight and metabolic risk.",
                    delta=-20,
                    references=cite("PSY-FIRST-EPISODE-OLANZAPINE"),
                )
            elif name == "quetiapine":
                card.add_caution(
                    "PSY-FIRST-EPISODE-QUETIAPINE",
                    "Quetiapine is not preferred for the first schizophrenia trial because of metabolic burden and a weaker maintenance/relapse-prevention record.",
                    delta=-12,
                    references=cite("PSY-FIRST-EPISODE-QUETIAPINE"),
                )
            elif drug.get("class_name") == "First-generation antipsychotic" or name in FGA_NAMES:
                card.add_caution(
                    "PSY-FIRST-EPISODE-FGA",
                    "First-generation antipsychotics are not preferred in first-episode schizophrenia because of EPS and tardive-dyskinesia burden.",
                    delta=-15,
                    references=cite("PSY-FIRST-EPISODE-FGA"),
                )
            elif (
                drug.get("class_name") == "Second-generation antipsychotic"
                and name != "clozapine"
            ):
                card.add_caution(
                    "PSY-FIRST-EPISODE-OTHER-SGA",
                    "This SGA is not among the loaded algorithm's preferred first-episode options; use a preferred initial agent unless patient-specific factors justify otherwise.",
                    delta=-6,
                    references=cite("PSY-FIRST-EPISODE-OTHER-SGA"),
                )

        if failed_trials == 1 and name in SECOND_TRIAL_PREFERRED and name not in failed_names:
            card.add_reason(
                "PSY-SECOND-MONOTHERAPY",
                "After one adequate antipsychotic failure, use a second antipsychotic monotherapy; risperidone, olanzapine, or an FGA such as haloperidol are evidence-supported second-trial choices.",
                delta=9,
                references=cite("PSY-SECOND-MONOTHERAPY"),
            )

        if name == "clozapine":
            clozapine_trial = previous_clozapine_trial(ctx)
            early_clozapine = _active_suicidality(ctx) or ctx.profile.symptoms.aggression_risk
            optimized_clozapine_path = (
                clozapine_trial is not None
                and trial_adequacy(ctx, clozapine_trial) == "adequate"
                and normalise(clozapine_trial.response) in {"good", "partial", "none"}
            )

            if early_clozapine:
                card.add_reason(
                    "PSY-CLOZAPINE-EARLY-RISK",
                    "Active suicidality or persistent aggression is recorded; clozapine may be considered earlier than the usual treatment-resistance threshold with specialist monitoring.",
                    delta=30,
                    references=cite("PSY-CLOZAPINE-EARLY-RISK"),
                )
            elif optimized_clozapine_path:
                card.add_reason(
                    "PSY-CLOZAPINE-OPTIMIZE",
                    "A prior clozapine trial is recorded; optimize adherence, duration, tolerability, trough level, smoking status, and interacting medicines before switching away or augmenting.",
                    delta=15,
                    references=cite("PSY-CLOZAPINE-OPTIMIZE"),
                )
            elif failed_trials >= 2 and failed_names & CLOZAPINE_EFFICACY_GATE_TRIALS:
                card.add_reason(
                    "PSY-CLOZAPINE-TRS",
                    "Two adequate failed antipsychotic trials are recorded, including a risperidone, olanzapine, or FGA trial; clozapine should not be delayed for treatment-resistant schizophrenia.",
                    delta=35,
                    references=cite("PSY-CLOZAPINE-TRS"),
                )
            elif failed_trials >= 2:
                card.add_reason(
                    "PSY-CLOZAPINE-TRS-CONDITIONAL",
                    "Two adequate antipsychotic failures are recorded, so treatment resistance is likely.",
                    delta=12,
                    references=cite("PSY-CLOZAPINE-TRS-CONDITIONAL"),
                )
                card.add_caution(
                    "PSY-CLOZAPINE-EFFICACY-GATE",
                    "Before clozapine, the loaded algorithm asks that at least one adequate trial include risperidone, olanzapine, or an FGA unless suicidality/aggression justifies earlier clozapine.",
                    delta=-15,
                    references=cite("PSY-CLOZAPINE-EFFICACY-GATE"),
                )
            else:
                card.add_caution(
                    "PSY-CLOZAPINE-TRD",
                    "Clozapine is reserved for treatment-resistant schizophrenia (typically after "
                    "two adequate antipsychotic trials) and requires mandatory blood-count (ANC) "
                    "monitoring for agranulocytosis; it is not a first-line choice.",
                    delta=-25,
                    references=cite("PSY-CLOZAPINE-TRD"),
                )
            card.add_investigation("Clozapine trough plasma level when response, adherence, metabolism, or toxicity is uncertain.")
            card.add_monitoring("Smoking initiation/cessation and CYP1A2 interactions can markedly change clozapine exposure.")
        # NOTE: routine metabolic monitoring for second-generation antipsychotics is
        # applied by metabolic_safety (cross-cutting), so it is not repeated here.

    def extra_missing_info(self, ctx: PatientContext) -> List[str]:
        if not ctx.extended_rules:
            return []
        missing: List[str] = []
        if _needs_trial_adequacy_review(ctx):
            missing.append(
                "Antipsychotic trial adequacy: document 4-6 week duration, therapeutic dose, adherence, tolerability, interactions, and food/bioavailability requirements."
            )
        clozapine_trial = previous_clozapine_trial(ctx)
        if (
            clozapine_trial is not None
            and trial_adequacy(ctx, clozapine_trial) == "adequate"
            and normalise(clozapine_trial.response) in {"partial", "none"}
        ):
            missing.append(
                "Clozapine optimization data: trough level, adherence, smoking status/change, interacting medicines, tolerability, and treatment duration."
            )
        return missing

    def diagnosis_notes(self, ctx: PatientContext) -> List[str]:
        if not ctx.extended_rules:
            return []
        notes = [
            "Antipsychotic choice should weigh efficacy with metabolic, extrapyramidal, "
            "prolactin and sedation profiles and patient preference, alongside psychosocial "
            "interventions.",
            "Schizophrenia sequence: complete one adequate antipsychotic monotherapy trial, then a second monotherapy trial; after two adequate failures, move to clozapine rather than repeated switching or unsupported polypharmacy.",
            "Before declaring nonresponse, confirm dose, 4-6 week duration, adherence, interactions, substance use, and oral bioavailability; use plasma levels or an LAI when underexposure is suspected.",
            "Avoid routine long-term non-clozapine antipsychotic combinations; use cross-tapering or a clearly documented specialist augmentation plan.",
        ]
        if ctx.profile.non_adherence_risk:
            notes.append(
                "Adherence is uncertain: an LAI can help complete a true adequate trial and reduce relapse/rehospitalization when acceptable to the patient."
            )
        if has_any(ctx.profile.substance_use, ["tobacco", "smoking", "cigarette", "nicotine"]):
            notes.append(
                "Tobacco smoking can lower clozapine and olanzapine exposure; monitor levels and toxicity closely if smoking changes."
            )
        return notes

    def non_pharmacological(self, ctx: PatientContext) -> list[str]:
        recs = super().non_pharmacological(ctx)
        recs += [
            "Family psychoeducation and support.",
            "Cognitive behavioural therapy for psychosis (CBTp) where available.",
            "Supported employment/education and recovery-oriented rehabilitation.",
        ]
        return recs
