# CLAUDE.md — PsychRx Assist

Clinician-facing psychiatry **prescribing decision-support** tool. It ranks medication
options for a patient profile, explains each ranking, and lists required investigations,
monitoring, and guideline references. It is decision support, **not** an automatic
prescription generator and **not** a patient self-treatment app.

Read `backend/ARCHITECTURE.md` before making non-trivial changes — it documents the
layered engine, the `extended_rules` switch, and the recipes referenced below.

## Stack & layout

- **Backend** — FastAPI + Pydantic v2, Python 3.12, in `backend/`. Deterministic Python
  rules + JSON knowledge base. No LLM/network calls in the scoring path.
- **Frontend** — Next.js 15 / React 19 / TypeScript, in `frontend/`. Talks to the API at
  `NEXT_PUBLIC_API_BASE` (default `/api`), with `frontend/app/api/[...path]/route.ts`
  proxying to `API_BASE_URL` (default `http://127.0.0.1:8000`).

```
backend/app/
  models.py            Pydantic models (PatientProfile, RecommendationReport, DrugOption, ...)
  main.py              FastAPI app + endpoints
  rules_engine.py      generate_recommendations(profile, *, extended_rules=True) -> internal result
  knowledge_base.py    load_drugs() / load_references()  (lru_cached)
  data/                drugs.json, references.json
  engine/              context, scoring, core_rules, base, registry, safety_base,
                       safety_registry, global_checks, references, clinical_flags,
                       presentation (rich report), ips_rules, rule_store, utils
  _legacy_reference.py FROZEN original engine — parity baseline only, never wire in
  diagnoses/           one module per diagnosis (+ _*_common.py bases), self-registering
  safety/              12 safety modifiers, self-registering (ips_cpg runs last)
  rules/ips/           JSON-authored IPS CPG guideline rules + README
tests/                 parity, clinical_rules, output_format, ips_rules,
                       rule_admin_api, clinical_vignettes
frontend/app/          page.tsx (assessment dashboard), admin/rules/page.tsx, globals.css
frontend/lib/types.ts  mirrors RecommendationReport
```

## Commands

Run backend commands **from `backend/`** (modules import `from app.xxx`).

```bash
# backend
cd backend
python3 -m pytest tests/ -q          # full suite — currently 619 passing, keep it green
uvicorn app.main:app --reload        # dev server on :8000

# frontend
cd frontend
npm install
npm run dev                          # dev server on :3000
npx tsc --noEmit                     # type-check (no test runner is set up)
```

There is no virtualenv committed; create one and install fastapi, uvicorn, pydantic,
python-dotenv, pytest, httpx.

## Non-negotiable rules

1. **Never fabricate medical facts.** Encode only widely-accepted, bedrock clinical
   principles. All citations are honest **placeholders** tagged by `source_type`/`status`
   — never invent a real citation, page number, dose, or specific guideline claim.
   Derived content (e.g. `important_side_effects`) must come from existing structured
   data, not invention.
2. **No copyrighted guideline text.** Only clinician-written summaries + citation
   metadata.
3. **Deterministic engine.** No LLM calls or network in scoring/presentation. The AI layer
   only *explains* rule output; it never prescribes.
4. **Parity via `extended_rules`.** With `extended_rules=False` the engine must reproduce
   `_legacy_reference` exactly. Every clinician-authored rule self-gates with
   `if not ctx.extended_rules: return`. Baseline rules stay ungated. `tests/test_parity.py`
   enforces this (structured grid + fuzz, comparing multisets, excluding `rule_trace`).
   **Run the test suite after any engine change** — parity and determinism tests are
   load-bearing.
5. **No over-reach in output.** Ranking buckets are `most_suitable` /
   `use_with_caution` / `relatively_unsuitable` / `contraindicated_or_avoid`. Every drug
   option explains why, plus required investigations, monitoring, and supporting rule.

## Extending without touching core code

- **New diagnosis** → add `diagnoses/<name>.py` (subclass `DiagnosisRuleModule`,
  `register(...)`), import it in `diagnoses/__init__.py`. `assert_registry_complete`
  checks it against the `Diagnosis` enum.
- **New safety dimension** → add `safety/<name>_safety.py` (subclass `SafetyModifier`,
  `register(...)`), import it in `safety/__init__.py`.
- **New guideline rule** → add/edit JSON in `rules/ips/` (no Python). Validate with
  `GET /rules/ips` or the admin editor at `/admin/rules`. Vocabulary is documented in
  `rules/ips/README.md`; unknown condition keys make a rule invalid (excluded + reported).

## API surface (in `app/main.py`)

- `POST /recommend` → `RecommendationReport` (12-section, frontend-ready)
- `POST /recommend/raw` → internal engine result (debugging)
- `GET /rules` (filters: `diagnosis`, `population`, `include_disabled`),
  `GET /rules/{id}`, `POST /rules`, `PUT /rules/{id}`,
  `PATCH /rules/{id}/disable|enable` — admin CRUD via `engine/rule_store.py`
  (the swap-in seam for a future PostgreSQL store; keep that boundary clean)
- `GET /rules/ips` → validation/health for the JSON rules

## Conventions

- Keep all medical logic editable by clinicians (modules + JSON), separate from framework.
- Add a test for every behaviour change; prefer asserting invariants (a drug lands in a
  bucket, a keyword appears in a flag) over exact scores. See `tests/test_clinical_vignettes.py`.
- Frontend palette is intentionally restrained/clinical; status colors map green = most
  suitable, amber = caution, red = relatively unsuitable / avoid, blue = missing
  investigations, grey = guideline references. Don't introduce flashy styling.
