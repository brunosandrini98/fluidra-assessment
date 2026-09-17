import asyncio
import inspect
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypedDict

from langchain_core.callbacks import get_usage_metadata_callback
from langgraph.graph import END, START, StateGraph

from pool_qa import retrieval
from pool_qa.agents.intake import run_intake
from pool_qa.agents.researcher import ResearchRun, run_researcher
from pool_qa.agents.verifier import run_verifier
from pool_qa.checks import citation_check, enforce_claims, truncate_history
from pool_qa.contract import (
    AskRequest,
    AskResponse,
    Chunk,
    IntakeResult,
    ResearchResult,
    Turn,
    VerifierResult,
)
from pool_qa.llm import MalformedOutput, chat_model
from pool_qa.response import abstain_response, build_response
from pool_qa.settings import Settings

logger = logging.getLogger(__name__)


class RequestTimeout(Exception):
    """Request deadline exceeded."""


@dataclass
class Agents:
    intake: Callable[[str, list[Turn]], Awaitable[IntakeResult]]
    researcher: Callable[[str, list[Turn], IntakeResult, list[str]], Awaitable[ResearchRun]]
    verifier: Callable[[str, str, str, list[Chunk]], Awaitable[VerifierResult]]


class State(TypedDict):
    request_id: str
    question: str
    history: list[Turn]
    intake: IntakeResult | None
    research: ResearchResult | None
    verifier: VerifierResult | None
    retrieved: dict[str, Chunk]
    issues: list[str]
    revisions: int
    search_calls: int
    malformed: bool
    response: AskResponse | None


def build_graph(agents: Agents):
    async def intake(s: State) -> dict:
        try:
            return {"intake": await agents.intake(s["question"], s["history"])}
        except MalformedOutput:
            return {"malformed": True}

    async def researcher(s: State) -> dict:
        try:
            run = await agents.researcher(s["question"], s["history"], s["intake"], s["issues"])
        except MalformedOutput:
            return {"malformed": True}
        return {
            "research": run.result,
            "search_calls": s["search_calls"] + run.search_calls,
            "retrieved": {**s["retrieved"], **run.retrieved},
        }

    def check(s: State) -> dict:
        return {"issues": citation_check(s["research"], s["retrieved"])}

    async def verifier(s: State) -> dict:
        research = s["research"]
        chunks = [s["retrieved"][c.chunk_id] for c in research.citations]
        try:
            result = enforce_claims(
                await agents.verifier(s["question"], s["intake"].language, research.message, chunks)
            )
        except MalformedOutput:
            return {"malformed": True}
        return {"verifier": result, "issues": result.issues}

    def revise(s: State) -> dict:
        return {"revisions": 1, "verifier": None}

    def build(s: State) -> dict:
        if s["malformed"]:
            language = s["intake"].language if s["intake"] else "en"
            return {"response": abstain_response(language, s["revisions"], s["search_calls"])}
        return {
            "response": build_response(
                s["intake"], s["research"], s["verifier"], s["retrieved"], s["revisions"], s["search_calls"]
            )
        }

    def after_intake(s: State) -> str:
        if s["malformed"]:
            return "build"
        return "researcher" if s["intake"].decision == "proceed" else "build"

    def after_researcher(s: State) -> str:
        if s["malformed"]:
            return "build"
        return "check" if s["research"].outcome == "answer" else "build"

    def after_check(s: State) -> str:
        if not s["issues"]:
            return "verifier"
        return "revise" if s["revisions"] == 0 else "build"

    def after_verifier(s: State) -> str:
        if s["malformed"]:
            return "build"
        return "revise" if s["verifier"].verdict == "revise" and s["revisions"] == 0 else "build"

    graph = StateGraph(State)
    for name, node in [
        ("intake", intake),
        ("researcher", researcher),
        ("check", check),
        ("verifier", verifier),
        ("revise", revise),
        ("build", build),
    ]:
        graph.add_node(name, logged(name, node))
    graph.add_edge(START, "intake")
    graph.add_conditional_edges("intake", after_intake, ["researcher", "build"])
    graph.add_conditional_edges("researcher", after_researcher, ["check", "build"])
    graph.add_conditional_edges("check", after_check, ["verifier", "revise", "build"])
    graph.add_conditional_edges("verifier", after_verifier, ["revise", "build"])
    graph.add_edge("revise", "researcher")
    graph.add_edge("build", END)
    return graph.compile()


def summary(s: State, update: dict) -> dict:
    out: dict = {}
    if intake := update.get("intake"):
        out |= {"decision": intake.decision, "language": intake.language}
    if research := update.get("research"):
        out |= {
            "outcome": research.outcome,
            "citations": len(research.citations),
            "search_calls": update["search_calls"] - s["search_calls"],
            "retrieved": sorted(update["retrieved"]),
        }
    if "issues" in update:
        out["issues"] = update["issues"]
    if verifier := update.get("verifier"):
        out["verdict"] = verifier.verdict
    if response := update.get("response"):
        out["outcome"] = response.outcome
    if update.get("malformed"):
        out["malformed"] = True
    return out


def logged(name: str, node: Callable) -> Callable:
    async def run(s: State) -> dict:
        start = time.perf_counter()
        with get_usage_metadata_callback() as usage:
            update = node(s)
            if inspect.isawaitable(update):
                update = await update
        tokens = {
            model: {"input": u["input_tokens"], "output": u["output_tokens"]}
            for model, u in usage.usage_metadata.items()
        }
        logger.info(
            json.dumps(
                {
                    "request_id": s["request_id"],
                    "node": name,
                    "ms": round((time.perf_counter() - start) * 1000),
                    **summary(s, update),
                    "tokens": tokens,
                },
                ensure_ascii=False,
            )
        )
        return update

    return run


def make_ask(agents: Agents, settings: Settings) -> Callable[[AskRequest], Awaitable[AskResponse]]:
    graph = build_graph(agents)

    async def ask(request: AskRequest) -> AskResponse:
        state: State = {
            "request_id": uuid.uuid4().hex[:8],
            "question": request.question,
            "history": truncate_history(request.history, settings.history_turns),
            "intake": None,
            "research": None,
            "verifier": None,
            "retrieved": {},
            "issues": [],
            "revisions": 0,
            "search_calls": 0,
            "malformed": False,
            "response": None,
        }
        try:
            final = await asyncio.wait_for(graph.ainvoke(state), settings.request_deadline_s)
        except TimeoutError as exc:
            raise RequestTimeout(f"request exceeded {settings.request_deadline_s}s") from exc
        return final["response"]

    return ask


def default_agents(settings: Settings) -> Agents:
    pivot = settings.pivot_language
    intake_model = chat_model(settings.intake_model, settings)
    researcher_model = chat_model(settings.researcher_model, settings)
    verifier_model = chat_model(settings.verifier_model, settings)

    async def intake(question, history):
        return await run_intake(intake_model, pivot, question, history)

    async def researcher(question, history, intake_result, issues):
        return await run_researcher(
            researcher_model, retrieval.search, settings, question, history, intake_result, issues
        )

    async def verifier(question, language, draft, chunks):
        return await run_verifier(verifier_model, pivot, question, language, draft, chunks)

    return Agents(intake=intake, researcher=researcher, verifier=verifier)
