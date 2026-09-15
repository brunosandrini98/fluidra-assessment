import json
from datetime import date

import pytest
from pydantic import ValidationError

from pool_qa import contract
from pool_qa.contract import (
    AskRequest,
    Chunk,
    Citation,
    ErrorResponse,
    GoldenRecord,
    Trace,
    Turn,
)
from pool_qa.settings import ROOT

EXPECTED_FIELDS = {
    "AskRequest": ["question", "history"],
    "Turn": ["role", "content", "outcome"],
    "AskResponse": ["outcome", "language", "message", "citations", "warnings", "trace"],
    "Citation": ["id", "chunk_id", "document", "page", "page_in_language", "section", "quote"],
    "Warning": ["id", "kind", "text", "page"],
    "Trace": ["search_calls", "revisions", "verdict"],
    "ErrorResponse": ["error", "detail"],
    "Chunk": [
        "chunk_id", "document", "source_type", "effective_date", "language",
        "page", "section", "text", "figure_refs", "warning_ids",
    ],
    "Filters": ["language", "section", "page_range"],
    "IntakeResult": ["decision", "language", "retrieval_query"],
    "DraftCitation": ["chunk_id", "quote"],
    "ResearchResult": ["outcome", "message", "citations"],
    "Claim": ["text", "supported", "chunk_ids"],
    "VerifierResult": ["verdict", "claims", "issues"],
    "GoldenRecord": [
        "id", "question", "language", "expected_outcome", "expected_pages", "must_include",
    ],
}


@pytest.mark.parametrize("name", EXPECTED_FIELDS)
def test_model_fields_match_contract(name):
    model = getattr(contract, name)
    assert list(model.model_fields) == EXPECTED_FIELDS[name]


def test_outcome_vocabulary():
    assert set(contract.Outcome.__args__) == {"answer", "clarify", "abstain", "refuse"}


CITATION = dict(
    id="c1", chunk_id="x", document="d", page=1, page_in_language=None, section=None, quote="q"
)


@pytest.mark.parametrize(
    "build",
    [
        lambda: AskRequest(question=""),
        lambda: Citation(**{**CITATION, "quote": "a" * 201}),
        lambda: Turn(role="system", content="hi"),
        lambda: Turn(role="assistant", content="hi", outcome="proceed"),
        lambda: Trace(search_calls=1, revisions=2, verdict=None),
        lambda: Trace(search_calls=1, revisions=0, verdict="fail"),
        lambda: ErrorResponse(error="boom", detail=""),
    ],
)
def test_invalid_input_rejected(build):
    with pytest.raises(ValidationError):
        build()


def test_quote_at_limit_accepted():
    assert Citation(**{**CITATION, "quote": "a" * 200}).quote


def make_chunk(**overrides) -> Chunk:
    fields = dict(
        chunk_id="doc-p1-1", document="doc.pdf", source_type="manual", effective_date=None,
        language="en", page=1, section=None, text="t", figure_refs=[], warning_ids=[],
    )
    return Chunk(**{**fields, **overrides})


def test_chunk_unknown_metadata_serialized_not_omitted():
    data = json.loads(make_chunk().model_dump_json())
    assert data["section"] is None
    assert data["effective_date"] is None
    assert data["figure_refs"] == []
    assert data["warning_ids"] == []


def test_chunk_missing_metadata_field_rejected():
    data = make_chunk().model_dump()
    del data["section"]
    with pytest.raises(ValidationError):
        Chunk.model_validate(data)


def test_chunk_effective_date_parses():
    assert make_chunk(effective_date="2021-04-08").effective_date == date(2021, 4, 8)


def test_golden_set_validates():
    lines = (ROOT / "eval" / "golden.jsonl").read_text(encoding="utf-8").splitlines()
    records = [GoldenRecord.model_validate_json(line) for line in lines if line.strip()]
    assert len(records) == 5
