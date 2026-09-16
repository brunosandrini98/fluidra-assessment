import re

import pytest

from eval_stubs import CHUNKS, response
from pool_qa.eval.gates import CITATIONS, COMPLETED, FALSE_ANSWERS, Report, compute_gates
from pool_qa.eval.run import GOLDEN, load_golden, main
from pool_qa.graph import RequestTimeout
from pool_qa.llm import ProviderError
from pool_qa.settings import ROOT

RECORDS = load_golden(GOLDEN)


def stub(overrides=None):
    overrides = overrides or {}
    by_question = {r.question: r for r in RECORDS}

    async def ask(request):
        record = by_question[request.question]
        out = overrides.get(record.id, record.expected_outcome)
        if isinstance(out, Exception):
            raise out
        return response(out)

    return ask


def run(tmp_path, ask):
    code = main(["--reports-dir", str(tmp_path)], ask=ask)
    [path] = tmp_path.glob("*.json")
    return code, Report.model_validate_json(path.read_text(encoding="utf-8")), path


def gate(report, name):
    return next(g for g in report.gates if g.name == name)


def test_all_expected_outcomes_pass(tmp_path):  # D3, D8
    code, report, _ = run(tmp_path, stub())
    assert code == 0 and report.tier0 == "pass"
    assert all(g.status == "pass" for g in report.gates if g.tier == 0)
    assert any(g.status == "pending" for g in report.gates)


@pytest.mark.parametrize("qid", ["t0-04", "t0-05"])  # D1, D2
def test_answer_where_abstain_or_refuse_expected_fails(tmp_path, qid):
    code, report, _ = run(tmp_path, stub({qid: "answer"}))
    assert code == 1 and report.tier0 == "fail"
    g = gate(report, FALSE_ANSWERS)
    assert g.status == "fail" and g.failures[0].startswith(f"{qid}: ")


@pytest.mark.parametrize("exc, kind", [(ProviderError("down"), "provider_error"), (RequestTimeout("slow"), "timeout")])  # D7
def test_error_is_recorded_and_run_continues(tmp_path, exc, kind):
    code, report, _ = run(tmp_path, stub({"t0-02": exc}))
    by_id = {r.id: r for r in report.results}
    assert by_id["t0-02"].response is None and by_id["t0-02"].error.type == kind
    assert all(r.response is not None for r in report.results if r.id != "t0-02")
    assert (gate(report, COMPLETED).status, gate(report, COMPLETED).value) == ("fail", "4/5")
    assert code == 1


def test_table(tmp_path, capsys):  # D9
    run(tmp_path, stub({"t0-02": ProviderError("down")}))
    out = capsys.readouterr().out
    for record in RECORDS:
        assert record.id in out
    for part in ("expected", "actual", "provider_error", "Outcome match: 4/5", COMPLETED, CITATIONS, "pending", "Tier 0: fail"):
        assert part in out


def test_report_file(tmp_path, capsys):  # D10
    _, report, path = run(tmp_path, stub())
    assert re.fullmatch(r"\d{8}T\d{6}Z\.json", path.name)
    assert str(path) in capsys.readouterr().out
    assert [r.id for r in report.results] == [r.id for r in RECORDS]
    assert "eval/reports/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_gates_recompute_from_saved_report(tmp_path):  # D11
    _, report, _ = run(tmp_path, stub({"t0-04": "answer", "t0-02": ProviderError("down")}))
    assert compute_gates(report.results, CHUNKS) == report.gates


def test_setup_error_returns_2_without_report(tmp_path, monkeypatch, capsys):
    def broken(settings):
        raise RuntimeError("missing API key")

    monkeypatch.setattr("pool_qa.eval.run.default_agents", broken)
    assert main(["--reports-dir", str(tmp_path)]) == 2
    assert list(tmp_path.iterdir()) == []
    assert "Traceback" not in capsys.readouterr().err
