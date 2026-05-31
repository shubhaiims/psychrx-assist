"""FROZEN REFERENCE COPY of the original monolithic rule engine.

This module is NOT imported by the running application. It is kept only so the
parity test (tests/test_parity.py) can prove that the new modular engine in
``app.rules_engine`` produces byte-for-byte identical recommendations for the
existing fields. Do not edit; do not wire into ``main.py``.
"""
from app.models import PatientProfile, RecommendationItem, RecommendationResponse
from app.knowledge_base import load_drugs


def age_group(age: int) -> str:
    if age < 12:
        return "child"
    if age < 18:
        return "adolescent"
    if age >= 65:
        return "elderly"
    return "adult"


def bmi(profile: PatientProfile) -> float | None:
    if not profile.height_cm or not profile.weight_kg:
        return None
    height_m = profile.height_cm / 100
    return round(profile.weight_kg / (height_m * height_m), 1)


def normalise(text: str) -> str:
    return text.strip().lower().replace(" ", "_").replace("-", "_")


def has_any(items: list[str], keywords: list[str]) -> bool:
    haystack = " ".join([normalise(x) for x in items])
    return any(normalise(k) in haystack for k in keywords)


def previous_response_for(profile: PatientProfile, drug_name: str):
    for trial in profile.previous_drug_responses:
        if normalise(trial.drug) == normalise(drug_name):
            return trial
    return None


def compute_missing_information(profile: PatientProfile) -> list[str]:
    missing = []
    if profile.height_cm is None or profile.weight_kg is None:
        missing.append("Height and weight/BMI")
    if profile.pregnancy_status == "unknown" and profile.sex == "female":
        missing.append("Pregnancy status / urine pregnancy test where clinically relevant")
    if profile.renal_status == "unknown" and profile.labs.egfr is None:
        missing.append("Renal function / eGFR")
    if profile.hepatic_status == "unknown" and profile.labs.alt is None and profile.labs.ast is None:
        missing.append("Liver function tests")
    if profile.labs.qtc_ms is None:
        missing.append("ECG/QTc where QT-risk drug, cardiac illness, overdose risk, or polypharmacy is relevant")
    if not profile.current_medications:
        missing.append("Current medication list for interaction checking")
    if profile.diagnosis in ["bipolar_mania", "bipolar_depression", "bipolar_maintenance"]:
        if profile.labs.tsh is None:
            missing.append("TSH before lithium or mood-stabilizer planning")
    return missing


def compute_red_flags(profile: PatientProfile) -> list[str]:
    flags = []
    if profile.suicide_risk:
        flags.append("Suicide risk present: requires urgent clinical risk assessment and safety planning.")
    if profile.severity == "emergency":
        flags.append("Emergency severity selected: do not rely on routine outpatient algorithm.")
    if profile.labs.qtc_ms is not None and profile.labs.qtc_ms >= 500:
        flags.append("QTc >= 500 ms: high arrhythmia risk; avoid QT-prolonging drugs unless specialist-supervised.")
    if profile.pregnancy_status in ["pregnant_first_trimester", "pregnant_second_trimester", "pregnant_third_trimester"]:
        flags.append("Pregnancy present: requires perinatal psychiatry risk-benefit review.")
    return flags


def evaluate_drug(profile: PatientProfile, drug: dict) -> RecommendationItem | None:
    diagnosis = profile.diagnosis.value if hasattr(profile.diagnosis, "value") else str(profile.diagnosis)
    ag = age_group(profile.age)
    patient_bmi = bmi(profile)

    if diagnosis not in drug.get("diagnoses", []):
        return None

    score = drug.get("base_score", 50)
    reasons = []
    cautions = []

    reasons.append(f"Matches selected diagnosis pathway: {diagnosis.replace('_', ' ')}.")

    # Population fit
    allowed_age_groups = drug.get("age_groups", [])
    if ag in allowed_age_groups:
        score += 8
        reasons.append(f"Can be considered in {ag} population according to the local rule entry.")
    else:
        score -= 30
        cautions.append(f"Age group '{ag}' is not listed as a routine population for this drug in the current rule entry.")

    # Pregnancy and lactation rules
    pregnancy_status = profile.pregnancy_status.value if hasattr(profile.pregnancy_status, "value") else str(profile.pregnancy_status)
    if pregnancy_status in ["pregnant_first_trimester", "pregnant_second_trimester", "pregnant_third_trimester", "planning_pregnancy"]:
        pregnancy_rule = drug.get("pregnancy", "specialist_review")
        if pregnancy_rule == "avoid":
            score -= 80
            cautions.append("Avoid or strongly down-rank in pregnancy/planning pregnancy according to current rule entry.")
        elif pregnancy_rule == "specialist_review":
            score -= 25
            cautions.append("Pregnancy/planning pregnancy: use only after specialist risk-benefit review.")
        elif pregnancy_rule == "relatively_preferred_when_needed":
            score += 8
            reasons.append("Pregnancy status present: rule entry marks this as relatively preferred when medication is clinically needed.")

    if pregnancy_status == "lactating":
        lactation_rule = drug.get("lactation", "specialist_review")
        if lactation_rule == "avoid":
            score -= 50
            cautions.append("Avoid or strongly down-rank during lactation according to current rule entry.")
        elif lactation_rule == "specialist_review":
            score -= 15
            cautions.append("Lactation: use after infant-risk and maternal-benefit review.")

    # Renal rules
    renal_status = profile.renal_status.value if hasattr(profile.renal_status, "value") else str(profile.renal_status)
    if renal_status in ["moderate_impairment", "severe_impairment"] or (profile.labs.egfr is not None and profile.labs.egfr < 60):
        renal_rule = drug.get("renal", "standard")
        if renal_rule == "avoid_severe_or_specialist":
            score -= 45
            cautions.append("Renal impairment/eGFR concern: specialist dosing or alternative required.")
        elif renal_rule == "dose_adjust":
            score -= 20
            cautions.append("Renal impairment: dose adjustment and monitoring required.")

    # Hepatic rules
    hepatic_status = profile.hepatic_status.value if hasattr(profile.hepatic_status, "value") else str(profile.hepatic_status)
    if hepatic_status in ["moderate_impairment", "severe_impairment"]:
        hepatic_rule = drug.get("hepatic", "standard")
        if hepatic_rule == "avoid_severe_or_specialist":
            score -= 45
            cautions.append("Hepatic impairment: avoid or use only with specialist review according to rule entry.")
        elif hepatic_rule == "start_low_go_slow":
            score -= 15
            cautions.append("Hepatic impairment: start low, go slow, and monitor LFT/clinical toxicity.")

    # QTc rule
    if profile.labs.qtc_ms is not None:
        if profile.labs.qtc_ms >= 500 and drug.get("qt_risk") in ["moderate", "high"]:
            score -= 70
            cautions.append("QTc >= 500 ms and this drug has QT concern in the rule entry.")
        elif profile.labs.qtc_ms >= 470 and drug.get("qt_risk") == "high":
            score -= 35
            cautions.append("Borderline/prolonged QTc with high QT-risk drug entry.")

    # Metabolic risk
    if patient_bmi is not None and patient_bmi >= 30 and drug.get("metabolic_risk") == "high":
        score -= 30
        cautions.append("BMI is high and this drug is high metabolic-risk in the rule entry.")
    if has_any(profile.comorbidities, ["diabetes", "dyslipidemia", "metabolic syndrome", "obesity"]) and drug.get("metabolic_risk") == "high":
        score -= 30
        cautions.append("Metabolic comorbidity present; this drug is high metabolic-risk in the rule entry.")

    # Sedation preference
    if "avoid_sedation" in profile.preferences and drug.get("sedation") == "high":
        score -= 18
        cautions.append("Patient preference says avoid sedation; this drug is sedating in the rule entry.")

    if "avoid_weight_gain" in profile.preferences and drug.get("metabolic_risk") in ["moderate", "high"]:
        score -= 18
        cautions.append("Patient preference says avoid weight gain; this drug has metabolic/weight concern in the rule entry.")

    if profile.non_adherence_risk and drug.get("lai_available"):
        score += 12
        reasons.append("Non-adherence risk present and a long-acting injectable option exists for this drug/class.")

    # Past response
    past = previous_response_for(profile, drug["name"])
    if past:
        response = normalise(past.response)
        if response == "good":
            score += 25
            reasons.append("Previous good response to this drug recorded.")
        elif response == "partial":
            score += 10
            reasons.append("Previous partial response to this drug recorded.")
        elif response in ["none", "intolerable"]:
            score -= 35
            cautions.append(f"Previous {past.response} response/intolerance recorded for this drug.")
        if past.adverse_effects:
            cautions.append("Past adverse effects recorded: " + ", ".join(past.adverse_effects))

    # Family history signal
    if drug["name"].lower() == "lithium" and has_any(profile.family_history, ["good lithium response", "lithium responder"]):
        score += 10
        reasons.append("Family history suggests lithium response.")

    # Diagnosis-specific safety note
    if diagnosis == "bipolar_depression" and drug.get("class_name") in ["SSRI", "SNRI"]:
        score -= 25
        cautions.append("Bipolar depression: antidepressant monotherapy should not be treated as a default option; check mood stabilizer/antimanic cover.")

    # Suicide risk and overdose toxicity
    if profile.suicide_risk and drug.get("overdose_toxicity") == "high":
        score -= 35
        cautions.append("Suicide risk present; drug has high overdose-toxicity entry.")

    category = "most_suitable"
    if score < 40:
        category = "relatively_unsuitable"
    elif score < 70 or cautions:
        category = "use_with_caution"

    return RecommendationItem(
        drug=drug["name"],
        class_name=drug["class_name"],
        category=category,
        score=max(min(score, 100), 0),
        reasons=reasons,
        cautions=cautions,
        baseline_investigations=drug.get("baseline_investigations", []),
        monitoring=drug.get("monitoring", []),
        references=drug.get("references", [])
    )


def generate_recommendations(profile: PatientProfile) -> RecommendationResponse:
    items = []
    for drug in load_drugs():
        evaluated = evaluate_drug(profile, drug)
        if evaluated:
            items.append(evaluated)

    items.sort(key=lambda x: x.score, reverse=True)

    most = [x for x in items if x.category == "most_suitable"]
    caution = [x for x in items if x.category == "use_with_caution"]
    unsuitable = [x for x in items if x.category == "relatively_unsuitable"]

    patient_bmi = bmi(profile)
    summary = {
        "age_group": age_group(profile.age),
        "diagnosis": profile.diagnosis.value,
        "severity": profile.severity.value,
        "bmi": str(patient_bmi) if patient_bmi else "not_available"
    }

    general_notes = [
        "This output is a clinical decision-support draft, not a prescription.",
        "Every recommendation must be checked against full history, mental status examination, current medicines, allergies, local formulary, and clinician judgment.",
        "Replace the sample rule entries with psychiatrist-reviewed rules from licensed guidelines and drug references before clinical use."
    ]

    return RecommendationResponse(
        disclaimer="For qualified clinician decision support only. Not for patient self-medication or automatic prescribing.",
        patient_summary=summary,
        most_suitable=most[:8],
        use_with_caution=caution[:10],
        relatively_unsuitable=unsuitable[:10],
        missing_information=compute_missing_information(profile),
        urgent_red_flags=compute_red_flags(profile),
        general_notes=general_notes
    )
