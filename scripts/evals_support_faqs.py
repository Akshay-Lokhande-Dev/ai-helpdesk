import time
from types import SimpleNamespace

from datasets import load_dataset

from app.db import session_local
from app.models import KBArticle
from app.routers.ai import MAX_DISTANCE
from app.services.ingest import ingest_kb_article
from app.services.retrieval import retrieve

TENANT_B_ID = "c3d4e5f6-7a5b-4c4d-8e3f-9a0b1c2d3e4f"
SOURCE_SYSTEM = "hf_support_faqs"


def get_or_create_user(db):
    from sqlalchemy import text
    row = db.execute(
        text("SELECT id FROM users WHERE tenant_id::text = :tb LIMIT 1"),
        {"tb": TENANT_B_ID},
    ).fetchone()
    if not row:
        raise RuntimeError(f"Tenant B ({TENANT_B_ID}) ka koi user nahi mila!")
    return str(row[0])


def main():
    ds = load_dataset("MakTek/Customer_support_faqs_dataset", split="train")
    print(f"Loaded {len(ds)} FAQ rows | Columns: {ds.column_names}")
    print("Sample row keys:", list(ds[0].keys()))

    # Column names auto-detect karo (question / answer variants ke liye)
    cols = {c.lower(): c for c in ds.column_names}
    q_col = next((cols[k] for k in cols if "question" in k or "query" in k or "prompt" in k), ds.column_names[0])
    a_col = next((cols[k] for k in cols if "answer" in k or "response" in k), ds.column_names[1])

    db = session_local()
    try:
        user_id = get_or_create_user(db)
        user_b = SimpleNamespace(tenant_id=TENANT_B_ID, role="end_user")

        added = 0
        eval_pairs = []

        for idx, row in enumerate(ds):
            q_text = str(row[q_col]).strip()
            a_text = str(row[a_col]).strip()
            if not q_text or not a_text:
                continue

            source_id = f"faq_{idx}"
            title = q_text[:180]
            eval_pairs.append((source_id, title, q_text))

            existing = (
                db.query(KBArticle)
                .filter(
                    KBArticle.tenant_id == TENANT_B_ID,
                    KBArticle.source_system == SOURCE_SYSTEM,
                    KBArticle.source_id == source_id,
                )
                .first()
            )
            if not existing:
                article = KBArticle(
                    tenant_id=TENANT_B_ID,
                    title=title,
                    body=f"Question: {q_text}\n\nAnswer: {a_text}",
                    status="published",
                    source_system=SOURCE_SYSTEM,
                    source_id=source_id,
                    created_by=user_id,
                )
                db.add(article)
                db.flush()
                ingest_kb_article(db, article)
                added += 1

        print(f"Ingested {added} new FAQ articles into Tenant B. Evaluating {len(eval_pairs)} queries...")

        # Warmup
        if eval_pairs:
            retrieve(db, user_b, question=eval_pairs[0][2], limit=5, max_distance=MAX_DISTANCE)

        hit1 = 0
        hit5 = 0
        latencies = []

        for _, expected_title, q_text in eval_pairs:
            t0 = time.perf_counter()
            rows = retrieve(db, user_b, question=q_text, limit=5, max_distance=MAX_DISTANCE)
            latencies.append((time.perf_counter() - t0) * 1000)

            titles = [r["title"] for r in rows]
            if titles and titles[0] == expected_title:
                hit1 += 1
            if expected_title in titles:
                hit5 += 1

        total = len(eval_pairs)
        avg_ms = sum(latencies) / total if total else 0.0
        print("\n" + "=" * 60)
        print(f"Support FAQs Retrieval Eval ({total} queries):")
        print(f"  Hit@1   : {hit1}/{total} ({(hit1/total)*100:.1f}%)")
        print(f"  Recall@5: {hit5}/{total} ({(hit5/total)*100:.1f}%)")
        print(f"  Avg Lat : {avg_ms:.1f}ms")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    main()