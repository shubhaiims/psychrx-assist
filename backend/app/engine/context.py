"""PatientContext: a normalised, pre-computed view of a PatientProfile.

The monolithic engine recomputed derived facts (age group, BMI, "is this patient
renally impaired?") and repeatedly defended against Enum-vs-string ambiguity at
every use site. We compute all of that exactly once here, then pass the frozen
context to every rule. Rules stay small and read like clinical sentences.

Nothing in this module makes a clinical judgement; it only restates the input in
a convenient shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models import PatientProfile, PreviousDrugResponse
from app.engine.utils import enum_value, has_any, normalise

# Keywords that count as a metabolic comorbidity for metabolic-risk rules.
# (Migrated verbatim from the original engine so behaviour is unchanged.)
METABOLIC_COMORBIDITY_KEYWORDS = ["diabetes", "dyslipidemia", "metabolic syndrome", "obesity"]

# Free-text comorbidity keywords that also flag cardiac / seizure history, so a
# clinician can record these either via the explicit booleans or in comorbidities.
CARDIAC_KEYWORDS = ["cardiac", "heart", "arrhythmia", "qt", "ischaem", "ischem", "myocard", "cardiovascular"]
SEIZURE_KEYWORDS = ["seizure", "epilep", "convuls"]


def age_group(age: int) -> str:
    if age < 12:
        return "child"
    if age < 18:
        return "adolescent"
    if age >= 65:
        return "elderly"
    return "adult"


def compute_bmi(profile: PatientProfile) -> Optional[float]:
    if not profile.height_cm or not profile.weight_kg:
        return None
    height_m = profile.height_cm / 100
    return round(profile.weight_kg / (height_m * height_m), 1)


@dataclass(frozen=True)
class PatientContext:
    """Immutable derived view of a patient, handed to every rule."""

    profile: PatientProfile

    # Normalised primary fields
    diagnosis: str
    severity: str
    care_setting: str
    sex: str
    age: int
    age_group: str

    # Derived physiology
    bmi: Optional[float]
    egfr: Optional[float]
    trimester: Optional[int]

    # Boolean clinical flags (pre-evaluated once)
    pregnant_or_planning: bool
    lactating: bool
    renal_impaired: bool
    hepatic_impaired: bool
    has_metabolic_comorbidity: bool
    childbearing_potential: bool
    cardiac_disease: bool
    seizure_disorder: bool
    suicidality: Optional[str]

    # Engine configuration. When False, only the behaviour-preserving baseline
    # rules run (the extended, clinician-authored rule set is skipped). This is a
    # single, obvious kill-switch a clinician/developer can flip while reviewing,
    # and it is what the parity test uses to prove the mechanical core is unchanged.
    extended_rules: bool = True

    # ----- convenience predicates (no clinical logic, just lookups) -----

    def has_preference(self, preference: str) -> bool:
        return preference in self.profile.preferences

    def previous_response_for(self, drug_name: str) -> Optional[PreviousDrugResponse]:
        for trial in self.profile.previous_drug_responses:
            if normalise(trial.drug) == normalise(drug_name):
                return trial
        return None

    def family_history_has(self, keywords: list[str]) -> bool:
        # Searches both the general family-history list and the dedicated
        # family-history-of-drug-response list, so the same keyword matches either.
        combined = list(self.profile.family_history) + list(self.profile.family_history_drug_response)
        return has_any(combined, keywords)


# Reproductive-age window used to flag "childbearing potential" for population
# rules (e.g. valproate). Deliberately a single, editable constant rather than a
# magic number buried in logic; a reviewing clinician can widen/narrow it here.
CHILDBEARING_AGE_MIN = 12
CHILDBEARING_AGE_MAX = 55


def build_context(profile: PatientProfile, *, extended_rules: bool = True) -> PatientContext:
    """Derive a PatientContext from a raw PatientProfile (deterministic).

    ``extended_rules`` toggles the clinician-authored rule set on top of the
    behaviour-preserving baseline. It defaults to on; the parity test builds the
    context with it off to compare against the original engine.
    """
    diagnosis = enum_value(profile.diagnosis)
    severity = enum_value(profile.severity)
    care_setting = enum_value(profile.care_setting)
    sex = enum_value(profile.sex)
    pregnancy_status = enum_value(profile.pregnancy_status)
    renal_status = enum_value(profile.renal_status)
    hepatic_status = enum_value(profile.hepatic_status)
    egfr = profile.labs.egfr

    pregnant_or_planning = pregnancy_status in (
        "pregnant_first_trimester",
        "pregnant_second_trimester",
        "pregnant_third_trimester",
        "planning_pregnancy",
    )
    lactating = pregnancy_status == "lactating" or bool(profile.lactation_status)

    # Effective trimester: prefer the trimester encoded in pregnancy_status, else the
    # explicit trimester field.
    trimester_from_status = {
        "pregnant_first_trimester": 1,
        "pregnant_second_trimester": 2,
        "pregnant_third_trimester": 3,
    }.get(pregnancy_status)
    trimester = trimester_from_status if trimester_from_status is not None else profile.trimester

    # Mirrors the original engine: renal impairment is moderate/severe status OR eGFR < 60.
    renal_impaired = renal_status in ("moderate_impairment", "severe_impairment") or (
        egfr is not None and egfr < 60
    )
    hepatic_impaired = hepatic_status in ("moderate_impairment", "severe_impairment")

    # "Childbearing potential": used by pregnancy-psychiatry rules that apply even
    # when the patient is not currently pregnant (e.g. valproate restrictions).
    childbearing_potential = sex == "female" and (
        CHILDBEARING_AGE_MIN <= profile.age <= CHILDBEARING_AGE_MAX
    )

    # Cardiac / seizure history from the explicit flags OR free-text comorbidities.
    cardiac_disease = profile.cardiac_disease or has_any(profile.comorbidities, CARDIAC_KEYWORDS)
    seizure_disorder = profile.seizure_disorder or has_any(profile.comorbidities, SEIZURE_KEYWORDS)

    suicidality = enum_value(profile.suicidality) if profile.suicidality is not None else None

    return PatientContext(
        profile=profile,
        diagnosis=diagnosis,
        severity=severity,
        care_setting=care_setting,
        sex=sex,
        age=profile.age,
        age_group=age_group(profile.age),
        bmi=compute_bmi(profile),
        egfr=egfr,
        trimester=trimester,
        pregnant_or_planning=pregnant_or_planning,
        lactating=lactating,
        renal_impaired=renal_impaired,
        hepatic_impaired=hepatic_impaired,
        has_metabolic_comorbidity=has_any(profile.comorbidities, METABOLIC_COMORBIDITY_KEYWORDS),
        childbearing_potential=childbearing_potential,
        cardiac_disease=cardiac_disease,
        seizure_disorder=seizure_disorder,
        suicidality=suicidality,
        extended_rules=extended_rules,
    )
