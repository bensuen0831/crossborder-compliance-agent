from typing import Protocol

from crossborder_compliance.domain.knowledge import KnowledgeChunk, KnowledgeStructureNode


class ControlledDownloaderPort(Protocol):
    def download(self, url: str) -> tuple[bytes, dict]: ...


class ChunkingStrategyPort(Protocol):
    strategy_version: str

    def chunk(self, nodes: list[KnowledgeStructureNode], strategy: str) -> list[KnowledgeChunk]: ...


class EmbeddingPort(Protocol):
    def embed(
        self, texts: list[str], *, model_config_id: str, dimension: int
    ) -> list[list[float]]: ...


class KnowledgeRepositoryPort(Protocol):
    def schedule_ingestion(self, version_id: str, payload: dict) -> dict: ...
    def ingestion_input(self, run_id: str) -> dict: ...
    def complete_ingestion(
        self,
        run_id: str,
        nodes: list[KnowledgeStructureNode],
        chunks: list[KnowledgeChunk],
        audit: dict,
    ) -> dict: ...
    def fail_ingestion(self, run_id: str) -> None: ...
    def formal_context(
        self, project_id: str, subject_type: str, subject_id: str, snapshot_id: str | None
    ) -> dict: ...
    def scope_candidates(self, when, pinned_version_ids: tuple[str, ...] = ()) -> list[dict]: ...
    def saved_scope(
        self, project_id: str, subject_type: str, subject_id: str, snapshot_id: str
    ) -> dict | None: ...
    def save_scope(self, payload: dict) -> dict: ...
    def snapshot_date(self, snapshot_id: str): ...
