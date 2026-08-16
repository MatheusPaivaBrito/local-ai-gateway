from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.errors import openai_error

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/admin/ui/session", include_in_schema=False)
async def local_ui_session(request: Request) -> JSONResponse:
    settings = request.app.state.settings
    if not settings.local_ui_enabled:
        return openai_error(
            404,
            "Local UI is disabled.",
            error_type="invalid_request_error",
            code="local_ui_disabled",
        )
    raw_key = getattr(request.app.state, "local_ui_api_key", None)
    if not raw_key:
        return openai_error(
            503,
            "Local UI session is unavailable.",
            error_type="server_error",
            code="local_ui_session_unavailable",
        )
    return JSONResponse(
        {
            "ready": True,
            "api_key": raw_key,
            "mode": "gpu" if settings.gpu_telemetry_enabled else "cpu",
            "telemetry_enabled": settings.gpu_telemetry_enabled,
            "rag_enabled": settings.rag_enabled,
            "rag_embedding_model": settings.rag_embedding_model,
        },
        headers={"Cache-Control": "no-store"},
    )


@router.get("/admin/ui/status", include_in_schema=False)
async def local_ui_status(request: Request) -> JSONResponse:
    settings = request.app.state.settings
    if not settings.local_ui_enabled:
        return openai_error(
            404,
            "Local UI is disabled.",
            error_type="invalid_request_error",
            code="local_ui_disabled",
        )

    postgres_ok = redis_ok = ollama_ok = qdrant_ok = False
    try:
        async with request.app.state.database.sessions() as session:
            await session.execute(select(1))
        postgres_ok = True
    except Exception:
        pass

    try:
        redis_ok = bool(await request.app.state.redis.ping())
    except Exception:
        pass

    try:
        await request.app.state.model_catalog.client.list_installed()
        ollama_ok = True
    except Exception:
        pass

    try:
        qdrant_ok = bool(
            request.app.state.rag
            and await request.app.state.rag.store.ready()
        )
    except Exception:
        pass

    return JSONResponse(
        {
            "gateway": True,
            "postgres": postgres_ok,
            "redis": redis_ok,
            "ollama": ollama_ok,
            "qdrant": qdrant_ok,
            "mode": "gpu" if settings.gpu_telemetry_enabled else "cpu",
            "telemetry_enabled": settings.gpu_telemetry_enabled,
            "rag_enabled": settings.rag_enabled,
        },
        headers={"Cache-Control": "no-store"},
    )
