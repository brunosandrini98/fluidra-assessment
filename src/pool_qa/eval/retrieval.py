from collections.abc import Callable

from pydantic import BaseModel

from pool_qa.contract import Chunk, Filters, GoldenRecord
from pool_qa.eval.gates import GATED_OUT, RECALL, GateResult, QuestionResult

SearchFn = Callable[[str, Filters, int], list[Chunk]]


class RetrievalResult(BaseModel):
    id: str
    ranked_pages: list[int]
    expected_pages: list[int]


def _hit(result: RetrievalResult, k: int) -> bool:
    return bool(set(result.ranked_pages[:k]) & set(result.expected_pages))


def retrieval_results(records: list[GoldenRecord], search_fn: SearchFn, language: str, k: int) -> list[RetrievalResult]:
    candidates = [
        r for r in records if r.category not in GATED_OUT and r.language == language and r.expected_outcome == "answer"
    ]
    return [
        RetrievalResult(
            id=r.id,
            ranked_pages=[c.page for c in search_fn(r.question, Filters(language=language), k)],
            expected_pages=r.expected_pages,
        )
        for r in candidates
    ]


def recall_at(results: list[RetrievalResult], k: int) -> float:
    if not results:
        return 0.0
    return sum(_hit(r, k) for r in results) / len(results)


def mrr(results: list[RetrievalResult]) -> float:
    if not results:
        return 0.0
    reciprocals = []
    for r in results:
        rank = next((i for i, page in enumerate(r.ranked_pages, start=1) if page in r.expected_pages), None)
        reciprocals.append(1 / rank if rank else 0.0)
    return sum(reciprocals) / len(results)


def recall_gate(results: list[RetrievalResult]) -> GateResult:
    total = len(results)
    misses = [r for r in results if not _hit(r, 5)]
    hits = total - len(misses)
    failures = [f"{r.id}: top pages {r.ranked_pages}, expected {r.expected_pages}" for r in misses]
    return GateResult(
        name=RECALL,
        tier=0,
        threshold="≥ 90%",
        value=f"{hits}/{total}",
        status="pass" if total == 0 or hits * 10 >= 9 * total else "fail",
        failures=failures,
    )


def live_retrieval(results: list[QuestionResult], chunks: dict[str, Chunk]) -> tuple[int, int, list[str]]:
    candidates = [r for r in results if r.category not in GATED_OUT and r.expected_outcome == "answer"]
    hits = 0
    misses = []
    for r in candidates:
        pages = sorted({chunks[cid].page for cid in r.retrieved if cid in chunks})
        if set(pages) & set(r.expected_pages):
            hits += 1
        else:
            misses.append(f"{r.id}: retrieved pages {pages}, expected {r.expected_pages}")
    return hits, len(candidates), misses
