"""Bounded technical source-structure metadata; never a legal decision policy."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NativeStructureCue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    node_type: Literal[
        "ACT",
        "REGULATION",
        "PART",
        "CHAPTER",
        "SECTION",
        "ARTICLE",
        "ANNEX",
        "SCHEDULE",
        "GUIDANCE_SECTION",
    ]
    prefixes: tuple[str, ...] = Field(min_length=1, max_length=32)
    hierarchy_level: int = Field(ge=0, le=20)
    numbered: bool = False
    number_suffixes: tuple[str, ...] = Field(default=(), max_length=16)

    @field_validator("prefixes")
    @classmethod
    def bounded_literals(cls, values):
        if any(not value.strip() or len(value) > 64 for value in values):
            raise ValueError("INVALID_NATIVE_STRUCTURE_PREFIX")
        return values


def default_native_structure_cues():
    common = tuple(
        NativeStructureCue(
            node_type=kind, prefixes=prefixes, hierarchy_level=rank, numbered=numbered
        )
        for kind, prefixes, rank, numbered in [
            ("ACT", ("Act:", "法律：", "قانون:"), 0, False),
            ("REGULATION", ("Regulation:", "法規：", "لائحة:"), 0, False),
            ("PART", ("Part ", "部分 ", "الجزء "), 1, True),
            ("CHAPTER", ("Chapter ", "章 ", "الفصل "), 2, True),
            ("SECTION", ("Section ", "節 ", "节 ", "القسم "), 3, True),
            ("ARTICLE", ("Article ", "المادة "), 4, True),
            ("ANNEX", ("Annex ", "附件 ", "الملحق "), 1, True),
            ("SCHEDULE", ("Schedule ", "附表 "), 1, True),
            ("GUIDANCE_SECTION", ("Guidance:", "指引：", "إرشادات:"), 3, False),
        ]
    )
    return common + tuple(
        NativeStructureCue(
            node_type=kind,
            prefixes=("第",),
            hierarchy_level=rank,
            numbered=True,
            number_suffixes=suffixes,
        )
        for kind, rank, suffixes in [
            ("PART", 1, ("部分", "部")),
            ("CHAPTER", 2, ("章",)),
            ("SECTION", 3, ("節", "节")),
            ("ARTICLE", 4, ("條", "条")),
        ]
    )
