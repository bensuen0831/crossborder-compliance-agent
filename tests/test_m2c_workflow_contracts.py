"""Closed-version routing and reference bounds in the same canonical factory."""

import pytest
from test_phase1l_a_skeleton import build

from crossborder_compliance.application.workflow_skeleton import StageExecutionResult
from crossborder_compliance.workflows.canonical import (
    LEGACY_GRAPH_VERSION,
    LEGACY_STATE_VERSION,
    PIPELINE,
)


def test_legacy_version_retains_original_sixteen_step_order():
    factory, graph, run, _, _, _, authority = build(
        StageExecutionResult(status="SUCCESS"), all_steps=True
    )
    authority.identity = authority.identity.model_copy(
        update=dict(
            graph_definition_version=LEGACY_GRAPH_VERSION, state_schema_version=LEGACY_STATE_VERSION
        )
    )
    state = factory.initial_state(run)
    output = graph.invoke(state, factory.config(run))
    assert output["completed_steps"] == [
        step.value for step in PIPELINE if step.value != "cross_border"
    ]
    assert len(output["completed_steps"]) == 16 and output["route"] == "COMPLETED"
    assert graph.get_state(factory.config(run)).values == output


@pytest.mark.parametrize(
    "graph_version,state_version",
    [
        ("unknown", "unknown"),
        (LEGACY_GRAPH_VERSION, "phase1l-a-references-v2"),
        ("phase1l-a-canonical-v2", LEGACY_STATE_VERSION),
    ],
)
def test_unknown_or_mixed_version_pairs_fail_closed(graph_version, state_version):
    factory, _, run, _, _, _, authority = build(
        StageExecutionResult(status="SUCCESS"), all_steps=True
    )
    authority.identity = authority.identity.model_copy(
        update=dict(graph_definition_version=graph_version, state_schema_version=state_version)
    )
    with pytest.raises(ValueError):
        factory.initial_state(run)
