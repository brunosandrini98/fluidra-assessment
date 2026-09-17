import asyncio
import json
import logging

import pytest

from fakes import make_chunk
from invariants import assert_invariants
from pool_qa.agents.researcher import ResearchRun
from pool_qa.contract import AskRequest, Claim, DraftCitation, IntakeResult, ResearchResult, Turn, VerifierResult
from pool_qa.graph import Agents, RequestTimeout, make_ask
from pool_qa.llm import MalformedOutput
from pool_qa.phrases import abstention, refusal
from pool_qa.settings import Settings

CHUNK = make_chunk("user_manual-p12-1", "Replace the mechanical seal every year.")
PROCEED = IntakeResult(decision="proceed", language="es", retrieval_query="seal")
GOOD = ResearchResult(
    outcome="answer",
    message="Cada año [user_manual-p12-1].",
    citations=[DraftCitation(chunk_id="user_manual-p12-1", quote="every year")],
)
BAD = ResearchResult(
    outcome="answer",
    message="Cada año [user_manual-p12-1].",
    citations=[DraftCitation(chunk_id="user_manual-p12-1", quote="every month")],
)
CLARIFY = ResearchResult(outcome="clarify", message="¿Qué modelo?", citations=[])
ABSTAIN = ResearchResult(outcome="abstain", message="El manual no lo indica.", citations=[])


def verdict(v):
    return VerifierResult(verdict=v, claims=[], issues=["Claim 1 unsupported."] if v == "revise" else [])


class Script:
    def __init__(self, intake=PROCEED, research=(), verdicts=()):
        self.intake_result = intake
        self.research = list(research)
        self.verdicts = list(verdicts)
        self.intake_calls, self.research_calls, self.verifier_calls = [], [], []

    async def intake(self, question, history):
        self.intake_calls.append(history)
        return self.intake_result

    async def researcher(self, question, history, intake, issues):
        self.research_calls.append((history, list(issues)))
        return ResearchRun(self.research.pop(0), 2, {CHUNK.chunk_id: CHUNK})

    async def verifier(self, question, language, draft, chunks):
        self.verifier_calls.append((language, draft, chunks))
        return self.verdicts.pop(0)

    def agents(self):
        return Agents(intake=self.intake, researcher=self.researcher, verifier=self.verifier)


def ask(script, request=None, **settings_kw):
    settings = Settings(_env_file=None, **settings_kw)
    response = asyncio.run(make_ask(script.agents(), settings)(request or AskRequest(question="¿Cada cuánto?")))
    assert_invariants(response, {CHUNK.chunk_id: CHUNK})  # A12
    return response


def trace(r):
    return (r.trace.search_calls, r.trace.revisions, r.trace.verdict)


def test_a1_refuse():
    s = Script(intake=IntakeResult(decision="refuse", language="es", retrieval_query=None))
    r = ask(s)
    assert (r.outcome, r.message, r.citations, trace(r)) == ("refuse", refusal("es"), [], (0, 0, None))
    assert s.research_calls == [] and s.verifier_calls == []


def test_a2_refuse_unknown_language():
    r = ask(Script(intake=IntakeResult(decision="refuse", language="ja", retrieval_query=None)))
    assert (r.language, r.message) == ("ja", refusal("en"))


def test_a3_answer():
    s = Script(research=[GOOD], verdicts=[verdict("pass")])
    r = ask(s)
    assert (r.outcome, r.message, trace(r)) == ("answer", "Cada año [c1].", (2, 0, "pass"))
    assert s.verifier_calls == [("es", GOOD.message, [CHUNK])]


def test_a4_clarify():
    s = Script(research=[CLARIFY])
    r = ask(s)
    assert (r.outcome, r.message, r.citations, trace(r)) == ("clarify", "¿Qué modelo?", [], (2, 0, None))
    assert s.verifier_calls == []


def test_a5_abstain():
    s = Script(research=[ABSTAIN])
    r = ask(s)
    assert (r.outcome, r.message) == ("abstain", abstention("es"))
    assert s.verifier_calls == []


def test_a6_citation_check_fails_once():
    s = Script(research=[BAD, GOOD], verdicts=[verdict("pass")])
    r = ask(s)
    assert (r.outcome, trace(r)) == ("answer", (4, 1, "pass"))
    assert s.research_calls[0][1] == [] and s.research_calls[1][1] != []
    assert len(s.verifier_calls) == 1


def test_a7_verifier_revise_then_pass():
    s = Script(research=[GOOD, GOOD], verdicts=[verdict("revise"), verdict("pass")])
    r = ask(s)
    assert (r.outcome, trace(r)) == ("answer", (4, 1, "pass"))
    assert s.research_calls[1][1] == ["Claim 1 unsupported."]


def test_a8_citation_check_fails_twice():
    s = Script(research=[BAD, BAD])
    r = ask(s)
    assert (r.outcome, r.message, trace(r)) == ("abstain", abstention("es"), (4, 1, None))
    assert s.verifier_calls == []


def test_a9_verifier_revise_twice():
    s = Script(research=[GOOD, GOOD], verdicts=[verdict("revise"), verdict("revise")])
    r = ask(s)
    assert (r.outcome, r.message, trace(r)) == ("abstain", abstention("es"), (4, 1, "revise"))
    assert len(s.research_calls) == 2 and len(s.verifier_calls) == 2


def test_a10_verifier_abstain():
    s = Script(research=[GOOD], verdicts=[verdict("abstain")])
    r = ask(s)
    assert (r.outcome, r.message, trace(r)) == ("abstain", abstention("es"), (2, 0, "abstain"))
    assert len(s.research_calls) == 1


@pytest.mark.parametrize("second", [CLARIFY, ABSTAIN])
def test_a11_researcher_changes_course_after_revision(second):
    s = Script(research=[GOOD, second], verdicts=[verdict("revise")])
    r = ask(s)
    expected = second.message if second.outcome == "clarify" else abstention("es")
    assert (r.outcome, r.message, trace(r)) == (second.outcome, expected, (4, 1, None))
    assert len(s.verifier_calls) == 1


def test_verifier_revise_then_citation_check_fails_clears_verdict():
    s = Script(research=[GOOD, BAD], verdicts=[verdict("revise")])
    r = ask(s)
    assert (r.outcome, r.message, trace(r)) == ("abstain", abstention("es"), (4, 1, None))
    assert len(s.verifier_calls) == 1


def test_logs_one_line_per_node(caplog):
    caplog.set_level(logging.INFO, logger="pool_qa.graph")
    ask(Script(research=[BAD, GOOD], verdicts=[verdict("pass")]))
    lines = [json.loads(rec.message) for rec in caplog.records]
    assert [line["node"] for line in lines] == [
        "intake",
        "researcher",
        "check",
        "revise",
        "researcher",
        "check",
        "verifier",
        "build",
    ]
    assert len({line["request_id"] for line in lines}) == 1
    assert lines[1] | {"ms": 0} == {
        "request_id": lines[0]["request_id"],
        "node": "researcher",
        "ms": 0,
        "outcome": "answer",
        "citations": 1,
        "search_calls": 2,
        "retrieved": [CHUNK.chunk_id],
        "tokens": {},
    }
    assert lines[2]["issues"] and lines[6]["verdict"] == "pass" and lines[7]["outcome"] == "answer"


def test_a18_history_truncated_for_intake_and_researcher():
    history = [Turn(role="user" if i % 2 == 0 else "assistant", content=f"t{i}") for i in range(8)]
    s = Script(research=[ABSTAIN])
    ask(s, AskRequest(question="q", history=history), history_turns=5)
    expected = ["t0", "t3", "t4", "t5", "t6", "t7"]
    assert [t.content for t in s.intake_calls[0]] == expected
    assert [t.content for t in s.research_calls[0][0]] == expected


def test_a21_default_agents_use_per_agent_model_strings(monkeypatch):
    import pool_qa.graph as graph_module

    built = []
    monkeypatch.setattr(graph_module, "chat_model", lambda model, settings: built.append(model) or object())
    settings = Settings(
        _env_file=None, intake_model="m-intake", researcher_model="m-research", verifier_model="m-verify"
    )
    graph_module.default_agents(settings)
    assert built == ["m-intake", "m-research", "m-verify"]


def test_deadline_raises_request_timeout():
    class Slow(Script):
        async def intake(self, question, history):
            await asyncio.sleep(1)
            return PROCEED

    with pytest.raises(RequestTimeout):
        ask(Slow(), request_deadline_s=0.05)


def test_verifier_pass_with_unsupported_claim_revises_then_abstains():
    contradiction = VerifierResult(
        verdict="pass", claims=[Claim(text="Cada año.", supported=False, chunk_ids=[])], issues=[]
    )
    s = Script(research=[GOOD, GOOD], verdicts=[contradiction, contradiction])
    r = ask(s)
    assert (r.outcome, r.message, trace(r)) == ("abstain", abstention("es"), (4, 1, "revise"))
    assert s.research_calls[1][1] == ["Unsupported claim: Cada año."]


async def malformed(*args):
    raise MalformedOutput("bad output")


@pytest.mark.parametrize("stage, language", [("intake", "en"), ("researcher", "es"), ("verifier", "es")])
def test_malformed_output_abstains(stage, language):
    s = Script(research=[GOOD], verdicts=[verdict("pass")])
    agents = s.agents()
    setattr(agents, stage, malformed)
    request = AskRequest(question="¿Cada cuánto?")
    r = asyncio.run(make_ask(agents, Settings(_env_file=None))(request))
    assert (r.outcome, r.language, r.message, r.citations) == ("abstain", language, abstention(language), [])
    assert r.trace.verdict is None
    assert_invariants(r, {CHUNK.chunk_id: CHUNK})
