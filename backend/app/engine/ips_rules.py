"""IPS CPG (Indian Psychiatric Society Clinical Practice Guidelines) rule system.

Guideline rules are authored as JSON in ``app/rules/ips/*.json`` and loaded here. A
clinician can add or edit rules by editing those JSON files only — no Python changes.
This module does three things:

* **load + validate** every rule file (with clear per-rule error messages), merging any
  file-level defaults into each rule;
* **match** a rule against a (patient context, candidate drug) using a small, documented
  vocabulary for ``diagnosis`` / ``population`` / ``drug_or_drug_class`` / ``condition``; and
* **apply** a matching rule's effect to a ``ScoreCard`` (up-rank / caution /
  mark-unsuitable, plus investigations and monitoring), with the rule's citation
  attached for provenance.

It deliberately holds NO copyrighted guideline text — only clinician-written summaries
(``explanation_for_clinician``) and citation metadata.

The rule schema (per entry) and the supported vocabularies are documented in
``app/rules/ips/README.md``.
"""
from __future__ import annotations

import glob
import json
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from app.engine.context import PatientContext
from app.engine import rule_overrides
from app.engine.scoring import ScoreCard
from app.engine.utils import has_any, normalise

IPS_RULES_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "rules", "ips"))

REQUIRED_FIELDS = [
    "rule_id", "guideline_name", "guideline_section", "diagnosis", "population",
    "condition", "drug_or_drug_class", "recommendation_category", "score_modifier",
    "explanation_for_clinician", "missing_investigations", "monitoring_required",
    "contraindication_level", "citation_title", "citation_page", "citation_url",
    "citation_year", "last_reviewed_by", "last_reviewed_date",
]

# recommendation_category vocabulary -> how it maps onto the ScoreCard
UP_RANK = {"preferred", "first_line", "most_suitable", "relatively_preferred"}
CAUTION = {"use_with_caution", "second_line", "caution", "not_preferred", "relatively_unsuitable"}
AVOID = {"avoid", "contraindicated", "contraindicated_or_avoid"}
NEUTRAL = {"neutral", "informational", "monitoring"}
ALLOWED_CATEGORIES = UP_RANK | CAUTION | AVOID | NEUTRAL
ALLOWED_CONTRA = {"none", "relative", "absolute", ""}

WILDCARD = {"any", "all", "*", ""}

# population token -> predicate(ctx) -> bool
_POPULATION = {
    "adult": lambda c: c.age_group == "adult",
    "child": lambda c: c.age_group == "child",
    "adolescent": lambda c: c.age_group == "adolescent",
    "child_adolescent": lambda c: c.age_group in ("child", "adolescent"),
    "elderly": lambda c: c.age_group == "elderly",
    "geriatric": lambda c: c.age_group == "elderly",
    "pregnant": lambda c: c.pregnant_or_planning,
    "pregnancy": lambda c: c.pregnant_or_planning,
    "lactating": lambda c: c.lactating,
    "lactation": lambda c: c.lactating,
    "childbearing_potential": lambda c: c.childbearing_potential,
    "renal": lambda c: c.renal_impaired,
    "renal_impairment": lambda c: c.renal_impaired,
    "hepatic": lambda c: c.hepatic_impaired,
    "hepatic_impairment": lambda c: c.hepatic_impaired,
    "cardiac": lambda c: c.cardiac_disease,
    "cardiac_illness": lambda c: c.cardiac_disease,
    "seizure": lambda c: c.seizure_disorder,
    "neurological": lambda c: c.seizure_disorder,
    "suicide_risk": lambda c: c.profile.suicide_risk,
    "non_adherence": lambda c: c.profile.non_adherence_risk,
    "poor_adherence": lambda c: c.profile.non_adherence_risk,
}

# boolean flags usable in condition.flags_any / flags_all
_FLAGS = {
    "suicide_risk": lambda c: c.profile.suicide_risk,
    "non_adherence_risk": lambda c: c.profile.non_adherence_risk,
    "cardiac_disease": lambda c: c.cardiac_disease,
    "seizure_disorder": lambda c: c.seizure_disorder,
    "pregnant_or_planning": lambda c: c.pregnant_or_planning,
    "lactating": lambda c: c.lactating,
    "childbearing_potential": lambda c: c.childbearing_potential,
    "renal_impaired": lambda c: c.renal_impaired,
    "hepatic_impaired": lambda c: c.hepatic_impaired,
}

SUPPORTED_CONDITION_KEYS = {
    "description",            # free-text note (not gating; shown to clinician only)
    "severity_in", "diagnosis_subtype_in",
    "qtc_min", "qtc_max", "egfr_min", "egfr_max", "bmi_min", "bmi_max", "age_min", "age_max",
    "comorbidity_any", "current_med_any", "family_history_any",
    "flags_all", "flags_any",
    "drug_qt_risk_in", "drug_metabolic_risk_in", "drug_sedation_in", "drug_overdose_toxicity_in",
}


# --------------------------------------------------------------------------- #
# Loading + validation                                                        #
# --------------------------------------------------------------------------- #

def _as_list(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _validate_rule(rule: Dict[str, Any]) -> List[str]:
    """Return a list of human-readable problems with a rule (empty == valid)."""
    errs: List[str] = []
    for f in REQUIRED_FIELDS:
        if f not in rule:
            errs.append(f"missing required field '{f}'")
    if errs:
        return errs  # don't pile on once fields are missing

    if normalise(rule["recommendation_category"]) not in ALLOWED_CATEGORIES:
        errs.append(f"recommendation_category '{rule['recommendation_category']}' not in {sorted(ALLOWED_CATEGORIES)}")
    if normalise(rule.get("contraindication_level") or "") not in ALLOWED_CONTRA:
        errs.append(f"contraindication_level '{rule['contraindication_level']}' not in {sorted(ALLOWED_CONTRA - {''})}")
    try:
        int(rule.get("score_modifier") or 0)
    except (TypeError, ValueError):
        errs.append("score_modifier must be an integer")
    if not isinstance(rule.get("missing_investigations") or [], list):
        errs.append("missing_investigations must be a list")
    if not isinstance(rule.get("monitoring_required") or [], list):
        errs.append("monitoring_required must be a list")
    if "enabled" in rule and not isinstance(rule["enabled"], bool):
        errs.append("enabled must be a boolean")

    for tok in _as_list(rule["population"]):
        if normalise(tok) not in WILDCARD and normalise(tok) not in _POPULATION:
            errs.append(f"unknown population token '{tok}' (supported: {sorted(_POPULATION)} or 'any')")

    cond = rule.get("condition")
    if cond is not None and not isinstance(cond, (dict, str)):
        errs.append("condition must be an object, a string, or null")
    if isinstance(cond, dict):
        for k in cond:
            if k not in SUPPORTED_CONDITION_KEYS:
                errs.append(f"unknown condition key '{k}' (supported: {sorted(SUPPORTED_CONDITION_KEYS)})")
        for fk in ("flags_all", "flags_any"):
            for flag in cond.get(fk, []) or []:
                if flag not in _FLAGS:
                    errs.append(f"unknown flag '{flag}' in {fk} (supported: {sorted(_FLAGS)})")
    return errs


@lru_cache(maxsize=1)
def _load_raw() -> Tuple[Tuple[Dict[str, Any], ...], Tuple[str, ...]]:
    rules: List[Dict[str, Any]] = []
    problems: List[str] = []
    if not os.path.isdir(IPS_RULES_DIR):
        return tuple(), tuple()
    for path in sorted(glob.glob(os.path.join(IPS_RULES_DIR, "*.json"))):
        base = os.path.basename(path)
        try:
            with open(path) as fh:
                data = json.load(fh)
        except Exception as exc:  # malformed JSON should not crash the API
            problems.append(f"{base}: invalid JSON ({exc})")
            continue
        if isinstance(data, list):
            file_defaults, raw_rules = {}, data
        elif isinstance(data, dict):
            raw_rules = data.get("rules", [])
            file_defaults = {k: v for k, v in data.items() if k != "rules"}
        else:
            problems.append(f"{base}: top level must be a list or an object with 'rules'")
            continue
        for entry in raw_rules:
            if not isinstance(entry, dict):
                problems.append(f"{base}: each rule must be an object")
                continue
            merged = {**file_defaults, **entry}  # rule-level keys override file defaults
            errs = _validate_rule(merged)
            if errs:
                rid = merged.get("rule_id", "?")
                problems.extend(f"{base}[{rid}]: {e}" for e in errs)
                continue
            merged["_source_file"] = base
            merged["enabled"] = bool(merged.get("enabled", True))
            rules.append(merged)

    ordered_ids = [r["rule_id"] for r in rules]
    by_id = {r["rule_id"]: r for r in rules}

    problems.extend(rule_overrides.load_problems())
    for override in rule_overrides.load_overrides():
        rid = override.get("rule_id", "?")
        errs = _validate_rule(override)
        if errs:
            problems.extend(f"database[{rid}]: {e}" for e in errs)
            continue
        merged = dict(override)
        merged["_source_file"] = merged.get("_source_file") or "database"
        merged["enabled"] = bool(merged.get("enabled", True))
        if rid not in by_id:
            ordered_ids.append(rid)
        by_id[rid] = merged

    return tuple(by_id[rid] for rid in ordered_ids), tuple(problems)


def load_ips_rules() -> List[Dict[str, Any]]:
    """All valid IPS rules across the folder (cached). Invalid rules are excluded."""
    return list(_load_raw()[0])


def ips_rule_problems() -> List[str]:
    """Validation problems found while loading (empty == all rules valid)."""
    return list(_load_raw()[1])


def reload() -> None:
    """Clear the cache so newly added/edited JSON files are picked up."""
    _load_raw.cache_clear()
    rule_overrides.reload()


# --------------------------------------------------------------------------- #
# Matching                                                                    #
# --------------------------------------------------------------------------- #

def _match_diagnosis(value, ctx: PatientContext) -> bool:
    toks = [normalise(t) for t in _as_list(value)]
    if any(t in WILDCARD for t in toks):
        return True
    return normalise(ctx.diagnosis) in toks


def _match_population(value, ctx: PatientContext) -> bool:
    toks = [normalise(t) for t in _as_list(value)]
    if not toks or any(t in WILDCARD for t in toks):
        return True
    # list of populations is treated as OR
    return any(_POPULATION.get(t, lambda c: False)(ctx) for t in toks)


def _match_drug(value, drug: dict) -> bool:
    name = drug.get("name", "").strip().lower()
    cls = drug.get("class_name", "").strip().lower()
    for tok in _as_list(value):
        t = normalise(tok)
        if t in WILDCARD:
            return True
        if t == name or t == cls or (t and t in cls):
            return True
    return False


def _match_condition(cond, ctx: PatientContext, drug: dict) -> bool:
    if not cond or isinstance(cond, str):
        return True  # string conditions are descriptive only
    p = ctx.profile

    def num_ok(key_min, key_max, val):
        if key_min in cond:
            if val is None or val < cond[key_min]:
                return False
        if key_max in cond:
            if val is None or val > cond[key_max]:
                return False
        return True

    if not num_ok("qtc_min", "qtc_max", p.labs.qtc_ms):
        return False
    if not num_ok("egfr_min", "egfr_max", ctx.egfr):
        return False
    if not num_ok("bmi_min", "bmi_max", ctx.bmi):
        return False
    if not num_ok("age_min", "age_max", ctx.age):
        return False

    if "severity_in" in cond and normalise(ctx.severity) not in [normalise(x) for x in cond["severity_in"]]:
        return False
    if "diagnosis_subtype_in" in cond:
        sub = (p.diagnosis_subtype or "").strip().lower()
        if not sub or not any(normalise(x) in sub for x in cond["diagnosis_subtype_in"]):
            return False
    if "comorbidity_any" in cond and not has_any(p.comorbidities, cond["comorbidity_any"]):
        return False
    if "current_med_any" in cond and not has_any(p.current_medications, cond["current_med_any"]):
        return False
    if "family_history_any" in cond and not ctx.family_history_has(cond["family_history_any"]):
        return False
    if "flags_all" in cond and not all(_FLAGS[f](ctx) for f in cond["flags_all"]):
        return False
    if "flags_any" in cond and not any(_FLAGS[f](ctx) for f in cond["flags_any"]):
        return False

    if "drug_qt_risk_in" in cond and drug.get("qt_risk") not in cond["drug_qt_risk_in"]:
        return False
    if "drug_metabolic_risk_in" in cond and drug.get("metabolic_risk") not in cond["drug_metabolic_risk_in"]:
        return False
    if "drug_sedation_in" in cond and drug.get("sedation") not in cond["drug_sedation_in"]:
        return False
    if "drug_overdose_toxicity_in" in cond and drug.get("overdose_toxicity") not in cond["drug_overdose_toxicity_in"]:
        return False
    return True


def rule_matches(rule: Dict[str, Any], ctx: PatientContext, drug: dict) -> bool:
    return (
        _match_diagnosis(rule["diagnosis"], ctx)
        and _match_population(rule["population"], ctx)
        and _match_drug(rule["drug_or_drug_class"], drug)
        and _match_condition(rule.get("condition"), ctx, drug)
    )


# --------------------------------------------------------------------------- #
# Applying                                                                    #
# --------------------------------------------------------------------------- #

def format_citation(rule: Dict[str, Any]) -> str:
    """Build a single citation string from the rule's metadata (no guideline text)."""
    parts: List[str] = []
    if rule.get("guideline_name"):
        parts.append(str(rule["guideline_name"]))
    if rule.get("citation_title"):
        parts.append(str(rule["citation_title"]))
    yr = rule.get("citation_year")
    if yr:
        parts.append(f"({yr})")
    if rule.get("guideline_section"):
        parts.append(str(rule["guideline_section"]))
    if rule.get("citation_page"):
        parts.append(f"p.{rule['citation_page']}")
    if rule.get("citation_url"):
        parts.append(str(rule["citation_url"]))
    return " — ".join(parts) if parts else "IPS CPG citation (placeholder)"


def _apply_rule(rule: Dict[str, Any], card: ScoreCard) -> None:
    cat = normalise(rule["recommendation_category"])
    contra = normalise(rule.get("contraindication_level") or "") or "none"
    delta = int(rule.get("score_modifier") or 0)
    rid = rule["rule_id"]
    detail = rule["explanation_for_clinician"]
    refs = [format_citation(rule)]

    if contra == "absolute" or cat in AVOID:
        card.mark_unsuitable(rid, detail, delta=delta, references=refs)
    elif cat in UP_RANK:
        card.add_reason(rid, detail, delta=delta, references=refs)
    elif cat in CAUTION:
        card.add_caution(rid, detail, delta=delta, references=refs)
    else:  # neutral / informational
        if delta < 0:
            card.add_caution(rid, detail, delta=delta, references=refs)
        else:
            card.add_reason(rid, detail, delta=delta, references=refs)

    for inv in rule.get("missing_investigations") or []:
        card.add_investigation(inv)
    for mon in rule.get("monitoring_required") or []:
        card.add_monitoring(mon)


def apply_ips_rules(ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
    """Apply every matching, enabled IPS rule to this drug's scorecard (in file order)."""
    for rule in load_ips_rules():
        if not rule.get("enabled", True):
            continue
        if rule_matches(rule, ctx, drug):
            _apply_rule(rule, card)


def ips_reference_entries() -> Dict[str, Dict[str, str]]:
    """rule_id -> citation entry, so the presentation layer's guideline_references table
    can resolve IPS rule_ids alongside the built-in references registry."""
    out: Dict[str, Dict[str, str]] = {}
    for rule in load_ips_rules():
        if not rule.get("enabled", True):
            continue
        lrb = (rule.get("last_reviewed_by") or "").strip().lower()
        reviewed = bool(lrb) and "placeholder" not in lrb and lrb not in ("tbd", "unreviewed", "none")
        out[rule["rule_id"]] = {
            "citation": format_citation(rule),
            "source_type": "ips_cpg",
            "status": "reviewed" if reviewed else "placeholder",
        }
    return out
