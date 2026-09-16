# Pool Equipment Technical Assistant

Multi-agent question answering over pool equipment documents for pool professionals. Answers cite the pool equipment documents or abstain.

## Status

Tier 0 in progress: contract models, chunked English pages, BM25 search, the three-agent graph, `POST /ask`, and the CLI are in place; the eval command is not. See `DESIGN.md` § Tiers.

## Run

Requires Python 3.12, `uv`, and `ANTHROPIC_API_KEY` in `.env`.

```
uv sync
uv run pytest
uv run python -m pool_qa.cli "How often should the mechanical seal be replaced?"
uv run python -m pool_qa.cli "..." --json --history history.json
uv run uvicorn pool_qa.api:app
curl -s localhost:8000/ask -H 'content-type: application/json' -d '{"question": "How do I prime the pump?"}'
```

`history.json` is a list of turns (`role`, `content`, `outcome`) as in `CONTRACT.md`. Errors return `ErrorResponse`: 422 invalid request, 502 provider failure, 504 deadline; the CLI exits 2 or 1.

The parsed manual is committed in `data/chunks.jsonl`. Tier 0 chunking is structure-aware with fallback: pages are split at numbered section headings, pages without headings stay whole, and chunks are capped at 2,000 characters (`DECISIONS.md` D19). Regenerate with `uv run python -m pool_qa.ingest.pypdf_chunks`.

## Documents

- `DESIGN.md`: architecture, tiers, evaluation, known limitations
- `CONTRACT.md`: API and agent schemas
- `DECISIONS.md`: decision log
- `DEPLOYMENT.md`: production deployment (written in Tier 0)
