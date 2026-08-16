from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Agent:
    id: str
    api_key_id: int
    name: str
    system_prompt: str
    model: str
    reasoning_effort: str
    max_output_tokens: int
    rag_enabled: bool
    rag_collection: str | None
    memory_messages: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AgentMessage:
    role: str
    content: str
    created_at: datetime | None = None
