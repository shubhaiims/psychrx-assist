"""Unit tests for the extended (clinician-authored) rule set.

Each test constructs a minimal patient that should trigger one rule, then asserts the
rule fired with the expected effect (recorded in ``rule_trace``) or produced the
expected advisory. These tests lock in the behaviour of the new diagnosis and
population rules and double as living documentation a clinician can read and edit.

They also verify that the whole extended set is gated by ``extended_rules`` and that
the population layers are registered.
"""
from __future__ import annotations

from typing import List, Optional

from app.models import (
    LabValues,
    PatientProfile,
    PregnancyStatus,
    PreviousDrugResponse,
    Severity,
    Sex,
)
from app.rules_engine import generate_recommendations
from app.engine.safety_registry import all_modifiers


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

def recommend(extended: bool = True, **profile_kwargs):
    profile_kwargs.setdefault("age", 35)
    profile_kwargs.setdefault("sex", Sex.male)
    profile = PatientProfile(**profile_kwargs)
    return generate_recommendations(profile, extended_rules=extended)


def _all_items(resp):
    return resp.most_suitable + resp.use_with_caution + resp.relatively_unsuitable


def item_for(resp, drug: str):
    for it in _all_items(resp):
        if it.drug.lower() == drug.lower():
            return it
    return None


def hit(item, rule_id: str):
    if item is None:
        return None
    for e in item.rule_trace:
        if e.rule_id == rule_id:
            return e
    return None


def trace_ids(item) -> List[str]:
    return [e.rule_id for e in item.rule_trace] if item else []


# --------------------------------------------------------------------------- #
# 1. Major depressive disorder                                                #
# --------------------------------------------------------------------------- #

def test_mdd_ssri_first_line():
    r = recommend(diagnosis="major_depressive_disorder")
    e = hit(item_for(r, "Sertraline"), "MDD-SSRI-FIRSTLINE")
    assert e is not None and e.kind == "reason" and e.delta > 0


def test_mdd_antipsychotic_is_adjunct_not_first_line():
    r = recommend(diagnosis="major_depressive_disorder", severity=Severity.moderate)
    e = hit(item_for(r, "Quetiapine"), "MDD-SGA-ADJUNCT")
    assert e is not None and e.kind == "caution" and e.delta < 0


def test_mdd_psychotic_features_supports_antipsychotic():
    r = recommend(
        diagnosis="major_depressive_disorder",
        severity=Severity.severe_with_psychotic_features,
    )
    item = item_for(r, "Quetiapine")
    assert hit(item, "MDD-PSYCHOTIC-AUGMENT") is not None
    assert hit(item, "MDD-SGA-ADJUNCT") is None  # adjunct caution suppressed for psychotic features


def test_mdd_bupropion_first_line_and_preference_match():
    r = recommend(
        diagnosis="major_depressive_disorder",
        preferences=["avoid_sexual_side_effects", "avoid_weight_gain"],
    )
    item = item_for(r, "Bupropion")
    assert hit(item, "MDD-BUPROPION-FIRSTLINE") is not None
    assert hit(item, "MDD-BUPROPION-PREFERENCE") is not None


def test_psychotic_depression_favors_venlafaxine_and_evidence_sga():
    r = recommend(
        diagnosis="major_depressive_disorder",
        severity=Severity.severe_with_psychotic_features,
    )
    assert hit(item_for(r, "Venlafaxine XR"), "MDD-PSYCHOTIC-VENLAFAXINE") is not None
    assert hit(item_for(r, "Olanzapine"), "MDD-PSYCHOTIC-SGA-EVIDENCE") is not None


def test_psychotic_depression_downranks_nonpreferred_antidepressants():
    r = recommend(
        diagnosis="major_depressive_disorder",
        severity=Severity.severe_with_psychotic_features,
    )
    assert hit(item_for(r, "Bupropion"), "MDD-PSYCHOTIC-AD-NOTFAVORED") is not None
    assert hit(item_for(r, "Mirtazapine"), "MDD-PSYCHOTIC-AD-NOTFAVORED") is not None


def test_trd_after_two_adequate_antidepressant_failures_adds_lithium_augmentation():
    r = recommend(
        diagnosis="major_depressive_disorder",
        previous_drug_responses=[
            PreviousDrugResponse(drug="Sertraline", response="none", adequate_trial=True),
            PreviousDrugResponse(drug="Escitalopram", response="none", adequate_trial=True),
        ],
    )
    item = item_for(r, "Lithium")
    assert item is not None
    assert hit(item, "MDD-TRD-LITHIUM-AUGMENT") is not None


def test_inadequate_nonresponse_prompts_adequate_trial_before_declaring_failure():
    r = recommend(
        diagnosis="major_depressive_disorder",
        previous_drug_responses=[
            PreviousDrugResponse(
                drug="Sertraline",
                response="none",
                adequate_trial=False,
                adequate_dose=False,
                adequate_duration=False,
                duration_weeks=2,
            )
        ],
    )
    item = item_for(r, "Sertraline")
    assert hit(item, "PASTRESP-INADQ") is not None
    assert hit(item, "PASTRESP-ADEQ-NONRESP") is None
    assert item.category == "use_with_caution"
    assert any("Confirm adequate dose and duration" in m for m in item.monitoring)


def test_adequate_nonresponse_makes_same_drug_unsuitable():
    r = recommend(
        diagnosis="major_depressive_disorder",
        previous_drug_responses=[
            PreviousDrugResponse(drug="Sertraline", response="none", adequate_trial=True)
        ],
    )
    item = item_for(r, "Sertraline")
    e = hit(item, "PASTRESP-ADEQ-NONRESP")
    assert e is not None and e.kind == "caution" and e.delta < -50
    assert item.category == "relatively_unsuitable"


def test_prior_intolerance_makes_same_drug_unsuitable():
    r = recommend(
        diagnosis="major_depressive_disorder",
        previous_drug_responses=[
            PreviousDrugResponse(
                drug="Sertraline",
                response="intolerable",
                adequate_trial=True,
                adverse_effects=["severe nausea"],
            )
        ],
    )
    item = item_for(r, "Sertraline")
    assert hit(item, "PASTRESP-INTOL") is not None
    assert hit(item, "PASTRESP-AE") is not None
    assert item.category == "relatively_unsuitable"


def test_prior_response_protocol_preserves_legacy_when_extended_rules_off():
    r = recommend(
        extended=False,
        diagnosis="major_depressive_disorder",
        previous_drug_responses=[
            PreviousDrugResponse(drug="Sertraline", response="none", adequate_trial=False)
        ],
    )
    item = item_for(r, "Sertraline")
    assert hit(item, "PASTRESP-FAIL") is not None
    assert hit(item, "PASTRESP-INADQ") is None


# --------------------------------------------------------------------------- #
# 2. Bipolar disorder                                                         #
# --------------------------------------------------------------------------- #

def test_bipolar_mania_lithium_first_line():
    r = recommend(diagnosis="bipolar_mania")
    assert hit(item_for(r, "Lithium"), "BIP-LITHIUM-FIRSTLINE") is not None


def test_bipolar_mania_antipsychotic_first_line():
    r = recommend(diagnosis="bipolar_mania")
    assert hit(item_for(r, "Quetiapine"), "BIP-MANIA-ANTIPSYCHOTIC") is not None


def test_mixed_mania_uses_antipsychotic_first_sequence():
    r = recommend(
        diagnosis="bipolar_mania",
        diagnosis_subtype="mixed features",
        symptoms={"manic": True, "depressive": True},
    )
    assert hit(item_for(r, "Quetiapine"), "BIP-MANIA-MIXED-SGA") is not None
    assert hit(item_for(r, "Lithium"), "BIP-MANIA-MIXED-LITHIUM-SEQUENCE") is not None


def test_bipolar_depression_lamotrigine_first_line():
    r = recommend(diagnosis="bipolar_depression")
    assert hit(item_for(r, "Lamotrigine"), "BIP-LAMOTRIGINE") is not None


def test_bipolar_depression_preferred_options_are_ranked():
    r = recommend(diagnosis="bipolar_depression")
    for drug in ("Lithium", "Quetiapine", "Lamotrigine", "Lurasidone", "Cariprazine"):
        assert hit(item_for(r, drug), "BIP-DEP-PREFERRED") is not None, drug


def test_bipolar_depression_antidepressants_strongly_cautioned_with_mixed_features():
    r = recommend(
        diagnosis="bipolar_depression",
        diagnosis_subtype="rapid cycling mixed features",
        symptoms={"depressive": True, "manic": True},
    )
    item = item_for(r, "Sertraline")
    assert item is not None
    assert hit(item, "BIP-DEP-AD-RISK") is not None
    assert hit(item, "BIP-AD-MONOTX") is not None


def test_bipolar_lithium_family_history_is_baseline_rule():
    # The lithium family-history boost is part of the behaviour-preserving baseline,
    # so it fires even with the extended rule set OFF.
    r_off = recommend(extended=False, diagnosis="bipolar_mania", family_history=["good lithium response"])
    assert hit(item_for(r_off, "Lithium"), "BIP-LITHIUM-FHX") is not None


# --------------------------------------------------------------------------- #
# 3. Schizophrenia / psychosis                                                #
# --------------------------------------------------------------------------- #

def test_clozapine_reserved_for_treatment_resistance():
    r = recommend(diagnosis="schizophrenia")
    e = hit(item_for(r, "Clozapine"), "PSY-CLOZAPINE-TRD")
    assert e is not None and e.kind == "caution" and e.delta < 0


def test_clozapine_supported_after_two_adequate_antipsychotic_failures():
    r = recommend(
        diagnosis="schizophrenia",
        previous_drug_responses=[
            PreviousDrugResponse(drug="Risperidone", response="none", adequate_trial=True),
            PreviousDrugResponse(drug="Olanzapine", response="none", adequate_trial=True),
        ],
    )
    item = item_for(r, "Clozapine")
    e = hit(item, "PSY-CLOZAPINE-TRS")
    assert e is not None and e.kind == "reason" and e.delta > 0
    assert hit(item, "PSY-CLOZAPINE-TRD") is None


def test_first_episode_prefers_lower_burden_initial_antipsychotics():
    r = recommend(
        diagnosis="schizophrenia",
        diagnosis_subtype="first episode",
        symptoms={"psychotic": True},
    )
    for drug in ("Amisulpride", "Aripiprazole", "Lurasidone", "Risperidone", "Ziprasidone"):
        assert hit(item_for(r, drug), "PSY-FIRST-EPISODE-PREFERRED") is not None, drug
    assert hit(item_for(r, "Olanzapine"), "PSY-FIRST-EPISODE-OLANZAPINE") is not None
    assert hit(item_for(r, "Quetiapine"), "PSY-FIRST-EPISODE-QUETIAPINE") is not None
    assert hit(item_for(r, "Haloperidol"), "PSY-FIRST-EPISODE-FGA") is not None
    assert hit(item_for(r, "Cariprazine"), "PSY-FIRST-EPISODE-OTHER-SGA") is not None


def test_second_trial_prefers_new_monotherapy_after_one_adequate_failure():
    r = recommend(
        diagnosis="schizophrenia",
        previous_drug_responses=[
            PreviousDrugResponse(drug="Aripiprazole", response="none", adequate_trial=True),
        ],
    )
    for drug in ("Risperidone", "Olanzapine", "Haloperidol"):
        assert hit(item_for(r, drug), "PSY-SECOND-MONOTHERAPY") is not None, drug


def test_clozapine_gate_requires_one_high_efficacy_trial_when_risk_not_urgent():
    r = recommend(
        diagnosis="schizophrenia",
        previous_drug_responses=[
            PreviousDrugResponse(drug="Aripiprazole", response="none", adequate_trial=True),
            PreviousDrugResponse(drug="Lurasidone", response="none", adequate_trial=True),
        ],
    )
    item = item_for(r, "Clozapine")
    assert hit(item, "PSY-CLOZAPINE-TRS-CONDITIONAL") is not None
    assert hit(item, "PSY-CLOZAPINE-EFFICACY-GATE") is not None
    assert hit(item, "PSY-CLOZAPINE-TRS") is None


def test_clozapine_can_be_considered_early_for_suicidality_or_aggression():
    suicidal = recommend(
        diagnosis="schizophrenia",
        suicide_risk=True,
        suicidality="ideation_with_plan",
    )
    aggressive = recommend(
        diagnosis="schizophrenia",
        symptoms={"psychotic": True, "aggression_risk": True},
    )
    assert hit(item_for(suicidal, "Clozapine"), "PSY-CLOZAPINE-EARLY-RISK") is not None
    assert hit(item_for(aggressive, "Clozapine"), "PSY-CLOZAPINE-EARLY-RISK") is not None


def test_apparent_clozapine_nonresponse_prompts_optimization_not_automatic_rejection():
    r = recommend(
        diagnosis="schizophrenia",
        previous_drug_responses=[
            PreviousDrugResponse(drug="Clozapine", response="none", adequate_trial=True),
        ],
    )
    item = item_for(r, "Clozapine")
    assert hit(item, "PASTRESP-CLOZ-OPTIMIZE") is not None
    assert hit(item, "PASTRESP-ADEQ-NONRESP") is None
    assert hit(item, "PSY-CLOZAPINE-OPTIMIZE") is not None
    assert item.category != "relatively_unsuitable"
    assert any("trough" in investigation.lower() for investigation in item.baseline_investigations)


def test_optimized_clozapine_partial_response_surfaces_weak_augmentation_options():
    r = recommend(
        diagnosis="schizophrenia",
        previous_drug_responses=[
            PreviousDrugResponse(drug="Clozapine", response="partial", adequate_trial=True),
        ],
    )
    for drug in ("Risperidone", "Lamotrigine"):
        item = item_for(r, drug)
        assert item is not None
        assert hit(item, "PSY-CLOZAPINE-AUGMENT") is not None
        assert hit(item, "PSY-CLOZAPINE-AUGMENT-WEAK") is not None


def test_primary_negative_symptoms_surface_cariprazine_and_mirtazapine_adjunct():
    r = recommend(
        diagnosis="schizophrenia",
        symptoms={"negative": True},
    )
    assert hit(item_for(r, "Cariprazine"), "PSY-NEGATIVE-CARIPRAZINE") is not None
    mirtazapine = item_for(r, "Mirtazapine")
    assert mirtazapine is not None
    assert hit(mirtazapine, "PSY-NEGATIVE-MIRTAZAPINE") is not None
    assert hit(mirtazapine, "PSY-NEGATIVE-MIRTAZAPINE-ADJUNCT") is not None


def test_sga_metabolic_monitoring_added():
    r = recommend(diagnosis="schizophrenia")
    item = item_for(r, "Olanzapine")
    assert any("metabolic monitoring" in m.lower() for m in item.monitoring)


def test_acute_psychosis_rule_out_organic_note():
    r = recommend(diagnosis="acute_psychosis")
    assert any("organic" in n.lower() for n in r.general_notes)


# --------------------------------------------------------------------------- #
# 4. OCD / anxiety disorders                                                  #
# --------------------------------------------------------------------------- #

def test_anxiety_ssri_first_line():
    for dx in ("ocd", "generalized_anxiety_disorder", "social_anxiety_disorder", "panic_disorder", "ptsd"):
        r = recommend(diagnosis=dx)
        assert hit(item_for(r, "Sertraline"), "ANX-SSRI-FIRSTLINE") is not None, dx


def test_ocd_dosing_note():
    r = recommend(diagnosis="ocd")
    assert any("12-week" in n.lower() for n in r.general_notes)


def test_ocd_prefers_selected_ssris_and_keeps_clomipramine_later():
    r = recommend(diagnosis="ocd")
    assert hit(item_for(r, "Sertraline"), "OCD-PREFERRED-SSRI") is not None
    clomipramine = item_for(r, "Clomipramine")
    assert hit(clomipramine, "OCD-CLOMIPRAMINE-SAFETY") is not None
    assert hit(clomipramine, "OCD-CLOMIPRAMINE-LATER") is None


def test_ocd_after_one_adequate_failure_promotes_switch_and_clomipramine():
    r = recommend(
        diagnosis="ocd",
        previous_drug_responses=[
            {"drug": "Sertraline", "response": "none", "adequate_trial": True}
        ],
    )
    assert hit(item_for(r, "Fluoxetine"), "OCD-SECOND-SSRI") is not None
    assert hit(item_for(r, "Clomipramine"), "OCD-CLOMIPRAMINE-LATER") is not None


def test_ocd_after_two_adequate_failures_allows_antipsychotic_augmentation():
    r = recommend(
        diagnosis="ocd",
        previous_drug_responses=[
            {"drug": "Sertraline", "response": "none", "adequate_trial": True},
            {"drug": "Fluoxetine", "response": "none", "adequate_trial": True},
        ],
    )
    assert hit(item_for(r, "Aripiprazole"), "OCD-ANTIPSYCHOTIC-AUGMENT") is not None
    assert hit(item_for(r, "Risperidone"), "OCD-ANTIPSYCHOTIC-TRIAL") is not None


def test_ocd_experimental_options_hidden_until_three_adequate_failures():
    first = recommend(diagnosis="ocd")
    assert item_for(first, "Memantine") is None
    resistant = recommend(
        diagnosis="ocd",
        previous_drug_responses=[
            {"drug": "Sertraline", "response": "none", "adequate_trial": True},
            {"drug": "Fluoxetine", "response": "none", "adequate_trial": True},
            {"drug": "Clomipramine", "response": "none", "adequate_trial": True},
        ],
    )
    assert hit(item_for(resistant, "Memantine"), "OCD-EXPERIMENTAL-WEAK") is not None


def test_gad_sequence_and_benzodiazepine_safety():
    first = recommend(diagnosis="generalized_anxiety_disorder")
    assert hit(item_for(first, "Sertraline"), "GAD-FIRST-SERTRALINE") is not None
    with_substance_use = recommend(
        diagnosis="generalized_anxiety_disorder", substance_use=["alcohol"]
    )
    clonazepam = item_for(with_substance_use, "Clonazepam")
    assert clonazepam.forced_unsuitable
    assert hit(clonazepam, "GAD-BENZO-SUBSTANCE") is not None


def test_social_anxiety_dedicated_sequence_and_cbt():
    first = recommend(diagnosis="social_anxiety_disorder")
    assert hit(item_for(first, "Sertraline"), "SAD-FIRST-SSRI") is not None
    assert any("individual disorder-specific cbt" in n.lower() for n in first.general_notes)
    later = recommend(
        diagnosis="social_anxiety_disorder",
        previous_drug_responses=[
            {"drug": "Sertraline", "response": "none", "adequate_trial": True},
            {"drug": "Venlafaxine XR", "response": "none", "adequate_trial": True},
        ],
    )
    assert hit(item_for(later, "Phenelzine"), "SAD-MAOI-LATER") is not None


def test_ptsd_psychotherapy_note():
    r = recommend(diagnosis="ptsd")
    assert any("trauma-focused" in n.lower() for n in r.general_notes)


def test_ptsd_prazosin_only_promoted_for_nightmares():
    without_nightmares = recommend(diagnosis="ptsd")
    assert hit(item_for(without_nightmares, "Prazosin"), "PTSD-PRAZOSIN-NOT-GLOBAL") is not None
    with_nightmares = recommend(
        diagnosis="ptsd", symptoms={"nightmares": True, "insomnia": True}
    )
    assert hit(item_for(with_nightmares, "Prazosin"), "PTSD-PRAZOSIN-NIGHTMARES") is not None
    assert hit(item_for(with_nightmares, "Trazodone"), "PTSD-TRAZODONE-SLEEP") is not None


def test_maoi_serotonergic_interaction_forces_phenelzine_unsuitable():
    r = recommend(
        diagnosis="social_anxiety_disorder",
        current_medications=["sertraline"],
    )
    phenelzine = item_for(r, "Phenelzine")
    assert phenelzine.forced_unsuitable
    assert hit(phenelzine, "DDI-MAOI-SEROTONERGIC") is not None


# --------------------------------------------------------------------------- #
# 5. ADHD                                                                     #
# --------------------------------------------------------------------------- #

def test_adhd_stimulant_first_line():
    r = recommend(diagnosis="adhd")
    assert hit(item_for(r, "Methylphenidate"), "ADHD-STIMULANT-FIRSTLINE") is not None


def test_adhd_stimulant_cardiac_caution_only_with_cardiac_history():
    with_cardiac = recommend(diagnosis="adhd", comorbidities=["hypertension"])
    assert hit(item_for(with_cardiac, "Methylphenidate"), "ADHD-STIMULANT-CARDIAC") is not None
    without = recommend(diagnosis="adhd")
    assert hit(item_for(without, "Methylphenidate"), "ADHD-STIMULANT-CARDIAC") is None


def test_adhd_stimulant_substance_use_caution():
    r = recommend(diagnosis="adhd", substance_use=["alcohol"])
    assert hit(item_for(r, "Methylphenidate"), "ADHD-STIMULANT-SUD") is not None


def test_adhd_atomoxetine_alternative():
    r = recommend(diagnosis="adhd")
    assert hit(item_for(r, "Atomoxetine"), "ADHD-ATOMOXETINE-ALT") is not None


# --------------------------------------------------------------------------- #
# 6. Substance use disorders                                                  #
# --------------------------------------------------------------------------- #

def test_naltrexone_requires_opioid_free_interval():
    r = recommend(diagnosis="opioid_use_disorder")
    e = hit(item_for(r, "Naltrexone"), "SUD-NALTREXONE-OPIOID-FREE")
    assert e is not None and e.kind == "caution" and e.delta < 0
    item = item_for(r, "Naltrexone")
    assert any("opioid-free" in i.lower() for i in item.baseline_investigations)


def test_alcohol_use_disorder_options_note():
    r = recommend(diagnosis="alcohol_use_disorder")
    assert any("acamprosate" in n.lower() for n in r.general_notes)


def test_opioid_use_disorder_agonist_note():
    r = recommend(diagnosis="opioid_use_disorder")
    assert any("agonist" in n.lower() for n in r.general_notes)


# --------------------------------------------------------------------------- #
# 7. Pregnancy & lactation psychiatry                                         #
# --------------------------------------------------------------------------- #

def test_valproate_childbearing_potential_downranked():
    # Not currently pregnant, but of childbearing potential -> strong negative delta.
    r = recommend(diagnosis="bipolar_mania", sex=Sex.female, age=30)
    e = hit(item_for(r, "Valproate"), "PREG-VALPROATE")
    assert e is not None and e.delta == -40


def test_valproate_in_pregnancy_flagged_without_double_counting():
    r = recommend(
        diagnosis="bipolar_mania", sex=Sex.female, age=30,
        pregnancy_status=PregnancyStatus.pregnant_second_trimester,
    )
    item = item_for(r, "Valproate")
    # Per-drug "avoid" rule applies the score penalty; the population rule adds a
    # named explanatory caution with delta 0 (no double count).
    assert hit(item, "PREG-AVOID") is not None
    preg_valp = hit(item, "PREG-VALPROATE")
    assert preg_valp is not None and preg_valp.delta == 0


def test_pregnancy_layer_does_not_apply_to_men():
    r = recommend(diagnosis="bipolar_mania", sex=Sex.male, age=40)
    assert hit(item_for(r, "Valproate"), "PREG-VALPROATE") is None


def test_pregnancy_and_lactation_notes():
    preg = recommend(
        diagnosis="major_depressive_disorder", sex=Sex.female, age=30,
        pregnancy_status=PregnancyStatus.pregnant_first_trimester,
    )
    assert any("perinatal" in n.lower() for n in preg.general_notes)
    lact = recommend(
        diagnosis="major_depressive_disorder", sex=Sex.female, age=30,
        pregnancy_status=PregnancyStatus.lactating,
    )
    assert any("lactation" in n.lower() for n in lact.general_notes)


# --------------------------------------------------------------------------- #
# 8. Child & adolescent psychiatry                                            #
# --------------------------------------------------------------------------- #

def test_paediatric_antidepressant_suicidality_warning():
    r = recommend(diagnosis="major_depressive_disorder", age=10)
    e = hit(item_for(r, "Sertraline"), "PED-AD-SUICIDALITY")
    assert e is not None and e.kind == "caution"


def test_paediatric_atomoxetine_suicidality_warning():
    r = recommend(diagnosis="adhd", age=15)
    assert hit(item_for(r, "Atomoxetine"), "PED-ATOMOXETINE-SUICIDALITY") is not None


def test_paediatric_stimulant_growth_monitoring():
    r = recommend(diagnosis="adhd", age=10)
    item = item_for(r, "Methylphenidate")
    assert any("growth" in m.lower() for m in item.monitoring)


def test_child_specialist_note():
    r = recommend(diagnosis="adhd", age=10)
    assert any("child-and-adolescent" in n.lower() or "child/adolescent" in n.lower() for n in r.general_notes)


# --------------------------------------------------------------------------- #
# 9. Geriatric psychiatry                                                     #
# --------------------------------------------------------------------------- #

def test_geriatric_antipsychotic_in_dementia_boxed_warning():
    r = recommend(diagnosis="dementia_related_behavioural_symptoms", age=82, sex=Sex.female)
    e = hit(item_for(r, "Risperidone"), "GERI-ANTIPSYCHOTIC-DEMENTIA")
    assert e is not None and e.delta == -35


def test_geriatric_antipsychotic_general_caution_non_dementia():
    r = recommend(diagnosis="schizophrenia", age=70)
    item = item_for(r, "Risperidone")
    assert hit(item, "GERI-ANTIPSYCHOTIC-ELDERLY") is not None
    assert hit(item, "GERI-ANTIPSYCHOTIC-DEMENTIA") is None


def test_geriatric_sedation_fall_caution():
    r = recommend(diagnosis="schizophrenia", age=70)
    # Olanzapine has high sedation in the knowledge base.
    assert hit(item_for(r, "Olanzapine"), "GERI-SEDATION-FALLS") is not None


def test_geriatric_start_low_note():
    r = recommend(diagnosis="schizophrenia", age=70)
    assert any("start low" in n.lower() for n in r.general_notes)


# --------------------------------------------------------------------------- #
# Gating + registry                                                           #
# --------------------------------------------------------------------------- #

def test_extended_rules_off_suppresses_new_rules():
    # Diagnosis rule suppressed.
    r = recommend(extended=False, diagnosis="major_depressive_disorder")
    assert hit(item_for(r, "Sertraline"), "MDD-SSRI-FIRSTLINE") is None
    # Population rule suppressed.
    r2 = recommend(extended=False, diagnosis="dementia_related_behavioural_symptoms", age=82, sex=Sex.female)
    assert hit(item_for(r2, "Risperidone"), "GERI-ANTIPSYCHOTIC-DEMENTIA") is None


def test_safety_modifiers_registered():
    keys = [m.key for m in all_modifiers()]
    assert keys == [
        "pregnancy_lactation", "renal", "hepatic", "cardiac_qtc", "metabolic",
        "seizure", "elderly", "child_adolescent", "suicide_overdose", "adherence",
        "drug_interaction", "ips_cpg",
    ]


# --------------------------------------------------------------------------- #
# New universal safety-modifier capabilities                                  #
# --------------------------------------------------------------------------- #

def test_cardiac_illness_qt_caution():
    r = recommend(diagnosis="schizophrenia", cardiac_disease=True)
    # Risperidone has moderate QT risk in the knowledge base.
    assert hit(item_for(r, "Risperidone"), "CARDIAC-QT-ILLNESS") is not None


def test_seizure_disorder_clozapine_caution():
    r = recommend(diagnosis="schizophrenia", seizure_disorder=True)
    e = hit(item_for(r, "Clozapine"), "SEIZURE-CLOZAPINE")
    assert e is not None and e.kind == "caution"


def test_interaction_lithium_nsaid_caution():
    r = recommend(diagnosis="bipolar_maintenance", current_medications=["ibuprofen"])
    assert hit(item_for(r, "Lithium"), "DDI-LITHIUM-LEVEL") is not None


def test_interaction_ssri_maoi_forces_unsuitable():
    r = recommend(diagnosis="major_depressive_disorder", current_medications=["phenelzine"])
    item = item_for(r, "Sertraline")
    assert item is not None and item.category == "relatively_unsuitable"
    assert hit(item, "DDI-SEROTONIN-MAOI") is not None


def test_valproate_in_pregnancy_marked_unsuitable():
    r = recommend(
        diagnosis="bipolar_mania", sex=Sex.female, age=30,
        pregnancy_status=PregnancyStatus.pregnant_second_trimester,
    )
    item = item_for(r, "Valproate")
    assert item is not None and item.category == "relatively_unsuitable"


def test_catatonia_red_flag():
    from app.models import SymptomProfile
    r = recommend(diagnosis="schizophrenia", symptoms=SymptomProfile(catatonia=True))
    assert any("catatonia" in f.lower() for f in r.urgent_red_flags)


def test_graded_suicidality_red_flag_and_caution():
    from app.models import Suicidality
    r = recommend(diagnosis="major_depressive_disorder", suicidality=Suicidality.recent_attempt)
    assert any("active suicidality" in f.lower() for f in r.urgent_red_flags)


def test_investigations_done_are_not_re_requested():
    # 'Current medication list...' is normally flagged when none provided; mark it done.
    r = recommend(diagnosis="major_depressive_disorder",
                  investigations_done=["Current medication list for interaction checking"])
    assert all("current medication list" not in m.lower() for m in r.missing_information)


def test_inpatient_pathway_adds_safety_workflow_and_workup():
    r = recommend(
        diagnosis="schizophrenia",
        care_setting="inpatient",
        symptoms={"agitation": True, "aggression_risk": True},
    )
    assert any("de-escalation" in flag.lower() for flag in r.urgent_red_flags)
    assert any("medication reconciliation" in item.lower() for item in r.missing_information)
    assert any("prn" in note.lower() and "total daily dose" in note.lower() for note in r.general_notes)
    assert any("before discharge" in note.lower() for note in r.general_notes)


def test_poor_intake_or_immobility_is_urgent():
    r = recommend(
        diagnosis="major_depressive_disorder",
        care_setting="inpatient",
        symptoms={"poor_oral_intake": True, "immobility": True},
    )
    assert any("poor oral intake" in flag.lower() for flag in r.urgent_red_flags)
