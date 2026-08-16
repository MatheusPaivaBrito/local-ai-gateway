from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.agents.domain import Agent, AgentMessage
from app.domains.agents.persistence import AgentRecord
from app.domains.agents.repository import AgentRepository
from app.domains.inference.service import InferenceService, extract_assistant_text
from app.domains.rag.domain import RagHit
from app.domains.rag.service import RagService


class AgentNotFoundError(LookupError):
    pass


class AgentService:
    def __init__(
        self,
        *,
        repository: AgentRepository,
        inference: InferenceService,
        rag: RagService | None,
    ) -> None:
        self.repository = repository
        self.inference = inference
        self.rag = rag

    async def create(
        self,
        db: AsyncSession,
        *,
        api_key_id: int,
        name: str,
        system_prompt: str,
        model: str,
        reasoning_effort: str,
        max_output_tokens: int,
        rag_enabled: bool,
        rag_collection: str | None,
        memory_messages: int,
    ) -> Agent:
        # Resolve now so a saved agent cannot point to a missing model by accident.
        await self.inference.model_catalog.resolve(model)
        if rag_enabled and self.rag is None:
            raise ValueError("RAG is disabled")
        return await self.repository.create(
            db,
            AgentRecord(
                id=str(uuid4()),
                api_key_id=api_key_id,
                name=name.strip(),
                system_prompt=system_prompt.strip(),
                model=model.strip(),
                reasoning_effort=reasoning_effort,
                max_output_tokens=max_output_tokens,
                rag_enabled=rag_enabled,
                rag_collection=rag_collection.strip() if rag_collection else None,
                memory_messages=memory_messages,
            ),
        )

    async def chat(
        self,
        db: AsyncSession,
        *,
        api_key_id: int,
        agent_id: str,
        message: str,
        thread_id: str | None,
        request_id: str,
    ) -> dict[str, Any]:
        agent = await self.repository.get(db, api_key_id, agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id)

        thread = (thread_id or str(uuid4())).strip()
        history = await self.repository.recent_messages(
            db,
            api_key_id=api_key_id,
            agent_id=agent.id,
            thread_id=thread,
            limit=agent.memory_messages,
        )

        rag_context = ""
        rag_hits: list[RagHit] = []
        if agent.rag_enabled:
            if self.rag is None:
                raise ValueError("RAG is disabled")
            rag_context, rag_hits = await self.rag.context_for(
                query=message,
                collection=agent.rag_collection,
            )

        system_parts = [agent.system_prompt] if agent.system_prompt else []
        if rag_context:
            system_parts.append(
                "Use o contexto recuperado abaixo quando ele for relevante. "
                "Se o contexto não responder à pergunta, não invente informações.\n\n"
                f"{rag_context}"
            )

        messages: list[dict[str, str]] = []
        if system_parts:
            messages.append({"role": "system", "content": "\n\n".join(system_parts)})
        messages.extend({"role": item.role, "content": item.content} for item in history)
        messages.append({"role": "user", "content": message.strip()})

        result = await self.inference.generate(
            endpoint="/chat/completions",
            payload={
                "model": agent.model,
                "messages": messages,
                "stream": False,
                "max_tokens": agent.max_output_tokens,
                "reasoning_effort": agent.reasoning_effort,
            },
            api_key_id=api_key_id,
            db=db,
            request_id=request_id,
        )
        output = extract_assistant_text(result.payload)
        if result.status_code < 400 and output:
            await self.repository.add_messages(
                db,
                api_key_id=api_key_id,
                agent_id=agent.id,
                thread_id=thread,
                messages=[
                    AgentMessage(role="user", content=message.strip()),
                    AgentMessage(role="assistant", content=output),
                ],
            )

        return {
            "agent_id": agent.id,
            "thread_id": thread,
            "output_text": output,
            "rag_hits": [
                {
                    "id": hit.id,
                    "score": hit.score,
                    "text": hit.text,
                    "metadata": hit.metadata,
                }
                for hit in rag_hits
            ],
            "response": result.payload,
        }
