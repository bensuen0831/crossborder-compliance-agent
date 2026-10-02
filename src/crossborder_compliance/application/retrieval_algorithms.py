"""Deterministic policy calculations. Similarity never determines legal sufficiency."""

import hashlib
import math
from collections import defaultdict
from uuid import uuid4

from crossborder_compliance.application.retrieval_ports import RerankerPort, RetrievalRepositoryPort
from crossborder_compliance.domain.retrieval import (
    ActionableFallbackGuidanceContext,
    GuidanceAction,
    HybridRetrievalResult,
    KnowledgeSufficiencyResult,
    RerankResult,
    ScopeValidationResult,
)


class HybridMergeStrategy:
    def merge(self, lexical, vector, policy):
        by_id = {}
        ranks = {}
        for channel, candidates in (("LEXICAL", lexical.candidates), ("VECTOR", vector.candidates)):
            for rank, candidate in enumerate(candidates, 1):
                existing = by_id.get(candidate.chunk_id)
                if existing and (
                    existing.knowledge_version_id != candidate.knowledge_version_id
                    or existing.index_version_id != candidate.index_version_id
                ):
                    raise ValueError("inconsistent canonical duplicate")
                if (candidate.chunk_id, channel) in ranks:
                    continue
                ranks[(candidate.chunk_id, channel)] = rank
                merged = existing or candidate
                updates = {"channels": tuple(sorted(set(merged.channels) | {channel}))}
                updates["lexical_score" if channel == "LEXICAL" else "vector_score"] = (
                    candidate.lexical_score if channel == "LEXICAL" else candidate.vector_score
                )
                by_id[candidate.chunk_id] = merged.model_copy(update=updates)
        result = []
        total_weight = policy.lexical_weight + policy.vector_weight
        for ident, candidate in by_id.items():
            if policy.hybrid_strategy == "WEIGHTED_SCORE":
                lexical_score = max(0, candidate.lexical_score or 0)
                lexical_normalized = lexical_score / (1 + lexical_score)
                vector_normalized = max(0, min(1, ((candidate.vector_score or 0) + 1) / 2))
                if candidate.vector_score is None:
                    vector_normalized = 0
                score = (
                    policy.lexical_weight * lexical_normalized
                    + policy.vector_weight * vector_normalized
                ) / total_weight
            else:
                score = (
                    sum(
                        weight / (policy.rrf_constant + ranks[(ident, channel)])
                        for channel, weight in (
                            ("LEXICAL", policy.lexical_weight),
                            ("VECTOR", policy.vector_weight),
                        )
                        if (ident, channel) in ranks
                    )
                    / total_weight
                )
            if score >= policy.evidence_threshold:
                result.append(candidate.model_copy(update={"hybrid_score": score}))
        result.sort(key=lambda c: (-c.hybrid_score, c.chunk_id))
        return HybridRetrievalResult(candidates=tuple(result[: policy.candidate_limit]))


class RerankService:
    def __init__(self, adapter: RerankerPort):
        self.adapter = adapter

    def rerank(self, query, candidates, policy):
        allowed = {candidate.chunk_id: candidate for candidate in candidates}
        outputs = self.adapter.rerank(
            query, tuple(candidates), model_config_id=policy.rerank_config_id
        )
        ranked, dropped, seen = [], [], set()
        for ident, score in outputs:
            if ident not in allowed:
                dropped.append(
                    {
                        "reason_code": "RERANK_OUTSIDE_ALLOWED_SET",
                        "candidate_hash": hashlib.sha256(ident.encode()).hexdigest(),
                    }
                )
                continue
            if ident in seen:
                continue
            if not math.isfinite(score):
                raise ValueError("invalid rerank score")
            seen.add(ident)
            ranked.append(allowed[ident].model_copy(update={"rerank_score": float(score)}))
        # An adapter may omit candidates; it cannot silently delete their original provenance.
        ranked.extend(allowed[ident] for ident in sorted(set(allowed) - seen))
        ranked.sort(
            key=lambda c: (
                -(c.rerank_score if c.rerank_score is not None else -math.inf),
                -c.hybrid_score,
                c.chunk_id,
            )
        )
        return RerankResult(candidates=tuple(ranked), dropped=tuple(dropped))


class RetrievalScopeValidator:
    def __init__(self, repository: RetrievalRepositoryPort):
        self.repository = repository

    def validate(self, candidates, plan):
        ids = tuple(c.chunk_id for c in candidates)
        permitted = set(self.repository.eligible_chunk_ids(plan, ids))
        dropped = tuple(
            {
                "reason_code": "SCOPE_REVALIDATION_DROP",
                "candidate_hash": hashlib.sha256(i.encode()).hexdigest(),
            }
            for i in ids
            if i not in permitted
        )
        return ScopeValidationResult(
            allowed_chunk_ids=tuple(i for i in ids if i in permitted),
            dropped=dropped,
            status="NARROWED" if dropped else "PASS",
        )


class KnowledgeSufficiencyService:
    def assess(self, pack, scope, policy):
        effective = [
            e
            for e in pack.items
            if e.effective_from is not None
            and e.effective_from <= scope.effective_as_of
            and (e.effective_to is None or e.effective_to >= scope.effective_as_of)
            and e.citation_id
            and e.provenance
            and e.content_hash
        ]
        official = [
            e
            for e in effective
            if e.source_tier in policy.authoritative_tiers
            and e.source_authority
            and e.evidence_quality >= policy.minimum_evidence_quality
            and e.jurisdiction_specific
        ]
        jurisdiction = {
            j: any(e.jurisdiction_id == j for e in official) for j in scope.allowed_jurisdiction_ids
        }
        regulations = {
            r: any(r in e.regulation_refs for e in official)
            for r in policy.required_regulation_refs
        }
        topics = {r for e in official for r in e.topic_refs}
        missing = tuple(sorted(set(policy.required_topic_refs) - topics))
        claims = defaultdict(set)
        for evidence in effective:
            if evidence.conflict_key and evidence.claim_hash:
                claims[evidence.conflict_key].add(evidence.claim_hash)
        conflicts = sum(len(values) for values in claims.values() if len(values) > 1)
        reasons = []
        if not jurisdiction or not all(jurisdiction.values()):
            reasons.append("JURISDICTION_SPECIFIC_EVIDENCE_MISSING")
        if not official:
            reasons.append("OFFICIAL_EFFECTIVE_EVIDENCE_MISSING")
        if len(official) < policy.minimum_authoritative_evidence_count:
            reasons.append("AUTHORITATIVE_EVIDENCE_COUNT_LOW")
        if not all(regulations.values()):
            reasons.append("CONFIGURED_REGULATION_COVERAGE_MISSING")
        if missing:
            reasons.append("TOPIC_COVERAGE_MISSING")
        if len(effective) < len(pack.items):
            reasons.append("EFFECTIVE_DATE_OR_PROVENANCE_INCOMPLETE")
        if conflicts:
            reasons.append("APPROVED_EVIDENCE_CONFLICT")
        status = (
            "CONFLICTED"
            if conflicts
            else "SUFFICIENT"
            if not reasons
            else "PARTIALLY_SUFFICIENT"
            if official
            else "INSUFFICIENT"
        )
        quality = min((e.evidence_quality for e in effective), default=0)
        count = len(pack.items)
        confidence = min(
            quality,
            sum(jurisdiction.values()) / len(jurisdiction) if jurisdiction else 0,
            len(effective) / count if count else 0,
        )
        return KnowledgeSufficiencyResult(
            sufficiency_result_id=str(uuid4()),
            tenant_id=scope.tenant_id,
            project_id=scope.project_id,
            analysis_snapshot_id=scope.analysis_snapshot_id,
            subject_type=scope.subject_type,
            subject_id=scope.subject_id,
            jurisdiction_ids=scope.allowed_jurisdiction_ids,
            retrieval_run_id=pack.retrieval_run_id,
            evidence_pack_id=pack.evidence_pack_id,
            jurisdiction_coverage=jurisdiction,
            regulation_coverage=regulations,
            official_source_coverage=len(official) / count if count else 0,
            effective_date_coverage=len(effective) / count if count else 0,
            evidence_quality=quality,
            evidence_count=count,
            conflicting_evidence_count=conflicts,
            missing_topics=missing,
            reason_codes=tuple(reasons),
            confidence=confidence,
            review_required=status != "SUFFICIENT",
            status=status,
            policy_version=policy.policy_version_id,
        )


class FallbackGuidanceService:
    def build(self, sufficiency, policy):
        if sufficiency.status == "SUFFICIENT":
            return None

        def action(kind):
            return (
                GuidanceAction(
                    action_code=policy.guidance_actions[kind],
                    jurisdiction_ids=sufficiency.jurisdiction_ids,
                    topic_refs=sufficiency.missing_topics,
                ),
            )

        return ActionableFallbackGuidanceContext(
            conservative_controls=action("conservative_control"),
            evidence_acquisition_steps=action("evidence_acquisition"),
            jurisdiction_verification_steps=action("jurisdiction_verification"),
            unresolved_legal_questions=sufficiency.reason_codes,
            operational_next_steps=action("operational_next_step"),
            prohibited_assertions=(
                "UNSUPPORTED_LEGAL_APPLICABILITY",
                "CROSS_BORDER_LEGAL_DECISION",
                "LEGAL_OBLIGATION",
                "RISK_SCORE",
                "COMPLIANCE_PATH",
            ),
            evidence_status=sufficiency.status,
            confidence=sufficiency.confidence,
        )
