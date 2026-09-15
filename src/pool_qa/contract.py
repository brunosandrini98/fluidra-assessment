from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Outcome = Literal["answer", "clarify", "abstain", "refuse"]


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    outcome: Outcome | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    history: list[Turn] = []


class Citation(BaseModel):
    id: str
    chunk_id: str
    document: str
    page: int
    page_in_language: int | None
    section: str | None
    quote: str = Field(max_length=200)


class Warning(BaseModel):
    id: str
    kind: str
    text: str
    page: int


class Trace(BaseModel):
    search_calls: int
    revisions: Literal[0, 1]
    verdict: Literal["pass", "revise", "abstain"] | None


class AskResponse(BaseModel):
    outcome: Outcome
    language: str
    message: str
    citations: list[Citation]
    warnings: list[Warning]
    trace: Trace


class ErrorResponse(BaseModel):
    error: Literal["invalid_request", "provider_error", "timeout"]
    detail: str


class Chunk(BaseModel):
    chunk_id: str
    document: str
    source_type: str
    effective_date: date | None
    language: str
    page: int
    section: str | None
    text: str
    figure_refs: list[str]
    warning_ids: list[str]


class Filters(BaseModel):
    language: str
    section: str | None = None
    page_range: tuple[int, int] | None = None


class IntakeResult(BaseModel):
    decision: Literal["proceed", "refuse"]
    language: str
    retrieval_query: str | None


class DraftCitation(BaseModel):
    chunk_id: str
    quote: str


class ResearchResult(BaseModel):
    outcome: Literal["answer", "clarify", "abstain"]
    message: str
    citations: list[DraftCitation]


class Claim(BaseModel):
    text: str
    supported: bool
    chunk_ids: list[str]


class VerifierResult(BaseModel):
    verdict: Literal["pass", "revise", "abstain"]
    claims: list[Claim]
    issues: list[str]


class GoldenRecord(BaseModel):
    id: str
    question: str
    language: str
    expected_outcome: Outcome
    expected_pages: list[int]
    must_include: list[str]
