# Pool Equipment Technical Assistant

Multi-agent question answering over pool equipment documents for pool professionals. Answers cite the pool equipment documents or abstain.

## Status

Tier 0 not started. See `DESIGN.md` § Tiers.

## Run

Requires Python 3.12, `uv`, and `ANTHROPIC_API_KEY` in `.env`.

```
uv sync
uv run pytest
uv run python -m pool_qa.eval.run
```

## Documents

- `DESIGN.md`: architecture, tiers, evaluation, known limitations
- `CONTRACT.md`: API and agent schemas
- `DECISIONS.md`: decision log
- `DEPLOYMENT.md`: production deployment (written in Tier 0)
