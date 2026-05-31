"""Behaviour-preservation tests for the rule-engine refactor.

These tests prove that the new modular engine in ``app.rules_engine`` produces
recommendations identical to the original monolithic engine (frozen in
``app._legacy_reference``) for every existing output field.

Two comparisons run over a large grid of patient profiles:

* a STRUCTURED core that hits every diagnosis and every major safety branch in
  clean combinations, and
* a fixed-seed RANDOMISED fuzz that mixes all axes together (reproducible).

``rule_trace`` is the one field that legitimately differs (it is new and additive),
so it is excluded from the parity comparison. A separate test asserts the new
engine is deterministic (identical output, including rule_trace, across runs).
"""
from __future__ import annotations

import copy
import itertools
import random
from typing import Any, Dict, Iterator, List

import pytest

from app import rules_engine as new_engine
from app import _legacy_reference as legacy_engine
from app.knowledge_base import load_drugs
from app.models import (
    Diagnosis,
    HepaticStatus,
    LabValues,
    PatientProfile,
    PregnancyStatus,
    PreviousDrugResponse,
    RenalStatus,
    Severity,
    Sex,
)
from app.engine.registry import all_modules, assert_registry_complete

ALL_DIAGNOSES = [d.value for d in Diagnosis]
DRUG_NAMES = [d["name"] for d in load_drugs()]


# --------------------------------------------------------------------------- #
# Comparison helpers                                                          #
# --------------------------------------------------------------------------- #

def _canonical(dump: Dict[str, Any]) -> Dict[str, Any]:
    """Canonicalise a response dump for parity comparison.

    The safety-modifier refactor regroups rules by dimension, so the *order* of an
    item's reasons/cautions/investigations/monitoring lists can differ even though the
    content, score, and category are identical. We therefore compare those per-item
    lists as multisets (sorted), and drop ``rule_trace`` (new + additive). Scores,
    categories, drug order across buckets, and all patient-level fields are still
    compared exactly.
    """
    out = copy.deepcopy(dump)
    for bucket in ("most_suitable", "use_with_caution", "relatively_unsuitable"):
        for item in out.get(bucket, []):
            item.pop("rule_trace", None)
            for field in ("reasons", "cautions", "baseline_investigations", "monitoring", "references"):
                if isinstance(item.get(field), list):
                    item[field] = sorted(item[field])
    return out


def assert_parity(profile: PatientProfile) -> None:
    # The parity guarantee is about the *mechanical* refactor: with the extended
    # clinician rule set OFF, the modular engine must reproduce the original engine's
    # scores, categories, and field content. (With extended rules ON the output
    # deliberately differs — see test_extended_rules_change_output.)
    legacy = legacy_engine.generate_recommendations(profile).model_dump()
    new = new_engine.generate_recommendations(profile, extended_rules=False).model_dump()
    assert _canonical(legacy) == _canonical(new), (
        f"Parity mismatch for profile: {profile.model_dump()}"
    )


# --------------------------------------------------------------------------- #
# Profile generation                                                          #
# --------------------------------------------------------------------------- #

AGES = [8, 15, 35, 72]  # one per age group: child, adolescent, adult, elderly

# (height_cm, weight_kg) -> BMI ~ none / normal / obese
BODY = [(None, None), (170.0, 65.0), (160.0, 90.0)]

PREFERENCE_SETS = [
    [],
    ["avoid_sedation"],
    ["avoid_weight_gain"],
    ["avoid_sedation", "avoid_weight_gain"],
]

PREV_RESPONSE_SETS: List[List[PreviousDrugResponse]] = [
    [],
    [PreviousDrugResponse(drug="Sertraline", response="good")],
    [PreviousDrugResponse(drug="Lithium", response="partial")],
    [PreviousDrugResponse(drug="Risperidone", response="none")],
    [PreviousDrugResponse(
        drug="Olanzapine", response="intolerable", adverse_effects=["weight gain", "sedation"]
    )],
    [PreviousDrugResponse(
        drug="Quetiapine", response="good", adverse_effects=["dry mouth"]
    )],
]


def structured_profiles() -> Iterator[PatientProfile]:
    """Clean combinations that guarantee every diagnosis + major branch is hit."""
    # Core: every diagnosis x every age group x clean vs obese body x sex.
    for diagnosis, age, (h, w), sex in itertools.product(
        ALL_DIAGNOSES, AGES, BODY, [Sex.male, Sex.female]
    ):
        yield PatientProfile(
            age=age, sex=sex, height_cm=h, weight_kg=w, diagnosis=diagnosis
        )

    # Safety branches, exercised on a representative diagnosis set.
    safety_dx = [
        "major_depressive_disorder",
        "bipolar_mania",
        "bipolar_depression",
        "bipolar_maintenance",
        "schizophrenia",
        "adhd",
    ]
    for diagnosis in safety_dx:
        # pregnancy / lactation
        for preg in [
            PregnancyStatus.pregnant_second_trimester,
            PregnancyStatus.pregnant_first_trimester,
            PregnancyStatus.lactating,
            PregnancyStatus.planning_pregnancy,
        ]:
            yield PatientProfile(
                age=30, sex=Sex.female, pregnancy_status=preg, diagnosis=diagnosis
            )
        # renal / hepatic impairment
        yield PatientProfile(
            age=40, sex=Sex.male, renal_status=RenalStatus.moderate_impairment,
            diagnosis=diagnosis,
        )
        yield PatientProfile(
            age=40, sex=Sex.male, renal_status=RenalStatus.severe_impairment,
            diagnosis=diagnosis, labs=LabValues(egfr=25.0),
        )
        yield PatientProfile(
            age=40, sex=Sex.male, hepatic_status=HepaticStatus.moderate_impairment,
            diagnosis=diagnosis,
        )
        # QTc tiers
        for qtc in [460.0, 475.0, 505.0]:
            yield PatientProfile(
                age=50, sex=Sex.male, diagnosis=diagnosis, labs=LabValues(qtc_ms=qtc)
            )
        # metabolic comorbidity + obese
        yield PatientProfile(
            age=55, sex=Sex.male, height_cm=160.0, weight_kg=95.0,
            comorbidities=["diabetes", "dyslipidemia"], diagnosis=diagnosis,
        )
        # preferences
        for prefs in PREFERENCE_SETS:
            yield PatientProfile(
                age=35, sex=Sex.male, height_cm=170.0, weight_kg=80.0,
                preferences=prefs, diagnosis=diagnosis,
            )
        # adherence / LAI
        yield PatientProfile(
            age=35, sex=Sex.male, non_adherence_risk=True, diagnosis=diagnosis
        )
        # previous responses (incl. adverse effects)
        for prev in PREV_RESPONSE_SETS:
            yield PatientProfile(
                age=35, sex=Sex.male, previous_drug_responses=prev, diagnosis=diagnosis
            )
        # suicide risk + emergency severity
        yield PatientProfile(
            age=35, sex=Sex.male, suicide_risk=True, severity=Severity.emergency,
            diagnosis=diagnosis,
        )

    # Bipolar lithium family-history boost (all three phases).
    for diagnosis in ["bipolar_mania", "bipolar_depression", "bipolar_maintenance"]:
        yield PatientProfile(
            age=40, sex=Sex.male, family_history=["good lithium response"],
            diagnosis=diagnosis,
        )
        # with TSH present vs absent (exercises bipolar extra_missing_info)
        yield PatientProfile(
            age=40, sex=Sex.male, diagnosis=diagnosis, labs=LabValues(tsh=2.1)
        )


def random_profiles(n: int, seed: int = 1729) -> Iterator[PatientProfile]:
    """Fixed-seed randomised profiles mixing all axes (reproducible)."""
    rng = random.Random(seed)
    comorbidity_pool = [
        [], ["diabetes"], ["obesity"], ["dyslipidemia"],
        ["metabolic syndrome"], ["hypertension"], ["diabetes", "obesity"],
    ]
    family_pool = [
        [], ["good lithium response"], ["lithium responder"],
        ["depression"], ["schizophrenia in sibling"],
    ]
    pref_pool = ["avoid_sedation", "avoid_weight_gain", "avoid_sexual_side_effects", "low_cost"]
    response_pool = ["good", "partial", "none", "intolerable", "unknown"]
    ae_pool = ["weight gain", "sedation", "tremor", "nausea", "akathisia"]

    for _ in range(n):
        sex = rng.choice(list(Sex))
        has_body = rng.random() < 0.7
        height = round(rng.uniform(150, 190), 1) if has_body else None
        weight = round(rng.uniform(45, 110), 1) if has_body else None

        n_prev = rng.choice([0, 0, 1, 1, 2])
        prev: List[PreviousDrugResponse] = []
        for _i in range(n_prev):
            prev.append(PreviousDrugResponse(
                drug=rng.choice(DRUG_NAMES),
                response=rng.choice(response_pool),
                adverse_effects=(
                    rng.sample(ae_pool, rng.randint(1, 2)) if rng.random() < 0.4 else []
                ),
            ))

        labs = LabValues(
            egfr=rng.choice([None, 20.0, 45.0, 55.0, 80.0, 120.0]),
            alt=rng.choice([None, 30.0, 90.0]),
            ast=rng.choice([None, 25.0, 80.0]),
            qtc_ms=rng.choice([None, 420.0, 460.0, 475.0, 500.0, 510.0]),
            tsh=rng.choice([None, 1.5, 4.0]),
        )

        prefs = [p for p in pref_pool if rng.random() < 0.3]

        yield PatientProfile(
            age=rng.randint(5, 90),
            sex=sex,
            height_cm=height,
            weight_kg=weight,
            pregnancy_status=rng.choice(list(PregnancyStatus)),
            renal_status=rng.choice(list(RenalStatus)),
            hepatic_status=rng.choice(list(HepaticStatus)),
            diagnosis=rng.choice(ALL_DIAGNOSES),
            severity=rng.choice(list(Severity)),
            family_history=rng.choice(family_pool),
            comorbidities=rng.choice(comorbidity_pool),
            current_medications=rng.choice([[], ["metformin"], ["aspirin", "ramipril"]]),
            previous_drug_responses=prev,
            labs=labs,
            preferences=prefs,
            suicide_risk=rng.random() < 0.25,
            non_adherence_risk=rng.random() < 0.25,
        )


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #

def test_registry_is_complete():
    assert_registry_complete()  # raises if enum and modules disagree
    assert set(all_modules()) == set(ALL_DIAGNOSES)
    assert len(all_modules()) == 14


@pytest.mark.parametrize("profile", list(structured_profiles()))
def test_parity_structured(profile):
    assert_parity(profile)


def test_parity_random_fuzz():
    for profile in random_profiles(2000):
        assert_parity(profile)


def test_new_engine_is_deterministic():
    # Same input -> byte-identical output across runs, including rule_trace.
    # Run the FULL engine (extended rules ON, the default the app uses).
    for profile in random_profiles(200, seed=99):
        first = new_engine.generate_recommendations(profile).model_dump()
        second = new_engine.generate_recommendations(profile).model_dump()
        assert first == second


def test_extended_rules_change_output():
    # Sanity check that the extended rule set actually does something: for at least
    # some profiles, ON must differ from OFF (and OFF equals legacy, per assert_parity).
    differed = 0
    for profile in random_profiles(300, seed=7):
        off = new_engine.generate_recommendations(profile, extended_rules=False).model_dump()
        on = new_engine.generate_recommendations(profile, extended_rules=True).model_dump()
        if off != on:
            differed += 1
    assert differed > 0, "extended rules never changed output — they may not be wired in"


def test_rule_trace_is_populated_but_does_not_affect_parity():
    # A bipolar patient on an SSRI-eligible pathway still yields traceable rules.
    profile = PatientProfile(
        age=40, sex=Sex.male, diagnosis="major_depressive_disorder",
        labs=LabValues(qtc_ms=475.0),
    )
    resp = new_engine.generate_recommendations(profile)
    all_items = resp.most_suitable + resp.use_with_caution + resp.relatively_unsuitable
    assert all_items, "expected at least one recommendation"
    # Every item must carry a DX-MATCH trace entry at minimum.
    for item in all_items:
        rule_ids = [e.rule_id for e in item.rule_trace]
        assert "DX-MATCH" in rule_ids
