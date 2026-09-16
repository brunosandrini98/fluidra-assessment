from collections.abc import Callable
from dataclasses import dataclass

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

from pool_qa.agents import render_chunks, render_history
from pool_qa.contract import Chunk, Filters, IntakeResult, ResearchResult, Turn
from pool_qa.llm import ProviderError, invoke
from pool_qa.settings import Settings

SearchFn = Callable[[str, Filters, int], list[Chunk]]

SYSTEM = """You answer questions from pool professionals using only document chunks returned by the search tool. Never use general knowledge. If the chunks do not support an answer, abstain.

Tools:
- search(query): returns chunks in the pivot language ({pivot}). Write queries in {pivot}. At most {max_calls} searches.
- submit: your final result. Call it once, when done.

Submit exactly one of:
- "answer": the message in the user's language ({language}). End every claim with a marker [chunk_id] naming the chunk that supports it. Give exactly one citation per cited chunk, with a verbatim quote of at most 200 characters copied from that chunk. Copy characters exactly as they appear, including apostrophes and punctuation. Include the safety instructions (warnings, precautions) that the retrieved chunks give for the task. When the answer depends on a condition, give each branch with its citation. Use square brackets only for markers; write figure references as "Fig. 5".
- "clarify": one short question in the user's language, only when the answer depends on information you do not have and the branches cannot be listed briefly. No citations.
- "abstain": a short reason in the user's language when the chunks do not answer the question. No citations."""

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search",
        "description": "Search the documents. Returns chunks with chunk_id, page, section and text.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}
SUBMIT_TOOL = convert_to_openai_tool(ResearchResult)
SUBMIT_TOOL["function"]["name"] = "submit"
SUBMIT_TOOL["function"]["description"] = "Submit the final result."


@dataclass
class ResearchRun:
    result: ResearchResult
    search_calls: int
    retrieved: dict[str, Chunk]


class SearchTool:
    def __init__(self, search_fn: SearchFn, pivot: str, k: int, max_calls: int):
        self.search_fn = search_fn
        self.pivot = pivot
        self.k = k
        self.max_calls = max_calls
        self.calls = 0
        self.retrieved: dict[str, Chunk] = {}

    def __call__(self, args: dict) -> str:
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            return "Error: search needs a non-empty query."
        if self.calls >= self.max_calls:
            return "Error: search limit reached. Submit your result now."
        self.calls += 1
        chunks = self.search_fn(query, Filters(language=self.pivot), self.k)
        self.retrieved.update({c.chunk_id: c for c in chunks})
        return render_chunks(chunks) or "No results."


def researcher_messages(
    question: str, history: list[Turn], intake: IntakeResult, issues: list[str], pivot: str, max_calls: int
) -> list[BaseMessage]:
    parts = [
        f"Conversation so far:\n{render_history(history)}",
        f"Question:\n{question}",
        f"Suggested search query: {intake.retrieval_query or '-'}",
    ]
    if issues:
        parts.append("A previous draft was rejected. Fix these issues:\n" + "\n".join(f"- {i}" for i in issues))
    return [
        SystemMessage(SYSTEM.format(pivot=pivot, max_calls=max_calls, language=intake.language)),
        HumanMessage("\n\n".join(parts)),
    ]


async def run_researcher(
    model,
    search_fn: SearchFn,
    settings: Settings,
    question: str,
    history: list[Turn],
    intake: IntakeResult,
    issues: list[str],
) -> ResearchRun:
    tool = SearchTool(search_fn, settings.pivot_language, settings.search_k, settings.max_search_calls)
    messages = researcher_messages(
        question, history, intake, issues, settings.pivot_language, settings.max_search_calls
    )
    tools = [SEARCH_TOOL, SUBMIT_TOOL]
    free = model.bind_tools(tools)
    forced = model.bind_tools(tools, tool_choice="submit")
    max_steps = settings.max_search_calls + 2
    malformed = 0

    for step in range(max_steps + 2):
        reply = await invoke(forced if step >= max_steps - 1 else free, messages)
        messages.append(reply)
        if not reply.tool_calls:
            malformed += 1
            messages.append(HumanMessage("Call the submit tool with your result."))
        for call in reply.tool_calls:
            if call["name"] == "search":
                content = tool(call["args"])
            elif call["name"] == "submit":
                try:
                    result = ResearchResult.model_validate(call["args"])
                    return ResearchRun(result, tool.calls, tool.retrieved)
                except ValidationError as exc:
                    malformed += 1
                    content = f"Invalid submit arguments: {exc}"
            else:
                content = f"Error: unknown tool {call['name']}."
            messages.append(ToolMessage(content, tool_call_id=call["id"]))
        if malformed > 1:
            raise ProviderError("researcher returned malformed output twice")
    raise ProviderError("researcher did not submit a result")
