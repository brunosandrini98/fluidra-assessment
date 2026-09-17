import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager

LOGGER_NAME = "pool_qa.graph"


class Capture(logging.Handler):
    """Collects one parsed record per JSON log line from logger "pool_qa.graph"."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(json.loads(record.getMessage()))


@contextmanager
def capture() -> Iterator[Capture]:
    logger = logging.getLogger(LOGGER_NAME)
    handler = Capture()
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


def malformed(records: list[dict]) -> bool:
    return any(r.get("malformed") for r in records)


def tokens(records: list[dict]) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for record in records:
        for model, usage in record.get("tokens", {}).items():
            bucket = totals.setdefault(model, {"input": 0, "output": 0})
            bucket["input"] += usage["input"]
            bucket["output"] += usage["output"]
    return totals


def retrieved(records: list[dict]) -> list[str]:
    ids: set[str] = set()
    for record in records:
        ids.update(record.get("retrieved", []))
    return sorted(ids)
