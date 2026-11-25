import time
from types import SimpleNamespace
from sqlalchemy import text

from app.db import session_local
from app.models import KBArticle
from app.routers.ai import MAX_DISTANCE
from app.services.retrieval import retrieve

TENANT_B_ID = "c3d4e5f6-7a5b-4c4d-8e3f-9a0b1c2d3e4f"
SOURCE_SYSTEM = "hf_bitext_1k"
SAMPLE_SIZE = 100


def main():
    db = session_local()
    try:
        # Total chunks count check karo
        total_chunks = db.execute(text("SELECT COUNT(*) FROM content_chunks")).scalar()
        tenant_b_chunks = db.execute(
            text("SELECT COUNT(*) FROM content_chunks WHERE tenant_id::text = :tb"),
            {"tb": TENANT_B_ID},
        ).scalar()

        # Deterministic 100 articles uthao (Before & After dono mein exact same queries)
        articles = (
            db.query(KBArticle)
            .filter(
                KBArticle.tenant_id == TENANT_B_ID,
                KBArticle.source_system == SOURCE_SYSTEM,
            )
            .order_by(KBArticle.source_id)
            .limit(SAMPLE_SIZE)
            .all()
        )

        user_b = SimpleNamespace(tenant_id=TENANT_B_ID, role="end_user")

        # Warmup query (embedding model & DB cache warm karne ke liye)
        if articles:
            retrieve(db, user_b, question=articles[0].title, limit=5, max_distance=MAX_DISTANCE)

        hit1 = 0
        hit5 = 0
        latencies = []

        for art in articles:
            t0 = time.perf_counter()
            rows = retrieve(db, user_b, question=art.title, limit=5, max_distance=MAX_DISTANCE)
            latencies.append((time.perf_counter() - t0) * 1000)

            titles = [r["title"] for r in rows]
            if titles and titles[0] == art.title:
                hit1 += 1
            if art.title in titles:
                hit5 += 1

        latencies.sort()
        total = len(articles)
        avg_ms = sum(latencies) / total
        p50_ms = latencies[int(total * 0.50)]
        p95_ms = latencies[int(total * 0.95)]
        max_ms = latencies[-1]

        print("\n" + "=" * 60)
        print(f"Chunks in DB: {total_chunks} | Tenant B Chunks: {tenant_b_chunks}")
        print(f"Benchmark ({total} queries from {SOURCE_SYSTEM}):")
        print(f"  Hit@1    : {hit1}/{total} ({(hit1/total)*100:.1f}%)")
        print(f"  Recall@5 : {hit5}/{total} ({(hit5/total)*100:.1f}%)")
        print(f"  Avg Lat  : {avg_ms:.1f}ms")
        print(f"  P50 Lat  : {p50_ms:.1f}ms")
        print(f"  P95 Lat  : {p95_ms:.1f}ms")
        print(f"  Max Lat  : {max_ms:.1f}ms")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    main()