import re

from pool_qa.contract import Chunk, ResearchResult, Turn

QUOTE_MAX = 200
MARKER = re.compile(r"\[([^\[\]\s]+)\]")


def truncate_history(history: list[Turn], n: int) -> list[Turn]:
    start = max(len(history) - n, 0)
    first = next((i for i, turn in enumerate(history) if turn.role == "user"), None)
    if first is None or first >= start:
        return history[start:]
    return [history[first], *history[start:]]


def normalize_ws(text: str) -> str:
    # D22: tolerate pypdf line breaks; remove when ingestion joins wrapped lines.
    return " ".join(text.split())


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
        quote = normalize_ws(citation.quote)
        if chunk is None:
            issues.append(f"Chunk {citation.chunk_id} was not returned by search.")
        elif not quote or quote not in normalize_ws(chunk.text):
            issues.append(f"The quote for {citation.chunk_id} is not verbatim text from that chunk.")
        elif len(quote) > QUOTE_MAX:
            issues.append(f"The quote for {citation.chunk_id} exceeds {QUOTE_MAX} characters.")
        if citation.chunk_id not in marked:
            issues.append(f"Chunk {citation.chunk_id} is cited but has no [{citation.chunk_id}] marker.")
    for token in sorted(marked - set(cited)):
        issues.append(f"Marker [{token}] has no citation.")
    return issues
