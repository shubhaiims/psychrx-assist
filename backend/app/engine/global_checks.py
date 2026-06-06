"""Patient-level checks that are independent of any single drug.

``compute_global_missing_information`` lists generally-needed work-up that is absent.
``compute_red_flags`` lists urgent safety conditions. Diagnosis-specific additions
(e.g. "TSH before lithium" for bipolar) live in the relevant diagnosis module via its
``extra_missing_info`` / ``extra_red_flags`` hooks and are appended after these.

Wording is migrated verbatim from the original engine.
"""
from __future__ import annotations

from typing import List

from app.models import PatientProfile
from app.engine.utils import enum_value


def compute_global_missing_information(profile: PatientProfile) -> List[str]:
    missing: List[str] = []
    if profile.height_cm is None or profile.weight_kg is None:
        missing.append("Height and weight/BMI")
    if enum_value(profile.pregnancy_status) == "unknown" and enum_value(profile.sex) == "female":
        missing.append("Pregnancy status / urine pregnancy test where clinically relevant")
    if enum_value(profile.renal_status) == "unknown" and profile.labs.egfr is None:
        missing.append("Renal function / eGFR")
    if enum_value(profile.hepatic_status) == "unknown" and profile.labs.alt is None and profile.labs.ast is None:
        missing.append("Liver function tests")
    if profile.labs.qtc_ms is None:
        missing.append("ECG/QTc where QT-risk drug, cardiac illness, overdose risk, or polypharmacy is relevant")
    if not profile.current_medications:
        missing.append("Current medication list for interaction checking")
    if enum_value(profile.care_setting) in {"emergency_department", "inpatient"}:
        if not any(
            "reconciliation" in item.lower() or "collateral" in item.lower()
            for item in profile.investigations_done
        ):
            missing.append(
                "Medication reconciliation and collateral medication/adherence history"
            )
        if not any(
            keyword in item.lower()
            for item in profile.investigations_done
            for keyword in ("physical exam", "medical assessment", "toxicology", "withdrawal")
        ):
            missing.append(
                "Inpatient medical assessment: physical examination, vital signs, relevant CBC/CMP/electrolytes, toxicology/withdrawal assessment, and ECG when indicated"
            )
    return missing


def compute_red_flags(profile: PatientProfile) -> List[str]:
    flags: List[str] = []
    if profile.suicide_risk:
        flags.append("Suicide risk present: requires urgent clinical risk assessment and safety planning.")
    if enum_value(profile.severity) == "emergency":
        flags.append("Emergency severity selected: do not rely on routine outpatient algorithm.")
    if enum_value(profile.care_setting) == "emergency_department":
        flags.append(
            "Emergency-department setting selected: stabilize immediate medical and behavioural risks before using the longitudinal medication sequence."
        )
    if profile.labs.qtc_ms is not None and profile.labs.qtc_ms >= 500:
        flags.append("QTc >= 500 ms: high arrhythmia risk; avoid QT-prolonging drugs unless specialist-supervised.")
    if enum_value(profile.pregnancy_status) in (
        "pregnant_first_trimester",
        "pregnant_second_trimester",
        "pregnant_third_trimester",
    ):
        flags.append("Pregnancy present: requires perinatal psychiatry risk-benefit review.")
    return flags
