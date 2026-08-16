from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.agents.domain import Agent, AgentMessage
from app.domains.agents.persistence import AgentMessageRecord, AgentRecord


def _agent(record: AgentRecord) -> Agent:
    return Agent(
        id=record.id,
        api_key_id=record.api_key_id,
        name=record.name,
        system_prompt=record.system_prompt,
        model=record.model,
        reasoning_effort=record.reasoning_effort,
        max_output_tokens=record.max_output_tokens,
        rag_enabled=record.rag_enabled,
        rag_collection=record.rag_collection,
        memory_messages=record.memory_messages,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class AgentRepository:
    async def create(self, db: AsyncSession, record: AgentRecord) -> Agent:
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return _agent(record)

    async def list_for_api_key(self, db: AsyncSession, api_key_id: int) -> list[Agent]:
        result = await db.execute(
            select(AgentRecord)
            .where(AgentRecord.api_key_id == api_key_id)
            .order_by(AgentRecord.name.asc())
        )
        return [_agent(record) for record in result.scalars().all()]

    async def get(self, db: AsyncSession, api_key_id: int, agent_id: str) -> Agent | None:
        record = await db.scalar(
            select(AgentRecord).where(
                AgentRecord.id == agent_id,
                AgentRecord.api_key_id == api_key_id,
            )
        )
        return _agent(record) if record is not None else None

    async def delete(self, db: AsyncSession, api_key_id: int, agent_id: str) -> bool:
        result = await db.execute(
            delete(AgentRecord).where(
                AgentRecord.id == agent_id,
                AgentRecord.api_key_id == api_key_id,
            )
        )
        await db.commit()
        return bool(result.rowcount)

    async def recent_messages(
        self,
        db: AsyncSession,
        *,
        api_key_id: int,
        agent_id: str,
        thread_id: str,
        limit: int,
    ) -> list[AgentMessage]:
        result = await db.execute(
            select(AgentMessageRecord)
            .where(
                AgentMessageRecord.api_key_id == api_key_id,
                AgentMessageRecord.agent_id == agent_id,
                AgentMessageRecord.thread_id == thread_id,
            )
            .order_by(AgentMessageRecord.created_at.desc(), AgentMessageRecord.id.desc())
            .limit(limit)
        )
        records = list(reversed(result.scalars().all()))
        return [
            AgentMessage(
                role=record.role,
                content=record.content,
                created_at=record.created_at,
            )
            for record in records
        ]

    async def add_messages(
        self,
        db: AsyncSession,
        *,
        api_key_id: int,
        agent_id: str,
        thread_id: str,
        messages: list[AgentMessage],
    ) -> None:
        db.add_all(
            [
                AgentMessageRecord(
                    api_key_id=api_key_id,
                    agent_id=agent_id,
                    thread_id=thread_id,
                    role=message.role,
                    content=message.content,
                )
                for message in messages
            ]
        )
        await db.commit()

    async def clear_memory(
        self,
        db: AsyncSession,
        *,
        api_key_id: int,
        agent_id: str,
        thread_id: str,
    ) -> int:
        result = await db.execute(
            delete(AgentMessageRecord).where(
                AgentMessageRecord.api_key_id == api_key_id,
                AgentMessageRecord.agent_id == agent_id,
                AgentMessageRecord.thread_id == thread_id,
            )
        )
        await db.commit()
        return int(result.rowcount or 0)
