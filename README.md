# PsychRx Assist — Psychiatry Prescribing Decision Support

A clinician-facing decision-support prototype for psychiatry medication choice. It does
**not** prescribe automatically — it ranks options, flags cautions and contraindications,
lists the investigations and monitoring needed, and explains *why* each medication is
suitable, needs caution, or should be avoided, with a guideline reference for every rule
that fires.

> ## ⚠️ Safety notice — read first
> This is a **prototype for qualified clinicians**, not a prescription tool and **not for
> patient self-treatment**. Every clinical rule and citation shipped in this repository is
> an **unreviewed placeholder**. Before any clinical use you need, at minimum: psychiatrist
> review and sign-off of every rule (set `last_reviewed_by`/`last_reviewed_date`), exact
> citations against the source guidelines, licensed guideline/drug-database permissions,
> role-based authentication, audit logging, data-privacy compliance, medico-legal/regulatory
> review for your jurisdiction, and prospective validation on clinical vignettes.

## What it does

- Takes a structured patient profile (demographics, diagnosis, risk, comorbidity, previous
  trials, investigations, preferences) and returns a ranked, frontend-ready report.
- Buckets every candidate drug into **most suitable / use with caution / relatively
  unsuitable / contraindicated-or-avoid**, each with rationale, required baseline tests,
  monitoring, key adverse effects, interaction warnings, and organ/age notes.
- Also returns red flags, missing investigations, required monitoring, non-pharmacological
  recommendations, a guideline-reference table, a clinician-override note, and a disclaimer.
- The decision logic is a **deterministic Python rule engine** — there is no LLM in the
  decision path. Guideline rules can be authored as JSON and edited through an in-app admin
  page, with no code changes.

## Stack

- **Backend:** FastAPI + Pydantic v2 (Python 3.12), deterministic rule engine + JSON knowledge base
- **Frontend:** Next.js 15 / React 19 / TypeScript
- **Tests:** pytest (619 tests)

## Local setup

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Windows PowerShell: copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

API runs at `http://localhost:8000`; interactive docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
cp .env.example .env.local  # Windows PowerShell: copy .env.example .env.local
npm install
npm run dev
```

App runs at `http://localhost:3000`. The browser calls the local Next proxy at `/api`,
and the proxy forwards to `API_BASE_URL` (default `http://127.0.0.1:8000`). This keeps
local development and production deployment on the same request shape.

## Deployment

- Frontend: deploy `frontend/` to Vercel and set `API_BASE_URL` to your backend URL.
- Backend: deploy `backend/` to Render (or another Python host) with
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- CORS: if you ever call the backend directly from a browser, set `CORS_ALLOW_ORIGINS`
  in the backend environment.

See [`LAUNCH_WEBSITE.md`](LAUNCH_WEBSITE.md) for step-by-step GitHub + deployment setup.

## API

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/` | Health check |
| POST | `/recommend` | Full 12-section recommendation report (frontend-ready) |
| POST | `/recommend/raw` | Engine result before presentation formatting |
| GET | `/rules` | List guideline rules (optional `?diagnosis=&population=&include_disabled=`) |
| GET | `/rules/{rule_id}` | Get one rule |
| POST | `/rules` | Create a rule |
| PUT | `/rules/{rule_id}` | Update a rule |
| PATCH | `/rules/{rule_id}/disable` · `/enable` | Disable / re-enable a rule |
| GET | `/rules/ips` | Validate + summarise the JSON rule set (`?reload=true` to re-read) |

## Editing guideline rules

Guideline rules live as JSON in `backend/app/rules/ips/` (one file per topic) and are loaded,
validated, and applied without any code change — see that folder's `README.md` for the schema
and matching vocabulary. They can also be added/edited/disabled through the **Rule library**
page at `/admin/rules`, including citation and reviewer fields.

## Tests

```bash
cd backend
python -m pytest tests/ -q
```

## Project structure

```
backend/
  app/
    main.py                FastAPI app + endpoints
    models.py              Pydantic models (profile, report, rule)
    rules_engine.py        Orchestrator (engine result)
    knowledge_base.py      Loads drugs.json / references.json
    data/                  drugs.json, references.json
    engine/                context, scoring, base, registry, presentation,
                           ips_rules (JSON rule loader), rule_store (admin CRUD), ...
    diagnoses/             one module per diagnosis (+ shared bases)
    safety/                safety-modifier modules (incl. ips_cpg)
    rules/ips/             JSON guideline rules + README
  tests/                   pytest suite
  ARCHITECTURE.md          design, pipeline, and how-to-extend guide
frontend/
  app/
    page.tsx               assessment dashboard
    admin/rules/page.tsx   rule library / editor
    layout.tsx, globals.css
  lib/types.ts
```

## Architecture

See [`backend/ARCHITECTURE.md`](backend/ARCHITECTURE.md) for the engine layers, the
`extended_rules` parity switch, the scoring pipeline, the IPS rule system, the admin
rule-store seam (for a future PostgreSQL move), and recipes for adding a diagnosis or
safety modifier.

## Roadmap (not done yet)

- Clinical validation and psychiatrist sign-off of all rules/citations
- Authentication + audit trail on the rule-editing endpoints
- Move the rule store from JSON to PostgreSQL (the seam is in `engine/rule_store.py`)
- Containerisation and deployment

## License

No license is set. Add one (e.g. `LICENSE`) before publishing if you intend others to use it.
