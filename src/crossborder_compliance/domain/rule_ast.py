"""Closed JSON DSL. No expression interpreter, attribute lookup or external effects."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


class RuleValidationError(ValueError):
    pass


class FieldType(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["string", "boolean", "integer", "decimal", "date", "datetime", "code", "list", "set"]
    nullable: bool = False
    item: FieldType | None = None
    codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def complete(self):
        if (self.kind in {"list", "set"}) != (self.item is not None):
            raise ValueError("collection requires item type; scalar cannot have item")
        if self.item and self.item.kind in {"list", "set"}:
            raise ValueError("nested collections are not supported in V1")
        if self.kind == "code" and not self.codes:
            raise ValueError("code requires an explicit allowlist")
        return self


def typed_value(value: object, spec: FieldType, *, literal: bool = False) -> object:
    if value is None:
        if spec.nullable:
            return None
        raise RuleValidationError("null is not allowed")
    kind = spec.kind
    if kind in {"string", "code"} and type(value) is str:
        if len(value) > 4096 or (kind == "code" and value not in spec.codes):
            raise RuleValidationError("string/code outside declared bounds")
        return value
    if kind == "boolean" and type(value) is bool:
        return value
    if kind == "integer" and type(value) is int:
        if abs(value) > 2**63 - 1:
            raise RuleValidationError("integer outside signed 64-bit range")
        return value
    if kind == "decimal" and (type(value) in {int, Decimal} or (literal and type(value) is str)):
        try:
            number = Decimal(value)
        except Exception as exc:
            raise RuleValidationError("invalid decimal") from exc
        if not number.is_finite() or abs(number) > Decimal("1e30"):
            raise RuleValidationError("decimal outside bounds")
        return number
    if kind in {"date", "datetime"}:
        if literal and type(value) is str:
            try:
                value = date.fromisoformat(value) if kind == "date" else datetime.fromisoformat(value)
            except ValueError as exc:
                raise RuleValidationError("invalid ISO date") from exc
        if kind == "date" and type(value) is date:
            return value
        if kind == "datetime" and type(value) is datetime and value.tzinfo is not None:
            return value
    if kind in {"list", "set"} and type(value) in {list, tuple, set, frozenset}:
        if len(value) > 1000:
            raise RuleValidationError("collection exceeds limit")
        items = tuple(typed_value(v, spec.item, literal=literal) for v in value)
        return frozenset(items) if kind == "set" else items
    raise RuleValidationError(f"value does not match {kind}")


@dataclass(frozen=True, slots=True)
class TypedNode:
    op: str
    field: str | None = None
    field_type: FieldType | None = None
    value: object = None
    children: tuple[TypedNode, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidatedAST:
    root: TypedNode
    schema: tuple[tuple[str, FieldType], ...]
    referenced_fields: tuple[str, ...]


def parse_ast(dsl: str | dict, schema: dict[str, FieldType]) -> ValidatedAST:
    """Parse only closed JSON syntax, then validate every branch before evaluation."""
    if len(schema) > 100 or not schema:
        raise RuleValidationError("schema requires 1..100 fields")
    for name in schema:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", name):
            raise RuleValidationError("field names must be flat public identifiers")
    if isinstance(dsl, str):
        if len(dsl) > 65536:
            raise RuleValidationError("DSL exceeds size limit")
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise RuleValidationError("duplicate JSON key")
                result[key] = value
            return result
        try:
            dsl = json.loads(dsl, object_pairs_hook=unique)
        except (ValueError, RecursionError) as exc:
            raise RuleValidationError("invalid JSON DSL") from exc
    fields: set[str] = set()
    count = 0

    def node(raw, depth=0, element: FieldType | None = None):
        nonlocal count
        count += 1
        if depth > 20 or count > 200 or type(raw) is not dict:
            raise RuleValidationError("invalid node or AST resource limit")
        op = raw.get("op")
        if op in {"and", "or", "not"}:
            if set(raw) != {"op", "args"} or type(raw["args"]) is not list:
                raise RuleValidationError("logical node requires args")
            if not 1 <= len(raw["args"]) <= 50 or (op == "not" and len(raw["args"]) != 1):
                raise RuleValidationError("invalid logical arity")
            return TypedNode(op, children=tuple(node(c, depth + 1, element) for c in raw["args"]))
        if op not in {"eq", "ne", "in", "contains", "gt", "gte", "lt", "lte", "exists", "date_before", "date_after", "any", "all"}:
            raise RuleValidationError("unknown operator")
        expected = {"op", "field"}
        expected |= {"where"} if op in {"any", "all"} else set() if op == "exists" else {"value"}
        if set(raw) != expected:
            raise RuleValidationError("unexpected/missing node fields")
        field = raw["field"]
        if type(field) is not str:
            raise RuleValidationError("field must be identifier")
        spec = element if field == "$item" else schema.get(field)
        if spec is None or (element is not None and field != "$item"):
            raise RuleValidationError("unknown field or invalid quantifier scope")
        if field != "$item":
            fields.add(field)
        if op in {"any", "all"}:
            if spec.kind not in {"list", "set"}:
                raise RuleValidationError("quantifier requires collection")
            return TypedNode(op, field, spec, children=(node(raw["where"], depth + 1, spec.item),))
        if op == "exists":
            return TypedNode(op, field, spec)
        literal_spec = spec
        if op == "in":
            if spec.kind in {"list", "set"}:
                raise RuleValidationError("in requires scalar left operand")
            literal_spec = FieldType(kind="list", item=spec)
        elif op == "contains":
            if spec.kind not in {"list", "set", "string"}:
                raise RuleValidationError("contains requires collection/string")
            literal_spec = spec.item or spec
        elif op in {"gt", "gte", "lt", "lte"} and spec.kind not in {"integer", "decimal"}:
            raise RuleValidationError("ordering requires numeric type")
        elif op in {"date_before", "date_after"} and spec.kind not in {"date", "datetime"}:
            raise RuleValidationError("date operator requires date/datetime")
        value = typed_value(raw["value"], literal_spec, literal=True)
        if value is None and op not in {"eq", "ne"}:
            raise RuleValidationError("null only supports equality")
        return TypedNode(op, field, spec, value)

    root = node(dsl)
    return ValidatedAST(root, tuple(sorted(schema.items())), tuple(sorted(fields)))


def evaluate(ast: ValidatedAST, facts: dict[str, object]) -> bool:
    if not isinstance(ast, ValidatedAST):
        raise RuleValidationError("runtime accepts validated AST only")
    schema = dict(ast.schema)
    if set(facts) - set(schema):
        raise RuleValidationError("unknown fact field")
    prepared = {key: typed_value(value, schema[key]) for key, value in facts.items()}
    # Validate missing inputs before short circuiting, including negated predicates.
    def check(n):
        if n.field and n.field != "$item" and n.op != "exists" and n.field not in prepared:
            raise RuleValidationError("missing required fact")
        for child in n.children:
            check(child)
    check(ast.root)

    def run(n, item=None):
        if n.op == "and":
            values = [run(c, item) for c in n.children]
            return False if False in values else None if None in values else True
        if n.op == "or":
            values = [run(c, item) for c in n.children]
            return True if True in values else None if None in values else False
        if n.op == "not":
            value = run(n.children[0], item)
            return None if value is None else not value
        left = item if n.field == "$item" else prepared.get(n.field)
        if n.op == "exists":
            return left is not None
        if n.op in {"any", "all"}:
            if left is None or not left:
                return False  # empty ALL never fabricates a positive decision
            values = [run(n.children[0], v) for v in left]
            if n.op == "any":
                return True if True in values else None if None in values else False
            return False if False in values else None if None in values else True
        if left is None and n.value is not None:
            return None
        if n.op == "eq":
            return left == n.value
        if n.op == "ne":
            return left != n.value
        if left is None:
            return None
        if n.op == "in":
            return left in n.value
        if n.op == "contains":
            return n.value in left
        if n.op in {"gt", "date_after"}:
            return left > n.value
        if n.op == "gte":
            return left >= n.value
        if n.op in {"lt", "date_before"}:
            return left < n.value
        if n.op == "lte":
            return left <= n.value
        raise RuleValidationError("invalid validated operator")
    return run(ast.root) is True
