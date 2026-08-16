import pytest

from app.domains.model_catalog.domain import RegistryModel
from app.domains.model_catalog.infrastructure import parse_registry_search_html
from app.domains.model_catalog.service import ModelCatalogService


class FakeModelClient:
    async def list_installed(self):
        return []

    async def list_running(self):
        return []

    async def pull_stream(self, model: str):
        yield {"status": "pulling manifest"}
        yield {"status": "downloading", "completed": 50, "total": 100}
        yield {"status": "success"}


class FakeRegistryClient:
    async def search(self, query: str, limit: int = 20):
        return [RegistryModel(name=f"{query}-model")][:limit]


def test_registry_parser_reads_official_and_community_models() -> None:
    html = """
    <html><body>
      <a href="/library/qwen3.8">
        <div><strong>qwen3.8</strong><span>vision tools 27b</span></div>
      </a>
      <a href="/alice/qwen-tuned"><div>alice/qwen-tuned <span>coding model</span></div></a>
      <a href="/search?q=qwen">search</a>
      <a href="/library/qwen3.8">qwen3.8 duplicate</a>
    </body></html>
    """
    results = parse_registry_search_html(html)
    assert [item.name for item in results] == ["qwen3.8", "alice/qwen-tuned"]
    assert results[0].url == "https://ollama.com/library/qwen3.8"
    assert "vision" in results[0].description


@pytest.mark.asyncio
async def test_catalog_searches_remote_registry() -> None:
    service = ModelCatalogService(
        FakeModelClient(),  # type: ignore[arg-type]
        {},
        registry=FakeRegistryClient(),  # type: ignore[arg-type]
    )
    results = await service.search_registry("qwen", 10)
    assert results[0].name == "qwen-model"


@pytest.mark.asyncio
async def test_catalog_streams_pull_progress() -> None:
    service = ModelCatalogService(FakeModelClient(), {})  # type: ignore[arg-type]
    events = [event async for event in service.pull_stream("qwen3:4b")]
    assert events[-1]["status"] == "success"
    assert events[1]["completed"] == 50
