"""Locale presentation over canonical registry rows; never translates legal authority."""

from copy import deepcopy

from crossborder_compliance.domain.localized_metadata import (
    LocalizedDisplayMetadata,
    PresentationLocale,
    resolve_display,
)


def present_metadata(row: dict, locale: PresentationLocale) -> dict:
    output = deepcopy(row)
    payload = row.get("payload") or {}
    display = payload.get("localized_display")
    metadata = LocalizedDisplayMetadata.model_validate(display) if display is not None else None
    output["presentation"] = resolve_display(
        str(row.get("code") or row.get("capability_code") or row["definition_id"]),
        row.get("display_name"),
        metadata,
        locale,
    ).model_dump(mode="json")
    output["presentation"]["code_labels"] = {
        code: resolve_display(
            code, None, LocalizedDisplayMetadata.model_validate(value), locale
        ).model_dump(mode="json")
        for code, value in payload.get("localized_code_labels", {}).items()
    }
    return output


def present_applicability(result: dict, config_payload: dict, locale: PresentationLocale) -> dict:
    labels = config_payload.get("localized_code_labels", {})

    def display(code):
        value = labels.get(code)
        return resolve_display(
            code, None, LocalizedDisplayMetadata.model_validate(value) if value else None, locale
        ).model_dump(mode="json")

    return {
        "result": deepcopy(result),
        "presentation": {
            "status": display(result["applicability_status"]),
            "reasons": [display(code) for code in result["reason_codes"]],
        },
    }
