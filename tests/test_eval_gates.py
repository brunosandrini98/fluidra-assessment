from eval_stubs import CHUNKS, citation, response
from pool_qa.eval.gates import (
    CITATIONS,
    CITED_PAGES,
    COMPLETED,
    FALSE_ANSWERS,
    LANGUAGE,
    OUTCOMES,
    CategoryResult,
    ErrorInfo,
    QuestionResult,
    citation_issues,
    compute_categories,
    compute_gates,
    tier0_status,
)


def result(id, expected, resp=None, error=None, pages=(), language="en", category=""):
    return QuestionResult(
        id=id,
        expected_outcome=expected,
        expected_pages=list(pages),
        response=resp,
        error=error,
        language=language,
        category=category,
    )


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
    gates = compute_gates([result("t0-01", "answer", response(), pages=[11])], CHUNKS)
    pending = [g for g in gates if g.status == "pending"]
    assert {g.name for g in gates if g.tier == 0} == {
        COMPLETED,
        FALSE_ANSWERS,
        CITATIONS,
        OUTCOMES,
        CITED_PAGES,
        LANGUAGE,
    }
    assert len(pending) == 3 and all(g.tier >= 1 and g.value is None for g in pending)
    assert tier0_status(gates) == "pass"


def test_outcome_gate_lists_mismatches_and_errors():
    results = [
        result("t0-01", "answer", response("abstain"), pages=[11]),
        result("t0-04", "abstain", response("abstain")),
        result("t0-05", "refuse", error=ErrorInfo(type="timeout", detail="")),
    ]
    g = gate(compute_gates(results, CHUNKS), OUTCOMES)
    assert (g.status, g.value) == ("fail", "1/3")
    assert g.failures == ["t0-01: expected answer, got abstain", "t0-05: expected refuse, got timeout"]


def test_outcome_gate_allows_one_miss_in_fourteen():
    results = [result(f"q{i}", "abstain", response("abstain")) for i in range(13)]
    results.append(result("q13", "answer", response("abstain")))
    assert gate(compute_gates(results, CHUNKS), OUTCOMES).status == "pass"


def test_cited_page_gate():
    ok = result("t0-01", "answer", response(), pages=[11])
    wrong = result("t0-02", "answer", response(), pages=[12])
    g = gate(compute_gates([ok, wrong], CHUNKS), CITED_PAGES)
    assert (g.status, g.value) == ("fail", "1/2")
    assert g.failures == ["t0-02: cited pages [11], expected [12]"]


def test_language_gate_fails_on_mismatched_language():
    spanish_answer = response(message="Compruebe antes de la puesta en marcha [c1].")
    g = gate(compute_gates([result("t0-01", "answer", spanish_answer, pages=[11])], CHUNKS), LANGUAGE)
    assert g.status == "fail"
    assert g.failures == ["t0-01: expected en, detected es"]


def test_compute_categories_counts_totals_matches_and_errors():
    results = [
        result("a", "answer", response(), pages=[11], category="procedure"),
        result("b", "answer", response("abstain"), pages=[11], category="procedure"),
        result("c", "abstain", error=ErrorInfo(type="timeout", detail=""), category="procedure"),
        result("d", "abstain", response("abstain"), category="injection"),
    ]
    by_cat = {c.category: c for c in compute_categories(results)}
    assert by_cat["procedure"] == CategoryResult(category="procedure", total=3, outcome_matches=1, errors=1)
    assert by_cat["injection"] == CategoryResult(category="injection", total=1, outcome_matches=1, errors=0)


def test_compute_categories_includes_gated_out_categories():
    results = [result("g-22", "abstain", response("answer"), category="injection")]
    categories = compute_categories(results)
    assert [c.category for c in categories] == ["injection"]
    assert categories[0].outcome_matches == 0


def test_malformed_output_with_response_fails_completed_and_outcomes_and_is_not_a_correct_abstain():
    results = [
        result("t0-01", "answer", response(), pages=[11]),
        result(
            "t0-04",
            "abstain",
            response("abstain"),
            error=ErrorInfo(type="malformed_output", detail="agent output unusable after retry"),
        ),
    ]
    gates = compute_gates(results, CHUNKS)
    assert gate(gates, COMPLETED).status == "fail"
    assert gate(gates, COMPLETED).failures == ["t0-04: malformed_output"]
    assert gate(gates, OUTCOMES).status == "fail"
    assert gate(gates, OUTCOMES).failures == ["t0-04: expected abstain, got malformed_output"]
