import json
from datetime import UTC, datetime

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.errors import openai_error
from app.domains.model_catalog.schemas import PullModelRequest
from app.http.dependencies import AuthDep, require_admin

router = APIRouter()


@router.get("/v1/models")
async def openai_models(request: Request, auth: AuthDep):
    if isinstance(auth, JSONResponse):
        return auth
    try:
        names = await request.app.state.model_catalog.public_model_names()
    except Exception as exc:
        return openai_error(
            502,
            f"Ollama model catalog unavailable: {exc}",
            error_type="upstream_error",
            code="ollama_catalog_unavailable",
        )

    now = int(datetime.now(UTC).timestamp())
    return JSONResponse(
        {
            "object": "list",
            "data": [
                {
                    "id": name,
                    "object": "model",
                    "created": now,
                    "owned_by": "local-ai-gateway",
                }
                for name in names
            ],
        },
        headers=auth.rate_limit.headers(),
    )


@router.get("/admin/models")
async def installed_models(request: Request, auth: AuthDep):
    if isinstance(auth, JSONResponse):
        return auth
    try:
        models = await request.app.state.model_catalog.list_models()
    except Exception as exc:
        return openai_error(
            502,
            f"Could not read Ollama models: {exc}",
            error_type="upstream_error",
            code="ollama_catalog_unavailable",
        )
    aliases = request.app.state.settings.model_aliases
    return JSONResponse(
        {
            "models": [
                {
                    "name": model.name,
                    "size": model.size,
                    "digest": model.digest,
                    "modified_at": model.modified_at,
                    "details": model.details,
                    "running": model.running,
                    "aliases": sorted(
                        alias for alias, target in aliases.items() if target == model.name
                    ),
                }
                for model in models
            ],
            "aliases": aliases,
        },
        headers=auth.rate_limit.headers(),
    )


@router.get("/admin/models/registry/search")
async def search_registry(
    request: Request,
    auth: AuthDep,
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
):
    if isinstance(auth, JSONResponse):
        return auth
    denied = require_admin(request, auth)
    if denied is not None:
        return denied
    try:
        results = await request.app.state.model_catalog.search_registry(q, limit)
    except Exception as exc:
        return openai_error(
            502,
            f"Could not search ollama.com: {exc}",
            error_type="upstream_error",
            code="ollama_registry_search_failed",
            param="q",
        )
    return JSONResponse(
        {
            "query": q,
            "results": [
                {
                    "name": item.name,
                    "description": item.description,
                    "url": item.url,
                }
                for item in results
            ],
            "source": "https://ollama.com/search",
        },
        headers=auth.rate_limit.headers(),
    )


@router.get("/admin/models/registry/{model_name:path}/tags")
async def registry_model_tags(
    model_name: str,
    request: Request,
    auth: AuthDep,
    limit: int = Query(default=100, ge=1, le=200),
):
    if isinstance(auth, JSONResponse):
        return auth
    denied = require_admin(request, auth)
    if denied is not None:
        return denied
    try:
        tags = await request.app.state.model_catalog.list_registry_tags(model_name, limit)
    except ValueError as exc:
        return openai_error(
            400,
            str(exc),
            error_type="invalid_request_error",
            code="invalid_model_name",
            param="model_name",
        )
    except Exception as exc:
        return openai_error(
            502,
            f"Could not read tags for '{model_name}' from ollama.com: {exc}",
            error_type="upstream_error",
            code="ollama_registry_tags_failed",
            param="model_name",
        )

    return JSONResponse(
        {
            "model": model_name,
            "tags": [
                {
                    "name": item.name,
                    "tag": item.tag,
                    "size": item.size,
                    "size_bytes": item.size_bytes,
                    "digest": item.digest,
                    "context_window": item.context_window,
                    "input_types": list(item.input_types),
                    "updated": item.updated,
                    "url": item.url,
                }
                for item in tags
            ],
        },
        headers=auth.rate_limit.headers(),
    )


@router.post("/admin/models/pull")
async def pull_model(body: PullModelRequest, request: Request, auth: AuthDep):
    if isinstance(auth, JSONResponse):
        return auth
    denied = require_admin(request, auth)
    if denied is not None:
        return denied
    try:
        result = await request.app.state.model_catalog.pull(body.model)
    except Exception as exc:
        return openai_error(
            502,
            f"Ollama could not pull model '{body.model}': {exc}",
            error_type="upstream_error",
            code="model_pull_failed",
            param="model",
        )
    return JSONResponse(result, headers=auth.rate_limit.headers())


@router.post("/admin/models/pull/stream")
async def pull_model_stream(body: PullModelRequest, request: Request, auth: AuthDep):
    if isinstance(auth, JSONResponse):
        return auth
    denied = require_admin(request, auth)
    if denied is not None:
        return denied

    try:
        clean = request.app.state.model_catalog.validate_model_name(body.model)
    except ValueError as exc:
        return openai_error(
            400,
            str(exc),
            error_type="invalid_request_error",
            code="invalid_model_name",
            param="model",
        )

    async def events():
        try:
            async for event in request.app.state.model_catalog.pull_stream(clean):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as exc:
            yield json.dumps(
                {
                    "error": str(exc),
                    "status": "error",
                },
                ensure_ascii=False,
            ) + "\n"

    headers = {
        **auth.rate_limit.headers(),
        "Cache-Control": "no-store",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(events(), media_type="application/x-ndjson", headers=headers)


@router.delete("/admin/models/{model_name:path}")
async def delete_model(model_name: str, request: Request, auth: AuthDep):
    if isinstance(auth, JSONResponse):
        return auth
    denied = require_admin(request, auth)
    if denied is not None:
        return denied
    try:
        await request.app.state.model_catalog.delete(model_name)
    except Exception as exc:
        return openai_error(
            502,
            f"Ollama could not remove model '{model_name}': {exc}",
            error_type="upstream_error",
            code="model_delete_failed",
            param="model",
        )
    return JSONResponse(
        {"deleted": True, "model": model_name},
        headers=auth.rate_limit.headers(),
    )
