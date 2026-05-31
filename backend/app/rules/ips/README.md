# IPS CPG rule entries

Guideline rules live here as JSON. **Add or edit rules by editing these files only — no
Python changes are needed.** On the next server start (or after calling the reload
helper), the loader (`app/engine/ips_rules.py`) globs every `*.json` in this folder,
validates each rule, and applies matching rules during drug evaluation.

**Important — these are starter templates.** The clinical summaries are conservative,
widely-accepted principles written in our own words; the citation fields are
**placeholders**. Before any clinical use, a psychiatrist must verify each rule against
the actual Indian Psychiatric Society Clinical Practice Guideline, fill in the exact
`citation_title` / `citation_page` / `citation_url` / `citation_year`, and set
`last_reviewed_by` / `last_reviewed_date`. Do **not** paste copyrighted guideline text
into these files — only clinician-written summaries and citation metadata.

## File format

Each file is a JSON object with optional **file-level defaults** plus a `rules` array.
Any key set at the top level is merged into every rule in that file (a rule may override
it). A bare JSON array of rules is also accepted.

```json
{
  "guideline_name": "Indian Psychiatric Society Clinical Practice Guidelines (verify edition)",
  "guideline_section": "Pharmacological management",
  "citation_title": "...", "citation_page": "TBD", "citation_url": "...",
  "citation_year": null, "last_reviewed_by": "PLACEHOLDER ...", "last_reviewed_date": null,
  "condition": null, "missing_investigations": [], "monitoring_required": [],
  "contraindication_level": "none",
  "rules": [ { "rule_id": "...", "diagnosis": "...", "population": "...", "...": "..." } ]
}
```

## Rule fields (all required after merge with file defaults)

`rule_id`, `guideline_name`, `guideline_section`, `diagnosis`, `population`,
`condition`, `drug_or_drug_class`, `recommendation_category`, `score_modifier`,
`explanation_for_clinician`, `missing_investigations`, `monitoring_required`,
`contraindication_level`, `citation_title`, `citation_page`, `citation_url`,
`citation_year`, `last_reviewed_by`, `last_reviewed_date`.

## Matching vocabulary

- **diagnosis** — a diagnosis value (e.g. `major_depressive_disorder`), a list (OR), or
  `any`.
- **population** — a token, a list (OR), or `any`. Supported: `adult`, `child`,
  `adolescent`, `child_adolescent`, `elderly`/`geriatric`, `pregnant`/`pregnancy`,
  `lactating`/`lactation`, `childbearing_potential`, `renal`/`renal_impairment`,
  `hepatic`/`hepatic_impairment`, `cardiac`/`cardiac_illness`, `seizure`/`neurological`,
  `suicide_risk`, `non_adherence`/`poor_adherence`.
- **drug_or_drug_class** — a drug name (e.g. `Lithium`), a class (e.g. `SSRI`,
  `Second-generation antipsychotic`), a list (OR), or `any`. Class match is a
  case-insensitive substring (so `antipsychotic` matches the SGA class).
- **condition** — `null`, a descriptive string (shown to clinicians, not gating), or an
  object using these keys: `description`, `severity_in`, `diagnosis_subtype_in`,
  `qtc_min`/`qtc_max`, `egfr_min`/`egfr_max`, `bmi_min`/`bmi_max`, `age_min`/`age_max`,
  `comorbidity_any`, `current_med_any`, `family_history_any`, `flags_all`/`flags_any`
  (flags: `suicide_risk`, `non_adherence_risk`, `cardiac_disease`, `seizure_disorder`,
  `pregnant_or_planning`, `lactating`, `childbearing_potential`, `renal_impaired`,
  `hepatic_impaired`), and drug-property keys `drug_qt_risk_in`,
  `drug_metabolic_risk_in`, `drug_sedation_in`, `drug_overdose_toxicity_in`. A numeric
  threshold that cannot be evaluated (missing lab) means the rule does **not** fire.
  Unknown condition keys make the rule invalid (it is skipped and reported, not applied).

## Effect vocabulary

- **recommendation_category** — `preferred`/`first_line`/`most_suitable`/
  `relatively_preferred` (up-rank), `use_with_caution`/`second_line`/`caution`/
  `not_preferred`/`relatively_unsuitable` (caution / down-rank), `avoid`/`contraindicated`/
  `contraindicated_or_avoid` (force into the avoid bucket), or `neutral`/`informational`/
  `monitoring` (no ranking change beyond `score_modifier`, but still adds
  explanation/investigations/monitoring).
- **score_modifier** — integer added to the suitability score (positive up-ranks,
  negative down-ranks; `0` for informational).
- **contraindication_level** — `none`, `relative`, or `absolute`. `absolute` forces the
  drug into `contraindicated_or_avoid` regardless of category/score.
- **missing_investigations** / **monitoring_required** — added to that drug's required
  baseline tests and monitoring.

Validate the current folder at any time via `GET /rules/ips` (returns counts and any
validation problems).
