import time
from pathlib import Path
from sqlalchemy import text

from app.db import session_local
from app.models import KBArticle, ContentChunk
from app.services.ingest import ingest_kb_article

TENANT_B_ID = "c3d4e5f6-7a5b-4c4d-8e3f-9a0b1c2d3e4f"
DOCS_ROOT = Path("/tmp/fastapi-docs/docs/en/docs")
TARGET_DIRS = ["tutorial", "advanced"]
MAX_FILES = 50  # ~500-800 chunks, CPU pe fast run ke liye


def extract_title(md_text: str, fallback: str) -> str:
    for line in md_text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()[:200]
    return fallback.replace("-", " ").title()


def collect_md_files() -> list[Path]:
    files = []
    for sub in TARGET_DIRS:
        folder = DOCS_ROOT / sub
        if folder.exists():
            files.extend(sorted(folder.rglob("*.md")))
    valid = []
    for f in files:
        size = f.stat().st_size
        if 300 <= size <= 40_000:
            valid.append(f)
        if len(valid) >= MAX_FILES:
            break
    return valid


def main():
    md_files = collect_md_files()
    if not md_files:
        print(f"No markdown files found in {DOCS_ROOT}. Check sparse-checkout path.")
        return

    db = session_local()
    start = time.time()
    added = 0
    skipped = 0

    try:
        user_row = db.execute(
            text("SELECT id FROM users WHERE tenant_id::text = :tb LIMIT 1"),
            {"tb": TENANT_B_ID},
        ).fetchone()
        if not user_row:
            print(f"Tenant B ({TENANT_B_ID}) ka koi user nahi mila!")
            return
        created_by = str(user_row[0])

        print(f"Feeding {len(md_files)} FastAPI docs into Tenant B ({TENANT_B_ID})...")

        for idx, path in enumerate(md_files, start=1):
            rel_id = str(path.relative_to(DOCS_ROOT))
            existing = db.query(KBArticle).filter(
                KBArticle.tenant_id == TENANT_B_ID,
                KBArticle.source_system == "fastapi_docs",
                KBArticle.source_id == rel_id,
            ).first()
            if existing:
                skipped += 1
                continue

            body = path.read_text(encoding="utf-8", errors="ignore").strip()
            title = extract_title(body, path.stem)

            article = KBArticle(
                tenant_id=TENANT_B_ID,
                title=title,
                body=body,
                status="published",
                source_system="fastapi_docs",
                source_id=rel_id,
                created_by=created_by,
            )
            db.add(article)
            db.flush()
            ingest_kb_article(db, article)
            added += 1

            if idx % 10 == 0 or idx == len(md_files):
                print(f"  Progress: {idx}/{len(md_files)} files processed ({time.time() - start:.1f}s)")

        total_articles = db.query(KBArticle).filter(KBArticle.tenant_id == TENANT_B_ID).count()
        total_chunks = db.query(ContentChunk).filter(ContentChunk.tenant_id == TENANT_B_ID).count()
        print(
            f"\nDone in {time.time() - start:.1f}s! "
            f"Added={added}, Skipped={skipped} | "
            f"Tenant B Totals -> Articles: {total_articles}, Chunks: {total_chunks}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()