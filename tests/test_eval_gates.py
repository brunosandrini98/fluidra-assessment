from eval_stubs import CHUNKS, citation, response
from pool_qa.eval.gates import (
    CITATIONS,
    COMPLETED,
    FALSE_ANSWERS,
    ErrorInfo,
    QuestionResult,
    citation_issues,
    compute_gates,
    outcome_match,
    tier0_status,
)


def result(id, expected, resp=None, error=None):
    return QuestionResult(id=id, expected_outcome=expected, response=resp, error=error)


def gate(gates, name):
    return next(g for g in gates if g.name == name)


def test_valid_answer_has_no_issues():
    assert citation_issues(response(), CHUNKS) == []


def test_non_answer_without_citations_has_no_issues():
    assert citation_issues(response("abstain"), CHUNKS) == []


def test_marker_without_citation():  # D4
    issues = citation_issues(response(message="Check [c1] and [c2]."), CHUNKS)
    assert any("[c2]" in i for i in issues)


def test_citation_without_marker():  # D4
    issues = citation_issues(response(message="No markers here."), CHUNKS)
    assert any("c1" in i for i in issues)


def test_duplicate_citation_id():  # D4
    issues = citation_issues(response(citations=[citation(), citation()]), CHUNKS)
    assert issues


def test_unknown_chunk():  # D5
    issues = citation_issues(response(citations=[citation(chunk_id="user_manual-p99-9")]), CHUNKS)
    assert any("user_manual-p99-9" in i for i in issues)


def test_page_mismatch():  # D6
    assert citation_issues(response(citations=[citation(page=12)]), CHUNKS)


def test_quote_not_in_chunk():  # D6
    assert citation_issues(response(citations=[citation(quote="Run the pump dry")]), CHUNKS)


def test_quote_differing_only_in_whitespace_passes():  # D6
    quote = "4. START-UP INSTRUCTIONS PRIOR TO START-UP"
    assert quote not in CHUNKS["user_manual-p11-1"].text
    assert citation_issues(response(citations=[citation(quote=quote)]), CHUNKS) == []


def test_citation_gate_lists_failures():
    gates = compute_gates([result("t0-01", "answer", response(message="No markers."))], CHUNKS)
    g = gate(gates, CITATIONS)
    assert g.status == "fail"
    assert g.failures and all(f.startswith("t0-01: ") for f in g.failures)


def test_false_answer_gate():
    gates = compute_gates(
        [result("t0-04", "abstain", response("answer")), result("t0-05", "refuse", response("refuse"))], CHUNKS
    )
    g = gate(gates, FALSE_ANSWERS)
    assert (g.status, g.value, g.failures) == ("fail", "1", ["t0-04: expected abstain, got answer"])


def test_errored_question_fails_completed_only():
    results = [
        result("t0-01", "answer", response()),
        result("t0-02", "answer", error=ErrorInfo(type="timeout", detail="slow")),
    ]
    gates = compute_gates(results, CHUNKS)
    assert (gate(gates, COMPLETED).status, gate(gates, COMPLETED).value) == ("fail", "1/2")
    assert gate(gates, COMPLETED).failures == ["t0-02: timeout"]
    assert gate(gates, FALSE_ANSWERS).status == "pass"
    assert gate(gates, CITATIONS).status == "pass"


def test_later_tier_gates_pending_and_ignored():  # D8
    gates = compute_gates([result("t0-01", "answer", response())], CHUNKS)
    pending = [g for g in gates if g.status == "pending"]
    assert {g.name for g in gates if g.tier == 0} == {COMPLETED, FALSE_ANSWERS, CITATIONS}
    assert len(pending) == 7 and all(g.tier >= 1 and g.value is None for g in pending)
    assert tier0_status(gates) == "pass"


def test_outcome_match():
    results = [
        result("t0-01", "answer", response("abstain")),
        result("t0-04", "abstain", response("abstain")),
        result("t0-05", "refuse", error=ErrorInfo(type="timeout", detail="")),
    ]
    assert outcome_match(results) == "1/3"
