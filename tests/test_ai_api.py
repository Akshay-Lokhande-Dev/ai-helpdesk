from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient

import app.routers.ai as ai_router
from app.deps import get_current_user
from app.main import app

TENANT_A_ID = "9a45b7c2-5d3e-4f2a-8b1c-6d7e8f9a0b1c"
TENANT_B_ID = "c3d4e5f6-7a5b-4c4d-8e3f-9a0b1c2d3e4f"
USER_A_ID = "861fdcb0-c26b-40fc-8cf2-4d62b2729f7e"

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def _override_user(tenant_id: str, role: str = "end_user"):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=USER_A_ID,
        tenant_id=tenant_id,
        role=role,
    )


def test_ai_ask_requires_auth():
    res = client.post("/ai/ask", json={"question": "how do I request a refund?"})
    assert res.status_code in (401, 403)


def test_ai_ask_answerable_returns_citations_and_similarity(monkeypatch):
    _override_user(TENANT_A_ID, role="end_user")

    def fake_generate(question, rows):
        assert len(rows) > 0
        return {
            "text": "Email billing@company.com from the Account Owner email to request a refund.",
            "abstained": False,
            "fallback": False,
        }

    monkeypatch.setattr(ai_router, "generate_answer", fake_generate)

    res = client.post("/ai/ask", json={"question": "how do I request a refund?"})
    assert res.status_code == 200
    body = res.json()

    assert "billing@company.com" in body["answer"]
    assert len(body["citations"]) > 0
    assert any("refund" in (c["title"] or "").lower() for c in body["citations"])
    assert body["similarity"] is not None and 0 < body["similarity"] <= 1
    assert body["degraded"] is False


def test_ai_ask_out_of_domain_abstains_without_calling_llm(monkeypatch):
    _override_user(TENANT_A_ID, role="end_user")

    def should_not_call_llm(question, rows):
        raise AssertionError("generate_answer should not be called when retrieval returns no rows")

    monkeypatch.setattr(ai_router, "generate_answer", should_not_call_llm)

    res = client.post("/ai/ask", json={"question": "give me a quick recipe for pasta"})
    assert res.status_code == 200
    body = res.json()

    assert body["answer"] == "I don't know."
    assert body["citations"] == []
    assert body["similarity"] is None
    assert body["degraded"] is False


def test_ai_ask_llm_abstention_clears_citations(monkeypatch):
    _override_user(TENANT_A_ID, role="end_user")

    def fake_abstain(question, rows):
        assert len(rows) > 0  # In-domain query retrieved chunks, LLM chooses to abstain
        return {"text": "I don't know.", "abstained": True, "fallback": False}

    monkeypatch.setattr(ai_router, "generate_answer", fake_abstain)

    res = client.post(
        "/ai/ask",
        json={"question": "do you offer HIPAA BAA compliance agreements on the Pro plan?"},
    )
    assert res.status_code == 200
    body = res.json()

    assert body["answer"] == "I don't know."
    assert body["citations"] == []
    assert body["similarity"] is None
    assert body["degraded"] is False


def test_ai_ask_cross_tenant_isolation_over_http(monkeypatch):
    _override_user(TENANT_B_ID, role="admin")

    def should_not_call_llm(question, rows):
        raise AssertionError("Tenant B admin should get 0 rows for Tenant A WiFi article")

    monkeypatch.setattr(ai_router, "generate_answer", should_not_call_llm)

    res = client.post("/ai/ask", json={"question": "my laptop wifi wont connect pls help"})
    assert res.status_code == 200
    body = res.json()

    assert body["answer"] == "I don't know."
    assert body["citations"] == []

def test_ai_ask_returns_only_sources_cited_by_generation(monkeypatch):
    _override_user(TENANT_A_ID, role="end_user")

    rows = [
        {
            "title": "Uncited article",
            "parent_type": "kb_article",
            "parent_id": "11111111-1111-4111-8111-111111111111",
            "chunk_index": 0,
            "distance": 0.2,
            "content_masked": "Unrelated source text.",
        },
        {
            "title": "Cited article",
            "parent_type": "kb_article",
            "parent_id": "22222222-2222-4222-8222-222222222222",
            "chunk_index": 1,
            "distance": 0.4,
            "content_masked": "Relevant source text.",
        },
    ]

    monkeypatch.setattr(ai_router, "retrieve", lambda *args, **kwargs: rows)
    monkeypatch.setattr(
        ai_router,
        "generate_answer",
        lambda question, retrieved: {
            "text": "Grounded answer. [S2]",
            "abstained": False,
            "fallback": False,
            "source_indexes": [1],
        },
    )

    response = client.post("/ai/ask", json={"question": "Tell me about this issue"})
    assert response.status_code == 200
    body = response.json()

    assert body["answer"] == "Grounded answer. [S2]"
    assert len(body["citations"]) == 1
    assert body["citations"][0]["title"] == "Cited article"
    assert body["similarity"] == 0.6
