from typing import Literal

from pydantic import BaseModel, Field


class CreateAgentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    system_prompt: str = Field(default="", max_length=20_000)
    model: str = Field(min_length=1, max_length=200)
    reasoning_effort: Literal["none", "low", "medium", "high", "max"] = "none"
    max_output_tokens: int = Field(default=256, ge=1, le=8192)
    rag_enabled: bool = False
    rag_collection: str | None = Field(default=None, max_length=120)
    memory_messages: int = Field(default=12, ge=0, le=100)


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=100_000)
    thread_id: str | None = Field(default=None, max_length=64)
