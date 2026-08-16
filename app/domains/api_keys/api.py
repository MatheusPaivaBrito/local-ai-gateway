from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.errors import openai_error
from app.domains.api_keys.schemas import CreateApiKeyRequest
from app.http.dependencies import AuthDep, DbDep, require_admin

router = APIRouter()


@router.post("/admin/api-keys")
async def create_admin_api_key(
    body: CreateApiKeyRequest,
    request: Request,
    auth: AuthDep,
    db: DbDep,
):
    if isinstance(auth, JSONResponse):
        return auth
    denied = require_admin(request, auth)
    if denied is not None:
        return denied

    settings = request.app.state.settings
    if body.name.strip() == settings.local_ui_api_key_name:
        return openai_error(
            400,
            f"The name '{settings.local_ui_api_key_name}' is reserved.",
            error_type="invalid_request_error",
            code="reserved_api_key_name",
            param="name",
            headers=auth.rate_limit.headers(),
        )

    api_key, raw_key = await request.app.state.api_keys.create(db, name=body.name)
    return JSONResponse(
        {
            "id": api_key.id,
            "name": api_key.name,
            "api_key": raw_key,
            "key_prefix": api_key.key_prefix,
            "created_at": api_key.created_at.isoformat() if api_key.created_at else None,
        },
        status_code=201,
        headers={**auth.rate_limit.headers(), "Cache-Control": "no-store"},
    )
