import re

from pool_qa.contract import Chunk, ResearchResult, Turn, VerifierResult

QUOTE_MAX = 200
MARKER = re.compile(r"\[([^\[\]\s]+)\]")


def truncate_history(history: list[Turn], n: int) -> list[Turn]:
    start = max(len(history) - n, 0)
    first = next((i for i, turn in enumerate(history) if turn.role == "user"), None)
    if first is None or first >= start:
        return history[start:]
    return [history[first], *history[start:]]


def quote_span(quote: str, text: str) -> str | None:
    # D22: whitespace-only tolerance for pypdf line breaks; hyphen splits still
    # fail; remove when ingestion joins wrapped lines.
    tokens = quote.split()
    if not tokens:
        return None
    pattern = r"\s+".join(re.escape(token) for token in tokens)
    match = re.search(pattern, text)
    return match.group(0) if match else None


def markers(message: str) -> list[str]:
    return MARKER.findall(message)


def citation_check(result: ResearchResult, retrieved: dict[str, Chunk]) -> list[str]:
    issues = []
    if not result.citations:
        issues.append("The answer has no citations.")
    cited = [c.chunk_id for c in result.citations]
    marked = set(markers(result.message))
    for chunk_id in sorted({c for c in cited if cited.count(c) > 1}):
        issues.append(f"Chunk {chunk_id} is cited more than once; cite each chunk once.")
    for citation in {c.chunk_id: c for c in reversed(result.citations)}.values():
        chunk = retrieved.get(citation.chunk_id)
        if chunk is None:
            issues.append(f"Chunk {citation.chunk_id} was not returned by search.")
        else:
            span = quote_span(citation.quote, chunk.text)
            if span is None:
                issues.append(
                    f'The quote "{citation.quote}" for {citation.chunk_id} is not verbatim text from that chunk.'
                )
            elif len(span) > QUOTE_MAX:
                issues.append(f"The quote for {citation.chunk_id} exceeds {QUOTE_MAX} characters.")
        if citation.chunk_id not in marked:
            issues.append(f"Chunk {citation.chunk_id} is cited but has no [{citation.chunk_id}] marker.")
    for token in sorted(marked - set(cited)):
        issues.append(f"Marker [{token}] has no citation.")
    return issues


def enforce_claims(result: VerifierResult) -> VerifierResult:
    unsupported = [c.text for c in result.claims if not c.supported]
    if result.verdict != "pass" or not unsupported:
        return result
    issues = result.issues + [f"Unsupported claim: {text}" for text in unsupported]
    return result.model_copy(update={"verdict": "revise", "issues": issues})
