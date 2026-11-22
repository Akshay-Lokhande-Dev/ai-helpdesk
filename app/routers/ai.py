from fastapi import APIRouter, Depends
from app.db import session_local
from app.deps import get_current_user
from app.schemas import AiAskRequest, AiAskResponse
from app.services.retrieval import retrieve

router = APIRouter(prefix="/ai", tags=["ai"])

def get_db():
    db = session_local()
    try:
        yield db
    finally:
        db.close()

@router.post("/ask", response_model=AiAskResponse)
def ai_ask(payload: AiAskRequest, db=Depends(get_db), current_user=Depends(get_current_user)):
    rows = retrieve(
    db,
    current_user,
    question=payload.question,
    limit=5,
)

    if not rows:
        return {"answer": "I don't know", "citations": [], "confidence": 0.0}

    best = rows[0]

    if best["distance"] > 0.8:
        return {"answer": "I don't know", "citations": [], "confidence": 0.0}

    return {
        "answer": best["content_masked"],
        "citations": [
            {
                "parent_type": r["parent_type"],
                "parent_id": str(r["parent_id"]),
                "chunk_index": r["chunk_index"],
                "distance": float(r["distance"]),
            } for r in rows
        ],
        "confidence": round(1 - float(best["distance"]), 3),
    }