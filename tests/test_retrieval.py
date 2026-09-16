import inspect
import subprocess
import sys

import pytest

from pool_qa.contract import Chunk, Filters, GoldenRecord
from pool_qa.retrieval import search
from pool_qa.settings import ROOT

EN = Filters(language="en")


def golden(record_id: str) -> GoldenRecord:
    for line in (ROOT / "eval" / "golden.jsonl").read_text(encoding="utf-8").splitlines():
        record = GoldenRecord.model_validate_json(line)
        if record.id == record_id:
            return record
    raise KeyError(record_id)


def pages(chunks: list[Chunk]) -> list[int]:
    return [c.page for c in chunks]


def test_signature_matches_contract():
    sig = inspect.signature(search)
    assert list(sig.parameters) == ["query", "filters", "k"]
    assert sig.parameters["query"].annotation is str
    assert sig.parameters["filters"].annotation is Filters
    assert sig.parameters["k"].annotation is int
    assert sig.return_annotation == list[Chunk]


@pytest.mark.parametrize(
    ("query", "page"),
    [
        (golden("t0-01").question, 11),
        (golden("t0-03").question, 13),
        ("how often replace mechanical seal", 12),
    ],
)
def test_expected_page_in_top_3(query, page):
    assert page in pages(search(query, EN, 3))


def test_at_most_k_and_consistent_ranking():
    query = "pump pre-filter basket seal"
    top3 = search(query, EN, 3)
    top5 = search(query, EN, 5)
    assert len(top3) <= 3
    assert top5[:3] == top3
    assert search(query, EN, 3) == top3


def test_results_do_not_share_state_with_index():
    first = search("pump", EN, 1)[0]
    first.text = "mutated"
    first.figure_refs.append("Fig. 99")
    again = search("pump", EN, 1)[0]
    assert again.text != "mutated"
    assert "Fig. 99" not in again.figure_refs


def test_language_filter():
    assert search("pump", Filters(language="fr"), 5) == []


def test_section_filter():
    section = "5. MAINTENANCE"
    results = search("pump", Filters(language="en", section=section), 10)
    assert results
    assert all(c.section == section for c in results)


def test_page_range_filter_inclusive():
    results = search("pump", Filters(language="en", page_range=(11, 12)), 10)
    assert set(pages(results)) == {11, 12}


def test_no_matching_terms_returns_empty():
    assert search("zzzz", EN, 3) == []


def test_empty_query_returns_empty():
    assert search("   ", EN, 3) == []


def test_k_below_one_rejected():
    with pytest.raises(ValueError):
        search("pump", EN, 0)


def test_search_does_not_read_pdf():
    code = (
        "import sys\n"
        "from pool_qa.contract import Filters\n"
        "from pool_qa.retrieval import search\n"
        "assert search('pump', Filters(language='en'), 3)\n"
        "assert 'pypdf' not in sys.modules\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
