"""Patient-level clinical flags derived from symptom dimensions.

These are not drug-ranking safety screens, so they live here rather than in a safety
module. They turn a couple of the universal symptom fields (catatonia, aggression) into
patient-level red flags / notes. Extended-rule-set only; with extended rules off these
return nothing (baseline behaviour unchanged). Each is conservative and editable.
"""
from __future__ import annotations

from typing import List, Tuple

from app.engine.context import PatientContext


def clinical_red_flags(ctx: PatientContext) -> List[str]:
    if not ctx.extended_rules:
        return []
    flags: List[str] = []
    if ctx.profile.symptoms.catatonia:
        flags.append("Catatonia reported: assess urgently; catatonia needs specific management (e.g. benzodiazepine trial/ECT per local protocol) and a medical work-up.")
    return flags


def clinical_notes(ctx: PatientContext) -> List[str]:
    if not ctx.extended_rules:
        return []
    notes: List[str] = []
    if ctx.profile.symptoms.aggression_risk:
        notes.append("Aggression/agitation risk recorded: prioritise de-escalation and safety, treat the underlying disorder, and avoid relying on sedation alone.")
    if ctx.profile.cost_concern:
        notes.append("Cost concern recorded: check local formulary and generic availability when choosing between comparable options.")
    return notes
