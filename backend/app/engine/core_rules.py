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


def apply_previous_response(ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
    past = ctx.previous_response_for(drug["name"])
    if not past:
        return
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
