from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class RagHit:
    id: str
    score: float
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RagIngestResult:
    collection: str
    source_id: str
    chunks: int
    embedding_model: str
