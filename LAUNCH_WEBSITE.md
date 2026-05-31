# Launching PsychRx Assist

This project has two deployable parts:

- `frontend/`: Next.js website
- `backend/`: FastAPI API

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

If Git is not installed, install Git or GitHub Desktop first, then push this folder as a
new repository.

## 3. Deploy backend

This repo includes [render.yaml](./render.yaml) and [backend/Procfile](./backend/Procfile)
for a simple Render deployment.

Set:

- `CORS_ALLOW_ORIGINS=https://your-frontend-domain.vercel.app`

Start command:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## 4. Deploy frontend

Deploy the `frontend/` folder to Vercel.

Set:

- `API_BASE_URL=https://your-backend-service.onrender.com`
- `NEXT_PUBLIC_API_BASE=/api`

Because the frontend now proxies API requests through Next route handlers, the browser
can keep calling `/api/...` in both local and production environments.
