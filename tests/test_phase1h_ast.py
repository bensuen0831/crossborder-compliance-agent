from datetime import UTC, date, datetime, tzinfo
from decimal import Decimal

import pytest

from crossborder_compliance.domain.rule_ast import (
    FieldType,
    RuleValidationError,
    TypedNode,
    ValidatedAST,
    evaluate,
    parse_ast,
)


@pytest.mark.parametrize(
    "op,left,right,expected",
    [
        ("eq", 3, 3, True),
        ("eq", 3, 4, False),
        ("ne", 3, 4, True),
        ("gt", 3, 2, True),
        ("gte", 3, 3, True),
        ("lt", 3, 4, True),
        ("lte", 3, 3, True),
        ("in", 3, [2, 3], True),
    ],
)
def test_numeric_operators(op, left, right, expected):
    ast = parse_ast(
        {"op": op, "field": "value", "value": right}, {"value": FieldType(kind="integer")}
    )
    assert evaluate(ast, {"value": left}) is expected


@pytest.mark.parametrize(
    "kind,left,right",
    [
        ("string", "document", "doc"),
        ("list", ["a", "b"], "a"),
        ("set", {"a", "b"}, "b"),
    ],
)
def test_contains(kind, left, right):
    spec = FieldType(kind=kind, item=FieldType(kind="string") if kind != "string" else None)
    assert evaluate(
        parse_ast({"op": "contains", "field": "v", "value": right}, {"v": spec}), {"v": left}
    )


@pytest.mark.parametrize(
    "op,values,expected",
    [
        ("any", [1, 3], True),
        ("all", [1, 3], False),
        ("all", [3, 4], True),
        ("any", [], False),
        ("all", [], False),
    ],
)
def test_quantifiers(op, values, expected):
    ast = parse_ast(
        {"op": op, "field": "values", "where": {"op": "gt", "field": "$item", "value": 2}},
        {"values": FieldType(kind="list", item=FieldType(kind="integer"))},
    )
    assert evaluate(ast, {"values": values}) is expected


def test_nested_logical():
    eq = {"op": "eq", "field": "v", "value": 3}
    dsl = {"op": "and", "args": [{"op": "or", "args": [eq, {"op": "not", "args": [eq]}]}, eq]}
    assert evaluate(parse_ast(dsl, {"v": FieldType(kind="integer")}), {"v": 3})


@pytest.mark.parametrize(
    "kind,value,op,literal",
    [
        ("date", date(2026, 1, 1), "date_before", "2026-02-01"),
        (
            "datetime",
            datetime(2026, 1, 1, tzinfo=UTC),
            "date_after",
            "2025-01-01T00:00:00+00:00",
        ),
        ("decimal", Decimal("1.01"), "gt", "1.001"),
        ("boolean", True, "eq", True),
        ("code", "PERSONAL", "eq", "PERSONAL"),
    ],
)
def test_typed_values(kind, value, op, literal):
    spec = FieldType(kind=kind, codes=("PERSONAL", "OTHER") if kind == "code" else ())
    assert evaluate(
        parse_ast({"op": op, "field": "v", "value": literal}, {"v": spec}), {"v": value}
    )


def test_null_and_missing_are_not_negated_into_decisions():
    schema = {"v": FieldType(kind="integer", nullable=True)}
    predicate = {"op": "gt", "field": "v", "value": 1}
    negated = parse_ast({"op": "not", "args": [predicate]}, schema)
    assert not evaluate(negated, {"v": None})
    with pytest.raises(RuleValidationError, match="missing"):
        evaluate(negated, {})
    assert evaluate(parse_ast({"op": "eq", "field": "v", "value": None}, schema), {"v": None})
    assert not evaluate(parse_ast({"op": "exists", "field": "v"}, schema), {})


@pytest.mark.parametrize(
    "dsl",
    [
        {"op": "__import__", "field": "v", "value": "os"},
        {"op": "eq", "field": "v.__class__", "value": 1},
        {"op": "eq", "field": "unknown", "value": 1},
        {"op": "eq", "field": "v", "value": "1"},
        {"op": "eq", "field": "v", "value": True},
        {"op": "eq", "field": "v", "value": 1, "call": "open"},
        "__import__('os').system('touch /tmp/phase1h-malicious')",
        '{"op":"exists","op":"eq","field":"v"}',
    ],
)
def test_reject_untrusted_dsl(dsl):
    with pytest.raises(ValueError):
        parse_ast(dsl, {"v": FieldType(kind="integer")})


def test_malicious_literal_is_data_only(tmp_path):
    target = tmp_path / "should-not-exist"
    payload = f"__import__('pathlib').Path('{target}').touch()"
    ast = parse_ast({"op": "eq", "field": "v", "value": payload}, {"v": FieldType(kind="string")})
    assert evaluate(ast, {"v": payload})
    assert not target.exists()


def test_runtime_type_unknowns_and_limits():
    ast = parse_ast({"op": "eq", "field": "v", "value": 1}, {"v": FieldType(kind="integer")})
    for facts in ({"v": True}, {"v": "1"}, {"v": 1, "extra": 2}):
        with pytest.raises(ValueError):
            evaluate(ast, facts)
    raw = {"op": "exists", "field": "v"}
    for _ in range(22):
        raw = {"op": "not", "args": [raw]}
    with pytest.raises(ValueError, match="limit"):
        parse_ast(raw, {"v": FieldType(kind="integer")})


def test_forged_python_ast_cannot_execute_comparison_objects():
    effects = []

    class MaliciousComparison:
        def __eq__(self, other):
            effects.append("executed")
            return True

    spec = FieldType(kind="integer")
    forged = ValidatedAST(TypedNode("eq", "v", spec, MaliciousComparison()), (("v", spec),), ("v",))
    with pytest.raises(RuleValidationError, match="closed typed"):
        evaluate(forged, {"v": 1})
    assert effects == []


def test_custom_datetime_hooks_do_not_execute():
    effects = []

    class UnsafeTimezone(tzinfo):
        def utcoffset(self, value):
            effects.append("executed")
            raise RuntimeError("unsafe timezone")

    spec = FieldType(kind="datetime")
    ast = parse_ast(
        {"op": "date_before", "field": "when", "value": "2026-01-01T00:00:00+00:00"}, {"when": spec}
    )
    with pytest.raises(RuleValidationError):
        evaluate(ast, {"when": datetime(2025, 1, 1, tzinfo=UnsafeTimezone())})
    assert effects == []
