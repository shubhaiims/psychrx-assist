from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, computed_field

from app.diagnosis_catalog import DIAGNOSIS_OPTIONS


class Sex(str, Enum):
    male = "male"
    female = "female"
    other = "other"


class AgeGroup(str, Enum):
    child = "child"
    adolescent = "adolescent"
    adult = "adult"
    elderly = "elderly"


class PregnancyStatus(str, Enum):
    not_applicable = "not_applicable"
    not_pregnant = "not_pregnant"
    pregnant_first_trimester = "pregnant_first_trimester"
    pregnant_second_trimester = "pregnant_second_trimester"
    pregnant_third_trimester = "pregnant_third_trimester"
    lactating = "lactating"
    planning_pregnancy = "planning_pregnancy"
    unknown = "unknown"


class RenalStatus(str, Enum):
    normal = "normal"
    mild_impairment = "mild_impairment"
    moderate_impairment = "moderate_impairment"
    severe_impairment = "severe_impairment"
    unknown = "unknown"


class HepaticStatus(str, Enum):
    normal = "normal"
    mild_impairment = "mild_impairment"
    moderate_impairment = "moderate_impairment"
    severe_impairment = "severe_impairment"
    unknown = "unknown"


Diagnosis = Enum(
    "Diagnosis",
    {value: value for value, _label in DIAGNOSIS_OPTIONS},
    type=str,
    module=__name__,
)


class Severity(str, Enum):
    mild = "mild"
    moderate = "moderate"
    severe = "severe"
    severe_with_psychotic_features = "severe_with_psychotic_features"
    emergency = "emergency"


class Suicidality(str, Enum):
    """Graded suicidality. ``suicide_risk`` (a bool) remains the field the baseline
    safety rule keys on; this graded field refines it for the extended rule set."""
    none = "none"
    ideation = "ideation"
    ideation_with_plan = "ideation_with_plan"
    recent_attempt = "recent_attempt"
    unknown = "unknown"


class SymptomProfile(BaseModel):
    """Cross-diagnosis symptom dimensions. All default to absent so the schema works
    for any population without forcing the clinician to fill everything in. These are
    captured universally; diagnosis modules and the extended rule set consume them
    (e.g. catatonia/aggression flags). Add severities here as rules require them."""
    psychotic: bool = False
    negative: bool = False
    manic: bool = False
    depressive: bool = False
    anxiety: bool = False
    ocd: bool = False
    aggression_risk: bool = False
    catatonia: bool = False


class PreviousDrugResponse(BaseModel):
    drug: str
    response: str = Field(description="good, partial, none, intolerable, unknown")
    adverse_effects: List[str] = []
    adequate_trial: bool = False
    dose: Optional[str] = Field(default=None, description="Free-text dose reached, e.g. 'sertraline 150 mg/day'")
    duration_weeks: Optional[float] = Field(default=None, ge=0, description="Approximate duration of the trial in weeks")
    adequate_dose: Optional[bool] = Field(default=None, description="Whether a protocol-level dose was reached")
    adequate_duration: Optional[bool] = Field(default=None, description="Whether protocol-level duration was reached")


class LabValues(BaseModel):
    egfr: Optional[float] = None
    alt: Optional[float] = None
    ast: Optional[float] = None
    qtc_ms: Optional[float] = None
    tsh: Optional[float] = None
    hba1c: Optional[float] = None
    fasting_glucose: Optional[float] = None
    triglycerides: Optional[float] = None
    prolactin: Optional[float] = None
    anc: Optional[float] = None
    platelet_count: Optional[float] = None
    pregnancy_test_done: Optional[bool] = None


class PatientProfile(BaseModel):
    """Universal patient profile for all populations (adult, child/adolescent,
    elderly, pregnant, lactating, renal/hepatic impairment, cardiac/neurological
    illness, substance use, suicide risk, poor adherence).

    Only ``age``, ``sex`` and ``diagnosis`` are required; everything else is optional
    with a safe default, so a minimal profile is valid and richer profiles unlock more
    rules. New fields are consumed by the extended rule set; with extended rules off the
    engine reproduces the original behaviour regardless of these fields.
    """

    # --- demographics / anthropometrics ---
    age: int = Field(ge=0, le=120)
    sex: Sex
    height_cm: Optional[float] = Field(default=None, ge=30, le=250)
    weight_kg: Optional[float] = Field(default=None, ge=1, le=300)

    # --- reproductive status ---
    pregnancy_status: PregnancyStatus = PregnancyStatus.unknown
    trimester: Optional[int] = Field(default=None, ge=1, le=3, description="1, 2 or 3; supplements pregnancy_status")
    lactation_status: Optional[bool] = Field(default=None, description="supplements pregnancy_status == lactating")

    # --- organ function ---
    renal_status: RenalStatus = RenalStatus.unknown
    hepatic_status: HepaticStatus = HepaticStatus.unknown
    cardiac_disease: bool = False
    seizure_disorder: bool = Field(default=False, description="epilepsy/seizure history (neurological illness)")

    # --- diagnosis & illness course ---
    diagnosis: Diagnosis
    diagnosis_subtype: Optional[str] = None
    severity: Severity = Severity.moderate
    total_duration_months: Optional[int] = Field(default=None, ge=0)
    current_episode_duration_weeks: Optional[int] = Field(default=None, ge=0)

    # --- symptom dimensions & risk ---
    symptoms: SymptomProfile = Field(default_factory=SymptomProfile)
    suicide_risk: bool = False
    suicidality: Optional[Suicidality] = None

    # --- history ---
    family_history: List[str] = []
    family_history_drug_response: List[str] = Field(default=[], description="e.g. 'good lithium response in mother'")
    comorbidities: List[str] = []
    current_medications: List[str] = []
    previous_drug_responses: List[PreviousDrugResponse] = []

    # --- investigations ---
    labs: LabValues = Field(default_factory=LabValues)
    investigations_done: List[str] = Field(default=[], description="baseline investigations already completed")

    # --- preferences / practical ---
    preferences: List[str] = Field(default=[], description="Examples: avoid_weight_gain, avoid_sedation, avoid_sexual_side_effects, low_cost, once_daily")
    cost_concern: bool = False
    non_adherence_risk: bool = False
    substance_use: List[str] = []

    @computed_field  # exposes derived BMI in the schema/JSON; read-only
    @property
    def bmi(self) -> Optional[float]:
        if not self.height_cm or not self.weight_kg:
            return None
        height_m = self.height_cm / 100
        return round(self.weight_kg / (height_m * height_m), 1)


class Evidence(BaseModel):
    """Per-rule provenance: which named rule fired, its effect, and its citation.

    This is ADDITIVE. The flat ``reasons`` / ``cautions`` / ``references`` lists are
    still populated exactly as before; ``rule_trace`` lets a reviewer (or the
    explanation layer) see which specific rule produced each statement and what
    guideline/drug-reference rule supports it.
    """

    rule_id: str
    kind: str = Field(description="reason or caution")
    detail: str
    delta: int = 0
    references: List[str] = []


class RecommendationItem(BaseModel):
    drug: str
    class_name: str
    category: str = Field(description="most_suitable, use_with_caution, relatively_unsuitable")
    score: int
    reasons: List[str]
    cautions: List[str]
    baseline_investigations: List[str]
    monitoring: List[str]
    references: List[str]
    rule_trace: List[Evidence] = []
    forced_unsuitable: bool = Field(default=False, description="True if a rule forced this into the avoid/contraindicated bucket")


class RecommendationResponse(BaseModel):
    disclaimer: str
    patient_summary: Dict[str, str]
    most_suitable: List[RecommendationItem]
    use_with_caution: List[RecommendationItem]
    relatively_unsuitable: List[RecommendationItem]
    missing_information: List[str]
    urgent_red_flags: List[str]
    general_notes: List[str]


# --------------------------------------------------------------------------- #
# Rich, frontend-ready API output                                             #
# --------------------------------------------------------------------------- #
# The models above are the engine's internal result. The models below are the
# clean, display-ready shape the API returns (built by engine/presentation.py).

class CaseSummary(BaseModel):
    summary_text: str
    age: int
    age_group: str
    sex: str
    bmi: Optional[float] = None
    diagnosis: str
    diagnosis_display: str
    diagnosis_subtype: Optional[str] = None
    severity: str
    pregnancy_status: str
    lactating: bool = False
    renal_status: str
    hepatic_status: str
    cardiac_disease: bool = False
    seizure_disorder: bool = False
    suicide_risk: bool = False
    non_adherence_risk: bool = False


class GuidelineReference(BaseModel):
    rule_id: str
    citation: str
    source_type: str
    status: str


class DrugOption(BaseModel):
    drug_name: str
    drug_class: str
    suitability_score: int
    category: str = Field(description="most_suitable | use_with_caution | relatively_unsuitable | contraindicated_or_avoid")
    reason_for_category: str
    why_suitable: List[str] = []
    why_caution: List[str] = []
    why_unsuitable: List[str] = []
    dose_note_placeholder: str
    required_baseline_tests: List[str] = []
    monitoring_required: List[str] = []
    important_side_effects: List[str] = []
    interaction_warnings: List[str] = []
    pregnancy_lactation_note: str = ""
    renal_note: str = ""
    hepatic_note: str = ""
    elderly_note: str = ""
    child_adolescent_note: str = ""
    guideline_reference_placeholder: List[str] = []


class RecommendationReport(BaseModel):
    """The final, frontend-ready API response (always has all 12 sections)."""
    case_summary: CaseSummary
    red_flags: List[str] = []
    most_suitable_options: List[DrugOption] = []
    use_with_caution: List[DrugOption] = []
    relatively_unsuitable: List[DrugOption] = []
    contraindicated_or_avoid: List[DrugOption] = []
    missing_investigations: List[str] = []
    required_monitoring: List[str] = []
    non_pharmacological_recommendations: List[str] = []
    guideline_references: List[GuidelineReference] = []
    clinician_override_note: str
    disclaimer: str


# --------------------------------------------------------------------------- #
# IPS CPG rule editing (admin API)                                            #
# --------------------------------------------------------------------------- #
# Permissive model for creating/updating a guideline rule. Shape/type checking
# happens here; domain-vocabulary checking happens in engine.ips_rules._validate_rule.

class IpsRuleModel(BaseModel):
    rule_id: str
    recommendation_category: str
    explanation_for_clinician: str
    diagnosis: Union[str, List[str]] = "any"
    population: Union[str, List[str]] = "any"
    drug_or_drug_class: Union[str, List[str]] = "any"
    condition: Union[Dict[str, Any], str, None] = None
    score_modifier: int = 0
    contraindication_level: str = "none"
    guideline_name: str = ""
    guideline_section: str = ""
    missing_investigations: List[str] = []
    monitoring_required: List[str] = []
    citation_title: Optional[str] = None
    citation_page: Union[str, int, None] = None
    citation_url: Optional[str] = None
    citation_year: Union[int, str, None] = None
    last_reviewed_by: Optional[str] = None
    last_reviewed_date: Optional[str] = None
    enabled: bool = True
