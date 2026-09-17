from pool_qa.eval.language import detect_language
from pool_qa.phrases import LANGUAGES, abstention, refusal


def test_detects_static_phrases_in_golden_languages():
    for language in ("en", "es", "fr", "it"):
        assert detect_language(refusal(language)) == language
        assert detect_language(abstention(language)) == language


def test_strips_citation_markers_before_detecting():
    assert detect_language("Check before start-up [c1].") == "en"
    assert detect_language("Compruebe antes de la puesta en marcha [c1].") == "es"


def test_undetectable_text_returns_none():
    assert detect_language("") is None
    assert detect_language("1234 !!! ???") is None


def test_all_golden_languages_are_covered_by_the_detector():
    # LANGUAGES is pool_qa.phrases' full static-phrase set; the detector only
    # restricts to the 9 configured languages, all of which are in LANGUAGES.
    for language in LANGUAGES:
        assert detect_language(refusal(language)) == language
