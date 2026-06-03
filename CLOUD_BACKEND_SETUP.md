# Cloud Backend and Web Editing Setup

This is the setup you want when all background data should live on the web:

- The public website runs as the frontend.
- The backend API runs on a web host.
- A Postgres database stores rule edits.
- `/admin/rules` edits the backend database.
- The assessment page reads rules from the backend.

## Required Web Services

Use these three pieces:

- Frontend host: Vercel project with root directory `frontend`
- Backend host: Vercel project with root directory `backend`
- Database: Postgres from Supabase, Neon, or a Vercel Marketplace Postgres provider

## Backend Environment Variables

Set these in the backend web project:

```text
CORS_ALLOW_ORIGINS=https://your-frontend-domain.vercel.app
RULE_STORE_DATABASE_URL=postgres://your-database-url
ADMIN_AUTH_TOKEN=make-a-long-private-password
SENTRY_DSN=
SENTRY_TRACES_SAMPLE_RATE=0.1
```

The backend creates the `ips_rule_overrides` table automatically. You can also run
`backend/sql/rule_overrides.sql` manually inside your database SQL editor.

## Frontend Environment Variables

Set these in the frontend web project:

```text
API_BASE_URL=https://your-backend-domain.vercel.app
NEXT_PUBLIC_API_BASE=/api
NEXT_PUBLIC_SITE_URL=https://your-frontend-domain.vercel.app
NEXT_PUBLIC_SENTRY_DSN=
SENTRY_DSN=
```

## Editing Data on the Web

1. Open `https://your-frontend-domain.vercel.app/admin/rules`.
2. Enter the same value you set in `ADMIN_AUTH_TOKEN`.
3. Add, edit, enable, or disable a rule.
4. The backend saves the change to Postgres.
5. New assessments use the edited cloud rules.

## Important

Do not leave `ADMIN_AUTH_TOKEN` empty on a public website. If it is empty, anyone who can
reach your admin page may be able to edit rules.
