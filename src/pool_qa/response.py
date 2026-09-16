from pool_qa.checks import MARKER, markers, quote_span
from pool_qa.contract import (
    AskResponse, Chunk, Citation, IntakeResult, Outcome, ResearchResult, Trace, VerifierResult,
)
from pool_qa.phrases import abstention, refusal


def build_response(
    intake: IntakeResult,
    research: ResearchResult | None,
    verifier: VerifierResult | None,
    retrieved: dict[str, Chunk],
    revisions: int,
    search_calls: int,
) -> AskResponse:
    trace = Trace(
        search_calls=search_calls, revisions=revisions, verdict=verifier.verdict if verifier else None
    )

    def reply(outcome: Outcome, message: str, citations: list[Citation] | None = None) -> AskResponse:
        return AskResponse(
            outcome=outcome, language=intake.language, message=message,
            citations=citations or [], warnings=[], trace=trace,
        )

    if research is None:
        return reply("refuse", refusal(intake.language))
    if research.outcome != "answer":
        return reply(research.outcome, research.message)
    if trace.verdict != "pass":
        return reply("abstain", abstention(intake.language))

    ids: dict[str, str] = {}
    for chunk_id in markers(research.message):
        ids.setdefault(chunk_id, f"c{len(ids) + 1}")
    quotes = {c.chunk_id: c.quote for c in research.citations}
    citations = [
        Citation(
            id=cid, chunk_id=chunk_id, document=retrieved[chunk_id].document,
            page=retrieved[chunk_id].page, page_in_language=None,
            section=retrieved[chunk_id].section, quote=quote_span(quotes[chunk_id], retrieved[chunk_id].text),
        )
        for chunk_id, cid in ids.items()
    ]
    message = MARKER.sub(lambda m: f"[{ids[m.group(1)]}]", research.message)
    return reply("answer", message, citations)
