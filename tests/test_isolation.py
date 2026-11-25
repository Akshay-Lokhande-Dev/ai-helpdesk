from types import SimpleNamespace
import pytest
from app.models import KBArticle

from app.db import session_local
from app.routers.ai import MAX_DISTANCE
from app.services.retrieval import retrieve

TENANT_A_ID = "9a45b7c2-5d3e-4f2a-8b1c-6d7e8f9a0b1c"
TENANT_B_ID = "c3d4e5f6-7a5b-4c4d-8e3f-9a0b1c2d3e4f"


@pytest.fixture
def db():
    session = session_local()
    try:
        yield session
    finally:
        session.close()


def test_tenant_a_retrieves_own_article(db):
    user_a = SimpleNamespace(tenant_id=TENANT_A_ID, role="end_user")
    rows = retrieve(db, user_a, question="how do I request a refund?", limit=5, max_distance=MAX_DISTANCE)

    assert len(rows) > 0
    titles = [r["title"].lower() for r in rows]
    assert any("refund" in t for t in titles)


def test_tenant_b_admin_retrieves_only_tenant_b_rows(db):
    # Tenant B can have its own FAQ article about refunds. A title containing
    # "refund" is not evidence of a Tenant A leak; assert the tenant IDs.
    admin_b = SimpleNamespace(tenant_id=TENANT_B_ID, role="admin")

    tenant_a_ids = {
        str(row[0])
        for row in db.query(KBArticle.id)
        .filter(KBArticle.tenant_id == TENANT_A_ID)
        .all()
    }

    wifi_rows = retrieve(
        db,
        admin_b,
        question="my laptop wifi wont connect pls help",
        limit=5,
        max_distance=MAX_DISTANCE,
    )
    refund_rows = retrieve(
        db,
        admin_b,
        question="how do I request a refund for my subscription?",
        limit=5,
        max_distance=MAX_DISTANCE,
    )

    returned_rows = wifi_rows + refund_rows
    assert all(str(row["tenant_id"]) == TENANT_B_ID for row in returned_rows)

    # Also assert that no known Tenant A KB article ID was returned.
    returned_article_ids = {
        str(row["parent_id"])
        for row in returned_rows
        if row["parent_type"] == "kb_article"
    }
    assert returned_article_ids.isdisjoint(tenant_a_ids)

def test_tenant_a_cannot_see_tenant_b_fastapi_docs(db):
    user_a = SimpleNamespace(tenant_id=TENANT_A_ID, role="end_user")
    rows = retrieve(db, user_a, question="how to enable CORS middleware in FastAPI?", limit=5, max_distance=MAX_DISTANCE)

    titles = [r["title"].lower() for r in rows]
    assert not any("cors" in t or "fastapi" in t or "middleware" in t for t in titles)


def test_out_of_domain_query_blocked_by_threshold(db):
    user_a = SimpleNamespace(tenant_id=TENANT_A_ID, role="end_user")
    rows = retrieve(db, user_a, question="give me a quick recipe for pasta", limit=5, max_distance=MAX_DISTANCE)

    assert rows == []
