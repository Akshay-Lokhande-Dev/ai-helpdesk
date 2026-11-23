from fastapi import APIRouter, Depends

from app.db import get_db
from app.deps import get_current_user
from app.schemas import AiAskRequest, AiAskResponse
from app.services.generate import generate_answer
from app.services.retrieval import retrieve

router = APIRouter(prefix="/ai", tags=["ai"])

MAX_DISTANCE = 0.65          # the only threshold; tune it with the eval


@router.post("/ask", response_model=AiAskResponse)
def ai_ask(payload: AiAskRequest, db=Depends(get_db), current_user=Depends(get_current_user)):
    rows = retrieve(db, current_user, question=payload.question, limit=5, max_distance=MAX_DISTANCE)
    if not rows:
        return {"answer": "I don't know.", "citations": [], "similarity": None, "degraded": False}

    result = generate_answer(payload.question, rows)     # {"text", "abstained", "fallback"}
    if result["abstained"]:
        return {"answer": "I don't know.", "citations": [], "similarity": None, "degraded": False}

    distances = [r["distance"] for r in rows if r["distance"] is not None]
    return {
        "answer": result["text"],
        "citations": [
            {"parent_type": r["parent_type"], "parent_id": str(r["parent_id"]),
             "title": r.get("title"), "chunk_index": r["chunk_index"]}
            for r in rows
        ],
        "similarity": round(1 - min(distances), 3) if distances else None,
        "degraded": result["fallback"],
    }