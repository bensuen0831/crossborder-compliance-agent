import hashlib
import json
from uuid import uuid4

from crossborder_compliance.domain.llm_gateway import (
    GatewayDenied,
    RedactedRange,
    RedactionResult,
)


def input_digest(texts):
    return hashlib.sha256(json.dumps(texts, ensure_ascii=False).encode()).hexdigest()


class DataRedactionService:
    """Irreversible deterministic transformation; detection is a mandatory trusted port."""

    def __init__(self, detector):
        self.detector = detector

    def redact(self, texts, refs, policy_versions):
        try:
            detection = self.detector.detect(texts)
            if (
                not detection.complete
                or detection.reviewer_required
                or detection.input_hash != input_digest(texts)
            ):
                raise GatewayDenied("REDACTION_NOT_VALIDATED")
            ranges = []
            for span in detection.spans:
                if span.part_index >= len(texts) or not 0 <= span.start < span.end <= len(
                    texts[span.part_index]
                ):
                    raise GatewayDenied("REDACTION_RANGE_INVALID")
                ranges.append(span)
            # Overlap is merged into one covering interval, never partially masked.
            merged = []
            for span in sorted(ranges, key=lambda x: (x.part_index, x.start, x.end)):
                if merged and merged[-1][0] == span.part_index and span.start <= merged[-1][2]:
                    prior = merged[-1]
                    merged[-1] = (prior[0], prior[1], max(prior[2], span.end), prior[3])
                else:
                    merged.append((span.part_index, span.start, span.end, span.sensitive_type))
            run = uuid4()
            masked = list(texts)
            records = tuple(
                RedactedRange(
                    part_index=part,
                    start=start,
                    end=end,
                    sensitive_type=kind,
                    replacement_token=f"[REDACTED:{run.hex}:{i}]",
                )
                for i, (part, start, end, kind) in enumerate(merged)
            )
            for r in reversed(records):
                masked[r.part_index] = (
                    masked[r.part_index][: r.start]
                    + r.replacement_token
                    + masked[r.part_index][r.end :]
                )
            result = RedactionResult(
                run_id=run,
                input_refs=refs,
                input_hash=input_digest(texts),
                detected_sensitive_types=tuple(sorted({r.sensitive_type for r in ranges})),
                redacted_ranges=records,
                redacted_texts=tuple(masked),
                policy_versions=policy_versions,
                reviewer_required=False,
            )
            self.validate(result, texts, refs, policy_versions)
            return result
        except Exception:
            raise GatewayDenied("REDACTION_NOT_VALIDATED") from None

    @staticmethod
    def validate(result, texts, refs, policy_versions):
        if (
            result.input_hash != input_digest(texts)
            or result.input_refs != refs
            or result.policy_versions != policy_versions
            or result.reviewer_required
            or result.reversible
            or len(result.redacted_texts) != len(texts)
        ):
            raise GatewayDenied("REDACTION_NOT_VALIDATED")
        expected = list(texts)
        for r in reversed(result.redacted_ranges):
            expected[r.part_index] = (
                expected[r.part_index][: r.start]
                + r.replacement_token
                + expected[r.part_index][r.end :]
            )
        if tuple(expected) != result.redacted_texts:
            raise GatewayDenied("REDACTION_NOT_VALIDATED")
