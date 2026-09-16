import pytest
from fastapi.testclient import TestClient

from pool_qa.api import app, get_ask
from pool_qa.contract import AskResponse, ErrorResponse, Trace
from pool_qa.graph import RequestTimeout
from pool_qa.llm import ProviderError

RESPONSE = AskResponse(
    outcome="abstain", language="en", message="No info.", citations=[], warnings=[],
    trace=Trace(search_calls=1, revisions=0, verdict=None),
)


def client_with(ask):
    app.dependency_overrides[get_ask] = lambda: ask
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


async def ok(request):
    return RESPONSE


def test_a23_valid_request():
    r = client_with(ok).post("/ask", json={"question": "How often?", "history": []})
    assert r.status_code == 200
    assert AskResponse.model_validate(r.json()) == RESPONSE


@pytest.mark.parametrize("body", [
    {},
    {"question": ""},
    {"question": "   "},
    {"question": "q", "history": [{"role": "system", "content": "x"}]},
])
def test_a24_invalid_request(body):
    r = client_with(ok).post("/ask", json=body)
    assert r.status_code == 422
    assert ErrorResponse.model_validate(r.json()).error == "invalid_request"


def raising(exc):
    async def ask(request):
        raise exc
    return ask


@pytest.mark.parametrize("exc, status, error", [
    (ProviderError("overloaded"), 502, "provider_error"),
    (RequestTimeout("slow"), 504, "timeout"),
])
def test_a25_error_mapping(exc, status, error):
    r = client_with(raising(exc)).post("/ask", json={"question": "q"})
    assert r.status_code == status
    assert ErrorResponse.model_validate(r.json()).error == error


def test_a25_unexpected_error_hides_details():
    r = client_with(raising(KeyError("secret-internal"))).post("/ask", json={"question": "q"})
    assert r.status_code == 500
    assert "secret-internal" not in r.text and "Traceback" not in r.text
