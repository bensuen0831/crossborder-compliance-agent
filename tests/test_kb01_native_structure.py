"""Published technical parsing cues and language proposals cannot become legal authority."""

import pytest

from crossborder_compliance.domain.knowledge_native_parsing import KnowledgeNativeParsingPolicy
from crossborder_compliance.infrastructure.knowledge_binary_extraction import knowledge_source_block
from crossborder_compliance.infrastructure.native_language import native_language_hints


@pytest.mark.parametrize(
    "text,kind,number",
    [
        ("Act: Synthetic source", "ACT", None),
        ("Regulation: Synthetic source", "REGULATION", None),
        ("Part II. Scope", "PART", "II"),
        ("Chapter 3. Duties", "CHAPTER", "3"),
        ("Section 2. Controls", "SECTION", "2"),
        ("Article 12. Actual text", "ARTICLE", "12"),
        ("第十二條 原始文字", "ARTICLE", "十二"),
        ("第一章 總則", "CHAPTER", "一"),
        ("المادة ١٢ النص الأصلي", "ARTICLE", "١٢"),
        ("Annex 4. Source", "ANNEX", "4"),
        ("Schedule 2. Source", "SCHEDULE", "2"),
        ("Guidance: source", "GUIDANCE_SECTION", None),
        ("Article without a reliable number", "PARAGRAPH", None),
    ],
)
def test_structure_number_comes_only_from_source_text(text, kind, number):
    row = knowledge_source_block(
        {"original_text": text, "locator": "/line/1", "source_locator": {"line_no": 1}},
        KnowledgeNativeParsingPolicy(),
    )
    assert row["node_type"] == kind and row["official_number"] == number
    assert row["original_text"] == text


@pytest.mark.parametrize(
    "text,expected",
    [
        (
            "This is a clear English synthetic document that preserves every original paragraph.",
            "en",
        ),
        ("這是一份清晰的中文法規測試文件，保留來源與原始文字。", "zh-tw"),
        ("هذا مستند تجريبي باللغة العربية يحتفظ بالنص الأصلي ومصدره القانوني.", "ar"),
        ("Ceci est un document de test en langue française qui conserve le texte original.", "fr"),
    ],
)
def test_actual_language_detection_is_deterministic_and_proposed_only(text, expected):
    first = native_language_hints(text)
    assert first == native_language_hints(text)
    assert first["proposals"][0]["language"] == expected
    assert first["authority"] == "PROPOSED_LANGUAGE_ONLY"


def test_mixed_scripts_and_nfc_preserve_original_text():
    text = "Article 1. Cafe\u0301. 法規. المادة ١."
    row = knowledge_source_block(
        {"original_text": text, "locator": "/line/1", "source_locator": {}},
        KnowledgeNativeParsingPolicy(),
    )
    assert row["original_text"] == text and "Café" in row["normalized_text"]
    assert row["language_hints"]["scripts"] == ["ARABIC", "CJK", "LATIN"]
    assert row["language_hints"]["rtl"] is True
