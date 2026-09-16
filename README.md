# Pool Equipment Technical Assistant

Multi-agent question answering over pool equipment documents for pool professionals. Answers cite the pool equipment documents or abstain.

## Status

Tier 0 in progress: contract models, chunked English pages, and BM25 search are in place; agents, API, and eval are not. See `DESIGN.md` § Tiers.

## Run

Requires Python 3.12, `uv`, and `ANTHROPIC_API_KEY` in `.env`.

```
uv sync
uv run pytest
uv run python -m pool_qa.eval.run
```

The parsed manual is committed in `data/chunks.jsonl`. Tier 0 chunking is structure-aware with fallback: pages are split at numbered section headings, pages without headings stay whole, and chunks are capped at 2,000 characters (`DECISIONS.md` D19). Regenerate with `uv run python -m pool_qa.ingest.pypdf_chunks`.

## Documents

- `DESIGN.md`: architecture, tiers, evaluation, known limitations
- `CONTRACT.md`: API and agent schemas
- `DECISIONS.md`: decision log
- `DEPLOYMENT.md`: production deployment (written in Tier 0)
