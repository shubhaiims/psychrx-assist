# Launching PsychRx Assist

This project has two deployable parts:

- `frontend/`: Next.js website
- `backend/`: FastAPI API

The smoothest Vercel setup is to create two Vercel projects from the same GitHub repo:

- frontend project with root directory `frontend`
- backend project with root directory `backend`

## 1. Run locally

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`.

The browser talks to `frontend/app/api/[...path]/route.ts`, which forwards requests to
`API_BASE_URL` from `frontend/.env.local`. The default local backend target is
`http://127.0.0.1:8000`.

## 2. Push to GitHub

If Git is installed on your machine, run:

```powershell
cd psychrx-assist
git init
git add .
git commit -m "Initial PsychRx Assist website"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

## 3. Deploy backend on Vercel

Create a Vercel project with root directory `backend`.

Set backend environment variables:

- `CORS_ALLOW_ORIGINS=https://your-frontend-domain.vercel.app`
- `RULE_STORE_DATABASE_URL=postgres://...` if you want persistent rule editing
- `SENTRY_DSN=https://...` to enable backend error monitoring
- `SENTRY_TRACES_SAMPLE_RATE=0.1`

Notes:

- If you connect a Postgres provider through the Vercel Marketplace, the backend can also
  read `DATABASE_URL`, `POSTGRES_URL`, `POSTGRES_URL_NON_POOLING`, or `POSTGRES_PRISMA_URL`.
- To create the persistent override table manually, run the SQL in `backend/sql/rule_overrides.sql`.
- Without a database, rule editing stays read-only on Vercel.

## 4. Deploy frontend on Vercel

Create a second Vercel project with root directory `frontend`.

Set frontend environment variables:

- `API_BASE_URL=https://your-backend-project.vercel.app`
- `NEXT_PUBLIC_API_BASE=/api`
- `NEXT_PUBLIC_SITE_URL=https://your-frontend-domain.vercel.app`
- `NEXT_PUBLIC_SENTRY_DSN=https://...` to enable frontend error monitoring
- `SENTRY_DSN=https://...` if you want server-side Next.js events in the same project

Because the frontend proxies API requests through Next route handlers, the browser keeps
calling `/api/...` in both local and production environments.

## 5. Turn on analytics and monitoring

After the frontend deploy is live:

- open the Vercel project and enable Web Analytics
- open the Vercel project and enable Speed Insights
- add Sentry DSNs to frontend and backend env vars, then redeploy both projects

The codebase already includes the Vercel Analytics component, Speed Insights component,
and Sentry initialization hooks.

## 6. Add a custom domain

For the frontend project:

1. Open `Settings > Domains`
2. Add your apex domain, for example `psychrxassist.com`
3. Add the `www` domain if Vercel prompts for it
4. Update `NEXT_PUBLIC_SITE_URL=https://psychrxassist.com`
5. Redeploy the frontend project

Optional backend domain:

1. Add a subdomain such as `api.psychrxassist.com` to the backend project
2. Update frontend `API_BASE_URL=https://api.psychrxassist.com`
3. Update backend `CORS_ALLOW_ORIGINS=https://psychrxassist.com`
4. Redeploy both projects

## 7. Final checks

- open the frontend domain and pass the clinician safety gate
- generate a sample assessment
- open `/admin/rules`
- if Postgres is configured, create a test rule and confirm it is still present after a redeploy
- confirm Vercel Analytics and Speed Insights data starts appearing in the dashboard
- trigger one test error in Sentry so you know monitoring is live
