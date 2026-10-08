"""An owning legal review cannot be approved into a fabricated formal result."""

# ruff: noqa: F401,F811 -- shared canonical fixtures
from uuid import UUID, uuid4

import pytest
from phase1l_b_worker import build
from test_m2c_authority_postgres import authority
from test_phase1j_postgres import fixture, foundation_i
from test_phase1l_b_postgres import manifest

from crossborder_compliance.application.review_services import (
    HumanReviewService,
    ReviewDecisionRequest,
)
from crossborder_compliance.domain.security import RepositoryContext
from crossborder_compliance.infrastructure.persistence.postgres_repositories import (
    PostgresReviewRepository,
)
from crossborder_compliance.infrastructure.persistence.review_governance import ReviewConflict

pytestmark = pytest.mark.runtime_smoke


@pytest.mark.parametrize("authority", [{"permission_field": "missing_formal_fact"}], indirect=True)
def test_formal_crossborder_review_refuses_approval_and_retains_support(authority):
    f = authority
    m = manifest(f)
    runtime, factory = build(m)
    run = UUID(m["run"])
    runtime.inspect_checkpoint_state(run)
    assert runtime.start(run, factory.initial_state(run)).status == "REVIEW_REQUIRED"
    repo = PostgresReviewRepository(
        f["sf"], RepositoryContext.user(UUID(f["tenant"]), "author", set(m["scopes"]))
    )
    task = repo.list().items[0]
    assert task.owning_stage == "cross_border" and "APPROVE" not in task.allowed_actions
    assert task.evidence_refs and UUID(f["basis"]) in task.legal_basis_refs
    before = runtime.inspect_checkpoint_state(run)
    payload = dict(expected_record_version=task.record_version, idempotency_key=str(uuid4()))
    with pytest.raises(ReviewConflict, match="ACTION_NOT_ALLOWED"):
        repo.decide(task.review_id, ReviewDecisionRequest(decision="APPROVE", **payload))
    HumanReviewService(repo, lambda _: pytest.fail("formal review cannot resume")).decide(
        task.review_id, ReviewDecisionRequest(decision="REQUEST_CHANGES", **payload)
    )
    after = runtime.inspect_checkpoint_state(run)
    assert after == before and "candidate_path" not in after["values"]["result_refs"]
    assert (
        "final_path" not in after["values"]["result_refs"]
        and "documents" not in after["values"]["result_refs"]
    )
