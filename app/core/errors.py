from typing import Any

from fastapi.responses import JSONResponse


def openai_error(
    status_code: int,
    message: str,
    *,
    error_type: str,
    code: str,
    param: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "error": {
            "message": message,
            "type": error_type,
            "param": param,
            "code": code,
        }
    }
    return JSONResponse(status_code=status_code, content=body, headers=headers)
