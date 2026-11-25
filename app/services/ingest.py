from app.models import ContentChunk
from app.services.chunking import chunk_text, make_hash, mask_pii
from app.services.embeddings import EMBEDDING_MODEL, embed_texts


def ingest_kb_article(db, article, *, allowed_emails: set[str] | None = None) -> None:
    """Synchronize an article's sanitized chunks and embeddings.

    Business contact addresses that are intentionally public can be passed in
    allowed_emails. Other email addresses and phone numbers are masked before
    chunking, hashing, embedding, storage, and later LLM prompting.
    """
    body = (article.body or "").strip()
    clean_title = (article.title or "").strip()

    existing_rows = (
        db.query(ContentChunk)
        .filter(
            ContentChunk.tenant_id == article.tenant_id,
            ContentChunk.parent_type == "kb_article",
            ContentChunk.parent_id == article.id,
        )
        .all()
    )
    existing_by_idx = {row.chunk_index: row for row in existing_rows}

    if not body:
        for row in existing_rows:
            db.delete(row)
        db.commit()
        return

    visibility = "public" if article.status == "published" else "internal"

    # Mask before chunking so an email address or phone number cannot evade
    # masking merely because it straddles a chunk boundary.
    safe_title = mask_pii(clean_title, allowed_emails)
    safe_body = mask_pii(body, allowed_emails)
    chunks = chunk_text(safe_body)
    combined_chunks = [f"{safe_title}\n\n{chunk}" for chunk in chunks]
    hashes = [make_hash(chunk) for chunk in combined_chunks]

    to_embed_indices = []
    to_embed_texts = []

    for index, content_hash in enumerate(hashes):
        row = existing_by_idx.get(index)
        if (
            row
            and row.content_hash == content_hash
            and row.embedding_model == EMBEDDING_MODEL
            and row.embedding is not None
        ):
            if row.visibility != visibility:
                row.visibility = visibility
        else:
            to_embed_indices.append(index)
            to_embed_texts.append(combined_chunks[index])

    vectors = embed_texts(to_embed_texts) if to_embed_texts else []
    if len(vectors) != len(to_embed_indices):
        raise RuntimeError(
            "Embedding service returned a different number of vectors than input chunks"
        )

    for index, vector in zip(to_embed_indices, vectors):
        row = existing_by_idx.get(index)
        if row:
            row.content_masked = combined_chunks[index]
            row.content_hash = hashes[index]
            row.visibility = visibility
            row.embedding = vector
            row.embedding_model = EMBEDDING_MODEL
        else:
            db.add(
                ContentChunk(
                    tenant_id=article.tenant_id,
                    parent_type="kb_article",
                    parent_id=article.id,
                    chunk_index=index,
                    content_masked=combined_chunks[index],
                    content_hash=hashes[index],
                    visibility=visibility,
                    embedding=vector,
                    embedding_model=EMBEDDING_MODEL,
                )
            )

    for index, row in existing_by_idx.items():
        if index >= len(combined_chunks):
            db.delete(row)

    db.commit()
