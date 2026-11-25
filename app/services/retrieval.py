import re

from sqlalchemy import text

from app.services.embeddings import EMBEDDING_MODEL, embed_texts


def _or_query(question: str) -> str:
    """Build a safe OR tsquery from alphanumeric terms in the question."""
    words = re.findall(r"[A-Za-z0-9]{3,}", (question or "").lower())
    return " | ".join(dict.fromkeys(words))


INTERNAL_ROLES = {"agent", "admin"}
RRF_K = 60

HYBRID_SQL = text(
    """
    WITH vec AS (
        SELECT
            c.id,
            c.embedding <=> CAST(:qvec AS vector) AS distance,
            row_number() OVER (
                ORDER BY c.embedding <=> CAST(:qvec AS vector)
            ) AS rnk
        FROM content_chunks AS c
        LEFT JOIN kb_articles AS k
          ON c.parent_type = 'kb_article'
         AND k.id = c.parent_id
         AND k.tenant_id = c.tenant_id
        WHERE c.tenant_id = CAST(:tenant AS uuid)
          AND c.embedding_model = :model
          AND c.embedding IS NOT NULL
          AND (
              :include_internal
              OR (
                  c.parent_type = 'kb_article'
                  AND k.status = 'published'
                  AND c.visibility = 'public'
              )
          )
        ORDER BY c.embedding <=> CAST(:qvec AS vector)
        LIMIT :pool
    ),
    kw AS (
        SELECT
            c.id,
            row_number() OVER (
                ORDER BY ts_rank(c.tsv, q.query) DESC, c.id
            ) AS rnk
        FROM content_chunks AS c
        LEFT JOIN kb_articles AS k
          ON c.parent_type = 'kb_article'
         AND k.id = c.parent_id
         AND k.tenant_id = c.tenant_id
        CROSS JOIN LATERAL (
            SELECT to_tsquery('english', :q_or) AS query
        ) AS q
        WHERE :q_or <> ''
          AND c.tenant_id = CAST(:tenant AS uuid)
          AND c.embedding_model = :model
          AND c.tsv @@ q.query
          AND (
              :include_internal
              OR (
                  c.parent_type = 'kb_article'
                  AND k.status = 'published'
                  AND c.visibility = 'public'
              )
          )
        ORDER BY ts_rank(c.tsv, q.query) DESC, c.id
        LIMIT :pool
    ),
    candidate_ids AS (
        -- UNION is intentional: FTS can introduce a candidate that was not
        -- present in the vector top-pool.
        SELECT id FROM vec
        UNION
        SELECT id FROM kw
    ),
    candidate_rows AS (
        -- Calculate vector distance for every candidate, including FTS-only
        -- candidates. This allows the hybrid distance gate to be applied to
        -- candidates that vector top-pool retrieval did not return.
        SELECT
            c.id,
            c.tenant_id,
            c.content_masked,
            c.parent_type,
            c.parent_id,
            c.chunk_index,
            k.title,
            c.embedding <=> CAST(:qvec AS vector) AS distance
        FROM candidate_ids AS candidates
        JOIN content_chunks AS c ON c.id = candidates.id
        LEFT JOIN kb_articles AS k
          ON c.parent_type = 'kb_article'
         AND k.id = c.parent_id
         AND k.tenant_id = c.tenant_id
        WHERE c.tenant_id = CAST(:tenant AS uuid)
          AND c.embedding_model = :model
          AND c.embedding IS NOT NULL
          AND (
              :include_internal
              OR (
                  c.parent_type = 'kb_article'
                  AND k.status = 'published'
                  AND c.visibility = 'public'
              )
          )
    )
    SELECT
        candidate_rows.id,
        candidate_rows.tenant_id,
        candidate_rows.content_masked,
        candidate_rows.parent_type,
        candidate_rows.parent_id,
        candidate_rows.chunk_index,
        candidate_rows.title,
        candidate_rows.distance,
        (
            COALESCE(1.0 / (:rrf_k + vec.rnk), 0)
            + COALESCE(1.0 / (:rrf_k + kw.rnk), 0)
        ) AS score
    FROM candidate_rows
    LEFT JOIN vec ON vec.id = candidate_rows.id
    LEFT JOIN kw ON kw.id = candidate_rows.id
    WHERE
        candidate_rows.distance <= :max_distance
        OR (
            kw.id IS NOT NULL
            AND candidate_rows.distance <= :max_distance + :keyword_distance_allowance
        )
    ORDER BY score DESC, candidate_rows.distance ASC, candidate_rows.id
    LIMIT :fetch
    """
)


def retrieve(
    db,
    current_user,
    question: str,
    limit: int = 5,
    max_distance: float = 0.65,
    pool: int = 20,
    keyword_distance_allowance: float = 0.15,
) -> list[dict]:
    question = (question or "").strip()
    if not question or limit <= 0 or pool <= 0:
        return []

    query_vector = embed_texts([question])[0]
    params = {
        "tenant": str(current_user.tenant_id),
        "include_internal": current_user.role in INTERNAL_ROLES,
        "model": EMBEDDING_MODEL,
        "qvec": "[" + ",".join(map(str, query_vector)) + "]",
        "q_or": _or_query(question),
        "pool": max(pool, limit),
        "fetch": max(pool, limit) * 2,
        "max_distance": max_distance,
        "keyword_distance_allowance": keyword_distance_allowance,
        "rrf_k": RRF_K,
    }

    rows = [dict(row) for row in db.execute(HYBRID_SQL, params).mappings().all()]

    # Keep retrieval diverse without allowing one long article to dominate.
    parent_counts: dict[tuple[str, object], int] = {}
    results: list[dict] = []
    for row in rows:
        parent_key = (row["parent_type"], row["parent_id"])
        count = parent_counts.get(parent_key, 0)
        if count >= 2:
            continue

        parent_counts[parent_key] = count + 1
        results.append(row)
        if len(results) >= limit:
            break

    return results
