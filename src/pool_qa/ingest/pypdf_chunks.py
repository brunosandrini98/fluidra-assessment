import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

from pool_qa.contract import Chunk
from pool_qa.settings import ROOT, Settings

PDF_PATH = ROOT / "data" / "user_manual.pdf"
DOCUMENT = "user_manual.pdf"
ENGLISH_PAGES = range(5, 14)
MAX_CHARS = 2000
HEADING = re.compile(r"^\d+\s*\.\s+[A-Z][A-Z\s,\-]*$")
FIGURE = re.compile(r"\(Fig\. (\d+)\)")


def strip_furniture(pages: dict[int, list[str]]) -> dict[int, list[str]]:
    counts = Counter(line for lines in pages.values() for line in set(lines))
    repeated = {line for line, n in counts.items() if n * 2 >= len(pages)}
    return {
        page: [l for l in lines if l not in repeated and l != str(page)]
        for page, lines in pages.items()
    }


def split_sections(
    pages: dict[int, list[str]],
) -> list[tuple[int, str | None, str]]:
    parts = []
    section = None
    for page, lines in sorted(pages.items()):
        current: list[str] = []
        for line in lines:
            if HEADING.match(line):
                if current:
                    parts.append((page, section, "\n".join(current)))
                section, current = line, []
            current.append(line)
        if current:
            parts.append((page, section, "\n".join(current)))
    return parts


def cap(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    pieces = []
    while len(text) > max_chars:
        cut = text.rfind("\n", 0, max_chars)
        if cut <= 0:
            cut = max_chars
        pieces.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return pieces + [text]


def figure_refs(text: str) -> list[str]:
    return list(dict.fromkeys(f"Fig. {n}" for n in FIGURE.findall(text)))


def build_chunks(pages: dict[int, list[str]]) -> list[Chunk]:
    chunks = []
    counter: Counter[int] = Counter()
    for page, section, text in split_sections(strip_furniture(pages)):
        for piece in cap(text):
            counter[page] += 1
            chunks.append(
                Chunk(
                    chunk_id=f"user_manual-p{page}-{counter[page]}",
                    document=DOCUMENT,
                    source_type="manual",
                    effective_date=None,
                    language="en",
                    page=page,
                    section=section,
                    text=piece,
                    figure_refs=figure_refs(piece),
                    warning_ids=[],
                )
            )
    return chunks


def read_pages(pdf_path: Path = PDF_PATH) -> dict[int, list[str]]:
    reader = PdfReader(pdf_path)
    return {
        page: [line.strip() for line in reader.pages[page - 1].extract_text().splitlines()]
        for page in ENGLISH_PAGES
    }


def render(chunks: list[Chunk]) -> str:
    return "".join(chunk.model_dump_json() + "\n" for chunk in chunks)


def main() -> None:
    path = Settings().chunks_path
    path.write_text(render(build_chunks(read_pages())), encoding="utf-8")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
