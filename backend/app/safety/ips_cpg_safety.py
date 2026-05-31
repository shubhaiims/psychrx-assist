"""ips_cpg_safety — applies the JSON-authored IPS CPG guideline rules.

This is the bridge between the JSON rule files in ``app/rules/ips/`` and the scoring
pipeline. It holds no rules of its own: it asks ``engine/ips_rules.py`` for every rule
that matches the patient + candidate drug and applies their effects. Adding or editing
rules is therefore a pure-JSON operation — this module never needs to change.

Gated on ``extended_rules`` (like the rest of the clinician-authored layer), so with the
extended set off the engine reproduces the original behaviour.
"""
from __future__ import annotations

from app.engine.context import PatientContext
from app.engine.ips_rules import apply_ips_rules
from app.engine.safety_base import SafetyModifier
from app.engine.safety_registry import register
from app.engine.scoring import ScoreCard


class IpsCpgSafety(SafetyModifier):
    key = "ips_cpg"
    display_name = "IPS CPG guideline rules"

    def apply(self, ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
        if not ctx.extended_rules:
            return
        apply_ips_rules(ctx, drug, card)


MODIFIER = register(IpsCpgSafety())
