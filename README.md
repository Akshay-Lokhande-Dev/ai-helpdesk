# AI Helpdesk

A multi-tenant helpdesk (ITSM) backend built with Python, FastAPI and PostgreSQL. Each customer company is a *tenant*, with its own users, tickets and comments. The long-term goal is smooth migration from ServiceNow and AI-assisted answers with citations.

**Status: in progress.** See "What works today" and "Planned" below. Nothing under "Planned" is built yet.

## What works today
- **Database design (PostgreSQL + SQLAlchemy 2.0):** tables for `tenants`, `users`, `tickets` and `ticket_comments`, with foreign keys, per-tenant composite unique constraints (email and ticket number) and indexes on `tickets.caller_id` and `tickets.assignee_id`.
- **Comment visibility:** each comment is `public` or `internal`; a test script confirms the filter (an agent sees both, an end user would see only public).
- **Schema migrations with Alembic**, including one fix for autogenerate missing server defaults (`compare_server_default`).
- **FastAPI endpoints:**
  - `GET /health`, `GET /db-check`
  - `GET /tickets` (latest 50), `GET /tickets/{ticket_id}` (404 if not found)
  - `POST /tickets` (validates that the tenant and caller exist and belong together; returns 404 otherwise)
- Pydantic response schemas, so only chosen fields leave the API; a per-request database session dependency.
- PostgreSQL (pgvector image) running in Docker.

## Known limitations (on purpose, for now)
- **No authentication yet.** `POST /tickets` takes `tenant_id` and `caller_id` in the request body; these will come from a login token later.
- `GET /tickets` currently returns tickets from all tenants. Tenant filtering will come with login.
- Ticket numbers are random for now (`T-XXXXXXXX`).

## Planned (not started)
- Users endpoint, password hashing and JWT login with roles
- Comments endpoints
- ServiceNow data migration (idempotent import, dry run, reconciliation)
- Retrieval-augmented answers with citations (pgvector)
- Deployment and tests

## Run it locally
Requirements: Python 3.13, Docker.

```bash
git clone https://github.com/Akshay-Lokhande-Dev/ai-helpdesk.git
cd ai-helpdesk
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then fill in the values (see below)
docker compose up -d          # starts PostgreSQL on host port 5433
alembic upgrade head          # creates the tables
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API docs.

Optional: `python -m scripts.smoke_test` creates a sample tenant, user, ticket and comments and prints the visibility check.

`.env` keys: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL` (use `localhost:5433` in the URL).

## Project layout
```
app/            FastAPI app, models, schemas, routers
alembic/        database migrations
scripts/        helper scripts (smoke test)
ERRORS.md       bugs I hit and how I fixed them
```

## Tech
Python, FastAPI, PostgreSQL (pgvector image), SQLAlchemy 2.0, Alembic, Pydantic, Docker.
