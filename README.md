# Pool Equipment Technical Assistant

Multi-agent question answering over pool equipment documents for pool professionals. Answers cite the pool equipment documents or abstain.

- **Intake:** refuses off-topic questions, detects the language, writes the search query.
- **Researcher:** searches the manual and drafts an answer with verbatim quoted citations, or asks one clarifying question, or abstains.
- **Verifier:** checks each claim against its cited chunks with fresh context; passes, requests one revision, or abstains.

Citation IDs and quotes are checked in code before the Verifier runs. See `DESIGN.md` § Architecture.

## Scope and assumptions

- Users are certified pool professionals. The tool is advisory; the technician remains responsible for the work.
- No general knowledge: the system cites the documents or abstains.
- One example manual today; the design assumes many brands, languages and document types later (`DESIGN.md` § Known limitations).

## Status

Features are planned in tiers (`DESIGN.md` § Tiers). Tier 0 is functional: a question goes through the three agents over the English pages of the manual, from the CLI or `POST /ask`, with an eval command and a container image. Later tiers improve ingestion, retrieval and evaluation behind the same interfaces.

## Work in progress

Draft PRs, not merged:

- `feat/eval-coverage`: broaden the eval so results say more about retrieval and answer quality across question types.
- `spike/docling`: test whether layout-aware parsing can replace the hand transcriptions of tables and figures.

Built with AI coding agents: `AGENTS.md` holds their instructions, `DECISIONS.md` the decisions, and each PR one batch of work.

## Run

Requires Python 3.12, `uv`, and `ANTHROPIC_API_KEY` in `.env`.

```
uv sync
uv run pytest
uv run python -m pool_qa.eval.run
uv run python -m pool_qa.cli "How often should the mechanical seal be replaced?"
uv run python -m pool_qa.cli "..." --json --history history.json
uv run uvicorn pool_qa.api:app
docker build -t pool-qa . && docker run --rm -p 8000:8000 --env-file .env pool-qa
curl -s localhost:8000/ask -H 'content-type: application/json' -d '{"question": "How do I prime the pump?"}'
```

`history.json` is a list of turns (`role`, `content`, `outcome`) as in `CONTRACT.md`. Errors return `ErrorResponse`: 422 invalid request, 502 provider failure, 504 deadline; the CLI exits 2 or 1.

The eval runs `eval/golden.jsonl` through the app with live LLM calls, prints a table, and writes `eval/reports/<UTC timestamp>.json` (not committed). Tier 0 gates are defined in `DECISIONS.md` D25 and D31; later-tier gates are reported as pending. Exit code 0 means Tier 0 gates pass, 1 means a gate failed.

The parsed manual is committed in `data/chunks.jsonl`. Tier 0 chunking is structure-aware with fallback: pages are split at numbered section headings, pages without headings stay whole, and chunks are capped at 2,000 characters (`DECISIONS.md` D19). Regenerate with `uv run python -m pool_qa.ingest.pypdf_chunks`. Content the PDF text loses — the page 13 troubleshooting matrix, Fig. 4 and the page 97 installation zones — is transcribed by hand into `data/transcriptions.jsonl` and replaces those pages at ingestion (`DECISIONS.md` D27).

## Documents

- `DESIGN.md`: architecture, tiers, evaluation, known limitations
- `CONTRACT.md`: API and agent schemas
- `DECISIONS.md`: decision log
- `DEPLOYMENT.md`: production deployment on AWS
