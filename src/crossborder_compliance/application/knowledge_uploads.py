"""Multipart orchestration is technical transport, never publication or legal analysis."""

from crossborder_compliance.application.knowledge_binary_ports import KnowledgeBinaryStorePort


class KnowledgeUploadService:
    def __init__(self, repository, storage: KnowledgeBinaryStorePort):
        self.repository, self.storage = repository, storage

    def start(self, request):
        row = self.repository.start(request)
        claim = self.repository.initialize_claim(row["upload_session_id"])
        if claim:
            upload_id = self.storage.begin(claim["object_key"], "application/octet-stream")
            try:
                self.repository.initialized(
                    row["upload_session_id"], claim["lease_token"], upload_id
                )
            except Exception:
                self.storage.abort(claim["object_key"], upload_id)
                raise
        return self.repository.detail(row["upload_session_id"])

    def part_url(self, identity, request):
        part = self.repository.part_request(identity, request)
        return self.storage.part_url(
            part["object_key"],
            part["multipart_id"],
            part["number"],
            part["size"],
            part["sha256"],
            part["expiry"],
        )

    def acknowledge(self, identity, request):
        self.repository.part_request(identity, request)
        row = self.repository.transport(identity)
        part = next(
            (
                p
                for p in self.storage.parts(row["object_key"], row["multipart_id"])
                if p["number"] == request.part_number
            ),
            None,
        )
        return self.repository.acknowledge_part(identity, request, part)

    def complete(self, identity, request):
        row = self.repository.transport(identity, "upload:complete")
        if row["status"] == "UPLOADING":
            parts = self.storage.parts(row["object_key"], row["multipart_id"])
        else:
            parts = []
        intent = self.repository.complete_intent(identity, request, parts)
        if intent["status"] == "FINALIZING":
            if parts:
                head = self.storage.complete(row["object_key"], row["multipart_id"], parts)
            else:
                committed_parts = self.repository.completion_parts(identity)
                head = self.storage.complete(
                    row["object_key"], row["multipart_id"], committed_parts
                )
            self.repository.completed(identity, head)
        return self.repository.detail(identity)

    def cancel(self, identity, request):
        intent = self.repository.cancel_intent(identity, request)
        if intent["status"] == "CANCELLING":
            transport = self.repository.transport(identity, "upload:cancel")
            if transport["object_version"]:
                self.storage.delete(transport["object_key"], transport["object_version"])
            elif transport["multipart_id"]:
                self.storage.abort(transport["object_key"], transport["multipart_id"])
            self.repository.cancelled(identity)
        return self.repository.detail(identity)

    def cleanup_once(self):
        claim = self.repository.cleanup_claim()
        if claim is None:
            return False
        if claim["object_version"]:
            self.storage.delete(claim["object_key"], claim["object_version"])
        elif claim["multipart_id"]:
            self.storage.abort(claim["object_key"], claim["multipart_id"])
        else:
            self.storage.abort_pending(claim["object_key"])
        self.repository.cleanup_finished(claim["upload_session_id"], claim["lease_token"])
        return True
