import re

from pool_qa.checks import normalize_ws
from pool_qa.contract import AskResponse, Chunk


def assert_invariants(response: AskResponse, retrieved: dict[str, Chunk]) -> None:
    assert bool(response.citations) == (response.outcome == "answer")  # 1
    ids = [c.id for c in response.citations]
    assert len(ids) == len(set(ids))
    assert set(re.findall(r"\[(c\d+)\]", response.message)) == set(ids)  # 2
    assert not re.search(r"\[(?!c\d+\])[^\[\]\s]+\]", response.message)
    for c in response.citations:
        assert c.chunk_id in retrieved  # 3
        assert len(c.quote) <= 200 and c.quote in normalize_ws(retrieved[c.chunk_id].text)  # 4
    assert response.warnings == []  # 5
    assert response.trace.revisions in (0, 1)  # 7
