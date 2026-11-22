from app.models import ContentChunk
from app.services.chunking import chunk_text, mask_pii, make_hash
from app.services.embeddings import embed_texts

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

def ingest_kb_article(db, article):
    body = (article.body or "").strip()
    visibility = "public" if article.status == "published" else "internal"

    # 1 hi query me saare existing chunks le aao (N+1 khatam)
    existing_rows = db.query(ContentChunk).filter(
        ContentChunk.tenant_id == article.tenant_id,
        ContentChunk.parent_type == "kb_article",
        ContentChunk.parent_id == article.id,
    ).all()
    existing_by_idx = {row.chunk_index: row for row in existing_rows}

    if not body:
        for row in existing_rows:
            db.delete(row)
        db.commit()
        return

    masked = mask_pii(body)
    chunks = chunk_text(masked)
    hashes = [make_hash(c) for c in chunks]

    # Sirf naye ya changed chunks ko hi embed ke liye nikalo
    to_embed_indices = []
    to_embed_texts = []

    for i, (chunk, h) in enumerate(zip(chunks, hashes)):
        row = existing_by_idx.get(i)
        if row and row.content_hash == h:
            # Content same hai, bas visibility sync kar do
            if row.visibility != visibility:
                row.visibility = visibility
        else:
            to_embed_indices.append(i)
            to_embed_texts.append(chunk)

    vecs = embed_texts(to_embed_texts) if to_embed_texts else []

    for i, vec in zip(to_embed_indices, vecs):
        row = existing_by_idx.get(i)
        if row:
            row.content_masked = chunks[i]
            row.content_hash = hashes[i]
            row.visibility = visibility
            row.embedding = vec
            row.embedding_model = EMBEDDING_MODEL
        else:
            db.add(ContentChunk(
                tenant_id=article.tenant_id,
                parent_type="kb_article",
                parent_id=article.id,
                chunk_index=i,
                content_masked=chunks[i],
                content_hash=hashes[i],
                visibility=visibility,
                embedding=vec,
                embedding_model=EMBEDDING_MODEL,
            ))

    # Agar article chhota ho gaya ho toh extra purane chunks uda do
    for idx, row in existing_by_idx.items():
        if idx >= len(chunks):
            db.delete(row)

    db.commit()