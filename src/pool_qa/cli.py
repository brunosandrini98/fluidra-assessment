import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from pydantic import ValidationError

from pool_qa.contract import AskRequest, AskResponse, ErrorResponse
from pool_qa.graph import RequestTimeout, default_agents, make_ask
from pool_qa.llm import ProviderError
from pool_qa.settings import Settings


def render(response: AskResponse) -> str:
    lines = [f"Outcome: {response.outcome} ({response.language})", "", response.message]
    if response.citations:
        lines += ["", "Citations:"]
        for c in response.citations:
            section = f", {c.section}" if c.section else ""
            lines.append(f'  [{c.id}] {c.document} p. {c.page}{section}: "{c.quote}"')
    t = response.trace
    lines += ["", f"Trace: search_calls={t.search_calls} revisions={t.revisions} verdict={t.verdict}"]
    return "\n".join(lines)


def _error(error: str, detail: str, code: int) -> int:
    print(ErrorResponse(error=error, detail=detail).model_dump_json())
    return code


def main(argv: list[str] | None = None, ask=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pool_qa.cli", description="Ask about pool equipment documents.")
    parser.add_argument("question")
    parser.add_argument("--history", type=Path, help="JSON file with a list of turns")
    parser.add_argument("--json", action="store_true", help="print the response as JSON")
    args = parser.parse_args(argv)

    try:
        history = json.loads(args.history.read_text(encoding="utf-8")) if args.history else []
        request = AskRequest(question=args.question, history=history)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        return _error("invalid_request", str(exc), 2)

    try:
        if ask is None:
            settings = Settings()
            ask = make_ask(default_agents(settings), settings)
        response = asyncio.run(ask(request))
    except ProviderError as exc:
        return _error("provider_error", str(exc), 1)
    except RequestTimeout as exc:
        return _error("timeout", str(exc), 1)
    except Exception as exc:  # noqa: BLE001 -- CLI boundary: report any failure as exit code 1
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(response.model_dump_json(indent=2) if args.json else render(response))
    return 0


if __name__ == "__main__":
    logging.basicConfig(format="%(message)s")
    logging.getLogger("pool_qa").setLevel(logging.INFO)
    sys.exit(main())
