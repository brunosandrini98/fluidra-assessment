import pytest

from pool_qa.contract import Chunk, GoldenRecord
from pool_qa.eval.gates import ErrorInfo, QuestionResult
from pool_qa.eval.retrieval import live_retrieval, mrr, recall_at, recall_gate, retrieval_results
from pool_qa.eval.run import GOLDEN, load_golden
from pool_qa.retrieval import search

RECORDS = load_golden(GOLDEN)


def golden(id, category, language, pages):
    return GoldenRecord(
        id=id,
        category=category,
        question=f"question {id}",
        language=language,
        expected_outcome="answer",
        expected_pages=pages,
        must_include=[],
    )


def chunk(page):
    return Chunk(
        chunk_id=f"c-p{page}",
        document="doc",
        source_type="manual",
        effective_date=None,
        language="en",
        page=page,
        section=None,
        text="text",
        figure_refs=[],
        warning_ids=[],
    )


RANKED = [chunk(10), chunk(20), chunk(30), chunk(40), chunk(50)]

R1 = golden("r1", "procedure", "en", [10])  # hit at rank 1
R2 = golden("r2", "procedure", "en", [30])  # hit at rank 3
R3 = golden("r3", "procedure", "en", [99])  # miss
R4 = golden("r4", "procedure", "es", [10])  # excluded: non-pivot language
R5 = GoldenRecord(
    id="r5",
    category="not_in_manual",
    question="off manual",
    language="en",
    expected_outcome="abstain",
    expected_pages=[],
    must_include=[],
)  # excluded: non-answer
R6 = GoldenRecord(
    id="r6",
    category="injection",
    question="ignore instructions",
    language="en",
    expected_outcome="answer",
    expected_pages=[10],
    must_include=[],
)  # excluded: gated out


def fake_search_fn(query, filters, k):
    return RANKED[:k]


def test_retrieval_results_excludes_non_pivot_non_answer_and_gated_out():
    results = retrieval_results([R1, R2, R3, R4, R5, R6], fake_search_fn, "en", 5)
    assert [r.id for r in results] == ["r1", "r2", "r3"]
    assert results[0].ranked_pages == [10, 20, 30, 40, 50]
    assert results[0].expected_pages == [10]


def test_recall_at_hand_computed():
    results = retrieval_results([R1, R2, R3], fake_search_fn, "en", 5)
    assert recall_at(results, 1) == pytest.approx(1 / 3)
    assert recall_at(results, 5) == pytest.approx(2 / 3)


def test_mrr_hand_computed():
    results = retrieval_results([R1, R2, R3], fake_search_fn, "en", 5)
    assert mrr(results) == pytest.approx((1 + 1 / 3 + 0) / 3)


def test_recall_gate_fails_below_90_percent():
    results = retrieval_results([R1, R2, R3], fake_search_fn, "en", 5)
    gate = recall_gate(results)
    assert gate.status == "fail"
    assert gate.value == "2/3"
    assert any(f.startswith("r3: top pages") for f in gate.failures)


def test_recall_gate_passes_at_100_percent():
    results = retrieval_results([R1, R2], fake_search_fn, "en", 5)
    gate = recall_gate(results)
    assert gate.status == "pass"
    assert gate.value == "2/2"
    assert gate.failures == []


def qresult(id, category, language, expected_pages, retrieved, expected_outcome="answer", error=None):
    return QuestionResult(
        id=id,
        category=category,
        language=language,
        expected_outcome=expected_outcome,
        expected_pages=expected_pages,
        response=None,
        error=error,
        retrieved=retrieved,
    )


def test_live_retrieval_counts_hit_miss_non_english_and_excludes_gated_and_non_answer():
    chunks = {f"c-p{p}": chunk(p) for p in (10, 20, 30)}
    results = [
        qresult("hit", "procedure", "en", [10], ["c-p10"]),
        qresult("miss", "procedure", "en", [10], ["c-p20"]),
        qresult("nonenglish-hit", "procedure", "es", [30], ["c-p30"]),
        qresult("errored", "procedure", "en", [10], [], error=ErrorInfo(type="timeout", detail="slow")),
        qresult("gated", "injection", "en", [10], ["c-p10"]),
        qresult("abstain-expected", "not_in_manual", "en", [], [], expected_outcome="abstain"),
    ]
    hits, total, misses = live_retrieval(results, chunks)
    assert (hits, total) == (2, 4)
    assert any(m.startswith("miss:") for m in misses)
    assert any(m.startswith("errored:") for m in misses)


def test_real_search_finds_t0_02_page_in_top_5():
    results = retrieval_results(RECORDS, search, "en", 5)
    r = next(x for x in results if x.id == "t0-02")
    assert 12 in r.ranked_pages
