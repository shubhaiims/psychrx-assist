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
    if ctx.care_setting in {"emergency_department", "inpatient"} and (
        ctx.profile.symptoms.agitation or ctx.profile.symptoms.aggression_risk
    ):
        flags.append(
            "Acute agitation/aggression in an emergency or inpatient setting: use immediate "
            "staff/patient safety measures, verbal de-escalation, medical/substance/withdrawal "
            "assessment, and the current local rapid-tranquillisation protocol."
        )
    if ctx.profile.symptoms.poor_oral_intake or ctx.profile.symptoms.immobility:
        flags.append(
            "Poor oral intake or immobility reported: urgently assess hydration, nutrition, "
            "electrolytes, thrombosis/pressure-injury risk, catatonia, medication effects, and "
            "medical causes."
        )
    return flags


def clinical_notes(ctx: PatientContext) -> List[str]:
    if not ctx.extended_rules:
        return []
    notes: List[str] = []
    if ctx.profile.symptoms.aggression_risk:
        notes.append("Aggression/agitation risk recorded: prioritise de-escalation and safety, treat the underlying disorder, and avoid relying on sedation alone.")
    if ctx.care_setting in {"emergency_department", "inpatient"}:
        notes += [
            "Inpatient sequence: reconcile all prescribed, non-prescribed, and recently stopped medicines; obtain collateral history and identify intoxication, withdrawal, delirium, or another medical driver before changing the psychiatric regimen.",
            "Record target symptoms for every standing and PRN medicine, count the total daily dose from all routes, and prefer the same antipsychotic for standing and PRN use when clinically appropriate.",
            "Minimise simultaneous medication changes and long-term polypharmacy. When switching is necessary, document the cross-titration plan, adverse-effect surveillance, and the date response will be judged.",
            "Before discharge, simplify the regimen where possible, provide a safe medication supply and monitoring plan, communicate with outpatient clinicians, and involve family/carers with consent.",
        ]
    if ctx.profile.cost_concern:
        notes.append("Cost concern recorded: check local formulary and generic availability when choosing between comparable options.")
    return notes
