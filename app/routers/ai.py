import logging

from fastapi import APIRouter, Depends

from app.db import get_db
from app.deps import get_current_user
from app.schemas import AiAskRequest, AiAskResponse
from app.services.generate import generate_answer
from app.services.retrieval import retrieve


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

MAX_DISTANCE = 0.65  # Tune with the retrieval and answer-quality evaluation sets.


@router.post("/ask", response_model=AiAskResponse)
def ai_ask(
    payload: AiAskRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = retrieve(
        db,
        current_user,
        question=payload.question,
        limit=5,
        max_distance=MAX_DISTANCE,
    )
    if not rows:
        return {
            "answer": "I don't know.",
            "citations": [],
            "similarity": None,
            "degraded": False,
        }

    result = generate_answer(payload.question, rows)
    if result["abstained"]:
        return {
            "answer": "I don't know.",
            "citations": [],
            "similarity": None,
            "degraded": False,
        }

    source_indexes = result.get("source_indexes")
    if source_indexes is None:
        # Backwards-compatible behaviour for injected/test generators that do
        # not yet return source indexes.
        citation_rows = rows
    else:
        citation_rows = [
            rows[index]
            for index in source_indexes
            if isinstance(index, int) and 0 <= index < len(rows)
        ]

    if not citation_rows:
        logger.warning("AI generation returned no valid source rows; abstaining.")
        return {
            "answer": "I don't know.",
            "citations": [],
            "similarity": None,
            "degraded": False,
        }

    distances = [
        row["distance"]
        for row in citation_rows
        if row.get("distance") is not None
    ]

    return {
        "answer": result["text"],
        "citations": [
            {
                "parent_type": row["parent_type"],
                "parent_id": str(row["parent_id"]),
                "title": row.get("title"),
                "chunk_index": row["chunk_index"],
            }
            for row in citation_rows
        ],
        "similarity": round(1 - min(distances), 3) if distances else None,
        "degraded": result["fallback"],
    }
