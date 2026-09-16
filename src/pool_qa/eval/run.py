import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from pool_qa.contract import AskRequest, GoldenRecord
from pool_qa.eval.gates import (
    ErrorInfo,
    QuestionResult,
    Report,
    compute_gates,
    tier0_status,
)
from pool_qa.graph import RequestTimeout, default_agents, make_ask
from pool_qa.llm import ProviderError
from pool_qa.retrieval import load_chunks
from pool_qa.settings import ROOT, Settings

GOLDEN = ROOT / "eval" / "golden.jsonl"
REPORTS = ROOT / "eval" / "reports"


def load_golden(path: Path) -> list[GoldenRecord]:
    with path.open(encoding="utf-8") as f:
        return [GoldenRecord.model_validate_json(line) for line in f if line.strip()]


async def run_all(records: list[GoldenRecord], ask) -> list[QuestionResult]:
    results = []
    for record in records:
        response, error = None, None
        try:
            response = await ask(AskRequest(question=record.question))
        except ProviderError as exc:
            error = ErrorInfo(type="provider_error", detail=str(exc))
        except RequestTimeout as exc:
            error = ErrorInfo(type="timeout", detail=str(exc))
        except Exception as exc:  # noqa: BLE001 -- record any failure per question, don't abort the run
            error = ErrorInfo(type=type(exc).__name__, detail=str(exc))
        print(f"{record.id}: {response.outcome if response else error.type}", file=sys.stderr, flush=True)
        results.append(
            QuestionResult(
                id=record.id,
                expected_outcome=record.expected_outcome,
                expected_pages=record.expected_pages,
                response=response,
                error=error,
            )
        )
    return results


def render(report: Report) -> str:
    lines = [f"{'id':<8}{'expected':<10}{'actual':<10}citations / error"]
    for r in report.results:
        actual, detail = (r.response.outcome, len(r.response.citations)) if r.response else ("error", r.error.type)
        lines.append(f"{r.id:<8}{r.expected_outcome:<10}{actual:<10}{detail}")
    lines.append("")
    lines.append(f"{'gate':<42}{'tier':<6}{'threshold':<11}{'value':<8}status")
    for g in report.gates:
        lines.append(f"{g.name:<42}{g.tier:<6}{g.threshold:<11}{g.value or '-':<8}{g.status}")
        lines += [f"  - {failure}" for failure in g.failures]
    lines += ["", f"Tier 0: {report.tier0}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None, ask=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m pool_qa.eval.run", description="Run the golden set and report gates."
    )
    parser.add_argument("--golden", type=Path, default=GOLDEN)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS)
    args = parser.parse_args(argv)

    settings = Settings()
    records = load_golden(args.golden)
    chunks = {c.chunk_id: c for c in load_chunks(settings.chunks_path)}
    if ask is None:
        try:
            ask = make_ask(default_agents(settings), settings)
        except Exception as exc:  # noqa: BLE001 -- CLI boundary: report any failure as exit code 2
            print(f"error: {type(exc).__name__}", file=sys.stderr)
            return 2

    results = asyncio.run(run_all(records, ask))
    gates = compute_gates(results, chunks)
    report = Report(
        created_at=datetime.now(UTC),
        tier0=tier0_status(gates),
        results=results,
        gates=gates,
    )
    args.reports_dir.mkdir(parents=True, exist_ok=True)
    path = args.reports_dir / f"{report.created_at:%Y%m%dT%H%M%SZ}.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(render(report))
    print(f"\nReport: {path}")
    return 0 if report.tier0 == "pass" else 1


if __name__ == "__main__":
    logging.basicConfig(format="%(message)s")
    logging.getLogger("pool_qa").setLevel(logging.INFO)
    sys.exit(main())
