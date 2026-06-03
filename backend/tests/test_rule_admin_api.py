"""Tests for the admin rule editor API (CRUD over the JSON rule store).

Each test runs against an isolated *copy* of the rule files in a temp dir, so the shipped
JSON is never mutated.
"""
from __future__ import annotations

import glob
import os
import shutil

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app.engine import ips_rules
    for f in glob.glob(os.path.join(ips_rules.IPS_RULES_DIR, "*.json")):
        shutil.copy(f, tmp_path / os.path.basename(f))
    monkeypatch.setattr(ips_rules, "IPS_RULES_DIR", str(tmp_path))
    ips_rules.reload()
    from app.main import app
    yield TestClient(app)
    ips_rules.reload()  # monkeypatch restores the dir; clear the cache for other tests


def _new_rule(**over):
    rule = {
        "rule_id": "IPS-TEST-NEWRULE",
        "guideline_name": "Test guideline",
        "guideline_section": "Test section",
        "diagnosis": "major_depressive_disorder",
        "population": "adult",
        "condition": None,
        "drug_or_drug_class": "SSRI",
        "recommendation_category": "first_line",
        "score_modifier": 5,
        "explanation_for_clinician": "Test explanation.",
        "missing_investigations": [],
        "monitoring_required": [],
        "contraindication_level": "none",
        "citation_title": "Test title",
        "citation_page": "1",
        "citation_url": "https://example.org",
        "citation_year": 2024,
        "last_reviewed_by": "Dr Test",
        "last_reviewed_date": "2024-01-01",
        "enabled": True,
    }
    rule.update(over)
    return rule


# --------------------------------------------------------------------------- #
# read + filter                                                               #
# --------------------------------------------------------------------------- #

def test_list_rules(client):
    body = client.get("/rules").json()
    assert body["problems"] == []
    assert len(body["rules"]) >= 25
    sample = body["rules"][0]
    assert "_source_file" in sample and "enabled" in sample
    # the IPS health endpoint must still resolve (not shadowed by /rules/{rule_id})
    assert client.get("/rules/ips").json()["ok"] is True


def test_filter_by_diagnosis(client):
    ids = [r["rule_id"] for r in client.get("/rules", params={"diagnosis": "ocd"}).json()["rules"]]
    assert "IPS-OCD-SSRI-FIRSTLINE" in ids
    assert "IPS-BIP-LITHIUM-FIRSTLINE" not in ids


def test_filter_by_population(client):
    ids = [r["rule_id"] for r in client.get("/rules", params={"population": "elderly"}).json()["rules"]]
    assert "IPS-GER-ANTIPSYCH-DEMENTIA" in ids
    assert "IPS-MDD-SSRI-FIRSTLINE" not in ids


def test_get_rule_and_404(client):
    r = client.get("/rules/IPS-MDD-SSRI-FIRSTLINE")
    assert r.status_code == 200
    assert r.json()["rule_id"] == "IPS-MDD-SSRI-FIRSTLINE"
    assert client.get("/rules/NOPE").status_code == 404


# --------------------------------------------------------------------------- #
# create                                                                      #
# --------------------------------------------------------------------------- #

def test_create_rule(client):
    r = client.post("/rules", json=_new_rule())
    assert r.status_code == 201
    created = r.json()
    assert created["rule_id"] == "IPS-TEST-NEWRULE"
    assert created["_source_file"] == "custom_rules.json"
    # readable back, and actually applied by the engine
    assert client.get("/rules/IPS-TEST-NEWRULE").status_code == 200
    raw = client.post("/recommend/raw", json={"age": 30, "sex": "male", "diagnosis": "major_depressive_disorder"}).json()
    fired = {e["rule_id"] for it in raw["most_suitable"] + raw["use_with_caution"] for e in it["rule_trace"]}
    assert "IPS-TEST-NEWRULE" in fired


def test_create_duplicate_conflict(client):
    assert client.post("/rules", json=_new_rule(rule_id="IPS-MDD-SSRI-FIRSTLINE")).status_code == 409


def test_create_invalid_unprocessable(client):
    bad = _new_rule(recommendation_category="use_this_one")
    r = client.post("/rules", json=bad)
    assert r.status_code == 422
    assert any("recommendation_category" in str(p) for p in r.json()["detail"])

    bad_cond = _new_rule(rule_id="IPS-TEST-BADCOND", condition={"unknown_key": 1})
    r2 = client.post("/rules", json=bad_cond)
    assert r2.status_code == 422


def test_create_rule_requires_admin_token_when_configured(client, monkeypatch):
    monkeypatch.setenv("ADMIN_AUTH_TOKEN", "test-secret")

    assert client.post("/rules", json=_new_rule()).status_code == 401

    r = client.post("/rules", json=_new_rule(), headers={"X-Admin-Token": "test-secret"})
    assert r.status_code == 201


# --------------------------------------------------------------------------- #
# update                                                                      #
# --------------------------------------------------------------------------- #

def test_update_rule(client):
    rule = client.get("/rules/IPS-MDD-SSRI-FIRSTLINE").json()
    rule["score_modifier"] = 3
    rule["explanation_for_clinician"] = "Edited summary."
    rule["last_reviewed_by"] = "Dr Reviewer"
    rule["last_reviewed_date"] = "2025-02-02"
    r = client.put("/rules/IPS-MDD-SSRI-FIRSTLINE", json=rule)
    assert r.status_code == 200
    after = client.get("/rules/IPS-MDD-SSRI-FIRSTLINE").json()
    assert after["score_modifier"] == 3
    assert after["explanation_for_clinician"] == "Edited summary."
    assert after["last_reviewed_by"] == "Dr Reviewer"


def test_update_not_found(client):
    assert client.put("/rules/NOPE", json=_new_rule(rule_id="NOPE")).status_code == 404


# --------------------------------------------------------------------------- #
# disable / enable                                                            #
# --------------------------------------------------------------------------- #

def _ssri_fires(client) -> bool:
    raw = client.post("/recommend/raw", json={"age": 30, "sex": "male", "diagnosis": "major_depressive_disorder"}).json()
    for it in raw["most_suitable"] + raw["use_with_caution"] + raw["relatively_unsuitable"]:
        if it["drug"] == "Sertraline":
            return "IPS-MDD-SSRI-FIRSTLINE" in {e["rule_id"] for e in it["rule_trace"]}
    return False


def test_disable_then_enable(client):
    assert _ssri_fires(client) is True

    d = client.patch("/rules/IPS-MDD-SSRI-FIRSTLINE/disable")
    assert d.status_code == 200 and d.json()["enabled"] is False
    assert _ssri_fires(client) is False  # disabled rule no longer applied

    e = client.patch("/rules/IPS-MDD-SSRI-FIRSTLINE/enable")
    assert e.status_code == 200 and e.json()["enabled"] is True
    assert _ssri_fires(client) is True


def test_disable_not_found(client):
    assert client.patch("/rules/NOPE/disable").status_code == 404
