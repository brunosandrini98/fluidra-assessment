import asyncio

import pytest
from langchain_core.messages import AIMessage

from fakes import FakeToolModel, ai_tool_call, make_chunk
from pool_qa.agents.researcher import SearchTool, researcher_messages, run_researcher
from pool_qa.contract import Filters, IntakeResult, ResearchResult
from pool_qa.llm import ProviderError
from pool_qa.settings import Settings

CHUNK = make_chunk("user_manual-p12-1", "Replace the mechanical seal every year.")
INTAKE = IntakeResult(decision="proceed", language="en", retrieval_query="mechanical seal")
SUBMIT = {
    "outcome": "answer",
    "message": "Every year [user_manual-p12-1].",
    "citations": [{"chunk_id": "user_manual-p12-1", "quote": "every year"}],
}


class RecordingSearch:
    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = []

    def __call__(self, query, filters, k):
        self.calls.append((query, filters, k))
        return self.chunks


def settings(**kw):
    return Settings(_env_file=None, **kw)


def run(model, search, issues=(), **kw):
    return asyncio.run(run_researcher(model, search, settings(**kw), "How often?", [], INTAKE, list(issues)))


def test_search_tool_forces_filters_and_k():
    search = RecordingSearch([CHUNK])
    tool = SearchTool(search, pivot="en", k=5, max_calls=3)
    out = tool({"query": "seal", "language": "fr", "k": 50, "filters": {"language": "fr"}})
    assert search.calls == [("seal", Filters(language="en"), 5)]
    assert "user_manual-p12-1" in out and CHUNK.text in out
    assert tool.calls == 1 and tool.retrieved == {"user_manual-p12-1": CHUNK}


def test_search_tool_limit_returns_error_without_searching():
    search = RecordingSearch([CHUNK])
    tool = SearchTool(search, pivot="en", k=5, max_calls=1)
    tool({"query": "a"})
    out = tool({"query": "b"})
    assert len(search.calls) == 1 and tool.calls == 1
    assert "limit" in out.lower()


def test_search_tool_missing_query():
    search = RecordingSearch([CHUNK])
    tool = SearchTool(search, pivot="en", k=5, max_calls=3)
    assert "query" in tool({}).lower() and search.calls == []


def test_search_then_submit():
    model = FakeToolModel([ai_tool_call("search", {"query": "seal"}, "s1"), ai_tool_call("submit", SUBMIT, "f1")])
    run_ = run(model, RecordingSearch([CHUNK]))
    assert run_.result == ResearchResult.model_validate(SUBMIT)
    assert run_.search_calls == 1
    assert run_.retrieved == {"user_manual-p12-1": CHUNK}
    assert [name for name in (t["function"]["name"] for t in model.tools)] == ["search", "submit"]


def test_submit_forced_at_step_cap():
    replies = [ai_tool_call("search", {"query": f"q{i}"}, f"s{i}") for i in range(4)]
    model = FakeToolModel([*replies, ai_tool_call("submit", SUBMIT, "f1")])
    run_ = run(model, RecordingSearch([CHUNK]), max_search_calls=3)
    assert [choice for choice, _ in model.calls] == [None, None, None, None, "submit"]
    assert run_.search_calls == 3


def test_malformed_submit_retried_once_with_feedback():
    bad = ai_tool_call("submit", {"outcome": "maybe"}, "f0")
    model = FakeToolModel([bad, ai_tool_call("submit", SUBMIT, "f1")])
    assert run(model, RecordingSearch([CHUNK])).result.outcome == "answer"
    assert "invalid" in model.calls[1][1][-1].content.lower()


def test_second_malformed_reply_raises():
    model = FakeToolModel([AIMessage(content="plain text"), ai_tool_call("submit", {"outcome": "maybe"}, "f0")])
    with pytest.raises(ProviderError):
        run(model, RecordingSearch([CHUNK]))


def test_provider_exception_wrapped():
    model = FakeToolModel([RuntimeError("connection reset")])
    with pytest.raises(ProviderError):
        run(model, RecordingSearch([CHUNK]))


def test_issues_passed_to_model():
    model = FakeToolModel([ai_tool_call("submit", SUBMIT, "f1")])
    run(model, RecordingSearch([CHUNK]), issues=["Quote for user_manual-p12-1 is not verbatim."])
    text = "\n".join(m.content for m in model.calls[0][1] if isinstance(m.content, str))
    assert "Quote for user_manual-p12-1 is not verbatim." in text


def test_prompt_cite_or_abstain():
    system = researcher_messages("q", [], INTAKE, [], "en", 3)[0].content.lower()
    assert "only" in system and "general knowledge" in system
    assert "abstain" in system and "safety" in system and "verbatim" in system
    assert "[chunk_id]" in system
