"""Thin orchestrator for the modular rule engine.

Public entry point used by the API (``main.py`` calls ``generate_recommendations``).
It contains no clinical logic of its own; it wires the pieces together:

    1. derive a normalised PatientContext from the raw profile,
    2. pick the diagnosis module,
    3. evaluate each candidate drug = core rules + diagnosis rules + every safety
       modifier (each modifier screens one safety dimension),
    4. sort and bucket the results deterministically,
    5. assemble the response: the three suitability buckets PLUS the patient-level
       "missing investigations before final prescribing" list, red flags, and notes.

``extended_rules`` (default True) toggles the clinician-authored rule set on top of the
behaviour-preserving baseline. With it off the engine reproduces the original engine
exactly (tests/test_parity.py); with it on, the diagnosis-specific rules, the extended
safety logic, and the safety modules' patient advisories are applied.

Determinism: candidate drugs are produced in knowledge-base order and sorted by score
with a *stable* sort, so ties resolve to a fixed order; safety modifiers run in a fixed
registration order.
"""
from __future__ import annotations

from typing import List

# Importing these packages registers every diagnosis module and safety modifier
# (and asserts at startup that the diagnosis registry matches the Diagnosis enum).
import app.diagnoses  # noqa: F401  (side-effect: diagnosis registration + integrity check)
import app.safety  # noqa: F401     (side-effect: safety-modifier registration)

from app.engine.clinical_flags import clinical_notes, clinical_red_flags
from app.engine.context import build_context
from app.engine.global_checks import compute_global_missing_information, compute_red_flags
from app.engine.registry import get_module
from app.engine.safety_registry import all_modifiers
from app.engine.utils import normalise
from app.knowledge_base import load_drugs
from app.models import PatientProfile, RecommendationItem, RecommendationResponse

GENERAL_NOTES = [
    "This output is a clinical decision-support draft, not a prescription.",
    "Every recommendation must be checked against full history, mental status "
    "examination, current medicines, allergies, local formulary, and clinician judgment.",
    "Replace the sample rule entries with psychiatrist-reviewed rules from licensed "
    "guidelines and drug references before clinical use.",
]

DISCLAIMER = (
    "For qualified clinician decision support only. "
    "Not for patient self-medication or automatic prescribing."
)


def _dedupe_against_done(missing: List[str], done: List[str]) -> List[str]:
    """Drop any 'missing' investigation already recorded as done (loose substring match)."""
    if not done:
        return missing
    done_norm = [normalise(d) for d in done]
    kept = []
    for item in missing:
        item_norm = normalise(item)
        if any(d and (d in item_norm or item_norm in d) for d in done_norm):
            continue
        kept.append(item)
    return kept


def generate_recommendations(
    profile: PatientProfile, *, extended_rules: bool = True
) -> RecommendationResponse:
    ctx = build_context(profile, extended_rules=extended_rules)
    module = get_module(ctx.diagnosis)
    modifiers = all_modifiers()

    # 1) Evaluate each candidate drug: core rules + diagnosis rules + safety modifiers.
    items: List[RecommendationItem] = [
        module.evaluate(ctx, drug, modifiers)
        for drug in module.candidate_drugs(ctx, load_drugs())
    ]

    # 2) Rank (stable sort by clamped score, ties keep knowledge-base order).
    items.sort(key=lambda x: x.score, reverse=True)

    # 3) Bucket by category (category decided on the raw score inside each ScoreCard,
    #    including any forced 'relatively_unsuitable' from mark_unsuitable()).
    most = [x for x in items if x.category == "most_suitable"]
    caution = [x for x in items if x.category == "use_with_caution"]
    unsuitable = [x for x in items if x.category == "relatively_unsuitable"]

    # 4) Patient-level outputs.
    #    Order: global checks -> diagnosis additions -> safety-modifier advisories
    #    -> symptom-level clinical flags.
    missing_information = compute_global_missing_information(profile) + module.extra_missing_info(ctx)
    urgent_red_flags = compute_red_flags(profile) + module.extra_red_flags(ctx)
    general_notes = GENERAL_NOTES + module.diagnosis_notes(ctx)
    for modifier in modifiers:
        adv = modifier.patient_advisories(ctx)
        missing_information += adv.missing_information
        urgent_red_flags += adv.red_flags
        general_notes += adv.notes
    urgent_red_flags += clinical_red_flags(ctx)
    general_notes += clinical_notes(ctx)

    # Don't ask for investigations the clinician has already recorded as done.
    missing_information = _dedupe_against_done(missing_information, profile.investigations_done)

    summary = {
        "age_group": ctx.age_group,
        "diagnosis": ctx.diagnosis,
        "severity": ctx.severity,
        "bmi": str(ctx.bmi) if ctx.bmi else "not_available",
    }

    return RecommendationResponse(
        disclaimer=DISCLAIMER,
        patient_summary=summary,
        most_suitable=most[:8],
        use_with_caution=caution[:10],
        relatively_unsuitable=unsuitable[:10],
        missing_information=missing_information,
        urgent_red_flags=urgent_red_flags,
        general_notes=general_notes,
    )
