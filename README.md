# Pool Equipment Technical Assistant

Multi-agent question answering over pool equipment documents for pool professionals. Answers cite the pool equipment documents or abstain.

## Status

Tier 0 complete: contract models, chunked English pages with hand transcriptions, BM25 search, the three-agent graph, `POST /ask`, the CLI, and the eval command. Latest eval (2026-09-16, one run per question): Tier 0 pass — 5/5 outcomes, citations valid, cited pages in expected pages. See `DESIGN.md` § Tiers.

## Run

Requires Python 3.12, `uv`, and `ANTHROPIC_API_KEY` in `.env`.

```
uv sync
uv run pytest
uv run python -m pool_qa.eval.run
uv run python -m pool_qa.cli "How often should the mechanical seal be replaced?"
uv run python -m pool_qa.cli "..." --json --history history.json
uv run uvicorn pool_qa.api:app
curl -s localhost:8000/ask -H 'content-type: application/json' -d '{"question": "How do I prime the pump?"}'
```

`history.json` is a list of turns (`role`, `content`, `outcome`) as in `CONTRACT.md`. Errors return `ErrorResponse`: 422 invalid request, 502 provider failure, 504 deadline; the CLI exits 2 or 1.

The eval runs `eval/golden.jsonl` through the app with live LLM calls, prints a table, and writes `eval/reports/<UTC timestamp>.json` (not committed). Tier 0 gates are defined in `DECISIONS.md` D25 and D31; later-tier gates are reported as pending. Exit code 0 means Tier 0 gates pass, 1 means a gate failed.

The parsed manual is committed in `data/chunks.jsonl`. Tier 0 chunking is structure-aware with fallback: pages are split at numbered section headings, pages without headings stay whole, and chunks are capped at 2,000 characters (`DECISIONS.md` D19). Regenerate with `uv run python -m pool_qa.ingest.pypdf_chunks`. Content the PDF text loses — the page 13 troubleshooting matrix, Fig. 4 and the page 97 installation zones — is transcribed by hand into `data/transcriptions.jsonl` and replaces those pages at ingestion (`DECISIONS.md` D27).

## Documents

- `DESIGN.md`: architecture, tiers, evaluation, known limitations
- `CONTRACT.md`: API and agent schemas
- `DECISIONS.md`: decision log
- `DEPLOYMENT.md`: production deployment (written in Tier 0)
