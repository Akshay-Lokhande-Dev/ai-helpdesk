import time
from types import SimpleNamespace

from app.db import session_local
from app.routers.ai import MAX_DISTANCE
from app.services.retrieval import retrieve
from app.services.generate import generate_answer

TENANT_B_ID = "c3d4e5f6-7a5b-4c4d-8e3f-9a0b1c2d3e4f"

TESTS = [
    ("ANSWERABLE", "how do I enable CORS middleware in FastAPI?"),
    ("ANSWERABLE", "how to run background tasks after returning a response?"),
    ("ANSWERABLE", "how to upload files using UploadFile in FastAPI?"),
    ("UNANSWERABLE", "how do I request a refund for my subscription?"),  # Tenant A data
    ("UNANSWERABLE", "how do I deploy Django on Kubernetes?"),           # Out of domain
]


def main():
    db = session_local()
    user_b = SimpleNamespace(tenant_id=TENANT_B_ID, role="end_user")
    try:
        for kind, q in TESTS:
            rows = retrieve(db, user_b, question=q, limit=5, max_distance=MAX_DISTANCE)
            if not rows:
                ans, abstained, titles = "I don't know.", True, []
            else:
                res = generate_answer(q, rows)
                ans = res["text"]
                abstained = res["abstained"]
                titles = list(dict.fromkeys(r["title"] for r in rows))[:2]

            status = "PASS" if (kind == "UNANSWERABLE") == abstained else "FAIL"
            print(f"[{status}] ({kind}) {q}")
            print(f"       Abstained={abstained} | Citations={titles}")
            print(f"       Answer: {ans[:180].replace(chr(10), ' ')}\n")
            time.sleep(1.5)  # rate limit safe
    finally:
        db.close()


if __name__ == "__main__":
    main()