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

<<<<<<< HEAD
| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/login` | Authenticate with tenant slug, email, and password |
| GET | `/auth/me` | Get the current authenticated user |

### Users

| Method | Endpoint | Description |
|---|---|---|
| POST | `/users` | Create a user (admin only) |
| GET | `/users/test/{user_id}` | Development/test user lookup route; currently unauthenticated |

### Tickets

| Method | Endpoint | Description |
|---|---|---|
| GET | `/tickets` | List up to 50 visible tickets |
| POST | `/tickets` | Create a ticket for the authenticated user |
| GET | `/tickets/{ticket_number}` | Retrieve a visible ticket by ticket number |
| PATCH | `/tickets/{ticket_id}` | Update ticket fields (agent/admin only) |

### Comments

| Method | Endpoint | Description |
|---|---|---|
| POST | `/tickets/{ticket_id}/comments` | Add a comment |
| GET | `/tickets/{ticket_id}/comments` | List comments visible to the current user |

### Timeline

| Method | Endpoint | Description |
|---|---|---|
| GET | `/tickets/{ticket_id}/timeline` | Retrieve the ticket activity timeline |

### AI assistant

| Method | Endpoint | Description |
|---|---|---|
| POST | `/ai/ask` | Ask a question against the current tenant's knowledge base |

The AI request body accepts a `question` string (3–500 characters). The response includes an answer, citation metadata, a similarity value where available, and a degraded flag.

## RAG architecture

### Knowledge-base ingestion

1. Read a knowledge-base article.
2. Split its body into chunks (default: 800 characters with 100-character overlap).
3. Combine each chunk with the article title.
4. Generate normalized embeddings using `all-MiniLM-L6-v2`.
5. Store chunks, SHA-256 content hashes, metadata, and 384-dimensional vectors in PostgreSQL with pgvector.
6. Synchronize changed and removed chunks when an article is re-ingested.

### Retrieval and answer generation

1. Embed the incoming question.
2. Restrict the search to the authenticated user's tenant and permitted knowledge visibility.
3. Run vector similarity search and PostgreSQL full-text search.
4. Combine ranks using Reciprocal Rank Fusion (RRF).
5. Apply the configured vector-distance gate; keyword matches can be admitted within the additional distance allowance.
6. Limit retrieval to five chunks and at most two chunks per parent article.
7. Send retrieved context and the question to Gemini with instructions to answer only from the supplied context.
8. Return an answer with source citation metadata, or abstain with `I don't know.` when the system cannot support an answer.

End users retrieve published knowledge-base articles. Agents and administrators can also retrieve internal knowledge-base content.

## Evaluation & benchmarks

The repository includes a 55-query golden dataset and separate Tenant B retrieval and cross-tenant test scripts. The figures below are reported local benchmark results supplied for this project; they are not automatically generated by the README or independently rerun as part of this documentation update.

### 1. Golden-set evaluation — Tenant A

Reported evaluation configuration: **21 knowledge-base articles and 55 queries**.

| Metric | Reported result |
|---|---:|
| Retrieval Hit@1 (answerable) | 41/42 (98%) |
| Retrieval Recall@5 (answerable) | 42/42 (100%) |
| Unanswerable / abstention accuracy | 100% |

The checked-in `golden_set.json` contains 55 entries: 42 marked answerable and 13 marked unanswerable. The reported scores above are presented as local run results; use the evaluation script to reproduce them against the matching database seed and knowledge-base state.

Run the evaluation:

```bash
python eval_golden.py
```

Retrieval-only mode:

```bash
python eval_golden.py --retrieval-only
```

### 2. Multi-tenant scale and isolation — Tenant B

Reported local stress-test configuration: **472 FastAPI documentation chunks** ingested into a secondary tenant.

| Measurement | Reported result |
|---|---:|
| Average retrieval latency | ~35.2 ms |
| Maximum retrieval latency | 143.7 ms |
| Tenant A golden-set degradation | 0% reported |
| Cross-tenant leakage checks | 0% reported |

The latency figures are from the reported local CPU run and are environment-dependent, not a production SLA.

The repository includes scripts for seeding Tenant B, running retrieval stress queries, and checking cross-tenant answers:

```bash
python -m scripts.seed_fastapi_tenant_b
python -m scripts.stress_test_b
python -m scripts.eval_tenant_b_llm
```

The Tenant B seeding script expects FastAPI Markdown documentation to be available at `/tmp/fastapi-docs/docs/en/docs`.

### 3. Automated tests

Run the test suite:

```bash
pytest -v
```

Run focused tests:

```bash
pytest tests/test_ai_api.py -v
pytest tests/test_isolation.py -v
```

These tests expect a configured database containing the relevant seeded tenants and knowledge-base data. They are not a substitute for a clean, isolated CI test database.

## Project structure

```text
ai-helpdesk/
├── app/
│   ├── routers/
│   │   ├── ai.py
│   │   ├── auth.py
│   │   ├── tickets.py
│   │   ├── users.py
│   │   ├── comments.py
│   │   └── timeline.py
│   ├── services/
│   │   ├── chunking.py
│   │   ├── embeddings.py
│   │   ├── generate.py
│   │   ├── ingest.py
│   │   └── retrieval.py
│   ├── auth.py
│   ├── db.py
│   ├── deps.py
│   ├── models.py
│   ├── queries.py
│   ├── schemas.py
│   └── main.py
├── alembic/
│   └── versions/
├── scripts/
│   ├── eval_tenant_b_llm.py
│   ├── seed_fastapi_tenant_b.py
│   ├── smoke_test.py
│   └── stress_test_b.py
├── tests/
│   ├── test_ai_api.py
│   └── test_isolation.py
├── eval_golden.py
├── golden_set.json
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── alembic.ini
└── ERRORS.md
```

## Technology stack

| Category | Technology |
|---|---|
| Language | Python |
| Backend framework | FastAPI |
| Validation | Pydantic |
| Relational database | PostgreSQL 16 |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Vector search | pgvector |
| Full-text search | PostgreSQL TSVECTOR |
| Embeddings | Sentence Transformers |
| Embedding model | all-MiniLM-L6-v2 (384 dimensions) |
| LLM | Google Gemini |
| Authentication | JWT |
| Password hashing | Argon2 |
| Containerization | Docker |
| Testing | Pytest, FastAPI TestClient |

## Future improvements

- ServiceNow data migration with idempotent imports, dry runs, and reconciliation.
- Knowledge-base CRUD and document upload APIs.
- Production deployment, structured logging, monitoring, and tracing.
- Rate limiting and stronger operational controls.
- More comprehensive automated tests with isolated test databases.
- Frontend dashboard for agents and end users.
- Expanded retrieval and answer-quality evaluation.

## Author

**Akshay Lokhande**

- GitHub: [Akshay-Lokhande-Dev](https://github.com/Akshay-Lokhande-Dev)
- Project: [AI Helpdesk](https://github.com/Akshay-Lokhande-Dev/ai-helpdesk)

---

Built as a hands-on project exploring backend engineering, ITSM workflows, multi-tenant systems, and practical Retrieval-Augmented Generation (RAG).
=======
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
>>>>>>> bfb395f (Add multi-tenant stress tests (FastAPI docs + 200 support FAQs) and 9 pytest integration tests)
