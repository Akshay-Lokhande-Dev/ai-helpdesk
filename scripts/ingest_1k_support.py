import time
from datasets import load_dataset
from sqlalchemy import text

from app.db import session_local
from app.models import KBArticle
from app.services.ingest import ingest_kb_article

TENANT_B_ID = "c3d4e5f6-7a5b-4c4d-8e3f-9a0b1c2d3e4f"
SOURCE_SYSTEM = "hf_bitext_1k"
TARGET_COUNT = 1000


def get_tenant_b_user(db):
    row = db.execute(
        text("SELECT id FROM users WHERE tenant_id::text = :tb LIMIT 1"),
        {"tb": TENANT_B_ID},
    ).fetchone()
    if not row:
        raise RuntimeError(f"Tenant B ({TENANT_B_ID}) ka koi user nahi mila!")
    return str(row[0])


def main():
    print("Loading Bitext customer support dataset...")
    ds = load_dataset(
        "bitext/Bitext-customer-support-llm-chatbot-training-dataset",
        split="train",
    )
    print(f"Loaded {len(ds)} total rows | Columns: {ds.column_names}")

    # Deduplicate by normalized instruction before ingesting
    seen = set()
    unique_rows = []
    for row in ds:
        q_text = str(row["instruction"]).strip()
        a_text = str(row["response"]).strip()
        if not q_text or not a_text:
            continue

        key = q_text.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append((q_text, a_text))

        if len(unique_rows) >= TARGET_COUNT:
            break

    print(f"Selected {len(unique_rows)} unique articles. Starting ingestion...")

    db = session_local()
    t0 = time.perf_counter()
    added = 0
    skipped = 0

    try:
        user_id = get_tenant_b_user(db)

        for idx, (q_text, a_text) in enumerate(unique_rows, start=1):
            source_id = f"bitext_{idx}"
            existing = (
                db.query(KBArticle)
                .filter(
                    KBArticle.tenant_id == TENANT_B_ID,
                    KBArticle.source_system == SOURCE_SYSTEM,
                    KBArticle.source_id == source_id,
                )
                .first()
            )
            if existing:
                skipped += 1
                continue

            article = KBArticle(
                tenant_id=TENANT_B_ID,
                title=q_text[:180],
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

            if idx % 100 == 0:
                elapsed = time.perf_counter() - t0
                print(f"  Progress: {idx}/{len(unique_rows)} | Added: {added} | Elapsed: {elapsed:.1f}s")

        total_time = time.perf_counter() - t0
        print("\n" + "=" * 60)
        print(f"Done! Added: {added}, Skipped: {skipped} in {total_time:.1f}s")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    main()