"""Run FastAPI directly in the local Python environment with auto-reload."""

import uvicorn

from app.core.config import Settings


def main() -> None:
    settings = Settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
