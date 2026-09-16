FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project

COPY README.md ./
COPY src ./src
COPY data/chunks.jsonl ./data/chunks.jsonl
RUN uv sync --locked

RUN useradd --system app
USER app

EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "pool_qa.api:app", "--host", "0.0.0.0", "--port", "8000"]
