import asyncio

import pytest

from fakes import FakeStructuredModel
from pool_qa.contract import IntakeResult
from pool_qa.llm import ProviderError, chat_model, structured
from pool_qa.settings import Settings

INTAKE = IntakeResult(decision="proceed", language="en", retrieval_query="prime pump")


def test_chat_model_built_from_config_string(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    s = Settings(_env_file=None, intake_model="claude-haiku-4-5", llm_timeout_s=12, llm_max_retries=4)
    model = chat_model(s.intake_model, s)
    assert model.model == "claude-haiku-4-5"
    assert model.default_request_timeout == 12
    assert model.max_retries == 4


def test_structured_returns_parsed():
    model = FakeStructuredModel([INTAKE])
    assert asyncio.run(structured(model, IntakeResult, ["m"])) == INTAKE
    assert model.schema is IntakeResult


def test_structured_retries_once_on_malformed_output():
    model = FakeStructuredModel([None, INTAKE])
    assert asyncio.run(structured(model, IntakeResult, ["m"])) == INTAKE
    assert len(model.calls) == 2


def test_structured_raises_after_second_malformed_output():
    model = FakeStructuredModel([None, None])
    with pytest.raises(ProviderError):
        asyncio.run(structured(model, IntakeResult, ["m"]))


def test_structured_invalid_by_predicate_counts_as_malformed():
    model = FakeStructuredModel([INTAKE, INTAKE])
    with pytest.raises(ProviderError):
        asyncio.run(structured(model, IntakeResult, ["m"], valid=lambda r: False))


def test_provider_exception_wrapped():
    model = FakeStructuredModel([RuntimeError("503 overloaded")])
    with pytest.raises(ProviderError):
        asyncio.run(structured(model, IntakeResult, ["m"]))
