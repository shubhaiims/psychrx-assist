"""Loaders for the structured clinical knowledge base.

All clinical *facts* live in JSON (drugs.json) and all rule *citations* live in
references.json. Keeping them as data — not code — means a psychiatrist can review
and edit them without touching the engine, and the engine can never silently
invent a fact or a citation that is not present here.
"""
import json
from pathlib import Path
from functools import lru_cache

DATA_DIR = Path(__file__).parent / "data"


@lru_cache
def load_drugs() -> list[dict]:
    with open(DATA_DIR / "drugs.json", "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def load_references() -> dict:
    """rule_id -> {citation, source_type, status}. Placeholders until reviewed."""
    with open(DATA_DIR / "references.json", "r", encoding="utf-8") as f:
        return json.load(f)
