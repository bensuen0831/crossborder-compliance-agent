"""Runtime evidence augmentation through controlled ports, separate from ACTIVE knowledge."""

import hashlib
import json
from datetime import UTC, date, datetime
from uuid import uuid4

from crossborder_compliance.application.knowledge_services import (
    DataCategoryScopeResolver,
    IndustryScopeResolver,
    JurisdictionScopeResolver,
    PermissionScopeResolver,
    ProductScopeResolver,
    ScenarioScopeResolver,
)
from crossborder_compliance.domain.retrieval import (
    ExternalEvidencePack,
    ExternalEvidenceValidationResult,
    RuntimeVerifiedExternalEvidence,
    TrustedSourcePolicy,
)


def rule_permits(rule, formal, context):
    binding = rule.model_dump(mode="json")
    if rule.scope_type == "PRODUCT_SPECIFIC" and not any(
        binding["dimensions"].get(k) for k in ProductScopeResolver.dimensions
    ):
        return False
    if not PermissionScopeResolver().permits(binding, context):
        return False
    if not set(rule.jurisdiction_ids) <= set(formal.dimensions.get("jurisdiction", ())):
        return False
    return all(
        r.permits(binding, formal)
        for r in (
            ProductScopeResolver(),
            JurisdictionScopeResolver(),
            ScenarioScopeResolver(),
            IndustryScopeResolver(),
            DataCategoryScopeResolver(),
        )
    )


class ExternalEvidenceAugmentationService:
    def __init__(self, repository, context, planner, discovery, downloader_factory):
        self.repository, self.context = repository, context
        self.planner, self.discovery, self.downloader_factory = (
            planner,
            discovery,
            downloader_factory,
        )

    def augment(self, query, plan, gaps, suffpolicy):
        repo = self.repository
        policy = TrustedSourcePolicy.model_validate(
            repo.resolve_policy(
                "trusted_source", plan.policy.trusted_source_policy_id, query.analysis_snapshot_id
            )
        )
        formal = repo.retrieval_context(plan.scope)
        # Discovery itself sees only allowed, permission-filtered policy sources.
        policy = policy.model_copy(
            update={
                "source_rules": tuple(
                    r for r in policy.source_rules if rule_permits(r, formal, self.context)
                )
            }
        )
        records, validations = [], []
        candidates = self.discovery.discover(self.planner.plan(query.query_text, gaps), policy)
        rules = {r.source_id: r for r in policy.source_rules}
        for candidate in candidates[: policy.maximum_sources]:
            rule = rules.get(candidate.source_id)
            status, reason = "REJECTED", "SOURCE_OUTSIDE_TRUSTED_SCOPE"
            checks = {}
            try:
                if rule is None:
                    # Do not persist a guessed foreign source identifier via a tenant-blind FK.
                    continue
                source = repo.source(candidate.source_id)
                if (
                    candidate.discovery_origin == "LLM_DISCOVERY_ONLY"
                    or rule.source_tier.startswith("T4")
                ):
                    status, reason = "DISCOVERY_ONLY", "DISCOVERY_CANNOT_BECOME_EVIDENCE"
                    raise ValueError(reason)
                if candidate.source_url != source["canonical_url"]:
                    raise ValueError("SOURCE_URL_NOT_CANONICAL")
                if source.get("authority_ref") != rule.authority_ref:
                    raise ValueError("SOURCE_AUTHORITY_MISMATCH")
                if not set(rule.jurisdiction_ids) <= set(source.get("jurisdiction_refs", ())):
                    raise ValueError("SOURCE_JURISDICTION_MISMATCH")
                official = {
                    "T1_PRIMARY_OFFICIAL": "OFFICIAL_LEGISLATION",
                    "T2_OFFICIAL_GUIDANCE": "OFFICIAL_REGULATOR",
                }
                if (
                    rule.source_tier in official
                    and source["source_type"] != official[rule.source_tier]
                ):
                    raise ValueError("OFFICIAL_SOURCE_TYPE_MISMATCH")
                old = repo.saved_external(
                    query.analysis_snapshot_id, rule.source_id, policy.policy_version_id
                )
                if old is not None:
                    records.append(old)
                    validations.append(old.validation_result)
                    continue
                downloader = self.downloader_factory(source, rule, policy)
                raw, audit = downloader.download(candidate.source_url)
                digest = hashlib.sha256(raw).hexdigest()
                if len(raw) > policy.max_file_size or audit.get("content_hash") != digest:
                    raise ValueError("EXTERNAL_HASH_OR_SIZE_FAILED")
                final_url = audit.get("canonical_url", candidate.source_url)
                if final_url not in (source["canonical_url"], *rule.approved_redirect_urls):
                    raise ValueError("UNAPPROVED_REDIRECT_URL")
                payload = json.loads(raw)
                # Identity/date values come from attributed downloaded metadata, never LLM guesses.
                if payload["authority_ref"] != rule.authority_ref or set(
                    payload["jurisdiction_ids"]
                ) != set(rule.jurisdiction_ids):
                    raise ValueError("ATTRIBUTION_MISMATCH")
                start = date.fromisoformat(payload["effective_from"])
                end = (
                    date.fromisoformat(payload["effective_to"])
                    if payload.get("effective_to")
                    else None
                )
                if start > plan.scope.effective_as_of or (end and end < plan.scope.effective_as_of):
                    raise ValueError("EXTERNAL_EVIDENCE_NOT_EFFECTIVE")
                language = payload["language"]
                if plan.languages and language not in plan.languages:
                    raise ValueError("EXTERNAL_LANGUAGE_EXCLUDED")
                nodes = payload["nodes"]
                if (
                    not nodes
                    or len(nodes) > 10000
                    or len({n["canonical_locator"] for n in nodes}) != len(nodes)
                ):
                    raise ValueError("EXTERNAL_STRUCTURE_INVALID")
                for node in nodes:
                    if not node.get("original_text") or not node.get("canonical_locator"):
                        raise ValueError("EXTERNAL_CITATION_INVALID")
                repo.validate_external_metadata(payload)
                checks = dict(
                    source=True,
                    authority=True,
                    jurisdiction=True,
                    effective_date=True,
                    content_hash=True,
                    citation=True,
                    provenance=True,
                    controlled_transport=True,
                )
                validation = ExternalEvidenceValidationResult(
                    candidate_id=candidate.candidate_id,
                    status="VERIFIED",
                    reason_codes=(),
                    validation_checks=checks,
                )
                record = RuntimeVerifiedExternalEvidence(
                    external_evidence_id=str(uuid4()),
                    analysis_snapshot_id=query.analysis_snapshot_id,
                    source_id=rule.source_id,
                    source_url=candidate.source_url,
                    canonical_url=final_url,
                    source_authority=rule.authority_ref,
                    source_tier=rule.source_tier,
                    jurisdiction_ids=rule.jurisdiction_ids,
                    retrieved_at=datetime.now(UTC),
                    effective_from=start,
                    effective_to=end,
                    publication_date=date.fromisoformat(payload["publication_date"])
                    if payload.get("publication_date")
                    else None,
                    language=language,
                    content_hash=digest,
                    parsed_artifact_version=str(uuid4()),
                    parsed_structure=tuple(
                        dict(n, structure_node_id=str(uuid4()), chunk_id=str(uuid4()))
                        for n in nodes
                    ),
                    validation_result=validation,
                    retrieval_policy_version=plan.policy.policy_version_id,
                    sufficiency_policy_version=suffpolicy.policy_version_id,
                    trusted_source_policy_version=policy.policy_version_id,
                    provenance={
                        "request_audit": audit,
                        "source_hash": source.get("source_hash"),
                        "scope_version": plan.scope.version,
                        "validation_checks": checks,
                    },
                )
                record = repo.persist_external(
                    gaps.retrieval_run_id, candidate, raw, record, validation
                )
                records.append(record)
                validations.append(validation)
            except (
                ValueError,
                KeyError,
                TypeError,
                TimeoutError,
                OSError,
                PermissionError,
                LookupError,
            ):
                # Preserve a stable reason without echoing downloaded content or secrets.
                validation = ExternalEvidenceValidationResult(
                    candidate_id=candidate.candidate_id,
                    status=status,
                    reason_codes=(
                        reason if status == "DISCOVERY_ONLY" else "EXTERNAL_VALIDATION_FAILED",
                    ),
                    validation_checks=checks,
                )
                repo.external_candidate(gaps.retrieval_run_id, candidate, validation)
                validations.append(validation)
        return ExternalEvidencePack(
            records=tuple(records),
            validations=tuple(validations),
            reason_codes=() if records else ("NO_VERIFIED_EXTERNAL_EVIDENCE",),
        )
