# Personal Finance Intelligence

A lightweight FastAPI app to upload card statements, analyze transactions, and manage personal finance data with secure authentication.

## What It Does

- Upload and parse PDF statements
- Track statements, transactions, accounts, reports, expenses, income, liabilities
- Email/password authentication (session + JWT)
- Google sign-in support (ID token flow)
- Password reset flow
- Multi-user data isolation via `user_id`

## Tech Stack

- FastAPI
- SQLAlchemy (async)
- Alembic
- Jinja2 + Tailwind
- PostgreSQL (recommended) or SQLite

## Quick Start

1. Create and activate virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment in `.env` (minimum):

```env
DATABASE_URL=postgresql+asyncpg://postgres@localhost:5434/pfi_db
APP_ENV=development
DEBUG=False
JWT_SECRET_KEY=replace-with-openssl-rand-hex-32
SESSION_SECRET_KEY=change-me
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
```

4. Run the app:

```bash
bash run.sh
```

Open: http://localhost:8000

## Available Commands

### App Runner

```bash
# Start server (development defaults)
bash run.sh

# Production-style run (no reload)
APP_ENV=production UVICORN_RELOAD=false bash run.sh
```

### User Management CLI

```bash
# Create user
bash run.sh create-user --email user@example.com --password "password123" --name "User Name"

# Create admin user
bash run.sh create-user --email admin@example.com --password "password123" --name "Admin" --admin

# Set/reset password
bash run.sh set-password --email user@example.com --password "newpassword123"
```

Direct usage:

```bash
python manage_user.py create-user --email user@example.com --password "password123"
python manage_user.py set-password --email user@example.com --password "newpassword123"
```

## Authentication Endpoints

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/login/json`
- `POST /api/auth/google/login`
- `POST /api/auth/request-password-reset`
- `POST /api/auth/reset-password`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/auth/session`

## Google OAuth Setup (Important)

In Google Cloud Console (Web app client):

Authorized JavaScript origins:
- `http://localhost:8000`
- `http://127.0.0.1:8000`

For the current ID-token flow, redirect URI is not actively used. If Google asks for one, use:
- `http://localhost:8000/api/auth/google/callback`
- `http://127.0.0.1:8000/api/auth/google/callback`

## Notes

- If login fails after DB/schema changes, run migrations and verify the `users` table matches current models.
- Use strong secrets in production.
- Keep `.env` out of version control.

## Production Checklist

- Set `APP_ENV=production`.
- Set strong `JWT_SECRET_KEY` and `SESSION_SECRET_KEY` values.
- Use PostgreSQL via `DATABASE_URL`.
- Run behind HTTPS and a reverse proxy (Nginx/Caddy/Cloud Run ingress).
- Ensure SMTP values are configured if password reset is enabled.
- Keep `UVICORN_RELOAD=false` in production.
- Remove local artifacts (`*.db`, `*.dump`, backups) from any release bundles.

## License

MIT
