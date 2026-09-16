from pool_qa.contract import AskResponse, Citation, Trace
from pool_qa.retrieval import load_chunks
from pool_qa.settings import Settings

CHUNKS = {c.chunk_id: c for c in load_chunks(Settings().chunks_path)}


def citation(**overrides) -> Citation:
    fields = {
        "id": "c1",
        "chunk_id": "user_manual-p11-1",
        "document": "user_manual.pdf",
        "page": 11,
        "page_in_language": None,
        "section": "4. START-UP INSTRUCTIONS",
        "quote": "PRIOR TO START-UP",
    }
    return Citation(**(fields | overrides))


def answer_on(page: int) -> AskResponse:
    chunk = next(c for c in CHUNKS.values() if c.page == page)
    return response(
        citations=[
            citation(
                chunk_id=chunk.chunk_id,
                page=page,
                section=chunk.section,
                quote=chunk.text.splitlines()[0][:200],
            )
        ]
    )


def response(
    outcome: str = "answer", message: str | None = None, citations: list[Citation] | None = None
) -> AskResponse:
    if outcome == "answer":
        message = "Check before start-up [c1]." if message is None else message
        citations = [citation()] if citations is None else citations
    return AskResponse(
        outcome=outcome,
        language="en",
        message=message or f"{outcome} message",
        citations=citations or [],
        warnings=[],
        trace=Trace(search_calls=1, revisions=0, verdict="pass" if outcome == "answer" else None),
    )
