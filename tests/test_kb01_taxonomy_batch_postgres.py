"""Real-PG batch counts and complete JSON parity with the reviewed pre-fix reader."""

import hashlib
import json
import os
import subprocess
import time
import types
from functools import partial
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event
from test_kb01_taxonomy_postgres import create, mutation, publish
from test_kb01_taxonomy_postgres import env as env

from crossborder_compliance.domain.knowledge_management import (
    EditTaxonomy,
    KnowledgeManagementPermissionError,
    TaxonomyPayload,
)
from crossborder_compliance.infrastructure.persistence.knowledge_taxonomy import (
    PostgresKnowledgeTaxonomyRepository,
)

pytestmark = pytest.mark.runtime_smoke
REFERENCE = "39c3581ca455df4e3ce9760ed2deab8905a5f588"


@pytest.fixture(scope="module")
def reference_reader():
    # Trusted committed code is used only as a test oracle, never production.
    path = "src/crossborder_compliance/infrastructure/persistence/knowledge_taxonomy.py"
    source = subprocess.check_output(["git", "show", REFERENCE + ":" + path])
    module = types.ModuleType("kb01_reviewed_taxonomy_test_oracle")
    exec(compile(source, REFERENCE + ":" + path, "exec"), module.__dict__)
    return module.PostgresKnowledgeTaxonomyRepository


def measured(engine, callback):
    queries = []

    def capture(*args):
        queries.append(1)

    event.listen(engine, "before_cursor_execute", capture)
    start = time.perf_counter()
    try:
        result = callback()
    finally:
        elapsed = time.perf_counter() - start
        event.remove(engine, "before_cursor_execute", capture)
    return result, {"sql_statements": len(queries), "elapsed_seconds": elapsed}


@pytest.mark.parametrize("lifecycle", ["DRAFT", "ACTIVE", "MIXED"])
def test_bounded_page_reads_match_complete_reviewed_json(env, reference_reader, lifecycle):
    sf, _, context, service = env
    for n in range(100):
        row = create(
            service(),
            payload=TaxonomyPayload(
                aliases=["batch parity"],
                localized_display={
                    "localized_display_names": {
                        "en-US": "Synthetic category",
                        "zh-CN": "合成分类",
                        "zh-HK": "合成分類",
                    }
                },
            ),
        )
        if lifecycle == "ACTIVE" or (lifecycle == "MIXED" and n % 2):
            publish(env, row)
    old, new = reference_reader(sf, context()), service().repository
    observations = []
    engine = sf.kw["bind"]
    for locale in ["en-US", "zh-CN", "zh-HK"]:
        for size in [1, 4, 25, 100]:
            before, b = measured(engine, partial(old.list, page_size=size, locale=locale))
            samples = []
            for _ in range(3):
                after, a = measured(engine, partial(new.list, page_size=size, locale=locale))
                assert after == before
                assert a["sql_statements"] == 5
                samples.append(a)
            observations.append(
                {
                    "locale": locale,
                    "page_size": size,
                    "before": b,
                    "after_samples": samples,
                    "complete_json_sha256": hashlib.sha256(
                        json.dumps(after, sort_keys=True).encode()
                    ).hexdigest(),
                }
            )
    for options in [
        {"page": 2, "page_size": 4},
        {"query": "batch parity", "page_size": 25},
        {"query": "合成", "locale": "zh-HK"},
        {"query": "not present"},
    ]:
        assert new.list(**options) == old.list(**options)
    # The reviewed enabled-filter scalar was incorrectly correlated for
    # multi-draft pages. Assert the documented semantics against the unfiltered
    # exact baseline projection instead of treating its SQL error as authority.
    expected = old.list(page_size=100)
    assert new.list(page_size=100, enabled=True) == expected
    assert new.list(enabled=False)["items"] == []
    destination = os.environ.get("EVIDENCE_DIR")
    if destination:
        p = Path(destination) / ("taxonomy-batch-" + lifecycle.lower() + ".json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(
                {
                    "reference_source": REFERENCE,
                    "lifecycle": lifecycle,
                    "measurements": observations,
                    "complete_json_parity": True,
                },
                indent=2,
            )
        )


def test_active_exact_pin_ignores_newer_draft_and_actor_is_preserved(env, reference_reader):
    sf, _, context, service = env
    row = create(service())
    publish(env, row)
    detail = service().detail(UUID(row["definition_id"]))
    service("new-draft-author").mutate(
        "NEW_VERSION",
        UUID(row["definition_id"]),
        EditTaxonomy(
            **mutation(detail["record_version"]).model_dump(),
            payload=TaxonomyPayload(description="Unpublished future version"),
        ),
    )
    result = service().repository.list()
    assert result == reference_reader(sf, context()).list()
    assert result["items"][0]["version_id"] == row["version_id"]
    assert result["items"][0]["created_by"] == "author"
    assert result["items"][0]["updated_by"] == "new-draft-author"


def test_batch_reader_empty_foreign_tenant_and_denial_make_no_cross_tenant_reads(
    env, reference_reader
):
    from crossborder_compliance.domain.security import RepositoryContext

    sf, _, context, service = env
    create(service())
    foreign = RepositoryContext.user(uuid4(), "other-tenant", {"knowledge:taxonomy:read"})
    new = PostgresKnowledgeTaxonomyRepository(sf, foreign)
    assert new.list() == reference_reader(sf, foreign).list()
    assert new.list()["items"] == []
    _, count = measured(sf.kw["bind"], lambda: new.list())
    assert count["sql_statements"] == 2
    denied = PostgresKnowledgeTaxonomyRepository(sf, context(grants=set()))
    with pytest.raises(KnowledgeManagementPermissionError):
        denied.list(page_size=100)


def test_missing_version_and_missing_actor_keep_exact_null_projection(env, reference_reader):
    from crossborder_compliance.infrastructure.persistence import metadata_models as m

    sf, tenant, context, service = env
    # A legitimate empty definition has no version/creator/operation receipt.
    with sf() as s, s.begin():
        s.add(
            m.MetadataDefinitionEntity(
                tenant_id=str(tenant),
                definition_id=str(uuid4()),
                kind="REGULATION_CATEGORY",
                code="EMPTY",
                display_name="Empty draft definition",
            )
        )
    assert service().repository.list() == reference_reader(sf, context()).list()
    row = service().repository.list()["items"][0]
    assert row["version_id"] is None and row["created_by"] is None and row["updated_by"] is None


def test_newest_draft_and_enabled_filter_remain_definition_correlated(env, reference_reader):
    from sqlalchemy.exc import ProgrammingError

    sf, _, context, service = env
    for enabled in (True, False):
        create(service(), payload=TaxonomyPayload(enabled=enabled))
    old = reference_reader(sf, context())
    # Record the concrete reviewed-source bug rather than silently changing
    # expectations: its nested scalar lost the version's correlation.
    with pytest.raises(ProgrammingError, match="more than one row"):
        old.list(enabled=True)
    for enabled in (True, False):
        expected = old.list(page_size=100)
        expected["items"] = [x for x in expected["items"] if x["enabled"] is enabled]
        expected["total"] = len(expected["items"])
        assert service().repository.list(page_size=100, enabled=enabled) == expected
