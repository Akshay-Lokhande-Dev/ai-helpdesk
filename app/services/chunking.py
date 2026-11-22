import re
import hashlib

def mask_pii(text: str) -> str:
    # Avoids swallowing trailing sentence punctuation (e.g., "user@example.com.")
    text = re.sub(
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+",
        "[EMAIL]",
        text,
    )
    # Catches 10-digit numbers with optional country code, spaces, dashes, or parentheses
    text = re.sub(
        r"(?<!\w)(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\w)",
        "[PHONE]",
        text,
    )
    return text

def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and less than chunk_size")

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks

def make_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()