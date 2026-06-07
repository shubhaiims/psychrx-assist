from app.models import PatientProfile
from app.rules_engine import generate_recommendations


def recommend(**kwargs):
    kwargs.setdefault("age", 35)
    kwargs.setdefault("sex", "male")
    kwargs.setdefault("diagnosis", "secondary_catatonia")
    return generate_recommendations(PatientProfile(**kwargs))


def all_items(resp):
    return resp.most_suitable + resp.use_with_caution + resp.relatively_unsuitable


def item_for(resp, drug):
    for item in all_items(resp):
        if item.drug.lower() == drug.lower():
            return item
    return None


def has_note(resp, text):
    return any(text.lower() in note.lower() for note in resp.general_notes)


def test_ordinary_catatonia_starts_with_lorazepam_not_nmda():
    resp = recommend(
        symptoms={"catatonia": True, "stupor": True, "mutism": True, "posturing": True},
        catatonia_assessment={"sign_count": 3, "bfcrs_score": 12},
    )

    assert item_for(resp, "Lorazepam") is not None
    assert item_for(resp, "Amantadine") is None
    assert item_for(resp, "Memantine") is None


def test_fewer_than_three_signs_requires_reassessment():
    resp = recommend(
        symptoms={"catatonia": True, "mutism": True},
        catatonia_assessment={"sign_count": 2, "bfcrs_score": 4},
    )

    assert any("Fewer than three" in item for item in resp.missing_information)


def test_positive_lorazepam_challenge_strengthens_lorazepam_branch():
    resp = recommend(
        symptoms={"catatonia": True, "stupor": True, "mutism": True, "posturing": True},
        catatonia_assessment={
            "sign_count": 3,
            "bfcrs_score": 15,
            "lorazepam_challenge_response": "positive",
        },
    )
    item = item_for(resp, "Lorazepam")

    assert item is not None
    assert any(hit.rule_id == "CAT-LORAZEPAM-CHALLENGE" for hit in item.rule_trace)


def test_adequate_lorazepam_without_remission_prompts_ect_before_nmda():
    resp = recommend(
        symptoms={"catatonia": True, "stupor": True, "mutism": True, "posturing": True},
        catatonia_assessment={
            "sign_count": 3,
            "bfcrs_score": 18,
            "lorazepam_trial_outcome": "none",
            "lorazepam_current_daily_mg": 16,
            "ect_status": "available_not_started",
        },
    )

    assert item_for(resp, "Amantadine") is None
    assert item_for(resp, "Memantine") is None
    assert has_note(resp, "arrange ECT promptly")


def test_nmda_options_after_adequate_lorazepam_when_ect_unavailable():
    resp = recommend(
        symptoms={"catatonia": True, "stupor": True, "mutism": True, "posturing": True},
        catatonia_assessment={
            "sign_count": 3,
            "bfcrs_score": 20,
            "lorazepam_trial_outcome": "partial",
            "lorazepam_current_daily_mg": 16,
            "ect_status": "unavailable",
        },
    )

    assert item_for(resp, "Amantadine") is not None
    assert item_for(resp, "Memantine") is not None
    assert has_note(resp, "consider amantadine or memantine")


def test_malignant_catatonia_emergency_branch():
    resp = recommend(
        severity="emergency",
        care_setting="emergency_department",
        symptoms={
            "catatonia": True,
            "stupor": True,
            "mutism": True,
            "rigidity": True,
            "hyperthermia": True,
            "autonomic_instability": True,
        },
        catatonia_assessment={
            "subtype": "malignant",
            "sign_count": 4,
            "bfcrs_score": 28,
            "temperature_c": 39.2,
            "heart_rate_bpm": 118,
        },
    )

    assert item_for(resp, "Lorazepam") is not None
    assert any("malignant catatonia" in flag.lower() for flag in resp.urgent_red_flags)
    assert has_note(resp, "48-72 hours")


def test_nms_moderate_uses_dopaminergic_options_without_dantrolene():
    resp = recommend(
        diagnosis="catatonia_induced_by_substances_or_medications",
        severity="severe",
        care_setting="emergency_department",
        symptoms={"catatonia": True, "rigidity": True, "mutism": True, "hyperthermia": True},
        catatonia_assessment={
            "subtype": "nms",
            "sign_count": 3,
            "bfcrs_score": 22,
            "temperature_c": 38.5,
            "heart_rate_bpm": 110,
            "recent_dopamine_antagonist_exposure": True,
        },
    )

    assert item_for(resp, "Bromocriptine") is not None
    assert item_for(resp, "Amantadine") is not None
    assert item_for(resp, "Dantrolene") is None
    assert has_note(resp, "Moderate NMS")


def test_nms_severe_adds_dantrolene_and_ect_warning():
    resp = recommend(
        diagnosis="catatonia_induced_by_substances_or_medications",
        severity="emergency",
        care_setting="emergency_department",
        symptoms={"catatonia": True, "rigidity": True, "mutism": True, "hyperthermia": True},
        catatonia_assessment={
            "subtype": "nms",
            "sign_count": 3,
            "bfcrs_score": 30,
            "temperature_c": 40.2,
            "heart_rate_bpm": 130,
            "recent_dopamine_antagonist_exposure": True,
        },
    )

    assert item_for(resp, "Dantrolene") is not None
    assert has_note(resp, "2-3 days")


def test_special_subtypes_are_narrowly_mapped():
    clozapine = recommend(
        diagnosis="catatonia_induced_by_substances_or_medications",
        symptoms={"catatonia": True, "stupor": True, "mutism": True, "posturing": True},
        catatonia_assessment={"subtype": "clozapine_withdrawal", "sign_count": 3, "bfcrs_score": 14},
    )
    periodic = recommend(
        symptoms={"catatonia": True, "stupor": True, "mutism": True, "posturing": True},
        catatonia_assessment={"subtype": "periodic", "sign_count": 3, "bfcrs_score": 12},
    )
    autism = recommend(
        age=14,
        symptoms={"catatonia": True, "stupor": True, "mutism": True, "posturing": True},
        catatonia_assessment={
            "subtype": "autism_associated",
            "sign_count": 3,
            "bfcrs_score": 12,
            "clear_change_from_autism_baseline": False,
        },
    )

    assert item_for(clozapine, "Clozapine") is not None
    assert item_for(periodic, "Lithium") is not None
    assert has_note(autism, "baseline")
