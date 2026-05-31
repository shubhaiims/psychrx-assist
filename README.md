# PsychRx Assist - Psychiatry Prescribing Decision Support

A clinician-facing decision-support prototype for psychiatry medication choice. It does
not prescribe automatically. Instead, it ranks options, flags cautions and
contraindications, lists the investigations and monitoring needed, and explains why each
medication is suitable, needs caution, or should be avoided, with a guideline reference
for every rule that fires.

> Safety notice
> This is a prototype for qualified clinicians, not a prescription tool and not for
> patient self-treatment. Every clinical rule and citation shipped in this repository is
> an unreviewed placeholder. Before any clinical use you need, at minimum: psychiatrist
> review and sign-off of every rule, exact citations against the source guidelines,
> licensed guideline and drug-database permissions, role-based authentication, audit
> logging, data-privacy compliance, medico-legal and regulatory review for your
> jurisdiction, and prospective validation on clinical vignettes.

## What it does

- Takes a structured patient profile and returns a ranked, frontend-ready medication assessment.
- Buckets every candidate drug into most suitable, use with caution, relatively unsuitable, or contraindicated-or-avoid.
- Returns red flags, missing investigations, required monitoring, non-pharmacological recommendations, guideline references, and a clinician override note.
- Uses a deterministic Python rule engine rather than an LLM in the clinical decision path.
- Supports clinician-authored rule review through an in-app admin page.

## Stack

- Backend: FastAPI + Pydantic v2 (Python 3.12), deterministic rule engine, JSON knowledge base, optional Postgres-backed rule overrides
- Frontend: Next.js 15 / React 19 / TypeScript with a Next route-handler API proxy
- Monitoring: optional Vercel Analytics, Speed Insights, and Sentry on both frontend and backend
- Tests: pytest (619 tests)

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
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

API runs at `http://localhost:8000`; interactive docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

App runs at `http://localhost:3000`. The browser calls the local Next proxy at `/api`,
and the proxy forwards to `API_BASE_URL` (default `http://127.0.0.1:8000`). This keeps
local development and production deployment on the same request shape.

## Persistent rule editing

By default, the IPS rules are loaded from JSON files under `backend/app/rules/ips/`.
If you configure a Postgres database, create, edit, enable, and disable actions are
stored as persistent overrides and merged on top of the JSON baseline at runtime.

Supported database environment variables:

- `RULE_STORE_DATABASE_URL`
- `POSTGRES_URL_NON_POOLING`
- `DATABASE_URL`
- `POSTGRES_URL`
- `POSTGRES_PRISMA_URL`

To create the override table manually, run the SQL in `backend/sql/rule_overrides.sql`.

## Deployment

- Frontend: deploy `frontend/` to Vercel and set `API_BASE_URL` to your backend URL.
- Backend: deploy `backend/` to Vercel or another Python host.
- Database: for persistent rule editing on Vercel, connect a Postgres provider through the Vercel Marketplace or set `RULE_STORE_DATABASE_URL` manually.
- Monitoring: set `NEXT_PUBLIC_SENTRY_DSN` and `SENTRY_DSN` to enable Sentry.
- Domain readiness: set `NEXT_PUBLIC_SITE_URL` to your production custom domain so canonical, Open Graph, robots, and sitemap metadata point at the right host.

See `LAUNCH_WEBSITE.md` for step-by-step deployment setup.

## API

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/` | Health check |
| POST | `/recommend` | Full 12-section recommendation report |
| POST | `/recommend/raw` | Engine result before presentation formatting |
| GET | `/rules` | List guideline rules |
| GET | `/rules/{rule_id}` | Get one rule |
| POST | `/rules` | Create a rule |
| PUT | `/rules/{rule_id}` | Update a rule |
| PATCH | `/rules/{rule_id}/disable` and `/enable` | Disable or re-enable a rule |
| GET | `/rules/ips` | Validate and summarize the rule set |

## Editing guideline rules

Guideline rules live as JSON in `backend/app/rules/ips/` and are loaded, validated, and
applied without any code change. They can also be added, edited, or disabled through the
Rule library page at `/admin/rules`, including citation and reviewer fields. When a
Postgres database is configured, those edits persist as overrides; otherwise the app
falls back to file-based storage.

## Tests

```bash
cd backend
python -m pytest tests/ -q
```

## Project structure

```text
backend/
  app/
    main.py                FastAPI app + endpoints
    monitoring.py          Sentry initialization
    models.py              Pydantic models
    rules_engine.py        Orchestrator
    knowledge_base.py      Loads drugs.json / references.json
    data/                  drugs.json, references.json
    engine/                scoring, registry, presentation, IPS rules, rule store, Postgres overrides
    diagnoses/             one module per diagnosis
    safety/                safety-modifier modules
    rules/ips/             JSON guideline rules + README
  sql/                     optional Postgres schema for rule overrides
  tests/                   pytest suite
  ARCHITECTURE.md          design, pipeline, and extension guide
frontend/
  app/
    page.tsx               assessment dashboard
    admin/rules/page.tsx   rule library / editor
    layout.tsx             metadata, nav, analytics hooks
    globals.css            shared styles
  lib/
    site.ts                canonical site URL helper
    types.ts
```

## Architecture

See `backend/ARCHITECTURE.md` for the engine layers, the scoring pipeline, the IPS rule
system, the rule-store seam, the Postgres override path, and recipes for adding a
diagnosis or safety modifier.

## Roadmap

- Clinical validation and psychiatrist sign-off of all rules and citations
- Authentication and audit trail on the rule-editing endpoints
- Containerization and deployment hardening
- Role-based governance around production rule editing

## License

No license is set. Add one before publishing if you intend others to use it.
