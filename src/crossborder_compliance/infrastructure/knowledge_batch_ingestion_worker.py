"""Durable import item adapter, invoking the single canonical Knowledge ingestion service."""

from botocore.exceptions import BotoCoreError, ClientError


class KnowledgeBatchIngestionWorker:
    def __init__(self, batches, ingestion):
        self.batches, self.ingestion = batches, ingestion

    def run_once(self):
        claim = self.batches.ingestion_claim()
        if claim is None:
            return False
        error = None
        try:
            identity = claim["ingestion_run_id"]
            if identity is None:
                run = self.ingestion.ingest(
                    claim["knowledge_version_id"],
                    {
                        "binary_upload_session_id": claim["upload_session_id"],
                        "expected_record_version": claim["expected_record_version"],
                        "idempotency_key": "batch-native:"
                        + claim["batch_id"]
                        + ":"
                        + claim["item_id"],
                    },
                )
                identity = run["ingestion_run_id"]
            self.ingestion.work(identity)
        except (BotoCoreError, ClientError):
            error = "BINARY_SOURCE_UNAVAILABLE"
        except (ValueError, TimeoutError):
            error = "NATIVE_EXTRACTION_REFUSED"
        self.batches.ingestion_finished(claim, error)
        return True
