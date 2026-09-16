from pool_qa.contract import Chunk
from pool_qa.ingest.pypdf_chunks import (
    cap,
    figure_refs,
    ingest,
    render,
    split_sections,
    strip_furniture,
)
from pool_qa.retrieval import load_chunks
from pool_qa.settings import Settings


def committed() -> list[Chunk]:
    return load_chunks(Settings().chunks_path)


def test_strip_furniture_removes_repeated_lines_and_page_numbers():
    pages = {
        1: ["Header", "1", "alpha"],
        2: ["Header", "2", "beta", "1"],
        3: ["Header", "gamma"],
        4: ["delta"],
        5: ["epsilon"],
    }
    assert strip_furniture(pages) == {
        1: ["alpha"],
        2: ["beta", "1"],
        3: ["gamma"],
        4: ["delta"],
        5: ["epsilon"],
    }


def test_split_sections_at_numbered_headings_and_carries_section():
    pages = {
        1: ["intro", "1. FIRST PART", "a", "1. Step one", "2. SECOND PART", "b"],
        2: ["c"],
    }
    assert split_sections(pages) == [
        (1, None, "intro"),
        (1, "1. FIRST PART", "1. FIRST PART\na\n1. Step one"),
        (1, "2. SECOND PART", "2. SECOND PART\nb"),
        (2, "2. SECOND PART", "c"),
    ]


def test_split_sections_falls_back_to_page_chunks_without_headings():
    pages = {1: ["Chapter One", "text"], 2: ["more text"]}
    assert split_sections(pages) == [(1, None, "Chapter One\ntext"), (2, None, "more text")]


def test_cap_leaves_short_text():
    assert cap("abc\ndef", max_chars=10) == ["abc\ndef"]


def test_cap_splits_at_last_line_break():
    pieces = cap("aaaa\nbbbb\ncccc", max_chars=10)
    assert pieces == ["aaaa\nbbbb", "cccc"]
    assert all(len(p) <= 10 for p in pieces)


def test_cap_hard_splits_without_line_break():
    assert cap("a" * 25, max_chars=10) == ["a" * 10, "a" * 10, "a" * 5]


def test_figure_refs_deduplicated_in_order():
    assert figure_refs("x (Fig. 5) y (Fig. 6) z (Fig. 5)") == ["Fig. 5", "Fig. 6"]
    assert figure_refs("no figures") == []


def test_committed_chunks_valid():
    chunks = committed()
    assert chunks
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert {c.page for c in chunks} == set(range(5, 14)) | {94, 97}
    for c in chunks:
        assert c.language == "en"
        assert c.source_type == "manual"
        assert c.document == "user_manual.pdf"
        assert c.effective_date is None
        assert c.warning_ids == []
        assert len(c.text) <= 2000
        assert "Installation and general maintenance manual - POOL PUMPS" not in c.text


def test_ingestion_reproduces_committed_file():
    expected = Settings().chunks_path.read_text(encoding="utf-8")
    assert render(ingest()) == expected


def test_transcribed_page_replaces_pypdf_chunks():
    page13 = [c for c in ingest() if c.page == 13]
    assert [c.chunk_id for c in page13] == [f"user_manual-p13-{i}" for i in range(1, 7)]
    assert all(c.text.startswith("7. TROUBLESHOOTING\nSymptom ") for c in page13)


def test_troubleshooting_symptom_1_causes():
    chunk = next(c for c in committed() if c.chunk_id == "user_manual-p13-1")
    causes = [
        line.removeprefix("Cause: ").split(". Solution:")[0]
        for line in chunk.text.splitlines()
        if line.startswith("Cause: ")
    ]
    assert causes == [
        "Air entering the suction pipe",
        "Filter cap badly sealed",
        "Motor turning in wrong direction",
        "Wrong voltage",
    ]


def test_figure_refs_on_committed_chunks():
    for c in committed():
        assert c.figure_refs == figure_refs(c.text)
        if "(Fig. 5)" in c.text:
            assert "Fig. 5" in c.figure_refs
        if "(Fig." not in c.text:
            assert c.figure_refs == []
        assert len(set(c.figure_refs)) == len(c.figure_refs)


def test_sections_on_committed_chunks():
    chunks = committed()
    start_up = next(c for c in chunks if c.page == 11 and "PRIOR TO START-UP" in c.text)
    assert start_up.section is not None and "START-UP INSTRUCTIONS" in start_up.section
    continuation = next(c for c in chunks if c.page == 12 and "Mechanical seal" in c.text)
    assert continuation.section is not None and "MAINTENANCE" in continuation.section
