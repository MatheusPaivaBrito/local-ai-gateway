from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

router = APIRouter(include_in_schema=False)
UI_FILE = Path(__file__).resolve().parents[1] / "ui" / "index.html"


@router.get("/")
async def root() -> RedirectResponse:
    return RedirectResponse(url="/ui")


@router.get("/ui")
async def ui() -> FileResponse:
    return FileResponse(UI_FILE, media_type="text/html")
