from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentRecord(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    reasoning_effort: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=256)
    rag_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rag_collection: Mapped[str | None] = mapped_column(String(120))
    memory_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AgentMessageRecord(Base):
    __tablename__ = "agent_messages"
    __table_args__ = (
        Index("ix_agent_messages_agent_thread_created", "agent_id", "thread_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), index=True)
    api_key_id: Mapped[int] = mapped_column(ForeignKey("api_keys.id"), index=True, nullable=False)
    thread_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
