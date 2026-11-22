import logging
import os
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

LLM_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

SYSTEM_INSTRUCTION = """You are a helpdesk assistant.
Rules:
- Answer using the provided CONTEXT. Use meaning, not exact words.
- Treat synonyms as same. WiFi, internet, network - ye sab same problem hai. Agar CONTEXT me WiFi likha hai aur sawal me internet hai, toh usi ko jawab samajh.
- Rephrase the answer in the user's words. If user asks 'internet', start with 'internet'.
- Keep the answer short, simple, and clear, in the same language as the question.
- Say "I don't know." ONLY if CONTEXT is totally unrelated to the question, like Mars vs WiFi.
"""

_client: genai.Client | None = None


def _get_client() -> genai.Client | None:
    global _client
    if _client is not None:
        return _client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    _client = genai.Client(api_key=api_key)
    return _client


def generate_answer(question: str, chunks: list) -> str:
    if not chunks:
        return "I don't know."

    context_parts = []
    for c in chunks:
        text = c.get("content_masked", "") if isinstance(c, dict) else getattr(c, "content_masked", "")
        text = (text or "").strip()
        if text:
            context_parts.append(text)

    if not context_parts:
        return "I don't know."

    client = _get_client()
    if client is None:
        logger.warning("GEMINI_API_KEY not set; falling back to top retrieved chunk.")
        return context_parts[0]

    context = "\n\n---\n\n".join(context_parts)
    user_prompt = f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"

    try:
        resp = client.models.generate_content(
            model=LLM_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.0,
            ),
        )
        answer = (resp.text or "").strip()
        return answer if answer else "I don't know."
    except Exception:
        logger.exception("Gemini generation failed; falling back to top retrieved chunk.")
        return context_parts[0]