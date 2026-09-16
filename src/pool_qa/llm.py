from collections.abc import Callable
from typing import Any

import anthropic
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from pool_qa.settings import Settings


class ProviderError(Exception):
    """LLM API call failed after retries."""


class MalformedOutput(Exception):
    """Model returned unusable output twice."""


def chat_model(model: str, settings: Settings) -> BaseChatModel:
    kwargs: dict[str, Any] = {"timeout": settings.llm_timeout_s, "max_retries": settings.llm_max_retries}
    if settings.anthropic_api_key:
        kwargs["api_key"] = settings.anthropic_api_key
    return init_chat_model(model, **kwargs)


async def invoke(runnable, messages: list) -> Any:
    try:
        return await runnable.ainvoke(messages)
    except anthropic.APIError as exc:
        raise ProviderError(f"{type(exc).__name__}: {exc}") from exc


async def structured[T: BaseModel](
    model, schema: type[T], messages: list, valid: Callable[[T], bool] = lambda _: True
) -> T:
    runnable = model.with_structured_output(schema, include_raw=True, method="function_calling")
    for _ in range(2):
        out = await invoke(runnable, messages)
        parsed = out["parsed"]
        if parsed is not None and valid(parsed):
            return parsed
    raise MalformedOutput(f"malformed {schema.__name__} output")
