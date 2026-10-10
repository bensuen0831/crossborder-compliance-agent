"""Runtime contracts generated from the public OpenAPI authority, not business logic."""

import json
from importlib.resources import files
from typing import Any, TypedDict

from jsonschema import Draft202012Validator

SCHEMAS = json.loads(files("crossborder_agent").joinpath("external-v1.json").read_text())[
    "components"
]["schemas"]


class ProjectCreate(TypedDict):
    name: str
    facts: dict[str, Any]


class IntakeUpdate(TypedDict):
    expected_version: int
    facts: dict[str, Any]


def validate(name: str, payload):
    Draft202012Validator(
        {"$ref": f"#/components/schemas/{name}", "components": {"schemas": SCHEMAS}}
    ).validate(payload)
    return payload
