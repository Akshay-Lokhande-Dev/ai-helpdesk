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


def test_tenant_b_admin_cannot_see_tenant_a_data(db):
    # Admin role hone ke baad bhi Tenant A ka data leak nahi hona chahiye
    admin_b = SimpleNamespace(tenant_id=TENANT_B_ID, role="admin")

    wifi_rows = retrieve(db, admin_b, question="my laptop wifi wont connect pls help", limit=5, max_distance=MAX_DISTANCE)
    assert wifi_rows == []

    refund_rows = retrieve(db, admin_b, question="how do I request a refund for my subscription?", limit=5, max_distance=MAX_DISTANCE)
    titles = [r["title"].lower() for r in refund_rows]
    assert not any("refund" in t for t in titles)


def test_tenant_a_cannot_see_tenant_b_fastapi_docs(db):
    user_a = SimpleNamespace(tenant_id=TENANT_A_ID, role="end_user")
    rows = retrieve(db, user_a, question="how to enable CORS middleware in FastAPI?", limit=5, max_distance=MAX_DISTANCE)

    titles = [r["title"].lower() for r in rows]
    assert not any("cors" in t or "fastapi" in t or "middleware" in t for t in titles)


def test_out_of_domain_query_blocked_by_threshold(db):
    user_a = SimpleNamespace(tenant_id=TENANT_A_ID, role="end_user")
    rows = retrieve(db, user_a, question="give me a quick recipe for pasta", limit=5, max_distance=MAX_DISTANCE)

    assert rows == []

def test_tenant_b_admin_cannot_see_tenant_a_data(db):
    # Admin role hone ke baad bhi Tenant A ka koi bhi article ID leak nahi hona chahiye
    admin_b = SimpleNamespace(tenant_id=TENANT_B_ID, role="admin")

    tenant_a_ids = {
        str(row[0])
        for row in db.query(KBArticle.id).filter(KBArticle.tenant_id == TENANT_A_ID).all()
    }

    wifi_rows = retrieve(db, admin_b, question="my laptop wifi wont connect pls help", limit=5, max_distance=MAX_DISTANCE)
    assert wifi_rows == []

    refund_rows = retrieve(db, admin_b, question="how do I request a refund for my subscription?", limit=5, max_distance=MAX_DISTANCE)
    returned_ids = {str(r["parent_id"]) for r in refund_rows}
    assert returned_ids.isdisjoint(tenant_a_ids)
