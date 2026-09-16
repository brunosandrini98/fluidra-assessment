from functools import cache
from pathlib import Path

import bm25s
import Stemmer

from pool_qa.contract import Chunk, Filters
from pool_qa.settings import Settings

_STEMMER = Stemmer.Stemmer("english")


def _tokenize(texts: list[str]) -> bm25s.tokenization.Tokenized:
    return bm25s.tokenize(texts, stopwords="en", stemmer=_STEMMER, show_progress=False)


def load_chunks(path: Path) -> list[Chunk]:
    with path.open(encoding="utf-8") as f:
        return [Chunk.model_validate_json(line) for line in f if line.strip()]


@cache
def _index(path: Path) -> tuple[list[Chunk], bm25s.BM25]:
    chunks = load_chunks(path)
    retriever = bm25s.BM25()
    retriever.index(_tokenize([c.text for c in chunks]), show_progress=False)
    return chunks, retriever


def _matches(chunk: Chunk, filters: Filters) -> bool:
    if chunk.language != filters.language:
        return False
    if filters.section is not None and chunk.section != filters.section:
        return False
    if filters.page_range is not None:
        first, last = filters.page_range
        if not first <= chunk.page <= last:
            return False
    return True


def search(query: str, filters: Filters, k: int) -> list[Chunk]:
    if k < 1:
        raise ValueError("k must be >= 1")
    if not query.strip():
        return []
    chunks, retriever = _index(Settings().chunks_path)
    docs, scores = retriever.retrieve(_tokenize([query]), k=len(chunks), show_progress=False)
    ranked = sorted(zip(docs[0].tolist(), scores[0].tolist()), key=lambda d: (-d[1], d[0]))
    hits = [chunks[i].model_copy(deep=True) for i, score in ranked if score > 0 and _matches(chunks[i], filters)]
    return hits[:k]
