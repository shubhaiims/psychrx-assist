"""Resolve rule ids to their supporting citations.

``cite("RENAL-DOSEADJ")`` returns the citation string(s) for that rule, or an
empty list if the rule has no registered reference. The engine never fabricates a
citation: an unmapped rule simply carries no reference, which is visible (and
auditable) rather than hidden behind invented text.
"""
from __future__ import annotations

from typing import List

from app.knowledge_base import load_references


def cite(rule_id: str) -> List[str]:
    entry = load_references().get(rule_id)
    if not entry:
        return []
    citation = entry.get("citation")
    return [citation] if citation else []


def is_placeholder(rule_id: str) -> bool:
    entry = load_references().get(rule_id)
    return bool(entry) and entry.get("status") == "placeholder"
