# AI Helpdesk

A multi-tenant IT service management (ITSM) backend built with Python, FastAPI, and PostgreSQL. It provides tenant-scoped ticket workflows and an AI knowledge assistant that retrieves relevant knowledge-base (KB) content before generating an answer.

**Project status: in progress.** Ticket management, authentication, role-based access, comments, activity timelines, KB ingestion services, hybrid retrieval, and the authenticated AI question endpoint are implemented. ServiceNow migration, a public KB management API, a frontend, and production deployment are not implemented.

## What works today

- **Multi-tenant data model:** tenants, users, tickets, ticket comments, ticket events, KB articles, and content chunks in PostgreSQL using SQLAlchemy.
- **Authentication and authorization:** JWT access tokens, Argon2 password hashing, and admin, agent, and end-user roles.
- **Ticket workflows:** create, list, and retrieve visible tickets; agents and admins can update ticket state, priority, assignee, and resolution.
- **Comments and timeline:** public/internal comments and a timeline combining comments with ticket events. End users receive filtered views.
- **Tenant-scoped access:** ticket queries and AI retrieval are scoped to the authenticated user's tenant. End users see their own tickets; agents and admins have broader access within their tenant.
- **KB ingestion service:** chunking, content hashing, embedding generation, and synchronization of stored chunks when articles change or are re-ingested.
- **AI question endpoint:** authenticated `POST /ai/ask` retrieves tenant-scoped KB context, generates a grounded answer using Gemini, and returns citation metadata.
- **Hybrid retrieval:** pgvector semantic search and PostgreSQL full-text search (FTS) combined using Reciprocal Rank Fusion (RRF).
- **Evaluation and tests:** golden-set evaluation, Tenant B retrieval stress-test scripts, cross-tenant isolation checks, and AI API tests.

## AI and RAG architecture

### Request flow

1. An authenticated user sends a question to `POST /ai/ask`.
2. The question is embedded using `all-MiniLM-L6-v2`.
3. Retrieval is restricted in SQL to the authenticated user's tenant and the knowledge visibility allowed for their role.
4. The retrieval query runs vector similarity search with pgvector and keyword search using PostgreSQL FTS.
5. The two ranked result sets are combined using Reciprocal Rank Fusion (RRF).
6. A hybrid distance gate filters weak matches. FTS matches can be included only when their vector distance is within the configured additional allowance.
7. Retrieval returns up to five chunks, with a maximum of two chunks per parent article.
8. Retrieved context and the question are sent to Gemini with instructions to answer only from the supplied context.
9. The API returns the answer, citation metadata, similarity where available, and a `degraded` flag.

### Retrieval guardrails

- **SQL-level tenant isolation:** the retrieval query filters content chunks by the authenticated user's tenant before ranking. A user from another tenant cannot retrieve another tenant's KB content, including when the user has an admin role.
- **Role-aware KB visibility:** end users retrieve published KB articles; agents and admins can also retrieve internal KB content.
- **Hybrid distance gate:** vector distance is checked against `max_distance`. An FTS match may be rescued only when its distance is no greater than `max_distance + 0.15`.
- **Parent-level diversity:** no more than two chunks from the same parent article are returned.
- **Abstention:** if retrieval returns no relevant context, the API responds with `I don't know.` without invoking the LLM. The Gemini system instruction also requires `I don't know.` when the supplied context does not contain the answer.

Cross-tenant requests are blocked by tenant-scoped SQL retrieval; the LLM is not used to enforce tenant boundaries. The abstention response is the user-facing behaviour when no permitted context is available.

### Degraded fallback

If `GEMINI_API_KEY` is missing or Gemini generation fails, the generation service returns the top retrieved chunk as a fallback. The API sets `degraded: true` to indicate that the response did not come from normal Gemini generation. This fallback is not equivalent to a generated, context-synthesized answer.

### Citation response

The AI response includes citation metadata for the retrieved source, including `parent_type`, `parent_id`, `title`, and `chunk_index`. It also includes a similarity value where available and the `degraded` status.

## Evaluation-driven engineering

Evaluation exposed retrieval and answer-generation edge cases. The following changes were made in response to those failures:

### 1. Keep useful chunks from the same article

Retrieval originally risked dropping later troubleshooting or footer content when deduplicating by article. The per-parent limit was changed to allow up to **two chunks per article**, preserving relevant sections such as `chunk_index=1` without allowing one article to dominate the context.

### 2. Gate keyword matches using vector distance

FTS can find exact technical terms even when semantic similarity is weaker, but keyword matches alone can introduce unrelated content. The hybrid query therefore allows a keyword match only when its vector distance is within `max_distance + 0.15`. This helped retain exact-term matches such as Okta metadata XML while filtering unrelated queries.

### 3. Distinguish unsupported features from missing information

The Gemini system prompt was revised to answer clearly when retrieved documentation explicitly says a feature is unsupported or a user is ineligible. Examples include SMS 2FA and auto-renewal refunds. This avoids treating an explicit negative answer as a reason to abstain.

### 4. Preserve official contact details in curated KB content

`mask_pii()` was removed from curated KB article ingestion so legitimate support and billing email addresses remain searchable and available in answers. PII masking remains applied to incoming user questions before they are sent to Gemini.

## Evaluation and benchmarks

The following are reported local results for the datasets and configurations described. Retrieval latency depends on the machine, database state, and embedding model warm-up; it should not be interpreted as a production SLA.

## Vector Indexing & Scale Benchmark (pgvector HNSW)

To validate retrieval performance at scale, 1,000 deduplicated customer support articles (`bitext/Bitext-customer-support-llm-chatbot-training-dataset`) were ingested into Tenant B, bringing the `content_chunks` table to **2,176 chunks** (2,144 in Tenant B).

An HNSW index (`vector_cosine_ops`, `m=16`, `ef_construction=64`) was added via Alembic migration and verified using PostgreSQL `EXPLAIN ANALYZE` and a deterministic 100-query benchmark:

| Metric (2,176 Chunks) | Without Index (`Seq Scan`) | With HNSW Index (`Index Scan`) | Result |
| :--- | :--- | :--- | :--- |
| **Query Plan** | `Seq Scan` + `top-N heapsort` | `Index Scan using ix_content_chunks_embedding_hnsw` | O(N) → O(log N) |
| **Pure SQL Execution Time** | ~9.04 ms | **1.45 ms** | **~6.2x faster** |
| **Recall@5 (100-query eval)** | 43.0% | **43.0%** | **0% recall loss** |
| **Hit@1 (100-query eval)** | 27.0% | **27.0%** | Consistent |

### Key Engineering Findings
* **Database vs. CPU Bottleneck:** End-to-end Python retrieval latency (~25–42 ms) is dominated (~95%) by local CPU query embedding (`all-MiniLM-L6-v2`), while PostgreSQL vector search takes ~1.45 ms.
* **Multi-Tenant Post-Filtering:** `EXPLAIN ANALYZE` confirmed that `pgvector` traverses the HNSW graph first and post-filters on `tenant_id` (`Rows Removed by Filter: 6`), highlighting when `hnsw.iterative_scan` becomes necessary for smaller tenants at larger scale.

### Tenant A — Golden Set

**Dataset:** 21 KB articles and 55 questions: 42 answerable and 13 unanswerable.

| Metric | Result |
|---|---:|
| Retrieval Hit@1 (answerable) | 41/42 (98%) |
| Retrieval Recall@5 (answerable) | 42/42 (100%) |
| Unanswerable / abstention accuracy | 100% |

The checked-in `golden_set.json` contains 55 queries. Run the evaluation against a database seeded with the matching Tenant A KB content:

```bash
python eval_golden.py
python eval_golden.py --retrieval-only
```

### Tenant B — FastAPI documentation stress test

**Dataset:** 50 real-world FastAPI Markdown documents, ingested as 472 chunks in Tenant B.

| Measurement | Reported result |
|---|---:|
| Average retrieval latency (CPU) | ~35.2 ms |
| Maximum retrieval latency (CPU) | 143.7 ms |
| Degradation to Tenant A golden-set results | 0% |
| End-to-end Tenant B LLM evaluation | 5/5 passed |

The stress test checks in-domain FastAPI questions and cross-tenant retrieval attempts. The separate LLM evaluation is implemented in `scripts/eval_tenant_b_llm.py`.

```bash
python -m scripts.seed_fastapi_tenant_b
python -m scripts.stress_test_b
python -m scripts.eval_tenant_b_llm
```

The FastAPI seeding script expects Markdown documentation under `/tmp/fastapi-docs/docs/en/docs`.

### Tenant B — Customer support FAQ retrieval benchmark

**Dataset:** `MakTek/Customer_support_faqs_dataset`, with 200 FAQ articles and approximately 672 total chunks in Tenant B.

| Metric | Reported result |
|---|---:|
| Retrieval Hit@1 | 194/200 (97.0%) |
| Retrieval Recall@5 | 200/200 (100.0%) |
| Average retrieval latency (CPU) | ~225.0 ms |

This is a retrieval benchmark: each FAQ question is used to check whether its corresponding article is retrieved. It does not measure generated-answer correctness.

```bash
python -m scripts.evals_support_faqs
```

### Cross-tenant isolation checks

Reported checks found no cross-tenant data leakage across:

- SQL retrieval constrained by tenant ID.
- `parent_id` disjointness assertions between tenant datasets, including queries performed as a Tenant B admin.
- End-to-end Tenant B LLM evaluation, where cross-tenant content is not available as retrieved context.

These checks provide evidence for the tested datasets and queries; they are not a formal security audit.

## Tests

Run the test suite:

```bash
pytest -v
```

The checked-in tests cover:

- `tests/test_isolation.py`: retrieval of a tenant's own content, cross-tenant isolation for Tenant B admins, tenant separation for FastAPI documentation, and out-of-domain threshold blocking.
- `tests/test_ai_api.py`: authentication enforcement for `/ai/ask`, citation-bearing responses (with mocked generation), retrieval-level abstention, LLM-level abstention, and HTTP-level tenant isolation.

**Test-count note:** the current checked-in `tests/test_isolation.py` defines `test_tenant_b_admin_cannot_see_tenant_a_data` twice. The later definition shadows the earlier one during Python module import. Together, the two test files therefore contain eight distinct collected test functions as currently committed. A reported 9/9 run may refer to a different local revision; rename or restore the additional test before describing the current repository state as 9/9.

Tests use a configured database with the expected tenant and KB seed data. They are not currently set up as isolated, self-provisioning CI tests.

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Application health check |
| GET | `/db-check` | Database connectivity check |
| POST | `/auth/login` | Authenticate using tenant slug, email, and password |
| GET | `/auth/me` | Get the current authenticated user |
| POST | `/users` | Create a user (admin only) |
| GET | `/users/test/{user_id}` | Development/test user lookup; currently unauthenticated |
| GET | `/tickets` | List up to 50 tickets visible to the current user |
| POST | `/tickets` | Create a ticket for the current user |
| GET | `/tickets/{ticket_number}` | Retrieve a visible ticket by ticket number |
| PATCH | `/tickets/{ticket_id}` | Update ticket fields (agent/admin only) |
| POST | `/tickets/{ticket_id}/comments` | Add a comment |
| GET | `/tickets/{ticket_id}/comments` | List comments visible to the current user |
| GET | `/tickets/{ticket_id}/timeline` | Retrieve the ticket activity timeline |
| POST | `/ai/ask` | Retrieve KB context and generate an AI-assisted answer |

Interactive API documentation is available at `http://127.0.0.1:8000/docs` when the application is running.

## Technology

| Area | Technology |
|---|---|
| Language | Python 3.12 |
| API framework | FastAPI |
| Validation | Pydantic |
| Database | PostgreSQL 16 |
| ORM and migrations | SQLAlchemy, Alembic |
| Vector search | pgvector |
| Full-text search | PostgreSQL TSVECTOR / FTS |
| Embeddings | Sentence Transformers, `all-MiniLM-L6-v2` (384 dimensions) |
| LLM | Google Gemini |
| Authentication | JWT |
| Password hashing | Argon2 |
| Local database environment | Docker Compose |
| Tests | Pytest, FastAPI TestClient |

## Run locally

### Requirements

- Python 3.12
- Docker and Docker Compose
- A Gemini API key for normal LLM answer generation

### Setup

```bash
git clone https://github.com/Akshay-Lokhande-Dev/ai-helpdesk.git
cd ai-helpdesk

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and add the values listed below.

docker compose up -d
alembic upgrade head
uvicorn app.main:app --reload
```

### Environment variables

Set the database credentials and connection string in `.env`. The Compose file exposes PostgreSQL on host port `5433`:

```env
POSTGRES_USER=your_database_user
POSTGRES_PASSWORD=your_database_password
POSTGRES_DB=ai_helpdesk
DATABASE_URL=postgresql+psycopg://your_database_user:your_database_password@localhost:5433/ai_helpdesk
SECRET_KEY=your_long_random_secret
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

`SECRET_KEY` is needed for JWT signing. `GEMINI_API_KEY` enables Gemini generation; without it, the service uses the degraded top-chunk fallback described above. Do not commit `.env` or real credentials.

### Useful commands

```bash
# Start the database
docker compose up -d

# Apply database migrations
alembic upgrade head

# Run the API
uvicorn app.main:app --reload

# Run tests
pytest -v

# Run the golden-set evaluation
python eval_golden.py
```

## Project structure

```text
ai-helpdesk/
├── app/
│   ├── routers/
│   │   ├── ai.py
│   │   ├── auth.py
│   │   ├── comments.py
│   │   ├── tickets.py
│   │   ├── timeline.py
│   │   └── users.py
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
│   ├── evals_support_faqs.py
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

## Current limitations

- No ServiceNow migration or import/reconciliation workflow yet.
- No public KB CRUD or document-upload API; KB ingestion is currently implemented as an internal service and scripts.
- No frontend UI.
- No production deployment, production monitoring, or observability setup.
- `GET /users/test/{user_id}` is currently unauthenticated and should be removed or protected before production use.
- Ticket numbers are generated as random `T-XXXXXXXX` identifiers.

## Author

**Akshay Lokhande**

- GitHub: [Akshay-Lokhande-Dev](https://github.com/Akshay-Lokhande-Dev)
- Repository: [ai-helpdesk](https://github.com/Akshay-Lokhande-Dev/ai-helpdesk)

---

Built as a practical project to explore backend engineering, tenant-aware ITSM workflows, hybrid retrieval, and evaluation-driven RAG development.