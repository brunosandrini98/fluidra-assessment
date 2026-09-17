from functools import cache

from lingua import Language, LanguageDetectorBuilder

from pool_qa.checks import MARKER

_LANGUAGES = (
    Language.ENGLISH,
    Language.FRENCH,
    Language.SPANISH,
    Language.ITALIAN,
    Language.GERMAN,
    Language.PORTUGUESE,
    Language.GREEK,
    Language.RUSSIAN,
    Language.ARABIC,
)


@cache
def _detector():
    return LanguageDetectorBuilder.from_languages(*_LANGUAGES).build()


def detect_language(text: str) -> str | None:
    stripped = MARKER.sub("", text)
    detected = _detector().detect_language_of(stripped)
    return detected.iso_code_639_1.name.lower() if detected else None
