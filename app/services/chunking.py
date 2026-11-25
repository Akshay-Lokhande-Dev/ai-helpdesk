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


def _soft_chunk_end(text: str, start: int, target_end: int) -> int:
    """Prefer a natural boundary near the target without making tiny chunks."""
    minimum_end = start + int((target_end - start) * 0.6)

    paragraph = text.rfind("\n\n", minimum_end, target_end)
    if paragraph >= 0:
        return paragraph + 2

    line = text.rfind("\n", minimum_end, target_end)
    if line >= 0:
        return line + 1

    sentence_ends = [
        text.rfind(delimiter, minimum_end, target_end)
        for delimiter in (". ", "? ", "! ", "; ")
    ]
    sentence_end = max(sentence_ends)
    if sentence_end >= 0:
        return sentence_end + 2

    word_end = text.rfind(" ", minimum_end, target_end)
    if word_end >= 0:
        return word_end + 1

    return target_end


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks, preferring paragraph/sentence boundaries.

    Chunk size and overlap are measured in characters, not model tokens.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and less than chunk_size")

    text = (text or "").strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        target_end = min(start + chunk_size, len(text))
        if target_end == len(text):
            end = target_end
        else:
            end = _soft_chunk_end(text, start, target_end)

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        next_start = max(start + 1, end - overlap)
        if next_start < end:
            # Move the overlap start forward to a whitespace boundary rather
            # than beginning in the middle of a word.
            boundaries = [
                position
                for position in (
                    text.find(" ", next_start, end),
                    text.find("\n", next_start, end),
                )
                if position >= 0
            ]
            if boundaries:
                next_start = min(boundaries) + 1

        start = next_start

    return chunks


def make_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
