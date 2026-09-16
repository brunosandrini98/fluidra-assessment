import pytest

from pool_qa.phrases import LANGUAGES, abstention, refusal


def test_manual_languages_covered():
    assert set(LANGUAGES) == {"en", "fr", "es", "it", "de", "pt", "el", "ru", "ar"}


@pytest.mark.parametrize("language", ["en", "fr", "es", "it", "de", "pt", "el", "ru", "ar"])
def test_phrases_non_empty(language):
    assert refusal(language).strip()
    assert abstention(language).strip()


def test_non_english_differs_from_english():
    assert refusal("es") != refusal("en")
    assert abstention("es") != abstention("en")


def test_unknown_language_falls_back_to_english():
    assert refusal("ja") == refusal("en")
    assert abstention("ja") == abstention("en")
