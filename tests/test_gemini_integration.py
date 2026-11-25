import os

import pytest
from dotenv import load_dotenv

load_dotenv()

from app.services import generate


RUN_LIVE_GEMINI = (
    os.getenv("RUN_GEMINI_INTEGRATION") == "1"
    and bool(os.getenv("GEMINI_API_KEY"))
)


@pytest.mark.skipif(
    not RUN_LIVE_GEMINI,
    reason="Set RUN_GEMINI_INTEGRATION=1 and GEMINI_API_KEY to call Gemini.",
)
def test_live_gemini_generation_returns_a_cited_grounded_answer():
    # Do not reuse a client created by another test or with another API key.
    generate._client = None

    chunks = [
        {
            "content_masked": (
                "To reset your password, open the sign-in page and select "
                "'Forgot Password'. Enter your registered work email address. "
                "Use the password-reset link sent to that email to create a new password."
            ),
            "title": "How to reset your account password",
            "parent_type": "kb_article",
            "parent_id": "live-gemini-integration-test",
            "chunk_index": 0,
        }
    ]

    result = generate.generate_answer(
        "How can I reset my password?",
        chunks,
    )

    assert result["fallback"] is False, (
        "Gemini call failed or GEMINI_API_KEY was not accepted; inspect application logs."
    )
    assert result["abstained"] is False
    assert result["source_indexes"] == [0]
    assert "[S1]" in result["text"]
