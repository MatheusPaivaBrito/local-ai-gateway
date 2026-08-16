import pytest

from app.domains.model_catalog.domain import ModelNotInstalledError
from app.domains.model_catalog.service import ModelCatalogService


class FakeClient:
    async def list_installed(self):
        return [{"name": "qwen3:4b"}, {"name": "embeddinggemma:latest"}]

    async def list_running(self):
        return []


@pytest.mark.asyncio
async def test_catalog_accepts_installed_model_and_latest_shorthand() -> None:
    service = ModelCatalogService(FakeClient(), {})  # type: ignore[arg-type]
    assert await service.resolve("qwen3:4b") == "qwen3:4b"
    assert await service.resolve("embeddinggemma") == "embeddinggemma:latest"


@pytest.mark.asyncio
async def test_catalog_resolves_configured_alias() -> None:
    client = FakeClient()
    service = ModelCatalogService(  # type: ignore[arg-type]
        client,
        {"gpt-5-nano": "qwen3:4b"},
    )
    assert await service.resolve("gpt-5-nano") == "qwen3:4b"


@pytest.mark.asyncio
async def test_catalog_rejects_missing_model() -> None:
    service = ModelCatalogService(FakeClient(), {})  # type: ignore[arg-type]
    with pytest.raises(ModelNotInstalledError):
        await service.resolve("missing")
