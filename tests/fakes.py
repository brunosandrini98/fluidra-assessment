from langchain_core.messages import AIMessage

from pool_qa.contract import Chunk


def make_chunk(chunk_id: str, text: str, page: int = 11, section: str | None = "4. START-UP") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document="user_manual.pdf",
        source_type="manual",
        effective_date=None,
        language="en",
        page=page,
        section=section,
        text=text,
        figure_refs=[],
        warning_ids=[],
    )


def ai_tool_call(name: str, args: dict, call_id: str = "call-1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


class FakeStructuredModel:
    """Stands in for `model.with_structured_output(..., include_raw=True)`."""

    def __init__(self, outputs: list):
        self.outputs = list(outputs)
        self.calls: list[list] = []
        self.schema = None

    def with_structured_output(self, schema, **kwargs):
        self.schema = schema
        return self

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        if out is None:
            return {"raw": None, "parsed": None, "parsing_error": ValueError("bad output")}
        return {"raw": None, "parsed": out, "parsing_error": None}


class _Bound:
    def __init__(self, model: "FakeToolModel", tool_choice):
        self.model = model
        self.tool_choice = tool_choice

    async def ainvoke(self, messages):
        self.model.calls.append((self.tool_choice, list(messages)))
        out = self.model.replies.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


class FakeToolModel:
    """Stands in for `model.bind_tools(...)`; records (tool_choice, messages) per call."""

    def __init__(self, replies: list):
        self.replies = list(replies)
        self.calls: list[tuple] = []
        self.tools = None

    def bind_tools(self, tools, tool_choice=None, **kwargs):
        self.tools = tools
        return _Bound(self, tool_choice)
