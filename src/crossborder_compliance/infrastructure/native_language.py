"""Deterministic language proposals; original/declared language is not overwritten."""

import unicodedata
from functools import lru_cache


@lru_cache(maxsize=1)
def _language_profiles():
    from langdetect.detector_factory import PROFILES_DIRECTORY, DetectorFactory

    factory = DetectorFactory()
    factory.load_profile(PROFILES_DIRECTORY)
    factory.seed = 0
    return factory


def native_language_hints(text):
    from langdetect.lang_detect_exception import LangDetectException

    detector = _language_profiles().create()
    detector.append(text[:4096])
    try:
        languages = [
            {"language": row.lang, "confidence": row.prob} for row in detector.get_probabilities()
        ]
    except LangDetectException:
        languages = []
    scripts = set()
    for character in text:
        name = unicodedata.name(character, "")
        for script in (
            "ARABIC",
            "HEBREW",
            "CJK",
            "HIRAGANA",
            "KATAKANA",
            "HANGUL",
            "CYRILLIC",
            "GREEK",
            "LATIN",
        ):
            if script in name:
                scripts.add(script)
                break
    return {
        "proposals": languages,
        "scripts": sorted(scripts),
        "rtl": any(unicodedata.bidirectional(character) in {"R", "AL"} for character in text),
        "detector": "langdetect-1.0.9-seed0",
        "authority": "PROPOSED_LANGUAGE_ONLY",
    }
