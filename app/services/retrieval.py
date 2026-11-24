from sqlalchemy import text
from app.services.embeddings import EMBEDDING_MODEL, embed_texts

import re

def _or_query(q: str) -> str:
    words = re.findall(r"[A-Za-z0-9]{3,}", q.lower())
    return " | ".join(dict.fromkeys(words))

INTERNAL_ROLES = {"agent", "admin"}

HYBRID_SQL = text("""
WITH allowed AS (
    SELECT c.id, c.content_masked, c.parent_type, c.parent_id, c.chunk_index, c.embedding, c.tsv,k.title
    FROM content_chunks c
    LEFT JOIN kb_articles k
      ON c.parent_type = 'kb_article' AND k.id = c.parent_id AND k.tenant_id = c.tenant_id
    WHERE c.tenant_id = CAST(:tenant AS uuid)
      AND c.embedding_model = :model
      AND (:include_internal OR (c.parent_type = 'kb_article' AND k.status = 'published'))
),
vec AS (
    SELECT id,
           embedding <=> CAST(:qvec AS vector) AS distance,
           row_number() OVER (ORDER BY embedding <=> CAST(:qvec AS vector)) AS rnk
    FROM allowed
    WHERE embedding IS NOT NULL
    ORDER BY distance
    LIMIT :pool
),
kw AS (
    SELECT a.id,
           row_number() OVER (ORDER BY ts_rank(a.tsv, q.query) DESC) AS rnk
    FROM allowed a, to_tsquery('english', :q_or) AS q(query)
    WHERE a.tsv @@ q.query
    ORDER BY ts_rank(a.tsv, q.query) DESC
    LIMIT :pool
)
SELECT a.id, a.content_masked, a.parent_type, a.parent_id, a.chunk_index,a.title,
       v.distance,
       COALESCE(1.0 / (60 + v.rnk), 0) + COALESCE(1.0 / (60 + k.rnk), 0) AS score
FROM allowed a
LEFT JOIN vec v ON v.id = a.id
LEFT JOIN kw  k ON k.id = a.id
WHERE v.id IS NOT NULL AND (
    v.distance <= :max_distance
    OR (k.id IS NOT NULL AND v.distance <= :max_distance + 0.15)
)
ORDER BY score DESC
LIMIT :fetch
""")

def retrieve(db, current_user, question: str, limit: int = 5,
             max_distance: float = 0.65, pool: int = 20) -> list[dict]:
    question = (question or "").strip()
    if not question:
        return []

    q_vec = embed_texts([question])[0]
    params = {
        "tenant": str(current_user.tenant_id),
        "include_internal": current_user.role in INTERNAL_ROLES,
        "model": EMBEDDING_MODEL,
        "qvec": "[" + ",".join(map(str, q_vec)) + "]",
        "q_or": _or_query(question),
        "pool": pool,
        "fetch": limit * 4,
        "max_distance": max_distance,
    }
    rows = [dict(r) for r in db.execute(HYBRID_SQL, params).mappings().all()]
    counts, out = {}, []
    for r in rows:
        key = (r["parent_type"], r["parent_id"])
        if counts.get(key, 0) >= 2:
            continue
        counts[key] = counts.get(key, 0) + 1
        out.append(r)
        if len(out) == limit:
            break
    return out