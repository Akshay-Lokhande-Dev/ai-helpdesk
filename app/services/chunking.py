import hashlib
import re


_EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+"
)
_PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\w)"
)


def mask_pii(text: str, allowed_emails: set[str] | None = None) -> str:
    """Mask email addresses and phone numbers, preserving explicit trusted contacts.

    Supply an allowlist only for public business contact addresses that are
    intentionally meant to appear in retrieved knowledge-base answers.
    """
    allowed = {email.strip().lower() for email in (allowed_emails or set())}

    def replace_email(match: re.Match[str]) -> str:
        email = match.group(0)
        return email if email.lower() in allowed else "[EMAIL]"

    text = _EMAIL_PATTERN.sub(replace_email, text)
    return _PHONE_PATTERN.sub("[PHONE]", text)


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
