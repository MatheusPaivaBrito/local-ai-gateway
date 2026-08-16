from collections.abc import AsyncIterator
from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.errors import openai_error
from app.domains.model_catalog.domain import ModelNotInstalledError
from app.http.dependencies import AuthDep, DbDep

router = APIRouter()


async def _proxy(
    request: Request,
    endpoint: str,
    auth: AuthDep,
    db: DbDep,
) -> JSONResponse | StreamingResponse:
    if isinstance(auth, JSONResponse):
        return auth
    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        return openai_error(
            400,
            "Request body must be valid JSON.",
            error_type="invalid_request_error",
            code="invalid_json",
        )

    public_model = payload.get("model")
    if not isinstance(public_model, str) or not public_model.strip():
        return openai_error(
            400,
            "Field 'model' is required.",
            error_type="invalid_request_error",
            code="missing_model",
            param="model",
        )

    try:
        if bool(payload.get("stream", False)):
            upstream, _, _ = await request.app.state.inference.open_stream(
                endpoint=endpoint,
                payload=payload,
            )

            async def iterator() -> AsyncIterator[bytes]:
                try:
                    async for chunk in upstream.aiter_bytes():
                        yield chunk
                finally:
                    await upstream.aclose()

            content_type = upstream.headers.get("content-type", "text/event-stream")
            return StreamingResponse(
                iterator(),
                status_code=upstream.status_code,
                media_type=content_type.split(";", 1)[0],
                headers={
                    "x-request-id": request.state.request_id,
                    **auth.rate_limit.headers(),
                },
            )

        result = await request.app.state.inference.generate(
            endpoint=endpoint,
            payload=payload,
            api_key_id=auth.api_key.id,
            db=db,
            request_id=request.state.request_id,
        )
        return JSONResponse(
            status_code=result.status_code,
            content=result.payload,
            headers={
                "x-request-id": request.state.request_id,
                **auth.rate_limit.headers(),
            },
        )
    except ModelNotInstalledError as exc:
        return openai_error(
            404,
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
            code="invalid_request",
            headers=auth.rate_limit.headers(),
        )
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500] if exc.response is not None else str(exc)
        return openai_error(
            502,
            f"Ollama upstream rejected the request: {detail}",
            error_type="upstream_error",
            code="upstream_rejected",
            headers=auth.rate_limit.headers(),
        )
    except Exception as exc:
        return openai_error(
            502,
            f"Ollama upstream unavailable: {exc}",
            error_type="upstream_error",
            code="upstream_unavailable",
            headers=auth.rate_limit.headers(),
        )


@router.post("/v1/responses")
async def responses(request: Request, auth: AuthDep, db: DbDep):
    return await _proxy(request, "/responses", auth, db)


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, auth: AuthDep, db: DbDep):
    return await _proxy(request, "/chat/completions", auth, db)
