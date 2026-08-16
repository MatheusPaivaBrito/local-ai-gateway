from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.domains.model_catalog.domain import (
    InstalledModel,
    ModelNotInstalledError,
    RegistryModel,
    RegistryModelTag,
)
from app.domains.model_catalog.infrastructure import OllamaModelClient, OllamaRegistryClient


class ModelCatalogService:
    def __init__(
        self,
        client: OllamaModelClient,
        aliases: dict[str, str],
        registry: OllamaRegistryClient | None = None,
    ) -> None:
        self.client = client
        self.aliases = aliases
        self.registry = registry

    async def list_models(self) -> list[InstalledModel]:
        installed = await self.client.list_installed()
        try:
            running_raw = await self.client.list_running()
        except Exception:
            running_raw = []
        running_names = {
            str(item.get("name") or item.get("model"))
            for item in running_raw
            if item.get("name") or item.get("model")
        }
        models: list[InstalledModel] = []
        for item in installed:
            name = str(item.get("name") or item.get("model") or "").strip()
            if not name:
                continue
            models.append(
                InstalledModel(
                    name=name,
                    size=int(item["size"]) if item.get("size") is not None else None,
                    digest=str(item["digest"]) if item.get("digest") else None,
                    modified_at=str(item["modified_at"]) if item.get("modified_at") else None,
                    details=dict(item.get("details") or {}),
                    running=name in running_names,
                )
            )
        return sorted(models, key=lambda model: model.name.lower())

    async def installed_names(self) -> set[str]:
        installed = await self.client.list_installed()
        return {
            str(item.get("name") or item.get("model")).strip()
            for item in installed
            if item.get("name") or item.get("model")
        }

    async def resolve(self, requested_model: str, *, require_installed: bool = True) -> str:
        upstream = self.aliases.get(requested_model, requested_model).strip()
        if not require_installed:
            return upstream

        installed = await self.installed_names()
        if upstream in installed:
            return upstream
        latest = f"{upstream}:latest" if ":" not in upstream else upstream
        if latest in installed:
            return latest
        raise ModelNotInstalledError(upstream)

    async def search_registry(self, query: str, limit: int = 20) -> list[RegistryModel]:
        if self.registry is None:
            raise RuntimeError("Ollama registry search is not configured")
        clean = " ".join(query.split())
        if len(clean) < 2:
            return []
        return await self.registry.search(clean, max(1, min(limit, 50)))

    async def list_registry_tags(
        self,
        model: str,
        limit: int = 100,
    ) -> list[RegistryModelTag]:
        if self.registry is None:
            raise RuntimeError("Ollama registry search is not configured")
        clean = self.validate_model_name(model)
        return await self.registry.list_tags(clean, max(1, min(limit, 200)))

    async def pull(self, model: str) -> dict[str, object]:
        clean = self.validate_model_name(model)
        result = await self.client.pull(clean)
        return {"model": clean, "status": result.get("status", "success")}

    async def pull_stream(self, model: str) -> AsyncIterator[dict[str, Any]]:
        clean = self.validate_model_name(model)
        async for event in self.client.pull_stream(clean):
            yield event

    @staticmethod
    def validate_model_name(model: str) -> str:
        clean = model.strip()
        if not clean or len(clean) > 200:
            raise ValueError("Invalid Ollama model name")
        if any(char.isspace() for char in clean) or "://" in clean or clean.startswith("/"):
            raise ValueError("Invalid Ollama model name")
        return clean

    async def delete(self, model: str) -> None:
        clean = self.validate_model_name(model)
        await self.client.delete(clean)

    async def public_model_names(self) -> list[str]:
        installed = await self.installed_names()
        aliases: set[str] = set()
        for alias, upstream in self.aliases.items():
            target = upstream.strip()
            latest = f"{target}:latest" if ":" not in target else target
            if target in installed or latest in installed:
                aliases.add(alias)
        return sorted(installed | aliases)
