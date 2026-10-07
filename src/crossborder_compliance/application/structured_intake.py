"""Generic governed field binding, independent of any legal decision."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from crossborder_compliance.application.intake_services import IntakeFacts
from crossborder_compliance.domain.rule_ast import FieldType, typed_value


class StructuredIntakeBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    field_path: str
    value_type: Literal["string", "integer", "boolean", "string_list"]

    @field_validator("field_path")
    @classmethod
    def canonical_field(cls, value):
        if value not in IntakeFacts.model_fields:
            raise ValueError("binding must name one canonical writable intake field")
        return value

    def normalize(self, value):
        if self.value_type == "integer" and type(value) is str:
            if not re.fullmatch(r"-?[0-9]{1,19}", value.strip()):
                raise ValueError("structured integer requires explicit bounded numeric input")
            value = int(value.strip())
        spec = (
            FieldType(kind="list", item=FieldType(kind="string"))
            if (self.value_type == "string_list")
            else FieldType(kind=self.value_type)
        )
        result = typed_value(value, spec)
        return list(result) if self.value_type == "string_list" else result
