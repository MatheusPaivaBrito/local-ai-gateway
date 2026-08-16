from importlib import import_module


def test_agents_vertical_slice_imports_repository_and_service() -> None:
    repository = import_module("app.domains.agents.repository")
    service = import_module("app.domains.agents.service")
    assert hasattr(repository, "AgentRepository")
    assert hasattr(service, "AgentService")


def test_all_vertical_slice_api_modules_are_importable() -> None:
    for module in (
        "app.domains.agents.api",
        "app.domains.api_keys.api",
        "app.domains.inference.api",
        "app.domains.model_catalog.api",
        "app.domains.rag.api",
        "app.domains.usage.api",
    ):
        assert import_module(module) is not None
