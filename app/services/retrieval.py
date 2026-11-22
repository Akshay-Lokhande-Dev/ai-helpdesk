from sqlalchemy import text
from app.services.embeddings import EMBEDDING_MODEL, embed_texts

INTERNAL_ROLES = {"agent", "admin"}

HYBRID_SQL = text("""
WITH allowed AS (
    SELECT c.id, c.content_masked, c.parent_type, c.parent_id, c.chunk_index, c.embedding, c.tsv
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
    FROM allowed a, websearch_to_tsquery('english', :q) AS q(query)
    WHERE a.tsv @@ q.query
    ORDER BY ts_rank(a.tsv, q.query) DESC
    LIMIT :pool
)
SELECT a.id, a.content_masked, a.parent_type, a.parent_id, a.chunk_index,
       v.distance,
       COALESCE(1.0 / (60 + v.rnk), 0) + COALESCE(1.0 / (60 + k.rnk), 0) AS score
FROM allowed a
LEFT JOIN vec v ON v.id = a.id
LEFT JOIN kw  k ON k.id = a.id
WHERE (v.id IS NOT NULL AND v.distance <= :max_distance) OR k.id IS NOT NULL
ORDER BY score DESC
LIMIT :limit
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
        "q": question,
        "pool": pool,
        "limit": limit,
        "max_distance": max_distance,
    }
    return [dict(r) for r in db.execute(HYBRID_SQL, params).mappings().all()]