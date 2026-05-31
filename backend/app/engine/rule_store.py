"""Rule store — read/write access to the IPS CPG rules for the admin editor.

This is the single seam between the rule data and the rest of the app. Today it persists
to the JSON files in ``app/rules/ips/`` (via ``engine/ips_rules.py`` for reads); later it
can be swapped for a PostgreSQL-backed implementation without changing the API layer or
the engine. All write operations re-validate the rule with the same ``_validate_rule``
used at load time and then clear the loader cache so reads/scoring see the change.

Conventions:
* rules are addressed by ``rule_id`` (unique across all files);
* reads return the *merged* rule (file-level defaults applied) plus ``_source_file`` and
  ``enabled``;
* new rules are written to ``custom_rules.json`` by default (keeping the curated,
  topic-organised files tidy), unless a target file is given;
* edits and enable/disable are written back to the rule's own source file;
* writes are atomic (temp file + ``os.replace``).
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from app.engine import ips_rules
from app.engine.ips_rules import _as_list  # noqa: PLC2701  (internal helper reuse)
from app.engine.utils import normalise

DEFAULT_TARGET_FILE = "custom_rules.json"


class RuleStoreError(Exception):
    """Base class for rule-store errors."""


class RuleNotFound(RuleStoreError):
    pass


class RuleConflict(RuleStoreError):
    pass


class RuleInvalid(RuleStoreError):
    def __init__(self, problems: List[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


# --------------------------------------------------------------------------- #
# low-level file helpers                                                      #
# --------------------------------------------------------------------------- #

def _rules_dir() -> str:
    # read at call time so tests can monkeypatch ips_rules.IPS_RULES_DIR
    return ips_rules.IPS_RULES_DIR


def _safe_file(name: str) -> str:
    name = os.path.basename(name or DEFAULT_TARGET_FILE)
    if not name.endswith(".json"):
        name += ".json"
    return name


def _read_raw(path: str) -> Any:
    with open(path) as fh:
        return json.load(fh)


def _rules_list(data: Any) -> List[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.setdefault("rules", [])
    raise RuleStoreError("rule file must be a list or an object with 'rules'")


def _write_raw(path: str, data: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def _clean(rule: Dict[str, Any]) -> Dict[str, Any]:
    """Strip internal/derived keys and normalise types before persisting."""
    out = {k: v for k, v in rule.items() if not k.startswith("_")}
    out["enabled"] = bool(out.get("enabled", True))
    if out.get("score_modifier") is not None:
        try:
            out["score_modifier"] = int(out["score_modifier"])
        except (TypeError, ValueError):
            pass  # let _validate_rule report it
    return out


# --------------------------------------------------------------------------- #
# reads                                                                       #
# --------------------------------------------------------------------------- #

def _explicit_match(field_value, want: str) -> bool:
    toks = [normalise(t) for t in _as_list(field_value)]
    return normalise(want) in toks


def list_rules(diagnosis: Optional[str] = None, population: Optional[str] = None,
               include_disabled: bool = True) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in ips_rules.load_ips_rules():
        if not include_disabled and not r.get("enabled", True):
            continue
        if diagnosis and not _explicit_match(r.get("diagnosis"), diagnosis):
            continue
        if population and not _explicit_match(r.get("population"), population):
            continue
        out.append(r)
    return out


def get_rule(rule_id: str) -> Optional[Dict[str, Any]]:
    for r in ips_rules.load_ips_rules():
        if r.get("rule_id") == rule_id:
            return r
    return None


def list_problems() -> List[str]:
    return ips_rules.ips_rule_problems()


# --------------------------------------------------------------------------- #
# writes                                                                      #
# --------------------------------------------------------------------------- #

def create_rule(rule: Dict[str, Any], target_file: Optional[str] = None) -> Dict[str, Any]:
    rid = (rule.get("rule_id") or "").strip()
    if not rid:
        raise RuleInvalid(["rule_id is required"])
    if get_rule(rid) is not None:
        raise RuleConflict(f"a rule with rule_id '{rid}' already exists")
    clean = _clean(rule)
    errs = ips_rules._validate_rule(dict(clean))
    if errs:
        raise RuleInvalid(errs)

    path = os.path.join(_rules_dir(), _safe_file(target_file or DEFAULT_TARGET_FILE))
    data = _read_raw(path) if os.path.exists(path) else {"rules": []}
    _rules_list(data).append(clean)
    _write_raw(path, data)
    ips_rules.reload()
    return get_rule(rid)


def update_rule(rule_id: str, rule: Dict[str, Any]) -> Dict[str, Any]:
    existing = get_rule(rule_id)
    if existing is None:
        raise RuleNotFound(rule_id)
    clean = _clean(rule)
    clean["rule_id"] = rule_id  # the path id is authoritative
    errs = ips_rules._validate_rule(dict(clean))
    if errs:
        raise RuleInvalid(errs)

    path = os.path.join(_rules_dir(), existing["_source_file"])
    data = _read_raw(path)
    lst = _rules_list(data)
    for i, entry in enumerate(lst):
        if entry.get("rule_id") == rule_id:
            lst[i] = clean
            break
    else:
        raise RuleNotFound(rule_id)
    _write_raw(path, data)
    ips_rules.reload()
    return get_rule(rule_id)


def set_enabled(rule_id: str, enabled: bool) -> Dict[str, Any]:
    existing = get_rule(rule_id)
    if existing is None:
        raise RuleNotFound(rule_id)
    path = os.path.join(_rules_dir(), existing["_source_file"])
    data = _read_raw(path)
    for entry in _rules_list(data):
        if entry.get("rule_id") == rule_id:
            entry["enabled"] = bool(enabled)
            break
    else:
        raise RuleNotFound(rule_id)
    _write_raw(path, data)
    ips_rules.reload()
    return get_rule(rule_id)
