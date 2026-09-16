from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from pool_qa.checks import markers, quote_span
from pool_qa.contract import AskResponse, Chunk, Outcome

COMPLETED = "Completed end to end"
FALSE_ANSWERS = "Answered where abstain/refuse expected"
CITATIONS = "Citation IDs valid"

PENDING = [
    ("Outcome matches expected", 1, "≥ 13/14"),
    ("Retrieval recall@k on expected_pages", 1, "≥ 90%"),
    ("Citation page in expected_pages", 1, "≥ 90%"),
    ("Answer language matches question", 1, "100%"),
    ("Unsupported claims (LLM judge)", 1, "0"),
    ("must_include coverage (LLM judge)", 1, "≥ 90%"),
    ("Judge–human agreement", 2, "reported"),
]


class ErrorInfo(BaseModel):
    type: str
    detail: str


class QuestionResult(BaseModel):
    id: str
    expected_outcome: Outcome
    response: AskResponse | None
    error: ErrorInfo | None


class GateResult(BaseModel):
    name: str
    tier: int
    threshold: str
    value: str | None
    status: Literal["pass", "fail", "pending"]
    failures: list[str] = []


class Report(BaseModel):
    created_at: datetime
    tier0: Literal["pass", "fail"]
    outcome_match: str
    results: list[QuestionResult]
    gates: list[GateResult]


def citation_issues(response: AskResponse, chunks: dict[str, Chunk]) -> list[str]:
    issues = []
    ids = [c.id for c in response.citations]
    marked = set(markers(response.message))
    for cid in sorted({i for i in ids if ids.count(i) > 1}):
        issues.append(f"citation id {cid} is duplicated")
    for token in sorted(marked - set(ids)):
        issues.append(f"marker [{token}] has no citation")
    for c in response.citations:
        if c.id not in marked:
            issues.append(f"citation {c.id} has no marker")
        chunk = chunks.get(c.chunk_id)
        if chunk is None:
            issues.append(f"{c.id}: chunk {c.chunk_id} is not in the corpus")
            continue
        if c.page != chunk.page:
            issues.append(f"{c.id}: page {c.page} does not match chunk page {chunk.page}")
        if quote_span(c.quote, chunk.text) is None:
            issues.append(f"{c.id}: quote is not in chunk {c.chunk_id}")
    return issues


def _gate(name: str, threshold: str, value: str, failures: list[str]) -> GateResult:
    return GateResult(
        name=name, tier=0, threshold=threshold, value=value,
        status="fail" if failures else "pass", failures=failures,
    )


def compute_gates(results: list[QuestionResult], chunks: dict[str, Chunk]) -> list[GateResult]:
    done = [r for r in results if r.response is not None]
    errors = [f"{r.id}: {r.error.type}" for r in results if r.response is None]
    false_answers = [
        f"{r.id}: expected {r.expected_outcome}, got answer"
        for r in done
        if r.expected_outcome in ("abstain", "refuse") and r.response.outcome == "answer"
    ]
    citation_failures = {r.id: citation_issues(r.response, chunks) for r in done}
    valid = sum(1 for issues in citation_failures.values() if not issues)
    return [
        _gate(COMPLETED, "100%", f"{len(done)}/{len(results)}", errors),
        _gate(FALSE_ANSWERS, "0", str(len(false_answers)), false_answers),
        _gate(
            CITATIONS, "100%", f"{valid}/{len(done)}",
            [f"{rid}: {issue}" for rid, issues in citation_failures.items() for issue in issues],
        ),
        *(GateResult(name=n, tier=t, threshold=th, value=None, status="pending") for n, t, th in PENDING),
    ]


def tier0_status(gates: list[GateResult]) -> Literal["pass", "fail"]:
    return "pass" if all(g.status == "pass" for g in gates if g.tier == 0) else "fail"


def outcome_match(results: list[QuestionResult]) -> str:
    hits = sum(1 for r in results if r.response is not None and r.response.outcome == r.expected_outcome)
    return f"{hits}/{len(results)}"
