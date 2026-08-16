from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, unquote, urljoin

import httpx

from app.domains.model_catalog.domain import RegistryModel, RegistryModelTag


class _OllamaSearchParser(HTMLParser):
    """Best-effort parser for the public ollama.com search page."""

    _reserved_roots = {
        "account",
        "api",
        "blog",
        "contact",
        "docs",
        "download",
        "library",
        "login",
        "pricing",
        "privacy",
        "search",
        "settings",
        "signin",
        "terms",
    }

    def __init__(self, base_url: str = "https://ollama.com") -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url.rstrip("/")
        self._active: dict[str, Any] | None = None
        self.results: list[RegistryModel] = []
        self._seen: set[str] = set()

    @classmethod
    def _name_from_href(cls, href: str) -> str | None:
        if not href.startswith("/"):
            return None
        path = href.split("?", 1)[0].split("#", 1)[0].strip("/")
        if not path:
            return None

        parts = path.split("/")
        if parts[0] == "library" and len(parts) == 2:
            return unquote(parts[1])
        if len(parts) == 2 and parts[0] not in cls._reserved_roots:
            return unquote(f"{parts[0]}/{parts[1]}")
        return None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._active is not None or tag != "a":
            return
        href = dict(attrs).get("href") or ""
        name = self._name_from_href(href)
        if name:
            self._active = {"name": name, "href": href, "text": []}

    def handle_data(self, data: str) -> None:
        if self._active is not None:
            self._active["text"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._active is None or tag != "a":
            return

        name = str(self._active["name"])
        text = " ".join(" ".join(self._active["text"]).split())
        description = text
        if description.lower().startswith(name.lower()):
            description = description[len(name) :].strip(" -–—•")
        if name not in self._seen:
            self._seen.add(name)
            self.results.append(
                RegistryModel(
                    name=name,
                    description=description[:240],
                    url=urljoin(self.base_url + "/", str(self._active["href"])),
                )
            )
        self._active = None


class _OllamaTagsParser(HTMLParser):
    _size_re = re.compile(r"^(\d+(?:\.\d+)?)\s*(KB|MB|GB|TB)$", re.IGNORECASE)
    _context_re = re.compile(
        r"^(\d+(?:\.\d+)?\s*[KMB]?)\s+context\s+window$",
        re.IGNORECASE,
    )
    _digest_re = re.compile(r"^[0-9a-f]{12,64}$", re.IGNORECASE)

    def __init__(self, model: str, base_url: str = "https://ollama.com") -> None:
        super().__init__(convert_charrefs=True)
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self._active: dict[str, Any] | None = None
        self.results: list[RegistryModelTag] = []
        self._seen: set[str] = set()

    @staticmethod
    def _candidate_from_href(href: str) -> str | None:
        if not href.startswith("/"):
            return None
        path = href.split("?", 1)[0].split("#", 1)[0].strip("/")
        parts = path.split("/") if path else []
        if len(parts) == 2 and parts[0] == "library":
            candidate = unquote(parts[1])
            return candidate if ":" in candidate else None
        if len(parts) == 2 and parts[0] != "library":
            candidate = unquote(f"{parts[0]}/{parts[1]}")
            return candidate if ":" in candidate else None
        return None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._active is not None or tag != "a":
            return
        href = dict(attrs).get("href") or ""
        candidate = self._candidate_from_href(href)
        if not candidate or not candidate.startswith(f"{self.model}:"):
            return
        self._active = {"name": candidate, "href": href, "text": []}

    def handle_data(self, data: str) -> None:
        if self._active is not None:
            self._active["text"].append(data)

    @classmethod
    def _size_bytes(cls, size: str | None) -> int | None:
        if not size:
            return None
        match = cls._size_re.match(size.strip())
        if not match:
            return None
        value = float(match.group(1))
        unit = match.group(2).upper()
        factor = {
            "KB": 1024,
            "MB": 1024**2,
            "GB": 1024**3,
            "TB": 1024**4,
        }[unit]
        return int(value * factor)

    def handle_endtag(self, tag: str) -> None:
        if self._active is None or tag != "a":
            return

        name = str(self._active["name"])
        if name in self._seen:
            self._active = None
            return

        text = " ".join(" ".join(self._active["text"]).split())
        parts = [part.strip() for part in re.split(r"[•·]", text) if part.strip()]
        size = digest = context_window = updated = None
        input_types: tuple[str, ...] = ()

        for part in parts:
            clean = " ".join(part.split())
            if self._size_re.match(clean):
                size = clean.replace(" ", "")
                continue
            context_match = self._context_re.match(clean)
            if context_match:
                context_window = context_match.group(1).replace(" ", "")
                continue
            if clean.lower().endswith(" input"):
                raw_inputs = clean[:-6].strip()
                input_types = tuple(
                    item.strip() for item in raw_inputs.split(",") if item.strip()
                )
                continue
            if self._digest_re.match(clean):
                digest = clean
                continue
            if clean.endswith("ago"):
                updated = clean

        if digest is None:
            digest_match = re.search(r"\b[0-9a-f]{12,64}\b", text, re.IGNORECASE)
            if digest_match:
                digest = digest_match.group(0)

        tag_name = name[len(self.model) + 1 :]
        self._seen.add(name)
        self.results.append(
            RegistryModelTag(
                name=name,
                tag=tag_name,
                size=size,
                size_bytes=self._size_bytes(size),
                digest=digest,
                context_window=context_window,
                input_types=input_types,
                updated=updated,
                url=urljoin(self.base_url + "/", str(self._active["href"])),
            )
        )
        self._active = None


class OllamaRegistryClient:
    def __init__(self, base_url: str = "https://ollama.com") -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=True,
            headers={"User-Agent": "local-ai-gateway/0.4.1"},
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def search(self, query: str, limit: int = 20) -> list[RegistryModel]:
        clean = " ".join(query.split())
        if len(clean) < 2:
            return []
        response = await self.client.get("/search", params={"q": clean})
        response.raise_for_status()
        parser = _OllamaSearchParser(self.base_url)
        parser.feed(response.text)
        return parser.results[:limit]

    async def list_tags(self, model: str, limit: int = 100) -> list[RegistryModelTag]:
        clean = model.strip()
        if not clean:
            return []
        if ":" in clean:
            clean = clean.split(":", 1)[0]

        if "/" in clean:
            owner, model_name = clean.split("/", 1)
            path = f"/{quote(owner, safe='')}/{quote(model_name, safe='')}/tags"
        else:
            path = f"/library/{quote(clean, safe='')}/tags"

        response = await self.client.get(path)
        response.raise_for_status()
        parser = _OllamaTagsParser(clean, self.base_url)
        parser.feed(response.text)
        return parser.results[:limit]


class OllamaModelClient:
    def __init__(self, base_url: str) -> None:
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(300.0, connect=5.0),
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def list_installed(self) -> list[dict[str, Any]]:
        response = await self.client.get("/api/tags", timeout=10.0)
        response.raise_for_status()
        payload = response.json()
        return list(payload.get("models") or [])

    async def list_running(self) -> list[dict[str, Any]]:
        response = await self.client.get("/api/ps", timeout=10.0)
        response.raise_for_status()
        payload = response.json()
        return list(payload.get("models") or [])

    async def pull(self, model: str) -> dict[str, Any]:
        response = await self.client.post(
            "/api/pull",
            json={"model": model, "stream": False},
            timeout=None,
        )
        response.raise_for_status()
        return response.json()

    async def pull_stream(self, model: str) -> AsyncIterator[dict[str, Any]]:
        async with self.client.stream(
            "POST",
            "/api/pull",
            json={"model": model, "stream": True},
            timeout=None,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    yield {"status": line.strip()}
                    continue
                if isinstance(payload, dict):
                    yield payload

    async def delete(self, model: str) -> None:
        response = await self.client.request("DELETE", "/api/delete", json={"model": model})
        response.raise_for_status()


# Exposed for focused parser tests without making them part of the domain API.
def parse_registry_search_html(html: str) -> list[RegistryModel]:
    parser = _OllamaSearchParser()
    parser.feed(html)
    return parser.results


def parse_registry_tags_html(html: str, model: str) -> list[RegistryModelTag]:
    parser = _OllamaTagsParser(model)
    parser.feed(html)
    return parser.results
