from fakes import make_chunk
from invariants import assert_invariants
from pool_qa.contract import DraftCitation, IntakeResult, ResearchResult, VerifierResult
from pool_qa.phrases import abstention, refusal
from pool_qa.response import build_response

A = make_chunk("user_manual-p11-1", "Remove the pre-filter cap by\nunscrewing the nut.", page=11, section="4. START-UP")
B = make_chunk("user_manual-p12-1", "Replace the mechanical seal every year.", page=12, section=None)
RETRIEVED = {c.chunk_id: c for c in (A, B)}
PROCEED = IntakeResult(decision="proceed", language="es", retrieval_query="q")
ANSWER = ResearchResult(
    outcome="answer",
    message="Quite la tapa [user_manual-p11-1]. Cambie el sello [user_manual-p12-1]. Tapa [user_manual-p11-1].",
    citations=[
        DraftCitation(chunk_id="user_manual-p12-1", quote="Replace the mechanical seal"),
        DraftCitation(chunk_id="user_manual-p11-1", quote="pre-filter cap by\nunscrewing"),
    ],
)


def verdict(v):
    return VerifierResult(verdict=v, claims=[], issues=["x"] if v == "revise" else [])


def test_refuse():
    r = build_response(IntakeResult(decision="refuse", language="es", retrieval_query=None), None, None, {}, 0, 0)
    assert (r.outcome, r.language, r.message, r.citations) == ("refuse", "es", refusal("es"), [])
    assert r.trace.model_dump() == {"search_calls": 0, "revisions": 0, "verdict": None}
    assert_invariants(r, {})


def test_answer_renumbers_markers_and_builds_citations():
    r = build_response(PROCEED, ANSWER, verdict("pass"), RETRIEVED, 1, 2)
    assert r.outcome == "answer"
    assert r.message == "Quite la tapa [c1]. Cambie el sello [c2]. Tapa [c1]."
    assert [(c.id, c.chunk_id, c.page, c.section, c.document) for c in r.citations] == [
        ("c1", "user_manual-p11-1", 11, "4. START-UP", "user_manual.pdf"),
        ("c2", "user_manual-p12-1", 12, None, "user_manual.pdf"),
    ]
    assert r.citations[0].quote == "pre-filter cap by\nunscrewing"
    assert all(c.page_in_language is None for c in r.citations)
    assert r.warnings == []
    assert r.trace.model_dump() == {"search_calls": 2, "revisions": 1, "verdict": "pass"}
    assert_invariants(r, RETRIEVED)


def test_researcher_clarify_and_abstain_keep_message():
    for outcome in ("clarify", "abstain"):
        research = ResearchResult(outcome=outcome, message="¿Qué modelo?", citations=[])
        r = build_response(PROCEED, research, verdict("revise"), RETRIEVED, 1, 1)
        assert (r.outcome, r.message, r.citations, r.trace.verdict) == (outcome, "¿Qué modelo?", [], "revise")
        assert_invariants(r, RETRIEVED)


def test_answer_without_pass_is_static_abstain():
    for v in (None, verdict("revise"), verdict("abstain")):
        r = build_response(PROCEED, ANSWER, v, RETRIEVED, 1, 1)
        assert (r.outcome, r.message, r.citations) == ("abstain", abstention("es"), [])
        assert r.trace.verdict == (v.verdict if v else None)
        assert_invariants(r, RETRIEVED)
