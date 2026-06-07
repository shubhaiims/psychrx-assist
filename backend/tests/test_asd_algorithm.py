from app.models import PatientProfile, PreviousDrugResponse
from app.rules_engine import generate_recommendations


def recommend(**kwargs):
    kwargs.setdefault("age", 10)
    kwargs.setdefault("sex", "male")
    kwargs.setdefault("diagnosis", "autism_spectrum_disorder")
    return generate_recommendations(PatientProfile(**kwargs))


def all_items(resp):
    return resp.most_suitable + resp.use_with_caution + resp.relatively_unsuitable


def item_for(resp, drug):
    for item in all_items(resp):
        if item.drug.lower() == drug.lower():
            return item
    return None


def hit(item, rule_id):
    if item is None:
        return None
    return next((entry for entry in item.rule_trace if entry.rule_id == rule_id), None)


def has_missing(resp, text):
    return any(text.lower() in item.lower() for item in resp.missing_information)


def has_note(resp, text):
    return any(text.lower() in item.lower() for item in resp.general_notes)


def safe_asd_checks(**overrides):
    base = {
        "target_behaviour_defined": True,
        "baseline_measure_recorded": True,
        "functional_behaviour_assessment_done": True,
        "psychosocial_intervention_attempted": True,
        "medical_or_environmental_triggers_reviewed": True,
        "communication_needs_reviewed": True,
        "sensory_triggers_reviewed": True,
    }
    base.update(overrides)
    return base


def test_asd_without_target_does_not_rank_medication():
    resp = recommend()

    assert all_items(resp) == []
    assert has_missing(resp, "Select one ASD target symptom")
    assert has_note(resp, "do not prescribe to treat autism itself")


def test_asd_severe_irritability_ranks_risperidone_and_aripiprazole():
    resp = recommend(
        symptoms={"aggression_risk": True, "self_injury": True},
        asd_assessment=safe_asd_checks(
            target_domain="irritability",
            irritability_level="severe",
            psychosocial_unavailable_due_to_severity=True,
            psychosocial_intervention_attempted=False,
        ),
    )

    assert item_for(resp, "Risperidone") is not None
    assert item_for(resp, "Aripiprazole") is not None
    assert hit(item_for(resp, "Risperidone"), "ASD-IRRITABILITY-ANTIPSYCHOTIC") is not None
    assert any("Self-injury" in flag for flag in resp.urgent_red_flags)


def test_asd_mild_irritability_prefers_alpha2_and_requires_psychosocial_documentation():
    resp = recommend(
        symptoms={"agitation": True},
        asd_assessment={
            "target_domain": "irritability",
            "irritability_level": "mild",
            "target_behaviour_defined": True,
            "baseline_measure_recorded": True,
        },
    )

    guanfacine = item_for(resp, "Guanfacine")
    assert guanfacine is not None
    assert item_for(resp, "Risperidone") is None
    assert hit(guanfacine, "ASD-PSYCHOSOCIAL-FIRST") is not None
    assert has_missing(resp, "behavioural/educational/environmental")


def test_asd_adhd_with_anxiety_sleep_avoids_stimulant_until_nonstimulant_failure():
    first = recommend(
        symptoms={"hyperactivity": True, "inattention": True, "anxiety": True, "insomnia": True},
        asd_assessment=safe_asd_checks(target_domain="adhd"),
    )
    resistant = recommend(
        symptoms={"hyperactivity": True, "inattention": True, "anxiety": True, "insomnia": True},
        asd_assessment=safe_asd_checks(target_domain="adhd"),
        previous_drug_responses=[
            PreviousDrugResponse(drug="Guanfacine", response="none", adequate_trial=True),
            PreviousDrugResponse(drug="Atomoxetine", response="none", adequate_trial=True),
        ],
    )

    assert item_for(first, "Guanfacine") is not None
    assert item_for(first, "Atomoxetine") is not None
    assert item_for(first, "Methylphenidate") is None
    assert item_for(resistant, "Methylphenidate") is not None
    assert hit(item_for(resistant, "Methylphenidate"), "ASD-STIMULANT-TOLERABILITY") is not None


def test_asd_anxiety_prefers_buspirone_mirtazapine_and_marks_ssri_caution_for_ocd_like_symptoms():
    anxiety = recommend(
        symptoms={"anxiety": True},
        asd_assessment=safe_asd_checks(target_domain="anxiety"),
    )
    ocd_like = recommend(
        symptoms={"anxiety": True, "ocd": True, "repetitive_behaviour": True},
        asd_assessment=safe_asd_checks(target_domain="anxiety"),
    )

    assert item_for(anxiety, "Buspirone") is not None
    assert item_for(anxiety, "Mirtazapine") is not None
    assert item_for(anxiety, "Sertraline") is None
    assert hit(item_for(ocd_like, "Sertraline"), "ASD-SSRI-ACTIVATION") is not None


def test_asd_sleep_uses_melatonin_after_sleep_plan_review():
    resp = recommend(
        symptoms={"insomnia": True},
        asd_assessment=safe_asd_checks(
            target_domain="sleep",
            sleep_plan_attempted=True,
            sleep_log_days=14,
        ),
    )

    melatonin = item_for(resp, "Melatonin")
    assert melatonin is not None
    assert hit(melatonin, "ASD-SLEEP-MELATONIN") is not None
    assert hit(melatonin, "ASD-SLEEP-BEHAVIOURAL-FIRST") is None


def test_asd_feeding_has_no_routine_medication_branch():
    resp = recommend(
        symptoms={"feeding_problem": True, "poor_oral_intake": True},
        asd_assessment={
            "target_domain": "feeding",
            "target_behaviour_defined": True,
            "baseline_measure_recorded": True,
        },
    )

    assert all_items(resp) == []
    assert has_missing(resp, "nutrition/growth")
    assert has_note(resp, "no routine medication branch")
