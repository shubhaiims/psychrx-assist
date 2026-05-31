# Rule Engine Architecture

This document describes the rule-engine structure and how to extend it.

The engine has two layers of behaviour:

* a **behaviour-preserving baseline** — the mechanical refactor of the original
  monolithic engine. With the extended rule set turned off
  (`extended_rules=False`), the API response is byte-for-byte identical to the
  original engine on every existing field (proven by `tests/test_parity.py`); and
* an **extended, clinician-authored rule set** (on by default) — diagnosis-specific
  and population-specific rules that deliberately change the ranking. These are
  covered by `tests/test_clinical_rules.py`.

`rule_trace` (an additive field on each recommendation) records which named rule
produced each reason/caution, its score delta, and its citation, so every output is
auditable and editable.

## Why this shape

The original engine put every diagnosis's logic inside one `evaluate_drug()`
function, with the diagnosis-specific bits buried as `if diagnosis == "..."`
branches. That does not scale as you expand diagnosis-wise and population-wise. The
layout gives **one rule module per diagnosis**, a small shared core they all reuse,
and **cross-cutting safety modifiers** (one per safety dimension: pregnancy/lactation,
renal, hepatic, cardiac/QTc, metabolic, seizure, elderly, child/adolescent,
suicide/overdose, adherence, interactions), so adding or changing one area never
touches the others.

## The `extended_rules` switch

`generate_recommendations(profile, extended_rules=True)` (and
`build_context(profile, extended_rules=...)`) gate the entire clinician-authored
rule set behind a single boolean, threaded onto `PatientContext.extended_rules`.

* `True` (default, what the API uses): baseline + all extended diagnosis/population
  rules.
* `False`: baseline only — reproduces the original engine exactly.

This is the kill-switch the parity test uses, and a safe way for a clinician/dev to
compare "with vs without" a rule change while reviewing. Every extended rule begins
with `if not ctx.extended_rules: return` (diagnosis rules) or is only invoked when
the flag is on (population layers). The original baseline rules — the diagnosis match,
the shared safety bundle, and the pre-existing bipolar lithium-family-history /
antidepressant-monotherapy / TSH rules — are **not** gated, because they are part of
the parity baseline.

## Layers

```
backend/app/
├── rules_engine.py          # thin orchestrator (public entry point; no clinical logic)
├── models.py                # Pydantic models (+ additive Evidence/rule_trace)
├── knowledge_base.py        # load_drugs(), load_references()
├── data/
│   ├── drugs.json           # drug knowledge base (unchanged)
│   └── references.json      # rule_id -> citation registry (placeholders for now)
├── engine/                  # diagnosis-agnostic framework
│   ├── context.py           # PatientContext (universal flags: pregnancy, trimester, renal,
│   │                        #   hepatic, cardiac, seizure, childbearing, suicidality, extended_rules)
│   ├── scoring.py           # ScoreCard + RuleHit (add_reason/add_caution/mark_unsuitable/
│   │                        #   add_investigation/add_monitoring); category thresholds
│   ├── core_rules.py        # non-safety per-drug rules: age-fit, preference, prior response
│   ├── global_checks.py     # patient-level missing-info + red-flags
│   ├── clinical_flags.py    # catatonia/aggression/cost patient-level flags (extended)
│   ├── references.py        # cite(rule_id) -> citations (never fabricated)
│   ├── base.py              # DiagnosisRuleModule: the contract + evaluation pipeline
│   ├── registry.py          # diagnosis registry: register / get_module / assert_registry_complete
│   ├── safety_base.py       # SafetyModifier + PatientAdvisory (the safety-module contract)
│   ├── safety_registry.py   # safety registry: register / all_modifiers
│   └── utils.py             # small pure helpers
├── diagnoses/               # ONE module per diagnosis (clinical/diagnosis logic)
│   ├── __init__.py          # imports all modules (self-register) + integrity check
│   ├── _bipolar_common.py / _psychosis_common.py / _anxiety_common.py / _substance_common.py
│   ├── major_depressive_disorder.py
│   ├── bipolar_mania.py / bipolar_depression.py / bipolar_maintenance.py
│   ├── schizophrenia.py / acute_psychosis.py
│   ├── ocd.py / generalized_anxiety_disorder.py / panic_disorder.py / ptsd.py
│   ├── adhd.py
│   ├── alcohol_use_disorder.py / opioid_use_disorder.py
│   └── dementia_related_behavioural_symptoms.py
└── safety/                  # ONE module per safety dimension (cross-cutting screens)
    ├── __init__.py          # imports all modifiers (self-register); defines application order
    ├── pregnancy_lactation_safety.py
    ├── renal_safety.py
    ├── hepatic_safety.py
    ├── cardiac_qtc_safety.py
    ├── metabolic_safety.py
    ├── seizure_safety.py
    ├── elderly_safety.py
    ├── child_adolescent_safety.py
    ├── suicide_overdose_safety.py
    ├── adherence_safety.py
    └── drug_interaction_safety.py
```

## How a recommendation is produced

`generate_recommendations(profile, extended_rules=True)` in `rules_engine.py`:

1. `build_context(profile, extended_rules=...)` derives a frozen `PatientContext`
   (age group, BMI, organ-function and pregnancy flags, cardiac/seizure history,
   childbearing potential, graded suicidality, the `extended_rules` flag) **once**.
2. `get_module(ctx.diagnosis)` selects the diagnosis module; `all_modifiers()` is the
   ordered list of safety screens.
3. The module's `candidate_drugs(...)` returns the drugs indicated for that diagnosis
   (knowledge-base order).
4. Each candidate is scored by `module.evaluate(ctx, drug, modifiers)`.
5. Results are sorted by score (descending, stable sort → ties keep knowledge-base
   order) and bucketed into `most_suitable` / `use_with_caution` /
   `relatively_unsuitable` (a safety modifier can also force `relatively_unsuitable`
   via `mark_unsuitable`).
6. Patient-level outputs are assembled: global checks → diagnosis additions → each
   safety modifier's `patient_advisories` → symptom-level clinical flags. The
   `missing_information` list (the fourth output, "missing investigations before final
   prescribing") then has anything in `investigations_done` removed.

### The per-drug evaluation pipeline

Inside `DiagnosisRuleModule.evaluate`:

```
DX-MATCH → core rules (age-fit, preference, prior response)
         → diagnosis_specific_rules
         → safety modifiers (each dimension, in registration order)
```

- **core rules** (`core_rules.py`): population/age fit, patient preference, previous
  drug response — baseline, ungated.
- **diagnosis_specific_rules**: the module's own logic (e.g. SSRI-first-line for MDD;
  bipolar lithium family-history; clozapine-reserved-for-TRD).
- **safety modifiers** (`safety/`): each screens one dimension. Every modifier applies
  its behaviour-preserving baseline portion unconditionally and its extended,
  clinician-authored portion only when `ctx.extended_rules` is on.

Deltas are additive, so this order affects only the order of the reasons/cautions
lists, not the score or category. With `extended_rules=False` the scores, categories,
and field content reproduce the original engine; the parity test asserts this
(comparing the reason/caution lists as multisets, since rules are now grouped by
source).

## Categorisation (unchanged)

Decided on the *raw* (un-clamped) score, then the reported score is clamped to
0–100:

```
raw < 40                       → relatively_unsuitable
raw < 70  OR any caution        → use_with_caution
otherwise                       → most_suitable
```

The thresholds live as named constants in `engine/scoring.py` so a reviewer can
adjust them in one place.

## Adding a new diagnosis

1. Add the value to the `Diagnosis` enum in `models.py`.
2. Create `diagnoses/<your_diagnosis>.py`:

   ```python
   from app.engine.base import DiagnosisRuleModule
   from app.engine.registry import register

   MODULE = register(DiagnosisRuleModule(
       diagnosis="your_diagnosis",
       display_name="Human-readable name",
   ))
   ```

   That generic module already does indication-based candidate selection and the
   full shared safety bundle. If the diagnosis needs unique logic, subclass
   `DiagnosisRuleModule` and override only the relevant hook(s):
   `diagnosis_specific_rules`, `extra_missing_info`, `extra_red_flags`,
   `diagnosis_notes`, or `candidate_drugs`. See `bipolar_depression.py` for an
   example.
3. Add an import line in `diagnoses/__init__.py`.
4. Ensure each drug that applies lists the diagnosis in its `diagnoses[]` in
   `drugs.json`.

`assert_registry_complete()` runs at import time: if the enum and the registered
modules ever drift apart, the app refuses to start with a clear error instead of
silently routing a patient to a generic fallback.

## Adding a safety modifier

Safety modifiers screen one dimension across every diagnosis. To add one:

1. Create `safety/<name>_safety.py` subclassing `SafetyModifier`; set `key` and
   `display_name`, optionally override `applies(ctx, drug)` (a cheap pre-check), and
   implement `apply(ctx, drug, card)` and/or `patient_advisories(ctx)`. Inside `apply`
   a modifier can up-rank (`card.add_reason(..., delta=+N)`), down-rank
   (`card.add_caution(..., delta=-N)`), move to use-with-caution (any `add_caution`),
   move to relatively-unsuitable (`card.mark_unsuitable(...)`), add a missing
   investigation (`card.add_investigation`), add monitoring (`card.add_monitoring`),
   and attach citations (`references=cite(rule_id)`). Gate clinician-authored logic
   behind `ctx.extended_rules`.
2. `register(...)` the modifier and add an import line in `safety/__init__.py` (its
   position there is its application order).

The orchestrator runs every modifier for each candidate drug and merges their patient
advisories, so a safety concern can refine a diagnosis-driven recommendation, and each
firing is captured in `rule_trace`.

## What the extended rule set encodes

The extended rules are conservative, widely-accepted *structural / ranking* rules
(first-line vs reserve/adjunct, reserve/avoid conditions, monitoring), not dosing.
They are organised by area:

- **MDD** — SSRIs first-line; antipsychotics adjunct/augmentation (or for psychotic
  features); early-suicidality monitoring; psychotherapy advisory.
- **Bipolar** — lithium first-line (mania/maintenance); SGAs first-line for mania;
  lamotrigine for the depressive pole; (plus the baseline lithium-family-history,
  antidepressant-monotherapy caution, and TSH work-up).
- **Schizophrenia/psychosis** — clozapine reserved for treatment resistance with ANC
  monitoring; SGA metabolic monitoring; exclude organic causes in acute psychosis.
- **OCD/anxiety (OCD, GAD, panic, PTSD)** — SSRIs first-line; OCD dosing, panic
  start-low, and PTSD trauma-focused-psychotherapy advisories.
- **ADHD** — stimulants first-line; cardiac-history and substance-use cautions;
  atomoxetine as a non-stimulant alternative.
- **Substance use** — naltrexone requires an opioid-free interval; advisories noting
  the agonist/acamprosate options not yet in the knowledge base.
- **Pregnancy & lactation** (safety modifier) — valproate restricted in pregnancy *and*
  childbearing potential; perinatal/lactation advisories.
- **Child & adolescent** (safety modifier) — antidepressant and atomoxetine boxed-warning
  suicidality cautions; stimulant growth/cardiac monitoring; specialist advisory.
- **Geriatric / elderly** (safety modifier) — antipsychotic-in-dementia boxed-warning caution (this
  fulfils the safety hook previously flagged in the dementia module); general
  antipsychotic caution; sedation/fall caution; start-low advisory.

Every reason/caution above maps to a placeholder citation in `references.json`
(`source_type` records whether it stands in for a guideline, boxed warning, regulatory
restriction, or drug reference). **All of these are starting placeholders and must be
reviewed, corrected, and cited by a qualified psychiatrist before clinical use** — the
engine encodes the *logic*, not a verified guideline.

## API output shape (presentation layer)

The engine produces an internal result (`RecommendationResponse`: scores, categories,
reasons/cautions, investigations, monitoring, per-rule `rule_trace`). `engine/
presentation.py` reshapes that into the public, frontend-ready `RecommendationReport`
returned by `POST /recommend`. The report always contains twelve sections:
`case_summary`, `red_flags`, `most_suitable_options`, `use_with_caution`,
`relatively_unsuitable`, `contraindicated_or_avoid`, `missing_investigations`,
`required_monitoring`, `non_pharmacological_recommendations`, `guideline_references`,
`clinician_override_note`, `disclaimer`.

Each drug is rendered as a `DrugOption` with: `drug_name`, `drug_class`,
`suitability_score`, `category`, `reason_for_category`, `why_suitable`,
`why_caution`, `why_unsuitable`, `dose_note_placeholder`, `required_baseline_tests`,
`monitoring_required`, `important_side_effects`, `interaction_warnings`,
`pregnancy_lactation_note`, `renal_note`, `hepatic_note`, `elderly_note`,
`child_adolescent_note`, `guideline_reference_placeholder`.

The internal three categories map to four display buckets: an item whose
`forced_unsuitable` flag is set (a rule called `mark_unsuitable`) is surfaced under
`contraindicated_or_avoid` rather than `relatively_unsuitable`. `POST /recommend/raw`
returns the pre-presentation engine result for debugging/integration. The presentation
layer adds no clinical logic — it only formats; `important_side_effects` is derived
from the structured risk flags already in the knowledge base (not fabricated), and
`dose_note_placeholder` reflects that the engine deliberately does not generate doses.

## IPS CPG rule system (JSON-authored guideline rules)

Guideline rules can be added as pure JSON — no Python changes. Files live in
`app/rules/ips/*.json`; the loader (`engine/ips_rules.py`) globs the folder, validates
each rule, merges any file-level defaults, and a single registered safety modifier
(`safety/ips_cpg_safety.py`, key `ips_cpg`, runs last) applies every matching rule to
each candidate drug's scorecard.

Each rule has 19 fields (`rule_id`, `guideline_name`, `guideline_section`, `diagnosis`,
`population`, `condition`, `drug_or_drug_class`, `recommendation_category`,
`score_modifier`, `explanation_for_clinician`, `missing_investigations`,
`monitoring_required`, `contraindication_level`, `citation_title`, `citation_page`,
`citation_url`, `citation_year`, `last_reviewed_by`, `last_reviewed_date`). Matching uses
a documented vocabulary: `diagnosis` (value/list/`any`), `population` (token/list/`any`;
adult, child, elderly, pregnant, renal/hepatic/cardiac, etc.), `drug_or_drug_class`
(name, class substring, or `any`), and a structured `condition` (lab thresholds, flags,
comorbidity/med keywords, severity/subtype, and candidate-drug-property checks). Unknown
condition keys or population tokens make a rule invalid — it is excluded and reported
rather than mis-applied. Effects map onto the scorecard: `preferred`/`first_line` →
up-rank, `use_with_caution`/`not_preferred` → caution, `avoid`/`contraindicated` or
`contraindication_level: absolute` → mark-unsuitable (→ contraindicated_or_avoid bucket),
`neutral`/`informational` → note only; plus the rule's investigations and monitoring.

The whole layer is gated on `extended_rules` (off → no IPS rules, preserving legacy
parity). It holds no copyrighted text — only clinician summaries and citation metadata,
and the shipped rules are unreviewed placeholders (verify against the actual IPS CPG and
set `last_reviewed_by` before clinical use). IPS citations flow into both the per-drug
`guideline_reference_placeholder` and the case-level `guideline_references` table (tagged
`source_type: ips_cpg`). Validate the folder at runtime via `GET /rules/ips`
(`?reload=true` re-reads after edits).

To add a rule: edit/add a file under `app/rules/ips/`, then restart (or hit
`/rules/ips?reload=true`). To add a new *kind* of condition predicate, extend
`SUPPORTED_CONDITION_KEYS` and `_match_condition` in `engine/ips_rules.py`.

## Admin rule editor (CRUD API + /admin/rules page)

Clinicians edit rules without coding through `/admin/rules` (frontend) backed by a CRUD
API. The seam is `engine/rule_store.py` — the single place that reads/writes rules. Today
it persists to the JSON files (reads via `ips_rules`, writes atomically); swapping it for
a PostgreSQL-backed module later changes nothing in the API or engine. Rules carry an
optional persisted `enabled` flag (default true); disabled rules load and are visible in
the editor but are skipped during scoring and in the references table.

API (in `main.py`): `GET /rules` (optional `?diagnosis=&population=&include_disabled=`
filters; returns rules + any validation problems), `GET /rules/{rule_id}`, `POST /rules`
(writes to `custom_rules.json` by default, or `?file=`), `PUT /rules/{rule_id}`,
`PATCH /rules/{rule_id}/disable`, and `PATCH /rules/{rule_id}/enable`. The static
`/rules/ips` health route is declared before `/rules/{rule_id}` so it is not shadowed.
Writes re-validate with the same `_validate_rule` used at load time (invalid → HTTP 422
with the problem list; duplicate id → 409; missing → 404) and clear the loader cache so
changes take effect immediately. `POST`/`PUT` bodies are the `IpsRuleModel` (permissive
types; vocabulary still checked by the store). New rules default to
`custom_rules.json` to keep the curated topic files tidy; edits and enable/disable are
written back to the rule's own source file (enable/disable touches only the `enabled`
key, preserving the file's minimal entries).

The page supports view, filter by diagnosis/population, add, edit, disable/enable, and
editing citation + reviewer (`last_reviewed_by` / `last_reviewed_date`) fields.

## Provenance: rule_trace and references.json

Every rule records a `RuleHit` (rule id, reason/caution, score delta, and its
supporting citation). These surface on each recommendation as `rule_trace`
(additive — the flat `reasons`/`cautions`/`references` lists are unchanged), so a
reviewer or the explanation layer can see exactly which rule produced each line
and which guideline supports it.

Citations come from `data/references.json` via `cite(rule_id)`. The engine
**never fabricates a citation**: an unmapped rule simply carries no reference. All
current entries are honest placeholders (`"status": "placeholder"`) and must be
replaced with psychiatrist-reviewed citations from licensed guidelines and drug
references before any clinical use.

## Where the future AI explanation layer attaches

The AI layer (rule 6: explain, don't prescribe) consumes the finished
`RecommendationResponse` — specifically each item's `reasons`, `cautions`, and
`rule_trace` — and turns it into clinician-facing prose. It must **never** alter
scores, categories, or ordering; the deterministic engine remains the single
source of truth.

## Running the tests

```
cd backend
pip install -r requirements.txt --break-system-packages
pip install pytest httpx --break-system-packages
python -m pytest tests/ -q
```

- `tests/test_parity.py` proves the **baseline** (run with `extended_rules=False`)
  reproduces the original engine across a large structured grid (every diagnosis ×
  age group × major safety branch) plus a fixed-seed randomised fuzz of 2000
  profiles; it also checks the full engine is deterministic and that the extended
  rules actually change output. `app/_legacy_reference.py` is the frozen original,
  kept only for this comparison and not wired into the app.
- `tests/test_clinical_rules.py` has one focused test per extended rule (diagnosis
  and safety modifiers), plus gating and safety-registry checks. It doubles as readable,
  editable documentation of each rule's trigger and effect.
