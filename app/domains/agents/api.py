import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.errors import openai_error
from app.domains.agents.domain import Agent
from app.domains.agents.schemas import AgentChatRequest, CreateAgentRequest
from app.domains.agents.service import AgentNotFoundError
from app.domains.model_catalog.domain import ModelNotInstalledError
from app.http.dependencies import AuthDep, DbDep

router = APIRouter()


def _agent_payload(agent: Agent) -> dict[str, object]:
    return {
        "id": agent.id,
        "name": agent.name,
        "system_prompt": agent.system_prompt,
        "model": agent.model,
        "reasoning_effort": agent.reasoning_effort,
        "max_output_tokens": agent.max_output_tokens,
        "rag_enabled": agent.rag_enabled,
        "rag_collection": agent.rag_collection,
        "memory_messages": agent.memory_messages,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
    }


@router.get("/admin/agents")
async def list_agents(request: Request, auth: AuthDep, db: DbDep):
    if isinstance(auth, JSONResponse):
        return auth
    agents = await request.app.state.agents.repository.list_for_api_key(db, auth.api_key.id)
    return JSONResponse(
        {"agents": [_agent_payload(agent) for agent in agents]},
        headers=auth.rate_limit.headers(),
    )


@router.post("/admin/agents")
async def create_agent(body: CreateAgentRequest, request: Request, auth: AuthDep, db: DbDep):
    if isinstance(auth, JSONResponse):
        return auth
    try:
        agent = await request.app.state.agents.create(
            db,
            api_key_id=auth.api_key.id,
            name=body.name,
            system_prompt=body.system_prompt,
            model=body.model,
            reasoning_effort=body.reasoning_effort,
            max_output_tokens=body.max_output_tokens,
            rag_enabled=body.rag_enabled,
            rag_collection=body.rag_collection,
            memory_messages=body.memory_messages,
        )
    except ModelNotInstalledError as exc:
        return openai_error(
            400,
            f"The model '{exc.args[0]}' is not installed in Ollama.",
            error_type="invalid_request_error",
            code="model_not_found",
            param="model",
            headers=auth.rate_limit.headers(),
        )
    except ValueError as exc:
        return openai_error(
            400,
            str(exc),
            error_type="invalid_request_error",
            code="invalid_agent",
            headers=auth.rate_limit.headers(),
        )
    return JSONResponse(_agent_payload(agent), status_code=201, headers=auth.rate_limit.headers())


@router.delete("/admin/agents/{agent_id}")
async def delete_agent(agent_id: str, request: Request, auth: AuthDep, db: DbDep):
    if isinstance(auth, JSONResponse):
        return auth
    deleted = await request.app.state.agents.repository.delete(db, auth.api_key.id, agent_id)
    if not deleted:
        return openai_error(
            404,
            "Agent not found.",
            error_type="invalid_request_error",
            code="agent_not_found",
            headers=auth.rate_limit.headers(),
        )
    return JSONResponse({"deleted": True, "agent_id": agent_id}, headers=auth.rate_limit.headers())


@router.post("/admin/agents/{agent_id}/chat")
async def chat_with_agent(
    agent_id: str,
    body: AgentChatRequest,
    request: Request,
    auth: AuthDep,
    db: DbDep,
):
    if isinstance(auth, JSONResponse):
        return auth
    try:
        payload = await request.app.state.agents.chat(
            db,
            api_key_id=auth.api_key.id,
            agent_id=agent_id,
            message=body.message,
            thread_id=body.thread_id,
            request_id=request.state.request_id,
        )
    except AgentNotFoundError:
        return openai_error(
            404,
            "Agent not found.",
            error_type="invalid_request_error",
            code="agent_not_found",
            headers=auth.rate_limit.headers(),
        )
    except httpx.HTTPStatusError as exc:
        return openai_error(
            502,
            f"Agent dependency rejected the request: {exc.response.text[:500]}",
            error_type="upstream_error",
            code="agent_dependency_error",
            headers=auth.rate_limit.headers(),
        )
    except Exception as exc:
        return openai_error(
            502,
            f"Agent execution failed: {exc}",
            error_type="upstream_error",
            code="agent_execution_failed",
            headers=auth.rate_limit.headers(),
        )
    return JSONResponse(
        payload,
        headers={"x-request-id": request.state.request_id, **auth.rate_limit.headers()},
    )


@router.delete("/admin/agents/{agent_id}/memory/{thread_id}")
async def clear_agent_memory(
    agent_id: str,
    thread_id: str,
    request: Request,
    auth: AuthDep,
    db: DbDep,
):
    if isinstance(auth, JSONResponse):
        return auth
    agent = await request.app.state.agents.repository.get(db, auth.api_key.id, agent_id)
    if agent is None:
        return openai_error(
            404,
            "Agent not found.",
            error_type="invalid_request_error",
            code="agent_not_found",
            headers=auth.rate_limit.headers(),
        )
    deleted = await request.app.state.agents.repository.clear_memory(
        db,
        api_key_id=auth.api_key.id,
        agent_id=agent_id,
        thread_id=thread_id,
    )
    return JSONResponse(
        {"deleted_messages": deleted, "agent_id": agent_id, "thread_id": thread_id},
        headers=auth.rate_limit.headers(),
    )
