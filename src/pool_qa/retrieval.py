from pathlib import Path

from pool_qa.contract import Chunk


def load_chunks(path: Path) -> list[Chunk]:
    chunks = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            chunks.append(Chunk.model_validate_json(line))
    return chunks
