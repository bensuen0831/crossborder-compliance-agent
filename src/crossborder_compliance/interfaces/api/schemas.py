from __future__ import annotations

from crossborder_compliance.application.dtos import (
    ConversationThreadDTO,
    ProjectDTO,
    ProjectVersionDTO,
)

# API response schemas are Pydantic DTOs, never ORM entities.
ProjectResponse = ProjectDTO
ProjectVersionResponse = ProjectVersionDTO
ConversationThreadResponse = ConversationThreadDTO

__all__ = ["ProjectResponse", "ProjectVersionResponse", "ConversationThreadResponse"]
