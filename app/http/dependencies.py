from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import openai_error
from app.core.security import verify_api_key
from app.domains.api_keys.domain import ApiKeyIdentity
from app.domains.rate_limit.service import RateLimitResult


@dataclass(frozen=True, slots=True)
class AuthContext:
    api_key: ApiKeyIdentity
    rate_limit: RateLimitResult


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async for session in request.app.state.database.session():
        yield session


DbDep = Annotated[AsyncSession, Depends(get_db)]
AuthorizationHeader = Annotated[str | None, Header()]


async def authorize(
    request: Request,
    db: DbDep,
    authorization: AuthorizationHeader = None,
) -> AuthContext | JSONResponse:
    if not authorization or not authorization.startswith("Bearer "):
        return openai_error(
            401,
            "Missing or invalid Authorization header.",
            error_type="authentication_error",
            code="invalid_api_key",
        )

    raw_key = authorization.removeprefix("Bearer ").strip()
    api_key = await request.app.state.api_keys.authenticate(db, raw_key)
    if api_key is None:
        return openai_error(
            401,
            "Invalid API key.",
            error_type="authentication_error",
            code="invalid_api_key",
        )

    rate = await request.app.state.rate_limiter.check(api_key.id)
    if not rate.allowed:
        return openai_error(
            429,
            "Rate limit exceeded.",
            error_type="rate_limit_error",
            code="rate_limit_exceeded",
            headers=rate.headers(),
        )
    return AuthContext(api_key=api_key, rate_limit=rate)


AuthDep = Annotated[AuthContext | JSONResponse, Depends(authorize)]


def is_admin(request: Request, auth: AuthContext) -> bool:
    settings = request.app.state.settings
    bootstrap_key = settings.bootstrap_api_key
    if bootstrap_key and verify_api_key(bootstrap_key, auth.api_key.key_hash):
        return True

    local_ui_key = getattr(request.app.state, "local_ui_api_key", None)
    return bool(
        settings.local_ui_enabled
        and local_ui_key
        and verify_api_key(local_ui_key, auth.api_key.key_hash)
    )


def require_admin(request: Request, auth: AuthContext) -> JSONResponse | None:
    if is_admin(request, auth):
        return None
    return openai_error(
        403,
        "This API key does not have local administration permission.",
        error_type="permission_error",
        code="admin_key_required",
    )
