from typing import Any

from pydantic import BaseModel, Field


class IngestDocumentRequest(BaseModel):
    text: str = Field(min_length=1)
    collection: str | None = None
    source_id: str | None = Field(default=None, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchRagRequest(BaseModel):
    query: str = Field(min_length=1)
    collection: str | None = None
    limit: int | None = Field(default=None, ge=1, le=20)
