from __future__ import annotations

from uuid import uuid4

import pytest

from crossborder_compliance.domain.entities import ClassificationResult, ProjectVersion
from crossborder_compliance.domain.foundation import DataFlowEdge, WorkflowRun
from crossborder_compliance.domain.security import RepositoryContext, TenantAccessDenied


def test_version_invariant_rejects_zero() -> None:
    with pytest.raises(ValueError):
        ProjectVersion(
            tenant_id=uuid4(),
            project_version_id=uuid4(),
            project_id=uuid4(),
            version_no=1,
            record_version=0,
        )


def test_project_version_number_invariant() -> None:
    with pytest.raises(ValueError):
        ProjectVersion(
            tenant_id=uuid4(),
            project_version_id=uuid4(),
            project_id=uuid4(),
            version_no=0,
        )


def test_data_flow_edge_requires_distinct_nodes() -> None:
    node = uuid4()
    with pytest.raises(ValueError):
        DataFlowEdge(
            tenant_id=uuid4(),
            flow_edge_id=uuid4(),
            project_id=uuid4(),
            source_node_id=node,
            target_node_id=node,
            flow_type="TRANSFER",
        )


def test_classification_confidence_invariant() -> None:
    with pytest.raises(ValueError):
        ClassificationResult(
            tenant_id=uuid4(),
            classification_result_id=uuid4(),
            subject_type="DATA_ITEM",
            subject_id=uuid4(),
            scheme_id=uuid4(),
            jurisdiction_id=uuid4(),
            confidence=1.1,
        )


def test_formal_workflow_thread_identity_invariant() -> None:
    workflow_run_id = uuid4()
    with pytest.raises(ValueError):
        WorkflowRun(
            tenant_id=uuid4(),
            workflow_run_id=workflow_run_id,
            thread_id=uuid4(),
            analysis_snapshot_id=uuid4(),
        )


def test_repository_context_requires_explicit_target_tenant() -> None:
    tenant_a, tenant_b = uuid4(), uuid4()
    context = RepositoryContext.user(tenant_a, actor_id="user-a")
    with pytest.raises(TenantAccessDenied):
        context.assert_tenant(tenant_b)
    RepositoryContext.system(tenant_b).assert_tenant(tenant_b)
