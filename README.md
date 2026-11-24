# AI Helpdesk

A multi-tenant helpdesk (ITSM) backend built with Python, FastAPI and PostgreSQL. Each customer company is a *tenant*, with its own users, tickets and comments. The project explores ServiceNow-inspired ticket workflows and AI-assisted support answers grounded in knowledge-base content with citations.

**Status: in progress.** Core ticketing, authentication, role-based access, comments, activity timelines, knowledge-base ingestion services, hybrid retrieval, and the AI question endpoint are implemented. ServiceNow migration and production deployment are not currently implemented.

## What works today

- **Multi-tenant database design (PostgreSQL + SQLAlchemy):** tables for tenants, users, tickets, ticket comments, ticket events, knowledge-base articles, and content chunks.
- **Tenant-aware access:** ticket and AI retrieval queries are scoped to the authenticated user's tenant. End users see their own tickets; agents and admins have broader tenant-scoped visibility.
- **Authentication:** JWT login, 30-minute access tokens, Argon2 password hashing, and protected routes.
- **Role-based access control:** admin, agent, and end-user roles.
- **Ticket management:** create and list tickets, retrieve by ticket number, and update state, priority, assignee, and resolution (agent/admin only).
- **Comments and visibility:** public and internal comments. End users see public comments; agents and admins can see both.
- **Activity timeline:** ticket creation and field-change events combined with comments. End-user timeline output is filtered.
- **Alembic migrations:** versioned database schema migrations, including pgvector and full-text search support.
- **Knowledge-base ingestion service:** article chunking, content hashing, embedding generation, and synchronization of stored chunks with article content and publication status.
- **AI question endpoint:** authenticated `POST /ai/ask` retrieves tenant-scoped context, generates a grounded answer with Gemini, and returns citation metadata.
- **Hybrid retrieval:** pgvector semantic search combined with PostgreSQL full-text search and Reciprocal Rank Fusion (RRF), with a distance gate and a maximum of two chunks per parent article.
- **Evaluation and tests:** golden-set evaluation scripts, tenant-isolation checks, and AI API tests.

## Current limitations

- **No ServiceNow migration workflow yet.** Idempotent import, dry-run, and reconciliation are future work.
- **No public knowledge-base management API yet.** Ingestion currently exists as a Python service and supporting scripts, rather than a complete set of article CRUD endpoints.
- **No frontend UI.** The project currently exposes a backend API and Swagger documentation.
- **No production deployment or production observability setup yet.**
- The user lookup route `GET /users/test/{user_id}` is a development/test route and currently lacks authentication. It should be restricted or removed before production use.
- Ticket numbers are generated as random `T-XXXXXXXX` identifiers.

## Run it locally

Requirements: Python 3.12+, Docker and Docker Compose. The Dockerfile uses Python 3.12 and the Compose configuration runs PostgreSQL 16 with the pgvector image.

```bash
git clone https://github.com/Akshay-Lokhande-Dev/ai-helpdesk.git
cd ai-helpdesk

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and provide the required values.

docker compose up -d
alembic upgrade head
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation.

### Environment variables

Configure these values in `.env`:

```env
POSTGRES_USER=your_database_user
POSTGRES_PASSWORD=your_database_password
POSTGRES_DB=ai_helpdesk
DATABASE_URL=postgresql+psycopg://your_database_user:your_database_password@localhost:5433/ai_helpdesk
SECRET_KEY=your_long_random_secret
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

The database container is exposed on host port **5433**. Keep `.env` private and never commit API keys or credentials.

The `GEMINI_API_KEY` is required for Gemini answer generation. When it is absent or Gemini generation fails, the current implementation can fall back to the top retrieved chunk and mark the response as degraded.

## API endpoints

### Health

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Application health check |
| GET | `/db-check` | Database connectivity check |

### Authentication

**Key fixes driven by eval failures:**
- **2 chunks per article:** Allowed up to 2 chunks per article in deduplication so troubleshooting/footer sections (`chunk_index=1`) aren't dropped.
- **Hybrid distance gate:** Gated FTS keyword matches with `distance <= max_distance + 0.15` to block unrelated queries while still rescuing exact technical terms (e.g., Okta metadata XML).
- **Negative-answer prompting:** Updated system instructions so explicitly unsupported/ineligible features (e.g., SMS 2FA, auto-renewal refunds) are answered directly instead of triggering false abstentions.
- **KB PII masking fix:** Removed `mask_pii()` from curated KB article ingestion (while keeping it on incoming user queries) so official support/billing emails remain intact.


## Evaluation & Benchmarks

### 1. Golden Set Evaluation (Tenant A — 21 KB Articles, 55 Queries)
- **Retrieval Hit@1 (Answerable):** 41/42 (98%)
- **Retrieval Recall@5 (Answerable):** 42/42 (100%)
- **Unanswerable / Abstention Accuracy:** 100% (hybrid threshold + grounded LLM guardrail)

### 2. Multi-Tenant Scale & Isolation Stress Test (Tenant B — 472 FastAPI Doc Chunks)
- Ingested 50 real-world FastAPI Markdown docs (**472 chunks**) into a secondary tenant (`Tenant B`) to test noisy-neighbor interference and real messy formatting.
- **Average Retrieval Latency:** ~35.2ms (max 143.7ms) across 472 chunks on CPU.
- **Noisy-Neighbor Impact:** 0% degradation on Tenant A's golden set scores.
- **Cross-Tenant Isolation:** 0% data leakage verified across both SQL retrieval and end-to-end LLM generation (5/5 pass on `scripts/eval_tenant_b_llm.py`).

### 3. Automated Integration Tests (`pytest`)
Run the full suite:
```bash
pytest -v
