"""Typed technical parsing metadata on the existing governed management policy."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crossborder_compliance.domain.native_structure import (
    NativeStructureCue,
    default_native_structure_cues,
)


class KnowledgeNativeParsingPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    profile: Literal["KB01_NATIVE_V1"] = "KB01_NATIVE_V1"
    max_native_blocks: int = Field(default=20000, ge=1, le=100000)
    max_native_output_bytes: int = Field(default=32 * 1024**2, ge=1, le=1024**3)
    max_block_chars: int = Field(default=1_000_000, ge=1, le=1_000_000)
    max_xml_bytes: int = Field(default=128 * 1024**2, ge=1, le=1024**3)
    max_archive_entries: int = Field(default=20000, ge=1, le=100000)
    conversion_timeout_seconds: int = Field(default=600, ge=1, le=14400)
    ocr_enabled: bool = True
    max_ocr_pages: int = Field(default=100, ge=1, le=10000)
    ocr_languages: tuple[Literal["eng", "chi_sim", "chi_tra", "ara", "heb"], ...] = Field(
        default=("eng",), min_length=1, max_length=5
    )
    ocr_minimum_confidence: float = Field(default=0.75, ge=0, le=1)
    structure_cues: tuple[NativeStructureCue, ...] = Field(
        default_factory=default_native_structure_cues, min_length=1, max_length=64
    )
