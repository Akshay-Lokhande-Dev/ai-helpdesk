import time
from types import SimpleNamespace

from app.db import session_local
from app.routers.ai import MAX_DISTANCE
from app.services.retrieval import retrieve

TENANT_B_ID = "c3d4e5f6-7a5b-4c4d-8e3f-9a0b1c2d3e4f"

QUERIES = [
    # 8 real messy FastAPI queries
    ("IN-DOMAIN", "how do I add optional query parameters with default values?"),
    ("IN-DOMAIN", "how to validate JSON request body using Pydantic BaseModel?"),
    ("IN-DOMAIN", "how does Depends() dependency injection work in FastAPI?"),
    ("IN-DOMAIN", "how to set up OAuth2 with Password and Bearer JWT tokens?"),
    ("IN-DOMAIN", "how to run background tasks after returning a response?"),
    ("IN-DOMAIN", "how do I enable CORS middleware for frontend requests?"),
    ("IN-DOMAIN", "how to upload files using UploadFile?"),
    ("IN-DOMAIN", "how to raise HTTPException with custom status codes?"),
    # 2 cross-tenant leak checks (Tenant A data — MUST NOT leak)
    ("LEAK-CHECK", "how do I request a refund for my subscription?"),
    ("LEAK-CHECK", "my laptop wifi wont connect pls help"),
]


def main():
    db = session_local()
    user_b = SimpleNamespace(tenant_id=TENANT_B_ID, role="end_user")
    latencies = []

    try:
        # Warmup: embedding model pehli baar load hone ka time exclude karne ke liye
        retrieve(db, user_b, "warmup query", limit=5, max_distance=MAX_DISTANCE)

        for tag, q in QUERIES:
            t0 = time.perf_counter()
            rows = retrieve(db, user_b, question=q, limit=5, max_distance=MAX_DISTANCE)
            ms = (time.perf_counter() - t0) * 1000
            latencies.append(ms)

            titles = list(dict.fromkeys(r["title"] for r in rows))[:3]
            top_dist = round(rows[0]["distance"], 3) if rows and rows[0].get("distance") is not None else None
            print(f"[{tag:10s}] {ms:6.1f}ms | dist={str(top_dist):5s} | {q}")
            print(f"             -> Top titles: {titles}")

        avg_ms = sum(latencies) / len(latencies)
        max_ms = max(latencies)
        print("\n" + "=" * 60)
        print(f"Tenant B Retrieval Latency (472 chunks): avg={avg_ms:.1f}ms | max={max_ms:.1f}ms")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    main()