"""Governed display metadata; independent of machine codes and official legal content."""

from typing import Annotated, Literal

from pydantic import Field

from crossborder_compliance.domain.rules import Contract

PresentationLocale = Literal["zh-CN", "zh-HK", "en-US"]
StableDisplayCode = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{0,119}$")]
DisplayLabel = Annotated[str, Field(min_length=1, max_length=400)]


class LocalizedDisplayMetadata(Contract):
    localized_display_names: dict[PresentationLocale, DisplayLabel] = Field(default_factory=dict)
    fallback_locale: PresentationLocale = "en-US"


class ResolvedDisplayMetadata(Contract):
    stable_code: str
    requested_locale: PresentationLocale
    resolved_locale: PresentationLocale | None
    display_name: str
    fallback_used: bool


def resolve_display(
    stable_code: str,
    canonical_display_name: str | None,
    metadata: LocalizedDisplayMetadata | None,
    locale: PresentationLocale,
) -> ResolvedDisplayMetadata:
    names = metadata.localized_display_names if metadata else {}
    configured = metadata.fallback_locale if metadata else "en-US"
    resolved = locale if locale in names else configured if configured in names else None
    return ResolvedDisplayMetadata(
        stable_code=stable_code,
        requested_locale=locale,
        resolved_locale=resolved,
        display_name=names[resolved] if resolved else canonical_display_name or stable_code,
        fallback_used=resolved != locale,
    )


def validate_localized_payload(payload: dict) -> None:
    """One generic optional payload convention on the existing versioned metadata store."""
    if payload.get("localized_display") is not None:
        LocalizedDisplayMetadata.model_validate(payload["localized_display"])
    # Labels for stable reasons/statuses remain display-only metadata in that same version.
    if "localized_code_labels" in payload:
        from pydantic import TypeAdapter

        TypeAdapter(dict[StableDisplayCode, LocalizedDisplayMetadata]).validate_python(
            payload["localized_code_labels"]
        )
