from pool_qa.contract import Chunk, Turn


def render_history(history: list[Turn]) -> str:
    if not history:
        return "(none)"
    return "\n".join(f"{turn.role}: {turn.content}" for turn in history)


def render_chunks(chunks: list[Chunk]) -> str:
    return "\n\n".join(
        f"chunk_id: {c.chunk_id}\npage: {c.page}\nsection: {c.section or '-'}\ntext:\n{c.text}" for c in chunks
    )
