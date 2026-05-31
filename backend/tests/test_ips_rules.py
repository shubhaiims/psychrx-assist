"""Tests for the IPS CPG JSON rule system (engine/ips_rules.py + safety/ips_cpg_safety.py)."""
from __future__ import annotations

import copy

import app.safety  # noqa: F401  (registers the ips_cpg modifier)
from app.engine.ips_rules import (
    _validate_rule,
    ips_reference_entries,
    ips_rule_problems,
    load_ips_rules,
)
from app.engine.presentation import build_report
from app.knowledge_base import load_drugs
from app.models import PatientProfile, PregnancyStatus, Sex
from app.rules_engine import generate_recommendations


def _item(resp, drug):
    for bucket in (resp.most_suitable, resp.use_with_caution, resp.relatively_unsuitable):
        for it in bucket:
            if it.drug.lower() == drug.lower():
                return it
    return None


def _ips_ids(item):
    return [e.rule_id for e in item.rule_trace if e.rule_id.startswith("IPS-")]


# --------------------------------------------------------------------------- #
# loading + validation                                                        #
# --------------------------------------------------------------------------- #

def test_loader_loads_rules_with_no_problems():
    rules = load_ips_rules()
    assert len(rules) > 0
    assert ips_rule_problems() == []
    # every shipped rule carries all required fields after merge
    for r in rules:
        for f in ("rule_id", "diagnosis", "population", "drug_or_drug_class",
                  "recommendation_category", "score_modifier", "explanation_for_clinician",
                  "citation_title", "last_reviewed_by"):
            assert f in r


def test_validate_rule_catches_bad_rules():
    base = load_ips_rules()[0]

    missing = copy.deepcopy(base)
    del missing["drug_or_drug_class"]
    assert any("drug_or_drug_class" in e for e in _validate_rule(missing))

    bad_cat = copy.deepcopy(base)
    bad_cat["recommendation_category"] = "definitely_use_this"
    assert any("recommendation_category" in e for e in _validate_rule(bad_cat))

    bad_pop = copy.deepcopy(base)
    bad_pop["population"] = "martian"
    assert any("population" in e for e in _validate_rule(bad_pop))

    bad_cond = copy.deepcopy(base)
    bad_cond["condition"] = {"unknown_key": 5}
    assert any("condition key" in e for e in _validate_rule(bad_cond))

    bad_flag = copy.deepcopy(base)
    bad_flag["condition"] = {"flags_any": ["not_a_flag"]}
    assert any("flag" in e for e in _validate_rule(bad_flag))


# --------------------------------------------------------------------------- #
# matching + application                                                      #
# --------------------------------------------------------------------------- #

def test_known_rule_fires_with_citation():
    r = generate_recommendations(PatientProfile(age=30, sex=Sex.male, diagnosis="major_depressive_disorder"))
    sertraline = _item(r, "Sertraline")
    assert "IPS-MDD-SSRI-FIRSTLINE" in _ips_ids(sertraline)
    hit = next(e for e in sertraline.rule_trace if e.rule_id == "IPS-MDD-SSRI-FIRSTLINE")
    assert hit.references and "Indian Psychiatric Society" in hit.references[0]


def test_population_gating_child_vs_adult():
    child = generate_recommendations(PatientProfile(age=10, sex=Sex.male, diagnosis="major_depressive_disorder"))
    adult = generate_recommendations(PatientProfile(age=30, sex=Sex.male, diagnosis="major_depressive_disorder"))
    assert "IPS-CAP-AD-SUICIDALITY" in _ips_ids(_item(child, "Sertraline"))
    assert "IPS-CAP-AD-SUICIDALITY" not in _ips_ids(_item(adult, "Sertraline"))


def test_condition_drug_property_gating_qt_cardiac():
    # IPS-CL-QT-CARDIAC must fire only for moderate/high-QT drugs in a cardiac patient.
    qt = {d["name"]: d.get("qt_risk") for d in load_drugs()}
    r = generate_recommendations(PatientProfile(age=40, sex=Sex.male, diagnosis="schizophrenia", cardiac_disease=True))
    seen_true = seen_false = False
    for bucket in (r.most_suitable, r.use_with_caution, r.relatively_unsuitable):
        for it in bucket:
            fired = "IPS-CL-QT-CARDIAC" in _ips_ids(it)
            assert fired == (qt.get(it.drug) in ("moderate", "high"))
            seen_true = seen_true or fired
            seen_false = seen_false or not fired
    assert seen_true and seen_false  # rule both fired and was withheld -> real gating


def test_absolute_contraindication_forces_unsuitable():
    r = generate_recommendations(PatientProfile(
        age=30, sex=Sex.female, diagnosis="bipolar_mania",
        pregnancy_status=PregnancyStatus.pregnant_second_trimester))
    valp = _item(r, "Valproate")
    assert valp.forced_unsuitable is True
    assert valp.category == "relatively_unsuitable"  # internal category for forced items
    assert "IPS-PREG-VALPROATE-AVOID" in _ips_ids(valp)


def test_rule_adds_investigations_and_monitoring():
    r = generate_recommendations(PatientProfile(age=30, sex=Sex.male, diagnosis="major_depressive_disorder"))
    sertraline = _item(r, "Sertraline")
    assert any("baseline physical-health screen" in i.lower() for i in sertraline.baseline_investigations)

    r2 = generate_recommendations(PatientProfile(age=35, sex=Sex.male, diagnosis="bipolar_mania"))
    lithium = _item(r2, "Lithium")
    assert "IPS-BIP-LITHIUM-FIRSTLINE" in _ips_ids(lithium)
    assert any("thyroid" in m.lower() for m in lithium.monitoring)


def test_extended_rules_off_disables_ips():
    off = generate_recommendations(
        PatientProfile(age=30, sex=Sex.male, diagnosis="major_depressive_disorder"),
        extended_rules=False)
    assert _ips_ids(_item(off, "Sertraline")) == []


# --------------------------------------------------------------------------- #
# presentation + references                                                   #
# --------------------------------------------------------------------------- #

def test_ips_reference_entries_tagged_ips_cpg():
    entries = ips_reference_entries()
    assert "IPS-MDD-SSRI-FIRSTLINE" in entries
    e = entries["IPS-MDD-SSRI-FIRSTLINE"]
    assert e["source_type"] == "ips_cpg"
    assert e["status"] == "placeholder"  # shipped rules are unreviewed placeholders


def test_report_guideline_references_include_ips():
    report = build_report(PatientProfile(age=30, sex=Sex.male, diagnosis="major_depressive_disorder"))
    ips_refs = [g for g in report.guideline_references if g.rule_id.startswith("IPS-")]
    assert ips_refs
    assert all(g.source_type == "ips_cpg" and g.citation for g in ips_refs)
    # and the per-drug card surfaces the IPS citation too
    sertraline = next(o for b in (report.most_suitable_options, report.use_with_caution,
                                  report.relatively_unsuitable, report.contraindicated_or_avoid)
                      for o in b if o.drug_name == "Sertraline")
    assert any("Indian Psychiatric Society" in c for c in sertraline.guideline_reference_placeholder)
