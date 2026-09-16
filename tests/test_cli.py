import json

from pool_qa.cli import main
from pool_qa.contract import AskResponse, Citation, ErrorResponse, Trace
from pool_qa.graph import RequestTimeout
from pool_qa.llm import ProviderError

RESPONSE = AskResponse(
    outcome="answer", language="en", message="Every year [c1].",
    citations=[Citation(id="c1", chunk_id="user_manual-p12-1", document="user_manual.pdf", page=12,
                        page_in_language=None, section="5. MAINTENANCE", quote="Every 1 year")],
    warnings=[], trace=Trace(search_calls=1, revisions=0, verdict="pass"),
)


def recording():
    seen = []

    async def ask(request):
        seen.append(request)
        return RESPONSE

    return ask, seen


def test_text_output(capsys):
    ask, seen = recording()
    assert main(["How often?"], ask=ask) == 0
    out = capsys.readouterr().out
    for part in ("answer", "en", "Every year [c1].", "[c1]", "p. 12", "Every 1 year", "search_calls=1", "verdict=pass"):
        assert part in out
    assert seen[0].question == "How often?"


def test_json_output(capsys):
    ask, _ = recording()
    assert main(["How often?", "--json"], ask=ask) == 0
    assert AskResponse.model_validate_json(capsys.readouterr().out) == RESPONSE


def test_history_file(tmp_path):
    path = tmp_path / "history.json"
    path.write_text(json.dumps([{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Which pump?", "outcome": "clarify"}]))
    ask, seen = recording()
    assert main(["The small one", "--history", str(path)], ask=ask) == 0
    assert [t.outcome for t in seen[0].history] == [None, "clarify"]


def test_blank_question_is_invalid(capsys):
    ask, seen = recording()
    assert main(["   "], ask=ask) == 2
    assert ErrorResponse.model_validate_json(capsys.readouterr().out).error == "invalid_request"
    assert seen == []


def test_bad_history_is_invalid(tmp_path, capsys):
    path = tmp_path / "history.json"
    path.write_text('[{"role": "system", "content": "x"}]')
    ask, _ = recording()
    assert main(["q", "--history", str(path)], ask=ask) == 2
    assert ErrorResponse.model_validate_json(capsys.readouterr().out).error == "invalid_request"


def raising(exc):
    async def ask(request):
        raise exc
    return ask


def test_provider_error_and_timeout(capsys):
    assert main(["q"], ask=raising(ProviderError("down"))) == 1
    assert ErrorResponse.model_validate_json(capsys.readouterr().out).error == "provider_error"
    assert main(["q"], ask=raising(RequestTimeout("slow"))) == 1
    assert ErrorResponse.model_validate_json(capsys.readouterr().out).error == "timeout"
