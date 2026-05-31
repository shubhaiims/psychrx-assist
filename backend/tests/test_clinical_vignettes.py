"""Clinical vignettes — end-to-end sanity checks for the recommendation report.

Thirty representative psychiatry cases (plus one extra that exercises the
contraindicated/avoid bucket). Each vignette asserts the clinically-meaningful parts of
the report: red flags, missing investigations, drugs flagged unsuitable, drugs flagged as
caution, and the most-suitable options. Assertions target invariants (a drug lands in a
bucket, a keyword appears in a flag) rather than exact lists/scores, so they stay robust
as rules evolve — while still failing if the clinical behaviour regresses.

These run with the full (extended) rule set, the same as the live API.
"""
from __future__ import annotations

import pytest

from app.engine.presentation import build_report
from app.models import PatientProfile

# --------------------------------------------------------------------------- #
# vignette definitions (plain dicts; pydantic coerces nested dicts/enums)     #
# --------------------------------------------------------------------------- #
VIGNETTES = {
    "adult_depression": dict(age=30, sex="female", diagnosis="major_depressive_disorder",
        severity="moderate", symptoms={"depressive": True}),
    "depression_suicidality": dict(age=35, sex="male", diagnosis="major_depressive_disorder",
        severity="severe", suicide_risk=True, suicidality="recent_attempt", symptoms={"depressive": True}),
    "depression_pregnancy": dict(age=30, sex="female", diagnosis="major_depressive_disorder",
        severity="moderate", pregnancy_status="pregnant_first_trimester", symptoms={"depressive": True}),
    "depression_hepatic": dict(age=45, sex="male", diagnosis="major_depressive_disorder",
        severity="moderate", hepatic_status="severe_impairment"),
    "bipolar_mania": dict(age=28, sex="male", diagnosis="bipolar_mania", severity="severe",
        symptoms={"manic": True}),
    "bipolar_depression": dict(age=32, sex="female", diagnosis="bipolar_depression",
        severity="moderate", symptoms={"depressive": True}),
    "bipolar_renal": dict(age=40, sex="male", diagnosis="bipolar_maintenance",
        renal_status="severe_impairment", labs={"egfr": 22}),
    "first_episode_psychosis": dict(age=22, sex="male", diagnosis="acute_psychosis",
        severity="severe", diagnosis_subtype="first_episode", symptoms={"psychotic": True}),
    "schizophrenia_poor_adherence": dict(age=30, sex="male", diagnosis="schizophrenia",
        severity="severe", non_adherence_risk=True, symptoms={"psychotic": True}),
    "treatment_resistant_schizophrenia": dict(age=35, sex="male", diagnosis="schizophrenia",
        severity="severe", diagnosis_subtype="treatment_resistant",
        previous_drug_responses=[
            {"drug": "Risperidone", "response": "none", "adequate_trial": True},
            {"drug": "Olanzapine", "response": "none", "adequate_trial": True}]),
    "psychosis_diabetes_obesity": dict(age=40, sex="male", diagnosis="schizophrenia",
        severity="moderate", height_cm=170, weight_kg=104,
        comorbidities=["type 2 diabetes", "obesity"], labs={"hba1c": 8.1, "fasting_glucose": 150},
        symptoms={"psychotic": True}),
    "ocd_adult": dict(age=28, sex="female", diagnosis="ocd", severity="moderate", symptoms={"ocd": True}),
    "ocd_adolescent": dict(age=15, sex="male", diagnosis="ocd", severity="moderate", symptoms={"ocd": True}),
    "gad": dict(age=30, sex="female", diagnosis="generalized_anxiety_disorder", severity="moderate",
        symptoms={"anxiety": True}),
    "panic_disorder": dict(age=27, sex="female", diagnosis="panic_disorder", severity="moderate",
        symptoms={"anxiety": True}),
    "adhd_child": dict(age=9, sex="male", diagnosis="adhd", severity="moderate"),
    "adhd_adult": dict(age=30, sex="male", diagnosis="adhd", severity="moderate"),
    "aud_liver_disease": dict(age=50, sex="male", diagnosis="alcohol_use_disorder",
        hepatic_status="moderate_impairment", comorbidities=["alcoholic liver disease"],
        substance_use=["alcohol"]),
    "opioid_use_disorder": dict(age=35, sex="male", diagnosis="opioid_use_disorder",
        substance_use=["opioids"]),
    "elderly_depression": dict(age=75, sex="female", diagnosis="major_depressive_disorder",
        severity="moderate"),
    "elderly_delirium_risk": dict(age=82, sex="male", diagnosis="acute_psychosis", severity="moderate",
        comorbidities=["delirium risk", "frailty"], symptoms={"psychotic": True}),
    "dementia_behavioural": dict(age=80, sex="female", diagnosis="dementia_related_behavioural_symptoms",
        severity="moderate", symptoms={"aggression_risk": True}),
    "prolonged_qtc": dict(age=50, sex="male", diagnosis="schizophrenia", severity="moderate",
        labs={"qtc_ms": 500}, symptoms={"psychotic": True}),
    "seizure_disorder": dict(age=35, sex="male", diagnosis="schizophrenia", severity="severe",
        seizure_disorder=True, symptoms={"psychotic": True}),
    "polypharmacy": dict(age=60, sex="male", diagnosis="bipolar_maintenance",
        current_medications=["ibuprofen", "hydrochlorothiazide", "carbamazepine"]),
    "lactation": dict(age=30, sex="female", diagnosis="major_depressive_disorder", severity="moderate",
        pregnancy_status="lactating", lactation_status=True),
    "adolescent_suicidality": dict(age=16, sex="male", diagnosis="major_depressive_disorder",
        severity="severe", suicide_risk=True, suicidality="ideation_with_plan", symptoms={"depressive": True}),
    "past_severe_adr": dict(age=40, sex="female", diagnosis="schizophrenia", severity="moderate",
        previous_drug_responses=[{"drug": "Risperidone", "response": "intolerable",
            "adverse_effects": ["severe dystonia"], "adequate_trial": True}], symptoms={"psychotic": True}),
    "family_history_bipolar": dict(age=26, sex="female", diagnosis="bipolar_maintenance",
        family_history=["bipolar disorder"], family_history_drug_response=["good lithium response in mother"]),
    "non_adherence": dict(age=33, sex="male", diagnosis="schizophrenia", severity="moderate",
        non_adherence_risk=True, symptoms={"psychotic": True}),
    # --- extra: exercises the contraindicated_or_avoid bucket ---
    "bipolar_mania_pregnancy": dict(age=30, sex="female", diagnosis="bipolar_mania", severity="severe",
        pregnancy_status="pregnant_second_trimester", symptoms={"manic": True}),
}


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #

def report(key: str):
    return build_report(PatientProfile(**VIGNETTES[key]))


def _names(opts):
    return {o.drug_name for o in opts}


def most(r):
    return _names(r.most_suitable_options)


def caution(r):
    return _names(r.use_with_caution)


def unsuitable(r):
    return _names(r.relatively_unsuitable)


def avoid(r):
    return _names(r.contraindicated_or_avoid)


def flagged(r):
    """Drugs flagged unsuitable (relatively unsuitable or contraindicated/avoid)."""
    return unsuitable(r) | avoid(r)


def concern(r):
    """Drugs the report flags with any concern (caution, unsuitable, or avoid)."""
    return caution(r) | unsuitable(r) | avoid(r)


def usable(r):
    return most(r) | caution(r)


def red_text(r):
    return " ".join(r.red_flags).lower()


def missing_text(r):
    return " ".join(r.missing_investigations).lower()


def option(r, drug):
    for bucket in (r.most_suitable_options, r.use_with_caution,
                   r.relatively_unsuitable, r.contraindicated_or_avoid):
        for o in bucket:
            if o.drug_name == drug:
                return o
    return None


# --------------------------------------------------------------------------- #
# structural checks across every vignette                                     #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("key", list(VIGNETTES))
def test_vignette_report_is_well_formed(key):
    r = report(key)
    # all 12 sections exist and the boilerplate is populated
    assert r.case_summary.diagnosis == VIGNETTES[key]["diagnosis"]
    assert r.clinician_override_note and r.disclaimer
    # baseline investigations are always surfaced
    assert r.missing_investigations
    # at least one candidate drug is returned somewhere
    all_names = most(r) | caution(r) | unsuitable(r) | avoid(r)
    assert all_names, "no candidate drugs returned"
    # buckets are mutually exclusive
    buckets = [most(r), caution(r), unsuitable(r), avoid(r)]
    for i in range(len(buckets)):
        for j in range(i + 1, len(buckets)):
            assert not (buckets[i] & buckets[j]), "a drug appears in two buckets"
    # most-suitable options never carry an 'unsuitable' explanation
    for o in r.most_suitable_options:
        assert o.why_unsuitable == []


def test_thirty_plus_vignettes_present():
    assert len(VIGNETTES) >= 30


# --------------------------------------------------------------------------- #
# 1. adult depression                                                         #
# --------------------------------------------------------------------------- #
def test_adult_depression():
    r = report("adult_depression")
    assert r.red_flags == []                                   # no red flags
    assert "pregnancy" in missing_text(r)                      # childbearing -> pregnancy test
    assert {"Sertraline", "Escitalopram", "Fluoxetine"} <= most(r)   # SSRIs first-line
    assert flagged(r) == set()                                 # nothing unsuitable


# 2. depression with suicidality
def test_depression_with_suicidality():
    r = report("depression_suicidality")
    assert "suicid" in red_text(r)                             # red flag detected
    assert most(r)                                             # options still returned
    assert "Sertraline" in most(r)


# 3. depression with pregnancy
def test_depression_with_pregnancy():
    r = report("depression_pregnancy")
    assert "pregnan" in red_text(r)                            # perinatal red flag
    assert "Sertraline" in most(r)                             # better perinatal data -> preferred
    assert "Escitalopram" in concern(r)                        # other SSRIs cautioned


# 4. depression with hepatic impairment
def test_depression_hepatic_impairment():
    r = report("depression_hepatic")
    assert usable(r)                                           # treatment still possible
    assert {"Sertraline", "Escitalopram", "Fluoxetine"} <= concern(r)   # all cautioned in severe hepatic
    assert option(r, "Sertraline").hepatic_note.startswith("Hepatic:")


# 5. bipolar mania
def test_bipolar_mania():
    r = report("bipolar_mania")
    assert "tsh" in missing_text(r)                            # TSH before lithium/mood stabiliser
    assert "Lithium" in most(r)                                # lithium first-line
    assert most(r) & {"Olanzapine", "Risperidone", "Quetiapine"}   # plus an antipsychotic


# 6. bipolar depression
def test_bipolar_depression():
    r = report("bipolar_depression")
    assert "Lamotrigine" in most(r)                            # lamotrigine for depressive pole
    assert not ({"Sertraline", "Escitalopram", "Fluoxetine"} & most(r))  # no AD monotherapy promoted


# 7. bipolar disorder with renal impairment
def test_bipolar_renal_impairment():
    r = report("bipolar_renal")
    assert "Lithium" in flagged(r)                             # lithium unsuitable in severe renal
    assert usable(r)                                           # alternatives remain


# 8. first episode psychosis
def test_first_episode_psychosis():
    r = report("first_episode_psychosis")
    assert most(r)                                             # antipsychotic options returned
    assert "Olanzapine" in most(r) or "Risperidone" in most(r)


# 9. schizophrenia with poor adherence
def test_schizophrenia_poor_adherence():
    r = report("schizophrenia_poor_adherence")
    assert usable(r)
    # a long-acting/adherence rationale surfaces on at least one option
    reasons = " ".join(s for o in r.most_suitable_options for s in o.why_suitable).lower()
    assert "long-acting" in reasons or "adherence" in reasons
    assert "Clozapine" in concern(r)                           # clozapine not first-line


# 10. treatment-resistant schizophrenia
def test_treatment_resistant_schizophrenia():
    r = report("treatment_resistant_schizophrenia")
    clo = option(r, "Clozapine")
    assert clo is not None
    assert any("anc" in m.lower() for m in clo.monitoring_required)   # mandatory ANC monitoring
    assert {"Risperidone", "Olanzapine"} <= concern(r)         # the two failed trials are down-ranked


# 11. psychosis with diabetes / obesity
def test_psychosis_with_diabetes_obesity():
    r = report("psychosis_diabetes_obesity")
    assert "Olanzapine" in flagged(r)                          # high metabolic-risk agent flagged
    assert "metabolic" in " ".join(option(r, "Olanzapine").why_unsuitable).lower()
    assert most(r) & {"Risperidone", "Quetiapine"}             # lower-metabolic options preferred
    assert "weight" not in missing_text(r)                     # height/weight already provided


# 12. OCD adult
def test_ocd_adult():
    r = report("ocd_adult")
    assert {"Sertraline", "Escitalopram", "Fluoxetine"} <= most(r)   # SSRIs first-line for OCD


# 13. OCD child / adolescent
def test_ocd_adolescent():
    r = report("ocd_adolescent")
    assert usable(r)
    assert "Sertraline" in concern(r)                          # under-25 SSRI suicidality caution


# 14. GAD
def test_gad():
    r = report("gad")
    assert "Sertraline" in most(r)                             # SSRI first-line for GAD


# 15. panic disorder
def test_panic_disorder():
    r = report("panic_disorder")
    assert "Sertraline" in most(r)


# 16. ADHD child
def test_adhd_child():
    r = report("adhd_child")
    assert "Methylphenidate" in most(r)                        # stimulant first-line
    mph = option(r, "Methylphenidate")
    assert any("growth" in m.lower() for m in mph.monitoring_required)   # paediatric growth monitoring
    assert any("cardiac" in b.lower() or "bp" in b.lower() for b in mph.required_baseline_tests)


# 17. ADHD adult
def test_adhd_adult():
    r = report("adhd_adult")
    assert "Methylphenidate" in most(r)


# 18. alcohol use disorder with liver disease
def test_aud_liver_disease():
    r = report("aud_liver_disease")
    assert "Naltrexone" in flagged(r)                          # hepatically-handled agent flagged
    assert r.missing_investigations


# 19. opioid use disorder
def test_opioid_use_disorder():
    r = report("opioid_use_disorder")
    nal = option(r, "Naltrexone")
    assert "Naltrexone" in concern(r)                          # caution before detox
    assert any("opioid-free" in b.lower() for b in nal.required_baseline_tests)


# 20. elderly depression
def test_elderly_depression():
    r = report("elderly_depression")
    assert "Sertraline" in most(r)
    assert usable(r)


# 21. elderly delirium risk
def test_elderly_delirium_risk():
    r = report("elderly_delirium_risk")
    assert usable(r)
    assert "Risperidone" in concern(r)                         # elderly antipsychotic caution


# 22. dementia with behavioural symptoms
def test_dementia_behavioural():
    r = report("dementia_behavioural")
    assert any("first-line" in n.lower() for n in r.non_pharmacological_recommendations)  # non-pharm first
    ris = option(r, "Risperidone")
    assert ris is not None
    assert "dementia" in " ".join(ris.why_caution + ris.why_unsuitable).lower()


# 23. patient with prolonged QTc
def test_prolonged_qtc():
    r = report("prolonged_qtc")
    assert "qtc" in red_text(r)                                # QTc red flag
    assert "Olanzapine" in most(r)                             # low-QT option preferred
    assert "Quetiapine" in flagged(r)                          # QT-concern agent flagged


# 24. patient with seizure disorder
def test_seizure_disorder():
    r = report("seizure_disorder")
    assert "Clozapine" in flagged(r)
    assert "seizure" in " ".join(option(r, "Clozapine").why_unsuitable).lower()


# 25. patient with polypharmacy
def test_polypharmacy_interactions():
    r = report("polypharmacy")
    li = option(r, "Lithium")
    assert "Lithium" in concern(r)
    assert li.interaction_warnings and "lithium" in " ".join(li.interaction_warnings).lower()


# 26. patient with lactation
def test_lactation():
    r = report("lactation")
    assert "Sertraline" in usable(r)                           # better infant-safety data
    assert "lactation" in option(r, "Sertraline").pregnancy_lactation_note.lower()
    assert "Fluoxetine" in concern(r)


# 27. adolescent with suicidality
def test_adolescent_suicidality():
    r = report("adolescent_suicidality")
    assert "suicid" in red_text(r)
    assert "Sertraline" in concern(r)                          # cautioned under-25 + suicide risk
    assert usable(r)


# 28. patient with past severe adverse drug reaction
def test_past_severe_adr():
    r = report("past_severe_adr")
    ris = option(r, "Risperidone")
    assert "Risperidone" in concern(r)
    text = " ".join(ris.why_caution).lower()
    assert "adverse" in text or "intolerab" in text or "previous" in text
    assert usable(r)                                           # alternatives available


# 29. patient with family history of bipolar disorder
def test_family_history_bipolar():
    r = report("family_history_bipolar")
    assert "Lithium" in most(r)
    assert "family" in " ".join(option(r, "Lithium").why_suitable).lower()
    assert "Valproate" in flagged(r)                           # childbearing-potential caution


# 30. patient with non-adherence
def test_non_adherence():
    r = report("non_adherence")
    assert usable(r)
    reasons = " ".join(s for o in r.most_suitable_options for s in o.why_suitable).lower()
    assert "long-acting" in reasons or "adherence" in reasons


# 31. (extra) bipolar mania in pregnancy -> contraindicated/avoid bucket
def test_bipolar_mania_pregnancy_avoid_bucket():
    r = report("bipolar_mania_pregnancy")
    assert "pregnan" in red_text(r)
    assert "Valproate" in avoid(r)                             # absolute contraindication -> avoid bucket
    assert option(r, "Valproate").category == "contraindicated_or_avoid"
