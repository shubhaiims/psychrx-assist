// Types mirror the backend RecommendationReport (engine/presentation.py).

export type DrugOption = {
  drug_name: string;
  drug_class: string;
  suitability_score: number;
  category:
    | "most_suitable"
    | "use_with_caution"
    | "relatively_unsuitable"
    | "contraindicated_or_avoid";
  reason_for_category: string;
  why_suitable: string[];
  why_caution: string[];
  why_unsuitable: string[];
  dose_note_placeholder: string;
  required_baseline_tests: string[];
  monitoring_required: string[];
  important_side_effects: string[];
  interaction_warnings: string[];
  pregnancy_lactation_note: string;
  renal_note: string;
  hepatic_note: string;
  elderly_note: string;
  child_adolescent_note: string;
  guideline_reference_placeholder: string[];
};

export type CaseSummary = {
  summary_text: string;
  age: number;
  age_group: string;
  sex: string;
  bmi: number | null;
  diagnosis: string;
  diagnosis_display: string;
  diagnosis_subtype: string | null;
  severity: string;
  pregnancy_status: string;
  lactating: boolean;
  renal_status: string;
  hepatic_status: string;
  cardiac_disease: boolean;
  seizure_disorder: boolean;
  suicide_risk: boolean;
  non_adherence_risk: boolean;
};

export type GuidelineReference = {
  rule_id: string;
  citation: string;
  source_type: string;
  status: string;
};

export type RecommendationReport = {
  case_summary: CaseSummary;
  red_flags: string[];
  most_suitable_options: DrugOption[];
  use_with_caution: DrugOption[];
  relatively_unsuitable: DrugOption[];
  contraindicated_or_avoid: DrugOption[];
  missing_investigations: string[];
  required_monitoring: string[];
  non_pharmacological_recommendations: string[];
  guideline_references: GuidelineReference[];
  clinician_override_note: string;
  disclaimer: string;
};

// --- admin rule editor ---
export type IpsRule = {
  rule_id: string;
  guideline_name?: string;
  guideline_section?: string;
  diagnosis: string | string[];
  population: string | string[];
  condition?: Record<string, unknown> | string | null;
  drug_or_drug_class: string | string[];
  recommendation_category: string;
  score_modifier: number;
  explanation_for_clinician: string;
  missing_investigations?: string[];
  monitoring_required?: string[];
  contraindication_level?: string;
  citation_title?: string | null;
  citation_page?: string | number | null;
  citation_url?: string | null;
  citation_year?: number | string | null;
  last_reviewed_by?: string | null;
  last_reviewed_date?: string | null;
  enabled?: boolean;
  _source_file?: string;
};

export type RulesListResponse = {
  rules: IpsRule[];
  problems: string[];
};
