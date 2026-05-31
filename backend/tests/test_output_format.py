"""Tests for the rich, frontend-ready report (engine/presentation.build_report)."""
from __future__ import annotations

from app.engine.presentation import build_report
from app.models import PatientProfile, PregnancyStatus, RecommendationReport, Sex

EXPECTED_SECTIONS = [
    "case_summary", "red_flags", "most_suitable_options", "use_with_caution",
    "relatively_unsuitable", "contraindicated_or_avoid", "missing_investigations",
    "required_monitoring", "non_pharmacological_recommendations",
    "guideline_references", "clinician_override_note", "disclaimer",
]

DRUG_FIELDS = [
    "drug_name", "drug_class", "suitability_score", "category", "reason_for_category",
    "why_suitable", "why_caution", "why_unsuitable", "dose_note_placeholder",
    "required_baseline_tests", "monitoring_required", "important_side_effects",
    "interaction_warnings", "pregnancy_lactation_note", "renal_note", "hepatic_note",
    "elderly_note", "child_adolescent_note", "guideline_reference_placeholder",
]


def _report(**kw) -> RecommendationReport:
    kw.setdefault("age", 35)
    kw.setdefault("sex", Sex.male)
    return build_report(PatientProfile(**kw))


def _all_options(report: RecommendationReport):
    return (report.most_suitable_options + report.use_with_caution
            + report.relatively_unsuitable + report.contraindicated_or_avoid)


def test_report_has_all_sections_in_order():
    report = _report(diagnosis="schizophrenia")
    dump = report.model_dump()
    assert list(dump.keys()) == EXPECTED_SECTIONS


def test_every_drug_option_has_all_fields():
    report = _report(diagnosis="schizophrenia", non_adherence_risk=True)
    options = _all_options(report)
    assert options
    for opt in options:
        d = opt.model_dump()
        for field in DRUG_FIELDS:
            assert field in d, f"missing {field}"
        assert d["category"] in (
            "most_suitable", "use_with_caution", "relatively_unsuitable", "contraindicated_or_avoid"
        )
        assert d["dose_note_placeholder"]                 # always present
        assert d["important_side_effects"]                # always at least the placeholder
        assert d["guideline_reference_placeholder"]       # always at least the placeholder


def test_most_suitable_have_no_unsuitable_text():
    report = _report(diagnosis="schizophrenia", non_adherence_risk=True)
    for opt in report.most_suitable_options:
        assert opt.why_unsuitable == []
        assert opt.category == "most_suitable"


def test_contraindicated_bucket_gets_forced_items():
    # Valproate in pregnancy is forced unsuitable -> contraindicated_or_avoid bucket.
    report = _report(diagnosis="bipolar_mania", sex=Sex.female, age=30,
                     pregnancy_status=PregnancyStatus.pregnant_second_trimester)
    names = [o.drug_name for o in report.contraindicated_or_avoid]
    assert "Valproate" in names
    valp = next(o for o in report.contraindicated_or_avoid if o.drug_name == "Valproate")
    assert valp.category == "contraindicated_or_avoid"
    assert valp.why_unsuitable  # explanation present
    # And it must NOT also appear under relatively_unsuitable.
    assert "Valproate" not in [o.drug_name for o in report.relatively_unsuitable]


def test_interaction_warning_surfaces_on_drug():
    report = _report(diagnosis="bipolar_maintenance", current_medications=["ibuprofen"])
    li = next(o for o in _all_options(report) if o.drug_name == "Lithium")
    assert any("lithium" in w.lower() for w in li.interaction_warnings)


def test_non_pharmacological_and_guideline_sections_populated():
    report = _report(diagnosis="ptsd")
    assert report.non_pharmacological_recommendations
    assert any("trauma-focused" in n.lower() for n in report.non_pharmacological_recommendations)
    assert report.guideline_references
    for g in report.guideline_references:
        assert g.rule_id and g.citation and g.status


def test_case_summary_and_static_notes():
    report = _report(diagnosis="schizophrenia")
    assert report.case_summary.diagnosis == "schizophrenia"
    assert report.case_summary.diagnosis_display
    assert report.case_summary.summary_text
    assert report.clinician_override_note
    assert report.disclaimer


def test_pregnancy_renal_hepatic_notes_always_present():
    report = _report(diagnosis="schizophrenia")
    for opt in _all_options(report):
        assert opt.pregnancy_lactation_note.startswith("Pregnancy:")
        assert opt.renal_note.startswith("Renal:")
        assert opt.hepatic_note.startswith("Hepatic:")
