"""drug_interaction_safety — pairwise interaction screening (STUB).

This is a deliberately small, transparent, *editable* interaction table, not a real
drug-interaction database. It matches the candidate drug against keywords in the
patient's free-text ``current_medications`` and applies a conservative caution (or, for
dangerous combinations, forces 'relatively unsuitable'). Because matching is keyword-
based it can both miss and over-match.

PRODUCTION NOTE: replace this table with a validated DDI source (e.g. a licensed
interaction database) before clinical use. Every entry carries a placeholder citation.

Each rule in INTERACTIONS is a plain dict so a clinician can edit it without touching
logic:
    applies_to_name / applies_to_class : which candidate drug the rule is about
    current_med_keywords               : substrings to look for in current_medications
    severity                           : "caution" (down-rank) or "contraindicated" (force unsuitable)
    rule_id / detail / monitoring / investigation
"""
from __future__ import annotations

from typing import List, Optional

from app.engine.context import PatientContext
from app.engine.references import cite
from app.engine.safety_base import PatientAdvisory, SafetyModifier
from app.engine.safety_registry import register
from app.engine.scoring import ScoreCard
from app.engine.utils import has_any

# --- editable interaction table -------------------------------------------- #
INTERACTIONS: List[dict] = [
    {
        "rule_id": "DDI-LITHIUM-LEVEL",
        "applies_to_name": "lithium",
        "current_med_keywords": ["nsaid", "ibuprofen", "naproxen", "diclofenac", "ace inhibitor", "ramipril", "enalapril", "lisinopril", "perindopril", "arb", "losartan", "valsartan", "candesartan", "thiazide", "hydrochlorothiazide", "diuretic"],
        "severity": "caution",
        "delta": -15,
        "detail": "Co-medication can raise lithium levels (NSAIDs, ACE inhibitors/ARBs, thiazide diuretics): risk of lithium toxicity. Monitor lithium levels and renal function closely or choose an alternative.",
        "monitoring": "More frequent lithium level and renal-function checks while on the interacting medication.",
        "investigation": "Baseline and follow-up lithium level + renal function with interacting co-medication.",
    },
    {
        "rule_id": "DDI-CLOZAPINE-MARROW",
        "applies_to_name": "clozapine",
        "current_med_keywords": ["carbamazepine"],
        "severity": "caution",
        "delta": -15,
        "detail": "Combining clozapine with another marrow-suppressing agent (e.g. carbamazepine) increases agranulocytosis risk; avoid the combination or monitor blood counts very closely.",
        "monitoring": "Intensified blood-count (ANC) monitoring if combined with another myelosuppressive agent.",
        "investigation": None,
    },
    {
        "rule_id": "DDI-SEROTONIN-MAOI",
        "applies_to_classes": [
            "SSRI",
            "SNRI",
            "Tricyclic antidepressant / serotonin reuptake inhibitor",
            "Serotonin antagonist and reuptake inhibitor",
        ],
        "current_med_keywords": ["maoi", "phenelzine", "tranylcypromine", "isocarboxazid", "selegiline", "moclobemide", "linezolid"],
        "severity": "contraindicated",
        "delta": 0,
        "detail": "A serotonergic antidepressant with a monoamine-oxidase inhibitor (or linezolid) risks serotonin syndrome and is contraindicated without an adequate washout; do not co-prescribe.",
        "monitoring": None,
        "investigation": None,
    },
    {
        "rule_id": "DDI-SEROTONIN-OTHER",
        "applies_to_classes": [
            "SSRI",
            "SNRI",
            "Tricyclic antidepressant / serotonin reuptake inhibitor",
            "Serotonin antagonist and reuptake inhibitor",
        ],
        "current_med_keywords": ["tramadol", "triptan", "sumatriptan", "st john", "fentanyl", "pethidine", "meperidine"],
        "severity": "caution",
        "delta": -15,
        "detail": "Additional serotonergic co-medication (e.g. tramadol, triptans, St John's wort) raises serotonin-syndrome risk; review necessity and counsel on warning signs.",
        "monitoring": "Counsel on and monitor for serotonin-syndrome features when combined with other serotonergic agents.",
        "investigation": None,
    },
    {
        "rule_id": "DDI-MAOI-SEROTONERGIC",
        "applies_to_name": "phenelzine",
        "current_med_keywords": [
            "ssri", "snri", "sertraline", "fluoxetine", "fluvoxamine", "paroxetine",
            "escitalopram", "citalopram", "venlafaxine", "duloxetine", "clomipramine",
            "trazodone", "tramadol", "linezolid",
        ],
        "severity": "contraindicated",
        "delta": 0,
        "detail": "Phenelzine with a serotonergic antidepressant or selected serotonergic medicines can cause life-threatening serotonin toxicity; do not combine and use the required drug-specific washout.",
        "monitoring": None,
        "investigation": "Complete medication and recent-discontinuation review before starting an MAOI.",
    },
    {
        "rule_id": "DDI-SEDATIVE-RESPIRATORY",
        "applies_to_names": ["clonazepam", "lorazepam", "pregabalin", "gabapentin"],
        "current_med_keywords": [
            "opioid", "morphine", "oxycodone", "fentanyl", "codeine", "methadone",
            "buprenorphine", "alcohol", "benzodiazepine", "zopiclone", "zolpidem",
        ],
        "severity": "caution",
        "delta": -20,
        "detail": "Combining this sedating medicine with opioids, alcohol, benzodiazepines, or other sedatives increases respiratory depression, overdose, falls, and cognitive impairment risk.",
        "monitoring": "Review sedation, respiratory risk, falls, driving, misuse, and the necessity of every CNS depressant.",
        "investigation": None,
    },
]


def _candidate_matches(rule: dict, drug: dict) -> bool:
    name = drug.get("name", "").strip().lower()
    class_name = drug.get("class_name", "")
    if "applies_to_name" in rule and name == rule["applies_to_name"]:
        return True
    if "applies_to_names" in rule and name in rule["applies_to_names"]:
        return True
    if "applies_to_class" in rule and class_name == rule["applies_to_class"]:
        return True
    if "applies_to_classes" in rule and class_name in rule["applies_to_classes"]:
        return True
    return False


class DrugInteractionSafety(SafetyModifier):
    key = "drug_interaction"
    display_name = "Drug interaction safety"

    def applies(self, ctx: PatientContext, drug: dict) -> bool:
        return bool(ctx.profile.current_medications)

    def apply(self, ctx: PatientContext, drug: dict, card: ScoreCard) -> None:
        if not ctx.extended_rules or not ctx.profile.current_medications:
            return
        meds = ctx.profile.current_medications
        for rule in INTERACTIONS:
            if not _candidate_matches(rule, drug):
                continue
            if not has_any(meds, rule["current_med_keywords"]):
                continue
            refs = cite(rule["rule_id"])
            if rule["severity"] == "contraindicated":
                card.mark_unsuitable(rule["rule_id"], rule["detail"], delta=rule.get("delta", 0), references=refs)
            else:
                card.add_caution(rule["rule_id"], rule["detail"], delta=rule.get("delta", 0), references=refs)
            if rule.get("monitoring"):
                card.add_monitoring(rule["monitoring"])
            if rule.get("investigation"):
                card.add_investigation(rule["investigation"])

    def patient_advisories(self, ctx: PatientContext) -> PatientAdvisory:
        if not ctx.extended_rules or not ctx.profile.current_medications:
            return PatientAdvisory()
        return PatientAdvisory(notes=[
            "Interaction screening here is a simplified keyword-based stub; verify all combinations against a full drug-interaction reference before prescribing."
        ])


MODIFIER = register(DrugInteractionSafety())
