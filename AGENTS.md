# AGENTS.md

Multi-agent question answering over pool equipment documents. Python 3.12, `uv`.

## Sources of truth

| File | Owns |
|---|---|
| `DESIGN.md` | Architecture, tiers, evaluation gates, known limitations |
| `CONTRACT.md` | Schemas, invariants, error format |
| `DECISIONS.md` | Decisions and rationale; append-only |
| `eval/golden.jsonl` | Golden questions; dev-owned |

Code conforms to these files. If code and a file disagree, stop and report; do not silently change either.

## Commands

```
uv sync                                       # install
uv run pytest                                 # tests
uv run python -m pool_qa.ingest.pypdf_chunks  # regenerate data/chunks.jsonl
uv run python -m pool_qa.eval.run             # eval report
```

Add new commands here when they are created.

## Setup

- `ANTHROPIC_API_KEY` in `.env`. Never commit `.env`.
- Source document: `data/user_manual.pdf`. Parsed output is committed; the app does not run ingestion.

## Workflow

- Work in the current tier only (`DESIGN.md` § Tiers). A tier is done when its exit gates pass, tests pass, and docs match the code.
- Interfaces and schemas in `CONTRACT.md` are fixed; change implementations, not signatures.
- Every change keeps the app running end to end.
- Run `uv run pytest` before reporting work as done. Run the eval when agents, prompts, retrieval, or ingestion change, and report the gate results.

## Conventions

- Pydantic v2 models mirror `CONTRACT.md` names exactly.
- Models are configured per agent by config string; no provider-specific API features.
- Code checks (citations, quotes, history, clarification cap) are plain functions with unit tests; no LLM calls in tests.
- Missing chunk metadata is empty or null, never omitted.
- Comments only where the code cannot say it.

## Commits

- One commit per batch of related changes.
- Message: `type(scope): one-line description`, e.g. `feat(retrieval): add bm25 search`. Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`. Scope optional.

## Boundaries

Ask first:
- Changing `CONTRACT.md`, `DESIGN.md`, or `eval/golden.jsonl`.
- Adding a dependency not listed in `DESIGN.md` § Stack.
- Starting work from a later tier.

Never:
- Edit or delete existing `DECISIONS.md` entries; propose new entries for the dev to approve.
- Weaken an eval gate or golden question to make a run pass.
- Write prompts that allow answers from general knowledge; the system cites or abstains.
- Commit secrets or run paid calls in loops without a stated budget.
