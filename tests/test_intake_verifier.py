import asyncio
import inspect

import pytest

from fakes import FakeStructuredModel, make_chunk
from pool_qa.agents.intake import intake_messages, run_intake
from pool_qa.agents.verifier import run_verifier, verifier_messages
from pool_qa.contract import IntakeResult, Turn, VerifierResult
from pool_qa.llm import ProviderError

CHUNK = make_chunk("user_manual-p12-1", "Replace the mechanical seal every year.")


def test_intake_returns_structured_result_and_sees_history():
    result = IntakeResult(decision="proceed", language="es", retrieval_query="mechanical seal replacement")
    model = FakeStructuredModel([result])
    history = [Turn(role="user", content="Hola"), Turn(role="assistant", content="Hola", outcome="answer")]
    assert asyncio.run(run_intake(model, "en", "¿Cada cuánto cambio el sello?", history)) == result
    text = "\n".join(m.content for m in model.calls[0])
    assert "¿Cada cuánto cambio el sello?" in text and "Hola" in text


def test_intake_prompt_scope():
    system = intake_messages("q", [], "en")[0].content
    assert "refuse" in system and "proceed" in system and "ISO 639-1" in system


def test_verifier_prompt_states_languages():  # invariant 11
    system = verifier_messages("q", "es", "draft", [CHUNK], "en")[0].content
    assert "pivot language (en)" in system
    assert "user's language (es)" in system
    assert "never" in system.lower() and "rewrite" in system.lower()
    assert "A factual claim without a [chunk_id] marker is unsupported." in system


def test_verifier_receives_full_chunk_text_and_no_history():
    assert "history" not in inspect.signature(run_verifier).parameters
    text = "\n".join(m.content for m in verifier_messages("q", "es", "draft [user_manual-p12-1]", [CHUNK], "en"))
    assert CHUNK.text in text and "draft [user_manual-p12-1]" in text


def test_verifier_revise_without_issues_is_malformed():
    bad = VerifierResult(verdict="revise", claims=[], issues=[])
    model = FakeStructuredModel([bad, bad])
    with pytest.raises(ProviderError):
        asyncio.run(run_verifier(model, "en", "q", "en", "d", [CHUNK]))


def test_verifier_malformed_then_valid():
    good = VerifierResult(verdict="pass", claims=[], issues=[])
    model = FakeStructuredModel([None, good])
    assert asyncio.run(run_verifier(model, "en", "q", "en", "d", [CHUNK])) == good
