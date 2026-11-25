import json
import uuid
from types import SimpleNamespace

import app.services.generate as generate
import app.services.ingest as ingest
from app.services.chunking import mask_pii
from app.services.retrieval import HYBRID_SQL, _or_query, retrieve


def test_mask_pii_masks_personal_contacts_and_preserves_allowlisted_business_email():
    text = "Personal jane@example.com, phone 212-555-0199, billing billing@example.com"

    masked = mask_pii(text, allowed_emails={"BILLING@example.com"})

    assert "jane@example.com" not in masked
    assert "[EMAIL]" in masked
    assert "[PHONE]" in masked
    assert "billing@example.com" in masked


def test_ingestion_masks_before_embedding_and_storage(monkeypatch):
    class EmptyQuery:
        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return []

    class FakeDb:
        def __init__(self):
            self.added = []
            self.committed = False

        def query(self, model):
            return EmptyQuery()

        def add(self, row):
            self.added.append(row)

        def delete(self, row):
            raise AssertionError("No existing chunks should be deleted")

        def commit(self):
            self.committed = True

    captured_texts = []

    def fake_embed_texts(texts):
        captured_texts.extend(texts)
        return [[0.0] * 384 for _ in texts]

    monkeypatch.setattr(ingest, "embed_texts", fake_embed_texts)

    article = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        title="Order support",
        body="Contact jane@example.com at 212-555-0199. Billing: billing@example.com.",
        status="published",
    )
    db = FakeDb()

    ingest.ingest_kb_article(
        db,
        article,
        allowed_emails={"billing@example.com"},
    )

    assert db.committed is True
    assert len(db.added) == 1
    stored = db.added[0].content_masked
    assert "jane@example.com" not in stored
    assert "[EMAIL]" in stored
    assert "[PHONE]" in stored
    assert "billing@example.com" in stored
    assert captured_texts == [stored]


def test_or_query_deduplicates_terms_and_ignores_short_tokens():
    assert _or_query("WiFi wifi & 401 login?") == "wifi | 401 | login"
    assert _or_query("a, I, to") == ""


def test_hybrid_retrieval_can_add_fts_candidates_outside_vector_pool():
    sql = " ".join(HYBRID_SQL.text.split())

    assert "SELECT id FROM vec UNION SELECT id FROM kw" in sql
    assert "JOIN content_chunks AS c ON c.id = candidates.id" in sql
    assert "candidate_rows.distance <= :max_distance" in sql
    assert "kw.id IS NOT NULL" in sql


def test_retrieve_returns_early_for_blank_question(monkeypatch):
    def should_not_embed(_):
        raise AssertionError("Blank questions should not be embedded")

    monkeypatch.setattr("app.services.retrieval.embed_texts", should_not_embed)

    assert retrieve(None, None, question="   ") == []


class FakeModels:
    def __init__(self, response_text):
        self.response_text = response_text
        self.kwargs = None

    def generate_content(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(text=self.response_text)


def _source():
    return {
        "content_masked": "To reset your password, use the Forgot Password link.",
        "title": "Password reset",
        "parent_type": "kb_article",
        "parent_id": str(uuid.uuid4()),
        "chunk_index": 0,
    }


def test_generate_answer_uses_json_sources_and_returns_only_valid_citations(monkeypatch):
    fake_models = FakeModels(
        "Use the Forgot Password link to reset your password. [S1]"
    )
    monkeypatch.setattr(
        generate,
        "_get_client",
        lambda: SimpleNamespace(models=fake_models),
    )

    result = generate.generate_answer(
        "My email is jane@example.com. How do I reset my password?",
        [_source()],
    )

    prompt = json.loads(fake_models.kwargs["contents"])
    assert prompt["question"] == "My email is [EMAIL]. How do I reset my password?"
    assert prompt["sources"][0]["label"] == "S1"
    assert prompt["sources"][0]["title"] == "Password reset"
    assert result["abstained"] is False
    assert result["fallback"] is False
    assert result["source_indexes"] == [0]


def test_generate_answer_abstains_when_model_does_not_cite_a_source(monkeypatch):
    fake_models = FakeModels("Use the Forgot Password link to reset your password.")
    monkeypatch.setattr(
        generate,
        "_get_client",
        lambda: SimpleNamespace(models=fake_models),
    )

    result = generate.generate_answer("How do I reset my password?", [_source()])

    assert result["text"] == "I don't know."
    assert result["abstained"] is True
    assert result["source_indexes"] == []


def test_generate_answer_marks_top_chunk_fallback_as_degraded(monkeypatch):
    monkeypatch.setattr(generate, "_get_client", lambda: None)

    result = generate.generate_answer("How do I reset my password?", [_source()])

    assert result["abstained"] is False
    assert result["fallback"] is True
    assert result["source_indexes"] == [0]



def test_generate_answer_abstains_when_model_cites_unknown_source(monkeypatch):
    fake_models = FakeModels("The feature is supported. [S9]")
    monkeypatch.setattr(
        generate,
        "_get_client",
        lambda: SimpleNamespace(models=fake_models),
    )

    result = generate.generate_answer("Is the feature supported?", [_source()])

    assert result["text"] == "I don't know."
    assert result["abstained"] is True
    assert result["source_indexes"] == []


def test_generate_answer_maps_source_labels_to_original_rows(monkeypatch):
    fake_models = FakeModels("Use the Forgot Password link. [S1]")
    monkeypatch.setattr(
        generate,
        "_get_client",
        lambda: SimpleNamespace(models=fake_models),
    )

    empty_row = {
        "content_masked": "   ",
        "title": "Empty source",
        "parent_type": "kb_article",
        "parent_id": str(uuid.uuid4()),
        "chunk_index": 0,
    }
    result = generate.generate_answer(
        "How do I reset my password?",
        [empty_row, _source()],
    )

    assert result["source_indexes"] == [1]
