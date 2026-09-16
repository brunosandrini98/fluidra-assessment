from fakes import make_chunk
from pool_qa.checks import citation_check, markers, quote_span, truncate_history
from pool_qa.contract import DraftCitation, ResearchResult, Turn

P11 = make_chunk("user_manual-p11-1", "1. Remove the pre-filter cap by unscrewing the nut\nholding it in place (Fig. 5).")
P10 = make_chunk("user_manual-p10-1", "the grounding conductor is correctly con -\nnected. Connect the motor", page=10)
RETRIEVED = {c.chunk_id: c for c in (P11, P10)}


def draft(message, citations, outcome="answer"):
    return ResearchResult(
        outcome=outcome, message=message,
        citations=[DraftCitation(chunk_id=i, quote=q) for i, q in citations],
    )


VALID = draft(
    "Remove the pre-filter cap [user_manual-p11-1].",
    [("user_manual-p11-1", "Remove the pre-filter cap")],
)


def test_valid_draft_passes():
    assert citation_check(VALID, RETRIEVED) == []


def test_answer_without_citations():
    assert len(citation_check(draft("Remove the cap.", []), RETRIEVED)) == 1


def test_chunk_not_retrieved():
    d = draft("Text [user_manual-p99-1].", [("user_manual-p99-1", "x")])
    assert len(citation_check(d, RETRIEVED)) == 1


def test_quote_not_in_chunk():
    d = draft("Text [user_manual-p11-1].", [("user_manual-p11-1", "Remove the filter lid")])
    issues = citation_check(d, RETRIEVED)
    assert len(issues) == 1
    assert "Remove the filter lid" in issues[0]


def test_empty_quote():
    d = draft("Text [user_manual-p11-1].", [("user_manual-p11-1", "  ")])
    assert len(citation_check(d, RETRIEVED)) == 1


def test_quote_too_long():
    long_text = "a " * 150
    chunk = make_chunk("long-1", long_text)
    d = draft("Text [long-1].", [("long-1", long_text.strip())])
    assert len(citation_check(d, {"long-1": chunk})) == 1


def test_marker_without_citation():
    d = draft(
        "Remove the pre-filter cap [user_manual-p11-1] [user_manual-p10-1].",
        [("user_manual-p11-1", "Remove the pre-filter cap")],
    )
    assert len(citation_check(d, RETRIEVED)) == 1


def test_citation_without_marker():
    d = draft("Remove the pre-filter cap.", [("user_manual-p11-1", "Remove the pre-filter cap")])
    assert len(citation_check(d, RETRIEVED)) == 1


def test_chunk_cited_twice():
    d = draft(
        "Remove the pre-filter cap [user_manual-p11-1].",
        [("user_manual-p11-1", "Remove the pre-filter cap"), ("user_manual-p11-1", "unscrewing the nut")],
    )
    assert len(citation_check(d, RETRIEVED)) == 1


def test_bracketed_figure_counts_as_marker_without_citation():
    d = draft(
        "Remove the pre-filter cap [user_manual-p11-1] [Fig.5].",
        [("user_manual-p11-1", "Remove the pre-filter cap")],
    )
    assert len(citation_check(d, RETRIEVED)) == 1


def test_whitespace_only_difference_passes():  # D22
    d = draft("Unscrew [user_manual-p11-1].", [("user_manual-p11-1", "unscrewing the nut holding it")])
    assert citation_check(d, RETRIEVED) == []


def test_hyphen_split_word_fails():  # D22 known parser limitation; remove in Tier 1
    d = draft("Check it [user_manual-p10-1].", [("user_manual-p10-1", "correctly connected")])
    assert len(citation_check(d, RETRIEVED)) == 1


def test_quote_span_whitespace_only_difference_returns_raw_span():  # D22
    assert quote_span("unscrewing the nut holding it", P11.text) == "unscrewing the nut\nholding it"


def test_quote_span_hyphen_split_returns_none():  # D22 known parser limitation; remove in Tier 1
    assert quote_span("correctly connected", P10.text) is None


def test_quote_span_blank_returns_none():
    assert quote_span("   ", P11.text) is None


def test_markers_in_order():
    assert markers("x [a-1] y [b-2] z [a-1]") == ["a-1", "b-2", "a-1"]


def turns(n):
    return [Turn(role="user" if i % 2 == 0 else "assistant", content=f"t{i}") for i in range(n)]


def test_truncate_keeps_first_user_turn_and_last_n():
    h = turns(8)
    assert [t.content for t in truncate_history(h, 5)] == ["t0", "t3", "t4", "t5", "t6", "t7"]


def test_truncate_no_duplicate_when_overlapping():
    h = turns(4)
    assert truncate_history(h, 5) == h


def test_truncate_empty():
    assert truncate_history([], 5) == []


def test_truncate_first_user_turn_not_at_index_zero():
    h = [Turn(role="assistant", content="hi"), *turns(8)]
    assert [t.content for t in truncate_history(h, 2)] == ["t0", "t6", "t7"]
