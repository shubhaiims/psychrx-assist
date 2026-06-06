"""Core per-drug rules that are not 'safety modifiers'.

These three modifiers — population/age fit, patient preference, and previous drug
response — shape ranking but are not safety screens, so they live here rather than in
the named safety modules. Wording, deltas, and behaviour are migrated verbatim from
the original engine; they are part of the behaviour-preserving baseline (not gated by
``extended_rules``) and are asserted by the parity test.
"""
from __future__ import annotations

from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.scoring import ScoreCard
from app.engine.utils import normalise
from app.models import PreviousDrugResponse


ADEQUATE_TRIAL_WEEKS_BY_DIAGNOSIS = {
    "schizophrenia": 4.0,
    "acute_psychosis": 4.0,
    "ocd": 12.0,
    "major_depressive_disorder": 6.0,
    "generalized_anxiety_disorder": 8.0,
    "social_anxiety_disorder": 10.0,
    "panic_disorder": 6.0,
    "ptsd": 8.0,
    "bipolar_depression": 6.0,
    "bipolar_mania": 2.0,
}


def apply_age_fit(ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
    if ctx.age_group in drug.get("age_groups", []):
        card.add_reason(
            "POP-AGE-FIT",
            f"Can be considered in {ctx.age_group} population according to the local rule entry.",
            delta=8,
            references=cite("POP-AGE-FIT"),
        )
    else:
        card.add_caution(
            "POP-AGE-OFFLABEL",
            f"Age group '{ctx.age_group}' is not listed as a routine population for this drug in the current rule entry.",
            delta=-30,
            references=cite("POP-AGE-OFFLABEL"),
        )


def apply_patient_preference(ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
    if ctx.has_preference("avoid_sedation") and drug.get("sedation") == "high":
        card.add_caution(
            "PREF-SEDATION",
            "Patient preference says avoid sedation; this drug is sedating in the rule entry.",
            delta=-18,
            references=cite("PREF-SEDATION"),
        )
    if ctx.has_preference("avoid_weight_gain") and drug.get("metabolic_risk") in ("moderate", "high"):
        card.add_caution(
            "PREF-WEIGHT",
            "Patient preference says avoid weight gain; this drug has metabolic/weight concern in the rule entry.",
            delta=-18,
            references=cite("PREF-WEIGHT"),
        )


def _adequate_duration_from_weeks(ctx: PatientContext, trial: PreviousDrugResponse) -> bool | None:
    if trial.adequate_duration is not None:
        return trial.adequate_duration
    if trial.duration_weeks is None:
        return None
    minimum = ADEQUATE_TRIAL_WEEKS_BY_DIAGNOSIS.get(ctx.diagnosis)
    if minimum is None:
        return None
    return trial.duration_weeks >= minimum


def trial_adequacy(ctx: PatientContext, trial: PreviousDrugResponse) -> str:
    """Return adequate, inadequate, or unknown using explicit clinician inputs first."""
    if trial.adequate_trial:
        return "adequate"

    dose_ok = trial.adequate_dose
    duration_ok = _adequate_duration_from_weeks(ctx, trial)

    if dose_ok is False or duration_ok is False:
        return "inadequate"
    if dose_ok is True and duration_ok is True:
        return "adequate"
    return "unknown"


def _apply_previous_response_baseline(past: PreviousDrugResponse, card: ScoreCard) -> None:
    """Legacy behaviour used when extended rules are disabled."""
    response = normalise(past.response)
    if response == "good":
        card.add_reason("PASTRESP-GOOD", "Previous good response to this drug recorded.", delta=25, references=cite("PASTRESP-GOOD"))
    elif response == "partial":
        card.add_reason("PASTRESP-PARTIAL", "Previous partial response to this drug recorded.", delta=10, references=cite("PASTRESP-PARTIAL"))
    elif response in ("none", "intolerable"):
        card.add_caution(
            "PASTRESP-FAIL",
            f"Previous {past.response} response/intolerance recorded for this drug.",
            delta=-35,
            references=cite("PASTRESP-FAIL"),
        )
    if past.adverse_effects:
        card.add_caution(
            "PASTRESP-AE",
            "Past adverse effects recorded: " + ", ".join(past.adverse_effects),
            delta=0,
            references=cite("PASTRESP-AE"),
        )


def apply_previous_response(ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
    past = ctx.previous_response_for(drug["name"])
    if not past:
        return
    if not ctx.extended_rules:
        _apply_previous_response_baseline(past, card)
        return

    response = normalise(past.response)
    adequacy = trial_adequacy(ctx, past)

    if response == "good":
        card.add_reason(
            "PASTRESP-GOOD",
            "Previous good response to this drug recorded.",
            delta=25,
            references=cite("PASTRESP-GOOD"),
        )
    elif response == "partial":
        if adequacy == "adequate":
            card.add_reason(
                "PASTRESP-PARTIAL",
                "Previous partial response after an adequate trial; consider optimisation or augmentation before abandoning this option.",
                delta=8,
                references=cite("PASTRESP-PARTIAL"),
            )
        else:
            card.add_caution(
                "PASTRESP-INADQ",
                "Previous partial response was not documented as an adequate dose-duration trial; complete an adequate trial before judging failure.",
                delta=-5,
                references=cite("PASTRESP-INADQ"),
            )
            card.add_monitoring("Confirm adequate dose and duration before classifying this previous trial as failed.")
    elif response == "none":
        if adequacy == "adequate":
            if ctx.diagnosis == "schizophrenia" and normalise(drug["name"]) == "clozapine":
                card.add_caution(
                    "PASTRESP-CLOZ-OPTIMIZE",
                    "Apparent clozapine nonresponse requires confirmation of adherence, duration, tolerability, smoking/CYP interactions, and a therapeutic trough level before abandoning clozapine.",
                    delta=-10,
                    references=cite("PASTRESP-CLOZ-OPTIMIZE"),
                )
                card.add_investigation("Clozapine trough plasma level before declaring treatment failure.")
                card.add_monitoring("Review smoking changes and CYP1A2 interactions when interpreting clozapine response or toxicity.")
            else:
                card.add_caution(
                    "PASTRESP-ADEQ-NONRESP",
                    "Previous no response after an adequate trial; do not re-suggest this drug unless there is a clear clinician override reason.",
                    delta=-85,
                    references=cite("PASTRESP-ADEQ-NONRESP"),
                )
        else:
            card.add_caution(
                "PASTRESP-INADQ",
                "Previous no response was not documented as an adequate dose-duration trial; complete an adequate trial before calling it ineffective.",
                delta=-5,
                references=cite("PASTRESP-INADQ"),
            )
            card.add_monitoring("Confirm adequate dose and duration before classifying this previous trial as failed.")
    elif response == "intolerable":
        card.add_caution(
            "PASTRESP-INTOL",
            "Previous intolerance recorded for this drug; avoid re-challenge unless the clinician documents a specific rationale.",
            delta=-85,
            references=cite("PASTRESP-INTOL"),
        )
    elif response == "unknown" and adequacy != "adequate":
        card.add_caution(
            "PASTRESP-INADQ",
            "Previous trial outcome or adequacy is unclear; confirm dose, duration, adherence, and tolerability before making a switch decision.",
            delta=-5,
            references=cite("PASTRESP-INADQ"),
        )

    if past.adverse_effects:
        card.add_caution(
            "PASTRESP-AE",
            "Past adverse effects recorded: " + ", ".join(past.adverse_effects),
            delta=0,
            references=cite("PASTRESP-AE"),
        )
